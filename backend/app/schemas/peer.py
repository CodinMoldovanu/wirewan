from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import ipaddress

from app.models.peer import PeerType, MikrotikAuthMethod, MikrotikApiStatus


class MikrotikConfigBase(BaseModel):
    mikrotik_management_ip: Optional[str] = None
    mikrotik_api_port: Optional[int] = Field(default=8728, ge=1, le=65535)
    mikrotik_auth_method: Optional[MikrotikAuthMethod] = None
    mikrotik_username: Optional[str] = None
    mikrotik_password: Optional[str] = None
    mikrotik_api_token: Optional[str] = None
    mikrotik_use_ssl: bool = True
    mikrotik_verify_cert: bool = False
    mikrotik_auto_deploy: bool = False
    mikrotik_interface_name: Optional[str] = Field(default="wg-wan-overlay")

    @field_validator("mikrotik_management_ip", "mikrotik_username", "mikrotik_password", "mikrotik_api_token", "mikrotik_interface_name", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for optional fields."""
        if v == "":
            return None
        return v


class SubnetInput(BaseModel):
    cidr: str
    is_routed: bool = True
    description: Optional[str] = None

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid CIDR notation: {e}")
        return v


class PeerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: PeerType
    endpoint: Optional[str] = None  # ip:port
    listen_port: Optional[int] = Field(default=51820, ge=1, le=65535)
    persistent_keepalive: Optional[int] = Field(default=25, ge=0, le=65535)
    tags: Optional[List[str]] = Field(default_factory=list)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: Optional[str]) -> Optional[str]:
        # Convert empty string to None
        if v is None or v == "":
            return None

        # Check if port is included
        parts = v.rsplit(":", 1)
        if len(parts) == 2:
            # Has a colon - check if the second part is a valid port
            try:
                port = int(parts[1])
                if not 1 <= port <= 65535:
                    raise ValueError("Port must be between 1 and 65535")
                return v  # Valid format with port
            except ValueError:
                # Second part is not a number - might be IPv6 or hostname with no port
                pass

        # No port specified or invalid port - append default WireGuard port
        # Handle IPv6 addresses (contains multiple colons)
        if v.count(":") > 1 and not v.startswith("["):
            # IPv6 without brackets - wrap it
            return f"[{v}]:51820"
        elif v.startswith("[") and "]" in v:
            # IPv6 with brackets - check if port exists
            if v.endswith("]"):
                return f"{v}:51820"
            return v  # Already has port after ]
        else:
            # Hostname or IPv4 without port
            return f"{v}:51820"


class PeerCreate(PeerBase, MikrotikConfigBase):
    local_subnets: Optional[List[SubnetInput]] = Field(default_factory=list)


class PeerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    endpoint: Optional[str] = None
    listen_port: Optional[int] = Field(None, ge=1, le=65535)
    persistent_keepalive: Optional[int] = Field(None, ge=0, le=65535)
    tags: Optional[List[str]] = None
    peer_metadata: Optional[dict] = None

    # MikroTik fields
    mikrotik_management_ip: Optional[str] = None
    mikrotik_api_port: Optional[int] = Field(None, ge=1, le=65535)
    mikrotik_auth_method: Optional[MikrotikAuthMethod] = None
    mikrotik_username: Optional[str] = None
    mikrotik_password: Optional[str] = None
    mikrotik_api_token: Optional[str] = None
    mikrotik_use_ssl: Optional[bool] = None
    mikrotik_verify_cert: Optional[bool] = None
    mikrotik_auto_deploy: Optional[bool] = None
    mikrotik_interface_name: Optional[str] = None


class SubnetResponse(BaseModel):
    id: str
    cidr: str
    is_routed: bool
    nat_enabled: bool
    nat_translated_cidr: Optional[str]
    description: Optional[str]

    class Config:
        from_attributes = True


class PeerResponse(PeerBase):
    id: str
    wan_id: str
    public_key: Optional[str]
    tunnel_ip: Optional[str]
    is_online: bool
    last_seen: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    peer_metadata: Optional[dict] = None

    # MikroTik fields (excluding sensitive data)
    mikrotik_management_ip: Optional[str] = None
    mikrotik_api_port: Optional[int] = None
    mikrotik_auth_method: Optional[MikrotikAuthMethod] = None
    mikrotik_username: Optional[str] = None
    mikrotik_use_ssl: bool = True
    mikrotik_verify_cert: bool = False
    mikrotik_auto_deploy: bool = False
    mikrotik_interface_name: Optional[str] = None
    mikrotik_last_api_check: Optional[datetime] = None
    mikrotik_api_status: Optional[MikrotikApiStatus] = None
    mikrotik_router_identity: Optional[str] = None
    mikrotik_routeros_version: Optional[str] = None

    local_subnets: List[SubnetResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PeerListResponse(BaseModel):
    items: List[PeerResponse]
    total: int


class MikrotikTestConnectionResponse(BaseModel):
    success: bool
    router_identity: Optional[str] = None
    routeros_version: Optional[str] = None
    error_message: Optional[str] = None


class PeerConfigResponse(BaseModel):
    config_type: str
    config_text: str
    peer_name: str
    generated_at: datetime
