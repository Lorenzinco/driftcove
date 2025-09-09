from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.core.config import settings
from backend.core.database import db
from backend.core.logger import logging
from backend.core.nftables import flush_dcv, ensure_subnet, add_member, make_public, add_p2p_link, grant_service, connect_subnets_bidirectional_public, grant_subnet_service
from backend.core.wireguard import apply_to_wg_config, flush_wireguard
from backend.db.init_db import init_db
from backend.core.nftables import ensure_table_and_chain

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP CODE
    logging.info("Starting Driftcove WireGuard API...")
    try:
        init_db(settings.db_path)
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise
    logging.info("Applying WireGuard configuration and nftables rules from database...")
    try:
        apply_config_from_database()
    except Exception as e:
        logging.error(f"Failed to configure WireGuard on startup: {e}")
        raise

    yield  # control passes to the app here

def apply_config_from_database():
    try:
        logging.info("Resetting iptables rules for WireGuard and WireGuard config...")
        flush_dcv(wg_if=settings.wg_interface)
        flush_wireguard()

        # ensure base table/chain exist
        ensure_table_and_chain(wg_if=settings.wg_interface)

        peers = db.get_all_peers()
        services = db.get_all_services()
        peer2services = db.get_links_between_peers_and_services()
        peer2peers = db.get_links_between_peers()

        for peer in peers:
            apply_to_wg_config(peer)
            for link in peer2peers.get(peer.address, []):
                add_p2p_link(peer.address, link.address)

        for service in services:
            for peer in peer2services.get(service.name, []):
                host = db.get_service_host(service)
                if host is None:
                    raise Exception(f"Service host for service {service.name} not found")
                grant_service(peer.address, host.address, service.port)

        # 3) Subnets: create sets & rule, then members/public
        logging.info("Applying subnet membership/public flags…")
        subnets = db.get_subnets()
        subnet_to_subnet_links = db.get_links_between_subnets()
        subnet_to_service_links = db.get_links_from_subnets_to_services()

        for subnet in subnets:
            ensure_subnet(subnet.subnet)   # creates {members,public} sets and the members->public rule

            # (A) Members: if you have an explicit list in DB, use it:
            # members = db.get_peers_in_subnet(subnet)   # preferred
            # If not, fall back to "linked-to-subnet == public+member" (as legacy iptables code implied)
            linked_peers = db.get_peers_linked_to_subnet(subnet)  # legacy “link”
            for peer in linked_peers:
                add_member(subnet.subnet, peer.address)
                make_public(subnet.subnet, peer.address)
            
            peers_inside = db.get_peers_in_subnet(subnet) # peers whose address is inside the subnet
            for peer in peers_inside:
                if peer not in linked_peers:
                    add_member(subnet.subnet, peer.address)

            subnet_links = subnet_to_subnet_links.get(subnet.subnet, [])
            for linked_subnet in subnet_links:
                logging.info(f"Subnet {subnet.name} ({subnet.subnet}) is linked to {linked_subnet.name} ({linked_subnet.subnet})")
                connect_subnets_bidirectional_public(subnet.subnet, linked_subnet.subnet)

            services = subnet_to_service_links.get(subnet.subnet, [])
            for service in services:
                host = db.get_service_host(service)
                if host is None:
                    raise Exception(f"Service host for service {service.name} not found")
                logging.info(f"Subnet {subnet.name} ({subnet.subnet}) has service {service.name} on {host.address}:{service.port}")
                grant_subnet_service(subnet.subnet, host.address, service.port)
                

        
        logging.info("Loaded and applied WireGuard configuration from database")
    except Exception as e:
        logging.error(f"Failed to apply WireGuard configuration: {e}")
        raise e
