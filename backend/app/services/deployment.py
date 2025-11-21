import asyncio
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.peer import Peer, PeerType, MikrotikApiStatus
from app.models.deployment import DeploymentJob, JobType, JobStatus
from app.models.api_log import MikrotikApiCallLog, HttpMethod
from app.services.mikrotik_client import MikrotikAPIClient, MikrotikAPIError
from app.services.config_generator import ConfigGeneratorService
from app.services.conflict_detection import ConflictDetectionService
from app.core.security import decrypt_value
from app.core.config import settings


class DeploymentService:
    """Service for deploying configurations to MikroTik routers."""

    COMMENT_PREFIX = "WAN-Overlay-Manager:"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_peer(self, peer_id: str) -> Optional[Peer]:
        """Get peer with all related data."""
        result = await self.db.execute(
            select(Peer)
            .options(
                selectinload(Peer.wan),
                selectinload(Peer.local_subnets),
                selectinload(Peer.published_services),
                selectinload(Peer.config_history),
            )
            .where(Peer.id == peer_id)
        )
        return result.scalar_one_or_none()

    def _get_mikrotik_client(self, peer: Peer) -> MikrotikAPIClient:
        """Create MikroTik API client for a peer."""
        password = None
        api_token = None

        if peer.mikrotik_password_encrypted:
            try:
                password = decrypt_value(peer.mikrotik_password_encrypted)
            except Exception:
                raise ValueError("Cannot decrypt stored password. Please update the MikroTik credentials.")
        if peer.mikrotik_api_token_encrypted:
            try:
                api_token = decrypt_value(peer.mikrotik_api_token_encrypted)
            except Exception:
                raise ValueError("Cannot decrypt stored API token. Please update the MikroTik credentials.")

        return MikrotikAPIClient(
            host=peer.mikrotik_management_ip,
            port=peer.mikrotik_api_port or 8728,
            username=peer.mikrotik_username,
            password=password,
            api_token=api_token,
            auth_method=peer.mikrotik_auth_method,
            use_ssl=peer.mikrotik_use_ssl,
            verify_cert=peer.mikrotik_verify_cert,
        )

    async def plan_configuration(self, peer_id: str) -> Dict[str, Any]:
        """Return a plan/preview of changes without applying them."""
        peer = await self.get_peer(peer_id)
        if not peer:
            raise ValueError("Peer not found")
        if peer.type != PeerType.MIKROTIK:
            raise ValueError("Peer is not a MikroTik device")

        client = self._get_mikrotik_client(peer)
        desired_state = ConfigGeneratorService(self.db)
        private_key = decrypt_value(peer.private_key_encrypted) if peer.private_key_encrypted else ""
        desired = await desired_state.get_mikrotik_desired_state(peer_id, private_key)
        current = await client.get_managed_resources()

        def summarize(kind: str, desired_items: List[Dict], current_items: List[Dict]) -> Dict[str, int]:
            desired_comments = {item.get("comment") for item in desired_items if item.get("comment")}
            current_comments = {item.get("comment") for item in current_items if item.get("comment")}
            return {
                "to_create": len(desired_comments - current_comments),
                "to_delete": len(current_comments - desired_comments),
                "managed_current": len(current_comments),
                "managed_desired": len(desired_comments),
                "kind": kind,
            }

        plan = {
            "interface": desired.get("interface", {}),
            "summary": {
                "ips": summarize("ip_addresses", desired.get("ip_addresses", []), current.get("ip_addresses", [])),
                "routes": summarize("routes", desired.get("routes", []), current.get("routes", [])),
                "firewall": summarize("firewall_rules", desired.get("firewall_rules", []), current.get("firewall_filter_rules", [])),
                "nat": summarize("nat_rules", desired.get("nat_rules", []), current.get("nat_rules", [])),
                "peers": summarize("peers", desired.get("peers", []), current.get("wireguard_peers", [])),
            },
        }
        return plan

    async def test_connection(self, peer_id: str) -> Dict[str, Any]:
        """Test MikroTik API connection."""
        peer = await self.get_peer(peer_id)
        if not peer:
            return {"success": False, "error_message": "Peer not found"}

        if peer.type != PeerType.MIKROTIK:
            return {"success": False, "error_message": "Peer is not a MikroTik device"}

        try:
            client = self._get_mikrotik_client(peer)
        except ValueError as e:
            return {"success": False, "error_message": str(e)}

        result = await client.test_connection()

        # Update peer status
        peer.mikrotik_last_api_check = datetime.utcnow()
        if result.success:
            peer.mikrotik_api_status = MikrotikApiStatus.CONNECTED
            peer.mikrotik_router_identity = result.router_identity
            peer.mikrotik_routeros_version = result.routeros_version
            peer.is_online = True
            peer.last_seen = datetime.utcnow()
        else:
            if "auth" in (result.error_message or "").lower():
                peer.mikrotik_api_status = MikrotikApiStatus.AUTH_FAILED
            else:
                peer.mikrotik_api_status = MikrotikApiStatus.UNREACHABLE
            peer.is_online = False

        await self.db.commit()

        return {
            "success": result.success,
            "router_identity": result.router_identity,
            "routeros_version": result.routeros_version,
            "error_message": result.error_message,
        }

    async def apply_raw_mikrotik_config(self, peer_id: str, config_text: str) -> None:
        """Apply a raw MikroTik config (script) to the router."""
        peer = await self.get_peer(peer_id)
        if not peer:
            raise ValueError("Peer not found")
        if peer.type != PeerType.MIKROTIK:
            raise ValueError("Peer is not a MikroTik device")

        client = self._get_mikrotik_client(peer)
        # Use the script via API (RouterOS import)
        await client.run_script(config_text)

    async def clear_managed_configuration(self, peer_id: str) -> None:
        """Remove all WireWAN-managed resources from the MikroTik."""
        peer = await self.get_peer(peer_id)
        if not peer:
            raise ValueError("Peer not found")
        if peer.type != PeerType.MIKROTIK:
            raise ValueError("Peer is not a MikroTik device")

        client = self._get_mikrotik_client(peer)
        await client.remove_managed_resources()

    async def preflight_check(self, peer_id: str) -> Dict[str, Any]:
        """Check for potential conflicts on the router before deploying."""
        peer = await self.get_peer(peer_id)
        if not peer:
            return {"success": False, "issues": ["Peer not found"]}

        if peer.type != PeerType.MIKROTIK:
            return {"success": False, "issues": ["Peer is not a MikroTik device"]}

        client = self._get_mikrotik_client(peer)

        interface_name = peer.mikrotik_interface_name or "wg-wan-overlay"
        desired_port = peer.listen_port or 51820
        desired_state = ConfigGeneratorService(self.db)
        private_key = decrypt_value(peer.private_key_encrypted) if peer.private_key_encrypted else ""
        desired = await desired_state.get_mikrotik_desired_state(peer_id, private_key)

        issues: List[Dict[str, Any]] = []

        # Fetch current router state (unfiltered to spot conflicts)
        existing_interfaces = await client.get_wireguard_interfaces()
        existing_addresses = await client.get_ip_addresses()
        existing_routes = await client.get_routes()
        existing_firewall = await client.get_firewall_filter_rules()
        existing_nat = await client.get_nat_rules()
        try:
            conflict_service = ConflictDetectionService(self.db)
            overlaps = await conflict_service.detect_conflicts(
                peer.wan_id,
                peer.id,
                [r.get("dst-address") for r in desired.get("routes", []) if r.get("dst-address")],
                existing_routes=[r.get("dst-address") for r in existing_routes if r.get("dst-address")],
            )
            for c in overlaps:
                issues.append({
                    "type": c.conflict_type,
                    "description": c.description,
                    "suggestions": [s.value for s in c.suggested_resolutions],
                })
        except Exception:
            # best-effort; don't hard fail preflight on conflict check errors
            pass

        # Interface name clash
        for iface in existing_interfaces:
            if iface.get("name") == interface_name and not str(iface.get("comment", "")).startswith(self.COMMENT_PREFIX):
                issues.append({
                    "type": "interface-name",
                    "description": f"Interface '{interface_name}' already exists and is not managed by WireWAN.",
                    "suggestions": [
                        "Remove/rename the interface manually",
                        "Change the interface name in peer settings before deploying"
                    ],
                })
                break

        # Port clash
        for iface in existing_interfaces:
            if iface.get("listen-port") == desired_port and iface.get("name") != interface_name:
                issues.append({
                    "type": "listen-port",
                    "description": f"WireGuard listen port {desired_port} is already used by '{iface.get('name')}'.",
                    "suggestions": [
                        "Change listen port on this peer",
                        "Update or remove the conflicting interface on the router"
                    ],
                })
                break

        desired_ip_addresses = {addr["address"] for addr in desired.get("ip_addresses", [])}
        for addr in existing_addresses:
            if addr.get("address") in desired_ip_addresses and not str(addr.get("comment", "")).startswith(self.COMMENT_PREFIX):
                issues.append({
                    "type": "ip-address",
                    "description": f"IP {addr.get('address')} already exists on interface {addr.get('interface')} (not managed).",
                    "suggestions": [
                        "Remove or change the existing address",
                        "Adjust the peer tunnel IP or subnet"
                    ],
                })

        desired_route_dsts = {route["dst-address"] for route in desired.get("routes", [])}
        for route in existing_routes:
            if route.get("dst-address") in desired_route_dsts and not str(route.get("comment", "")).startswith(self.COMMENT_PREFIX):
                issues.append({
                    "type": "route",
                    "description": f"Route {route.get('dst-address')} already exists (not managed by WireWAN).",
                    "suggestions": [
                        "Remove or adjust the conflicting route",
                        "Change the managed route destinations"
                    ],
                })

        desired_nat = {(nat["chain"], nat.get("dst-address"), nat.get("dst-port")) for nat in desired.get("nat_rules", [])}
        for nat in existing_nat:
            key = (nat.get("chain"), nat.get("dst-address"), nat.get("dst-port"))
            if key in desired_nat and not str(nat.get("comment", "")).startswith(self.COMMENT_PREFIX):
                issues.append({
                    "type": "nat",
                    "description": f"NAT rule for chain {nat.get('chain')} dst {nat.get('dst-address')}:{nat.get('dst-port')} already exists (not managed).",
                    "suggestions": [
                        "Remove or adjust the existing NAT rule",
                        "Change the peer's NAT configuration"
                    ],
                })

        desired_fw = {(rule["chain"], rule["action"], rule.get("in-interface"), rule.get("out-interface")) for rule in desired.get("firewall_rules", [])}
        for rule in existing_firewall:
            key = (rule.get("chain"), rule.get("action"), rule.get("in-interface"), rule.get("out-interface"))
            if key in desired_fw and not str(rule.get("comment", "")).startswith(self.COMMENT_PREFIX):
                issues.append({
                    "type": "firewall",
                    "description": f"Firewall rule in chain {rule.get('chain')} already exists (not managed).",
                    "suggestions": [
                        "Remove/disable the existing rule",
                        "Adjust peer firewall settings"
                    ],
                })

        return {
            "success": len(issues) == 0,
            "issues": issues,
        }

    async def verify_configuration(self, peer_id: str) -> Dict[str, Any]:
        """Compare desired config vs what is deployed under WireWAN-managed comments."""
        peer = await self.get_peer(peer_id)
        if not peer:
            return {"in_sync": False, "issues": ["Peer not found"]}

        if peer.type != PeerType.MIKROTIK:
            return {"in_sync": False, "issues": ["Peer is not a MikroTik device"]}

        client = self._get_mikrotik_client(peer)
        desired_state = ConfigGeneratorService(self.db)
        private_key = decrypt_value(peer.private_key_encrypted) if peer.private_key_encrypted else ""
        desired = await desired_state.get_mikrotik_desired_state(peer_id, private_key)
        current = await client.get_managed_resources()

        issues: List[str] = []

        interface_name = desired["interface"]["name"]
        interface_match = any(
            iface.get("name") == interface_name for iface in current.get("wireguard_interfaces", [])
        )
        if not interface_match:
            issues.append(f"Managed interface '{interface_name}' is missing.")

        def _check_missing(set_desired, current_items, field):
            missing = []
            current_values = {item.get(field) for item in current_items}
            for value in set_desired:
                if value not in current_values:
                    missing.append(value)
            return missing

        desired_ips = {addr["address"] for addr in desired.get("ip_addresses", [])}
        missing_ips = _check_missing(desired_ips, current.get("ip_addresses", []), "address")
        if missing_ips:
            issues.append(f"Missing IP addresses: {', '.join(missing_ips)}")

        desired_routes = {route["dst-address"] for route in desired.get("routes", [])}
        missing_routes = _check_missing(desired_routes, current.get("routes", []), "dst-address")
        if missing_routes:
            issues.append(f"Missing routes: {', '.join(missing_routes)}")

        desired_fw_comments = {rule["comment"] for rule in desired.get("firewall_rules", []) if rule.get("comment")}
        missing_fw = _check_missing(desired_fw_comments, current.get("firewall_filter_rules", []), "comment")
        if missing_fw:
            issues.append(f"Missing firewall rules: {', '.join(missing_fw)}")

        desired_nat_comments = {rule["comment"] for rule in desired.get("nat_rules", []) if rule.get("comment")}
        missing_nat = _check_missing(desired_nat_comments, current.get("nat_rules", []), "comment")
        if missing_nat:
            issues.append(f"Missing NAT rules: {', '.join(missing_nat)}")

        desired_peer_comments = {peer_cfg["comment"] for peer_cfg in desired.get("peers", []) if peer_cfg.get("comment")}
        missing_peers = _check_missing(desired_peer_comments, current.get("wireguard_peers", []), "comment")
        if missing_peers:
            issues.append(f"Missing peer entries: {', '.join(missing_peers)}")

        # Drift checks on matching comments
        def _index_by_comment(items):
            return {item.get("comment"): item for item in items if item.get("comment")}

        # Firewall rule drift
        desired_fw_index = _index_by_comment(desired.get("firewall_rules", []))
        current_fw_index = _index_by_comment(current.get("firewall_filter_rules", []))
        for comment, rule in desired_fw_index.items():
            cur = current_fw_index.get(comment)
            if not cur:
                continue
            for field in ["chain", "action", "in-interface", "out-interface"]:
                if str(rule.get(field)) != str(cur.get(field)):
                    issues.append(f"Firewall rule {comment} differs on {field}: desired {rule.get(field)}, found {cur.get(field)}")

        # NAT drift
        desired_nat_index = _index_by_comment(desired.get("nat_rules", []))
        current_nat_index = _index_by_comment(current.get("nat_rules", []))
        for comment, rule in desired_nat_index.items():
            cur = current_nat_index.get(comment)
            if not cur:
                continue
            for field in ["chain", "protocol", "dst-address", "dst-port", "action", "to-addresses", "to-ports"]:
                if str(rule.get(field)) != str(cur.get(field)):
                    issues.append(f"NAT rule {comment} differs on {field}: desired {rule.get(field)}, found {cur.get(field)}")

        # Route drift
        desired_route_index = _index_by_comment(desired.get("routes", []))
        current_route_index = _index_by_comment(current.get("routes", []))
        for comment, rule in desired_route_index.items():
            cur = current_route_index.get(comment)
            if not cur:
                continue
            for field in ["dst-address", "gateway"]:
                if str(rule.get(field)) != str(cur.get(field)):
                    issues.append(f"Route {comment} differs on {field}: desired {rule.get(field)}, found {cur.get(field)}")

        return {
            "in_sync": len(issues) == 0,
            "issues": issues,
            "current": current,
        }

    async def create_deployment_job(
        self,
        peer_id: str,
        job_type: JobType,
        created_by_id: Optional[str] = None,
    ) -> DeploymentJob:
        """Create a new deployment job."""
        job = DeploymentJob(
            id=str(uuid.uuid4()),
            peer_id=peer_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            progress_percent=0,
            created_by_id=created_by_id,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def _log_api_call(
        self,
        job_id: str,
        peer_id: str,
        method: HttpMethod,
        endpoint: str,
        request_body: Optional[Dict],
        response_status: int,
        response_body: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> MikrotikApiCallLog:
        """Log an API call."""
        log = MikrotikApiCallLog(
            id=str(uuid.uuid4()),
            deployment_job_id=job_id,
            peer_id=peer_id,
            method=method,
            endpoint=endpoint,
            request_body=request_body,
            response_status=response_status,
            response_body=response_body,
            error_message=error_message,
        )
        self.db.add(log)
        return log

    async def deploy_configuration(
        self,
        peer_id: str,
        created_by_id: Optional[str] = None,
    ) -> DeploymentJob:
        """Deploy configuration to a MikroTik router."""
        peer = await self.get_peer(peer_id)
        if not peer:
            raise ValueError("Peer not found")

        if peer.type != PeerType.MIKROTIK:
            raise ValueError("Peer is not a MikroTik device")

        # Create deployment job
        job = await self.create_deployment_job(
            peer_id=peer_id,
            job_type=JobType.DEPLOY_CONFIG,
            created_by_id=created_by_id,
        )

        # Run deployment in background
        asyncio.create_task(self._execute_deployment(job.id, peer_id))

        return job

    async def _execute_deployment(self, job_id: str, peer_id: str):
        """Execute the deployment (runs as background task)."""
        # Get fresh database session for background task
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            try:
                # Get job and peer
                job_result = await db.execute(
                    select(DeploymentJob).where(DeploymentJob.id == job_id)
                )
                job = job_result.scalar_one()

                peer_result = await db.execute(
                    select(Peer)
                    .options(
                        selectinload(Peer.wan),
                        selectinload(Peer.local_subnets),
                        selectinload(Peer.published_services),
                    )
                    .where(Peer.id == peer_id)
                )
                peer = peer_result.scalar_one()

                # Update job status
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()
                job.progress_percent = 5
                await db.commit()

                # Get MikroTik client
                password = None
                api_token = None
                if peer.mikrotik_password_encrypted:
                    password = decrypt_value(peer.mikrotik_password_encrypted)
                if peer.mikrotik_api_token_encrypted:
                    api_token = decrypt_value(peer.mikrotik_api_token_encrypted)

                client = MikrotikAPIClient(
                    host=peer.mikrotik_management_ip,
                    port=peer.mikrotik_api_port or 443,
                    username=peer.mikrotik_username,
                    password=password,
                    api_token=api_token,
                    auth_method=peer.mikrotik_auth_method,
                    use_ssl=peer.mikrotik_use_ssl,
                    verify_cert=peer.mikrotik_verify_cert,
                )

                # Test connection first
                conn_result = await client.test_connection()
                if not conn_result.success:
                    raise MikrotikAPIError(f"Connection test failed: {conn_result.error_message}")

                job.progress_percent = 10
                await db.commit()

                # Get desired state
                config_gen = ConfigGeneratorService(db)
                private_key = decrypt_value(peer.private_key_encrypted) if peer.private_key_encrypted else ""
                desired_state = await config_gen.get_mikrotik_desired_state(peer_id, private_key)

                job.progress_percent = 15
                await db.commit()

                # Get current managed resources for backup
                current_resources = await client.get_managed_resources()
                job.backup_config = current_resources
                job.progress_percent = 20
                await db.commit()

                interface_name = peer.mikrotik_interface_name or "wg-wan-overlay"

                # Step 1: Create/update Wireguard interface (20-30%)
                existing_interfaces = await client.get_wireguard_interfaces()
                interface_exists = any(iface.get("name") == interface_name for iface in existing_interfaces)

                if interface_exists:
                    # Find interface ID and update
                    for iface in existing_interfaces:
                        if iface.get("name") == interface_name:
                            await client.update_wireguard_interface(
                                iface[".id"],
                                {
                                    "listen-port": desired_state["interface"]["listen-port"],
                                    "private-key": desired_state["interface"]["private-key"],
                                    "comment": desired_state["interface"]["comment"],
                                }
                            )
                            break
                else:
                    await client.create_wireguard_interface(
                        name=interface_name,
                        listen_port=desired_state["interface"]["listen-port"],
                        private_key=desired_state["interface"]["private-key"],
                        comment=desired_state["interface"]["comment"],
                    )

                job.progress_percent = 30
                await db.commit()

                # Step 2: Remove old peers and add new ones (30-50%)
                existing_peers = await client.get_wireguard_peers(interface=interface_name)
                for ep in existing_peers:
                    comment = ep.get("comment", "")
                    if comment and comment.startswith(self.COMMENT_PREFIX):
                        await client.delete_wireguard_peer(ep[".id"])

                job.progress_percent = 40
                await db.commit()

                for peer_config in desired_state["peers"]:
                    await client.create_wireguard_peer(
                        interface=peer_config["interface"],
                        public_key=peer_config["public-key"],
                        allowed_address=peer_config["allowed-address"],
                        endpoint_address=peer_config.get("endpoint-address"),
                        endpoint_port=peer_config.get("endpoint-port"),
                        persistent_keepalive=peer_config.get("persistent-keepalive"),
                        comment=peer_config["comment"],
                    )

                job.progress_percent = 50
                await db.commit()

                # Step 3: Configure IP addresses (50-60%)
                existing_addrs = await client.get_ip_addresses(interface=interface_name)
                for addr in existing_addrs:
                    comment = addr.get("comment", "")
                    if comment and comment.startswith(self.COMMENT_PREFIX):
                        await client.delete_ip_address(addr[".id"])

                for addr_config in desired_state["ip_addresses"]:
                    await client.create_ip_address(
                        address=addr_config["address"],
                        interface=addr_config["interface"],
                        comment=addr_config["comment"],
                    )

                job.progress_percent = 60
                await db.commit()

                # Step 4: Configure routes (60-70%)
                existing_routes = await client.get_routes()
                for route in existing_routes:
                    comment = route.get("comment", "")
                    if comment and comment.startswith(self.COMMENT_PREFIX):
                        await client.delete_route(route[".id"])

                for route_config in desired_state["routes"]:
                    await client.create_route(
                        dst_address=route_config["dst-address"],
                        gateway=route_config["gateway"],
                        comment=route_config["comment"],
                    )

                job.progress_percent = 70
                await db.commit()

                # Step 5: Configure firewall rules (70-80%)
                existing_rules = await client.get_firewall_filter_rules()
                for rule in existing_rules:
                    comment = rule.get("comment", "")
                    if comment and comment.startswith(self.COMMENT_PREFIX):
                        await client.delete_firewall_filter_rule(rule[".id"])

                for rule_config in desired_state["firewall_rules"]:
                    await client.create_firewall_filter_rule(
                        chain=rule_config["chain"],
                        action=rule_config["action"],
                        in_interface=rule_config.get("in-interface"),
                        out_interface=rule_config.get("out-interface"),
                        comment=rule_config["comment"],
                    )

                job.progress_percent = 80
                await db.commit()

                # Step 6: Configure NAT rules (80-90%)
                existing_nat = await client.get_nat_rules()
                for rule in existing_nat:
                    comment = rule.get("comment", "")
                    if comment and comment.startswith(self.COMMENT_PREFIX):
                        await client.delete_nat_rule(rule[".id"])

                for nat_config in desired_state["nat_rules"]:
                    await client.create_nat_rule(
                        chain=nat_config["chain"],
                        action=nat_config["action"],
                        dst_address=nat_config.get("dst-address"),
                        protocol=nat_config.get("protocol"),
                        dst_port=nat_config.get("dst-port"),
                        to_addresses=nat_config.get("to-addresses"),
                        to_ports=nat_config.get("to-ports"),
                        comment=nat_config["comment"],
                    )

                job.progress_percent = 90
                await db.commit()

                # Step 7: Verify deployment (90-100%)
                # Check interface is running
                interfaces = await client.get_wireguard_interfaces()
                interface_running = any(
                    iface.get("name") == interface_name and iface.get("running", False)
                    for iface in interfaces
                )

                job.progress_percent = 100
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()

                if not interface_running:
                    job.operations_log = [{"warning": "Interface created but may not be running"}]

                # Update peer status
                peer.mikrotik_api_status = MikrotikApiStatus.CONNECTED
                peer.mikrotik_last_api_check = datetime.utcnow()
                peer.is_online = True
                peer.last_seen = datetime.utcnow()

                await db.commit()
            except MikrotikAPIError as e:
                job.status = JobStatus.FAILED
                msg = f"{e.message}: {e.detail}" if e.detail else e.message
                job.error_message = msg
                job.completed_at = datetime.utcnow()
                await db.commit()

            except Exception as e:
                job.status = JobStatus.FAILED
                job.error_message = str(e) if str(e) else f"Unexpected error ({type(e).__name__})"
                job.operations_log = (job.operations_log or []) + [{"traceback": traceback.format_exc()}]
                job.completed_at = datetime.utcnow()
                await db.commit()

    async def get_job(self, job_id: str) -> Optional[DeploymentJob]:
        """Get a deployment job by ID."""
        result = await self.db.execute(
            select(DeploymentJob)
            .options(selectinload(DeploymentJob.api_call_logs))
            .where(DeploymentJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_peer_jobs(
        self,
        peer_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DeploymentJob]:
        """Get deployment jobs for a peer."""
        result = await self.db.execute(
            select(DeploymentJob)
            .where(DeploymentJob.peer_id == peer_id)
            .order_by(DeploymentJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
