from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.models.deployment import JobType, JobStatus
from app.models.api_log import HttpMethod


class ApiCallLogResponse(BaseModel):
    id: str
    method: HttpMethod
    endpoint: str
    request_body: Optional[Dict[str, Any]]
    response_status: int
    response_body: Optional[Dict[str, Any]]
    error_message: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class DeploymentJobResponse(BaseModel):
    id: str
    peer_id: str
    job_type: JobType
    status: JobStatus
    progress_percent: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    operations_log: Optional[List[Dict[str, Any]]]
    created_at: datetime
    created_by_id: Optional[str]

    class Config:
        from_attributes = True


class DeploymentJobListResponse(BaseModel):
    items: List[DeploymentJobResponse]
    total: int


class DeploymentJobDetailResponse(DeploymentJobResponse):
    api_call_logs: List[ApiCallLogResponse] = []


class ConfigDiff(BaseModel):
    resource_type: str  # wireguard_interface, wireguard_peer, ip_address, route, firewall_rule, nat_rule
    action: str  # create, update, delete
    current: Optional[Dict[str, Any]]
    desired: Optional[Dict[str, Any]]


class DeploymentPreviewResponse(BaseModel):
    peer_id: str
    peer_name: str
    changes: List[ConfigDiff]
    api_calls_count: int
    warnings: List[str]
    estimated_duration_seconds: int
