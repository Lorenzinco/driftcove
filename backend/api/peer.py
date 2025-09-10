from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated

from backend.core.config import verify_token, settings
from backend.core.lock import lock
from backend.core.database import db
from backend.core.state_manager import state_manager
from backend.core.logger import logging
from backend.core.models import Peer, Subnet
import ipaddress
from backend.core.wireguard import (
    apply_to_wg_config, generate_keys, generate_wg_config, remove_from_wg_config
)

# --- nftables helpers (replace iptables usage) ---
from backend.core.nftables import (
    revoke_service,            # peer -> service tuple revoke
    revoke_public, del_member, # subnet membership removal
    add_p2p_link, remove_p2p_link,
    add_member,
    grant_admin_peer_to_peer,
    revoke_admin_peer_to_peer,
    revoke_admin_peer_to_subnet,
    _purge_pair_set_for_ip,
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
                raise HTTPException(status_code=400, detail="Peer with this username already exists")

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
            apply_to_wg_config(peer)

            logging.info(f"Adding peer {peer.username}'s ruleset to nftables")
            subnets = db.get_peers_subnets(peer)
            if not subnets:
                raise HTTPException(status_code=404, detail=f"Peer {peer.username} is not in any subnet")
            for subnet in subnets:
                logging.info(f"Adding nftables rules for subnet {subnet}")
                add_member(subnet.subnet, peer.address)

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
            helper_remove_peer(peer)
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
            subnets = db.get_peers_subnets(peer)
            if subnets is None or len(subnets) == 0:
                raise HTTPException(status_code=404, detail="Peer is not in any subnet")
            #take the tightest matching subnet as primary
            best = None
            best_pl = -1
            for s in subnets:
                net_str = getattr(s, "address", None) or getattr(s, "subnet", None)
                if not net_str:
                    continue
                try:
                    pl = ipaddress.ip_network(net_str, strict=False).prefixlen
                except ValueError:
                    continue
                if pl > best_pl:
                    best_pl = pl
                    best = s
            subnet = best or subnets[0]
            subnet_links = db.get_links_from_peer_to_subnets(peer)
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
            db.add_link_from_peer_to_peer(peer1, peer2)

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
            db.remove_link_from_peer_to_peer(peer1, peer2)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnecting the two peers failed: {e}")
    return {"message": f"Peers {peer1_username} and {peer2_username} disconnected"}

@router.post("/admin/peer/connect", tags=["peer","admin"])
def connect_admin_peer_to_peer(admin_username: str, peer_username: str,
                      _: Annotated[str, Depends(verify_token)]):
    """
    Connect an admin peer to a regular peer via nftables p2p links.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            admin_peer = db.get_peer_by_username(admin_username)
            peer = db.get_peer_by_username(peer_username)
            if admin_peer is None or peer is None:
                raise HTTPException(status_code=404, detail="One or both peers not found")

            grant_admin_peer_to_peer(admin_peer.address, peer.address)
            db.add_admin_link_from_peer_to_peer(admin_peer, peer)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connecting the two peers failed: {e}")
    return {"message": f"Admin peer {admin_username} and peer {peer_username} connected"}

@router.delete("/admin/peer/disconnect", tags=["peer","admin"])
def disconnect_admin_peer_from_peer(admin_username: str, peer_username: str,
                         _: Annotated[str, Depends(verify_token)]):
    """
    Disconnect an admin peer from a regular peer (remove nftables p2p links and DB edge).
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            admin_peer = db.get_peer_by_username(admin_username)
            peer = db.get_peer_by_username(peer_username)
            if admin_peer is None or peer is None:
                raise HTTPException(status_code=404, detail="One or both peers not found")

            revoke_admin_peer_to_peer(admin_peer.address, peer.address)  # removes both directions
            db.remove_admin_link_from_peer_to_peer(admin_peer, peer)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnecting the two peers failed: {e}")
    return {"message": f"Admin peer {admin_username} and peer {peer_username} disconnected"}

def helper_remove_peer(peer: Peer):
    try:
        logging.info(f"Removing peer {peer.username} ({peer.address}) via helper")
        # 1) remove incoming peer to service rules and db entries
        hosting_services = db.get_services_by_host(peer)
        for service in hosting_services:
            service_peers = db.get_peers_linked_to_service(service)
            for guest_peer in service_peers:
                revoke_service(guest_peer.address, peer.address, service.port)
                db.remove_link_from_peer_to_service(guest_peer, service)
            db.remove_service(service)

        # 2) remove outgoing peer to service rules and db entries
        peer_services = db.get_peer_services(peer)
        for service in peer_services:
            host = db.get_service_host(service)
            if host:
                revoke_service(peer.address, host.address, service.port)
            db.remove_link_from_peer_to_service(peer, service)

        # 3a) Remove peer from every subnet it belongs to (membership)
        peer_subnets = db.get_links_from_peer_to_subnets(peer)
        for s in peer_subnets:
            revoke_public(s.subnet, peer.address)
            del_member(s.subnet, peer.address)
            db.remove_link_from_peer_to_subnet(peer, s)
        
        # 3b) Remove peer from every subnet it falls inside (address space)
        all_subnets = db.get_all_subnets()
        for s in all_subnets:
            if db.is_ip_in_subnet(peer.address, s):
                revoke_public(s.subnet, peer.address)
                del_member(s.subnet, peer.address)

        # 4a) Remove P2P links (nft + DB)
        p2p_links = db.get_links_from_peer_to_peer()  # dict: src_ip -> [dst_peer]
        for dst in p2p_links.get(peer.address, []):
            remove_p2p_link(peer.address, dst.address)
            db.remove_link_from_peer_to_peer(peer, dst)

        # 4b) Remove reverse P2P links (nft + DB)
        all_peers = db.get_all_peers()
        for other_peer in all_peers:
            for dst in p2p_links.get(other_peer.address, []):
                if dst.address == peer.address:
                    remove_p2p_link(other_peer.address, peer.address)
                    db.remove_link_from_peer_to_peer(other_peer, peer)
                    break

        # 4c) Remove all pairs involving this peer
        _purge_pair_set_for_ip("p2p_links", peer.address)

        # 5a) Remove admin peer to peer links if any
        admin_peer_to_peer_links = db.get_admin_links_from_peer_to_peer()
        for other_peer in admin_peer_to_peer_links.get(peer.address, []):
            revoke_admin_peer_to_peer(peer.address, other_peer.address)
            db.remove_admin_link_from_peer_to_peer(peer, other_peer)

        # 5b) Remove reverse admin peer to peer links if any
        for other_peer in all_peers:
            for dst in admin_peer_to_peer_links.get(other_peer.address, []):
                if dst.address == peer.address:
                    revoke_admin_peer_to_peer(other_peer.address, peer.address)
                    db.remove_admin_link_from_peer_to_peer(other_peer, peer)
                    break

        # 6) Remove admin peer to subnet links if any
        admin_links_from_peer_to_subnets = db.get_admin_links_from_peer_to_subnet()
        for subnet in admin_links_from_peer_to_subnets.get(peer.address, []):
            revoke_admin_peer_to_subnet(peer.address, subnet.subnet)
            db.remove_admin_link_from_peer_to_subnet(peer, subnet)
        
        # 7) Remove from WireGuard + DB
        remove_from_wg_config(peer)
        db.remove_peer(peer)
    except Exception as e:
        logging.error(f"Error in helper_remove_peer for {peer.username}: {e}")
        return