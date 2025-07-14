from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import db
from app.core.iptables import allow_link, flush_iptables, default_policy_drop
from app.core.models import Subnet
from app.core.wireguard import apply_to_wg_config
from app.db.init_db import init_db
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP CODE
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting Driftcove WireGuard API...")
    try:
        init_db(settings.db_path)
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise
    try:
        logging.info("Resetting iptables rules for WireGuard")
        flush_iptables()

        subnets = db.get_subnets()
        for subnet in subnets:
            peers = db.get_peers_in_subnet(subnet)
            for peer in peers:
                apply_to_wg_config(peer)
                logging.info(f"Adding route for peer {peer.username} in subnet {subnet.subnet}")
                allow_link(peer.address, subnet.subnet)

        logging.info("Loading from db peer to peer links")
        links = db.get_links_between_peers()
        for link in links:
            allow_link(link[0],link[1])
            allow_link(link[1],link[0])

        logging.info("Every non-allowed traffic will be dropped")
        default_policy_drop()

        logging.info(f"Loaded {len(subnets)} subnets and {sum(len(db.get_peers_in_subnet(subnet)) for subnet in subnets)} peers from the database.")

        logging.info("Loading and ")
    except Exception as e:
        logging.error(f"Failed to configure WireGuard on startup: {e}")
        raise

    yield  # control passes to the app here
