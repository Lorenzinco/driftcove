from fastapi import APIRouter, HTTPException, Depends
from backend.core.config import verify_token
from backend.core.database import db
from backend.core.state_manager import state_manager
from backend.core.wireguard import remove_from_wg_config
from backend.core.lock import lock
from backend.core.models import Subnet, Peer
from backend.core.logger import logging
from typing import Annotated
from backend.core.nftables import (
    add_member,
    make_public,
    ensure_subnet,
    disconnect_subnet_from_subnet_public,
    disconnect_subnets_bidirectional_public,
    destroy_subnet,
    revoke_subnet_service,
    del_member,
    revoke_public,
    revoke_service,
    grant_admin_peer_to_subnet,
    revoke_admin_peer_to_subnet,
    revoke_admin_subnet_to_subnet,
    revoke_admin_peer_to_peer,
    remove_p2p_link
)
from backend.api.peer import helper_remove_peer
import ipaddress



router = APIRouter(tags=["subnet"])

@router.post("/create",tags=["subnet"])
def create_subnet(subnet: Subnet, _: Annotated[str, Depends(verify_token)]):
    """
    Create a new subnet.
    This endpoint will add a new subnet to the database, to add peers into this subnet please see the other endpoint.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            db.create_subnet(subnet)
            ensure_subnet(subnet.subnet)
            # Auto-snap existing peers whose address already resides inside this subnet's CIDR.
            peers_in_subnet = db.get_peers_in_subnet(subnet)
            for peer in peers_in_subnet:
                # Persist membership link (DB) so frontend immediately reflects containment.
                try:
                    db.add_link_from_peer_to_subnet(peer, subnet)
                except Exception as inner_e:
                    logging.warning(f"Peer {peer.username} membership insert failed (possibly duplicate): {inner_e}")
                # nftables membership (do NOT mark public here; explicit connect endpoint handles that)
                add_member(subnet.subnet, peer.address)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Subnet creation failed: {e}")
    
    return {"message": "Subnet created"}

@router.post("/connect",tags=["subnet"])
def connect_peer_to_subnet(username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """ 
    Makes a peer public inside a specific subnet. A peer being public means that other peers inside the subnet can connect to it and he can connect to other public peers inside that subnet.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer_obj = db.get_peer_by_username(username)
            if peer_obj is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            subnet_obj = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            db.add_link_from_peer_to_subnet(peer_obj, subnet_obj)
            logging.info(f"Adding peer {peer_obj.username} to subnet {subnet_obj.subnet}")
            ensure_subnet(subnet_obj.subnet)
            add_member(subnet_obj.subnet, peer_obj.address)
            make_public(subnet_obj.subnet, peer_obj.address)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connecting peer {username} to subnet {subnet} failed: {e}")
    
    return {"message": "Peer connected to subnet"}

@router.delete("/", tags=["subnet"])
def delete_subnet(subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
    Deletes a subnet. Also cleans up nftables state for that subnet.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            subnet_obj: Subnet = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            helper_remove_subnet(subnet_obj)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Subnet deletion failed: {e}")

    return {"message": "Subnet deleted"}

@router.delete("/with_peers", tags=["subnet"])
def delete_subnet_with_peers(subnet: str, token: Annotated[str, Depends(verify_token)]):
    """
    Deletes a subnet and all the peers inside it.
    Cleans up nftables grants/links, WireGuard peers, and DB entries.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            subnet_obj: Subnet = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            # 1 a) Remove links to this subnet from all peers
            peers_in_subnet = db.get_links_from_peer_to_subnet()
            for peer in peers_in_subnet.get(subnet_obj.subnet, []):
                db.remove_link_from_peer_to_subnet(peer, subnet_obj)
                revoke_public(subnet_obj.subnet, peer.address)
                del_member(subnet_obj.subnet, peer.address)
            # 1 b) Remove leftover peer in the subnet that didn't have a link to it ( is inside the address range but no link)
            all_peers = db.get_all_peers()
            for peer in all_peers:
                if db.get_links_from_peer_to_subnets(peer).count(subnet_obj) == 0:
                    # Check if the peer's address is in the subnet range
                    try:
                        subnet_network = ipaddress.ip_network(subnet_obj.subnet, strict=False)
                        peer_ip = ipaddress.ip_address(peer.address)
                        if peer_ip in subnet_network:
                            logging.info(f"Removing peer {peer.username} from subnet {subnet_obj.subnet} due to address containment")
                            revoke_public(subnet_obj.subnet, peer.address)
                            del_member(subnet_obj.subnet, peer.address)
                    except ValueError as ve:
                        logging.warning(f"Invalid IP address or subnet format: {ve}")

            # 2) Revoke subnet -> service grants for this subnet
            service_links = db.get_links_from_subnet_to_service()
            for service in service_links.get(subnet_obj.subnet, []):
                host = db.get_service_host(service)
                if host:
                    revoke_subnet_service(subnet_obj.subnet, host.address, service.port)
                db.remove_link_from_subnet_to_service(subnet_obj, service)

            # 3) Remove cross-subnet(public) links (both directions)
            subnets_linked = db.get_links_from_subnet_to_subnet()
            for other_subnet in subnets_linked.get(subnet_obj.subnet, []):
                disconnect_subnets_bidirectional_public(subnet_obj.subnet, other_subnet.subnet)
                db.remove_link_from_subnet_to_subnet(subnet_obj, other_subnet)

            # 4 a) Destroy admin links involving this subnet as the source
            admin_subnet_to_subnet_links = db.get_admin_links_from_subnet_to_subnet()
            for target_subnet in admin_subnet_to_subnet_links.get(subnet_obj.subnet, []):
                db.remove_admin_link_from_subnet_to_subnet(subnet_obj, target_subnet)
                revoke_admin_subnet_to_subnet(subnet_obj.subnet, target_subnet.subnet)

            # 4 b) Refetch the links so no links with this subnet remain and also remove links where this subnet is the target
            admin_subnet_to_subnet_links = db.get_admin_links_from_subnet_to_subnet()
            all_subnets = db.get_all_subnets()
            for subnet_other in all_subnets:
                for target_subnet in admin_subnet_to_subnet_links.get(subnet_other.subnet, []):
                    if target_subnet.subnet == subnet_obj.subnet:
                        db.remove_admin_link_from_subnet_to_subnet(subnet_other, subnet_obj)
                        revoke_admin_subnet_to_subnet(subnet_other.subnet, subnet_obj.subnet)

            # 4 c) Destroy admin links from peers involving this subnet as the target
            admin_peer_to_subnet_links = db.get_admin_links_from_peer_to_subnet()
            all_peers = db.get_all_peers()
            for peer in all_peers:
                for target_subnet in admin_peer_to_subnet_links.get(peer.address, []):
                    if target_subnet.subnet == subnet_obj.subnet:
                        db.remove_admin_link_from_peer_to_subnet(peer, target_subnet)
                        revoke_admin_peer_to_subnet(peer.address, target_subnet.subnet)

            #5 a) Destroy any subnet inside this subnet
            nested_subnets = db.get_all_subnets()
            for target_subnet in nested_subnets:
                try:
                    # Check if the target_subnet is fully contained within the subnet to be deleted
                    parent_network = ipaddress.ip_network(subnet_obj.subnet, strict=False)
                    target_network = ipaddress.ip_network(target_subnet.subnet, strict=False)
                    if target_network.subnet_of(parent_network) and target_subnet.subnet != subnet_obj.subnet:
                        logging.info(f"Also deleting nested subnet {target_subnet.subnet} inside {subnet_obj.subnet}")
                        helper_remove_subnet(target_subnet)
                except ValueError as ve:
                    logging.warning(f"Invalid IP address or subnet format when checking nested subnets: {ve}")

            #5 b) Destroy all peers inside this subnet
            peers_in_subnet = db.get_peers_in_subnet(subnet_obj)
            for peer in peers_in_subnet:
                logging.info(f"Also deleting peer {peer.username} inside subnet {subnet_obj.subnet}")
                helper_remove_peer(peer)

            # 6) Finally destroy nftables artifacts for the subnet and delete it from DB
            destroy_subnet(subnet_obj.subnet, destroy_all_traffic_to_peers_inside=True)
            db.remove_subnet(subnet_obj)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Subnet deletion failed: {e}")

    return {"message": "Subnet and linked peers deleted"}

@router.delete("/disconnect", tags=["subnet"])
def disconnect_peer_from_subnet(username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
    Removes a peer from a specific subnet.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer: Peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")

            subnet_obj: Subnet = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            db.remove_link_from_peer_to_subnet(peer, subnet_obj)

            # nftables: reverse what connect did
            revoke_public(subnet_obj.subnet, peer.address)
            del_member(subnet_obj.subnet, peer.address)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnection of peer {username} from subnet {subnet} failed: {e}")

    return {"message": "Peer disconnected from subnet"}

@router.post("/admin/connect",tags=["subnet","admin"])
def admin_connect_peer_to_subnet(admin_username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """ 
    Makes a peer an admin of a specific subnet. An admin peer can connect to any other peer inside the subnet, even if they are not public.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer_obj = db.get_peer_by_username(admin_username)
            if peer_obj is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            subnet_obj = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            db.add_admin_link_from_peer_to_subnet(peer_obj, subnet_obj)
            logging.info(f"Adding admin peer {peer_obj.username} to subnet {subnet_obj.subnet}")
            ensure_subnet(subnet_obj.subnet)
            grant_admin_peer_to_subnet(peer_obj.address, subnet_obj.subnet)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connecting admin peer {admin_username} to subnet {subnet} failed: {e}")
    
    return {"message": "Admin peer connected to subnet"}

@router.delete("/admin/disconnect", tags=["subnet","admin"])
def admin_disconnect_peer_from_subnet(admin_username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
    Removes a peer's admin status from a specific subnet.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer: Peer = db.get_peer_by_username(admin_username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")

            subnet_obj: Subnet = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            db.remove_admin_link_from_peer_to_subnet(peer, subnet_obj)

            # nftables: reverse what admin connect did
            revoke_admin_peer_to_subnet(peer.address, subnet_obj.subnet)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnection of admin peer {admin_username} from subnet {subnet} failed: {e}")

    return {"message": "Admin peer disconnected from subnet"}

def helper_remove_subnet(subnet: Subnet):
    """
    Helper function to remove a subnet and all its references, without acquiring locks or managing state.
    This is intended for internal use only, e.g. when removing a peer that may be in subnets.
    """
    try:
        # 1 a) Remove links to this subnet from all peers
        peers_in_subnet = db.get_links_from_peer_to_subnet()
        for peer in peers_in_subnet.get(subnet.subnet, []):
            db.remove_link_from_peer_to_subnet(peer, subnet)
            revoke_public(subnet.subnet, peer.address)
            del_member(subnet.subnet, peer.address)
        # 1 b) Remove leftover peer in the subnet that didn't have a link to it ( is inside the address range but no link)
        all_peers = db.get_all_peers()
        for peer in all_peers:
            if db.get_links_from_peer_to_subnets(peer).count(subnet) == 0:
                # Check if the peer's address is in the subnet range
                try:
                    subnet_network = ipaddress.ip_network(subnet.subnet, strict=False)
                    peer_ip = ipaddress.ip_address(peer.address)
                    if peer_ip in subnet_network:
                        logging.info(f"Removing peer {peer.username} from subnet {subnet.subnet} due to address containment")
                        revoke_public(subnet.subnet, peer.address)
                        del_member(subnet.subnet, peer.address)
                except ValueError as ve:
                    logging.warning(f"Invalid IP address or subnet format: {ve}")

        # 2) Revoke subnet -> service grants for this subnet
        service_links = db.get_links_from_subnet_to_service()
        for service in service_links.get(subnet.subnet, []):
            host = db.get_service_host(service)
            if host:
                revoke_subnet_service(subnet.subnet, host.address, service.port)
            db.remove_link_from_subnet_to_service(subnet, service)

        # 3) Remove cross-subnet(public) links (both directions)
        subnets_linked = db.get_links_from_subnet_to_subnet()
        for other_subnet in subnets_linked.get(subnet.subnet, []):
            disconnect_subnets_bidirectional_public(subnet.subnet, other_subnet.subnet)
            db.remove_link_from_subnet_to_subnet(subnet, other_subnet)

        # 4 a) Destroy admin links involving this subnet as the source
        admin_subnet_to_subnet_links = db.get_admin_links_from_subnet_to_subnet()
        for target_subnet in admin_subnet_to_subnet_links.get(subnet.subnet, []):
            db.remove_admin_link_from_subnet_to_subnet(subnet, target_subnet)
            revoke_admin_subnet_to_subnet(subnet.subnet, target_subnet.subnet)

        # 4 b) Refetch the links so no links with this subnet remain and also remove links where this subnet is the target
        admin_subnet_to_subnet_links = db.get_admin_links_from_subnet_to_subnet()
        all_subnets = db.get_all_subnets()
        for subnet_other in all_subnets:
            for target_subnet in admin_subnet_to_subnet_links.get(subnet_other.subnet, []):
                if target_subnet.subnet == subnet.subnet:
                    db.remove_admin_link_from_subnet_to_subnet(subnet_other, subnet)
                    revoke_admin_subnet_to_subnet(subnet_other.subnet, subnet.subnet)

        # 4 c) Destroy admin links from peers involving this subnet as the target
        admin_peer_to_subnet_links = db.get_admin_links_from_peer_to_subnet()
        all_peers = db.get_all_peers()
        for peer in all_peers:
            for target_subnet in admin_peer_to_subnet_links.get(peer.address, []):
                if target_subnet.subnet == subnet.subnet:
                    db.remove_admin_link_from_peer_to_subnet(peer, target_subnet)
                    revoke_admin_peer_to_subnet(peer.address, target_subnet.subnet)
        # 5) Finally destroy nftables artifacts for the subnet and delete it from DB
        destroy_subnet(subnet.subnet)
        db.remove_subnet(subnet)
    except Exception as e:
        logging.error(f"Failed to remove subnet {subnet.subnet} in helper: {e}")
        raise e