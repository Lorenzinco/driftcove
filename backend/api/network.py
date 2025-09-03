from fastapi import APIRouter, HTTPException, Depends
from backend.core.state_manager import state_manager
from backend.core.config import verify_token
from backend.core.lock import lock
from backend.core.database import db
from backend.core.logger import logging
from backend.core.lifespan import apply_config_from_database
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
    logging.debug(f"Subnets: {subnets}")
    return {"subnets":subnets}

    
@router.get("/topology",tags=["network"])
def get_topology(_: Annotated[str, Depends(verify_token)])->dict:
    """
    Get the current network topology
    """
    subnets: list = []
    topology:list[dict] = []
    links: list[dict] = []
    try:
        with lock.read_lock():
            subnets = db.get_subnets()
            for subnet in subnets:
                peers = db.get_peers_in_subnet(subnet)
                logging.info(peers)
                topology.append({subnet.subnet:peers})
                peers_linked = db.get_peers_linked_to_subnet(subnet)
                for peer in peers_linked:
                    links.append({f"{subnet.subnet} <-subnet-> {peer.username}": [subnet, peer]})
            services = db.get_all_services()
            for service in services:
                peers = db.get_service_peers(service)
                links.append({f"{service.name} <-service->": peers})
            logging.info(f"Retrieved {len(topology)} subnets and {len(links)} service links from the database.")
            logging.info("Retrieving peer to peer links...")
            p2p_links = db.get_links_between_peers()
            for link in p2p_links:
                links.append({f"{link[0].username} <-p2p-> {link[1].username}": [link[0], link[1]]})
        logging.info(f"Retrieved {len(p2p_links)} peer to peer links from the database.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    return {"subnets":subnets,"networks":topology, "links": links}

@router.post("/topology",tags=["network"])
def upload_topology(topology: dict, _: Annotated[str, Depends(verify_token)]):
    """
    Upload a new network topology. If any of the peers inside the topology do not exist, an error will be returned, if any of the peer inside the topology have invalid addresses an error will be returned.
    """
    # Expected input structure (flexible):
    # {
    #   "subnets": [ { subnet, name, ... }, ...],
    #   "networks": [ { subnetCidr: [ peerObjOrDict, ... ] }, ...] OR { subnetCidr: [...] },
    #   "links": [ { "A <-p2p-> B": [peerA, peerB]}, { "subnetCidr <-subnet-> username": [subnetObj, peerObj]}, { "serviceName <-service->": [peerObj,...]} ]
    # }
    try:
        with lock.write_lock(), state_manager.saved_state():
            db.clear_database()

            subnets = topology.get("subnets", [])
            networks_raw = topology.get("networks", [])
            links = topology.get("links", [])

            # helper to convert dicts to simple objects with attribute access
            def ensure_obj(x):
                if isinstance(x, dict):
                    return type("Tmp", (), x)
                return x

            # Normalize networks into a mapping subnet_cidr -> list(peers)
            network_map = {}
            if isinstance(networks_raw, dict):
                network_map = networks_raw
            else:
                for entry in networks_raw:
                    if isinstance(entry, dict):
                        for k, v in entry.items():
                            network_map[k] = v

            # Create subnets and peers
            for subnet_entry in subnets:
                subnet_obj = ensure_obj(subnet_entry)
                # db.create_subnet expects an object with attributes (avoid attribute error when dict provided)
                db.create_subnet(subnet_obj)
                subnet_key = getattr(subnet_obj, "subnet", None) or getattr(subnet_obj, "cidr", None)
                peers_list = network_map.get(subnet_key, [])
                for peer_entry in peers_list:
                    peer_obj = ensure_obj(peer_entry)
                    db.create_peer(peer_obj)

            # Process links (list of single-key dicts)
            for link_entry in links:
                if not isinstance(link_entry, dict):
                    continue
                for key, value in link_entry.items():
                    if "<-p2p->" in key:
                        # value expected [peerA, peerB]
                        if isinstance(value, (list, tuple)) and len(value) == 2:
                            peerA = ensure_obj(value[0])
                            peerB = ensure_obj(value[1])
                            db.add_link_between_two_peers(peerA, peerB)
                        else:
                            raise HTTPException(status_code=400, detail=f"Invalid p2p link format for {key}")
                    elif "<-service->" in key:
                        service_name = key.split(" <-service->")[0]
                        service = db.get_service_by_name(service_name)
                        if not service:
                            raise HTTPException(status_code=400, detail=f"Service {service_name} not found")
                        for peer_entry in value:
                            peer_obj = ensure_obj(peer_entry)
                            db.add_peer_service_link(peer_obj, service)
                    elif "<-subnet->" in key:
                        subnet_address = key.split(" <-subnet->")[0]
                        for item in value:
                            obj = ensure_obj(item)
                            # Determine if obj is a peer or subnet based on available attributes
                            if hasattr(obj, "username"):
                                db.add_link_from_peer_to_subnet(obj, subnet_address)
                            elif hasattr(obj, "subnet"):
                                # If a subnet object appears, skip (already represented)
                                continue
                    else:
                        logging.error(f"Unknown link type in key: {key}, {value}")
                        raise HTTPException(status_code=501, detail=f"Topology upload failed: Unknown link type in key: {key}")

            # Apply WireGuard configuration once after all changes
            apply_config_from_database()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Topology update failed: {e}")
            
    return {"message": "Topology uploaded successfully"}

@router.get("/status",tags=["network"])
def status():
    return {"status": "running"}