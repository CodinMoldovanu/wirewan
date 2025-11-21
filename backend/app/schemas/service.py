from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import ipaddress

from app.models.service import ServiceProtocol


class ServiceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    local_ip: str
    local_port: int = Field(..., ge=0, le=65535)  # allow 0 to represent "all ports"
    shared_port: Optional[int] = Field(None, ge=0, le=65535)
    protocol: ServiceProtocol = ServiceProtocol.TCP

    @field_validator("local_ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"Invalid IP address: {e}")
        return v


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    local_ip: Optional[str] = None
    local_port: Optional[int] = Field(None, ge=1, le=65535)
    shared_port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: Optional[ServiceProtocol] = None
    is_active: Optional[bool] = None

    @field_validator("local_ip")
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                ipaddress.ip_address(v)
            except ValueError as e:
                raise ValueError(f"Invalid IP address: {e}")
        return v


class ServiceResponse(ServiceBase):
    id: str
    peer_id: str
    shared_ip: str
    is_active: bool
    created_at: datetime
    hostname: Optional[str] = None

    class Config:
        from_attributes = True


class ServiceListResponse(BaseModel):
    items: List[ServiceResponse]
    total: int
