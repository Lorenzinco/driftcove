from contextlib import contextmanager
from pydantic import BaseModel
from backend.core.config import settings
import subprocess

class Peer(BaseModel):
    username: str
    public_key: str
    preshared_key: str
    address: str
    
    x: float
    y: float

class Service(Peer):
    name: str
    department: str
    port: int

class Subnet(BaseModel):
    subnet: str
    name: str
    description: str
    x: float
    y: float
    width: float
    height: float
