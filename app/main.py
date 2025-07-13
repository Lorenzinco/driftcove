from fastapi import FastAPI
from app.api import peer, subnet, service, network
from app.core.config import tags_metadata
from app.core.lifespan import lifespan

app = FastAPI(
    title="Driftcove WireGuard API",
    version="0.1.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan
)

app.include_router(peer.router, prefix="/peer")
app.include_router(subnet.router, prefix="/subnet")
app.include_router(service.router, prefix="/service")
app.include_router(network.router, prefix="/network")