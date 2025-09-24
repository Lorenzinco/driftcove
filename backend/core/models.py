from contextlib import contextmanager
from pydantic import BaseModel, Field
from backend.core.config import settings
from backend.core.logger import logger as logging

class Service(BaseModel):
    port: int
    name: str
    department: str
    description: str = ""
    protocol: str = "tcp"

    def from_json(self, data: dict):
        self.port = data.get("port", self.port)
        self.name = data.get("name", self.name)
        self.department = data.get("department", self.department)
        self.description = data.get("description", self.description)
        return self
    

class Peer(BaseModel):
    username: str
    public_key: str
    preshared_key: str
    address: str
    # Use service name as key (JSON provides names, not numeric ids)
    services: dict[str, Service] = Field(default_factory=dict)
    x: float
    y: float
    tx: int = 0
    rx: int = 0
    last_handshake: int = 0

    def from_json(self, data: dict):
        self.username = data.get("username", self.username)
        self.public_key = data.get("public_key", self.public_key)
        self.preshared_key = data.get("preshared_key", self.preshared_key)
        self.address = data.get("address", self.address)
        raw_services = data.get("services", {})
        # Accept either dict[name] = service_dict or dict[port] = service_dict
        converted = {}
        for k, v in raw_services.items():
            try:
                # If key is numeric string and name missing, keep port as name
                if isinstance(k, str) and k.isdigit():
                    svc = Service(**v)
                    converted[svc.name or k] = svc
                else:
                    svc = Service(**v)
                    converted[svc.name or str(k)] = svc
            except Exception as e:
                logging.warning(f"Skipping service {k}: {e}")
        self.services = converted
        self.x = data.get("x", self.x)
        self.y = data.get("y", self.y)
        return self


class Subnet(BaseModel):
    subnet: str
    name: str
    description: str = ""
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
    rgba: int = 0x00FF0025  # Default to semi-transparent green

    def from_json(self, data: dict):
        self.subnet = data.get("subnet", self.subnet)
        self.name = data.get("name", self.name)
        self.description = data.get("description", self.description)
        self.x = data.get("x", self.x)
        self.y = data.get("y", self.y)
        self.width = data.get("width", self.width)
        self.height = data.get("height", self.height)
        self.rgba = data.get("rgba", self.rgba)
        return self

    
class Topology(BaseModel):
    subnets: dict[str, Subnet] = Field(default_factory=dict)
    peers: dict[str, Peer] = Field(default_factory=dict)
    services: dict[str, Service] = Field(default_factory=dict)
    network: dict[str, list[Peer]] = Field(default_factory=dict)
    service_links: dict[str, list[Peer]] = Field(default_factory=dict)
    p2p_links: dict[str, list[Peer]] = Field(default_factory=dict)
    subnet_links: dict[str, list[Peer]] = Field(default_factory=dict)
    subnet_to_subnet_links: dict[str, list[Subnet]] = Field(default_factory=dict)
    subnet_to_service_links: dict[str, list[Service]] = Field(default_factory=dict)
    admin_peer_to_peer_links: dict[str, list[Peer]] = Field(default_factory=dict)
    admin_peer_to_subnet_links: dict[str, list[Subnet]] = Field(default_factory=dict)
    admin_subnet_to_subnet_links: dict[str, list[Subnet]] = Field(default_factory=dict)