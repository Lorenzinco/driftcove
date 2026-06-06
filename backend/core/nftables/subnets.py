import ipaddress

from backend.core.nftables.base import flush_conntrack_for_ip, flush_conntrack_for_prefix
from backend.core.nftables.commands import (
    delete_rule_by_match,
    element_tuple,
    expression_has_set,
    list_set_elements,
    nft_try,
    slug,
    table_rules,
)


def ensure_subnet(subnet_id: str) -> None:
    subnet_slug = slug(subnet_id)
    members = f"subnet_{subnet_slug}_members"
    public = f"subnet_{subnet_slug}_public"

    nft_try(f"add set inet dcv {members} {{ type ipv4_addr; flags interval; }}")
    nft_try(f"add set inet dcv {public}  {{ type ipv4_addr; flags interval; }}")

    delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr @{public} ct state new accept")
    nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr @{public} ct state new accept")

    delete_rule_by_match("fwd_est", rf"ct original ip saddr @{members} ct original ip daddr @{public} accept")
    nft_try(
        f"add rule inet dcv fwd_est ct state established,related "
        f"ct original ip saddr @{members} ct original ip daddr @{public} accept"
    )


def destroy_subnet(subnet_id: str, destroy_all_traffic_to_peers_inside: bool = False) -> None:
    subnet_slug = slug(subnet_id)
    members = f"subnet_{subnet_slug}_members"
    public = f"subnet_{subnet_slug}_public"

    for set_name in ("p2p_links", "admin_links", "admin_peer2cidr", "svc_pairs_tcp", "svc_pairs_udp"):
        _purge_pair_set_for_subnet(set_name, subnet_id)
    for set_name in ("svc_guest_tcp", "svc_guest_udp"):
        _purge_service_triples_for_subnet(subnet_id, set_name)

    for rule in table_rules():
        chain = rule.get("chain")
        handle = rule.get("handle")
        expr = rule.get("expr", [])
        if chain and handle is not None and (expression_has_set(expr, members) or expression_has_set(expr, public)):
            nft_try(f"delete rule inet dcv {chain} handle {handle}")

    delete_rule_by_match("wg_allow", rf"@{members}")
    delete_rule_by_match("wg_allow", rf"@{public}")
    delete_rule_by_match("fwd_est", rf"@{members}")
    delete_rule_by_match("fwd_est", rf"@{public}")

    nft_try(f"flush set inet dcv {members}")
    nft_try(f"flush set inet dcv {public}")
    nft_try(f"delete set inet dcv {members}")
    nft_try(f"delete set inet dcv {public}")
    flush_conntrack_for_prefix(subnet_id, allow_large_prefix=destroy_all_traffic_to_peers_inside)


def _purge_pair_set_for_subnet(setname: str, cidr: str) -> None:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return
    for element in list_set_elements(setname):
        pair = element_tuple(element)
        if len(pair) != 2:
            continue
        a, b = pair
        if ipaddress.ip_address(a) in net or ipaddress.ip_address(b) in net:
            nft_try(f"delete element inet dcv {setname} {{ {a} . {b} }}")


def _purge_service_triples_for_subnet(cidr: str, setname: str) -> None:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return
    for element in list_set_elements(setname):
        triple = element_tuple(element)
        if len(triple) != 3:
            continue
        src_ip, dst_ip, port = triple
        if ipaddress.ip_address(src_ip) in net or ipaddress.ip_address(dst_ip) in net:
            nft_try(f"delete element inet dcv {setname} {{ {src_ip} . {dst_ip} . {port} }}")


def add_member(subnet_id: str, ip: str) -> None:
    nft_try(f"add element inet dcv subnet_{slug(subnet_id)}_members {{ {ip} }}")


def del_member(subnet_id: str, ip: str) -> None:
    nft_try(f"delete element inet dcv subnet_{slug(subnet_id)}_members {{ {ip} }}")
    flush_conntrack_for_ip(ip)


def make_public(subnet_id: str, ip: str) -> None:
    nft_try(f"add element inet dcv subnet_{slug(subnet_id)}_public {{ {ip} }}")


def revoke_public(subnet_id: str, ip: str) -> None:
    nft_try(f"delete element inet dcv subnet_{slug(subnet_id)}_public {{ {ip} }}")


def connect_subnet_to_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    src_members = f"subnet_{slug(src_subnet_id)}_members"
    dst_public = f"subnet_{slug(dst_subnet_id)}_public"

    delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")
    nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")

    delete_rule_by_match("fwd_est", rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")
    nft_try(
        f"add rule inet dcv fwd_est ct state established,related "
        f"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept"
    )


def disconnect_subnet_from_subnet_public(src_subnet_id: str, dst_subnet_id: str) -> None:
    src_members = f"subnet_{slug(src_subnet_id)}_members"
    dst_public = f"subnet_{slug(dst_subnet_id)}_public"
    delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_public} ct state new accept")
    delete_rule_by_match("fwd_est", rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_public} accept")


def connect_subnets_bidirectional_public(subnet_a: str, subnet_b: str) -> None:
    ensure_subnet(subnet_a)
    ensure_subnet(subnet_b)
    connect_subnet_to_subnet_public(subnet_a, subnet_b)
    connect_subnet_to_subnet_public(subnet_b, subnet_a)


def disconnect_subnets_bidirectional_public(subnet_a: str, subnet_b: str) -> None:
    disconnect_subnet_from_subnet_public(subnet_a, subnet_b)
    disconnect_subnet_from_subnet_public(subnet_b, subnet_a)


def grant_admin_subnet_to_peer(src_subnet_id: str, dst_ip: str) -> None:
    members = f"subnet_{slug(src_subnet_id)}_members"
    delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    nft_try(f"add rule inet dcv wg_allow ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    delete_rule_by_match("fwd_est", rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")
    nft_try(
        f"add rule inet dcv fwd_est ct state established,related "
        f"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept"
    )


def revoke_admin_subnet_to_peer(src_subnet_id: str, dst_ip: str) -> None:
    members = f"subnet_{slug(src_subnet_id)}_members"
    delete_rule_by_match("wg_allow", rf"ip saddr @{members} ip daddr {dst_ip} ct state new accept")
    delete_rule_by_match("fwd_est", rf"ct original ip saddr @{members} ct original ip daddr {dst_ip} accept")


def grant_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    src_members = f"subnet_{slug(src_subnet_id)}_members"
    dst_members = f"subnet_{slug(dst_subnet_id)}_members"
    delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    nft_try(f"add rule inet dcv wg_allow ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    delete_rule_by_match("fwd_est", rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")
    nft_try(
        f"add rule inet dcv fwd_est ct state established,related "
        f"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept"
    )


def revoke_admin_subnet_to_subnet(src_subnet_id: str, dst_subnet_id: str) -> None:
    src_members = f"subnet_{slug(src_subnet_id)}_members"
    dst_members = f"subnet_{slug(dst_subnet_id)}_members"
    delete_rule_by_match("wg_allow", rf"ip saddr @{src_members} ip daddr @{dst_members} ct state new accept")
    delete_rule_by_match("fwd_est", rf"ct original ip saddr @{src_members} ct original ip daddr @{dst_members} accept")
