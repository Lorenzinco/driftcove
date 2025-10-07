import subprocess
from typing import Iterable
from backend.core.logger import logger as logging
import ipaddress
import json
import re

NFT_BIN = "nft"

def _nft_batch(lines: Iterable[str]) -> None:
    script = "\n".join(lines) + "\n"
    try:
        subprocess.run([NFT_BIN, "-f", "-"], input=script.encode(), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        logging.error("nft batch failed: %s\n--- batch ---\n%s",
                      e.stderr.decode(errors="ignore"), script)
        raise

def _nft_try(cmd: str) -> None:
    proc = subprocess.run([NFT_BIN, *cmd.split()],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        logging.debug("nft try failed (ignored): %s -> %s", cmd, proc.stderr.strip())

def _slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s)

# ---------- Helpers: delete by handle (rules cannot be deleted by spec) ----------

def _delete_rule_by_match(chain: str, pattern: str) -> None:
    try:
        out = subprocess.check_output([NFT_BIN, "-a", "list", "chain", "inet", "dcv", chain], text=True)
    except subprocess.CalledProcessError:
        return
    for line in out.splitlines():
        if re.search(pattern, line):
            m = re.search(r"handle\s+(\d+)", line)
            if m:
                _nft_try(f"delete rule inet dcv {chain} handle {m.group(1)}")

# ---------- Flush & reseed only inet/dcv ----------

def flush_dcv(wg_if: str = "wg0") -> None:
    _nft_try("delete table inet dcv")
    ensure_table_and_chain(wg_if=wg_if)


def _try_conntrack(args: list[str]) -> None:
    try:
        subprocess.run(["conntrack", *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        logging.debug("conntrack not found; skipping flush")
    except subprocess.CalledProcessError as e:
        logging.debug("conntrack flush failed (ignored): %s %s", args, getattr(e, "stderr", ""))

def flush_conntrack_for_ip(ip: str) -> None:
    # Decide family
    fam = "ipv6" if ":" in ip else "ipv4"
    _try_conntrack(["-D", "-f", fam, "-s", ip])
    _try_conntrack(["-D", "-f", fam, "-d", ip])

def flush_conntrack_for_prefix(cidr: str, allow_large_prefix: bool = False) -> None:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        logging.debug("invalid CIDR %s; skipping conntrack flush", cidr)
        return
    # Skip very broad prefixes unless explicitly allowed
    if not allow_large_prefix:
        if (net.version == 4 and net.prefixlen < 24) or (net.version == 6 and net.prefixlen < 64):
            logging.debug("CIDR %s too broad; skipping conntrack flush", cidr)
            return
    fam = "ipv6" if net.version == 6 else "ipv4"
    _try_conntrack(["-D", "-f", fam, "-s", cidr])
    _try_conntrack(["-D", "-f", fam, "-d", cidr])

# ---------- Snapshot / Restore ----------

def backup_dcv_table() -> str:
    try:
        return subprocess.check_output([NFT_BIN, "list", "table", "inet", "dcv"], text=True)
    except subprocess.CalledProcessError:
        return "add table inet dcv\n"

def restore_dcv_table(dcv_text: str) -> None:
    _nft_try("delete table inet dcv")
    subprocess.run([NFT_BIN, "-f", "-"], input=dcv_text, text=True, check=True)

# ---------- Base ensure (idempotent) ----------

def ensure_table_and_chain(wg_if: str = "wg0", wg_server_ip: str = "10.128.0.1") -> None:
    _nft_try("add table inet dcv")

    # Sets
    _nft_try("add set inet dcv p2p_links { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv admin_links { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv admin_peer2cidr { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv blocked_pairs { type ipv4_addr . ipv4_addr; flags interval; }")

    # Per-protocol service sets
    _nft_try("add set inet dcv svc_guest_tcp { type ipv4_addr . ipv4_addr . inet_service; flags interval; }")
    _nft_try("add set inet dcv svc_guest_udp { type ipv4_addr . ipv4_addr . inet_service; flags interval; }")
    _nft_try("add set inet dcv svc_pairs_tcp { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv svc_pairs_udp { type ipv4_addr . ipv4_addr; flags interval; }")

    # Chains
    _nft_try('add chain inet dcv input   { type filter hook input   priority 0; policy accept; }')
    _nft_try('add chain inet dcv forward { type filter hook forward priority 0; policy accept; }')
    _nft_try('add chain inet dcv fwd_est')
    _nft_try('add chain inet dcv wg')
    _nft_try('add chain inet dcv wg_base')
    _nft_try('add chain inet dcv wg_allow')

    # INPUT
    _nft_try('flush chain inet dcv input')
    _nft_try('add rule inet dcv input ct state established,related accept')
    _nft_try(f'add rule inet dcv input iifname "{wg_if}" ip daddr {wg_server_ip} icmp type echo-request accept')

    # FORWARD (static order)
    _nft_try('flush chain inet dcv forward')
    _nft_try('add rule inet dcv forward ip saddr . ip daddr @blocked_pairs drop')  # panic drop
    _nft_try('add rule inet dcv forward jump fwd_est')                             # always before wg
    _nft_try(f'add rule inet dcv forward iifname "{wg_if}" goto wg')               # footer stays last
    _nft_try(f'add rule inet dcv forward oifname "{wg_if}" goto wg')

    # FWD_EST (constrained EST/REL acceptance by original tuple)
    _nft_try('flush chain inet dcv fwd_est')
    _nft_try('add rule inet dcv fwd_est ct state established,related '
             'ct original ip saddr . ct original ip daddr @admin_peer2cidr accept')
    _nft_try('add rule inet dcv fwd_est ct state established,related '
             'ct original ip saddr . ct original ip daddr @admin_links accept')
    _nft_try('add rule inet dcv fwd_est ct state established,related '
             'ct original ip saddr . ct original ip daddr @p2p_links accept')
    # Per-proto EST/REL for service flows
    _nft_try('add rule inet dcv fwd_est ct state established,related ct original protocol tcp '
             'ct original ip saddr . ct original ip daddr @svc_pairs_tcp accept')
    _nft_try('add rule inet dcv fwd_est ct state established,related ct original protocol udp '
             'ct original ip saddr . ct original ip daddr @svc_pairs_udp accept')

    # WG pipeline
    # base -> allow -> drop
    _nft_try('flush chain inet dcv wg')
    _nft_try('add rule inet dcv wg jump wg_base')
    _nft_try('add rule inet dcv wg jump wg_allow')
    _nft_try('add rule inet dcv wg counter drop')

    # NEW acceptance (set-based) — only NEW goes here
    _nft_try('flush chain inet dcv wg_base')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @admin_peer2cidr ct state new accept')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @admin_links   ct state new accept')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @p2p_links     ct state new accept')
    _nft_try('add rule inet dcv wg_base meta l4proto tcp ip saddr . ip daddr . th dport @svc_guest_tcp ct state new accept')
    _nft_try('add rule inet dcv wg_base meta l4proto udp ip saddr . ip daddr . th dport @svc_guest_udp ct state new accept')

    # Rule-based NEW acceptance lives here; we’ll add per-subnet/per-link rules to wg_allow
    _nft_try('flush chain inet dcv wg_allow')

# ---------- Service helpers (peer→host) ----------

def _svc_pair_has_other_ports(src_ip: str, dst_ip: str, proto: str) -> bool:
    setname = "svc_guest_tcp" if proto.lower() == "tcp" else "svc_guest_udp"
    try:
        out = subprocess.check_output([NFT_BIN, "-j", "list", "set", "inet", "dcv", setname], text=True)
        data = json.loads(out)
        for el in data.get("set", {}).get("elem", []):
            tup = el.get("elem", [])
            if len(tup) == 3 and tup[0] == src_ip and tup[1] == dst_ip:
                return True
    except Exception as e:
        logging.debug("%s query failed: %s", setname, e)
    return False

# ---------- Subnet primitives ----------

def ensure_subnet(subnet_id: str) -> None:
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    public  = f"subnet_{s}_public"

    _nft_try(f"add set inet dcv {members} {{ type ipv4_addr; flags interval; }}")
    _nft_try(f"add set inet dcv {public}  {{ type ipv4_addr; flags interval; }}")

    # NEW acceptance rule (wg_allow)
    _delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr @{public} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr @{public} ct state new accept")

    # EST acceptance matching the same relation (so replies flow) -> fwd_est
    _delete_rule_by_match("fwd_est", rf"ct original ip saddr @{members} ct original ip daddr @{public} accept")
    _nft_try(f"add rule inet dcv fwd_est ct state established,related "
             f"ct original ip saddr @{members} ct original ip daddr @{public} accept")

def destroy_subnet(subnet_id: str, destroy_all_traffic_to_peers_inside: bool=False) -> None:
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    public  = f"subnet_{s}_public"
    # First, clean up any elements in pair sets that reference this subnet
    _purge_pair_set_for_subnet("p2p_links", subnet_id)
    _purge_pair_set_for_subnet("admin_links", subnet_id)
    _purge_pair_set_for_subnet("admin_peer2cidr", subnet_id)
    # Clean service triples per-proto
    _purge_service_triples_for_subnet(subnet_id, "svc_guest_tcp")
    _purge_service_triples_for_subnet(subnet_id, "svc_guest_udp")
    # Also clean per-proto svc_pairs pairs referencing this subnet
    _purge_pair_set_for_subnet("svc_pairs_tcp", subnet_id)
    _purge_pair_set_for_subnet("svc_pairs_udp", subnet_id)

    # Broad sweep via JSON: delete any rule in any chain that references either set
    try:
        out = subprocess.check_output([NFT_BIN, "-j", "list", "table", "inet", "dcv"], text=True)
        data = json.loads(out)
    except Exception:
        data = None

    to_delete = []
    def has_set(node, name):
        if isinstance(node, dict):
            if node.get("set") == name: return True
            if "lookup" in node:
                lk = node["lookup"]
                if isinstance(lk, dict) and (lk.get("set") == name or lk.get("name") == name):
                    return True
            return any(has_set(v, name) for v in node.values())
        if isinstance(node, list):
            return any(has_set(v, name) for v in node)
        return False

    if isinstance(data, dict):
        for item in data.get("nftables", []):
            rule = item.get("rule")
            if not rule: continue
            chain = rule.get("chain"); handle = rule.get("handle")
            if chain and handle is not None:
                expr = rule.get("expr", [])
                if has_set(expr, members) or has_set(expr, public):
                    to_delete.append((chain, str(handle)))

    for chain, handle in to_delete:
        _nft_try(f"delete rule inet dcv {chain} handle {handle}")

    # Extra safety for your known patterns
    _delete_rule_by_match("wg_allow", rf"@{members}")
    _delete_rule_by_match("wg_allow", rf"@{public}")
    _delete_rule_by_match("fwd_est",  rf"@{members}")
    _delete_rule_by_match("fwd_est",  rf"@{public}")

    # Now sets can go
    _nft_try(f"flush set inet dcv {members}")
    _nft_try(f"flush set inet dcv {public}")
    _nft_try(f"delete set inet dcv {members}")
    _nft_try(f"delete set inet dcv {public}")
    # Conntrack cleanup is manual for instant flush
    flush_conntrack_for_prefix(subnet_id, allow_large_prefix=destroy_all_traffic_to_peers_inside)

def _purge_pair_set_for_subnet(setname: str, cidr: str):
    try:
        js = subprocess.check_output([NFT_BIN, "-j", "list", "set", "inet", "dcv", setname], text=True)
        data = json.loads(js)
        net = ipaddress.ip_network(cidr, strict=False)
        for el in data.get("set", {}).get("elem", []):
            pair = el.get("elem", [])
            if len(pair) != 2: continue
            a, b = pair
            if (ipaddress.ip_address(a) in net) or (ipaddress.ip_address(b) in net):
                _nft_try(f"delete element inet dcv {setname} {{ {a} . {b} }}")
    except Exception:
        pass

def _purge_service_triples_for_subnet(cidr: str, setname: str):
    """Remove service triples in the given set where src or dst is in the cidr (port ignored)."""
    try:
        js = subprocess.check_output([NFT_BIN, "-j", "list", "set", "inet", "dcv", setname], text=True)
        data = json.loads(js)
        net = ipaddress.ip_network(cidr, strict=False)
        for el in data.get("set", {}).get("elem", []):
            tup = el.get("elem", [])
            if len(tup) != 3:
                continue
            a, b, port = tup
            if (ipaddress.ip_address(a) in net) or (ipaddress.ip_address(b) in net):
                _nft_try(f"delete element inet dcv {setname} {{ {a} . {b} . {port} }}")
    except Exception:
        pass

def add_member(subnet_id: str, ip: str) -> None:
    s = _slug(subnet_id)
    _nft_try(f"add element inet dcv subnet_{s}_members {{ {ip} }}")

def del_member(subnet_id: str, ip: str) -> None:
    s = _slug(subnet_id)
    _nft_try(f"delete element inet dcv subnet_{s}_members {{ {ip} }}")
    # Conntrack cleanup
    flush_conntrack_for_ip(ip)

def make_public(subnet_id: str, ip: str) -> None:
    s = _slug(subnet_id)
    _nft_try(f"add element inet dcv subnet_{s}_public {{ {ip} }}")

def revoke_public(subnet_id: str, ip: str) -> None:
    s = _slug(subnet_id)
    _nft_try(f"delete element inet dcv subnet_{s}_public {{ {ip} }}")

# ---------- Peer ↔ Peer links ----------

def add_p2p_link(a_ip: str, b_ip: str) -> None:
    _nft_try(f"add element inet dcv p2p_links {{ {a_ip} . {b_ip} }}")
    _nft_try(f"add element inet dcv p2p_links {{ {b_ip} . {a_ip} }}")

def remove_p2p_link(a_ip: str, b_ip: str) -> None:
    _nft_try(f"delete element inet dcv p2p_links {{ {a_ip} . {b_ip} }}")
    _nft_try(f"delete element inet dcv p2p_links {{ {b_ip} . {a_ip} }}")

def _purge_pair_set_for_ip(setname: str, ip: str):
    try:
        js = subprocess.check_output([NFT_BIN,"-j","list","set","inet","dcv",setname], text=True)
        data = json.loads(js)
        for el in data.get("set",{}).get("elem",[]):
            pair = el.get("elem",[])
            if len(pair) == 2:
                a,b = pair
                if a == ip or b == ip:
                    _nft_try(f"delete element inet dcv {setname} {{ {a} . {b} }}")
    except Exception:
        pass

# ---------- Peer → Service links (peer-scoped) ----------

def grant_service(src_ip: str, dst_ip: str, port: int, proto: str = "both") -> None:
    """
    Grant a peer -> host service:
      proto: "tcp" | "udp" | "both"
    """
    protos = ["tcp", "udp"] if proto == "both" else [proto.lower()]
    for p in protos:
        if p == "tcp":
            _nft_try(f"add element inet dcv svc_guest_tcp {{ {src_ip} . {dst_ip} . {port} }}")
            _nft_try(f"add element inet dcv svc_pairs_tcp {{ {src_ip} . {dst_ip} }}")  # for EST replies
        elif p == "udp":
            _nft_try(f"add element inet dcv svc_guest_udp {{ {src_ip} . {dst_ip} . {port} }}")
            _nft_try(f"add element inet dcv svc_pairs_udp {{ {src_ip} . {dst_ip} }}")  # for EST replies

def revoke_service(src_ip: str, dst_ip: str, port: int, proto: str = "both") -> None:
    """
    Revoke a peer -> host service:
      proto: "tcp" | "udp" | "both"
    """
    protos = ["tcp", "udp"] if proto == "both" else [proto.lower()]
    for p in protos:
        if p == "tcp":
            _nft_try(f"delete element inet dcv svc_guest_tcp {{ {src_ip} . {dst_ip} . {port} }}")
            if not _svc_pair_has_other_ports(src_ip, dst_ip, "tcp"):
                _nft_try(f"delete element inet dcv svc_pairs_tcp {{ {src_ip} . {dst_ip} }}")
        elif p == "udp":
            _nft_try(f"delete element inet dcv svc_guest_udp {{ {src_ip} . {dst_ip} . {port} }}")
            if not _svc_pair_has_other_ports(src_ip, dst_ip, "udp"):
                _nft_try(f"delete element inet dcv svc_pairs_udp {{ {src_ip} . {dst_ip} }}")

# ---------- Subnet → Service links (rule-based) ----------

def grant_subnet_service(subnet_id: str, dst_ip: str, port: int, proto: str = "both"):
    """
    Allow members of subnet_id to reach dst_ip:port over proto ("tcp"|"udp"|"both").
    """
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    protos = ["tcp", "udp"] if proto == "both" else [proto.lower()]

    for p in protos:
        # NEW acceptance (wg_allow)
        _delete_rule_by_match(
            "wg_allow",
            rf"meta l4proto {p} ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
        )
        _nft_try(
            f"add rule inet dcv wg_allow meta l4proto {p} "
            f"ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
        )

        # EST acceptance (fwd_est) — tie replies to original l4proto + tuple
        _delete_rule_by_match(
            "fwd_est",
            rf"ct original l4proto {p} ct original ip saddr @{members} ct original ip daddr {dst_ip} accept"
        )
        _nft_try(
            f"add rule inet dcv fwd_est ct state established,related "
            f"ct original l4proto {p} ct original ip saddr @{members} ct original ip daddr {dst_ip} accept"
        )

def revoke_subnet_service(subnet_id: str, dst_ip: str, port: int, proto: str = "both"):
    """
    Revoke members of subnet_id reaching dst_ip:port over proto ("tcp"|"udp"|"both").
    """
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    protos = ["tcp", "udp"] if proto == "both" else [proto.lower()]

    for p in protos:
        _delete_rule_by_match(
            "wg_allow",
            rf"meta l4proto {p} ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
        )
        _delete_rule_by_match(
            "fwd_est",
            rf"ct original l4proto {p} ct original ip saddr @{members} ct original ip daddr {dst_ip} accept"
        )

# ------------- Subnet ↔ Subnet links (rule-based) -------------

def connect_subnet_to_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_public = f"subnet_{d}_public"

    # NEW acceptance (wg_allow)
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")

    # EST acceptance (fwd_est)
    _delete_rule_by_match("fwd_est",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")
    _nft_try(f"add rule inet dcv fwd_est ct state established,related "
             f"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")

def disconnect_subnet_from_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_public = f"subnet_{d}_public"
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")
    _delete_rule_by_match("fwd_est",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")

def connect_subnets_bidirectional_public(subnet_a: str, subnet_b: str) -> None:
    # idempotent safety
    ensure_subnet(subnet_a)
    ensure_subnet(subnet_b)
    connect_subnet_to_subnet_public(subnet_a, subnet_b)
    connect_subnet_to_subnet_public(subnet_b, subnet_a)

def disconnect_subnets_bidirectional_public(subnet_a: str, subnet_b: str) -> None:
    disconnect_subnet_from_subnet_public(subnet_a, subnet_b)
    disconnect_subnet_from_subnet_public(subnet_b, subnet_a)

# ---------- Admin grants: peer as admin (set-based, already covered by EST rule) ----------

def grant_admin_peer_to_peer(src_ip: str, dst_ip: str) -> None:
    _nft_try(f"add element inet dcv admin_links {{ {src_ip} . {dst_ip} }}")

def revoke_admin_peer_to_peer(src_ip: str, dst_ip: str) -> None:
    _nft_try(f"delete element inet dcv admin_links {{ {src_ip} . {dst_ip} }}")

def grant_admin_peer_to_subnet(src_ip: str, dst_cidr: str) -> None:
    _nft_try(f"add element inet dcv admin_peer2cidr {{ {src_ip} . {dst_cidr} }}")

def revoke_admin_peer_to_subnet(src_ip: str, dst_cidr: str) -> None:
    _nft_try(f"delete element inet dcv admin_peer2cidr {{ {src_ip} . {dst_cidr} }}")

# ---------- Admin grants: subnet as admin (rule-based) ----------

def grant_admin_subnet_to_peer(src_subnet_id: str, dst_ip: str) -> None:
    s = _slug(src_subnet_id)
    members = f"subnet_{s}_members"

    # NEW acceptance (wg_allow)
    _delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr {dst_ip} ct state new accept")

    # EST acceptance (fwd_est)
    _delete_rule_by_match("fwd_est", rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")
    _nft_try(f"add rule inet dcv fwd_est ct state established,related "
             f"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")

def revoke_admin_subnet_to_peer(src_subnet_id: str, dst_ip: str) -> None:
    s = _slug(src_subnet_id)
    members = f"subnet_{s}_members"
    _delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    _delete_rule_by_match("fwd_est",  rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")

def grant_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_members = f"subnet_{d}_members"

    # NEW acceptance (wg_allow)
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")

    # EST acceptance (fwd_est)
    _delete_rule_by_match("fwd_est",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")
    _nft_try(f"add rule inet dcv fwd_est ct state established,related "
             f"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")

def revoke_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_members = f"subnet_{d}_members"
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    _delete_rule_by_match("fwd_est",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")
