from fastapi import FastAPI, HTTPException, Header, Depends, responses
from database import Database
from pydantic import BaseModel
import subprocess
import os

app = FastAPI()
db = Database("/etc/wireguard/user_configs.db")

WG_INTERFACE = "wg0"
API_TOKEN = os.environ.get("WG_API_TOKEN", "supersecuretoken")

class Peer(BaseModel):
    username: str
    public_key: str
    allowed_ips: str

class Service(BaseModel):
    name: str
    department: str
    public_key: str
    allowed_ips: str

def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth scheme")
    token = authorization.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

@app.get("/")
def root():
    with open("docs.html", "r") as f:
        html_content = f.read()
    return responses.HTMLResponse(content=html_content)

@app.post("/generate")
def generate_keys(_=Depends(verify_token)):
    private_key = None
    public_key = None
    try:
        private_key = subprocess.check_output("wg genkey", shell=True).decode().strip()
        public_key = subprocess.check_output(
            f"echo {private_key} | wg pubkey", shell=True
        ).decode().strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Key generation failed: {e}")
    
    return {"private_key": private_key, "public_key": public_key}

@app.post("/update_peer")
def update_peer(peer: Peer, _=Depends(verify_token)):
    """
    Update or add a peer to the WireGuard configuration.
    This endpoint will add a new peer or update an existing one based on the public key.
    It sets the allowed IPs for the peer.
    If the peer already exists, it will update the allowed IPs.
    If the peer does not exist, it will add a new peer with the specified allowed IPs.
    """
    try:
        subprocess.run([
            "wg", "set", WG_INTERFACE,
            "peer", peer.public_key,
            "allowed-ips", peer.allowed_ips
        ], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to add peer: {e}")
    
    # database consistency
    try:
        db.update_peer(peer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failed: {e}")
    return {"message": "Peer added"}

@app.post("/remove_peer")
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