from fastapi import APIRouter

from app.api.endpoints import wan, peers, services, deployments, auth

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(wan.router, prefix="/wan", tags=["wan"])
api_router.include_router(peers.router, prefix="/peers", tags=["peers"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(deployments.router, prefix="/jobs", tags=["jobs"])
