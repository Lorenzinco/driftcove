import subprocess
from fastapi import HTTPException
from app.core.config import settings
from app.core.logger import logging

def allow_link(src:str,dst:str):
    """Allow a link via iptables."""
    try:
        subprocess.run([
            "iptables", "-A", "FORWARD",
            "-i", settings.wg_interface,
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
            "-i", settings.wg_interface,
            "-s", src,
            "-d", dst,
            "-j", "ACCEPT"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to remove link {src} -> {dst}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove link")
    
def flush_iptables():
    """Flush all iptables rules."""
    try:
        subprocess.run(["iptables", "-F", "FORWARD"], check=True)
        logging.info("Flushed all iptables rules.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to flush iptables: {e}")
        raise HTTPException(status_code=500, detail="Failed to flush iptables")
    
def default_policy_drop():
    """Set the default policy for the FORWARD chain to DROP."""
    try:
        subprocess.run(["iptables", "-P", "FORWARD", "DROP"], check=True)
        logging.info("Set default policy for FORWARD chain to DROP.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to set default policy: {e}")
        raise HTTPException(status_code=500, detail="Failed to set default policy")