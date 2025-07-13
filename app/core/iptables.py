import logging, subprocess
from fastapi import HTTPException
from app.core.config import settings

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