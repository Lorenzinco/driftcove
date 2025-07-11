from fastapi import FastAPI, HTTPException, Header, Depends, responses
from database import Database
from pydantic import BaseModel
import subprocess
import os

app = FastAPI()
db = Database("/etc/wireguard/user_configs.db")

WG_INTERFACE = "wg0"
API_TOKEN = os.environ.get("WG_API_TOKEN", "supersecuretoken")
ENDPOINT = os.getenv("WG_ENDPOINT", "localhost:51820")
WIREGUARD_SUBNET = os.getenv("WIREGUARD_SUBNET","10.128.0.0/9")

class Peer(BaseModel):
    username: str
    public_key: str

class Service(BaseModel):
    name: str
    department: str
    public_key: str
    address: str

class Subnet(BaseModel):
    subnet: str
    name: str
    description: str

def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth scheme")
    token = authorization.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

def generate_keys():
    private_key = None
    public_key = None
    try:
        private_key = subprocess.check_output("wg genkey", shell=True).decode().strip()
        public_key = subprocess.check_output(
            f"echo {private_key} | wg pubkey", shell=True
        ).decode().strip()
    except subprocess.CalledProcessError as e:
        print("Key generation failed: {e}")
    
    return {"private_key": private_key, "public_key": public_key}

@app.get("/")
def root():
    with open("docs.html", "r") as f:
        html_content = f.read()
    return responses.HTMLResponse(content=html_content)


@app.post("/create_subnet")
def create_subnet(subnet: Subnet, _=Depends(verify_token)):
    """
    Create a new subnet.
    This endpoint will add a new subnet to the database, to add peers into this subnet please see the other endpoint.
    """
    try:
        db.create_subnet(subnet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
 
    return {"message": "Subnet created"}

@app.delete("/delete_subnet")
def delete_subnet(subnet: Subnet, _=Depends(verify_token)):
    """
    Delete a subnet.
    This endpoint will delete a subnet from the database, it will also remove all peers associated with this subnet.
    """
    try:
        db.delete_subnet(subnet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
    return {"message": "Subnet deleted"}

@app.get("/get_subnets")
def get_subnets(_=Depends(verify_token)):
    """
    Get all subnets.
    This endpoint will return all the subnets that are currently in the database.
    """
    try:
        subnets = db.get_subnets()
        return {"subnets": subnets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
@app.get("/get_topology")
def get_topology(_=Depends(verify_token)):
    """
    Get the current network topology
    """
    topology = [{}]
    try:
        subnets = db.get_subnets()
        for subnet in subnets:
            peers = db.get_peers_by_subnet(subnet)
            topology.append({subnet:peers})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"topology":topology}



@app.post("/create_peer")
def create_peer(username:str , _=Depends(verify_token)):
    """
    Creates a peer and adds it to the wireguard configuration and returns a config, if it already exists, destroys the previous user and creates another one, then returns a config.
    The peer after the creation cannot really connect to anything, it needs to be added to a subnet first unless it already existed, in that case the endpoint returns a config which is already good for all the already existent routes the use is in.
    """
    keys = generate_keys()
    peer = Peer(username=username, public_key=keys["public_key"])
    old_peer = db.get_peer_by_username(username)
    try:
        # if the peer already exists, we remove it first
        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", old_peer.public_key, "remove"
        ], check=True)

        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", peer.public_key,
            "allowed-ips", ""
        ], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer: {e}")
    
    # database consistency
    try:
        # If the peer already exists, we remove it first
        db.remove_peer(old_peer)
        db.create_peer(peer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failed: {e}")
    
    configuration = f"""
[Interface]
PrivateKey = {keys["private_key"]}
Address = {db.get_peer_address(peer)}
DNS = ""

[Peer]
PublicKey = {peer.public_key}
Endpoint = {ENDPOINT}
AllowedIPs = {WIREGUARD_SUBNET}
PersistentKeepalive = 25
"""
    return {"configuration": configuration}



@app.delete("/remove_peer")
def remove_peer(peer: Peer, _=Depends(verify_token)):
    """
    Remove a peer from the WireGuard configuration.
    """
    try:
        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", peer.public_key, "remove"
        ], check=True)
        return {"message": "Peer removed"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove peer: {e}")
    
@app.post("/add_peer_to_subnet")
def add_peer_to_subnet(peer: Peer, subnet: Subnet, _=Depends(verify_token)):
    """ 
    Add a peer to a specific subnet.
    This endpoint will add a peer to a specific subnet, it will update the allowed IPs for the peer.
    """
    try:
        db.add_peer_to_subnet(peer, subnet)
        active_subnets = db.get_peers_subnets(peer)
        allowed_ips = ','.join(subnet.subnet for subnet in active_subnets)
        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", peer.public_key,
            "allowed-ips", allowed_ips
        ], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer to subnet: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
    return {"message": "Peer added to subnet"}

@app.delete("/remove_peer_from_subnet")
def remove_peer_from_subnet(peer: Peer, subnet: Subnet, _=Depends(verify_token)):
    """
        Remove a peer from a specific subnet.
    """
    try:
        db.remove_peer_from_subnet(peer, subnet)
        active_subnets = db.get_peers_subnets(peer)
        if not active_subnets:
            subprocess.run([
                "wg", "set", WG_INTERFACE,
                "peer", peer.public_key,
                "remove"
            ], check=True)
        else:
            allowed_ips = ','.join(subnet.subnet for subnet in active_subnets)
            subprocess.run([
                "wg", "set", WG_INTERFACE,
                "peer", peer.public_key,
                "allowed-ips", allowed_ips
            ], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove peer from subnet: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
@app.get("/get_user_subnets")
def get_user_subnets(peer: Peer, _=Depends(verify_token)):
    """
    Get all subnets that a peer is part of.
    This endpoint will return all the subnets that a peer is part of.
    """
    try:
        subnets = db.get_peers_subnets(peer)
        return {"subnets": subnets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    
    
    
@app.get("/sync")
def sync_config(_=Depends(verify_token)):
    """
    Sync the WireGuard configuration with the current state.
    """
    try:
        subprocess.run(["wg-quick", "syncconf", WG_INTERFACE, f"/etc/wireguard/{WG_INTERFACE}.conf"], check=True)
        return {"message": "Configuration synced"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync configuration: {e}")
    

@app.get("/status")
def status(_=Depends(verify_token)):
    try:
        result = subprocess.check_output(["wg", "show", WG_INTERFACE], text=True)
        return {"status": result}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")