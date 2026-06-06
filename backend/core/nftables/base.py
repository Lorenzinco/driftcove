import ipaddress

from backend.core.logger import logger as logging
from backend.core.nftables.commands import backup_table, nft_try, restore_table


def flush_dcv(wg_if: str = "wg0") -> None:
    nft_try("delete table inet dcv")
    ensure_table_and_chain(wg_if=wg_if)


def flush_conntrack_for_ip(ip: str) -> None:
    logging.debug("Skipping conntrack flush for %s; nftables package does not shell out to conntrack", ip)


def flush_conntrack_for_prefix(cidr: str, allow_large_prefix: bool = False) -> None:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        logging.debug("invalid CIDR %s; skipping conntrack flush", cidr)
        return
    if not allow_large_prefix:
        if (net.version == 4 and net.prefixlen < 24) or (net.version == 6 and net.prefixlen < 64):
            logging.debug("CIDR %s too broad; skipping conntrack flush", cidr)
            return
    logging.debug("Skipping conntrack flush for %s; nftables package does not shell out to conntrack", cidr)


def backup_dcv_table() -> str:
    return backup_table("inet", "dcv", "add table inet dcv\n")


def restore_dcv_table(dcv_text: str) -> None:
    restore_table(dcv_text, "inet", "dcv")


def ensure_table_and_chain(wg_if: str = "wg0", wg_server_ip: str = "10.128.0.1") -> None:
    nft_try("add table inet dcv")

    for command in (
        "add set inet dcv p2p_links { type ipv4_addr . ipv4_addr; flags interval; }",
        "add set inet dcv admin_links { type ipv4_addr . ipv4_addr; flags interval; }",
        "add set inet dcv admin_peer2cidr { type ipv4_addr . ipv4_addr; flags interval; }",
        "add set inet dcv blocked_pairs { type ipv4_addr . ipv4_addr; flags interval; }",
        "add set inet dcv svc_guest_tcp { type ipv4_addr . ipv4_addr . inet_service; flags interval; }",
        "add set inet dcv svc_guest_udp { type ipv4_addr . ipv4_addr . inet_service; flags interval; }",
        "add set inet dcv svc_pairs_tcp { type ipv4_addr . ipv4_addr; flags interval; }",
        "add set inet dcv svc_pairs_udp { type ipv4_addr . ipv4_addr; flags interval; }",
        'add chain inet dcv input   { type filter hook input   priority 0; policy accept; }',
        'add chain inet dcv forward { type filter hook forward priority 0; policy accept; }',
        "add chain inet dcv fwd_est",
        "add chain inet dcv wg",
        "add chain inet dcv wg_base",
        "add chain inet dcv wg_allow",
    ):
        nft_try(command)

    for command in (
        "flush chain inet dcv input",
        "add rule inet dcv input ct state established,related accept",
        f'add rule inet dcv input iifname "{wg_if}" ip daddr {wg_server_ip} icmp type echo-request accept',
        "flush chain inet dcv forward",
        "add rule inet dcv forward ip saddr . ip daddr @blocked_pairs drop",
        "add rule inet dcv forward jump fwd_est",
        f'add rule inet dcv forward iifname "{wg_if}" goto wg',
        f'add rule inet dcv forward oifname "{wg_if}" goto wg',
        "flush chain inet dcv fwd_est",
        "add rule inet dcv fwd_est ct state established,related ct original ip saddr . ct original ip daddr @admin_peer2cidr accept",
        "add rule inet dcv fwd_est ct state established,related ct original ip saddr . ct original ip daddr @admin_links accept",
        "add rule inet dcv fwd_est ct state established,related ct original ip saddr . ct original ip daddr @p2p_links accept",
        "add rule inet dcv fwd_est ct state established,related ct original protocol tcp ct original ip saddr . ct original ip daddr @svc_pairs_tcp accept",
        "add rule inet dcv fwd_est ct state established,related ct original protocol udp ct original ip saddr . ct original ip daddr @svc_pairs_udp accept",
        "flush chain inet dcv wg",
        "add rule inet dcv wg jump wg_base",
        "add rule inet dcv wg jump wg_allow",
        "add rule inet dcv wg counter drop",
        "flush chain inet dcv wg_base",
        "add rule inet dcv wg_base ip saddr . ip daddr @admin_peer2cidr ct state new accept",
        "add rule inet dcv wg_base ip saddr . ip daddr @admin_links   ct state new accept",
        "add rule inet dcv wg_base ip saddr . ip daddr @p2p_links     ct state new accept",
        "add rule inet dcv wg_base meta l4proto tcp ip saddr . ip daddr . th dport @svc_guest_tcp ct state new accept",
        "add rule inet dcv wg_base meta l4proto udp ip saddr . ip daddr . th dport @svc_guest_udp ct state new accept",
        "flush chain inet dcv wg_allow",
    ):
        nft_try(command)
