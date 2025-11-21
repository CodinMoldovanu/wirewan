from datetime import datetime
from typing import List, Optional, Dict
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.peer import Peer, PeerType
from app.models.wan import WanNetwork
from app.models.subnet import LocalSubnet
from app.models.service import PublishedService


class ConfigGeneratorService:
    """Service for generating WireGuard and MikroTik configurations."""

    COMMENT_PREFIX = "WAN-Overlay-Manager:"

    def __init__(self, db: AsyncSession):
        self.db = db

    def _should_route_all_traffic(self, peer: Peer) -> bool:
        try:
            meta = peer.peer_metadata or {}
            return bool(meta.get("route_all_traffic"))
        except Exception:
            return False

    async def get_peer_with_relations(self, peer_id: str) -> Optional[Peer]:
        """Get peer with all related data."""
        result = await self.db.execute(
            select(Peer)
            .options(
                selectinload(Peer.wan),
                selectinload(Peer.local_subnets),
                selectinload(Peer.published_services),
            )
            .where(Peer.id == peer_id)
        )
        return result.scalar_one_or_none()

    async def get_wan_peers(self, wan_id: str) -> List[Peer]:
        """Get all peers in a WAN with their relations."""
        result = await self.db.execute(
            select(Peer)
            .options(
                selectinload(Peer.local_subnets),
                selectinload(Peer.published_services),
            )
            .where(Peer.wan_id == wan_id)
        )
        return list(result.scalars().all())

    def _get_allowed_ips_for_peer(
        self,
        peer: Peer,
        all_peers: List[Peer],
        shared_services_range: str,
    ) -> List[str]:
        """Calculate AllowedIPs for a peer's WireGuard config."""
        allowed_ips = []

        for other_peer in all_peers:
            if other_peer.id == peer.id:
                continue

            # Add other peer's tunnel IP
            if other_peer.tunnel_ip:
                allowed_ips.append(f"{other_peer.tunnel_ip}/32")

            # Add other peer's routed local subnets
            for subnet in other_peer.local_subnets:
                if subnet.is_routed:
                    if subnet.nat_enabled and subnet.nat_translated_cidr:
                        allowed_ips.append(subnet.nat_translated_cidr)
                    else:
                        allowed_ips.append(subnet.cidr)

            # Add other peer's published service IPs
            for service in other_peer.published_services:
                if service.is_active:
                    allowed_ips.append(f"{service.shared_ip}/32")

        # Add shared services range
        allowed_ips.append(shared_services_range)

        return list(set(allowed_ips))  # Remove duplicates

    async def generate_wireguard_config(
        self,
        peer_id: str,
        private_key: str,  # Decrypted private key
    ) -> str:
        """Generate standard WireGuard INI configuration."""
        peer = await self.get_peer_with_relations(peer_id)
        if not peer:
            raise ValueError(f"Peer {peer_id} not found")

        all_peers = await self.get_wan_peers(peer.wan_id)

        config_lines = [
            f"# WAN-Overlay-Manager Configuration",
            f"# Peer: {peer.name}",
            f"# Generated: {datetime.utcnow().isoformat()}",
            "",
            "[Interface]",
            f"PrivateKey = {private_key}",
        ]

        # Add addresses
        addresses = [f"{peer.tunnel_ip}/32"]
        for service in peer.published_services:
            if service.is_active:
                addresses.append(f"{service.shared_ip}/32")
        config_lines.append(f"Address = {', '.join(addresses)}")

        if peer.listen_port:
            config_lines.append(f"ListenPort = {peer.listen_port}")

        config_lines.append("")

        # Generate peer sections for other peers
        route_all = self._should_route_all_traffic(peer)
        for other_peer in all_peers:
            if other_peer.id == peer.id:
                continue

            if not other_peer.public_key:
                continue

            config_lines.append(f"# Peer: {other_peer.name}")
            config_lines.append("[Peer]")
            config_lines.append(f"PublicKey = {other_peer.public_key}")

            if other_peer.endpoint:
                config_lines.append(f"Endpoint = {other_peer.endpoint}")

            # Calculate AllowedIPs for this specific peer connection
            allowed_ips = []
            if other_peer.tunnel_ip:
                allowed_ips.append(f"{other_peer.tunnel_ip}/32")

            if route_all and other_peer.endpoint:
                allowed_ips.append("0.0.0.0/0")

            for subnet in other_peer.local_subnets:
                if subnet.is_routed:
                    if subnet.nat_enabled and subnet.nat_translated_cidr:
                        allowed_ips.append(subnet.nat_translated_cidr)
                    else:
                        allowed_ips.append(subnet.cidr)

            for service in other_peer.published_services:
                if service.is_active:
                    allowed_ips.append(f"{service.shared_ip}/32")

            # Add shared services range
            allowed_ips.append(peer.wan.shared_services_range)

            config_lines.append(f"AllowedIPs = {', '.join(set(allowed_ips))}")

            if peer.persistent_keepalive:
                config_lines.append(f"PersistentKeepalive = {peer.persistent_keepalive}")

            config_lines.append("")

        return "\n".join(config_lines)

    async def generate_mikrotik_script(
        self,
        peer_id: str,
        private_key: str,  # Decrypted private key
    ) -> str:
        """Generate MikroTik RouterOS script."""
        peer = await self.get_peer_with_relations(peer_id)
        if not peer:
            raise ValueError(f"Peer {peer_id} not found")

        all_peers = await self.get_wan_peers(peer.wan_id)
        interface_name = peer.mikrotik_interface_name or "wg-wan-overlay"
        config_uuid = str(uuid.uuid4())[:8]

        lines = [
            f"# WAN-Overlay-Manager: {peer.name}",
            f"# Configuration ID: {config_uuid}",
            f"# Generated: {datetime.utcnow().isoformat()}",
            "",
            "# IMPORTANT: Review this script before applying",
            "# This script is designed to be non-destructive",
            "",
            "# Step 1: Create Wireguard interface if not exists",
            "/interface wireguard",
            f':if ([:len [find name="{interface_name}"]] = 0) do={{',
            f'  add name={interface_name} listen-port={peer.listen_port or 51820} private-key="{private_key}" \\',
            f'      comment="{self.COMMENT_PREFIX}{peer.id}"',
            "} else={",
            f'  set [find name="{interface_name}"] listen-port={peer.listen_port or 51820} private-key="{private_key}"',
            "}",
            "",
            "# Step 2: Remove old peers managed by this system",
            "/interface wireguard peers",
            f':foreach peer in=[find comment~"{self.COMMENT_PREFIX}"] do={{',
            "  remove $peer",
            "}",
            "",
            "# Step 3: Add Wireguard peers",
            "/interface wireguard peers",
        ]

        for other_peer in all_peers:
            if other_peer.id == peer.id:
                continue

            if not other_peer.public_key:
                continue

            allowed_ips = []
            if other_peer.tunnel_ip:
                allowed_ips.append(f"{other_peer.tunnel_ip}/32")

            for subnet in other_peer.local_subnets:
                if subnet.is_routed:
                    if subnet.nat_enabled and subnet.nat_translated_cidr:
                        allowed_ips.append(subnet.nat_translated_cidr)
                    else:
                        allowed_ips.append(subnet.cidr)

            for service in other_peer.published_services:
                if service.is_active:
                    allowed_ips.append(f"{service.shared_ip}/32")

            allowed_ips.append(peer.wan.shared_services_range)

            endpoint_parts = other_peer.endpoint.split(":") if other_peer.endpoint else [None, None]
            endpoint_ip = endpoint_parts[0] if endpoint_parts[0] else ""
            endpoint_port = endpoint_parts[1] if len(endpoint_parts) > 1 else "51820"

            lines.append(f'add interface={interface_name} public-key="{other_peer.public_key}" \\')
            if endpoint_ip:
                lines.append(f'    endpoint-address={endpoint_ip} endpoint-port={endpoint_port} \\')
            lines.append(f'    allowed-address={",".join(set(allowed_ips))} \\')
            keepalive = other_peer.persistent_keepalive or 25
            lines.append(f'    persistent-keepalive={keepalive}s comment="{self.COMMENT_PREFIX}peer-{other_peer.id}"')

        lines.extend([
            "",
            "# Step 4: Configure IP addressing",
            "/ip address",
            f':if ([:len [find address="{peer.tunnel_ip}/24" interface="{interface_name}"]] = 0) do={{',
            f'  add address={peer.tunnel_ip}/24 interface={interface_name} \\',
            f'      comment="{self.COMMENT_PREFIX}{peer.id}"',
            "}",
            "",
            "# Step 5: Remove old routes managed by this system",
            "/ip route",
            f':foreach route in=[find comment~"{self.COMMENT_PREFIX}"] do={{',
            "  remove $route",
            "}",
            "",
            "# Step 6: Add routes for remote networks",
            "/ip route",
        ])

        # Add routes for remote subnets
        for other_peer in all_peers:
            if other_peer.id == peer.id:
                continue

            for subnet in other_peer.local_subnets:
                if subnet.is_routed:
                    dest = subnet.nat_translated_cidr if subnet.nat_enabled and subnet.nat_translated_cidr else subnet.cidr
                    lines.append(
                        f'add dst-address={dest} gateway={interface_name} \\',
                    )
                    lines.append(f'    comment="{self.COMMENT_PREFIX}route-to-{other_peer.id}"')

        # Add route for shared services
        lines.append(
            f'add dst-address={peer.wan.shared_services_range} gateway={interface_name} \\',
        )
        lines.append(f'    comment="{self.COMMENT_PREFIX}route-shared-services-{peer.id}"')

        lines.extend([
            "",
            "# Step 7: Remove old firewall rules managed by this system",
            "/ip firewall filter",
            f':foreach rule in=[find comment~"{self.COMMENT_PREFIX}"] do={{',
            "  remove $rule",
            "}",
            "",
            "# Step 8: Add firewall rules to allow forwarding",
            "/ip firewall filter",
            f'add chain=input in-interface={interface_name} action=accept \\',
            f'    comment="{self.COMMENT_PREFIX}allow-input-wan-{peer.id}"',
            f'add chain=forward in-interface={interface_name} action=accept \\',
            f'    place-before=0 comment="{self.COMMENT_PREFIX}allow-from-wan-{peer.id}"',
            f'add chain=forward out-interface={interface_name} action=accept \\',
            f'    place-before=1 comment="{self.COMMENT_PREFIX}allow-to-wan-{peer.id}"',
        ])

        # Add NAT rules for published services
        if peer.published_services:
            lines.extend([
                "",
                "# Step 9: Remove old NAT rules managed by this system",
                "/ip firewall nat",
                f':foreach rule in=[find comment~"{self.COMMENT_PREFIX}"] do={{',
                "  remove $rule",
                "}",
                "",
                "# Step 10: NAT rules for published services",
                "/ip firewall nat",
            ])

            for service in peer.published_services:
                if service.is_active:
                    protocols = ["tcp", "udp"] if service.protocol.value == "both" else [service.protocol.value]
                    for proto in protocols:
                        lines.append(
                            f'add chain=dstnat dst-address={service.shared_ip} protocol={proto} \\'
                        )
                        dst_port_clause = f'dst-port={service.shared_port} ' if service.shared_port and service.shared_port > 0 else ''
                        to_ports_clause = f'to-ports={service.local_port} ' if service.local_port and service.local_port > 0 else ''
                        lines.append(
                            f'    {dst_port_clause}action=dst-nat to-addresses={service.local_ip} {to_ports_clause}\\'
                        )
                        lines.append(
                            f'    comment="{self.COMMENT_PREFIX}service-{service.id}"'
                        )

                        # Add source NAT for return traffic
                        lines.append(
                            f'add chain=srcnat src-address={service.local_ip} out-interface={interface_name} \\'
                        )
                        lines.append(
                            f'    action=src-nat to-addresses={service.shared_ip} \\'
                        )
                        lines.append(
                            f'    comment="{self.COMMENT_PREFIX}service-{service.id}-srcnat"'
                        )

        lines.extend([
            "",
            '# Verification commands',
            ':put "Configuration applied. Verifying..."',
            "/interface wireguard print",
            "/interface wireguard peers print",
            ':put "Check peer handshakes above. Recent timestamps indicate successful connection."',
        ])

        return "\n".join(lines)

    async def get_mikrotik_desired_state(
        self,
        peer_id: str,
        private_key: str,
    ) -> Dict:
        """Get the desired MikroTik configuration state for API deployment."""
        peer = await self.get_peer_with_relations(peer_id)
        if not peer:
            raise ValueError(f"Peer {peer_id} not found")

        all_peers = await self.get_wan_peers(peer.wan_id)
        interface_name = peer.mikrotik_interface_name or "wg-wan-overlay"

        state = {
            "interface": {
                "name": interface_name,
                "listen-port": peer.listen_port or 51820,
                "private-key": private_key,
                "comment": f"{self.COMMENT_PREFIX}peer-{peer.id}",
            },
            "peers": [],
            "ip_addresses": [
                {
                    "address": f"{peer.tunnel_ip}/24",
                    "interface": interface_name,
                    "comment": f"{self.COMMENT_PREFIX}peer-{peer.id}",
                }
            ],
            "routes": [],
            "firewall_rules": [
                {
                    "chain": "input",
                    "in-interface": interface_name,
                    "action": "accept",
                    "comment": f"{self.COMMENT_PREFIX}allow-input-wan-{peer.id}",
                },
                {
                    "chain": "forward",
                    "in-interface": interface_name,
                    "action": "accept",
                    "comment": f"{self.COMMENT_PREFIX}allow-from-wan-{peer.id}",
                },
                {
                    "chain": "forward",
                    "out-interface": interface_name,
                    "action": "accept",
                    "comment": f"{self.COMMENT_PREFIX}allow-to-wan-{peer.id}",
                },
            ],
            "nat_rules": [],
        }

        # Add peers
        for other_peer in all_peers:
            if other_peer.id == peer.id or not other_peer.public_key:
                continue

            allowed_ips = []
            if other_peer.tunnel_ip:
                allowed_ips.append(f"{other_peer.tunnel_ip}/32")

            for subnet in other_peer.local_subnets:
                if subnet.is_routed:
                    cidr = subnet.nat_translated_cidr if subnet.nat_enabled and subnet.nat_translated_cidr else subnet.cidr
                    allowed_ips.append(cidr)

            for service in other_peer.published_services:
                if service.is_active:
                    allowed_ips.append(f"{service.shared_ip}/32")

            allowed_ips.append(peer.wan.shared_services_range)

            keepalive = other_peer.persistent_keepalive or 25
            peer_config = {
                "interface": interface_name,
                "public-key": other_peer.public_key,
                "allowed-address": ",".join(set(allowed_ips)),
                "persistent-keepalive": f"{keepalive}s",
                "comment": f"{self.COMMENT_PREFIX}peer-{other_peer.id}",
            }

            if other_peer.endpoint:
                parts = other_peer.endpoint.split(":")
                peer_config["endpoint-address"] = parts[0]
                peer_config["endpoint-port"] = parts[1] if len(parts) > 1 else "51820"

            state["peers"].append(peer_config)

        # Add routes
        for other_peer in all_peers:
            if other_peer.id == peer.id:
                continue

            for subnet in other_peer.local_subnets:
                if subnet.is_routed:
                    cidr = subnet.nat_translated_cidr if subnet.nat_enabled and subnet.nat_translated_cidr else subnet.cidr
                    state["routes"].append({
                        "dst-address": cidr,
                        "gateway": interface_name,
                        "comment": f"{self.COMMENT_PREFIX}route-to-{other_peer.id}",
                    })

        # Shared services route
        state["routes"].append({
            "dst-address": peer.wan.shared_services_range,
            "gateway": interface_name,
            "comment": f"{self.COMMENT_PREFIX}route-shared-services-{peer.id}",
        })

        # Add NAT rules for published services
        for service in peer.published_services:
            if service.is_active:
                protocols = (
                    ["tcp", "udp"] if service.protocol.value == "both" else [service.protocol.value]
                )
                for proto in protocols:
                    rule = {
                        "chain": "dstnat",
                        "dst-address": service.shared_ip,
                        "protocol": proto,
                        "action": "dst-nat",
                        "to-addresses": service.local_ip,
                        "comment": f"{self.COMMENT_PREFIX}service-{service.id}",
                    }
                    if service.shared_port and service.shared_port > 0:
                        rule["dst-port"] = str(service.shared_port)
                    if service.local_port and service.local_port > 0:
                        rule["to-ports"] = str(service.local_port)
                    state["nat_rules"].append(rule)

        return state
