import subprocess
from typing import Iterable
from backend.core.logger import logging

NFT_BIN = "nft"

def _nft_batch(lines: Iterable[str]) -> None:
    """Run an atomic nftables batch. Raises on failure."""
    script = "\n".join(lines) + "\n"
    try:
        subprocess.run([NFT_BIN, "-f", "-"], input=script.encode(), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        logging.error("nft batch failed: %s\n--- batch ---\n%s",
                      e.stderr.decode(errors="ignore"), script)
        raise

def _nft_try(cmd: str) -> None:
    """
    Run a single nft command; ignore errors (useful for idempotent add/delete).
    NOT a batch: each command executes independently.
    """
    proc = subprocess.run([NFT_BIN, *cmd.split()],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        logging.debug("nft try failed (ignored): %s -> %s", cmd, proc.stderr.strip())

def _slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s)

# --- Flush & reseed only inet/dcv ---

def flush_dcv(wg_if: str = "wg0") -> None:
    """
    Delete inet/dcv entirely and recreate the base scaffold.
    Does not touch other tables (e.g., ip nat).
    """
    _nft_try("delete table inet dcv")
    ensure_table_and_chain(wg_if=wg_if)

# ---- DCV table snapshot/restore ----

def backup_dcv_table() -> str:
    """Return the textual definition of the inet/dcv table (or an empty 'add table' if missing)."""
    try:
        out = subprocess.check_output([NFT_BIN, "list", "table", "inet", "dcv"], text=True)
        return out
    except subprocess.CalledProcessError:
        # Table missing: return a minimal create so restore is valid/no-op
        return "add table inet dcv\n"

def restore_dcv_table(dcv_text: str) -> None:
    """Atomically replace inet/dcv with the provided snapshot, without touching other tables."""
    _nft_try("delete table inet dcv")
    subprocess.run([NFT_BIN, "-f", "-"], input=dcv_text, text=True, check=True)

# ---------- Base ensure (idempotent) ----------

def ensure_table_and_chain(wg_if: str = "wg0") -> None:
    """Ensure inet/dcv exists and normalize base chains/rules without touching dynamic allows."""
    _nft_try("add table inet dcv")

    # --- sets (idempotent) ---
    _nft_try("add set inet dcv p2p_links { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv svc_guest { type ipv4_addr . ipv4_addr . inet_service; flags interval; }")
    _nft_try("add set inet dcv admin_links { type ipv4_addr . ipv4_addr; flags interval; }")
    _nft_try("add set inet dcv admin_peer2cidr { type ipv4_addr . ipv4_addr; flags interval; }")

    # --- base chains (create if missing) ---
    _nft_try('add chain inet dcv forward { type filter hook forward priority 0; policy accept; }')
    _nft_try('add chain inet dcv wg')         # REGULAR chain (no policy!)
    _nft_try('add chain inet dcv wg_base')
    _nft_try('add chain inet dcv wg_allow')

    # --- forward: normalize content (re-add hooks to wg) ---
    _nft_try('flush chain inet dcv forward')
    _nft_try('add rule inet dcv forward ct state established,related accept')
    _nft_try(f'add rule inet dcv forward iifname "{wg_if}" goto wg')
    _nft_try(f'add rule inet dcv forward oifname "{wg_if}" goto wg')

    # --- wg: dispatch to base + allow, then hard reject ---
    _nft_try('flush chain inet dcv wg')
    _nft_try('add rule inet dcv wg jump wg_base')
    _nft_try('add rule inet dcv wg jump wg_allow')
    _nft_try('add rule inet dcv wg counter reject with icmpx type admin-prohibited')

    # --- wg_base: normalize base allows (admin > p2p > service) ---
    _nft_try('flush chain inet dcv wg_base')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @admin_peer2cidr ct state new accept')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @admin_links   ct state new accept')
    _nft_try('add rule inet dcv wg_base ip saddr . ip daddr @p2p_links     ct state new accept')
    _nft_try('add rule inet dcv wg_base meta l4proto { tcp, udp } ip saddr . ip daddr . th dport @svc_guest ct state new accept')

# ---------- Subnet primitives ----------

def ensure_subnet(subnet_id: str) -> None:
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    public  = f"subnet_{s}_public"

    _nft_try(f"add set inet dcv {members} {{ type ipv4_addr; flags interval; }}")
    _nft_try(f"add set inet dcv {public}  {{ type ipv4_addr; flags interval; }}")
    # place in wg_allow so it's evaluated before reject
    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{members} ip daddr @{public} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr @{public} ct state new accept")

def destroy_subnet(subnet_id: str) -> None:
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    public  = f"subnet_{s}_public"

    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{members} ip daddr @{public} ct state new accept")
    _nft_try(f"delete set inet dcv {members}")
    _nft_try(f"delete set inet dcv {public}")

def add_member(subnet_id: str, ip: str) -> None:
    """Add a peer IP to the subnet's members set (idempotent)."""
    s = _slug(subnet_id)
    _nft_try(f"add element inet dcv subnet_{s}_members {{ {ip} }}")

def del_member(subnet_id: str, ip: str) -> None:
    """Remove a peer IP from the subnet's members set (idempotent)."""
    s = _slug(subnet_id)
    _nft_try(f"delete element inet dcv subnet_{s}_members {{ {ip} }}")

def make_public(subnet_id: str, ip: str) -> None:
    """Mark a peer IP as public within the subnet."""
    s = _slug(subnet_id)
    _nft_try(f"add element inet dcv subnet_{s}_public {{ {ip} }}")

def revoke_public(subnet_id: str, ip: str) -> None:
    """Unmark a peer IP as public within the subnet."""
    s = _slug(subnet_id)
    _nft_try(f"delete element inet dcv subnet_{s}_public {{ {ip} }}")

# ---------- Peer ↔ Peer links ----------

def add_p2p_link(a_ip: str, b_ip: str) -> None:
    """
    Allow NEW connections both ways between two peers (bidirectional).
    We insert *both* tuples so a->b and b->a are permitted.
    """
    _nft_try(f"add element inet dcv p2p_links {{ {a_ip} . {b_ip} }}")
    _nft_try(f"add element inet dcv p2p_links {{ {b_ip} . {a_ip} }}")

def remove_p2p_link(a_ip: str, b_ip: str) -> None:
    """Revoke the bidirectional peer link (removes both tuples)."""
    _nft_try(f"delete element inet dcv p2p_links {{ {a_ip} . {b_ip} }}")
    _nft_try(f"delete element inet dcv p2p_links {{ {b_ip} . {a_ip} }}")

# ---------- Peer → Service links (port-agnostic) ----------

def grant_service(src_ip: str, dst_ip: str, port: int) -> None:
    """Allow NEW connections from a peer to a host's service (single rule covers TCP/UDP)."""
    _nft_try(f"add element inet dcv svc_guest {{ {src_ip} . {dst_ip} . {port} }}")

def revoke_service(src_ip: str, dst_ip: str, port: int) -> None:
    """Revoke access to a specific service tuple."""
    _nft_try(f"delete element inet dcv svc_guest {{ {src_ip} . {dst_ip} . {port} }}")

# ---------- Subnet → Service links (port-agnostic) ----------

def grant_subnet_service(subnet_id: str, dst_ip: str, port: int):
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    _nft_try(
        f"delete rule inet dcv wg_allow meta l4proto {{ tcp, udp }} "
        f"ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
    )
    _nft_try(
        f"add rule inet dcv wg_allow meta l4proto {{ tcp, udp }} "
        f"ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
    )

def revoke_subnet_service(subnet_id: str, dst_ip: str, port: int):
    s = _slug(subnet_id)
    members = f"subnet_{s}_members"
    _nft_try(
        f"delete rule inet dcv wg_allow meta l4proto {{ tcp, udp }} "
        f"ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
    )

# ------------- Subnet ↔ Subnet links (rule-based) -------------

def connect_subnet_to_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    """
    Allow NEW from members of src_subnet to PUBLIC peers of dst_subnet (all ports/protos).
    """
    s = _slug(src_subnet_id)
    d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"
    dst_public  = f"subnet_{d}_public"
    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")

def disconnect_subnet_from_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id)
    d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"
    dst_public  = f"subnet_{d}_public"
    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")

def connect_subnets_bidirectional_public(subnet_a: str, subnet_b: str) -> None:
    """A.members → B.public and B.members → A.public."""
    connect_subnet_to_subnet_public(subnet_a, subnet_b)
    connect_subnet_to_subnet_public(subnet_b, subnet_a)

def disconnect_subnets_bidirectional_public(subnet_a: str, subnet_b: str) -> None:
    disconnect_subnet_from_subnet_public(subnet_a, subnet_b)
    disconnect_subnet_from_subnet_public(subnet_b, subnet_a)

# ---------- Admin grants: peer as admin (one-way blanket) ----------

def grant_admin_peer_to_peer(src_ip: str, dst_ip: str) -> None:
    """Admin peer can initiate to a specific peer (all protocols/ports)."""
    _nft_try(f"add element inet dcv admin_links {{ {src_ip} . {dst_ip} }}")

def revoke_admin_peer_to_peer(src_ip: str, dst_ip: str) -> None:
    _nft_try(f"delete element inet dcv admin_links {{ {src_ip} . {dst_ip} }}")

def grant_admin_peer_to_subnet(src_ip: str, dst_cidr: str) -> None:
    """Admin peer can initiate to every IP in a CIDR (e.g., '10.100.50.0/24')."""
    _nft_try(f"add element inet dcv admin_peer2cidr {{ {src_ip} . {dst_cidr} }}")

def revoke_admin_peer_to_subnet(src_ip: str, dst_cidr: str) -> None:
    _nft_try(f"delete element inet dcv admin_peer2cidr {{ {src_ip} . {dst_cidr} }}")

# ---------- Admin grants: subnet as admin (rule-based) ----------

def grant_admin_subnet_to_peer(src_subnet_id: str, dst_ip: str) -> None:
    s = _slug(src_subnet_id)
    members = f"subnet_{s}_members"
    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr {dst_ip} ct state new accept")

def revoke_admin_subnet_to_peer(src_subnet_id: str, dst_ip: str) -> None:
    s = _slug(src_subnet_id)
    members = f"subnet_{s}_members"
    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{members} ip daddr {dst_ip} ct state new accept")

def grant_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_members = f"subnet_{d}_members"
    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    _nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")

def revoke_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    s = _slug(src_subnet_id); d = _slug(dst_subnet_id)
    src_members = f"subnet_{s}_members"; dst_members = f"subnet_{d}_members"
    _nft_try(f"delete rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
