from fastapi import APIRouter, HTTPException, Depends
from app.core.wireguard import generate_keys, apply_to_wg_config, remove_from_wg_config, generate_wg_config
from app.core.config import verify_token, settings
from app.core.lock import lock
from app.core.state_manager import state_manager
from app.core.database import db
from app.core.iptables import allow_link, remove_link
from app.core.models import Service
from app.core.logger import logging
from typing import Annotated

router = APIRouter(tags=["service"])


@router.post("/create",tags=["service"])
def create_service(service_name:str, department:str, subnet:str, _: Annotated[str, Depends(verify_token)]):
    """
    Creates a service, adds it to the wireguard configuration of the server and returns a config, the assigned ip address is an avaliable one inside the provided subnet. If the service already exists, destroys the previous service and creates another one, then returns a config.
    The service after the creation cannot really connect to anything, it needs to be "added" to a subnet, which really just enables routes to that subnet for that service.
    If you wish for selected peers to be able to connect to the service, you need to use the connect endpoint.
    """
    keys = generate_keys()
    with lock.write_lock(), state_manager.saved_state():
        old_service = db.get_service_by_name(service_name)
        # database consistency
        try:
            # If the peer already exists, we remove it first
            if old_service:
                db.remove_peer(old_service)
            subnet = db.get_subnet_by_address(subnet)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            address = db.get_avaliable_ip(subnet)
            if address is None:
                raise HTTPException(status_code=500, detail="No available IPs in subnet")
            username = db.get_avaliable_username_for_service()
            service = Service(username=username,
                            public_key=keys["public_key"],
                            preshared_key=keys["preshared_key"],
                            address=address,
                            name=service_name, 
                            department=department)
            db.create_service(service)
            if old_service:
                remove_from_wg_config(old_service)
            apply_to_wg_config(service)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create service: {e}")
            
    configuration = generate_wg_config(service, keys["private_key"])
    return {"configuration": configuration}

@router.delete("/delete",tags=["service"])
def delete_service(service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Delete a service, all the connections to the service will be removed, and the service will be removed from the database.
    """
    with lock.write_lock(), state_manager.saved_state():
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

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": "Service deleted"}

@router.post("/connect",tags=["service"])
def service_connect(username: str, service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Connect a peer to a service, provice the username of the peer and the name of the service, if both exists,
    the peer will be added to the users of the service and the link will be allowed in iptables.
    """
    with lock.write_lock(), state_manager.saved_state():
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
            raise HTTPException(status_code=500, detail=f"Connecting peer {username} to {service_name} failed: {e}")
    return {"message": f"Peer {username} connected to service {service.name}"}

@router.delete("/disconnect",tags=["service"])
def service_disconnect(username: str, service_name: str, _: Annotated[str, Depends(verify_token)]):
    """Disconnect a peer from a service.
    Provide the username of the peer and the name of the service, if both exist, and are linked,
    the peer will be removed from the users of the service and the link will be removed in iptables.
    """
    with lock.write_lock(), state_manager.saved_state():
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
    
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to disconnect {username} from {service_name}: {e}")
    return {"message": f"Peer {username} disconnected from service {service.name}"}
        
