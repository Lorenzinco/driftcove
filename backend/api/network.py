from fastapi import APIRouter, HTTPException, Depends
from backend.core.state_manager import state_manager
from backend.core.models import Peer, Subnet, Service, Topology
from backend.core.config import verify_token
from backend.core.lock import lock
from backend.core.database import db
from backend.core.logger import logging
from backend.core.lifespan import apply_config_from_database
from backend.core.iptables import allow_link, remove_link
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
    subnets: dict[str, Subnet] = {}
    peers: dict[str, Peer] = {}
    services: dict[str, Service] = {}
    network: dict[str, list[Peer]] = {}

    p2p_links : dict[str, list[Peer]] = {}
    service_links : dict[str, list[Peer]] = {}
    subnet_links : dict[str, list[Peer]] = {}
    subnet_to_subnet_links : dict[str, list[Subnet]] = {}
    subnet_to_service_links : dict[str, list[Service]] = {}


    try:
        with lock.read_lock():
            subnets_fetched = db.get_subnets()
            for subnet in subnets_fetched:
                peers_in_subnet = db.get_peers_in_subnet(subnet)
                subnets[subnet.subnet] = subnet
                network[subnet.subnet] = peers_in_subnet
            peers_fetched = db.get_all_peers()
            for peer in peers_fetched:
                peers[peer.address] = peer
            services_fetched = db.get_all_services()
            for service in services_fetched:
                services[service.name] = service

            p2p_links = db.get_links_between_peers()
            service_links = db.get_links_between_peers_and_services()
            subnet_links = db.get_links_between_subnets_and_peers()
            subnet_to_subnet_links = db.get_links_between_subnets()
            subnet_to_service_links = db.get_links_from_subnets_to_services()


            logging.info("Retrieved full topology from the database.")

            topology = Topology(subnets=subnets, peers=peers, services=services, network=network, service_links=service_links, p2p_links=p2p_links, subnet_links=subnet_links, subnet_to_subnet_links=subnet_to_subnet_links, subnet_to_service_links=subnet_to_service_links)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Topology get failed: {e}")
    return {"topology": topology}

@router.get("/iptables_rules",tags=["debug"])
def get_iptables_rules(_: Annotated[str, Depends(verify_token)]):
    """
    Get the current iptables rules.
    This endpoint will return all the iptables rules that are currently in the system.
    """
    import subprocess
    try:
        result = subprocess.run(["iptables", "-L", "FORWARD", "-n"], capture_output=True, text=True, check=True)
        rules = result.stdout
        logging.info("Retrieved iptables rules.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to get iptables rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get iptables rules")
    return {"iptables_rules": rules}

@router.post("/topology",tags=["network"])
def upload_topology(topology: Topology, _: Annotated[str, Depends(verify_token)]):
    """
    Upload a new network topology. If any of the peers inside the topology do not exist, an error will be returned, if any of the peer inside the topology have invalid addresses an error will be returned.
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            # Clear existing topology
            db.clear_database()

            # Create all subnets
            for subnet in topology.subnets.values():
                db.create_subnet(subnet)

            # Create all peers
            for peer in topology.peers.values():
                subnet = db.get_peers_subnet(peer)
                if subnet is None:
                    raise HTTPException(status_code=404, detail=f"Peer {peer.username} is in a subnet that does not exist")
                db.create_peer(peer)
                for service in peer.services.values():
                    db.create_service(peer, service)

            # Check that all services listed have a host
            for service in topology.services.values():
                host = db.get_service_host(service)
                if host is None:
                    raise HTTPException(status_code=404, detail=f"Service host for service {service.name} does not exist")

            # Create all p2p links
            for peer in topology.peers.values():
                if peer.address in topology.p2p_links:
                    logging.info(f"Peer {peer.username} has {len(topology.p2p_links[peer.address])} links")
                    for linked_peer in topology.p2p_links[peer.address]:
                        peer_in_db = db.get_peer_by_address(peer.address)
                        linked_peer_in_db = db.get_peer_by_address(linked_peer.address)
                        if peer_in_db is None:
                            raise HTTPException(status_code=404, detail=f"Peer with address {peer.address} does not exist")
                        if linked_peer_in_db is None:
                            raise HTTPException(status_code=404, detail=f"Linked peer with address {linked_peer.address} does not exist")
                        db.add_link_between_two_peers(peer_in_db, linked_peer_in_db)
                

            # Create all service links
            for service in topology.services.values():
                if service.name in topology.service_links:
                    for linked_peer in topology.service_links[service.name]:
                        peer_in_db = db.get_peer_by_address(linked_peer.address)
                        service_in_db = db.get_service_by_name(service.name)
                        if peer_in_db is None:
                            raise HTTPException(status_code=404, detail=f"Peer with address {linked_peer.address} does not exist")
                        if service_in_db is None:
                            raise HTTPException(status_code=404, detail=f"Service with name {service.name} does not exist")
                        db.add_peer_service_link(peer_in_db, service_in_db)

            # Create all subnet links
            for subnet in topology.subnets.values():
                if subnet.subnet in topology.subnet_links:
                    for linked_peer in topology.subnet_links[subnet.subnet]:
                        peer_in_db = db.get_peer_by_address(linked_peer.address)
                        subnet_in_db = db.get_subnet_by_address(subnet.subnet)
                        if peer_in_db is None:
                            raise HTTPException(status_code=404, detail=f"Peer with address {linked_peer.address} does not exist")
                        if subnet_in_db is None:
                            raise HTTPException(status_code=404, detail=f"Subnet with address {subnet.subnet} does not exist")
                        db.add_link_from_peer_to_subnet(peer_in_db, subnet_in_db)

            # Create all subnet-to-subnet links (undirected, de-duplicated)
            seen_pairs: set[tuple[str, str]] = set()
            for subnet_addr, linked_subnets in topology.subnet_to_subnet_links.items():
                for linked_subnet in linked_subnets:
                    a, b = sorted([subnet_addr, linked_subnet.subnet])
                    key = (a, b)
                    if key in seen_pairs:
                        continue
                    subnet_a_obj = db.get_subnet_by_address(a)
                    subnet_b_obj = db.get_subnet_by_address(b)
                    if subnet_a_obj is None:
                        raise HTTPException(status_code=404, detail=f"Subnet {a} does not exist")
                    if subnet_b_obj is None:
                        raise HTTPException(status_code=404, detail=f"Subnet {b} does not exist")
                    db.add_link_between_subnets(subnet_a_obj, subnet_b_obj)
                    seen_pairs.add(key)

            # Create all subnet-to-service links
            for subnet_addr, services in topology.subnet_to_service_links.items():
                subnet_in_db = db.get_subnet_by_address(subnet_addr)
                if subnet_in_db is None:
                    raise HTTPException(status_code=404, detail=f"Subnet with address {subnet_addr} does not exist")
                for service in services:
                    service_in_db = db.get_service_by_name(service.name)
                    if service_in_db is None:
                        raise HTTPException(status_code=404, detail=f"Service with name {service.name} does not exist")
                    db.add_link_from_subnet_to_service(subnet_in_db, service_in_db)

            # Finally, apply the new configuration
            apply_config_from_database()

    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Invalid topology data: {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Topology update failed: {e}")
    return {"message": "Topology uploaded successfully"}

@router.get("/status",tags=["network"])
def status():
    return {"status": "running"}

@router.post("/subnets/connect",tags=["network","subnets"])
def create_link_between_two_subnets(subnet_a: str, subnet_b: str, _: Annotated[str, Depends(verify_token)]):
    """
    Create a link between two subnets. This will allow all peers in subnet A to communicate with all peers in subnet B.
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            subnet_a_obj = db.get_subnet_by_address(subnet_a)
            subnet_b_obj = db.get_subnet_by_address(subnet_b)
            if subnet_a_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_a} does not exist")
            if subnet_b_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_b} does not exist")
            db.add_link_between_subnets(subnet_a_obj, subnet_b_obj)
            allow_link(subnet_a_obj.subnet, subnet_b_obj.subnet)
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Invalid subnet data: {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Link creation failed: {e}")
    return {"message": f"Link between {subnet_a} and {subnet_b} created successfully"}

@router.delete("/subnets/connect",tags=["network","subnets"])
def delete_link_between_two_subnets(subnet_a: str, subnet_b: str, _: Annotated[str, Depends(verify_token)]):
    """
    Delete a link between two subnets. This will prevent all peers in subnet A from communicating with all peers in subnet B.
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            subnet_a_obj = db.get_subnet_by_address(subnet_a)
            subnet_b_obj = db.get_subnet_by_address(subnet_b)
            if subnet_a_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_a} does not exist")
            if subnet_b_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_b} does not exist")
            db.remove_link_between_subnets(subnet_a_obj, subnet_b_obj)
            remove_link(subnet_a_obj.subnet, subnet_b_obj.subnet)
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Invalid subnet data: {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Link deletion failed: {e}")
    return {"message": f"Link between {subnet_a} and {subnet_b} deleted successfully"}