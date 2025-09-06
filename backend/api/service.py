from fastapi import APIRouter, HTTPException, Depends
from backend.core.wireguard import generate_keys, apply_to_wg_config, remove_from_wg_config, generate_wg_config
from backend.core.config import verify_token, settings
from backend.core.lock import lock
from backend.core.state_manager import state_manager
from backend.core.database import db
from backend.core.iptables import remove_link_with_port, allow_link_with_port, allow_answer_link, remove_answers_link
from backend.core.models import Service
from backend.core.logger import logging
from typing import Annotated

router = APIRouter(tags=["service"])


@router.post("/create",tags=["service"])
def create_service(service_name:str, department:str, username:str, port:int, _: Annotated[str, Depends(verify_token)], description: str = ""):
    """
    Creates a service, pairs it with an existing peer, the peer in question is identified by the address, the service will be created with the provided port. If the service already exists, nothing happens.
    If you wish for selected peers to be able to connect to the service, you need to use the connect endpoint.
    If a peer is connected to a peer with the same address, it will automatically be able to connect to the service.
    """
    keys = generate_keys()
    with lock.write_lock(), state_manager.saved_state():
        old_service = db.get_service_by_name(service_name)
        # database consistency
        try:
            # If the peer already exists, we remove it first
            if old_service:
                return {"message": "Service already exists"}
            peer = db.get_peer_by_username(username)
            if peer is None:
                raise HTTPException(status_code=404, detail=f"Peer {username} does not exist, to create a service, first create the peer and the assign the service to it.")
            subnet = db.get_peers_subnet(peer)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Peer is in a subnet that does not exist")
            service = Service(username=username,
                            public_key=peer.public_key,
                            preshared_key=peer.preshared_key,
                            address=peer.address,
                            name=service_name,
                            x=peer.x,
                            y=peer.y,
                            department=department,
                            port=port,
                            description=description)
            db.create_service(peer,service)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create service: {e}")
            
    return {"message": "Service created successfully"}

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
            peers_linked = db.get_service_peers(service)
            # Remove the service from the allowed IPs of the peers
            for peer in peers_linked:
                logging.info(f"Removing service {service.name} from peer {peer.username}")
                remove_link_with_port(peer.address, service.address)
            logging.info(f"Removing service {service.name} from the database")
            db.delete_service(service)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": "Service deleted"}

@router.post("/connect",tags=["service"])
def service_connect(username: str, service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Connect a peer to a service, provide the username of the peer and the name of the service, if both exists,
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
            
            host = db.get_service_host(service)
            if host is None:
                raise HTTPException(status_code=404, detail="Service host not found")
            
            
            db.add_peer_service_link(peer, service)
            logging.info(f"Connecting peer {peer.username} to service {service.name}")
            allow_link_with_port(peer.address, host.address, service.port)
            allow_answer_link(host.address, peer.address)


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
            
            host = db.get_service_host(service)
            if host is None:
                raise HTTPException(status_code=404, detail="Service host not found")
            
             # Check if the peer is linked to the service
            linked_peers = db.get_service_peers(service)
            if peer not in linked_peers:
                raise HTTPException(status_code=400, detail=f"Peer {username} is not connected to service {service_name}")
            
            logging.info(f"Disconnecting peer {peer.username} from service {service.name}")
            remove_link_with_port(peer.address, host.address, service.port)
            remove_answers_link(host.address, peer.address)
            db.remove_peer_service_link(peer, service)
    
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to disconnect {username} from {service_name}: {e}")
    return {"message": f"Peer {username} disconnected from service {service.name}"}
        
@router.post("/subnet/connect",tags=["service","subnets"])
def connect_subnet_to_service(subnet_address:str, service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Connect all peers in a subnet to a service. This will allow all peers in the subnet to connect to the service.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            subnet = db.get_subnet_by_address(subnet_address)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            
            service = db.get_service_by_name(service_name)
            if service is None:
                raise HTTPException(status_code=404, detail="Service not found")
            
            host = db.get_service_host(service)
            if host is None:
                raise HTTPException(status_code=404, detail="Service host not found")
            
            db.add_link_from_subnet_to_service(subnet, service)
            allow_link_with_port(subnet.subnet, host.address, service.port)
            allow_answer_link(host.address, subnet.subnet)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to connect subnet {subnet_address} to service {service_name}: {e}")
    return {"message": f"Subnet {subnet_address} connected to service {service.name}"}

@router.delete("/subnet/disconnect",tags=["service","subnets"])
def disconnect_subnet_from_service(subnet_address:str, service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Disconnect all peers in a subnet from a service. This will remove the ability for all peers in the subnet to connect to the service.
    """
    with lock.write_lock(), state_manager.saved_state():
        try:
            subnet = db.get_subnet_by_address(subnet_address)
            if subnet is None:
                raise HTTPException(status_code=404, detail="Subnet not found")
            
            service = db.get_service_by_name(service_name)
            if service is None:
                raise HTTPException(status_code=404, detail="Service not found")
            
            host = db.get_service_host(service)
            if host is None:
                raise HTTPException(status_code=404, detail="Service host not found")
            
            db.remove_link_from_subnet_to_service(subnet, service)
            remove_link_with_port(subnet.subnet, host.address, service.port)
            remove_answers_link(host.address, subnet.subnet)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to disconnect subnet {subnet_address} from service {service_name}: {e}")
    return {"message": f"Subnet {subnet_address} disconnected from service {service.name}"}