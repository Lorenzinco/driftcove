from fastapi import APIRouter, HTTPException, Depends
from app.core.config import verify_token, settings
from app.core.database import db
from app.core.iptables import allow_link, remove_link
from app.core.models import Peer
from app.core.wireguard import apply_to_wg_config, generate_keys, generate_wg_config, remove_from_wg_config
from typing import Annotated
import logging, subprocess

router = APIRouter(tags=["peer"])

@router.post("/create",tags=["peer"])
def create_peer(username:str , subnet:str, _: Annotated[str, Depends(verify_token)]):
    """
    Creates a peer and adds it to the wireguard configuration and returns a config, the assigned ip address is one inside the provided subnet. If the peer already exists, destroys the previous peer and creates another one, then returns a config.
    The peer after the creation cannot really connect to anything, it needs to be "added" to a subnet, which really just enables routes to that subnet for that peer.
    If you wish for selected peers to be able to connect to the peer, you need to use the connect endpoint.
    """
    keys = generate_keys()
    # start a transaction here

    old_peer = db.get_peer_by_username(username)
    logging.warning(f"Creating peer {username} with public key {keys['public_key']}")
    logging.warning(f"Old peer: {old_peer}, if none, it will be created anew")

    
    # database consistency
    try:
        # If the peer already exists, we remove it first
        logging.warning(f"Removing old peer {old_peer} if it exists")
        if old_peer:
            db.remove_peer(old_peer)

        logging.warning(f"Getting info for {subnet} from the database")
        subnet = db.get_subnet_by_address(subnet)
        logging.warning(f"Subnet found: {subnet}")
        if subnet is None:
            raise HTTPException(status_code=404, detail="Subnet not found")
        logging.warning(f"Getting an available IP address for peer {username} in subnet {subnet.subnet}")
        address = db.get_avaliable_ip(subnet)
        if address is None:
            raise HTTPException(status_code=500, detail="No available IPs in subnet")
        logging.warning(f"Assigned IP {address} to peer {username}")

        peer = Peer(username=username, public_key=keys["public_key"], preshared_key=keys["preshared_key"], address=address)
        logging.warning(f"Adding peer {peer} to the database")
        db.create_peer(peer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failed: {e}")
    try:
        # if the peer already exists, we remove it first
        if old_peer:
            remove_from_wg_config(old_peer)

        apply_to_wg_config(peer)

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer: {e}")
        
    configuration = generate_wg_config(peer, keys["private_key"])
    
    # close the transaction 
    return {"configuration": configuration}

@router.get("/get_info",tags=["peer"])
def get_peer_info(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Get information about a specific peer.
    This endpoint will return the public key and allowed IPs of the peer.
    """
    try:
        peer = db.get_peer_by_username(username)
        if not peer:
            raise HTTPException(status_code=404, detail="Peer not found")
        
        return {"username": peer.username, "public_key": peer.public_key, "address": peer.address}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")



@router.delete("/remove",tags=["peer"])
def remove_peer(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Remove a peer from the WireGuard configuration.
    """
    try:
        peer = db.get_peer_by_username(username)
        if peer is None:
            raise HTTPException(status_code=404, detail="Peer not found")
        peer_subnets = db.get_peers_subnets(peer)
        peer_services = db.get_peers_services(peer)
        for subnet in peer_subnets:
            remove_link(peer.address, subnet.subnet)
        for service in peer_services:
            remove_link(peer.address, service.address)
        remove_from_wg_config(peer)
        return {"message": "Peer removed"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove peer: {e}")
    

 
@router.get("/get_subnets",tags=["peer"])
def get_user_subnets(username: str, _: Annotated[str, Depends(verify_token)]):
    """
    Get all subnets that a peer is part of.
    This endpoint will return all the subnets that a peer is part of.
    """
    try:
        peer = db.get_peer_by_username(username)
        if peer is None:
            raise HTTPException(status_code=404, detail="Peer not found")
        subnets = db.get_peers_subnets(peer)
        return {"subnets": subnets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
@router.post("/connect",tags=["peer"])
def connect_two_peers(peer1_username:str, peer2_username:str, _: Annotated[str, Depends(verify_token)]):
    """
    Connect two peers, allowing them to communicate with each other.
    This endpoint will add the link between the two peers in iptables.
    """
    try:
        peer1_obj = db.get_peer_by_username(peer1_username)
        peer2_obj = db.get_peer_by_username(peer2_username)
        if peer1_obj is None or peer2_obj is None:
            raise HTTPException(status_code=404, detail="One or both peers not found")
        
        allow_link(peer1_obj.address, peer2_obj.address)
        allow_link(peer2_obj.address, peer1_obj.address)
        db.add_link_between_two_peers(peer1_obj, peer2_obj)
        return {"message": f"Peers {peer1_username} and {peer2_username} connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
@router.delete("/disconnect",tags=["peer"])
def disconnect_two_peers(peer1_username:str, peer2_username:str, _: Annotated[str, Depends(verify_token)]):
    """
    Disconnect two peers, removing the link between them in iptables.
    """
    try:
        peer1_obj = db.get_peer_by_username(peer1_username)
        peer2_obj = db.get_peer_by_username(peer2_username)
        if peer1_obj is None or peer2_obj is None:
            raise HTTPException(status_code=404, detail="One or both peers not found")
        
        remove_link(peer1_obj.address, peer2_obj.address)
        remove_link(peer2_obj.address, peer1_obj.address)
        db.remove_link_between_two_peers(peer1_obj, peer2_obj)
        return {"message": f"Peers {peer1_username} and {peer2_username} disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")