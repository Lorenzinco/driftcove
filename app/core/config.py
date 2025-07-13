from fastapi import HTTPException,Header
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_path: str = "/home/db/driftcove.db"
    wg_interface: str = "wg0"
    wg_udp_port: int =1194
    wg_backend_tcp_port: int=8000
    api_token: str = "supersecuretoken"
    endpoint: str = f"127.0.0.0:{wg_udp_port}"
    public_key: str = ""
    wg_default_subnet: str = "10.128.0.0/9"
    mtu: str = "1420"

try:
    with open("/etc/wireguard/publickey", "r") as f:
        public_key_value = f.read().strip()
except FileNotFoundError:
    public_key_value = ""

settings = Settings(public_key=public_key_value)

tags_metadata = [
    {
        "name": "subnet",
        "description": "Operations related to subnets, create, manage and delete subnets",
    },
    {
        "name": "peer",
        "description": "Operations related to peers, create, manage and delete peers, also get the subnets a peer is part of as well as the configuration for the peer",
    },
    {
        "name": "network",
        "description": "Network operations, such as getting all subnets and the current network topology",
    },
    {
        "name": "service",
        "description": "Operations related to services, create, manage and delete services, also get the peers that are part of a service",
    }
]

# DB_PATH = "/home/db/user_configs.db"
# WG_INTERFACE = "wg0"
# API_TOKEN = os.environ.get("WIREGUARD_API_TOKEN", "supersecuretoken")
# ENDPOINT = os.getenv("WIREGUARD_ENDPOINT", "127.0.0.1:1194")
# PUBLIC_KEY = os.getenv("WIREGUARD_PUBLIC_KEY", "")
# WIREGUARD_SUBNET = os.getenv("WIREGUARD_SUBNET","10.128.0.0/9")
# MTU = os.getenv("WIREGUARD_MTU", "1420")


def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth scheme")
    token = authorization.split(" ")[1]
    if token != settings.api_token:
        raise HTTPException(status_code=403, detail="Invalid token")