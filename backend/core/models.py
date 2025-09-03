from contextlib import contextmanager
from pydantic import BaseModel
from backend.core.config import settings

class Service(BaseModel):
    port: int
    name: str
    department: str
    description: str = ""

class Peer(BaseModel):
    username: str
    public_key: str
    preshared_key: str
    address: str
    services: dict[int, Service] = {}
    x: float
    y: float


class Subnet(BaseModel):
    subnet: str
    name: str
    description: str = ""
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
