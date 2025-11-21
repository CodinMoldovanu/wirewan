from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import encrypt_value, decrypt_value
from app.models.wan import WanNetwork
from app.models.peer import Peer, PeerType
from app.models.subnet import LocalSubnet
from app.schemas.peer import (
    PeerCreate,
    PeerUpdate,
    PeerResponse,
    PeerListResponse,
    MikrotikTestConnectionResponse,
    SubnetResponse,
    PeerConfigResponse,
)
from app.services.ip_allocation import IPAllocationService
from app.services.conflict_detection import ConflictDetectionService
from app.services.wireguard import WireGuardService
from app.services.config_generator import ConfigGeneratorService
from app.services.deployment import DeploymentService
from app.models.config_history import ConfigType, ConfigurationHistory
from sqlalchemy.orm import selectinload as _selectinload
from app.core.config import settings

router = APIRouter()


def peer_to_response(peer: Peer) -> PeerResponse:
    """Convert Peer model to response schema."""
    return PeerResponse(
        id=peer.id,
        wan_id=peer.wan_id,
        name=peer.name,
        type=peer.type,
        public_key=peer.public_key,
        tunnel_ip=peer.tunnel_ip,
        endpoint=peer.endpoint,
        listen_port=peer.listen_port,
        persistent_keepalive=peer.persistent_keepalive,
        tags=peer.tags or [],
        is_online=peer.is_online,
        last_seen=peer.last_seen,
        created_at=peer.created_at,
        updated_at=peer.updated_at,
        mikrotik_management_ip=peer.mikrotik_management_ip,
        mikrotik_api_port=peer.mikrotik_api_port,
        mikrotik_auth_method=peer.mikrotik_auth_method,
        mikrotik_username=peer.mikrotik_username,
        mikrotik_use_ssl=peer.mikrotik_use_ssl,
        mikrotik_verify_cert=peer.mikrotik_verify_cert,
        mikrotik_auto_deploy=peer.mikrotik_auto_deploy,
        mikrotik_interface_name=peer.mikrotik_interface_name,
        mikrotik_last_api_check=peer.mikrotik_last_api_check,
        mikrotik_api_status=peer.mikrotik_api_status,
        mikrotik_router_identity=peer.mikrotik_router_identity,
        mikrotik_routeros_version=peer.mikrotik_routeros_version,
        local_subnets=[
            SubnetResponse(
                id=s.id,
                cidr=s.cidr,
                is_routed=s.is_routed,
                nat_enabled=s.nat_enabled,
                nat_translated_cidr=s.nat_translated_cidr,
                description=s.description,
            )
            for s in peer.local_subnets
        ],
    )


@router.get("/wan/{wan_id}", response_model=PeerListResponse)
async def list_peers(
    wan_id: str,
    skip: int = 0,
    limit: int = 100,
    peer_type: Optional[PeerType] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all peers in a WAN network."""
    # Verify WAN exists
    wan_result = await db.execute(
        select(WanNetwork).where(WanNetwork.id == wan_id)
    )
    if not wan_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    query = (
        select(Peer)
        .options(selectinload(Peer.local_subnets))
        .where(Peer.wan_id == wan_id)
    )

    if peer_type:
        query = query.where(Peer.type == peer_type)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    peers = result.scalars().all()

    # Get total count
    count_query = select(func.count(Peer.id)).where(Peer.wan_id == wan_id)
    if peer_type:
        count_query = count_query.where(Peer.type == peer_type)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return PeerListResponse(
        items=[peer_to_response(p) for p in peers],
        total=total,
    )


@router.post("/wan/{wan_id}", response_model=PeerResponse, status_code=status.HTTP_201_CREATED)
async def create_peer(
    wan_id: str,
    peer_in: PeerCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new peer in a WAN network."""
    # Verify WAN exists
    wan_result = await db.execute(
        select(WanNetwork).where(WanNetwork.id == wan_id)
    )
    wan = wan_result.scalar_one_or_none()
    if not wan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WAN network not found",
        )

    # Check for conflicts with local subnets
    if peer_in.local_subnets:
        conflict_service = ConflictDetectionService(db)
        conflicts = await conflict_service.detect_conflicts(
            wan_id,
            "",  # New peer, no ID yet
            [s.cidr for s in peer_in.local_subnets],
        )
        critical_conflicts = [c for c in conflicts if c.severity.value == "critical"]
        if critical_conflicts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Critical subnet conflicts detected",
                    "conflicts": [
                        {
                            "subnet": c.subnet,
                            "description": c.description,
                        }
                        for c in critical_conflicts
                    ],
                },
            )

    # Allocate tunnel IP
    ip_service = IPAllocationService(db)
    tunnel_ip = await ip_service.allocate_tunnel_ip(wan_id, wan.tunnel_ip_range)
    if not tunnel_ip:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No available tunnel IPs in the WAN network",
        )

    # Generate WireGuard keypair
    keypair = WireGuardService.generate_keypair()

    peer = Peer(
        id=str(uuid.uuid4()),
        wan_id=wan_id,
        name=peer_in.name,
        type=peer_in.type,
        public_key=keypair.public_key,
        private_key_encrypted=encrypt_value(keypair.private_key),
        tunnel_ip=tunnel_ip,
        endpoint=peer_in.endpoint,
        listen_port=peer_in.listen_port,
        persistent_keepalive=peer_in.persistent_keepalive,
        tags=peer_in.tags,
    )

    # Handle MikroTik-specific fields
    if peer_in.type == PeerType.MIKROTIK:
        peer.mikrotik_management_ip = peer_in.mikrotik_management_ip
        peer.mikrotik_api_port = peer_in.mikrotik_api_port
        peer.mikrotik_auth_method = peer_in.mikrotik_auth_method
        peer.mikrotik_username = peer_in.mikrotik_username
        if peer_in.mikrotik_password:
            peer.mikrotik_password_encrypted = encrypt_value(peer_in.mikrotik_password)
        if peer_in.mikrotik_api_token:
            peer.mikrotik_api_token_encrypted = encrypt_value(peer_in.mikrotik_api_token)
        peer.mikrotik_use_ssl = peer_in.mikrotik_use_ssl
        peer.mikrotik_verify_cert = peer_in.mikrotik_verify_cert
        peer.mikrotik_auto_deploy = peer_in.mikrotik_auto_deploy
        peer.mikrotik_interface_name = peer_in.mikrotik_interface_name

    db.add(peer)

    # Add local subnets
    if peer_in.local_subnets:
        for subnet_in in peer_in.local_subnets:
            subnet = LocalSubnet(
                id=str(uuid.uuid4()),
                peer_id=peer.id,
                cidr=subnet_in.cidr,
                is_routed=subnet_in.is_routed,
                description=subnet_in.description,
            )
            db.add(subnet)

    await db.commit()

    # Refresh to get relationships
    result = await db.execute(
        select(Peer)
        .options(selectinload(Peer.local_subnets))
        .where(Peer.id == peer.id)
    )
    peer = result.scalar_one()

    return peer_to_response(peer)


@router.get("/{peer_id}", response_model=PeerResponse)
async def get_peer(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific peer."""
    result = await db.execute(
        select(Peer)
        .options(selectinload(Peer.local_subnets))
        .where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    return peer_to_response(peer)


@router.put("/{peer_id}", response_model=PeerResponse)
async def update_peer(
    peer_id: str,
    peer_in: PeerUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a peer."""
    result = await db.execute(
        select(Peer)
        .options(selectinload(Peer.local_subnets))
        .where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    # Update basic fields
    update_data = peer_in.model_dump(exclude_unset=True)

    # Handle password/token encryption
    if "mikrotik_password" in update_data and update_data["mikrotik_password"]:
        peer.mikrotik_password_encrypted = encrypt_value(update_data.pop("mikrotik_password"))
    elif "mikrotik_password" in update_data:
        update_data.pop("mikrotik_password")

    if "mikrotik_api_token" in update_data and update_data["mikrotik_api_token"]:
        peer.mikrotik_api_token_encrypted = encrypt_value(update_data.pop("mikrotik_api_token"))
    elif "mikrotik_api_token" in update_data:
        update_data.pop("mikrotik_api_token")

    for field, value in update_data.items():
        if hasattr(peer, field):
            setattr(peer, field, value)

    await db.commit()
    await db.refresh(peer)

    return peer_to_response(peer)


@router.delete("/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_peer(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a peer."""
    result = await db.execute(
        select(Peer).where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    # Best-effort cleanup of managed configuration before deletion
    if peer.type == PeerType.MIKROTIK:
        try:
            deployment_service = DeploymentService(db)
            await deployment_service.clear_managed_configuration(peer_id)
        except Exception:
            # Don't block deletion; surface as warning in operations log if present
            pass

    await db.delete(peer)
    await db.commit()


@router.post("/{peer_id}/regenerate-keys", response_model=PeerResponse)
async def regenerate_keys(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Regenerate WireGuard keypair for a peer."""
    result = await db.execute(
        select(Peer)
        .options(selectinload(Peer.local_subnets))
        .where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    keypair = WireGuardService.generate_keypair()
    peer.public_key = keypair.public_key
    peer.private_key_encrypted = encrypt_value(keypair.private_key)

    await db.commit()
    await db.refresh(peer)

    return peer_to_response(peer)


@router.get("/{peer_id}/config", response_model=PeerConfigResponse)
async def get_peer_config(
    peer_id: str,
    config_type: str = Query("wireguard", regex="^(wireguard|mikrotik-script)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get generated configuration for a peer."""
    result = await db.execute(
        select(Peer)
        .options(
            selectinload(Peer.wan),
            selectinload(Peer.local_subnets),
            selectinload(Peer.published_services),
        )
        .where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    config_gen = ConfigGeneratorService(db)
    private_key = decrypt_value(peer.private_key_encrypted) if peer.private_key_encrypted else ""

    if config_type == "wireguard":
        config_text = await config_gen.generate_wireguard_config(peer_id, private_key)
    else:  # mikrotik-script
        config_text = await config_gen.generate_mikrotik_script(peer_id, private_key)

    # Clear refresh flag on successful generation
    meta = peer.peer_metadata or {}
    if meta.get("needs_config_refresh"):
        meta.pop("needs_config_refresh", None)
        peer.peer_metadata = meta
        await db.commit()

    return PeerConfigResponse(
        config_type=config_type,
        config_text=config_text,
        peer_name=peer.name,
        generated_at=datetime.utcnow(),
    )


@router.post("/{peer_id}/mikrotik/test-connection", response_model=MikrotikTestConnectionResponse)
async def test_mikrotik_connection(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Test MikroTik API connection for a peer."""
    deployment_service = DeploymentService(db)
    result = await deployment_service.test_connection(peer_id)

    return MikrotikTestConnectionResponse(**result)


@router.get("/{peer_id}/mikrotik/preflight")
async def preflight_mikrotik(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Run a pre-deploy conflict check on the MikroTik router."""
    deployment_service = DeploymentService(db)
    result = await deployment_service.preflight_check(peer_id)
    return result


@router.get("/{peer_id}/mikrotik/verify")
async def verify_mikrotik(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify the router state matches desired managed configuration."""
    deployment_service = DeploymentService(db)
    result = await deployment_service.verify_configuration(peer_id)
    return result


@router.post("/{peer_id}/mikrotik/revert")
async def revert_mikrotik(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Revert to the last stored MikroTik API config for this peer."""
    result = await db.execute(
        select(ConfigurationHistory)
        .where(
            ConfigurationHistory.peer_id == peer_id,
            ConfigurationHistory.config_type == ConfigType.MIKROTIK_API,
        )
        .order_by(ConfigurationHistory.generated_at.desc())
        .limit(1)
    )
    history = result.scalar_one_or_none()
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stored MikroTik configuration to revert to",
        )

    deployment_service = DeploymentService(db)
    try:
        await deployment_service.apply_raw_mikrotik_config(peer_id, history.configuration_text)
        return {"message": "Reverted to last MikroTik configuration"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{peer_id}/mikrotik/clear")
async def clear_mikrotik(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove all WireWAN-managed resources from this MikroTik peer."""
    deployment_service = DeploymentService(db)
    try:
        await deployment_service.clear_managed_configuration(peer_id)
        return {"message": "Managed configuration cleared from router"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{peer_id}/mikrotik/deploy")
async def deploy_to_mikrotik(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
    approve: bool = Query(False, description="Set true to execute; false to preview plan only"),
):
    """Deploy configuration to MikroTik router via API."""
    deployment_service = DeploymentService(db)

    if settings.REQUIRE_DEPLOY_APPROVAL and not approve:
        plan = await deployment_service.plan_configuration(peer_id)
        return {"message": "Approval required", "plan": plan}

    try:
        job = await deployment_service.deploy_configuration(peer_id)
        return {
            "message": "Deployment job created",
            "job_id": job.id,
            "status": job.status.value,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{peer_id}/check-conflicts")
async def check_peer_conflicts(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Check for subnet conflicts for a peer."""
    result = await db.execute(
        select(Peer)
        .options(selectinload(Peer.local_subnets))
        .where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    conflict_service = ConflictDetectionService(db)
    conflicts = await conflict_service.detect_conflicts(
        peer.wan_id,
        peer.id,
        [s.cidr for s in peer.local_subnets],
    )

    return {
        "peer_id": peer_id,
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
        "has_critical_conflicts": any(c.severity.value == "critical" for c in conflicts),
    }


@router.post("/{peer_id}/subnets")
async def add_subnet(
    peer_id: str,
    cidr: str = Query(...),
    is_routed: bool = Query(True),
    description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Add a local subnet to a peer."""
    result = await db.execute(
        select(Peer).where(Peer.id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found",
        )

    # Check for conflicts
    conflict_service = ConflictDetectionService(db)
    conflicts = await conflict_service.detect_conflicts(
        peer.wan_id,
        peer.id,
        [cidr],
    )

    subnet = LocalSubnet(
        id=str(uuid.uuid4()),
        peer_id=peer_id,
        cidr=cidr,
        is_routed=is_routed,
        description=description,
    )
    db.add(subnet)
    await db.commit()
    await db.refresh(subnet)

    return {
        "subnet": {
            "id": subnet.id,
            "cidr": subnet.cidr,
            "is_routed": subnet.is_routed,
            "description": subnet.description,
        },
        "conflicts": [
            {
                "subnet": c.subnet,
                "severity": c.severity.value,
                "description": c.description,
            }
            for c in conflicts
        ] if conflicts else [],
    }


@router.delete("/{peer_id}/subnets/{subnet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subnet(
    peer_id: str,
    subnet_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a local subnet from a peer."""
    result = await db.execute(
        select(LocalSubnet).where(
            LocalSubnet.id == subnet_id,
            LocalSubnet.peer_id == peer_id,
        )
    )
    subnet = result.scalar_one_or_none()

    if not subnet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subnet not found",
        )

    await db.delete(subnet)
    await db.commit()
