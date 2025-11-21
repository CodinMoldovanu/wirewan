from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.wan import WanNetwork
from app.models.peer import Peer
from app.schemas.wan import WanCreate, WanUpdate, WanResponse, WanListResponse
from app.services.ip_allocation import IPAllocationService
from app.services.conflict_detection import ConflictDetectionService

router = APIRouter()


@router.get("", response_model=WanListResponse)
async def list_wan_networks(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all WAN networks."""
    # Get WANs with peer count
    result = await db.execute(
        select(WanNetwork)
        .options(selectinload(WanNetwork.peers))
        .offset(skip)
        .limit(limit)
    )
    wans = result.scalars().all()

    # Get total count
    count_result = await db.execute(select(func.count(WanNetwork.id)))
    total = count_result.scalar()

    items = []
    for wan in wans:
        wan_dict = {
            "id": wan.id,
            "name": wan.name,
            "description": wan.description,
            "tunnel_ip_range": wan.tunnel_ip_range,
            "shared_services_range": wan.shared_services_range,
            "topology_type": wan.topology_type,
            "created_at": wan.created_at,
            "updated_at": wan.updated_at,
            "peer_count": len(wan.peers),
        }
        items.append(WanResponse(**wan_dict))

    return WanListResponse(items=items, total=total)


@router.post("", response_model=WanResponse, status_code=status.HTTP_201_CREATED)
async def create_wan_network(
    wan_in: WanCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new WAN network."""
    # Check if name already exists
    existing = await db.execute(
        select(WanNetwork).where(WanNetwork.name == wan_in.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WAN network with this name already exists",
        )

    wan = WanNetwork(
        id=str(uuid.uuid4()),
        name=wan_in.name,
        description=wan_in.description,
        tunnel_ip_range=wan_in.tunnel_ip_range,
        shared_services_range=wan_in.shared_services_range,
        topology_type=wan_in.topology_type,
    )
    db.add(wan)
    await db.commit()
    await db.refresh(wan)

    return WanResponse(
        id=wan.id,
        name=wan.name,
        description=wan.description,
        tunnel_ip_range=wan.tunnel_ip_range,
        shared_services_range=wan.shared_services_range,
        topology_type=wan.topology_type,
        created_at=wan.created_at,
        updated_at=wan.updated_at,
        peer_count=0,
    )


@router.get("/{wan_id}", response_model=WanResponse)
async def get_wan_network(
    wan_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific WAN network."""
    result = await db.execute(
        select(WanNetwork)
        .options(selectinload(WanNetwork.peers))
        .where(WanNetwork.id == wan_id)
    )
    wan = result.scalar_one_or_none()

    if not wan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    return WanResponse(
        id=wan.id,
        name=wan.name,
        description=wan.description,
        tunnel_ip_range=wan.tunnel_ip_range,
        shared_services_range=wan.shared_services_range,
        topology_type=wan.topology_type,
        created_at=wan.created_at,
        updated_at=wan.updated_at,
        peer_count=len(wan.peers),
    )


@router.put("/{wan_id}", response_model=WanResponse)
async def update_wan_network(
    wan_id: str,
    wan_in: WanUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a WAN network."""
    result = await db.execute(
        select(WanNetwork)
        .options(selectinload(WanNetwork.peers))
        .where(WanNetwork.id == wan_id)
    )
    wan = result.scalar_one_or_none()

    if not wan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    # Update fields
    update_data = wan_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(wan, field, value)

    await db.commit()
    await db.refresh(wan)

    return WanResponse(
        id=wan.id,
        name=wan.name,
        description=wan.description,
        tunnel_ip_range=wan.tunnel_ip_range,
        shared_services_range=wan.shared_services_range,
        topology_type=wan.topology_type,
        created_at=wan.created_at,
        updated_at=wan.updated_at,
        peer_count=len(wan.peers),
    )


@router.delete("/{wan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wan_network(
    wan_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a WAN network."""
    result = await db.execute(
        select(WanNetwork).where(WanNetwork.id == wan_id)
    )
    wan = result.scalar_one_or_none()

    if not wan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    await db.delete(wan)
    await db.commit()


@router.get("/{wan_id}/ip-info")
async def get_wan_ip_info(
    wan_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get IP allocation information for a WAN network."""
    result = await db.execute(
        select(WanNetwork).where(WanNetwork.id == wan_id)
    )
    wan = result.scalar_one_or_none()

    if not wan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    ip_service = IPAllocationService(db)

    tunnel_info = ip_service.get_network_info(wan.tunnel_ip_range)
    shared_info = ip_service.get_network_info(wan.shared_services_range)

    allocated_tunnel = await ip_service.get_allocated_tunnel_ips(wan_id)
    allocated_services = await ip_service.get_allocated_service_ips(wan_id)

    return {
        "tunnel_network": {
            **tunnel_info,
            "allocated_count": len(allocated_tunnel),
            "available_count": tunnel_info["total_hosts"] - len(allocated_tunnel),
        },
        "shared_services_network": {
            **shared_info,
            "allocated_count": len(allocated_services),
            "available_count": shared_info["total_hosts"] - len(allocated_services),
        },
    }


@router.get("/{wan_id}/conflicts")
async def get_wan_conflicts(
    wan_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all subnet conflicts in a WAN network."""
    result = await db.execute(
        select(WanNetwork).where(WanNetwork.id == wan_id)
    )
    wan = result.scalar_one_or_none()

    if not wan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    conflict_service = ConflictDetectionService(db)
    conflicts = await conflict_service.get_all_conflicts(wan_id)

    return {
        "conflicts": [
            {
                "subnet": c.subnet,
                "conflict_type": c.conflict_type,
                "severity": c.severity.value,
                "conflicting_with": c.conflicting_with,
                "conflicting_subnet": c.conflicting_subnet,
                "description": c.description,
                "suggested_resolutions": [r.value for r in c.suggested_resolutions],
            }
            for c in conflicts
        ],
        "total": len(conflicts),
    }


@router.get("/{wan_id}/topology")
async def get_wan_topology(
    wan_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get network topology data for visualization."""
    result = await db.execute(
        select(WanNetwork)
        .options(
            selectinload(WanNetwork.peers).selectinload(Peer.local_subnets),
            selectinload(WanNetwork.peers).selectinload(Peer.published_services),
        )
        .where(WanNetwork.id == wan_id)
    )
    wan = result.scalar_one_or_none()

    if not wan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    nodes = []
    edges = []

    for peer in wan.peers:
        nodes.append({
            "id": peer.id,
            "name": peer.name,
            "type": peer.type.value,
            "tunnel_ip": peer.tunnel_ip,
            "is_online": peer.is_online,
            "endpoint": peer.endpoint,
            "subnet_count": len(peer.local_subnets),
            "service_count": len(peer.published_services),
            "is_mikrotik": peer.type.value == "mikrotik",
            "mikrotik_api_status": peer.mikrotik_api_status.value if peer.mikrotik_api_status else None,
        })

    # For mesh topology, create edges between all peers
    if wan.topology_type.value == "mesh":
        for i, peer_a in enumerate(wan.peers):
            for peer_b in wan.peers[i + 1:]:
                edges.append({
                    "source": peer_a.id,
                    "target": peer_b.id,
                    "type": "mesh",
                })
    # For hub-spoke, create edges from hub to all other peers
    elif wan.topology_type.value == "hub-spoke":
        hub = next((p for p in wan.peers if p.type.value == "hub"), None)
        if hub:
            for peer in wan.peers:
                if peer.id != hub.id:
                    edges.append({
                        "source": hub.id,
                        "target": peer.id,
                        "type": "hub-spoke",
                    })

    return {
        "wan_id": wan.id,
        "wan_name": wan.name,
        "topology_type": wan.topology_type.value,
        "nodes": nodes,
        "edges": edges,
    }
