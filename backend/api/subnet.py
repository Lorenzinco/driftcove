from fastapi import APIRouter, HTTPException, Depends
from backend.core.config import verify_token
from backend.core.database import db
from backend.core.state_manager import state_manager
from backend.core.lock import lock
from backend.core.iptables import allow_link, remove_link
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
    """ Connects a peer named username to a specific subnet if both exist.
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
            peers: list[Peer] = db.get_peers_in_subnet(subnet_obj)
            for peer in peers:
                db.remove_link_from_peer_from_subnet(peer, subnet_obj)
                remove_link(peer.address, subnet)
            db.delete_subnet(subnet_obj)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Deleting subnet {subnet} failed: {e}")
        
    return {"message": "Subnet deleted"}


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