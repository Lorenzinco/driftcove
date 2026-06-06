from backend.core.nftables.commands import element_tuple, list_set_elements, nft_try


def add_p2p_link(a_ip: str, b_ip: str) -> None:
    nft_try(f"add element inet dcv p2p_links {{ {a_ip} . {b_ip} }}")
    nft_try(f"add element inet dcv p2p_links {{ {b_ip} . {a_ip} }}")


def remove_p2p_link(a_ip: str, b_ip: str) -> None:
    nft_try(f"delete element inet dcv p2p_links {{ {a_ip} . {b_ip} }}")
    nft_try(f"delete element inet dcv p2p_links {{ {b_ip} . {a_ip} }}")


def _purge_pair_set_for_ip(setname: str, ip: str) -> None:
    for element in list_set_elements(setname):
        pair = element_tuple(element)
        if len(pair) == 2:
            a, b = pair
            if a == ip or b == ip:
                nft_try(f"delete element inet dcv {setname} {{ {a} . {b} }}")


def grant_admin_peer_to_peer(src_ip: str, dst_ip: str) -> None:
    nft_try(f"add element inet dcv admin_links {{ {src_ip} . {dst_ip} }}")


def revoke_admin_peer_to_peer(src_ip: str, dst_ip: str) -> None:
    nft_try(f"delete element inet dcv admin_links {{ {src_ip} . {dst_ip} }}")


def grant_admin_peer_to_subnet(src_ip: str, dst_cidr: str) -> None:
    nft_try(f"add element inet dcv admin_peer2cidr {{ {src_ip} . {dst_cidr} }}")


def revoke_admin_peer_to_subnet(src_ip: str, dst_cidr: str) -> None:
    nft_try(f"delete element inet dcv admin_peer2cidr {{ {src_ip} . {dst_cidr} }}")
