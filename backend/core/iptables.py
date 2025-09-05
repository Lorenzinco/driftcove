import subprocess
from fastapi import HTTPException
from backend.core.config import settings
from backend.core.logger import logging

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
    
def allow_link_with_port(src:str,dst:str,port:int):
    """Allow a link with a specific port via iptables."""
    try:
        subprocess.run([
            "iptables", "-A", "FORWARD",
            "-i", settings.wg_interface,
            "-s", src,
            "-d", dst,
            "-p", "tcp",
            "--dport", str(port),
            "-j", "ACCEPT"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to allow link {src} -> {dst} on port {port}: {e}")
        raise HTTPException(status_code=500, detail="Failed to allow link")
    
def allow_answer_link(src: str, dst: str):
    """Allow return traffic for an already established connection via iptables."""
    try:
        subprocess.run([
            "iptables", "-A", "FORWARD",
            "-o", settings.wg_interface,
            "-s", dst,
            "-d", src,
            "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED",
            "-j", "ACCEPT"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to allow answer link {dst} -> {src}: {e}")
        raise HTTPException(status_code=500, detail="Failed to allow answer link")

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
        raise HTTPException(status_code=500, detail=f"Failed to remove link {src} -> {dst}: {e}")

def remove_link_with_port(src: str, dst:str, port:int):
    """Remove an allow rule from iptables with a specific port, destroying the link between a peer and a service."""
    try:
        subprocess.run([
            "iptables", "-D", "FORWARD",
            "-i", settings.wg_interface,
            "-s", src,
            "-d", dst,
            "-p", "tcp",
            "--dport", str(port),
            "-j", "ACCEPT"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to remove link {src} -> {dst} on port {port}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove link {src} -> {dst} on port {port}: {e}")

def remove_answers_link(src: str, dst: str):
    """Remove the rule allowing return traffic for an already established connection via iptables."""
    try:
        subprocess.run([
            "iptables", "-D", "FORWARD",
            "-o", settings.wg_interface,
            "-s", dst,
            "-d", src,
            "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED",
            "-j", "ACCEPT"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to remove answer link {dst} -> {src}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove answer link {dst} -> {src}: {e}")

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