from fastapi import APIRouter, HTTPException, Depends
from app.core.config import verify_token,settings
from app.core.database import db
from typing import Annotated
import logging, subprocess

router = APIRouter(tags=["network"])


@router.get("/get_all",tags=["network"])
def get_subnets(_: Annotated[str, Depends(verify_token)]):
    """
    Get all subnets.
    This endpoint will return all the subnets that are currently in the database.
    """
    try:
        subnets = db.get_subnets()
        logging.info(f"Retrieved {len(subnets)} subnets from the database.")
        return {"subnets": subnets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")

    
@router.get("/get_topology",tags=["network"])
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
        logging.info(f"Retrieved {len(topology)} subnets and {len(links)} service links from the database.")
        logging.info("Retrieving peer to peer links...")
        p2p_links = db.get_links_between_peers()
        for link in p2p_links:
            links.append({f"{link[0].username} <-> {link[1].username}": [link[0], link[1]]})
        logging.info(f"Retrieved {len(p2p_links)} peer to peer links from the database.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"networks":topology, "links": links}

@router.get("/status",tags=["network"])
def status(_: Annotated[str, Depends(verify_token)]):
    try:
        result = subprocess.check_output(["wg", "show", settings.wg_interface], text=True)
        return {"status": result}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")