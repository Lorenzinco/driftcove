from fastapi import APIRouter, HTTPException, Depends
from app.core.config import verify_token
from app.core.lock import lock
from app.core.database import db
from app.core.logger import logging
from typing import Annotated

router = APIRouter(tags=["network"])


@router.get("/subnets",tags=["network"])
def get_subnets(_: Annotated[str, Depends(verify_token)]):
    """
    Get all subnets.
    This endpoint will return all the subnets that are currently in the database.
    """
    try:
        with lock.read_lock():
            subnets = db.get_subnets()
        logging.info(f"Retrieved {len(subnets)} subnets from the database.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {subnets}

    
@router.get("/topology",tags=["network"])
def get_topology(_: Annotated[str, Depends(verify_token)])->dict:
    """
    Get the current network topology
    """
    topology:list[dict] = []
    links: list[dict] = []
    try:
        with lock.read_lock():
            subnets = db.get_subnets()
            for subnet in subnets:
                peers = db.get_peers_in_subnet(subnet)
                services = db.get_services_in_subnet(subnet)
                topology.append({subnet.subnet:peers})
                peers_linked = db.get_peers_linked_to_subnet(subnet)
                for peer in peers_linked:
                    links.append({subnet.subnet:peer})
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
def status():
    return {"status": "running"}