from typing import Optional
from pydantic import BaseModel, Field, field_validator
import ipaddress


class SubnetBase(BaseModel):
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


class SubnetCreate(SubnetBase):
    pass


class SubnetUpdate(BaseModel):
    cidr: Optional[str] = None
    is_routed: Optional[bool] = None
    description: Optional[str] = None

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                ipaddress.ip_network(v, strict=False)
            except ValueError as e:
                raise ValueError(f"Invalid CIDR notation: {e}")
        return v


class SubnetResponse(SubnetBase):
    id: str
    peer_id: str
    nat_enabled: bool
    nat_translated_cidr: Optional[str]

    class Config:
        from_attributes = True
