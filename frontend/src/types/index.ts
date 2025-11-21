export type TopologyType = 'hub-spoke' | 'mesh' | 'hybrid';
export type PeerType = 'mikrotik' | 'generic-router' | 'server' | 'client' | 'hub';
export type MikrotikAuthMethod = 'password' | 'token';
export type MikrotikApiStatus = 'unknown' | 'connected' | 'auth-failed' | 'unreachable';
export type ServiceProtocol = 'tcp' | 'udp' | 'both';
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type JobType = 'deploy-config' | 'rollback' | 'verify' | 'test-connection';

export interface WanNetwork {
  id: string;
  name: string;
  description?: string;
  tunnel_ip_range: string;
  shared_services_range: string;
  topology_type: TopologyType;
  created_at: string;
  updated_at: string;
  peer_count: number;
}

export interface LocalSubnet {
  id: string;
  cidr: string;
  is_routed: boolean;
  nat_enabled: boolean;
  nat_translated_cidr?: string;
  description?: string;
}

export interface Peer {
  id: string;
  wan_id: string;
  name: string;
  type: PeerType;
  public_key?: string;
  tunnel_ip?: string;
  endpoint?: string;
  listen_port?: number;
  persistent_keepalive?: number;
  tags: string[];
  is_online: boolean;
  last_seen?: string;
  created_at: string;
  updated_at: string;
  peer_metadata?: Record<string, unknown>;
  mikrotik_management_ip?: string;
  mikrotik_api_port?: number;
  mikrotik_auth_method?: MikrotikAuthMethod;
  mikrotik_username?: string;
  mikrotik_password?: string;
  mikrotik_api_token?: string;
  mikrotik_use_ssl: boolean;
  mikrotik_verify_cert: boolean;
  mikrotik_auto_deploy: boolean;
  mikrotik_interface_name?: string;
  mikrotik_last_api_check?: string;
  mikrotik_api_status?: MikrotikApiStatus;
  mikrotik_router_identity?: string;
  mikrotik_routeros_version?: string;
  local_subnets: LocalSubnet[];
}

export interface PublishedService {
  id: string;
  peer_id: string;
  name: string;
  description?: string;
  local_ip: string;
  local_port: number;
  shared_ip: string;
  shared_port: number;
  protocol: ServiceProtocol;
  is_active: boolean;
  created_at: string;
  hostname?: string;
}

export interface DeploymentJob {
  id: string;
  peer_id: string;
  job_type: JobType;
  status: JobStatus;
  progress_percent: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  operations_log?: Record<string, unknown>[];
  created_at: string;
  created_by_id?: string;
}

export interface TopologyNode {
  id: string;
  name: string;
  type: PeerType;
  tunnel_ip?: string;
  is_online: boolean;
  endpoint?: string;
  subnet_count: number;
  service_count: number;
  is_mikrotik: boolean;
  mikrotik_api_status?: MikrotikApiStatus;
}

export interface TopologyEdge {
  source: string;
  target: string;
  type: string;
}

export interface Topology {
  wan_id: string;
  wan_name: string;
  topology_type: TopologyType;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface SubnetConflict {
  subnet: string;
  conflict_type: string;
  severity: 'critical' | 'warning' | 'info';
  conflicting_with: string;
  conflicting_subnet: string;
  description: string;
  suggested_resolutions: string[];
}
