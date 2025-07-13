from fastapi import APIRouter, HTTPException, Depends
from app.core.config import verify_token
from app.core.database import db
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
    try:
        db.create_subnet(subnet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subnet create failed: {e}")
 
    return {"message": "Subnet created"}

@router.post("/add_peer",tags=["subnet"])
def add_peer_to_subnet(username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """ Add a peer named to a specific subnet.
    """
    try:
        peer = db.get_peer_by_username(username)
        if peer is None:
            raise HTTPException(status_code=404, detail="Peer not found")
        subnet = db.get_subnet_by_address(subnet)
        if subnet is None:
            raise HTTPException(status_code=404, detail="Subnet not found")

        db.add_peer_to_subnet(peer, subnet)
        logging.info(f"Adding peer {peer.username} to subnet {subnet.subnet}")
        allow_link(peer.address, subnet.subnet)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subnet add peer failed: {e}")
    
    return {"message": "Peer added to subnet"}

@router.delete("/delete",tags=["subnet"])
def delete_subnet(subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
    Delete a subnet.
    This endpoint will delete a subnet from the database, all the peers who had this subnet on their allowed ips will get it removed.
    """
    try:
        subnet = db.get_subnet_by_address(subnet)
        peers = db.get_peers_in_subnet(subnet)
        for peer in peers:
            db.remove_peer_from_subnet(peer, subnet)
            logging.info(f"Removing subnet {subnet.subnet} from peer {peer.username}")
            remove_link(peer.address, subnet.subnet)
        db.delete_subnet(subnet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
    return {"message": "Subnet deleted"}


@router.delete("/remove_peer",tags=["subnet"])
def remove_peer_from_subnet(username: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
        Remove a peer from a specific subnet.
    """
    try:
        peer = db.get_peer_by_username(username)
        if peer is None:
            raise HTTPException(status_code=404, detail="Peer not found")
        subnet = db.get_subnet_by_address(subnet)
        if subnet is None:
            raise HTTPException(status_code=404, detail="Subnet not found")
        
        db.remove_peer_from_subnet(peer, subnet)
        logging.info(f"Removing subnet {subnet.subnet} from peer {peer.username}")
        remove_link(peer.address, subnet.subnet)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": "Peer removed from subnet"}