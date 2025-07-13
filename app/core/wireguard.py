import os, subprocess, tempfile, logging
from fastapi import HTTPException
from app.core.models import Peer, Service
from app.core.config import settings

def apply_to_wg_config(peer: Peer|Service):
    """Apply the peer configuration to the WireGuard interface."""
    with tempfile.NamedTemporaryFile(mode="w+",delete=False) as tmp_psk:
        tmp_psk.write(peer.preshared_key)
        tmp_psk.flush()
        tmp_psk_path = tmp_psk.name
    try:
        subprocess.run([
            "wg", "set", settings.wg_interface,
            "peer", peer.public_key,
            "preshared-key", tmp_psk_path,
            "allowed-ips", peer.address
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to apply peer config: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply peer configuration")
    finally:
        os.unlink(tmp_psk_path)

def remove_from_wg_config(peer: Peer|Service):
    try:
        subprocess.run([
                    "wg", "set", settings.wg_interface,
                    "peer", peer.public_key, "remove"
                ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to remove peer config: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove peer configuration")

def generate_keys():
    try:
        private_key = subprocess.check_output(["wg", "genkey"]).decode().strip()
        public_key = subprocess.check_output(["wg", "pubkey"], input=private_key.encode()).decode().strip()
        preshared_key = subprocess.check_output(["wg", "genpsk"]).decode().strip()

        return {"private_key": private_key, "public_key": public_key, "preshared_key": preshared_key}

    except subprocess.CalledProcessError as e:
        print(f"Key generation failed: {e}")
        return None
    
def generate_wg_config(peer: Peer|Service,private_key:str)->str:
    """Generate the WireGuard configuration for a peer."""
    config = f"""
[Interface]
PrivateKey = {private_key}
Address = {peer.address}
MTU = {settings.mtu}

[Peer]
PublicKey = {settings.public_key}
PresharedKey = {peer.preshared_key}
Endpoint = {settings.endpoint}
AllowedIPs = {settings.wg_default_subnet}
PersistentKeepalive = 15
"""
    return config