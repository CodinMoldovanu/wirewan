import ipaddress
from typing import List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.peer import Peer
from app.models.service import PublishedService


class IPAllocationService:
    """Service for allocating IPs from network ranges."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_allocated_tunnel_ips(self, wan_id: str) -> Set[str]:
        """Get all allocated tunnel IPs for a WAN."""
        result = await self.db.execute(
            select(Peer.tunnel_ip).where(
                Peer.wan_id == wan_id,
                Peer.tunnel_ip.isnot(None)
            )
        )
        return {row[0] for row in result.fetchall()}

    async def get_allocated_service_ips(self, wan_id: str) -> Set[str]:
        """Get all allocated shared service IPs for a WAN."""
        result = await self.db.execute(
            select(PublishedService.shared_ip)
            .join(Peer)
            .where(Peer.wan_id == wan_id)
        )
        return {row[0] for row in result.fetchall()}

    def get_available_hosts(self, cidr: str) -> List[str]:
        """Get list of available host IPs from a CIDR range."""
        network = ipaddress.ip_network(cidr, strict=False)
        # Skip network address and broadcast address
        hosts = list(network.hosts())
        return [str(ip) for ip in hosts]

    async def allocate_tunnel_ip(self, wan_id: str, tunnel_ip_range: str) -> Optional[str]:
        """Allocate the next available tunnel IP for a peer."""
        allocated = await self.get_allocated_tunnel_ips(wan_id)
        available = self.get_available_hosts(tunnel_ip_range)

        for ip in available:
            if ip not in allocated:
                return ip

        return None  # No IPs available

    async def allocate_shared_service_ip(
        self, wan_id: str, shared_services_range: str
    ) -> Optional[str]:
        """Allocate the next available shared service IP."""
        allocated = await self.get_allocated_service_ips(wan_id)
        available = self.get_available_hosts(shared_services_range)

        for ip in available:
            if ip not in allocated:
                return ip

        return None  # No IPs available

    def is_ip_in_range(self, ip: str, cidr: str) -> bool:
        """Check if an IP is within a CIDR range."""
        try:
            ip_addr = ipaddress.ip_address(ip)
            network = ipaddress.ip_network(cidr, strict=False)
            return ip_addr in network
        except ValueError:
            return False

    async def reserve_specific_tunnel_ip(
        self, wan_id: str, ip: str, tunnel_ip_range: str
    ) -> bool:
        """Reserve a specific tunnel IP if available."""
        if not self.is_ip_in_range(ip, tunnel_ip_range):
            return False

        allocated = await self.get_allocated_tunnel_ips(wan_id)
        return ip not in allocated

    async def reserve_specific_service_ip(
        self, wan_id: str, ip: str, shared_services_range: str
    ) -> bool:
        """Reserve a specific shared service IP if available."""
        if not self.is_ip_in_range(ip, shared_services_range):
            return False

        allocated = await self.get_allocated_service_ips(wan_id)
        return ip not in allocated

    def get_network_info(self, cidr: str) -> dict:
        """Get information about a network range."""
        network = ipaddress.ip_network(cidr, strict=False)
        hosts = list(network.hosts())
        return {
            "network_address": str(network.network_address),
            "broadcast_address": str(network.broadcast_address),
            "netmask": str(network.netmask),
            "prefix_length": network.prefixlen,
            "total_hosts": len(hosts),
            "first_host": str(hosts[0]) if hosts else None,
            "last_host": str(hosts[-1]) if hosts else None,
        }
