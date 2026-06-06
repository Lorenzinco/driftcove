import json as jsonlib
import os
import re
import socket
import subprocess
import tempfile
import textwrap
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_TOKEN = os.environ.get("API_TOKEN", "supersecuretoken")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
DEFAULT_SUBNET = "10.128.0.0/9"


def run(command: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=check,
    )


def docker(*args: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", *args], timeout=timeout, check=check)


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def address_from_config(config: str) -> str:
    match = re.search(r"^Address\s*=\s*([^\s/]+)", config, re.MULTILINE)
    assert match, f"WireGuard config did not contain an Address line:\n{config}"
    return match.group(1)


def wg_quick_client_config(config: str) -> str:
    """Make API-generated configs suitable for wg-quick inside Linux client containers."""
    return re.sub(r"^(Address\s*=\s*)([^\s/]+)\s*$", r"\1\2/32", config, count=1, flags=re.MULTILINE)


class JsonResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self.body = body

    def json(self):
        return jsonlib.loads(self.body.decode("utf-8"))


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, **kwargs) -> JsonResponse:
        params = kwargs.pop("params", None)
        json_body = kwargs.pop("json", None)
        if kwargs:
            raise TypeError(f"unsupported request arguments: {sorted(kwargs)}")

        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        body = None
        headers = dict(HEADERS)
        if json_body is not None:
            body = jsonlib.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return JsonResponse(response.status, response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc

    def wait_until_ready(self) -> None:
        deadline = time.monotonic() + 90
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                if self.request("GET", "/network/status").json() == {"status": "running"}:
                    return
            except (OSError, RuntimeError, AssertionError) as exc:
                last_error = exc
            time.sleep(1)
        raise RuntimeError(f"backend API did not become ready: {last_error}")

    def create_subnet(self, subnet: str, name: str | None = None) -> None:
        self.request(
            "POST",
            "/subnet/create",
            json={
                "subnet": subnet,
                "name": name or subnet,
                "description": "created by backend_network_policy_test.py",
            },
        )

    def create_peer(self, username: str, subnet: str = DEFAULT_SUBNET, address: str | None = None) -> str:
        params = {"username": username, "subnet": subnet}
        if address is not None:
            params["address"] = address
        return self.request("POST", "/peer/create", params=params).json()["configuration"]

    def connect_peers_p2p(self, peer1: str, peer2: str) -> None:
        self.request("POST", "/peer/connect", params={"peer1_username": peer1, "peer2_username": peer2})

    def disconnect_peers_p2p(self, peer1: str, peer2: str) -> None:
        self.request("DELETE", "/peer/disconnect", params={"peer1_username": peer1, "peer2_username": peer2})

    def create_service(self, name: str, host_username: str, port: int, protocol: str = "tcp") -> None:
        self.request(
            "POST",
            "/service/create",
            params={
                "service_name": name,
                "department": "test",
                "username": host_username,
                "port": port,
                "protocol": protocol,
                "description": "created by backend_network_policy_test.py",
            },
        )

    def connect_peer_to_service(self, username: str, service_name: str) -> None:
        self.request("POST", "/service/connect", params={"username": username, "service_name": service_name})

    def disconnect_peer_from_service(self, username: str, service_name: str) -> None:
        self.request("DELETE", "/service/disconnect", params={"username": username, "service_name": service_name})

    def make_peer_public_in_subnet(self, username: str, subnet: str) -> None:
        self.request("POST", "/subnet/connect", params={"username": username, "subnet": subnet})

    def make_peer_private_in_subnet(self, username: str, subnet: str) -> None:
        self.request("DELETE", "/subnet/disconnect", params={"username": username, "subnet": subnet})


class DockerHarness:
    def __init__(self):
        suffix = uuid.uuid4().hex[:10]
        self.network = f"dcv-policy-{suffix}"
        self.backend = f"dcv-backend-{suffix}"
        self.backend_image = f"dcv-backend-policy:{suffix}"
        self.client_image = f"dcv-wg-client-policy:{suffix}"
        self.api_port = free_local_port()
        self.tempdir = tempfile.TemporaryDirectory(prefix="dcv-policy-")
        self.root = Path(self.tempdir.name)
        self.peer_configs: dict[str, str] = {}
        self.peer_addresses: dict[str, str] = {}
        self.started_peers: set[str] = set()

    @property
    def api(self) -> ApiClient:
        return ApiClient(f"http://127.0.0.1:{self.api_port}")

    def setup(self) -> None:
        (self.root / "wireguard").mkdir()
        (self.root / "db").mkdir()
        (self.root / "captures").mkdir()

        docker("build", "-t", self.backend_image, "backend", timeout=240)
        docker("build", "-t", self.client_image, "backend/tests/docker/wg-client", timeout=240)
        docker("network", "create", self.network)
        docker(
            "run",
            "-d",
            "--name",
            self.backend,
            "--network",
            self.network,
            "--cap-add=NET_ADMIN",
            "--cap-add=SYS_MODULE",
            "--sysctl",
            "net.ipv4.ip_forward=1",
            "--sysctl",
            "net.ipv4.conf.all.rp_filter=0",
            "--sysctl",
            "net.ipv4.conf.default.rp_filter=0",
            "-e",
            "WG_IF=wg0",
            "-e",
            "WG_UDP_PORT=1194",
            "-e",
            "WG_ADDRESS_CIDR=10.128.0.1/24",
            "-e",
            f"WG_DEFAULT_SUBNET={DEFAULT_SUBNET}",
            "-e",
            "WAN_IF=eth0",
            "-e",
            "WG_BACKEND_TCP_PORT=8000",
            "-e",
            f"ENDPOINT={self.backend}",
            "-e",
            f"API_TOKEN={API_TOKEN}",
            "-p",
            f"127.0.0.1:{self.api_port}:8000",
            "-v",
            f"{self.root / 'wireguard'}:/etc/wireguard",
            "-v",
            f"{self.root / 'db'}:/home/db",
            "-v",
            f"{self.root / 'captures'}:/var/log/captures",
            self.backend_image,
            timeout=120,
        )
        try:
            self.api.wait_until_ready()
        except Exception:
            logs = docker("logs", self.backend, check=False).stdout
            raise RuntimeError(f"backend failed to become ready; logs:\n{logs}")

    def cleanup(self) -> None:
        for peer in list(self.started_peers):
            docker("rm", "-f", self.container_name(peer), timeout=30, check=False)
        docker("rm", "-f", self.backend, timeout=30, check=False)
        docker("network", "rm", self.network, timeout=30, check=False)
        docker("image", "rm", "-f", self.backend_image, self.client_image, timeout=120, check=False)
        self.tempdir.cleanup()

    def container_name(self, peer_name: str) -> str:
        return f"{self.network}-{peer_name}"

    def add_peer(self, username: str, *, subnet: str = DEFAULT_SUBNET, address: str | None = None) -> str:
        config = self.api.create_peer(username, subnet=subnet, address=address)
        self.peer_configs[username] = config
        self.peer_addresses[username] = address_from_config(config)
        return config

    def add_started_peer(self, username: str, *, subnet: str = DEFAULT_SUBNET, address: str | None = None) -> str:
        self.add_peer(username, subnet=subnet, address=address)
        self.start_peer(username)
        return self.peer_addresses[username]

    def start_peer(self, username: str) -> None:
        config_path = self.root / f"{username}.conf"
        config_path.write_text(wg_quick_client_config(self.peer_configs[username]), encoding="utf-8")
        docker(
            "run",
            "-d",
            "--name",
            self.container_name(username),
            "--network",
            self.network,
            "--cap-add=NET_ADMIN",
            "--cap-add=SYS_MODULE",
            "--sysctl",
            "net.ipv4.conf.all.src_valid_mark=1",
            "-v",
            f"{config_path}:/etc/wireguard/wg0.conf:ro",
            self.client_image,
            "sh",
            "-c",
            "wg-quick up wg0 && sleep infinity",
            timeout=120,
        )
        self.started_peers.add(username)
        # Give wg-quick route setup and the first handshake a moment before policy checks.
        time.sleep(1)
        result = self.exec(username, "wg show wg0", timeout=10, check=False)
        if result.returncode != 0:
            logs = docker("logs", self.container_name(username), check=False).stdout
            raise RuntimeError(f"peer {username} did not bring wg0 up:\n{logs}")

    def exec(self, peer: str, command: str, *, timeout: int = 20, check: bool = True) -> subprocess.CompletedProcess[str]:
        return docker("exec", self.container_name(peer), "sh", "-c", command, timeout=timeout, check=check)

    def start_tcp_server(self, peer: str, port: int) -> None:
        address = self.peer_addresses[peer]
        script = textwrap.dedent(
            f"""
            import socketserver

            class Handler(socketserver.BaseRequestHandler):
                def handle(self):
                    self.request.recv(1024)
                    self.request.sendall(b"ok")

            with socketserver.ThreadingTCPServer(("{address}", {port}), Handler) as server:
                server.allow_reuse_address = True
                server.serve_forever()
            """
        ).strip()
        encoded = script.replace("'", "'\"'\"'")
        self.exec(peer, f"nohup python3 -c '{encoded}' >/tmp/server-{port}.log 2>&1 &")
        time.sleep(0.5)

    def can_connect(self, src_peer: str, dst_peer: str, port: int, *, timeout_seconds: float = 1.5) -> bool:
        dst_ip = self.peer_addresses[dst_peer]
        script = textwrap.dedent(
            f"""
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout({timeout_seconds})
            try:
                sock.connect(("{dst_ip}", {port}))
                sock.sendall(b"ping")
                sock.recv(16)
            except Exception as exc:
                print(type(exc).__name__ + ": " + str(exc))
                raise SystemExit(1)
            finally:
                sock.close()
            """
        ).strip().replace("'", "'\"'\"'")
        result = self.exec(src_peer, f"python3 -c '{script}'", timeout=10, check=False)
        return result.returncode == 0

    def assert_can_connect(self, src_peer: str, dst_peer: str, port: int) -> None:
        deadline = time.monotonic() + 12
        last_output = ""
        while time.monotonic() < deadline:
            if self.can_connect(src_peer, dst_peer, port):
                return
            result = self.exec(src_peer, "true", check=False)
            last_output = result.stdout
            time.sleep(1)
        raise AssertionError(f"expected {src_peer} to connect to {dst_peer}:{port}; last output: {last_output}")

    def assert_cannot_connect(self, src_peer: str, dst_peer: str, port: int) -> None:
        # Retry a couple of times to avoid asserting during brief rule/conntrack transitions.
        for _ in range(3):
            if not self.can_connect(src_peer, dst_peer, port):
                return
            time.sleep(1)
        raise AssertionError(f"expected {src_peer} to be blocked from {dst_peer}:{port}")


@unittest.skipUnless(
    os.environ.get("RUN_BACKEND_DOCKER_TESTS") == "1",
    "Docker WireGuard policy tests are opt-in for local runs. GitHub Actions sets RUN_BACKEND_DOCKER_TESTS=1.",
)
class BackendNetworkPolicyTest(unittest.TestCase):
    harness: DockerHarness

    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = DockerHarness()
        cls.harness.setup()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.harness.cleanup()

    def test_default_policy_blocks_peer_to_peer_traffic_on_vpn(self):
        harness = self.harness
        harness.add_started_peer("default-a")
        harness.add_started_peer("default-b")
        harness.start_tcp_server("default-a", 8080)
        harness.start_tcp_server("default-b", 8080)
        harness.start_tcp_server("default-b", 9090)

        with self.subTest("a cannot reach b service port"):
            harness.assert_cannot_connect("default-a", "default-b", 8080)
        with self.subTest("a cannot reach b alternate port"):
            harness.assert_cannot_connect("default-a", "default-b", 9090)
        with self.subTest("b cannot reach a"):
            harness.assert_cannot_connect("default-b", "default-a", 8080)

    def test_p2p_policy_allows_all_ports_bidirectionally_and_revokes(self):
        harness = self.harness
        harness.add_started_peer("p2p-a")
        harness.add_started_peer("p2p-b")
        harness.start_tcp_server("p2p-a", 8080)
        harness.start_tcp_server("p2p-b", 8080)
        harness.start_tcp_server("p2p-b", 9090)

        with self.subTest("blocked before p2p grant"):
            harness.assert_cannot_connect("p2p-a", "p2p-b", 8080)

        harness.api.connect_peers_p2p("p2p-a", "p2p-b")
        with self.subTest("a can reach b declared service-like port"):
            harness.assert_can_connect("p2p-a", "p2p-b", 8080)
        with self.subTest("a can reach b arbitrary alternate port"):
            harness.assert_can_connect("p2p-a", "p2p-b", 9090)
        with self.subTest("b can reach a after bidirectional p2p grant"):
            harness.assert_can_connect("p2p-b", "p2p-a", 8080)

        harness.api.disconnect_peers_p2p("p2p-a", "p2p-b")
        with self.subTest("p2p revoke blocks new traffic again"):
            harness.assert_cannot_connect("p2p-a", "p2p-b", 8080)

    def test_peer_to_service_policy_allows_only_service_port_and_revokes(self):
        harness = self.harness
        harness.add_started_peer("svc-client")
        harness.add_started_peer("svc-host")
        harness.start_tcp_server("svc-client", 8080)
        harness.start_tcp_server("svc-host", 8080)
        harness.start_tcp_server("svc-host", 9090)

        harness.api.create_service("svc-http", "svc-host", 8080, protocol="tcp")
        with self.subTest("service client blocked before explicit service link"):
            harness.assert_cannot_connect("svc-client", "svc-host", 8080)

        harness.api.connect_peer_to_service("svc-client", "svc-http")
        with self.subTest("client reaches the exact service port"):
            harness.assert_can_connect("svc-client", "svc-host", 8080)
        with self.subTest("client cannot reach a different host port"):
            harness.assert_cannot_connect("svc-client", "svc-host", 9090)
        with self.subTest("service host does not get reverse initiation rights"):
            harness.assert_cannot_connect("svc-host", "svc-client", 8080)

        harness.api.disconnect_peer_from_service("svc-client", "svc-http")
        with self.subTest("service revoke blocks the service port again"):
            harness.assert_cannot_connect("svc-client", "svc-host", 8080)

    def test_private_subnet_members_are_not_reachable_by_containment_only(self):
        harness = self.harness
        subnet = "10.201.0.0/24"
        harness.api.create_subnet(subnet, name="private-subnet-policy")
        harness.add_started_peer("private-a", subnet=subnet, address="10.201.0.10")
        harness.add_started_peer("private-b", subnet=subnet, address="10.201.0.11")
        harness.start_tcp_server("private-a", 8080)
        harness.start_tcp_server("private-b", 8080)

        with self.subTest("peer inside subnet is not public by default"):
            harness.assert_cannot_connect("private-b", "private-a", 8080)
        with self.subTest("private subnet isolation is symmetric"):
            harness.assert_cannot_connect("private-a", "private-b", 8080)

    def test_public_subnet_guest_can_be_reached_but_can_initiate_only_to_public_guests(self):
        harness = self.harness
        subnet = "10.202.0.0/24"
        harness.api.create_subnet(subnet, name="public-subnet-policy")
        harness.add_started_peer("pub-a", subnet=subnet, address="10.202.0.10")
        harness.add_started_peer("priv-b", subnet=subnet, address="10.202.0.11")
        harness.add_started_peer("pub-c", subnet=subnet, address="10.202.0.12")
        harness.start_tcp_server("pub-a", 8080)
        harness.start_tcp_server("priv-b", 8080)
        harness.start_tcp_server("pub-c", 8080)

        harness.api.make_peer_public_in_subnet("pub-a", subnet)
        with self.subTest("private member can initiate to public guest"):
            harness.assert_can_connect("priv-b", "pub-a", 8080)
        with self.subTest("public guest cannot initiate to private member"):
            harness.assert_cannot_connect("pub-a", "priv-b", 8080)
        with self.subTest("another private member can also initiate to the public guest"):
            harness.assert_can_connect("pub-c", "pub-a", 8080)

        harness.api.make_peer_public_in_subnet("pub-c", subnet)
        with self.subTest("public guest can initiate to another public guest"):
            harness.assert_can_connect("pub-a", "pub-c", 8080)
        with self.subTest("public guest reachability is bidirectional between public guests"):
            harness.assert_can_connect("pub-c", "pub-a", 8080)

    def test_removing_public_subnet_guest_restores_private_reachability_policy(self):
        harness = self.harness
        subnet = "10.203.0.0/24"
        harness.api.create_subnet(subnet, name="public-revoke-policy")
        harness.add_started_peer("rev-public", subnet=subnet, address="10.203.0.10")
        harness.add_started_peer("rev-private", subnet=subnet, address="10.203.0.11")
        harness.start_tcp_server("rev-public", 8080)

        harness.api.make_peer_public_in_subnet("rev-public", subnet)
        with self.subTest("public guest is reachable before revoke"):
            harness.assert_can_connect("rev-private", "rev-public", 8080)

        harness.api.make_peer_private_in_subnet("rev-public", subnet)
        with self.subTest("public revoke makes peer unreachable again"):
            harness.assert_cannot_connect("rev-private", "rev-public", 8080)


if __name__ == "__main__":
    unittest.main()
