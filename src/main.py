from fastapi import FastAPI, HTTPException, Header, Depends, responses
from fastapi.staticfiles import StaticFiles
from .db import Database
from .init_db import init_db
from .models import Peer,Service,Subnet
from typing import Annotated
from contextlib import asynccontextmanager
import tempfile, subprocess, logging, os

description = """
# Driftcove VPN server🔑
Driftcove is a wireguard VPN server that allows you to manage services and peers in a simple way.

## Features
- Create and manage subnets
- Create and manage peers
- Add peers to subnets
- Remove peers from subnets
- Get the current network topology
- Sync the WireGuard configuration
- Get the status of the WireGuard interface

## Authentication
This API uses a Bearer token for authentication. You can set the token using the `WG_API_TOKEN` environment variable. The default token is `supersecuretoken`.
You can also set the endpoint using the `WG_ENDPOINT` environment variable, which defaults to `localhost:51820`.

"""

tags_metadata = [
    {
        "name": "subnet",
        "description": "Operations related to subnets, create, manage and delete subnets",
    },
    {
        "name": "peer",
        "description": "Operations related to peers, create, manage and delete peers, also get the subnets a peer is part of as well as the configuration for the peer",
    },
    {
        "name": "network",
        "description": "Network operations, such as getting all subnets and the current network topology",
    },
    {
        "name": "service",
        "description": "Operations related to services, create, manage and delete services, also get the peers that are part of a service",
    }
]



DB_PATH = "/home/db/user_configs.db"
WG_INTERFACE = "wg0"
API_TOKEN = os.environ.get("WIREGUARD_API_TOKEN", "supersecuretoken")
ENDPOINT = os.getenv("WIREGUARD_ENDPOINT", "127.0.0.1:1194")
PUBLIC_KEY = os.getenv("WIREGUARD_PUBLIC_KEY", "")
WIREGUARD_SUBNET = os.getenv("WIREGUARD_SUBNET","10.128.0.0/9")
MTU = os.getenv("WIREGUARD_MTU", "1420")

init_db(DB_PATH)
db = Database(DB_PATH)

def apply_to_wg_config(peer: Peer|Service):
    """Apply the peer configuration to the WireGuard interface."""
    with tempfile.NamedTemporaryFile(mode="w+",delete=False) as tmp_psk:
        tmp_psk.write(peer.preshared_key)
        tmp_psk.flush()
        tmp_psk_path = tmp_psk.name
    try:
        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", peer.public_key,
            "preshared-key", tmp_psk_path,
            "allowed-ips", peer.address
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to apply peer config: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply peer configuration")
    finally:
        os.unlink(tmp_psk_path)

def allow_link(src:str,dst:str):
    """Allow a link via iptables."""
    try:
        subprocess.run([
            "iptables", "-A", "FORWARD",
            "-i", WG_INTERFACE,
            "-s", src,
            "-d", dst,
            "-j", "ACCEPT"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to allow link {src} -> {dst}: {e}")
        raise HTTPException(status_code=500, detail="Failed to allow link")

def remove_link(src: str, dst: str):
    """Remove an allow rule from iptables, effectively denying the link."""
    try:
        subprocess.run([
            "iptables", "-D", "FORWARD",
            "-i", WG_INTERFACE,
            "-s", src,
            "-d", dst,
            "-j", "ACCEPT"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to remove link {src} -> {dst}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove link")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP CODE
    try:
        logging.info("Resetting iptables rules for WireGuard")
        subprocess.run(["iptables", "-F", "FORWARD"], check=True)

        subnets = db.get_subnets()
        for subnet in subnets:
            peers = db.get_peers_in_subnet(subnet)
            for peer in peers:
                apply_to_wg_config(peer)
                logging.info(f"Adding route for peer {peer.username} in subnet {subnet.subnet}")
                subprocess.run([
                    "iptables", "-A", "FORWARD",
                    "-i", WG_INTERFACE,
                    "-s", peer.address,
                    "-d", subnet.subnet,
                    "-j", "ACCEPT"
                ], check=True)

        logging.info("Every non-allowed traffic will be dropped")
        subprocess.run([
            "iptables", "-P", "FORWARD", "DROP"
        ], check=True)

        logging.info(f"Loaded {len(subnets)} subnets and {sum(len(db.get_peers_in_subnet(subnet)) for subnet in subnets)} peers from the database.")

        logging.info("Loading and ")
    except Exception as e:
        logging.error(f"Failed to configure WireGuard on startup: {e}")
        raise

    yield  # control passes to the app here


app = FastAPI(
    title="Driftcove WireGuard API",
    summary="API for managing WireGuard peers and subnets",
    version="0.1.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)


def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth scheme")
    token = authorization.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

def generate_keys():
    try:
        private_key = subprocess.check_output(["wg", "genkey"]).decode().strip()
        public_key = subprocess.check_output(["wg", "pubkey"], input=private_key.encode()).decode().strip()
        preshared_key = subprocess.check_output(["wg", "genpsk"]).decode().strip()

        return {"private_key": private_key, "public_key": public_key, "preshared_key": preshared_key}

    except subprocess.CalledProcessError as e:
        print(f"Key generation failed: {e}")
        return None


@app.post("/subnet/create",tags=["subnet"])
def create_subnet(subnet: Subnet, _: Annotated[str, Depends(verify_token)]):
    """
    Create a new subnet.
    This endpoint will add a new subnet to the database, to add peers into this subnet please see the other endpoint.
    """
    try:
        db.create_subnet(subnet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
 
    return {"message": "Subnet created"}

@app.post("/subnet/add_peer",tags=["subnet"])
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

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer to subnet: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
    return {"message": "Peer added to subnet"}

@app.delete("/subnet/delete",tags=["subnet"])
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


@app.delete("/subnet/remove_peer",tags=["subnet"])
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

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove peer from subnet: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": "Peer removed from subnet"}
    
   
@app.get("/network/get_all",tags=["network"])
def get_subnets(_: Annotated[str, Depends(verify_token)]):
    """
    Get all subnets.
    This endpoint will return all the subnets that are currently in the database.
    """
    try:
        subnets = db.get_subnets()
        return {"subnets": subnets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")

    
@app.get("/network/get_topology",tags=["network"])
def get_topology(_: Annotated[str, Depends(verify_token)])->dict:
    """
    Get the current network topology
    """
    topology:list[dict] = []
    links: list[dict] = []
    try:
        subnets = db.get_subnets()
        for subnet in subnets:
            peers = db.get_peers_in_subnet(subnet)
            topology.append({subnet.subnet:peers})
        services = db.get_all_services()
        for service in services:
            peers = db.get_service_peers(service)
            links.append({service.name: peers})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"networks":topology, "links": links}



@app.post("/peer/create",tags=["peer"])
def create_peer(username:str , subnet:str, _: Annotated[str, Depends(verify_token)]):
    """
    Creates a peer and adds it to the wireguard configuration and returns a config, the assigned ip address is one inside the default subnet, if it already exists, destroys the previous user and creates another one, then returns a config.
    The peer after the creation cannot really connect to anything, it needs to be "added" to a subnet, which really just enables routes to that subnet for that peer.
    """
    keys = generate_keys()
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
            subprocess.run([
                "wg", "set", WG_INTERFACE,
                "peer", old_peer.public_key, "remove"
            ], check=True)

        apply_to_wg_config(peer)

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer: {e}")
        
    configuration = f"""
[Interface]
PrivateKey = {keys["private_key"]}
Address = {peer.address}
MTU = {MTU}

[Peer]
PublicKey = {PUBLIC_KEY}
PresharedKey = {peer.preshared_key}
Endpoint = {ENDPOINT}
AllowedIPs = {WIREGUARD_SUBNET}
PersistentKeepalive = 15
"""
    return {"configuration": configuration}

@app.get("/peer/get_info",tags=["peer"])
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



@app.delete("/peer/remove",tags=["peer"])
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
        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", peer.public_key, "remove"
        ], check=True)
        return {"message": "Peer removed"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove peer: {e}")
    

 
@app.get("/peer/get_subnets",tags=["peer"])
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
    
@app.post("/peer/service_connect",tags=["peer"])
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

@app.delete("/peer/service_disconnect",tags=["peer"])
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
    
    
@app.get("/status",tags=["Debug"])
def status(_: Annotated[str, Depends(verify_token)]):
    try:
        result = subprocess.check_output(["wg", "show", WG_INTERFACE], text=True)
        return {"status": result}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")
    
@app.post("/service/create",tags=["service"])
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
            subprocess.run([
                "wg", "set", WG_INTERFACE,
                "peer", service.public_key, "remove"
            ], check=True)

        apply_to_wg_config(service)

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer: {e}")
        
    configuration = f"""
[Interface]
PrivateKey = {keys["private_key"]}
Address = {service.address}
MTU = {MTU}

[Peer]
PublicKey = {PUBLIC_KEY}
PresharedKey = {service.preshared_key}
Endpoint = {ENDPOINT}
AllowedIPs = {WIREGUARD_SUBNET}
PersistentKeepalive = 15
"""
    return {"configuration": configuration}

@app.delete("/service/delete",tags=["service"])
def delete_service(service_name: str, _: Annotated[str, Depends(verify_token)]):
    """
    Delete a service, all the connections to the service will be removed, and the service will be removed from the database.
    """
    try:
        service= db.get_service_by_name(service_name)
        if service is None:
            raise HTTPException(status_code=404, detail="Service not found")
        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", service.public_key, "remove"
        ], check=True)
        peers_linked = db.get_service_peers(service)
        # Remove the service from the allowed IPs of the peers
        for peer in peers_linked:
            logging.info(f"Removing service {service.name} from peer {peer.username}")
            remove_link(peer.address, service.address)
            db.remove_peer_service_link(peer, service)
        db.delete_service(service)
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete service: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"message": "Service deleted"}