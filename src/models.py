from pydantic import BaseModel

class Peer(BaseModel):
    username: str
    public_key: str
    preshared_key: str
    address: str

class Service(Peer):
    name: str
    department: str

class Subnet(BaseModel):
    subnet: str
    name: str
    description: str