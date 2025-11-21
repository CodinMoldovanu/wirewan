from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import ipaddress

from app.models.wan import TopologyType


class WanBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tunnel_ip_range: str = Field(default="10.0.0.0/24")
    shared_services_range: str = Field(default="10.0.5.0/24")
    topology_type: TopologyType = TopologyType.MESH

    @field_validator("tunnel_ip_range", "shared_services_range")
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid CIDR notation: {e}")
        return v


class WanCreate(WanBase):
    pass


class WanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tunnel_ip_range: Optional[str] = None
    shared_services_range: Optional[str] = None
    topology_type: Optional[TopologyType] = None

    @field_validator("tunnel_ip_range", "shared_services_range")
    @classmethod
    def validate_cidr(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                ipaddress.ip_network(v, strict=False)
            except ValueError as e:
                raise ValueError(f"Invalid CIDR notation: {e}")
        return v


class WanResponse(WanBase):
    id: str
    created_at: datetime
    updated_at: datetime
    peer_count: int = 0

    class Config:
        from_attributes = True


class WanListResponse(BaseModel):
    items: List[WanResponse]
    total: int
