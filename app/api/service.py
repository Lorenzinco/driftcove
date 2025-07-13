from fastapi import APIRouter, HTTPException, Depends
from app.core.wireguard import generate_keys, apply_to_wg_config, remove_from_wg_config, generate_wg_config
from app.core.config import verify_token, settings
from app.core.database import db
from app.core.iptables import allow_link, remove_link
from app.core.models import Service
from typing import Annotated
import subprocess,logging

router = APIRouter(tags=["service"])


@router.post("/create",tags=["service"])
def create_service(service_name:str, department:str, subnet:str, _: Annotated[str, Depends(verify_token)]):
    """
    Creates a peer and adds it to the wireguard configuration and returns a config, the assigned ip address is one inside the default subnet, if it already exists, destroys the previous user and creates another one, then returns a config.
    The peer after the creation cannot really connect to anything, it needs to be "added" to a subnet, which really just enables routes to that subnet for that peer.
    """
    keys = generate_keys()
    old_service = db.get_service_by_name(service_name)
    logging.warning(f"Creating service {service_name} with public key {keys['public_key']}, preshared key {keys['preshared_key']}")
    logging.warning(f"Old service: {old_service}, if none, it will be created anew")

    
    # database consistency
    try:
        # If the peer already exists, we remove it first
        logging.warning(f"Removing old peer {old_service} if it exists")
        if old_service:
            db.remove_peer(old_service)

        logging.warning(f"Getting info for {subnet} from the database")
        subnet = db.get_subnet_by_address(subnet)
        logging.warning(f"Subnet found: {subnet}")
        if subnet is None:
            raise HTTPException(status_code=404, detail="Subnet not found")
        logging.warning(f"Getting an available IP address for service {service_name} in subnet {subnet.subnet}")
        address = db.get_avaliable_ip(subnet)
        if address is None:
            raise HTTPException(status_code=500, detail="No available IPs in subnet")
        logging.warning(f"Assigned IP {address} to peer {service_name}")

        username = db.get_avaliable_username_for_service()
        service = Service(username=username, public_key=keys["public_key"], preshared_key=keys["preshared_key"], address=address, name=service_name, department=department)
        logging.warning(f"Adding service {service_name} to the database")
        db.create_service(service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failed: {e}")
    try:
        # if the service already exists, we remove it first
        if old_service:
            remove_from_wg_config(old_service)

        apply_to_wg_config(service)

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer: {e}")
        
    configuration = generate_wg_config(service, keys["private_key"])
    return {"configuration": configuration}

@router.delete("/delete",tags=["service"])
def delete_service(service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Delete a service, all the connections to the service will be removed, and the service will be removed from the database.
    """
    try:
        service= db.get_service_by_name(service_name)
        if service is None:
            raise HTTPException(status_code=404, detail="Service not found")
        logging .info(f"Deleting service {service.name} with address {service.address} from wireguard configuration")
        remove_from_wg_config(service)
        peers_linked = db.get_service_peers(service)
        # Remove the service from the allowed IPs of the peers
        for peer in peers_linked:
            logging.info(f"Removing service {service.name} from peer {peer.username}")
            remove_link(peer.address, service.address)
            db.remove_peer_service_link(peer, service)
        logging.info(f"Removing service {service.name} from the database")
        db.delete_service(service)
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete service: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": "Service deleted"}

@router.post("/connect",tags=["service"])
def service_connect(username: str, service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Connect a peer to a service.
    This endpoint will add the peer to the service and return the configuration for the peer.
    """
    try:
        peer = db.get_peer_by_username(username)
        if peer is None:
            raise HTTPException(status_code=404, detail="Peer not found")
        
        service = db.get_service_by_name(service_name)
        if service is None:
            raise HTTPException(status_code=404, detail="Service not found")
        
        db.add_peer_service_link(peer, service)
        logging.info(f"Connecting peer {peer.username} to service {service.name}")
        allow_link(peer.address, service.address)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": f"Peer {username} connected to service {service.name}"}

@router.delete("/disconnect",tags=["service"])
def service_disconnect(username: str, service_name: str, _: Annotated[str, Depends(verify_token)]):
    """Disconnect a peer from a service.
    """
    try:
        peer = db.get_peer_by_username(username)
        if peer is None:
            raise HTTPException(status_code=404, detail="Peer not found")
        
        service = db.get_service_by_name(service_name)
        if service is None:
            raise HTTPException(status_code=404, detail="Service not found")
        
        logging.info(f"Disconnecting peer {peer.username} from service {service.name}")
        remove_link(peer.address, service.address)
        db.remove_peer_service_link(peer, service)
    
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect peer from service: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": f"Peer {username} disconnected from service {service.name}"}
    
