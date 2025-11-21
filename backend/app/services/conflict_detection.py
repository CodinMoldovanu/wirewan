import ipaddress
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.peer import Peer
from app.models.subnet import LocalSubnet
from app.models.wan import WanNetwork


class ConflictSeverity(str, Enum):
    CRITICAL = "critical"  # Overlap with tunnel or shared services - blocks routing
    WARNING = "warning"  # Overlap with other peer's subnet - may cause routing issues
    INFO = "info"  # Informational notice


class ConflictResolution(str, Enum):
    DONT_ROUTE = "dont_route"
    USE_NAT = "use_nat"
    CHANGE_SUBNET = "change_subnet"
    SELECTIVE_ROUTING = "selective_routing"


@dataclass
class SubnetConflict:
    subnet: str
    conflict_type: str
    severity: ConflictSeverity
    conflicting_with: str
    conflicting_subnet: str
    description: str
    suggested_resolutions: List[ConflictResolution]


class ConflictDetectionService:
    """Service for detecting subnet conflicts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def subnets_overlap(self, cidr1: str, cidr2: str) -> bool:
        """Check if two CIDR ranges overlap."""
        try:
            net1 = ipaddress.ip_network(cidr1, strict=False)
            net2 = ipaddress.ip_network(cidr2, strict=False)
            return net1.overlaps(net2)
        except ValueError:
            return False

    async def get_wan_with_peers(self, wan_id: str) -> Optional[WanNetwork]:
        """Get WAN network with all peers and their subnets."""
        result = await self.db.execute(
            select(WanNetwork)
            .options(selectinload(WanNetwork.peers).selectinload(Peer.local_subnets))
            .where(WanNetwork.id == wan_id)
        )
        return result.scalar_one_or_none()

    async def detect_conflicts(
        self,
        wan_id: str,
        peer_id: str,
        subnets: List[str],
        existing_routes: Optional[List[str]] = None,
    ) -> List[SubnetConflict]:
        """Detect conflicts for a peer's local subnets."""
        conflicts = []
        existing_routes = existing_routes or []
        existing_route_nets = [ipaddress.ip_network(r, strict=False) for r in existing_routes if r]

        wan = await self.get_wan_with_peers(wan_id)
        if not wan:
            return conflicts

        for subnet in subnets:
            # Check against tunnel IP range
            if self.subnets_overlap(subnet, wan.tunnel_ip_range):
                conflicts.append(SubnetConflict(
                    subnet=subnet,
                    conflict_type="tunnel_ip_overlap",
                    severity=ConflictSeverity.CRITICAL,
                    conflicting_with="WAN Tunnel Network",
                    conflicting_subnet=wan.tunnel_ip_range,
                    description=f"Subnet {subnet} overlaps with WAN tunnel IP range {wan.tunnel_ip_range}",
                    suggested_resolutions=[
                        ConflictResolution.DONT_ROUTE,
                        ConflictResolution.USE_NAT,
                        ConflictResolution.CHANGE_SUBNET,
                    ]
                ))

            # Check against shared services range
            if self.subnets_overlap(subnet, wan.shared_services_range):
                conflicts.append(SubnetConflict(
                    subnet=subnet,
                    conflict_type="shared_services_overlap",
                    severity=ConflictSeverity.CRITICAL,
                    conflicting_with="WAN Shared Services Network",
                    conflicting_subnet=wan.shared_services_range,
                    description=f"Subnet {subnet} overlaps with shared services range {wan.shared_services_range}",
                    suggested_resolutions=[
                        ConflictResolution.DONT_ROUTE,
                        ConflictResolution.USE_NAT,
                        ConflictResolution.CHANGE_SUBNET,
                    ]
                ))

            # Check against other peers' subnets
            for peer in wan.peers:
                if peer.id == peer_id:
                    continue

                for local_subnet in peer.local_subnets:
                    if self.subnets_overlap(subnet, local_subnet.cidr):
                        conflicts.append(SubnetConflict(
                            subnet=subnet,
                            conflict_type="peer_subnet_overlap",
                            severity=ConflictSeverity.WARNING,
                            conflicting_with=f"Peer: {peer.name}",
                            conflicting_subnet=local_subnet.cidr,
                            description=f"Subnet {subnet} overlaps with {peer.name}'s subnet {local_subnet.cidr}",
                            suggested_resolutions=[
                                ConflictResolution.USE_NAT,
                                ConflictResolution.SELECTIVE_ROUTING,
                                ConflictResolution.CHANGE_SUBNET,
                            ]
                        ))

            # Check against existing routes on WAN peers (to avoid dual paths)
            for route_net in existing_route_nets:
                try:
                    subnet_net = ipaddress.ip_network(subnet, strict=False)
                    if subnet_net.overlaps(route_net):
                        conflicts.append(SubnetConflict(
                            subnet=subnet,
                            conflict_type="existing_route_overlap",
                            severity=ConflictSeverity.WARNING,
                            conflicting_with="Existing routed network",
                            conflicting_subnet=str(route_net),
                            description=f"Subnet {subnet} overlaps with existing routed network {route_net}",
                            suggested_resolutions=[
                                ConflictResolution.DONT_ROUTE,
                                ConflictResolution.SELECTIVE_ROUTING,
                                ConflictResolution.CHANGE_SUBNET,
                            ],
                        ))
                except ValueError:
                    continue

        return conflicts

    async def get_all_conflicts(self, wan_id: str) -> List[SubnetConflict]:
        """Get all conflicts across all peers in a WAN."""
        conflicts = []

        wan = await self.get_wan_with_peers(wan_id)
        if not wan:
            return conflicts

        for peer in wan.peers:
            peer_subnets = [s.cidr for s in peer.local_subnets]
            peer_conflicts = await self.detect_conflicts(wan_id, peer.id, peer_subnets)
            conflicts.extend(peer_conflicts)

        return conflicts

    def find_available_nat_subnet(
        self,
        conflicting_subnet: str,
        existing_subnets: List[str]
    ) -> Optional[str]:
        """Find an available subnet for NAT translation."""
        conflicting_net = ipaddress.ip_network(conflicting_subnet, strict=False)
        prefix_len = conflicting_net.prefixlen

        # Try 172.16.0.0/12 range first
        for base in range(16, 32):
            candidate = f"172.{base}.0.0/{prefix_len}"
            try:
                candidate_net = ipaddress.ip_network(candidate, strict=False)
                conflict_found = False

                for existing in existing_subnets:
                    existing_net = ipaddress.ip_network(existing, strict=False)
                    if candidate_net.overlaps(existing_net):
                        conflict_found = True
                        break

                if not conflict_found:
                    return str(candidate_net)
            except ValueError:
                continue

        # Try 192.168.0.0/16 range as fallback
        for third_octet in range(0, 256):
            candidate = f"192.168.{third_octet}.0/{prefix_len}"
            try:
                candidate_net = ipaddress.ip_network(candidate, strict=False)
                conflict_found = False

                for existing in existing_subnets:
                    existing_net = ipaddress.ip_network(existing, strict=False)
                    if candidate_net.overlaps(existing_net):
                        conflict_found = True
                        break

                if not conflict_found:
                    return str(candidate_net)
            except ValueError:
                continue

        return None
