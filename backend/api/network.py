from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated
import subprocess

from backend.core.state_manager import state_manager
from backend.core.models import Peer, Subnet, Service, Topology
from backend.core.config import verify_token
from backend.core.lock import lock
from backend.core.database import db
from backend.core.logger import logging
from backend.core.lifespan import apply_config_from_database
from backend.core.wireguard import getPeerInfo

from backend.core.nftables import (
    connect_subnets_bidirectional_public,
    disconnect_subnets_bidirectional_public,
    grant_admin_subnet_to_subnet, revoke_admin_subnet_to_subnet
)

router = APIRouter(tags=["network"])


@router.get("/subnets", tags=["network"])
def get_subnets(_: Annotated[str, Depends(verify_token)]):
    """
    Get a list of all subnets.
    """
    try:
        with lock.read_lock():
            subnets = db.get_all_subnets()
        logging.info(f"Retrieved {len(subnets)} subnets from the database.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    logging.debug(f"Subnets: {subnets}")
    return {"subnets": subnets}


@router.get("/topology", tags=["network"])
def get_topology(_: Annotated[str, Depends(verify_token)]) -> dict:
    """Fetch the full topology with granular error logging.

    Adds defensive try/except blocks around each DB aggregation to help locate
    intermittent 'tuple index out of range' errors (likely from a malformed row).
    """
    try:
        with lock.read_lock():
            # Base entities
            try:
                subnets_fetched = db.get_all_subnets()
                logging.debug(f"[topology] subnets fetched: {len(subnets_fetched)}")
            except Exception as e:
                logging.error("[topology] failed fetching subnets", exc_info=True)
                raise

            subnets: dict[str, Subnet] = {}
            peers: dict[str, Peer] = {}
            services: dict[str, Service] = {}
            network: dict[str, list[Peer]] = {}

            for subnet in subnets_fetched:
                try:
                    peers_in_subnet = db.get_peers_in_subnet(subnet)
                except Exception as e:
                    logging.error(f"[topology] failed peers_in_subnet for {subnet.subnet}: {e}", exc_info=True)
                    raise
                subnets[subnet.subnet] = subnet
                network[subnet.subnet] = peers_in_subnet

            try:
                peers_fetched = db.get_all_peers()
            except Exception:
                logging.error("[topology] failed fetching peers", exc_info=True)
                raise
            for peer in peers_fetched:
                try:
                    getPeerInfo(peer)
                except Exception as e:
                    logging.warning(f"[topology] getPeerInfo failed for {peer.username}: {e}")
                peers[peer.address] = peer

            try:
                services_fetched = db.get_all_services()
            except Exception:
                logging.error("[topology] failed fetching services", exc_info=True)
                raise
            for service in services_fetched:
                services[service.name] = service

            def safe(label, fn):
                try:
                    v = fn()
                    logging.debug(f"[topology] {label} size={len(v)}")
                    return v
                except Exception as inner:
                    logging.error(f"[topology] step {label} failed: {inner}", exc_info=True)
                    raise

            p2p_links = safe("p2p_links", db.get_links_from_peer_to_peer)
            service_links = safe("service_links", db.get_links_from_peers_to_service)
            subnet_links = safe("subnet_links", db.get_links_from_peer_to_subnet)
            subnet_to_subnet_links = safe("subnet_to_subnet_links", db.get_links_from_subnet_to_subnet)
            subnet_to_service_links = safe("subnet_to_service_links", db.get_links_from_subnet_to_service)
            admin_peer_to_peer_links = safe("admin_peer_to_peer_links", db.get_admin_links_from_peer_to_peer)
            admin_peer_to_subnet_links = safe("admin_peer_to_subnet_links", db.get_admin_links_from_peer_to_subnet)
            admin_subnet_to_subnet_links = safe("admin_subnet_to_subnet_links", db.get_admin_links_from_subnet_to_subnet)

            topology = Topology(
                subnets=subnets,
                peers=peers,
                services=services,
                network=network,
                service_links=service_links,
                p2p_links=p2p_links,
                subnet_links=subnet_links,
                subnet_to_subnet_links=subnet_to_subnet_links,
                subnet_to_service_links=subnet_to_service_links,
                admin_peer_to_peer_links=admin_peer_to_peer_links,
                admin_peer_to_subnet_links=admin_peer_to_subnet_links,
                admin_subnet_to_subnet_links=admin_subnet_to_subnet_links,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Topology get failed: {e}")
    return {"topology": topology}


@router.get("/nft_rules", tags=["debug"])
def get_nft_rules(_: Annotated[str, Depends(verify_token)]):
    """
    Get the current nftables rules for the Driftcove table.
    """
    try:
        out = subprocess.check_output(["nft", "list", "table", "inet", "dcv"], text=True)
        rules = out
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to get nft rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get nft rules")
    return {"nft_rules": rules}


@router.post("/topology", tags=["network"])
def upload_topology(topology: Topology, _: Annotated[str, Depends(verify_token)]):
    """
    Upload a new network topology and apply it (DB -> WG + nftables).
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            # Clear existing topology
            db.clear_database()

            # Create subnets
            for subnet in topology.subnets.values():
                db.create_subnet(subnet)

            # Create peers (and their services)
            for peer in topology.peers.values():
                subnets = db.get_peers_subnets(peer)
                if subnets is None or len(subnets) == 0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Peer {peer.username} is not in any subnet",
                    )
                db.create_peer(peer)
                for service in peer.services.values():
                    db.create_service(peer, service)

            # Check that all services listed have a host
            for service in topology.services.values():
                host = db.get_service_host(service)
                if host is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Service host for service {service.name} does not exist",
                    )

            # P2P links (DB only; nft applied later in apply_config_from_database)
            for peer in topology.peers.values():
                if peer.address in topology.p2p_links:
                    logging.info(
                        f"Peer {peer.username} has {len(topology.p2p_links[peer.address])} links"
                    )
                    for linked_peer in topology.p2p_links[peer.address]:
                        peer_in_db = db.get_peer_by_address(peer.address)
                        linked_peer_in_db = db.get_peer_by_address(linked_peer.address)
                        if peer_in_db is None:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Peer with address {peer.address} does not exist",
                            )
                        if linked_peer_in_db is None:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Linked peer with address {linked_peer.address} does not exist",
                            )
                        db.add_link_from_peer_to_peer(peer_in_db, linked_peer_in_db)

            # Peer->Service links (DB only; nft applied later)
            for service in topology.services.values():
                if service.name in topology.service_links:
                    for linked_peer in topology.service_links[service.name]:
                        peer_in_db = db.get_peer_by_address(linked_peer.address)
                        service_in_db = db.get_service_by_name(service.name)
                        if peer_in_db is None:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Peer with address {linked_peer.address} does not exist",
                            )
                        if service_in_db is None:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Service with name {service.name} does not exist",
                            )
                        db.add_link_from_peer_to_service(peer_in_db, service_in_db)

            # Subnet -> Peer links (DB only; nft applied later)
            for subnet in topology.subnets.values():
                if subnet.subnet in topology.subnet_links:
                    for linked_peer in topology.subnet_links[subnet.subnet]:
                        peer_in_db = db.get_peer_by_address(linked_peer.address)
                        subnet_in_db = db.get_subnet_by_address(subnet.subnet)
                        if peer_in_db is None:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Peer with address {linked_peer.address} does not exist",
                            )
                        if subnet_in_db is None:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Subnet with address {subnet.subnet} does not exist",
                            )
                        db.add_link_from_peer_to_subnet(peer_in_db, subnet_in_db)

            # Subnet <-> Subnet links (DB only; nft applied later)
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
                    db.add_link_from_subnet_to_subnet(subnet_a_obj, subnet_b_obj)
                    seen_pairs.add(key)

            # Subnet -> Service links (DB only; nft applied later)
            for subnet_addr, services in topology.subnet_to_service_links.items():
                subnet_in_db = db.get_subnet_by_address(subnet_addr)
                if subnet_in_db is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Subnet with address {subnet_addr} does not exist",
                    )
                for service in services:
                    service_in_db = db.get_service_by_name(service.name)
                    if service_in_db is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Service with name {service.name} does not exist",
                        )
                    db.add_link_from_subnet_to_service(subnet_in_db, service_in_db)

            # Admin Peer -> Peer links (DB only; nft applied later)
            for peer in topology.peers.values():
                for linked_peer in topology.admin_peer_to_peer_links.get(peer.address, []):
                    peer_in_db = db.get_peer_by_address(peer.address)
                    linked_peer_in_db = db.get_peer_by_address(linked_peer.address)
                    if peer_in_db is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Peer with address {peer.address} does not exist",
                        )
                    if linked_peer_in_db is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Linked peer with address {linked_peer.address} does not exist",
                        )
                    db.add_admin_link_from_peer_to_peer(peer_in_db, linked_peer_in_db)

                # Admin Peer -> Subnet links (DB only; nft applied later)
                for linked_subnet in topology.admin_peer_to_subnet_links.get(peer.address, []):
                    peer_in_db = db.get_peer_by_address(peer.address)
                    subnet_in_db = db.get_subnet_by_address(linked_subnet.subnet)
                    if peer_in_db is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Peer with address {peer.address} does not exist",
                        )
                    if subnet_in_db is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Subnet with address {linked_subnet.subnet} does not exist",
                        )
                    db.add_admin_link_from_peer_to_subnet(peer_in_db, subnet_in_db)

            # Admin Subnet -> Subnet links (DB only; nft applied later)
            # Keys: admin subnet address -> list of downstream subnets it can initiate to.
            for admin_subnet_addr, linked_subnets in topology.admin_subnet_to_subnet_links.items():
                admin_subnet_in_db = db.get_subnet_by_address(admin_subnet_addr)
                if admin_subnet_in_db is None:
                    raise HTTPException(status_code=404, detail=f"Admin subnet {admin_subnet_addr} does not exist")
                for linked_subnet in linked_subnets:
                    subnet_in_db = db.get_subnet_by_address(linked_subnet.subnet)
                    if subnet_in_db is None:
                        raise HTTPException(status_code=404, detail=f"Subnet {linked_subnet.subnet} does not exist")
                    db.add_admin_link_from_subnet_to_subnet(admin_subnet_in_db, subnet_in_db)

            # Apply to WG + nftables from DB snapshot
            apply_config_from_database()

    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Invalid topology data: {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Topology update failed: {e}")
    return {"message": "Topology uploaded successfully"}


@router.get("/status", tags=["network"])
def status():
    return {"status": "running"}


@router.post("/subnets/connect", tags=["network", "subnets"])
def create_link_between_two_subnets(
    subnet_a: str, subnet_b: str, _: Annotated[str, Depends(verify_token)]
):
    """
    Create a link between two subnets.

    Semantics (nftables model):
    - Members of subnet A can initiate to PUBLIC peers of subnet B.
    - Members of subnet B can initiate to PUBLIC peers of subnet A.
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            subnet_a_obj = db.get_subnet_by_address(subnet_a)
            subnet_b_obj = db.get_subnet_by_address(subnet_b)
            if subnet_a_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_a} does not exist")
            if subnet_b_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_b} does not exist")

            # DB first
            db.add_link_from_subnet_to_subnet(subnet_a_obj, subnet_b_obj)

            # nftables: bidirectional members -> public
            connect_subnets_bidirectional_public(subnet_a_obj.subnet, subnet_b_obj.subnet)

    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Invalid subnet data: {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Link creation failed: {e}")
    return {"message": f"Link between {subnet_a} and {subnet_b} created successfully"}


@router.delete("/subnets/connect", tags=["network", "subnets"])
def delete_link_between_two_subnets(
    subnet_a: str, subnet_b: str, _: Annotated[str, Depends(verify_token)]
):
    """
    Delete a link between two subnets (undo the members -> public allows both ways).
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            subnet_a_obj = db.get_subnet_by_address(subnet_a)
            subnet_b_obj = db.get_subnet_by_address(subnet_b)
            if subnet_a_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_a} does not exist")
            if subnet_b_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet_b} does not exist")

            # DB first
            db.remove_link_from_subnet_to_subnet(subnet_a_obj, subnet_b_obj)

            # nftables: remove both directions
            disconnect_subnets_bidirectional_public(subnet_a_obj.subnet, subnet_b_obj.subnet)

    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Invalid subnet data: {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Link deletion failed: {e}")
    return {"message": f"Link between {subnet_a} and {subnet_b} deleted successfully"}


@router.post("/update_coordinates", tags=["network", "peers", "subnets"])
def update_coordinates(topology: Topology, _: Annotated[str, Depends(verify_token)]):
    """
    Update coordinates/size/color for subnets and coordinates for peers.
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            for subnet in topology.subnets.values():
                subnet_in_db = db.get_subnet_by_address(subnet.subnet)
                if subnet_in_db is None:
                    raise HTTPException(
                        status_code=404, detail=f"Subnet {subnet.subnet} does not exist"
                    )
                subnet_in_db.x = subnet.x
                subnet_in_db.y = subnet.y
                subnet_in_db.width = subnet.width
                subnet_in_db.height = subnet.height
                subnet_in_db.rgba = subnet.rgba
                db.update_subnet_coordinates_size_and_color(subnet_in_db)

            for peer in topology.peers.values():
                peer_in_db = db.get_peer_by_address(peer.address)
                if peer_in_db is None:
                    raise HTTPException(
                        status_code=404, detail=f"Peer {peer.username} does not exist"
                    )
                peer_in_db.x = peer.x
                peer_in_db.y = peer.y
                db.update_peer_coordinates(peer_in_db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot update coordinates: {e}")
    
@router.post("/admin/connect_subnets", tags=["network", "subnets"])
def connect_admin_subnet_to_subnet(admin_subnet: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
    Connect a subnet to <admin_subnet> another subnet <subnet> with admin privileges, this means that every member of <admin_subnet> can initiate to every member of <subnet>, regardless of public flags.
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            subnet_obj = db.get_subnet_by_address(subnet)
            admin_subnet_obj = db.get_subnet_by_address(admin_subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet} does not exist")
            if admin_subnet_obj is None:
                raise HTTPException(status_code=404, detail=f"Admin Subnet {admin_subnet} does not exist")

            db.add_admin_link_from_subnet_to_subnet(admin_subnet_obj, subnet_obj)
            logging.info(f"Connecting admin subnet {admin_subnet_obj.subnet} to subnet {subnet_obj.subnet}")
            grant_admin_subnet_to_subnet(admin_subnet_obj.subnet, subnet_obj.subnet)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connecting admin subnet {admin_subnet} to subnet {subnet} failed: {e}")
    return {"message": f"Admin Subnet {admin_subnet} connected to subnet {subnet}"}

@router.delete("/admin/disconnect_subnets", tags=["network", "subnets"])
def disconnect_admin_subnet_to_subnet(admin_subnet: str, subnet: str, _: Annotated[str, Depends(verify_token)]):
    """
    Disconnect a subnet from <admin_subnet> another subnet <subnet> with admin privileges, this means that every member of <admin_subnet> will no longer be able to initiate to every member of <subnet>, unless public flags allow it.
    """
    try:
        with lock.write_lock(), state_manager.saved_state():
            subnet_obj = db.get_subnet_by_address(subnet)
            admin_subnet_obj = db.get_subnet_by_address(admin_subnet)
            if subnet_obj is None:
                raise HTTPException(status_code=404, detail=f"Subnet {subnet} does not exist")
            if admin_subnet_obj is None:
                raise HTTPException(status_code=404, detail=f"Admin Subnet {admin_subnet} does not exist")

            db.remove_admin_link_from_subnet_to_subnet(admin_subnet_obj, subnet_obj)
            logging.info(f"Disconnecting admin subnet {admin_subnet_obj.subnet} from subnet {subnet_obj.subnet}")
            revoke_admin_subnet_to_subnet(admin_subnet_obj.subnet, subnet_obj.subnet)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Disconnecting admin subnet {admin_subnet} from subnet {subnet} failed: {e}")
    return {"message": f"Admin Subnet {admin_subnet} disconnected from subnet {subnet}"}
