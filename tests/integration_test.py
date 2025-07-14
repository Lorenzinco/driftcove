# tests/integration_test.py
import os
import requests
import tempfile
import subprocess
import time

API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("API_TOKEN", "supersecuretoken")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

def wait_for_api():
    for _ in range(10):
        try:
            r = requests.get(f"{API_URL}/status", headers=HEADERS)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise Exception("API did not become ready")

def create_peer(name: str, subnet: str):
    r = requests.post(f"{API_URL}/peer/create?username={name}&subnet={subnet}", headers=HEADERS)
    r.raise_for_status()
    return r.json()["configuration"]

def run_client(config: str, name: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "wg0.conf")
        with open(config_path, "w") as f:
            f.write(config)

        subprocess.run([
            "docker", "run", "--rm", "--name", name,
            "--cap-add=NET_ADMIN",
            f"-v{config_path}:/etc/wireguard/wg0.conf",
            "linuxserver/wireguard", "bash", "-c",
            "wg-quick up wg0 && sleep 10 && ping -c 3 10.128.0.3"
        ], check=True)

def main():
    wait_for_api()

    print("Creating peers...")
    cfg1 = create_peer("client1", "10.128.0.0/9")
    cfg2 = create_peer("client2", "10.128.0.0/9")

    print("Running containers...")
    run_client(cfg1, "client1")  # Will ping 10.128.0.3 inside the container

if __name__ == "__main__":
    main()