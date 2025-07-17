from fastapi import APIRouter, HTTPException, Depends
from app.core.config import verify_token, settings
from app.core.lock import lock
from app.core.database import db
from app.core.iptables import allow_link, remove_link
from app.core.models import Peer
from app.core.state_manager import state_manager
from app.core.logger import logging
from app.core.wireguard import apply_to_wg_config, generate_keys, generate_wg_config, remove_from_wg_config
from typing import Annotated

router = APIRouter(tags=["peer"])

@router.post("/create",tags=["peer"])
def create_peer(username:str , subnet:str, _: Annotated[str, Depends(verify_token)]):
    """
    Creates a peer and adds it to the wireguard configuration and returns a config, the assigned ip address is one inside the provided subnet. If the peer already exists, destroys the previous peer and creates another one, then returns a config.
    The peer after the creation cannot really connect to anything, it needs to be "added" to a subnet, which really just enables routes to that subnet for that peer.
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
            address = db.get_avaliable_ip(subnet)
            if address is None:
                raise HTTPException(status_code=500, detail="No available IPs in subnet")
            peer = Peer(username=username, public_key=keys["public_key"], preshared_key=keys["preshared_key"], address=address)
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
        
        return {"username": peer.username, "public_key": peer.public_key, "address": peer.address, "preshared_key": peer.preshared_key}
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
            for subnet in peer_subnets:
                remove_link(peer.address, subnet.subnet)
            for service in peer_services:
                remove_link(peer.address, service.address)
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
            raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
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
            raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": f"Peers {peer1_username} and {peer2_username} disconnected"}