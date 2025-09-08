from fastapi import APIRouter, HTTPException, Depends
from backend.core.config import verify_token
from backend.core.database import db
from backend.core.state_manager import state_manager
from backend.core.wireguard import remove_from_wg_config
from backend.core.lock import lock
from backend.core.iptables import allow_link, remove_link, remove_link_with_port, remove_answers_link
from backend.core.models import Subnet, Peer
from backend.core.logger import logging
from typing import Annotated



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
            peer: Peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            subnet: Subnet = db.get_subnet_by_address(subnet)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            db.add_link_from_peer_to_subnet(peer, subnet)
            logging.info(f"Adding peer {peer.username} to subnet {subnet.subnet}")
            allow_link(peer.address, subnet.subnet)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connecting peer {username} to subnet {subnet} failed: {e}")
    
    return {"message": "Peer connected to subnet"}

@router.delete("/",tags=["subnet"])
def delete_subnet(subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
    Deletes a subnet.
    This endpoint will delete a subnet from the database, all the peers who had this subnet on their allowed ips will get it removed.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            subnet_obj: Subnet = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            
            peers_linked = db.get_peers_linked_to_subnet(subnet_obj)
            for peer in peers_linked:
                remove_link(peer.address, subnet_obj.subnet)
                remove_link(subnet_obj.subnet, peer.address)
            
            service_links = db.get_links_from_subnets_to_services()
            for service in service_links.get(subnet_obj.subnet, []):
                host = db.get_service_host(service)
                if host:
                    remove_link_with_port(subnet_obj.subnet, host.address, service.port)
                    remove_answers_link(host.address, subnet_obj.subnet)
                db.remove_link_from_subnet_to_service(subnet_obj, service)

            subnets_linked = db.get_links_between_subnets()
            for other_subnet in subnets_linked.get(subnet_obj.subnet, []):
                remove_link(subnet_obj.subnet, other_subnet.subnet)
                remove_link(other_subnet.subnet, subnet_obj.subnet)
                db.remove_link_between_subnets(subnet_obj, other_subnet)
            
            db.delete_subnet(subnet_obj)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Subnet deletion failed: {e}")
    return {"message": "Subnet deleted"}

# Aliases for clarity: expose /delete and /delete/with_peers endpoints
@router.delete("/delete", tags=["subnet"])
def delete_subnet_alias(subnet: str, token: Annotated[str, Depends(verify_token)]):
    return delete_subnet(subnet, token)

@router.delete("/with_peers",tags=["subnet"])
def delete_subnet_with_peers(subnet: str, token: Annotated[str, Depends(verify_token)]):
    """
    Deletes a subnet and all the peers inside it.
    This endpoint will delete a subnet from the database, all the peers who had this subnet on their allowed ips will get deleted as well.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            subnet_obj: Subnet = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            
            peers_linked = db.get_peers_linked_to_subnet(subnet_obj)
            for peer in peers_linked:
                remove_link(peer.address, subnet_obj.subnet)
                remove_link(subnet_obj.subnet, peer.address)

            service_links = db.get_links_from_subnets_to_services()
            for service in service_links.get(subnet_obj.subnet, []):
                host = db.get_service_host(service)
                if host:
                    remove_link_with_port(subnet_obj.subnet, host.address, service.port)
                    remove_answers_link(host.address, subnet_obj.subnet)
                db.remove_link_from_subnet_to_service(subnet_obj, service)

            subnets_linked = db.get_links_between_subnets()
            for other_subnet in subnets_linked.get(subnet_obj.subnet, []):
                remove_link(subnet_obj.subnet, other_subnet.subnet)
                remove_link(other_subnet.subnet, subnet_obj.subnet)
                db.remove_link_between_subnets(subnet_obj, other_subnet)

            peers_inside = db.get_peers_in_subnet(subnet_obj)
            for peer in peers_inside:
                peer = db.get_peer_by_username(peer.username)
                if peer is None:
                    raise HTTPException(status_code=404, detail="Peer not found")
                peer_subnets = db.get_peers_links_to_subnets(peer)
                peer_services = db.get_peer_services(peer)
                logging.info(f"Removing peer {peer} from the database")
                logging.info(f"{peer_services}")

                # remove links for the subnets the peer is part of
                for subnet in peer_subnets:
                    remove_link(peer.address, subnet.subnet)

                # remove links for the services the peer is part of
                for service in peer_services:
                    service_host = db.get_service_host(service)
                    if service_host is None:
                        continue
                    remove_link_with_port(peer.address, service_host.address, service.port)
                    remove_answers_link(service_host.address, peer.address)

                # remove links for the services that the peer hosts
                hosted_services = db.get_services_by_host(peer)
                for service in hosted_services:
                    service_peers = db.get_service_peers(service)
                    for service_peer in service_peers:
                        remove_link_with_port(service_peer.address, peer.address, service.port)
                        remove_answers_link(peer.address, service_peer.address)
                
                remove_from_wg_config(peer)
                db.remove_peer(peer)

            db.delete_subnet(subnet_obj)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Subnet and linked peers deletion failed: {e}")
    return {"message": "Subnet and linked peers deleted"}

@router.delete("/disconnect",tags=["subnet"])
def disconnect_peer_from_subnet(username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
        Removes a peer from a specific subnet, if both exist. 
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer: Peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            subnet: Subnet = db.get_subnet_by_address(subnet)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            
            db.remove_link_from_peer_from_subnet(peer, subnet)
            remove_link(peer.address, subnet.subnet)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnection of peer {username} from subnet {subnet} failed: {e}")
    return {"message": "Peer disconnected from subnet"}