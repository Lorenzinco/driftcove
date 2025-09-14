import os, subprocess, tempfile
from fastapi import HTTPException
from backend.core.models import Peer, Service
from backend.core.config import settings
from backend.core.logger import logging


def flush_wireguard():
    """Remove all peers from the WireGuard interface."""
    try:
        output = subprocess.check_output(
            ["wg", "show", settings.wg_interface, "peers"],
            text=True
        ).strip()
        if not output:
            logging.info("No peers to remove.")
            return
        for peer in output.split():
            subprocess.run(
                ["wg", "set", settings.wg_interface, "peer", peer, "remove"],
                check=True
            )
        logging.info("All peers removed from %s", settings.wg_interface)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to flush peers: {e}")
        raise HTTPException(status_code=500, detail="Failed to flush WireGuard peers")

def apply_to_wg_config(peer: Peer):
    """Apply the peer configuration to the WireGuard interface."""
    with tempfile.NamedTemporaryFile(mode="w+",delete=False) as tmp_psk:
        tmp_psk.write(peer.preshared_key)
        tmp_psk.flush()
        tmp_psk_path = tmp_psk.name
        try:
            print(f"Applying WireGuard config for peer: {peer}")
            subprocess.run([
                "wg", "set", settings.wg_interface,
                "peer", peer.public_key,
                "preshared-key", tmp_psk_path,
                "allowed-ips", peer.address
            ], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to apply peer config: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to apply peer configuration for {peer}")
        finally:
            os.unlink(tmp_psk_path)

def remove_from_wg_config(peer: Peer):
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
    
def generate_wg_config(peer: Peer,private_key:str)->str:
    """Generate the WireGuard configuration for a peer."""
    config = f"""[Interface]
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

def getPeerInfo(peer: Peer):
    try:
        output = subprocess.check_output(
            ["wg", "show", settings.wg_interface, "transfer"]
        ).strip().decode()
        lines = output.splitlines()
        for line in lines:
            parts = line.split()
            if len(parts) == 3:
                pubkey, rx, tx = parts
                if pubkey == peer.public_key:
                    peer.tx = int(tx)
                    peer.rx = int(rx)

        output = subprocess.check_output(
            ["wg", "show", settings.wg_interface, "latest-handshakes"]
        ).strip().decode()
        lines = output.splitlines()
        for line in lines:
            parts = line.split()
            if len(parts) == 2:
                pubkey, handshake = parts
                if pubkey == peer.public_key:
                    peer.last_handshake = int(handshake)
                    if peer.last_handshake == 0:
                        peer.last_handshake = -1
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to get peer info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get peer info")
    
def apply_ip_route():
    try:
        logging.info(f"Applying IP route for {settings.wg_default_subnet} via {settings.wg_interface}...")
        subprocess.run(
            ["ip", "route", "replace", settings.wg_default_subnet, "dev", settings.wg_interface],
            check=True
        )
        logging.info(f"IP route applied for {settings.wg_default_subnet} via {settings.wg_interface}.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to apply IP route: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply IP route")