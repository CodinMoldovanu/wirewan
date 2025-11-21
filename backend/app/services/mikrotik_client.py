import ssl
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import librouteros
from librouteros import connect
from librouteros.exceptions import TrapError, ConnectionClosed, ProtocolError

from app.models.peer import MikrotikAuthMethod


class MikrotikAPIError(Exception):
    """Exception raised for MikroTik API errors."""

    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


@dataclass
class MikrotikConnectionInfo:
    success: bool
    router_identity: Optional[str] = None
    routeros_version: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class WireguardInterface:
    id: str
    name: str
    listen_port: int
    private_key: Optional[str]
    public_key: Optional[str]
    running: bool
    comment: Optional[str]


@dataclass
class WireguardPeer:
    id: str
    interface: str
    public_key: str
    endpoint_address: Optional[str]
    endpoint_port: Optional[int]
    allowed_address: str
    persistent_keepalive: Optional[str]
    current_endpoint_address: Optional[str]
    current_endpoint_port: Optional[int]
    last_handshake: Optional[str]
    rx: Optional[int]
    tx: Optional[int]
    comment: Optional[str]


# Thread pool for running sync librouteros calls
_executor = ThreadPoolExecutor(max_workers=10)


class MikrotikAPIClient:
    """Client for MikroTik RouterOS API (native protocol on port 8728/8729)."""

    COMMENT_PREFIX = "WAN-Overlay-Manager:"

    def __init__(
        self,
        host: str,
        port: int = 8728,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_token: Optional[str] = None,
        auth_method: MikrotikAuthMethod = MikrotikAuthMethod.PASSWORD,
        use_ssl: bool = False,
        verify_cert: bool = False,
        timeout: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.username = username or "admin"
        self.password = password or ""
        self.api_token = api_token
        self.auth_method = auth_method
        self.use_ssl = use_ssl
        self.verify_cert = verify_cert
        self.timeout = timeout

    def _get_connection(self) -> librouteros.api.Api:
        """Create a connection to the MikroTik router."""
        try:
            if not self.host:
                raise MikrotikAPIError(
                    "Connection failed",
                    detail="MikroTik management IP/hostname is not configured for this peer.",
                )

            connect_kwargs = {
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "password": self.password,
                "timeout": self.timeout,
            }

            if self.use_ssl:
                ctx = ssl.create_default_context()
                if not self.verify_cert:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                connect_kwargs["ssl_wrapper"] = ctx.wrap_socket
                connect_kwargs["use_ssl"] = True

            api = connect(**connect_kwargs)
            return api
        except librouteros.exceptions.TrapError as e:
            raise MikrotikAPIError(
                "Authentication failed",
                status_code=401,
                detail=str(e)
            )
        except (ConnectionRefusedError, OSError) as e:
            raise MikrotikAPIError(
                "Connection refused",
                detail=f"Cannot connect to {self.host}:{self.port}. Is the API service enabled? Error: {str(e)}"
            )
        except TimeoutError:
            raise MikrotikAPIError(
                "Connection timeout",
                detail=f"Connection to {self.host}:{self.port} timed out"
            )
        except Exception as e:
            raise MikrotikAPIError(
                "Connection failed",
                detail=str(e)
            )

    def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function."""
        return func(*args, **kwargs)

    async def _run_async(self, func, *args, **kwargs):
        """Run a synchronous function in thread pool to avoid blocking."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))

    def _execute_sync(self, path_parts: Tuple[str, ...], command: str = "print", **kwargs) -> List[Dict]:
        """Execute a command synchronously."""
        api = self._get_connection()
        try:
            resource = api.path(*path_parts)
            if command == "print":
                return list(resource)
            elif command == "add":
                result = resource.add(**kwargs)
                return [{"ret": result}]
            elif command == "set":
                resource.update(**kwargs)
                return []
            elif command == "remove":
                resource.remove(kwargs.get(".id"))
                return []
            else:
                raise MikrotikAPIError(f"Unknown command: {command}")
        except TrapError as e:
            raise MikrotikAPIError(
                "API Error",
                detail=str(e)
            )
        except ConnectionClosed as e:
            raise MikrotikAPIError(
                "Connection closed",
                detail=str(e)
            )
        except ProtocolError as e:
            raise MikrotikAPIError(
                "Protocol error",
                detail=str(e)
            )
        finally:
            try:
                api.close()
            except Exception:
                pass

    async def _execute(self, *path_parts: str, command: str = "print", **kwargs) -> List[Dict]:
        """Execute a command asynchronously."""
        return await self._run_async(self._execute_sync, path_parts, command, **kwargs)

    def _test_connection_sync(self) -> MikrotikConnectionInfo:
        """Test API connectivity synchronously."""
        try:
            api = self._get_connection()
            try:
                # Get system identity
                identity_resource = api.path("system", "identity")
                identity_list = list(identity_resource)
                identity = identity_list[0].get("name", "Unknown") if identity_list else "Unknown"

                # Get RouterOS version
                resource_path = api.path("system", "resource")
                resource_list = list(resource_path)
                version = resource_list[0].get("version", "Unknown") if resource_list else "Unknown"

                return MikrotikConnectionInfo(
                    success=True,
                    router_identity=identity,
                    routeros_version=version
                )
            finally:
                try:
                    api.close()
                except Exception:
                    pass
        except MikrotikAPIError as e:
            return MikrotikConnectionInfo(
                success=False,
                error_message=f"{e.message}: {e.detail}"
            )
        except Exception as e:
            return MikrotikConnectionInfo(
                success=False,
                error_message=str(e)
            )

    async def test_connection(self) -> MikrotikConnectionInfo:
        """Test API connectivity and get router info."""
        return await self._run_async(self._test_connection_sync)

    # Wireguard Interface Operations
    async def get_wireguard_interfaces(
        self, comment_filter: Optional[str] = None
    ) -> List[Dict]:
        """Get Wireguard interfaces."""
        result = await self._execute("interface", "wireguard")
        if comment_filter:
            result = [r for r in result if comment_filter in r.get("comment", "")]
        return result

    async def create_wireguard_interface(
        self,
        name: str,
        listen_port: int,
        private_key: str,
        comment: Optional[str] = None,
    ) -> Dict:
        """Create a new Wireguard interface."""
        kwargs = {
            "name": name,
            "listen-port": str(listen_port),
            "private-key": private_key,
        }
        if comment:
            kwargs["comment"] = comment
        result = await self._execute("interface", "wireguard", command="add", **kwargs)
        return result[0] if result else {}

    async def update_wireguard_interface(
        self, interface_id: str, data: Dict
    ) -> Dict:
        """Update an existing Wireguard interface."""
        data[".id"] = interface_id
        # Convert keys from underscore to hyphen format
        converted = {}
        for k, v in data.items():
            if k == ".id":
                converted[k] = v
            else:
                converted[k.replace("_", "-")] = str(v) if v is not None else v
        await self._execute("interface", "wireguard", command="set", **converted)
        return {}

    async def delete_wireguard_interface(self, interface_id: str) -> None:
        """Delete a Wireguard interface."""
        await self._execute("interface", "wireguard", command="remove", **{".id": interface_id})

    # Wireguard Peer Operations
    async def get_wireguard_peers(
        self,
        interface: Optional[str] = None,
        comment_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Get Wireguard peers."""
        result = await self._execute("interface", "wireguard", "peers")
        if interface:
            result = [r for r in result if r.get("interface") == interface]
        if comment_filter:
            result = [r for r in result if comment_filter in r.get("comment", "")]
        return result

    async def create_wireguard_peer(
        self,
        interface: str,
        public_key: str,
        allowed_address: str,
        endpoint_address: Optional[str] = None,
        endpoint_port: Optional[int] = None,
        persistent_keepalive: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict:
        """Create a new Wireguard peer."""
        kwargs = {
            "interface": interface,
            "public-key": public_key,
            "allowed-address": allowed_address,
        }
        if endpoint_address:
            kwargs["endpoint-address"] = endpoint_address
        if endpoint_port:
            kwargs["endpoint-port"] = str(endpoint_port)
        if persistent_keepalive:
            kwargs["persistent-keepalive"] = persistent_keepalive
        if comment:
            kwargs["comment"] = comment
        result = await self._execute("interface", "wireguard", "peers", command="add", **kwargs)
        return result[0] if result else {}

    async def update_wireguard_peer(self, peer_id: str, data: Dict) -> Dict:
        """Update an existing Wireguard peer."""
        data[".id"] = peer_id
        converted = {}
        for k, v in data.items():
            if k == ".id":
                converted[k] = v
            else:
                converted[k.replace("_", "-")] = str(v) if v is not None else v
        await self._execute("interface", "wireguard", "peers", command="set", **converted)
        return {}

    async def delete_wireguard_peer(self, peer_id: str) -> None:
        """Delete a Wireguard peer."""
        await self._execute("interface", "wireguard", "peers", command="remove", **{".id": peer_id})

    # IP Address Operations
    async def get_ip_addresses(
        self, interface: Optional[str] = None, comment_filter: Optional[str] = None
    ) -> List[Dict]:
        """Get IP addresses."""
        result = await self._execute("ip", "address")
        if interface:
            result = [r for r in result if r.get("interface") == interface]
        if comment_filter:
            result = [r for r in result if comment_filter in r.get("comment", "")]
        return result

    async def create_ip_address(
        self,
        address: str,
        interface: str,
        comment: Optional[str] = None,
    ) -> Dict:
        """Create a new IP address."""
        kwargs = {
            "address": address,
            "interface": interface,
        }
        if comment:
            kwargs["comment"] = comment
        result = await self._execute("ip", "address", command="add", **kwargs)
        return result[0] if result else {}

    async def delete_ip_address(self, address_id: str) -> None:
        """Delete an IP address."""
        await self._execute("ip", "address", command="remove", **{".id": address_id})

    # Route Operations
    async def get_routes(self, comment_filter: Optional[str] = None) -> List[Dict]:
        """Get routes."""
        result = await self._execute("ip", "route")
        if comment_filter:
            result = [r for r in result if comment_filter in r.get("comment", "")]
        return result

    async def create_route(
        self,
        dst_address: str,
        gateway: str,
        comment: Optional[str] = None,
    ) -> Dict:
        """Create a new route."""
        kwargs = {
            "dst-address": dst_address,
            "gateway": gateway,
        }
        if comment:
            kwargs["comment"] = comment
        result = await self._execute("ip", "route", command="add", **kwargs)
        return result[0] if result else {}

    async def delete_route(self, route_id: str) -> None:
        """Delete a route."""
        await self._execute("ip", "route", command="remove", **{".id": route_id})

    # Firewall Filter Operations
    async def get_firewall_filter_rules(
        self, chain: Optional[str] = None, comment_filter: Optional[str] = None
    ) -> List[Dict]:
        """Get firewall filter rules."""
        result = await self._execute("ip", "firewall", "filter")
        if chain:
            result = [r for r in result if r.get("chain") == chain]
        if comment_filter:
            result = [r for r in result if comment_filter in r.get("comment", "")]
        return result

    async def create_firewall_filter_rule(
        self,
        chain: str,
        action: str,
        in_interface: Optional[str] = None,
        out_interface: Optional[str] = None,
        comment: Optional[str] = None,
        place_before: Optional[int] = None,
    ) -> Dict:
        """Create a new firewall filter rule."""
        kwargs = {
            "chain": chain,
            "action": action,
        }
        if in_interface:
            kwargs["in-interface"] = in_interface
        if out_interface:
            kwargs["out-interface"] = out_interface
        if comment:
            kwargs["comment"] = comment
        if place_before is not None:
            kwargs["place-before"] = str(place_before)
        result = await self._execute("ip", "firewall", "filter", command="add", **kwargs)
        return result[0] if result else {}

    async def delete_firewall_filter_rule(self, rule_id: str) -> None:
        """Delete a firewall filter rule."""
        await self._execute("ip", "firewall", "filter", command="remove", **{".id": rule_id})

    # NAT Operations
    async def get_nat_rules(
        self, chain: Optional[str] = None, comment_filter: Optional[str] = None
    ) -> List[Dict]:
        """Get NAT rules."""
        result = await self._execute("ip", "firewall", "nat")
        if chain:
            result = [r for r in result if r.get("chain") == chain]
        if comment_filter:
            result = [r for r in result if comment_filter in r.get("comment", "")]
        return result

    async def create_nat_rule(
        self,
        chain: str,
        action: str,
        dst_address: Optional[str] = None,
        src_address: Optional[str] = None,
        protocol: Optional[str] = None,
        dst_port: Optional[str] = None,
        to_addresses: Optional[str] = None,
        to_ports: Optional[str] = None,
        out_interface: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict:
        """Create a new NAT rule."""
        kwargs = {
            "chain": chain,
            "action": action,
        }
        if dst_address:
            kwargs["dst-address"] = dst_address
        if src_address:
            kwargs["src-address"] = src_address
        if protocol:
            kwargs["protocol"] = protocol
        if dst_port:
            kwargs["dst-port"] = dst_port
        if to_addresses:
            kwargs["to-addresses"] = to_addresses
        if to_ports:
            kwargs["to-ports"] = to_ports
        if out_interface:
            kwargs["out-interface"] = out_interface
        if comment:
            kwargs["comment"] = comment
        result = await self._execute("ip", "firewall", "nat", command="add", **kwargs)
        return result[0] if result else {}

    async def delete_nat_rule(self, rule_id: str) -> None:
        """Delete a NAT rule."""
        await self._execute("ip", "firewall", "nat", command="remove", **{".id": rule_id})

    # Helper methods for managed resources
    def get_managed_comment(self, resource_id: str) -> str:
        """Generate a comment for managed resources."""
        return f"{self.COMMENT_PREFIX}{resource_id}"

    async def get_managed_resources(self) -> Dict[str, List[Dict]]:
        """Get all resources managed by this application."""
        return {
            "wireguard_interfaces": await self.get_wireguard_interfaces(
                comment_filter=self.COMMENT_PREFIX
            ),
            "wireguard_peers": await self.get_wireguard_peers(
                comment_filter=self.COMMENT_PREFIX
            ),
            "ip_addresses": await self.get_ip_addresses(
                comment_filter=self.COMMENT_PREFIX
            ),
            "routes": await self.get_routes(comment_filter=self.COMMENT_PREFIX),
            "firewall_filter_rules": await self.get_firewall_filter_rules(
                comment_filter=self.COMMENT_PREFIX
            ),
            "nat_rules": await self.get_nat_rules(comment_filter=self.COMMENT_PREFIX),
        }

    async def remove_managed_resources(self) -> None:
        """Remove all managed resources identified by the app comment prefix."""
        # Remove NAT rules
        for nat in await self.get_nat_rules(comment_filter=self.COMMENT_PREFIX):
            await self.delete_nat_rule(nat[".id"])

        # Remove firewall rules
        for rule in await self.get_firewall_filter_rules(comment_filter=self.COMMENT_PREFIX):
            await self.delete_firewall_filter_rule(rule[".id"])

        # Remove routes
        for route in await self.get_routes(comment_filter=self.COMMENT_PREFIX):
            await self.delete_route(route[".id"])

        # Remove IP addresses
        for addr in await self.get_ip_addresses(comment_filter=self.COMMENT_PREFIX):
            await self.delete_ip_address(addr[".id"])

        # Remove WireGuard peers and interface
        for peer in await self.get_wireguard_peers(comment_filter=self.COMMENT_PREFIX):
            await self.delete_wireguard_peer(peer[".id"])
        for iface in await self.get_wireguard_interfaces(comment_filter=self.COMMENT_PREFIX):
            await self.delete_wireguard_interface(iface[".id"])

    async def run_script(self, script_text: str) -> None:
        """Run a RouterOS script by posting to the REST API."""
        api = self._get_connection()
        try:
            # RouterOS API via librouteros: /system/script/print/add/run is not directly exposed;
            # fallback: use "console" execute via .talk at /console
            console = api.path("console")
            console("execute", command=script_text)
        finally:
            try:
                api.close()
            except Exception:
                pass
