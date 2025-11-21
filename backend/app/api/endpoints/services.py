from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.peer import Peer, PeerType
from app.models.service import PublishedService
from app.models.wan import WanNetwork
from app.schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse, ServiceListResponse
from app.services.ip_allocation import IPAllocationService
from app.services.deployment import DeploymentService
from app.services.pihole import PiHoleService, _slugify

router = APIRouter()


def build_service_response(service: PublishedService, hostname: Optional[str] = None) -> ServiceResponse:
    return ServiceResponse(
        id=service.id,
        peer_id=service.peer_id,
        name=service.name,
        description=service.description,
        local_ip=service.local_ip,
        local_port=service.local_port,
        shared_ip=service.shared_ip,
        shared_port=service.shared_port,
        protocol=service.protocol,
        is_active=service.is_active,
        created_at=service.created_at,
        hostname=hostname,
    )


@router.get("/wan/{wan_id}", response_model=ServiceListResponse)
async def list_services(
    wan_id: str,
    skip: int = 0,
    limit: int = 100,
    peer_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all published services in a WAN network."""
    # Verify WAN exists
    wan_result = await db.execute(
        select(WanNetwork).where(WanNetwork.id == wan_id)
    )
    if not wan_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    query = select(PublishedService).join(Peer).where(Peer.wan_id == wan_id)
    if peer_id:
        query = query.where(PublishedService.peer_id == peer_id)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    services = result.scalars().all()

    # Get total count
    count_query = select(func.count(PublishedService.id)).join(Peer).where(Peer.wan_id == wan_id)
    if peer_id:
        count_query = count_query.where(PublishedService.peer_id == peer_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    pihole = PiHoleService()
    wan_name = wan.name if wan else None
    items = []
    for s in services:
        hostname = None
        if pihole.is_configured():
            hostname = pihole.build_hostname(s.name, s.id, wan_name=wan_name)
        items.append(build_service_response(s, hostname))

    return ServiceListResponse(items=items, total=total)


@router.post("/peer/{peer_id}", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    peer_id: str,
    service_in: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    auto_deploy: bool = Query(False, description="Automatically queue deploy jobs for auto-deploy peers"),
):
    """Publish a new service for a peer."""
    # Get peer with WAN
    result = await db.execute(
        select(Peer)
        .options(selectinload(Peer.wan))
        .where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    # Allocate shared service IP
    ip_service = IPAllocationService(db)
    shared_ip = await ip_service.allocate_shared_service_ip(
        peer.wan_id,
        peer.wan.shared_services_range,
    )

    if not shared_ip:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No available IPs in shared services range",
        )

    service = PublishedService(
        id=str(uuid.uuid4()),
        peer_id=peer_id,
        name=service_in.name,
        description=service_in.description,
        local_ip=service_in.local_ip,
        local_port=service_in.local_port,
        shared_ip=shared_ip,
        shared_port=service_in.shared_port or service_in.local_port,
        protocol=service_in.protocol,
        is_active=True,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)

    # Trigger auto-deploy for MikroTik peers in this WAN that have auto_deploy enabled
    pihole = PiHoleService()
    hostname = None
    try:
        if pihole.is_configured():
            hostname = pihole.build_hostname(service.name, service.id, wan_name=peer.wan.name)
            await pihole.add_record(hostname, service.shared_ip)
    except Exception:
        # don't block service creation on DNS failure
        pass

    if auto_deploy:
        peers_result = await db.execute(
            select(Peer).where(
                Peer.wan_id == peer.wan_id,
                Peer.type == PeerType.MIKROTIK,
                Peer.mikrotik_auto_deploy.is_(True),
            )
        )
        mikrotik_peers = peers_result.scalars().all()
        if mikrotik_peers:
            deployment_service = DeploymentService(db)
            for p in mikrotik_peers:
                try:
                    await deployment_service.deploy_configuration(p.id)
                except Exception:
                    # Don't block service creation if deployment queuing fails
                    continue

    # Mark non-auto peers as needing config refresh
    peers_to_mark = await db.execute(
        select(Peer).where(
            Peer.wan_id == peer.wan_id,
            (Peer.type != PeerType.MIKROTIK) | (Peer.mikrotik_auto_deploy.is_(False)),
        )
    )
    for p in peers_to_mark.scalars().all():
        meta = p.peer_metadata or {}
        meta["needs_config_refresh"] = True
        p.peer_metadata = meta
    await db.commit()

    return build_service_response(service, hostname)


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific service."""
    result = await db.execute(
        select(PublishedService).where(PublishedService.id == service_id)
    )
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    pihole = PiHoleService()
    hostname = None
    try:
        if pihole.is_configured():
            hostname = pihole.build_hostname(service.name, service.id)
    except Exception:
        pass

    return build_service_response(service, hostname)


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    service_in: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a service."""
    result = await db.execute(
        select(PublishedService).where(PublishedService.id == service_id)
    )
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    update_data = service_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    await db.commit()
    await db.refresh(service)

    return ServiceResponse(
        id=service.id,
        peer_id=service.peer_id,
        name=service.name,
        description=service.description,
        local_ip=service.local_ip,
        local_port=service.local_port,
        shared_ip=service.shared_ip,
        shared_port=service.shared_port,
        protocol=service.protocol,
        is_active=service.is_active,
        created_at=service.created_at,
    )


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a service."""
    result = await db.execute(
        select(PublishedService).where(PublishedService.id == service_id)
    )
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    pihole = PiHoleService()
    try:
        if pihole.is_configured():
            hostname = pihole.build_hostname(service.name, service.id)
            await pihole.delete_record(hostname, service.shared_ip)
    except Exception:
        pass

    await db.delete(service)
    await db.commit()
