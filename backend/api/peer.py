from fastapi import APIRouter, HTTPException, Depends
from backend.core.config import verify_token, settings
from backend.core.lock import lock
from backend.core.database import db
from backend.core.iptables import allow_link, remove_link, remove_link_with_port, remove_answers_link
from backend.core.models import Peer
from backend.core.state_manager import state_manager
from backend.core.logger import logging
from backend.core.wireguard import apply_to_wg_config, generate_keys, generate_wg_config, remove_from_wg_config
from typing import Annotated

router = APIRouter(tags=["peer"])

@router.post("/create",tags=["peer"])
def create_peer(username:str , subnet:str, _: Annotated[str, Depends(verify_token)],address: str | None = None):
    """
    Creates a peer and adds it to the wireguard configuration and returns a config, you can specify the address you want to assign to the peer or an automatic address will be found, if somebody already has that address or it is not in the address space of the subnet an error throws. The assigned ip address is one inside the provided subnet. If the peer already exists, destroys the previous peer and creates another one, then returns a config.
    The peer after the creation cannot connect to anything, it needs to be "added" to a subnet, which really just enables routes to that subnet for that peer.
    If you wish for selected peers to be able to connect to the peer, you need to use the connect endpoint.
    """

    keys = generate_keys()
    with lock.write_lock(), state_manager.saved_state():
        try:
            # If the peer already exists, we remove it first
            old_peer = db.get_peer_by_username(username)
            if old_peer is not None:
                db.remove_peer(old_peer)

            subnet = db.get_subnet_by_address(subnet)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            if address is not None:
                if db.is_ip_already_assigned(address):
                    raise HTTPException(status_code=400, detail="IP address is already assigned")
                if not db.is_ip_in_subnet(address, subnet):
                    raise HTTPException(status_code=400, detail="IP address specified is not in the subnet")
            else:
                address = db.get_avaliable_ip(subnet)
            # if an address is not found by dhcp then it is none, no repetition here
            if address is None:
                raise HTTPException(status_code=401, detail="No available IPs in subnet")
            # on creation put the peer in the middle of the subnet

            peer = Peer(username=username, public_key=keys["public_key"], preshared_key=keys["preshared_key"], address=address, x=subnet.x, y=subnet.y)
            logging.info(f"Adding peer {peer} to the database")
            db.create_peer(peer)
            # if the peer already exists, we remove it first
            if old_peer is not None:
                remove_from_wg_config(old_peer)

            apply_to_wg_config(peer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database update failed: {e}")
            
    configuration = generate_wg_config(peer, keys["private_key"])

    # close the transaction 
    return {"configuration": configuration}

@router.get("/config",tags=["peer"])
def get_peer_config(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Get the WireGuard configuration for a specific peer.
    This endpoint will return the WireGuard configuration file for the peer identified by the provided username.
    """
    try:
        with lock.read_lock():
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            configuration = generate_wg_config(peer)
        return {"configuration": configuration}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config generation failed: {e}")

@router.get("/info",tags=["peer"])
def get_peer_info(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Get information about a specific peer.
    This endpoint will return the public key and allowed IPs of the peer.
    """
    try:
        with lock.read_lock():
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")

        return {"username": peer.username, "public_key": peer.public_key, "address": peer.address, "preshared_key": peer.preshared_key, "x": peer.x, "y": peer.y, "services": peer.services}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")

@router.get("/all", tags=["peer"])
def get_all_peers():
    """
    Retrieve the complete list of peers
    """
    peer_list:list[Peer] = []
    with lock.read_lock():
        try:
            peer_list = db.get_all_peers()
        except Exception as e:
            logging.error(f"An error has occurred while retrieving the list: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get peer list: {e}")
    return {"peers":peer_list}


@router.delete("/",tags=["peer"])
def delete_peer(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Delete a peer from the WireGuard configuration.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer = db.get_peer_by_username(username)
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete peer {username}: {e}")
    return {"message": "Peer removed"}
    

 
@router.get("/subnets",tags=["peer"])
def get_user_subnets(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Get the subnet the peer is part of as well as the subnets towards which the peer has a link to.
    This endpoint will return all the subnets that a peer is part of.
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
    
@router.post("/connect",tags=["peer"])
def connect_two_peers(peer1_username:str, peer2_username:str, _: Annotated[str, Depends(verify_token)]):
    """
    Connect two peers, allowing them to communicate with each other.
    This endpoint will add the link between the two peers in iptables.
    """
    with lock.write_lock(),state_manager.saved_state():
        try:
            peer1_obj = db.get_peer_by_username(peer1_username)
            peer2_obj = db.get_peer_by_username(peer2_username)
            if peer1_obj is None or peer2_obj is None:
                raise HTTPException(status_code=404, detail="One or both peers not found")
            
            allow_link(peer1_obj.address, peer2_obj.address)
            allow_link(peer2_obj.address, peer1_obj.address)
            db.add_link_between_two_peers(peer1_obj, peer2_obj)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connecting the two peers failed: {e}")
    return {"message": f"Peers {peer1_username} and {peer2_username} connected"}
        
@router.delete("/disconnect",tags=["peer"])
def disconnect_two_peers(peer1_username:str, peer2_username:str, _: Annotated[str, Depends(verify_token)]):
    """
    Disconnect two peers, removing the link between them in iptables.
    """
    with lock.write_lock(),state_manager.saved_state():
        try:
            peer1_obj = db.get_peer_by_username(peer1_username)
            peer2_obj = db.get_peer_by_username(peer2_username)
            if peer1_obj is None or peer2_obj is None:
                raise HTTPException(status_code=404, detail="One or both peers not found")
            
            remove_link(peer1_obj.address, peer2_obj.address)
            remove_link(peer2_obj.address, peer1_obj.address)
            db.remove_link_between_two_peers(peer1_obj, peer2_obj)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Disconnecting the two peers failed: {e}")
    return {"message": f"Peers {peer1_username} and {peer2_username} disconnected"}