from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.database import init_db, get_db
from app.api import api_router
from app.models.peer import Peer
from app.models.service import PublishedService
from app.models.deployment import DeploymentJob, JobStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title=settings.APP_NAME,
    description="WireGuard WAN Overlay Network Management Application",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)):
    registry = CollectorRegistry()

    peers_q = await db.execute(
        select(
            func.count(Peer.id),
            func.sum(case((Peer.is_online == True, 1), else_=0)),
        )
    )
    total_peers, online_peers = peers_q.one()
    g_total_peers = Gauge("wirewan_peers_total", "Total peers", registry=registry)
    g_online_peers = Gauge("wirewan_peers_online", "Online peers", registry=registry)
    g_total_peers.set(total_peers or 0)
    g_online_peers.set(online_peers or 0)

    services_q = await db.execute(select(func.count(PublishedService.id)))
    services_total = services_q.scalar() or 0
    g_services = Gauge("wirewan_services_total", "Total published services", registry=registry)
    g_services.set(services_total)

    jobs_q = await db.execute(
        select(DeploymentJob.status, func.count(DeploymentJob.id)).group_by(DeploymentJob.status)
    )
    g_jobs = Gauge("wirewan_jobs_total", "Deployment jobs by status", ["status"], registry=registry)
    seen_statuses = set()
    for status, count in jobs_q.fetchall():
        seen_statuses.add(status)
        g_jobs.labels(status=status.value).set(count)
    for status in JobStatus:
        if status not in seen_statuses:
            g_jobs.labels(status=status.value).set(0)

    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
