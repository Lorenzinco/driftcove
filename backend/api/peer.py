from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated

from backend.core.config import verify_token, settings
from backend.core.lock import lock
from backend.core.database import db
from backend.core.state_manager import state_manager
from backend.core.logger import logging
from backend.core.models import Peer, Subnet
from backend.core.wireguard import (
    apply_to_wg_config, generate_keys, generate_wg_config, remove_from_wg_config
)

# --- nftables helpers (replace iptables usage) ---
from backend.core.nftables import (
    revoke_service,            # peer -> service tuple revoke
    revoke_public, del_member, # subnet membership removal
    add_p2p_link, remove_p2p_link,
)

router = APIRouter(tags=["peer"])

@router.post("/create", tags=["peer"])
def create_peer(username: str, subnet: str, _: Annotated[str, Depends(verify_token)],
                address: str | None = None):
    """
    Create (or recreate) a peer, add to WG config, and return its config.
    NOTE: Networking permissions are handled by subnet/service/p2p endpoints.
    """
    keys = generate_keys()
    if len(username) <= 0 or len(username) > 15:
        raise HTTPException(status_code=400, detail="Username must be between 1 and 15 characters long")
    with lock.write_lock(), state_manager.saved_state():
        try:
            # If peer exists, remove it first (DB + WG entry will be replaced)
            old_peer = db.get_peer_by_username(username)
            if old_peer is not None:
                db.remove_peer(old_peer)

            subnet_obj: Subnet | None = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            if address is not None:
                if db.is_ip_already_assigned(address):
                    raise HTTPException(status_code=400, detail="IP address is already assigned")
                if not db.is_ip_in_subnet(address, subnet_obj):
                    raise HTTPException(status_code=400, detail="IP address is not in the subnet")
            else:
                address = db.get_avaliable_ip(subnet_obj)

            if address is None:
                raise HTTPException(status_code=401, detail="No available IPs in subnet")

            peer = Peer(
                username=username,
                public_key=keys["public_key"],
                preshared_key=keys["preshared_key"],
                address=address,
                x=subnet_obj.x,
                y=subnet_obj.y,
            )
            logging.info(f"Adding peer {peer} to the database")
            db.create_peer(peer)

            if old_peer is not None:
                remove_from_wg_config(old_peer)

            apply_to_wg_config(peer)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database/WG update failed: {e}")

    configuration = generate_wg_config(peer, keys["private_key"])
    return {"configuration": configuration}


@router.get("/config", tags=["peer"])
def regenerate_config(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Rotate keys and regenerate a WireGuard config for the peer.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")

            keys = generate_keys()

            # Remove old key from WG, update DB, re-apply
            remove_from_wg_config(peer)
            peer.public_key = keys["public_key"]
            peer.preshared_key = keys["preshared_key"]
            db.update_peer(peer)
            apply_to_wg_config(peer)
            logging.info(f"Generating new config for peer {peer}")
            configuration = generate_wg_config(peer, keys["private_key"])
            return {"configuration": configuration}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Config generation failed: {e}")


@router.get("/info", tags=["peer"])
def get_peer_info(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Return metadata about a peer.
    """
    try:
        with lock.read_lock():
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")

        return {
            "username": peer.username,
            "public_key": peer.public_key,
            "address": peer.address,
            "preshared_key": peer.preshared_key,
            "x": peer.x,
            "y": peer.y,
            "services": peer.services,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")


@router.get("/all", tags=["peer"])
def get_all_peers():
    """
    Retrieve all peers.
    """
    with lock.read_lock():
        try:
            peer_list: list[Peer] = db.get_all_peers()
        except Exception as e:
            logging.error(f"Error retrieving peers: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get peer list: {e}")
    return {"peers": peer_list}


@router.delete("/", tags=["peer"])
def delete_peer(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Delete a peer: revoke nftables grants, remove WG entry, and delete from DB.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")

            logging.info(f"Removing peer {peer.username} ({peer.address})")

            # 1) Revoke peer→service grants this peer consumes
            peer_services = db.get_peer_services(peer)
            for service in peer_services:
                host = db.get_service_host(service)
                if host:
                    revoke_service(peer.address, host.address, service.port)
                db.remove_peer_service_link(peer, service)

            # 2) If peer hosts services, revoke guests' grants to those services and delete the services
            hosted_services = db.get_services_by_host(peer)
            for service in hosted_services:
                service_peers = db.get_service_peers(service)
                for guest_peer in service_peers:
                    revoke_service(guest_peer.address, peer.address, service.port)
                    db.remove_peer_service_link(guest_peer, service)
                db.delete_service(service)

            # 3) Remove peer from every subnet it belongs to (membership + public flag)
            peer_subnets = db.get_peers_links_to_subnets(peer)
            for s in peer_subnets:
                revoke_public(s.subnet, peer.address)
                del_member(s.subnet, peer.address)
                db.remove_link_from_peer_from_subnet(peer, s)

            # 4) Remove P2P links (nft + DB)
            # If you have a direct getter use it; else derive from dict
            links = db.get_links_between_peers()  # dict: src_ip -> [dst_peer]
            for dst in links.get(peer.address, []):
                remove_p2p_link(peer.address, dst.address)
                db.remove_link_between_two_peers(peer, dst)
            # Also remove reverse edges if they exist
            for src_ip, dst_list in links.items():
                for dst in dst_list:
                    if dst.address == peer.address:
                        remove_p2p_link(src_ip, peer.address)
                        src_peer = db.get_peer_by_address(src_ip)
                        if src_peer:
                            db.remove_link_between_two_peers(src_peer, peer)

            # 5) Remove from WireGuard + DB
            remove_from_wg_config(peer)
            db.remove_peer(peer)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete peer {username}: {e}")

    return {"message": "Peer removed"}


@router.get("/subnets", tags=["peer"])
def get_user_subnets(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Return the peer's primary subnet and the list of subnets it is linked to.
    """
    with lock.read_lock():
        try:
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            subnet = db.get_peers_subnet(peer)
            subnet_links = db.get_peers_links_to_subnets(peer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"subnet": subnet, "links": subnet_links}


@router.post("/connect", tags=["peer"])
def connect_two_peers(peer1_username: str, peer2_username: str,
                      _: Annotated[str, Depends(verify_token)]):
    """
    Connect two peers (bidirectional) via nftables p2p links.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer1 = db.get_peer_by_username(peer1_username)
            peer2 = db.get_peer_by_username(peer2_username)
            if peer1 is None or peer2 is None:
                raise HTTPException(status_code=404, detail="One or both peers not found")

            add_p2p_link(peer1.address, peer2.address)  # inserts both directions
            db.add_link_between_two_peers(peer1, peer2)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connecting the two peers failed: {e}")
    return {"message": f"Peers {peer1_username} and {peer2_username} connected"}


@router.delete("/disconnect", tags=["peer"])
def disconnect_two_peers(peer1_username: str, peer2_username: str,
                         _: Annotated[str, Depends(verify_token)]):
    """
    Disconnect two peers (remove nftables p2p links and DB edge).
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer1 = db.get_peer_by_username(peer1_username)
            peer2 = db.get_peer_by_username(peer2_username)
            if peer1 is None or peer2 is None:
                raise HTTPException(status_code=404, detail="One or both peers not found")

            remove_p2p_link(peer1.address, peer2.address)  # removes both directions
            db.remove_link_between_two_peers(peer1, peer2)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnecting the two peers failed: {e}")
    return {"message": f"Peers {peer1_username} and {peer2_username} disconnected"}
