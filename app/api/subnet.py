from fastapi import APIRouter, HTTPException, Depends
from app.core.config import verify_token
from app.core.database import db
from app.core.models import state_manager
from app.core.lock import lock
from app.core.iptables import allow_link, remove_link
from app.core.models import Subnet
from typing import Annotated
import logging



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
            state_manager.restore()
            raise HTTPException(status_code=500, detail=f"Subnet creation failed: {e}")
    
    return {"message": "Subnet created"}

@router.post("/connect",tags=["subnet"])
def connect_peer_to_subnet(username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """ Connects a peer named username to a specific subnet if both exist.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            subnet = db.get_subnet_by_address(subnet)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")

            db.add_link_from_peer_to_subnet(peer, subnet)
            logging.info(f"Adding peer {peer.username} to subnet {subnet.subnet}")
            allow_link(peer.address, subnet.subnet)

        except Exception as e:
            state_manager.restore()
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
            subnet_obj = db.get_subnet_by_address(subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            peers = db.get_peers_in_subnet(subnet_obj)
            for peer in peers:
                db.remove_link_from_peer_from_subnet(peer, subnet_obj)
                remove_link(peer.address, subnet)
            db.delete_subnet(subnet_obj)
        except Exception as e:
            state_manager.restore()
            raise HTTPException(status_code=500, detail=f"Deleting subnet {subnet} failed: {e}")
        
    return {"message": "Subnet deleted"}


@router.delete("/disconnect",tags=["subnet"])
def disconnect_peer_from_subnet(username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
        Removes a peer from a specific subnet, if both exist. 
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail="Peer not found")
            subnet = db.get_subnet_by_address(subnet)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            
            db.remove_link_from_peer_from_subnet(peer, subnet)
            remove_link(peer.address, subnet.subnet)

        except Exception as e:
            state_manager.restore()
            raise HTTPException(status_code=500, detail=f"Disconnection of peer {username} from subnet {subnet} failed: {e}")
    return {"message": "Peer disconnected from subnet"}