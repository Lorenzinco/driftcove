from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.core.config import settings
from backend.core.database import db
from backend.core.iptables import allow_link, flush_iptables, default_policy_drop, allow_link_with_port, allow_answer_link
from backend.core.logger import logging
from backend.core.wireguard import apply_to_wg_config, flush_wireguard
from backend.db.init_db import init_db

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
    try:
        apply_config_from_database()
    except Exception as e:
        logging.error(f"Failed to configure WireGuard on startup: {e}")
        raise

    yield  # control passes to the app here

def apply_config_from_database():
    try:
        logging.info("Resetting iptables rules for WireGuard and WireGuard config...")
        flush_iptables()
        flush_wireguard()

        peers = db.get_all_peers()
        for peer in peers:
            apply_to_wg_config(peer)

        logging.info("Loading from db peer to peer links")
        links = db.get_links_between_peers()

        for peer in peers:
            peers_linked_to_peer = links[peer.address] if peer.address in links else []
            if len(peers_linked_to_peer) > 0:
                logging.info(f"Peer {peer.username} ({peer.address}) is linked to {[p.username for p in peers_linked_to_peer]}")
                for linked_peer in peers_linked_to_peer:
                    allow_link(peer.address, linked_peer.address)
                    allow_link(linked_peer.address, peer.address)

        logging.info("Loading from db peer to service links")
        services = db.get_all_services()
        service_links = db.get_links_between_peers_and_services()
        for service in services:
            peers_linked_to_service = service_links[service.name] if service.name in service_links else []
            if len(peers_linked_to_service) > 0:
                logging.info(f"Service {service.name} is linked to {[p.username for p in peers_linked_to_service]}")
                for peer in peers_linked_to_service:
                    host = db.get_service_host(service)
                    if host is None:
                        raise Exception(f"Service host for service {service.name} not found")
                    allow_link_with_port(peer.address, host.address, service.port)
                    allow_answer_link(host.address, peer.address)

        logging.info("Loading from db subnet to peer links")
        subnets = db.get_subnets()
        subnet_links = db.get_links_between_subnets_and_peers()
        for subnet in subnets:
            peers_linked = subnet_links[subnet.subnet] if subnet.subnet in subnet_links else []
            if len(peers_linked) > 0:
                logging.info(f"Subnet {subnet.name} ({subnet.subnet}) has peers {[p.username for p in peers_linked]}")
            for peer in peers_linked:
                allow_link(subnet.subnet, peer.address)
                allow_link(peer.address, subnet.subnet)

        logging.info("Loading from db subnet to subnet links")
        subnet_to_subnet_links = db.get_links_between_subnets()
        for subnet in subnets:
            linked_subnets = subnet_to_subnet_links[subnet.subnet] if subnet.subnet in subnet_to_subnet_links else []
            if len(linked_subnets) > 0:
                logging.info(f"Subnet {subnet.name} ({subnet.subnet}) is linked to {[s.name for s in linked_subnets]}")
            for linked_subnet in linked_subnets:
                allow_link(subnet.subnet, linked_subnet.subnet)
                allow_link(linked_subnet.subnet, subnet.subnet)

        logging.info("Loading from db subnet to service links")
        subnet_to_service_links = db.get_links_from_subnets_to_services()
        for subnet in subnets:
            services_linked = subnet_to_service_links[subnet.subnet] if subnet.subnet in subnet_to_service_links else []
            if len(services_linked) > 0:
                logging.info(f"Subnet {subnet.name} ({subnet.subnet}) has services {[s.name for s in services_linked]}")
            for service in services_linked:
                host = db.get_service_host(service)
                if host is None:
                    raise Exception(f"Service host for service {service.name} not found")
                allow_link_with_port(subnet.subnet, host.address, service.port)
                allow_answer_link(host.address, subnet.subnet)


        default_policy_drop()
        logging.info("Loaded and applied WireGuard configuration from database")
    except Exception as e:
        logging.error(f"Failed to apply WireGuard configuration: {e}")
        raise e
