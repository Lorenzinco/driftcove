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
    destroy_subnet,
    revoke_subnet_service,
    del_member,
    revoke_public,
    revoke_service
)



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

            # 1) Revoke subnet -> service grants
            service_links = db.get_links_from_subnets_to_services()
            for service in service_links.get(subnet_obj.subnet, []):
                host = db.get_service_host(service)
                if host:
                    revoke_subnet_service(subnet_obj.subnet, host.address, service.port)
                db.remove_link_from_subnet_to_service(subnet_obj, service)

            # 2) Remove cross-subnet(public) links (both directions if you stored both)
            subnets_linked = db.get_links_between_subnets()
            for other_subnet in subnets_linked.get(subnet_obj.subnet, []):
                disconnect_subnet_from_subnet_public(subnet_obj.subnet, other_subnet.subnet)
                disconnect_subnet_from_subnet_public(other_subnet.subnet, subnet_obj.subnet)
                db.remove_link_between_subnets(subnet_obj, other_subnet)

            # 3) (Optional) If you tracked admin subnet grants involving this subnet,
            #    revoke them here using your admin revoke helpers.

            # 4) Destroy subnet sets + per-subnet rule
            destroy_subnet(subnet_obj.subnet)

            # 5) Finally remove from DB
            db.delete_subnet(subnet_obj)

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

            # 1) Revoke subnet -> service grants for this subnet
            service_links = db.get_links_from_subnets_to_services()
            for service in service_links.get(subnet_obj.subnet, []):
                host = db.get_service_host(service)
                if host:
                    revoke_subnet_service(subnet_obj.subnet, host.address, service.port)
                db.remove_link_from_subnet_to_service(subnet_obj, service)

            # 2) Remove cross-subnet(public) links (both directions)
            subnets_linked = db.get_links_between_subnets()
            for other_subnet in subnets_linked.get(subnet_obj.subnet, []):
                disconnect_subnet_from_subnet_public(subnet_obj.subnet, other_subnet.subnet)
                disconnect_subnet_from_subnet_public(other_subnet.subnet, subnet_obj.subnet)
                db.remove_link_between_subnets(subnet_obj, other_subnet)

            # 3) Remove peers inside this subnet
            peers_inside = db.get_peers_in_subnet(subnet_obj)
            for peer_ref in peers_inside:
                peer: Peer | None = db.get_peer_by_username(peer_ref.username)
                if peer is None:
                    raise HTTPException(status_code=404, detail=f"Peer {peer_ref.username} not found")

                logging.info(f"Removing peer {peer.username} ({peer.address})")

                # 3a) Revoke peer->service grants for services this peer consumes
                peer_services = db.get_peer_services(peer)
                for service in peer_services:
                    service_host = db.get_service_host(service)
                    if service_host:
                        revoke_service(peer.address, service_host.address, service.port)
                # Remove DB links
                db.remove_all_services_from_peer(peer)

                # 3b) If the peer hosts services, revoke guests' grants to those services
                hosted_services = db.get_services_by_host(peer)
                for service in hosted_services:
                    service_peers = db.get_service_peers(service)
                    for service_peer in service_peers:
                        revoke_service(service_peer.address, peer.address, service.port)
                        db.remove_peer_service_link(service_peer, service)
                    db.delete_service(service)  # remove the hosted service itself

                # 3c) Remove this peer from all subnets it belongs to
                peer_subnets = db.get_peers_links_to_subnets(peer)
                for s in peer_subnets:
                    revoke_public(s.subnet, peer.address)
                    del_member(s.subnet, peer.address)
                    db.remove_link_from_peer_from_subnet(peer, s)

                # 3d) Remove from WireGuard + DB
                remove_from_wg_config(peer)
                db.remove_peer(peer)

            # 4) Finally destroy nftables artifacts for the subnet and delete it from DB
            destroy_subnet(subnet_obj.subnet)
            db.delete_subnet(subnet_obj)

        except HTTPException:
            # re-raise HTTPException as-is
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Subnet and linked peers deletion failed: {e}")

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

            db.remove_link_from_peer_from_subnet(peer, subnet_obj)

            # nftables: reverse what connect did
            revoke_public(subnet_obj.subnet, peer.address)
            del_member(subnet_obj.subnet, peer.address)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnection of peer {username} from subnet {subnet} failed: {e}")

    return {"message": "Peer disconnected from subnet"}
