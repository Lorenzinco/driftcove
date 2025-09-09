import subprocess
from typing import Iterable
from backend.core.logger import logging
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
        logging.info("[ERROR] nft try failed (ignored): %s -> %s", cmd, proc.stderr.strip())

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
    _nft_try("add set inet dcv svc_guest { type ipv4_addr . ipv4_addr . inet_service; flags interval; }")
    _nft_try("add set inet dcv svc_pairs { type ipv4_addr . ipv4_addr; flags interval; }")  # for EST service flows
    _nft_try("add set inet dcv admin_links { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv admin_peer2cidr { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv blocked_pairs { type ipv4_addr . ipv4_addr; flags interval; }")  # panic drop

    # Chains
    _nft_try('add chain inet dcv input   { type filter hook input   priority 0; policy accept; }')
    _nft_try('add chain inet dcv forward { type filter hook forward priority 0; policy accept; }')
    _nft_try('add chain inet dcv wg')
    _nft_try('add chain inet dcv wg_base')
    _nft_try('add chain inet dcv wg_allow')

    # INPUT
    _nft_try('flush chain inet dcv input')
    _nft_try('add rule inet dcv input ct state established,related accept')
    _nft_try(f'add rule inet dcv input iifname "{wg_if}" ip daddr {wg_server_ip} icmp type echo-request accept')

    # FORWARD
    _nft_try('flush chain inet dcv forward')
    _nft_try('add rule inet dcv forward ip saddr . ip daddr @blocked_pairs drop')  # panic drop

    # Constrained EST/REL acceptance by original tuple
    _nft_try('add rule inet dcv forward ct state established,related '
             'ct original ip saddr . ct original ip daddr @admin_peer2cidr accept')
    _nft_try('add rule inet dcv forward ct state established,related '
             'ct original ip saddr . ct original ip daddr @admin_links accept')
    _nft_try('add rule inet dcv forward ct state established,related '
             'ct original ip saddr . ct original ip daddr @p2p_links accept')
    _nft_try('add rule inet dcv forward ct state established,related '
             'ct original ip saddr . ct original ip daddr @svc_pairs accept')

    # steer wg traffic to pipeline
    _nft_try(f'add rule inet dcv forward iifname "{wg_if}" goto wg')
    _nft_try(f'add rule inet dcv forward oifname "{wg_if}" goto wg')

    # WG pipeline
    _nft_try('flush chain inet dcv wg')
    _nft_try('add rule inet dcv wg jump wg_base')
    _nft_try('add rule inet dcv wg jump wg_allow')
    _nft_try('add rule inet dcv wg counter reject with icmpx type admin-prohibited')

    # NEW acceptance (set-based)
    _nft_try('flush chain inet dcv wg_base')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @admin_peer2cidr ct state new accept')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @admin_links   ct state new accept')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @p2p_links     ct state new accept')
    _nft_try('add rule inet dcv wg_base meta l4proto { tcp, udp } ip saddr . ip daddr . th dport @svc_guest ct state new accept')

    # Rule-based NEW acceptance lives here; we’ll add per-subnet/per-link rules to wg_allow
    _nft_try('flush chain inet dcv wg_allow')

# ---------- Service helpers (peer→host) ----------

def _svc_pair_has_other_ports(src_ip: str, dst_ip: str) -> bool:
    try:
        out = subprocess.check_output([NFT_BIN, "-j", "list", "set", "inet", "dcv", "svc_guest"], text=True)
        data = json.loads(out)
        for el in data.get("set", {}).get("elem", []):
            tup = el.get("elem", [])
            if len(tup) == 3 and tup[0] == src_ip and tup[1] == dst_ip:
                return True
    except Exception as e:
        logging.debug("svc_guest query failed: %s", e)
    return False

# ---------- Subnet primitives ----------

def ensure_subnet(subnet_id: str) -> None:
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    public  = f"subnet_{s}_public"

    _nft_try(f"add set inet dcv {members} {{ type ipv4_addr; flags interval; }}")
    _nft_try(f"add set inet dcv {public}  {{ type ipv4_addr; flags interval; }}")

    # NEW acceptance rule
    _delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr @{public} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr @{public} ct state new accept")

    # EST acceptance matching the same relation (so replies flow)
    _delete_rule_by_match("forward", rf"ct original ip saddr @{members} ct original ip daddr @{public} accept")
    _nft_try(f"add rule inet dcv forward ct state established,related "
             f"ct original ip saddr @{members} ct original ip daddr @{public} accept")

def destroy_subnet(subnet_id: str) -> None:
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    public  = f"subnet_{s}_public"

    _delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr @{public} ct state new accept")
    _delete_rule_by_match("forward",  rf"ct original ip saddr @{members} ct original ip daddr @{public} accept")
    _nft_try(f"delete set inet dcv {members}")
    _nft_try(f"delete set inet dcv {public}")

def add_member(subnet_id: str, ip: str) -> None:
    s = _slug(subnet_id)
    _nft_try(f"add element inet dcv subnet_{s}_members {{ {ip} }}")

def del_member(subnet_id: str, ip: str) -> None:
    s = _slug(subnet_id)
    _nft_try(f"delete element inet dcv subnet_{s}_members {{ {ip} }}")

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

# ---------- Peer → Service links (peer-scoped) ----------

def grant_service(src_ip: str, dst_ip: str, port: int) -> None:
    _nft_try(f"add element inet dcv svc_guest {{ {src_ip} . {dst_ip} . {port} }}")
    _nft_try(f"add element inet dcv svc_pairs {{ {src_ip} . {dst_ip} }}")  # for EST replies

def revoke_service(src_ip: str, dst_ip: str, port: int) -> None:
    _nft_try(f"delete element inet dcv svc_guest {{ {src_ip} . {dst_ip} . {port} }}")
    if not _svc_pair_has_other_ports(src_ip, dst_ip):
        _nft_try(f"delete element inet dcv svc_pairs {{ {src_ip} . {dst_ip} }}")

# ---------- Subnet → Service links (rule-based) ----------

def grant_subnet_service(subnet_id: str, dst_ip: str, port: int):
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"

    # NEW acceptance
    _delete_rule_by_match("wg_allow",
        rf"meta l4proto \{{ tcp, udp \}} ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept")
    _nft_try(
        f"add rule inet dcv wg_allow meta l4proto {{ tcp, udp }} "
        f"ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
    )

    # EST acceptance for replies of that relation
    _delete_rule_by_match("forward",
        rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")
    _nft_try(
        f"add rule inet dcv forward ct state established,related "
        f"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept"
    )

def revoke_subnet_service(subnet_id: str, dst_ip: str, port: int):
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    _delete_rule_by_match("wg_allow",
        rf"meta l4proto \{{ tcp, udp \}} ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept")
    _delete_rule_by_match("forward",
        rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")

# ------------- Subnet ↔ Subnet links (rule-based) -------------

def connect_subnet_to_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_public = f"subnet_{d}_public"

    # NEW acceptance
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")

    # EST acceptance for replies
    _delete_rule_by_match("forward",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")
    _nft_try(f"add rule inet dcv forward ct state established,related "
             f"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")

def disconnect_subnet_from_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_public = f"subnet_{d}_public"
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")
    _delete_rule_by_match("forward",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")

def connect_subnets_bidirectional_public(subnet_a: str, subnet_b: str) -> None:
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

    # NEW acceptance
    _delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr {dst_ip} ct state new accept")

    # EST acceptance
    _delete_rule_by_match("forward", rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")
    _nft_try(f"add rule inet dcv forward ct state established,related "
             f"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")

def revoke_admin_subnet_to_peer(src_subnet_id: str, dst_ip: str) -> None:
    s = _slug(src_subnet_id)
    members = f"subnet_{s}_members"
    _delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    _delete_rule_by_match("forward",  rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")

def grant_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_members = f"subnet_{d}_members"

    # NEW acceptance
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")

    # EST acceptance
    _delete_rule_by_match("forward",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")
    _nft_try(f"add rule inet dcv forward ct state established,related "
             f"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")

def revoke_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_members = f"subnet_{d}_members"
    _delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    _delete_rule_by_match("forward",
        rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")
