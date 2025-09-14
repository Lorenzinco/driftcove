from fastapi import FastAPI
from backend.api import peer, subnet, service, network
from backend.core.config import tags_metadata
from backend.core.lifespan import lifespan

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