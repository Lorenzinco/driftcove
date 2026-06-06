from backend.core.logger import logger as logging
from backend.core.nftables.commands import delete_rule_by_match, element_tuple, list_set_elements, nft_try, slug


def _protos(proto: str) -> list[str]:
    return ["tcp", "udp"] if proto == "both" else [proto.lower()]


def _svc_pair_has_other_ports(src_ip: str, dst_ip: str, proto: str) -> bool:
    setname = "svc_guest_tcp" if proto.lower() == "tcp" else "svc_guest_udp"
    try:
        for element in list_set_elements(setname):
            triple = element_tuple(element)
            if len(triple) == 3 and triple[0] == src_ip and triple[1] == dst_ip:
                return True
    except Exception as exc:
        logging.debug("%s query failed: %s", setname, exc)
    return False


def grant_service(src_ip: str, dst_ip: str, port: int, proto: str = "both") -> None:
    for p in _protos(proto):
        if p == "tcp":
            nft_try(f"add element inet dcv svc_guest_tcp {{ {src_ip} . {dst_ip} . {port} }}")
            nft_try(f"add element inet dcv svc_pairs_tcp {{ {src_ip} . {dst_ip} }}")
        elif p == "udp":
            nft_try(f"add element inet dcv svc_guest_udp {{ {src_ip} . {dst_ip} . {port} }}")
            nft_try(f"add element inet dcv svc_pairs_udp {{ {src_ip} . {dst_ip} }}")


def revoke_service(src_ip: str, dst_ip: str, port: int, proto: str = "both") -> None:
    for p in _protos(proto):
        if p == "tcp":
            nft_try(f"delete element inet dcv svc_guest_tcp {{ {src_ip} . {dst_ip} . {port} }}")
            if not _svc_pair_has_other_ports(src_ip, dst_ip, "tcp"):
                nft_try(f"delete element inet dcv svc_pairs_tcp {{ {src_ip} . {dst_ip} }}")
        elif p == "udp":
            nft_try(f"delete element inet dcv svc_guest_udp {{ {src_ip} . {dst_ip} . {port} }}")
            if not _svc_pair_has_other_ports(src_ip, dst_ip, "udp"):
                nft_try(f"delete element inet dcv svc_pairs_udp {{ {src_ip} . {dst_ip} }}")


def grant_subnet_service(subnet_id: str, dst_ip: str, port: int, proto: str = "both") -> None:
    members = f"subnet_{slug(subnet_id)}_members"
    for p in _protos(proto):
        delete_rule_by_match(
            "wg_allow",
            rf"meta l4proto {p} ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept",
        )
        nft_try(
            f"add rule inet dcv wg_allow meta l4proto {p} "
            f"ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept"
        )
        delete_rule_by_match(
            "fwd_est",
            rf"ct original l4proto {p} ct original ip saddr @{members} ct original ip daddr {dst_ip} accept",
        )
        nft_try(
            f"add rule inet dcv fwd_est ct state established,related "
            f"ct original l4proto {p} ct original ip saddr @{members} ct original ip daddr {dst_ip} accept"
        )


def revoke_subnet_service(subnet_id: str, dst_ip: str, port: int, proto: str = "both") -> None:
    members = f"subnet_{slug(subnet_id)}_members"
    for p in _protos(proto):
        delete_rule_by_match(
            "wg_allow",
            rf"meta l4proto {p} ip saddr @{members} ip daddr {dst_ip} th dport {port} ct state new accept",
        )
        delete_rule_by_match(
            "fwd_est",
            rf"ct original l4proto {p} ct original ip saddr @{members} ct original ip daddr {dst_ip} accept",
        )
