# Wireguard WAN Overlay Network - Detailed Specification

## 1. Overview

### 1.1 Purpose
Build a cross-platform application (web-based or native desktop app for Windows/Linux/macOS) that orchestrates and manages a Wireguard-based overlay network, allowing multiple peers to interconnect their networks into a unified WAN with selective service exposure capabilities. The application will provide automated configuration deployment to MikroTik routers via their REST API.

### 1.2 Key Objectives
- Automate Wireguard peer provisioning and configuration
- Manage a tiered IP addressing scheme for tunnel endpoints and shared services
- Handle IP subnet conflicts with NAT when necessary
- Enable selective service exposure from local networks to shared WAN space
- **Directly configure MikroTik routers via REST API without manual script application**
- Generate device-specific configurations for non-MikroTik devices
- Scale beyond manual peer-to-peer configuration
- Provide centralized management and monitoring

---

## 2. Architecture

### 2.1 Application Type Options
The application should be buildable as either:
- **Web application** (React/Vue/Svelte frontend + REST/GraphQL API backend)
- **Native cross-platform desktop app** (Electron, Tauri, or Flutter)

The backend must support:
- RESTful API or GraphQL for all operations
- SQLite or PostgreSQL for data persistence
- Authentication and authorization (JWT-based or similar)
- **MikroTik REST API client for automated device configuration**
- **Job queue for asynchronous configuration deployment**

### 2.2 Deployment Models
- **Self-hosted**: User deploys on their own infrastructure
- **Single-user mode**: Local database, no authentication required
- **Multi-user mode**: Team collaboration with role-based access

### 2.3 Network Topology
The system should support multiple topology modes:
- **Hub-and-spoke**: Central hub node, all peers connect to hub
- **Mesh**: Full or partial mesh where peers can connect directly
- **Hybrid**: Hub with optional direct peer-to-peer connections

---

## 3. IP Addressing Scheme

### 3.1 Address Spaces
The application must manage three distinct IP spaces:

#### 3.1.1 Wireguard Tunnel IPs (Point-to-Point)
- **Default range**: `10.0.0.0/24` (configurable)
- Each peer gets one IP from this range
- Used for Wireguard tunnel endpoints
- Must be unique across all peers

#### 3.1.2 Shared Services Subnet
- **Default range**: `10.0.5.0/24` (configurable)
- IPs in this range can be claimed by peers to expose services
- Globally routable across the WAN overlay
- Managed through central registry to prevent conflicts

#### 3.1.3 Local/Private Subnets
- Each peer's existing local network(s)
- Not part of the overlay by default
- Can be selectively routed or exposed
- Must be tracked to detect conflicts

### 3.2 IP Allocation Management
- **Automatic allocation**: System assigns IPs from available pools
- **Manual reservation**: Admin can reserve specific IPs for specific purposes
- **Conflict detection**: Automatically detect overlapping local subnets
- **NAT suggestion**: When conflicts detected, offer NAT as solution

---

## 4. Core Features

### 4.1 Peer Management

#### 4.1.1 Peer Types
The system must support multiple peer types:
- **MikroTik Router peers**: MikroTik routers managed via REST API
- **Generic Router peers**: Other routers requiring manual configuration
- **Server peers**: Standalone servers exposing services
- **Client peers**: End-user devices (laptops, workstations)
- **Hub peers**: Central coordination points for hub-spoke topology

#### 4.1.2 Peer Registration
When adding a new peer, collect:

**Common fields for all peers:**
- **Peer name/identifier** (human-readable)
- **Peer type** (mikrotik/generic-router/server/client/hub)
- **Public key** (Wireguard public key, auto-generated or provided)
- **Endpoint** (public IP/hostname and port for incoming connections)
- **Local subnets** (list of local network ranges this peer owns)
- **Persistent keepalive** (optional, default 25 seconds for NAT traversal)
- **Tags/labels** (for organization and filtering)

**Additional fields for MikroTik peers:**
- **MikroTik IP address** (management IP for API access)
- **MikroTik API port** (default 443 for HTTPS)
- **Authentication method** (username/password or API token)
- **Username** (for API authentication)
- **Password/API Token** (encrypted storage)
- **Use SSL** (boolean, default true)
- **Verify certificate** (boolean, default false for self-signed certs)
- **Auto-deploy** (boolean, whether to automatically push config changes)
- **Management interface** (which interface to use for WAN overlay, e.g., "wg-wan-overlay")

#### 4.1.3 Configuration Deployment Modes

**For MikroTik Peers:**
- **Automatic deployment**: System directly applies configuration via REST API
- **Preview mode**: Generate and show changes before applying
- **Manual mode**: Generate script for manual application (fallback)

**For Non-MikroTik Peers:**
- **Configuration generation only**: Create appropriate config files
- **Manual application**: User must apply configuration themselves

### 4.2 MikroTik REST API Integration

#### 4.2.1 MikroTik API Overview
MikroTik RouterOS v7+ provides a REST API over HTTP/HTTPS that allows:
- Reading configuration: `GET /rest/{path}`
- Creating resources: `POST /rest/{path}`
- Updating resources: `PATCH /rest/{path}/{id}`
- Deleting resources: `DELETE /rest/{path}/{id}`

**Key API endpoints for WAN overlay:**
- `/rest/interface/wireguard` - Manage Wireguard interfaces
- `/rest/interface/wireguard/peers` - Manage Wireguard peers
- `/rest/ip/address` - Manage IP addresses
- `/rest/ip/route` - Manage routing table
- `/rest/ip/firewall/filter` - Manage firewall filter rules
- `/rest/ip/firewall/nat` - Manage NAT rules
- `/rest/system/identity` - Get router identity
- `/rest/system/resource` - Get system status

#### 4.2.2 Authentication
MikroTik REST API supports:
- **Basic authentication**: Username/password in HTTP headers
- **Token-based authentication**: API tokens (more secure, recommended)

Application should:
- Store credentials encrypted in database
- Support both authentication methods
- Test connectivity before saving credentials
- Handle authentication failures gracefully

#### 4.2.3 Non-Destructive Configuration Strategy

The application must ensure it doesn't break existing MikroTik configurations:

**Strategy 1: Comment-based identification**
- All resources created by the application must include a comment field
- Comment format: `WAN-Overlay-Manager:{config-id}` where config-id is a UUID
- Before modifying, query existing resources by comment to find managed items
- Only delete/modify resources with matching comments

**Strategy 2: Naming conventions**
- Use consistent naming for created resources
- Interface name: `wg-{wan-name}` (e.g., `wg-wan-overlay`)
- Peer names: Include unique identifier
- List names: Prefix with application identifier

**Strategy 3: Read-before-write**
- Always query existing configuration before making changes
- Compare desired state with current state
- Only apply differences
- Never use commands that remove all items without filtering

#### 4.2.4 Configuration Deployment Workflow

**Step 1: Pre-deployment validation**
```
1. Test API connectivity
2. Verify credentials
3. Read current Wireguard configuration
4. Identify existing WAN-Overlay-Manager resources
5. Generate desired configuration state
6. Calculate diff between current and desired
7. Validate changes won't cause conflicts
```

**Step 2: Deployment execution**
```
1. Backup current configuration (store in database)
2. Create/update Wireguard interface
3. Create/update Wireguard peers
4. Create/update IP addresses
5. Create/update routes
6. Create/update firewall rules
7. Create/update NAT rules (if needed)
8. Verify configuration applied successfully
9. Test connectivity (ping tunnel endpoints)
10. Mark deployment as successful
```

**Step 3: Rollback capability**
```
If deployment fails:
1. Retrieve backup configuration
2. Remove newly created resources
3. Restore previous state
4. Log failure reason
5. Notify administrator
```

#### 4.2.5 MikroTik API Operations

**Creating Wireguard Interface:**
```http
POST /rest/interface/wireguard
Content-Type: application/json

{
  "name": "wg-wan-overlay",
  "listen-port": 51820,
  "private-key": "base64-encoded-private-key",
  "comment": "WAN-Overlay-Manager:uuid-here"
}
```

**Adding Wireguard Peer:**
```http
POST /rest/interface/wireguard/peers
Content-Type: application/json

{
  "interface": "wg-wan-overlay",
  "public-key": "peer-public-key",
  "endpoint-address": "1.2.3.4",
  "endpoint-port": 51820,
  "allowed-address": "10.0.0.2/32,192.168.2.0/24,10.0.5.0/24",
  "persistent-keepalive": "25s",
  "comment": "WAN-Overlay-Manager:peer-name-uuid"
}
```

**Adding IP Address:**
```http
POST /rest/ip/address
Content-Type: application/json

{
  "address": "10.0.0.1/24",
  "interface": "wg-wan-overlay",
  "comment": "WAN-Overlay-Manager:uuid-here"
}
```

**Adding Route:**
```http
POST /rest/ip/route
Content-Type: application/json

{
  "dst-address": "192.168.2.0/24",
  "gateway": "wg-wan-overlay",
  "comment": "WAN-Overlay-Manager:route-to-peer2"
}
```

**Adding Firewall Filter Rule:**
```http
POST /rest/ip/firewall/filter
Content-Type: application/json

{
  "chain": "forward",
  "in-interface": "wg-wan-overlay",
  "action": "accept",
  "comment": "WAN-Overlay-Manager:allow-from-wan"
}
```

**Adding NAT Rule:**
```http
POST /rest/ip/firewall/nat
Content-Type: application/json

{
  "chain": "dstnat",
  "dst-address": "10.0.5.10",
  "protocol": "tcp",
  "dst-port": "80",
  "action": "dst-nat",
  "to-addresses": "192.168.1.50",
  "to-ports": "8080",
  "comment": "WAN-Overlay-Manager:service-web-server"
}
```

**Querying Existing Configuration:**
```http
GET /rest/interface/wireguard?comment=WAN-Overlay-Manager
```

**Updating Peer:**
```http
PATCH /rest/interface/wireguard/peers/{peer-id}
Content-Type: application/json

{
  "allowed-address": "10.0.0.2/32,192.168.2.0/24,10.0.5.0/24,10.0.5.20/32"
}
```

**Deleting Resource:**
```http
DELETE /rest/interface/wireguard/peers/{peer-id}
```

#### 4.2.6 Error Handling for API Operations

The application must handle:
- **Connection failures**: Router unreachable, timeout
- **Authentication failures**: Invalid credentials
- **Configuration conflicts**: Resource already exists
- **Syntax errors**: Invalid parameter values
- **RouterOS version incompatibilities**: Features not available
- **Rate limiting**: If API has request limits

For each error:
- Log detailed error information
- Display user-friendly error message
- Suggest corrective actions
- Optionally fall back to manual script generation

#### 4.2.7 Configuration Verification

After deploying configuration to MikroTik:
1. **Query interface status**: Verify Wireguard interface is running
2. **Query peer status**: Check peer handshake timestamps
3. **Test connectivity**: Ping tunnel IPs of connected peers
4. **Verify routes**: Check routing table for expected routes
5. **Monitor logs**: Check MikroTik logs for errors

Mark deployment as:
- **Success**: All checks pass
- **Partial success**: Some checks fail but interface is up
- **Failure**: Critical errors prevent functionality

#### 4.2.8 Concurrent Deployments

To handle multiple MikroTik routers:
- **Job queue system**: Queue configuration deployments
- **Parallel execution**: Deploy to multiple routers simultaneously (configurable concurrency)
- **Progress tracking**: Show real-time status for each deployment
- **Failure isolation**: One router failure doesn't affect others

### 4.3 Service Exposure

#### 4.3.1 Service Publishing
Allow peers to publish services to the shared services subnet:
- Select a local IP:port from peer's network
- Claim an IP from the shared services subnet (10.0.5.0/24)
- Optional: specify port mapping (e.g., local 192.168.1.50:8080 → 10.0.5.10:80)
- Add service metadata (name, description, protocol)

#### 4.3.2 NAT/Port Forwarding Rules
Generate appropriate NAT rules for the peer device:

**For MikroTik (via API)**: Automatically create NAT rules
**For standard Linux Wireguard**: iptables/nftables rules
**For other platforms**: Configuration snippets or manual instructions

#### 4.3.3 Routing Announcements
Ensure all other peers know how to reach published services:
- Add appropriate `AllowedIPs` entries to peer configurations
- Update routing tables as needed
- Propagate changes to all affected peers (via API for MikroTik, generate new configs for others)

### 4.4 Conflict Resolution

#### 4.4.1 Subnet Overlap Detection
When adding a new peer:
- Check if peer's local subnets overlap with existing peers' subnets
- Check if peer's local subnets overlap with WAN subnets (10.0.0.0/24, 10.0.5.0/24)
- Display clear warnings and conflicts

#### 4.4.2 NAT Options
When conflicts detected, offer solutions:
- **Option 1**: Don't route the conflicting subnet (isolated)
- **Option 2**: Use NAT to translate the conflicting subnet to a non-conflicting range
- **Option 3**: Manually change one of the conflicting networks
- **Option 4**: Use selective routing (only route non-conflicting IPs)

#### 4.4.3 NAT Configuration
If user chooses NAT:
- Automatically assign a non-conflicting subnet range
- Generate NAT rules for the peer's device
- For MikroTik: Deploy NAT rules via API
- For others: Generate configuration snippets
- Update routing across the WAN to use translated IPs
- Document the translation mapping for troubleshooting

### 4.5 Configuration Templates

#### 4.5.1 Template System
Support configuration templates for common scenarios:
- **Simple client**: Basic endpoint with no routing
- **Site router**: Router connecting an entire site
- **Service host**: Server exposing services to shared subnet
- **Hub node**: Central point for hub-spoke topology
- **Custom**: User-defined template

#### 4.5.2 Template Variables
Templates should support variables:
- `{{PEER_NAME}}`
- `{{TUNNEL_IP}}`
- `{{SHARED_SERVICE_IP}}`
- `{{LOCAL_SUBNETS}}`
- `{{PUBLIC_KEY}}`
- `{{PRIVATE_KEY}}`
- `{{ENDPOINT}}`
- etc.

---

## 5. User Interface Requirements

### 5.1 Dashboard
- Overview of entire WAN topology
- Visual network map showing peers and connections
- Health status of each peer (online/offline/last seen)
- Quick stats (total peers, active connections, published services)
- **Deployment status widget**: Show ongoing/recent deployments

### 5.2 Peer Management Interface

**List view:**
- All peers with filtering and search
- Status indicators (online/offline, last handshake)
- **MikroTik-specific indicators**: API connection status, auto-deploy enabled
- Bulk operations (export all configs, regenerate keys, deploy to all)

**Add/Edit peer form:**
- Basic peer information fields
- **MikroTik-specific section** (shown when peer type is MikroTik):
  - Management IP input
  - Credentials input (encrypted)
  - Connection test button
  - Auto-deploy toggle
  - Interface name selection
- Local subnets management
- Conflict warnings (if applicable)

**Peer detail view:**
- Configuration details
- Connected local subnets
- Published services
- Connection status and statistics
- **For MikroTik peers**:
  - API connection status
  - Last deployment timestamp and status
  - Deployment history log
  - "Deploy Now" button
  - "Preview Changes" button
  - Current vs. desired state diff
- Generated configuration (downloadable for non-MikroTik)

### 5.3 MikroTik Management

**MikroTik connection testing:**
- "Test Connection" button in peer form
- Displays:
  - Connection success/failure
  - Router identity
  - RouterOS version
  - Available API endpoints

**Deployment interface:**
- "Preview Changes" mode:
  - Shows diff of current vs. desired configuration
  - Lists all API calls that will be made
  - Allows approval before deployment
- "Deploy Configuration" button:
  - Initiates deployment job
  - Shows real-time progress
  - Displays success/failure for each step
- Deployment history:
  - List of past deployments with timestamps
  - Success/failure status
  - Rollback capability for failed deployments
  - View detailed logs

**Bulk operations for MikroTik:**
- "Deploy to All MikroTik Peers" button
- Progress bar showing deployment status across multiple routers
- Summary of successes/failures

### 5.4 Service Registry
- List of all published services across the WAN
- Filterable by peer, service type, IP range
- Quick access/copy of service IPs
- Service health checks (optional feature)
- **For MikroTik-hosted services**: Show NAT rule status

### 5.5 Conflict Management UI
- Visual display of subnet overlaps
- Interactive conflict resolution wizard
- Preview of NAT translations before applying
- Warning indicators for potential routing issues
- **MikroTik-specific**: Option to deploy NAT rules immediately

### 5.6 Configuration Export
- Download generated configs for each peer
- Bulk export (ZIP file with all peer configs)
- Copy-to-clipboard functionality
- QR code generation for mobile devices
- **MikroTik script export** (as fallback/backup)

### 5.7 Network Topology Visualizer
- Interactive graph of peer connections
- Color coding for peer types and status
- **Special indicator for MikroTik peers with API enabled**
- Clickable nodes to see peer details
- Export topology as image/diagram

### 5.8 Job Queue Monitor
- Real-time view of deployment jobs
- Filter by status (pending, running, completed, failed)
- Job details (target peer, operations performed)
- Cancel running jobs
- Retry failed jobs

---

## 6. Data Model

### 6.1 Core Entities

#### 6.1.1 WAN Network
```
- id (UUID)
- name (string)
- description (text)
- tunnel_ip_range (CIDR, e.g., "10.0.0.0/24")
- shared_services_range (CIDR, e.g., "10.0.5.0/24")
- topology_type (enum: hub-spoke, mesh, hybrid)
- created_at (timestamp)
- updated_at (timestamp)
```

#### 6.1.2 Peer
```
- id (UUID)
- wan_id (FK to WAN Network)
- name (string)
- type (enum: mikrotik, generic-router, server, client, hub)
- public_key (string)
- private_key (string, encrypted)
- tunnel_ip (IP address)
- endpoint (string, nullable, e.g., "1.2.3.4:51820")
- listen_port (integer, nullable)
- persistent_keepalive (integer, nullable)
- is_online (boolean)
- last_seen (timestamp)
- tags (JSON array)
- metadata (JSON object)
- created_at (timestamp)
- updated_at (timestamp)

# MikroTik-specific fields
- mikrotik_management_ip (string, nullable)
- mikrotik_api_port (integer, nullable, default 443)
- mikrotik_auth_method (enum: password, token, nullable)
- mikrotik_username (string, nullable)
- mikrotik_password (string, encrypted, nullable)
- mikrotik_api_token (string, encrypted, nullable)
- mikrotik_use_ssl (boolean, default true)
- mikrotik_verify_cert (boolean, default false)
- mikrotik_auto_deploy (boolean, default false)
- mikrotik_interface_name (string, nullable, default "wg-wan-overlay")
- mikrotik_last_api_check (timestamp, nullable)
- mikrotik_api_status (enum: unknown, connected, auth-failed, unreachable, nullable)
- mikrotik_router_identity (string, nullable)
- mikrotik_routeros_version (string, nullable)
```

#### 6.1.3 Local Subnet
```
- id (UUID)
- peer_id (FK to Peer)
- cidr (CIDR notation)
- is_routed (boolean, whether this subnet is routed to WAN)
- nat_enabled (boolean)
- nat_translated_cidr (CIDR, nullable)
- description (text)
```

#### 6.1.4 Published Service
```
- id (UUID)
- peer_id (FK to Peer)
- name (string)
- description (text)
- local_ip (IP address)
- local_port (integer)
- shared_ip (IP address from shared services range)
- shared_port (integer)
- protocol (enum: tcp, udp, both)
- is_active (boolean)
- created_at (timestamp)
```

#### 6.1.5 Peer Connection
```
- id (UUID)
- peer_a_id (FK to Peer)
- peer_b_id (FK to Peer)
- is_active (boolean)
- last_handshake (timestamp)
- tx_bytes (bigint)
- rx_bytes (bigint)
```

#### 6.1.6 Configuration History
```
- id (UUID)
- peer_id (FK to Peer)
- configuration_text (text)
- config_type (enum: wireguard, mikrotik-script, mikrotik-api, iptables, etc.)
- generated_at (timestamp)
- applied_at (timestamp, nullable)
```

#### 6.1.7 Deployment Job (NEW)
```
- id (UUID)
- peer_id (FK to Peer)
- job_type (enum: deploy-config, rollback, verify, test-connection)
- status (enum: pending, running, completed, failed, cancelled)
- progress_percent (integer, 0-100)
- started_at (timestamp, nullable)
- completed_at (timestamp, nullable)
- error_message (text, nullable)
- operations_log (JSON array, detailed log of API calls)
- created_at (timestamp)
- created_by (FK to User, nullable)
```

#### 6.1.8 MikroTik API Call Log (NEW)
```
- id (UUID)
- deployment_job_id (FK to Deployment Job)
- peer_id (FK to Peer)
- method (enum: GET, POST, PATCH, DELETE)
- endpoint (string, e.g., "/rest/interface/wireguard")
- request_body (JSON, nullable)
- response_status (integer, HTTP status code)
- response_body (JSON, nullable)
- error_message (text, nullable)
- timestamp (timestamp)
```

### 6.2 Relationships
- One WAN Network has many Peers
- One Peer has many Local Subnets
- One Peer has many Published Services
- Peers have many-to-many connections (Peer Connections)
- One Peer has many Configuration History entries
- One Peer has many Deployment Jobs
- One Deployment Job has many MikroTik API Call Logs

---

## 7. API Endpoints

### 7.1 WAN Management
- `POST /api/wan` - Create new WAN network
- `GET /api/wan/:id` - Get WAN details
- `PUT /api/wan/:id` - Update WAN settings
- `DELETE /api/wan/:id` - Delete WAN network

### 7.2 Peer Management
- `GET /api/wan/:wanId/peers` - List all peers
- `POST /api/wan/:wanId/peers` - Add new peer
- `GET /api/peers/:id` - Get peer details
- `PUT /api/peers/:id` - Update peer
- `DELETE /api/peers/:id` - Remove peer
- `POST /api/peers/:id/regenerate-keys` - Generate new keypair
- `GET /api/peers/:id/config` - Get generated configuration
- `GET /api/peers/:id/config/mikrotik-script` - Get MikroTik script (fallback)
- `GET /api/peers/:id/config/qr` - Get QR code for mobile

### 7.3 MikroTik-Specific Endpoints (NEW)
- `POST /api/peers/:id/mikrotik/test-connection` - Test API connectivity
- `POST /api/peers/:id/mikrotik/deploy` - Deploy configuration via API
- `POST /api/peers/:id/mikrotik/preview` - Preview configuration changes
- `POST /api/peers/:id/mikrotik/rollback` - Rollback to previous configuration
- `GET /api/peers/:id/mikrotik/status` - Get current configuration from router
- `GET /api/peers/:id/mikrotik/diff` - Compare current vs. desired state
- `POST /api/wan/:wanId/mikrotik/deploy-all` - Deploy to all MikroTik peers
- `GET /api/peers/:id/mikrotik/logs` - Get MikroTik API call logs

### 7.4 Service Management
- `GET /api/wan/:wanId/services` - List all published services
- `POST /api/peers/:peerId/services` - Publish new service
- `GET /api/services/:id` - Get service details
- `PUT /api/services/:id` - Update service
- `DELETE /api/services/:id` - Remove service

### 7.5 Conflict Detection
- `POST /api/peers/:id/check-conflicts` - Check for subnet conflicts
- `GET /api/wan/:wanId/conflicts` - List all conflicts in WAN
- `POST /api/conflicts/:id/resolve` - Apply conflict resolution

### 7.6 Configuration Export
- `GET /api/wan/:wanId/export` - Export all configurations (ZIP)
- `GET /api/peers/:id/export` - Export single peer config
- `POST /api/wan/:wanId/regenerate-all` - Regenerate all peer configs

### 7.7 Deployment Jobs (NEW)
- `GET /api/jobs` - List all deployment jobs
- `GET /api/jobs/:id` - Get job details
- `POST /api/jobs/:id/cancel` - Cancel running job
- `POST /api/jobs/:id/retry` - Retry failed job
- `GET /api/peers/:id/jobs` - List jobs for specific peer
- `GET /api/jobs/:id/logs` - Get detailed job logs

### 7.8 Monitoring
- `GET /api/wan/:wanId/topology` - Get network topology data
- `GET /api/wan/:wanId/status` - Get overall WAN health
- `GET /api/peers/:id/status` - Get peer connection status

---

## 8. Configuration Generation Logic

### 8.1 Standard Wireguard Config (Linux/Windows/macOS)
For non-MikroTik peers, generate standard INI format:

```ini
[Interface]
PrivateKey = <peer-private-key>
Address = <tunnel-ip>/32
# Optional: Add shared services IP if peer publishes services
# Address = <tunnel-ip>/32, <shared-service-ip>/32
ListenPort = <port>
# Optional post-up/down scripts for NAT and routing

[Peer]
# One section per connected peer
PublicKey = <other-peer-public-key>
Endpoint = <other-peer-endpoint>
AllowedIPs = <other-peer-tunnel-ip>/32, <other-peer-local-subnets>, <other-peer-published-services>
PersistentKeepalive = 25
```

### 8.2 MikroTik Configuration via API

#### 8.2.1 Configuration Deployment Algorithm

```
Function: deploy_mikrotik_configuration(peer_id)

1. Pre-flight checks:
   - Verify peer is MikroTik type
   - Test API connectivity
   - Verify credentials
   - Check RouterOS version compatibility

2. Read current state:
   - Query existing Wireguard interfaces
   - Query existing Wireguard peers
   - Query existing IP addresses on WG interface
   - Query existing routes
   - Query existing firewall rules
   - Query existing NAT rules
   - Filter by comment "WAN-Overlay-Manager:*"

3. Calculate desired state:
   - Generate interface configuration
   - Generate peer configurations
   - Generate IP address configuration
   - Generate routes for remote subnets and shared services
   - Generate firewall rules
   - Generate NAT rules (if services are published)

4. Calculate diff:
   - Compare current vs. desired
   - Identify resources to create
   - Identify resources to update
   - Identify resources to delete

5. Create deployment job:
   - Create job record in database
   - Set status to "pending"

6. Execute deployment (asynchronously):
   a. Set job status to "running"
   
   b. Create backup of current configuration:
      - Store all current WAN-Overlay-Manager resources in job metadata
   
   c. Apply changes via API:
      i. Create/update Wireguard interface:
         - POST /rest/interface/wireguard (if not exists)
         - PATCH /rest/interface/wireguard/{id} (if exists)
      
      ii. Create/update Wireguard peers:
         - For each new peer: POST /rest/interface/wireguard/peers
         - For each existing peer: PATCH /rest/interface/wireguard/peers/{id}
         - For each removed peer: DELETE /rest/interface/wireguard/peers/{id}
      
      iii. Create/update IP addresses:
         - POST /rest/ip/address (if not exists)
         - PATCH /rest/ip/address/{id} (if exists)
      
      iv. Create/update routes:
         - For each new route: POST /rest/ip/route
         - For each removed route: DELETE /rest/ip/route/{id}
      
      v. Create/update firewall filter rules:
         - For each new rule: POST /rest/ip/firewall/filter
         - For each removed rule: DELETE /rest/ip/firewall/filter/{id}
      
      vi. Create/update NAT rules:
         - For each new rule: POST /rest/ip/firewall/nat
         - For each removed rule: DELETE /rest/ip/firewall/nat/{id}
   
   d. Log each API call to MikroTik API Call Log
   
   e. Verify deployment:
      - Query interface status
      - Check peer handshakes
      - Test connectivity (ping tunnel IPs)
   
   f. Update job status:
      - If all successful: status = "completed"
      - If verification fails: status = "failed", initiate rollback
      - If API error: status = "failed", log error
   
   g. Update peer status:
      - Set mikrotik_api_status based on result
      - Set mikrotik_last_api_check timestamp

7. Error handling:
   - If any step fails, log error
   - Attempt rollback to previous configuration
   - Mark job as failed with detailed error message

8. Return job ID to caller
```

#### 8.2.2 API Request Examples

**Create Wireguard Interface:**
```python
POST https://{mikrotik_ip}:{api_port}/rest/interface/wireguard
Authorization: Basic {base64(username:password)}
Content-Type: application/json

{
  "name": "wg-wan-overlay",
  "listen-port": 51820,
  "private-key": "eGFtcGxlLXByaXZhdGUta2V5LWJhc2U2NA==",
  "comment": "WAN-Overlay-Manager:550e8400-e29b-41d4-a716-446655440000"
}
```

**Add Wireguard Peer:**
```python
POST https://{mikrotik_ip}:{api_port}/rest/interface/wireguard/peers
Authorization: Basic {base64(username:password)}
Content-Type: application/json

{
  "interface": "wg-wan-overlay",
  "public-key": "cGVlci1wdWJsaWMta2V5LWV4YW1wbGU=",
  "endpoint-address": "203.0.113.10",
  "endpoint-port": 51820,
  "allowed-address": "10.0.0.2/32,192.168.2.0/24,10.0.5.0/24",
  "persistent-keepalive": "25s",
  "comment": "WAN-Overlay-Manager:peer-office-london"
}
```

**Query Existing Peers (to check what's already configured):**
```python
GET https://{mikrotik_ip}:{api_port}/rest/interface/wireguard/peers?comment=WAN-Overlay-Manager
Authorization: Basic {base64(username:password)}
```

**Update Peer's Allowed IPs (when new service published):**
```python
PATCH https://{mikrotik_ip}:{api_port}/rest/interface/wireguard/peers/{peer-id}
Authorization: Basic {base64(username:password)}
Content-Type: application/json

{
  "allowed-address": "10.0.0.2/32,192.168.2.0/24,10.0.5.0/24,10.0.5.20/32"
}
```

**Add NAT Rule for Published Service:**
```python
POST https://{mikrotik_ip}:{api_port}/rest/ip/firewall/nat
Authorization: Basic {base64(username:password)}
Content-Type: application/json

{
  "chain": "dstnat",
  "dst-address": "10.0.5.10",
  "protocol": "tcp",
  "dst-port": "80",
  "action": "dst-nat",
  "to-addresses": "192.168.1.50",
  "to-ports": "8080",
  "comment": "WAN-Overlay-Manager:service-webserver"
}
```

### 8.3 MikroTik Script Generation (Fallback)

For users who prefer manual application or when API is unavailable:

```routeros
# WAN-Overlay-Manager: <peer-name>
# Configuration ID: <uuid>
# Generated: <timestamp>

# IMPORTANT: Review this script before applying
# This script is designed to be non-destructive

# Step 1: Create Wireguard interface if not exists
/interface wireguard
:if ([:len [find name="wg-wan-overlay"]] = 0) do={
  add name=wg-wan-overlay listen-port=<port> private-key="<private-key>" \
      comment="WAN-Overlay-Manager:<uuid>"
} else={
  set [find name="wg-wan-overlay"] listen-port=<port> private-key="<private-key>"
}

# Step 2: Remove old peers managed by this system
/interface wireguard peers
:foreach peer in=[find comment~"WAN-Overlay-Manager"] do={
  remove $peer
}

# Step 3: Add Wireguard peers
/interface wireguard peers
add interface=wg-wan-overlay public-key="<peer1-public-key>" \
    endpoint-address=<peer1-endpoint-ip> endpoint-port=<peer1-port> \
    allowed-address=<peer1-tunnel-ip>/32,<peer1-subnets> \
    persistent-keepalive=25s comment="WAN-Overlay-Manager:peer1-name"
add interface=wg-wan-overlay public-key="<peer2-public-key>" \
    endpoint-address=<peer2-endpoint-ip> endpoint-port=<peer2-port> \
    allowed-address=<peer2-tunnel-ip>/32,<peer2-subnets> \
    persistent-keepalive=25s comment="WAN-Overlay-Manager:peer2-name"

# Step 4: Configure IP addressing
/ip address
:if ([:len [find address="<tunnel-ip>/24" interface="wg-wan-overlay"]] = 0) do={
  add address=<tunnel-ip>/24 interface=wg-wan-overlay \
      comment="WAN-Overlay-Manager:<uuid>"
}

# Step 5: Remove old routes managed by this system
/ip route
:foreach route in=[find comment~"WAN-Overlay-Manager"] do={
  remove $route
}

# Step 6: Add routes for remote networks
/ip route
add dst-address=<remote-subnet1> gateway=wg-wan-overlay \
    comment="WAN-Overlay-Manager:route-to-peer1"
add dst-address=<remote-subnet2> gateway=wg-wan-overlay \
    comment="WAN-Overlay-Manager:route-to-peer2"
add dst-address=10.0.5.0/24 gateway=wg-wan-overlay \
    comment="WAN-Overlay-Manager:shared-services"

# Step 7: Remove old firewall rules managed by this system
/ip firewall filter
:foreach rule in=[find comment~"WAN-Overlay-Manager"] do={
  remove $rule
}

# Step 8: Add firewall rules to allow forwarding
/ip firewall filter
add chain=forward in-interface=wg-wan-overlay action=accept \
    place-before=0 comment="WAN-Overlay-Manager:allow-from-wan"
add chain=forward out-interface=wg-wan-overlay action=accept \
    place-before=1 comment="WAN-Overlay-Manager:allow-to-wan"

# Step 9: Remove old NAT rules managed by this system
/ip firewall nat
:foreach rule in=[find comment~"WAN-Overlay-Manager"] do={
  remove $rule
}

# Step 10: NAT rules for published services (if any)
/ip firewall nat
add chain=dstnat dst-address=<shared-service-ip> protocol=tcp \
    dst-port=<shared-port> action=dst-nat to-addresses=<local-ip> \
    to-ports=<local-port> comment="WAN-Overlay-Manager:service-name"
add chain=srcnat src-address=<local-ip> out-interface=wg-wan-overlay \
    action=src-nat to-addresses=<shared-service-ip> \
    comment="WAN-Overlay-Manager:service-name-srcnat"

# Step 11: Verification commands
:put "Configuration applied. Verifying..."
/interface wireguard print
/interface wireguard peers print
:put "Check peer handshakes above. Recent timestamps indicate successful connection."
```

---

## 9. Business Logic

### 9.1 IP Allocation Algorithm
```
Function: allocate_tunnel_ip(wan_id)
1. Get all allocated tunnel IPs for this WAN
2. Find first available IP in tunnel_ip_range
3. If no IPs available, return error
4. Reserve IP and return
```

```
Function: allocate_shared_service_ip(wan_id)
1. Get all allocated shared service IPs for this WAN
2. Find first available IP in shared_services_range
3. If no IPs available, return error
4. Reserve IP and return
```

### 9.2 Conflict Detection Algorithm
```
Function: detect_conflicts(peer_id)
1. Get peer's local subnets
2. For each local subnet:
   a. Check if overlaps with tunnel_ip_range → Flag as critical conflict
   b. Check if overlaps with shared_services_range → Flag as critical conflict
   c. Check if overlaps with other peers' local subnets → Flag as routing conflict
3. Return list of conflicts with severity and suggested resolutions
```

### 9.3 NAT Translation Assignment
```
Function: assign_nat_translation(conflicting_subnet)
1. Identify the size of the conflicting subnet
2. Find an unused subnet of the same size in private IP space (avoiding 10.0.0.0/8)
3. Suggest 172.16.0.0/12 or 192.168.0.0/16 ranges
4. Reserve the translation subnet
5. Generate NAT rules
6. Update routing for other peers to use translated subnet
```

### 9.4 Configuration Regeneration
```
Function: regenerate_all_configs(wan_id)
1. Get all peers in WAN
2. For each peer:
   a. Calculate AllowedIPs (all other tunnel IPs + their routed subnets + shared services range)
   b. If peer is MikroTik with auto-deploy enabled:
      - Create deployment job
      - Queue for automatic deployment
   c. If peer is non-MikroTik or MikroTik without auto-deploy:
      - Generate appropriate config format (standard/mikrotik-script/etc.)
      - Save to Configuration History
      - Mark as pending manual application
3. Return summary of generated configs and queued jobs
```

### 9.5 Service Publishing Logic
```
Function: publish_service(peer_id, local_ip, local_port, shared_port)
1. Allocate shared_service_ip from shared services range
2. Create Published Service record
3. Generate NAT/port forwarding rules for peer's device
4. If peer is MikroTik with auto-deploy:
   a. Create deployment job to add NAT rules
   b. Queue for automatic deployment
5. Update all other peers' AllowedIPs to include new shared_service_ip
6. For each peer:
   - If MikroTik with auto-deploy: queue deployment job
   - If non-MikroTik: regenerate configuration file
7. Return service details and deployment status
```

### 9.6 MikroTik API Client Logic
```
Class: MikroTikAPIClient

Methods:
- test_connection() → Returns (success: bool, router_identity: str, version: str)
- get_wireguard_interfaces() → Returns list of interfaces
- get_wireguard_peers(interface_name) → Returns list of peers
- create_wireguard_interface(config) → Returns interface ID
- update_wireguard_interface(id, config) → Returns success bool
- create_wireguard_peer(config) → Returns peer ID
- update_wireguard_peer(id, config) → Returns success bool
- delete_wireguard_peer(id) → Returns success bool
- get_ip_addresses(interface) → Returns list of addresses
- create_ip_address(config) → Returns address ID
- get_routes(comment_filter) → Returns list of routes
- create_route(config) → Returns route ID
- delete_route(id) → Returns success bool
- get_firewall_rules(chain, comment_filter) → Returns list of rules
- create_firewall_rule(chain, config) → Returns rule ID
- delete_firewall_rule(id) → Returns success bool
- get_nat_rules(comment_filter) → Returns list of rules
- create_nat_rule(config) → Returns rule ID
- delete_nat_rule(id) → Returns success bool

Error handling:
- Wrap all API calls in try-catch
- Return structured error responses
- Log all API interactions
- Implement retry logic for transient failures
- Handle rate limiting if applicable
```

---

## 10. Security Considerations

### 10.1 Key Management
- **Private keys**: Encrypted at rest in database (AES-256)
- **MikroTik credentials**: Encrypted at rest in database
- **API tokens**: Encrypted at rest, never logged
- **Key rotation**: Support regenerating keypairs for peers
- **Secure distribution**: Configs should be transmitted over HTTPS/TLS
- **Access control**: Only authorized users can view private keys and credentials

### 10.2 MikroTik API Security
- **Use HTTPS**: Always connect via SSL/TLS (port 443)
- **Certificate validation**: Option to disable for self-signed certs
- **Credential storage**: Encrypt passwords and tokens in database
- **API token preference**: Recommend tokens over passwords
- **Least privilege**: Use API users with minimal required permissions
- **Connection timeouts**: Set reasonable timeouts to prevent hanging
- **Rate limiting**: Respect API rate limits (if any)

### 10.3 Authentication & Authorization
- **Admin users**: Full access to all WAN networks and peers
- **Operator users**: Can add/edit peers but not delete WANs
- **Read-only users**: Can view configurations but not modify
- **API keys**: For programmatic access to API endpoints
- **MFA support**: Optional two-factor authentication

### 10.4 Audit Logging
Log all critical operations:
- Peer additions/deletions
- Configuration changes
- Key regeneration
- Conflict resolutions
- Service publications
- **MikroTik API calls** (all requests/responses)
- **Deployment job execution**
- **Configuration deployments and rollbacks**

### 10.5 Configuration Validation
Before generating configs:
- Validate all IP addresses and CIDR ranges
- Check for invalid characters in peer names
- Verify port numbers are in valid range
- Ensure public keys are valid base64 Wireguard keys
- Validate MikroTik credentials before saving
- Test API connectivity before enabling auto-deploy

### 10.6 Network Security
- Application should support running behind reverse proxy
- Support for Let's Encrypt SSL certificates
- CORS configuration for web-based deployment
- CSP headers to prevent XSS
- Input sanitization to prevent injection attacks

---

## 11. Advanced Features (Optional/Future)

### 11.1 Automated Monitoring
- Periodic connectivity checks to MikroTik routers
- Alert when API becomes unreachable
- Monitor Wireguard peer handshake timestamps
- Alert when peers go offline
- Bandwidth usage tracking per peer

### 11.2 Configuration Drift Detection
- Periodically query MikroTik configuration
- Compare actual vs. expected configuration
- Alert when drift detected
- Option to automatically remediate drift

### 11.3 Scheduled Deployments
- Schedule configuration deployments for off-hours
- Maintenance windows for bulk updates
- Automatic retry failed deployments

### 11.4 High Availability
- Support for multiple hub nodes with failover
- Automatic route updates on hub failure
- Health checking and automatic peer failover

### 11.5 Service Discovery
- DNS server for shared services (e.g., service1.wan.local → 10.0.5.10)
- Automatic DNS updates when services published
- mDNS/Avahi integration for local service discovery

### 11.6 Traffic Policies
- QoS/traffic shaping rules
- Bandwidth limits per peer or service
- Priority routing for critical services
- Deploy QoS rules via MikroTik API

### 11.7 Multi-WAN Support
- Manage multiple independent WAN overlays
- Inter-WAN routing (connect WANs together)
- WAN federation

### 11.8 Backup & Restore
- Backup entire WAN configuration to JSON/YAML
- Export MikroTik configurations
- Import/restore from backup
- Version control for configurations

### 11.9 Ansible/Terraform Integration
- Generate Ansible playbooks for deployment
- Terraform provider for infrastructure-as-code
- GitOps workflow support

### 11.10 Mobile App
- iOS/Android app for monitoring
- Push notifications for peer status changes
- QR code scanner for quick peer enrollment
- View deployment job status

---

## 12. Testing Requirements

### 12.1 Unit Tests
- IP allocation algorithms
- Conflict detection logic
- Configuration generation for each device type
- NAT rule generation
- Subnet overlap detection
- MikroTik API client methods
- Deployment job creation and execution

### 12.2 Integration Tests
- Full peer provisioning flow
- Service publication flow
- Conflict resolution flow
- Configuration update flow
- MikroTik API integration (with mock server)
- Deployment job queue processing

### 12.3 MikroTik-Specific Tests
- Test API connectivity with real router
- Test configuration deployment end-to-end
- Test non-destructive updates (verify existing configs preserved)
- Test rollback functionality
- Test concurrent deployments to multiple routers
- Test error handling for API failures

### 12.4 End-to-End Tests
- Create WAN network
- Add multiple peers (including MikroTik)
- Deploy configuration to MikroTik via API
- Publish services
- Verify connectivity between peers
- Test NAT conflict resolution
- Update configurations and verify changes propagate
- Test rollback after failed deployment

---

## 13. Documentation Requirements

### 13.1 User Documentation
- Installation guide (self-hosted deployment)
- Quick start tutorial
- How to add different peer types
- **How to configure MikroTik for API access**
- How to set up credentials for MikroTik peers
- How to publish services
- How to resolve conflicts
- Troubleshooting guide
- **MikroTik API troubleshooting guide**

### 13.2 MikroTik Setup Guide
Document must include:
- How to enable REST API on MikroTik RouterOS
- Creating API user with appropriate permissions
- Generating API tokens (if using token auth)
- SSL certificate considerations
- Firewall rules to allow API access
- Testing API connectivity with curl examples

### 13.3 API Documentation
- OpenAPI/Swagger specification
- Example requests/responses for all endpoints
- Authentication guide
- Webhook documentation (if implemented)
- **MikroTik API endpoint documentation**
- **Deployment job status codes and error messages**

### 13.4 Developer Documentation
- Architecture overview
- Database schema
- Configuration generation logic
- **MikroTik API client implementation details**
- **Deployment job queue architecture**
- Adding support for new device types
- Contributing guide

---

## 14. Success Criteria

The application should be considered successful when:

1. ✅ An admin can create a WAN network and add 10+ peers of mixed types
2. ✅ MikroTik peers can be configured automatically via REST API
3. ✅ Peers can connect and communicate through the Wireguard overlay
4. ✅ Peers can publish services to the shared services subnet
5. ✅ Other peers can access published services
6. ✅ The system detects and resolves subnet conflicts with NAT
7. ✅ MikroTik routers are configured via API without breaking existing configs
8. ✅ Configurations can be updated and deployed without downtime
9. ✅ Failed deployments can be rolled back automatically
10. ✅ The UI provides clear visibility into network topology and deployment status
11. ✅ The system scales to 50+ peers without performance degradation
12. ✅ Configuration changes propagate correctly to all affected peers
13. ✅ Deployment jobs are tracked and logged for audit purposes
14. ✅ Concurrent deployments to multiple MikroTik routers work reliably

---

## 15. Technology Recommendations

### 15.1 Backend
- **Language**: Python (FastAPI), Go, or Node.js (TypeScript)
  - Python recommended for MikroTik API client libraries
- **Database**: PostgreSQL (production) or SQLite (small deployments)
- **ORM**: SQLAlchemy (Python), GORM (Go), Prisma (Node.js)
- **API**: REST with OpenAPI spec
- **Job Queue**: Celery (Python), Bull (Node.js), or Asynq (Go)
- **Task Scheduler**: APScheduler (Python) or node-cron (Node.js)

### 15.2 MikroTik API Client Libraries
- **Python**: `librouteros` or `routeros-api`
- **Node.js**: `node-routeros`
- **Go**: Custom implementation using `net/http`
- **Fallback**: Use generic HTTP client with proper error handling

### 15.3 Frontend (if web-based)
- **Framework**: React, Vue 3, or Svelte
- **UI Library**: TailwindCSS, Material UI, or Ant Design
- **State Management**: Redux, Zustand, Pinia, or React Query
- **Real-time updates**: WebSocket or Server-Sent Events for deployment status
- **Visualization**: D3.js, Cytoscape.js, or vis.js for network topology

### 15.4 Desktop App (if native)
- **Framework**: Electron, Tauri, or Flutter
- **Benefits**: Tauri (smaller bundle, Rust backend), Electron (mature ecosystem)

### 15.5 Configuration Management
- **Libraries**: 
  - Wireguard config parsing/generation
  - CIDR manipulation (netaddr, go-cidr, ipaddress)
  - SSH client for remote deployment (paramiko, ssh2)
  - HTTP client with retry logic

### 15.6 DevOps
- **Containerization**: Docker for easy deployment
- **Orchestration**: Docker Compose or Kubernetes
- **CI/CD**: GitHub Actions, GitLab CI, or Jenkins
- **Queue Backend**: Redis or RabbitMQ

---

## 16. Implementation Phases

### Phase 1: Core Infrastructure (MVP)
- Database schema and models
- Basic API endpoints for WAN and Peer management
- IP allocation logic
- Standard Wireguard config generation
- Simple web UI for peer management

### Phase 2: MikroTik API Integration
- MikroTik API client implementation
- Connection testing functionality
- Basic configuration deployment
- Deployment job queue
- API call logging

### Phase 3: Service Exposure
- Published services functionality
- Shared services subnet management
- NAT/port forwarding rule generation
- Service registry UI
- Automatic deployment of NAT rules to MikroTik

### Phase 4: Advanced MikroTik Features
- Configuration diff and preview
- Rollback functionality
- Non-destructive update logic
- Concurrent deployment to multiple routers
- Configuration drift detection

### Phase 5: Conflict Resolution
- Subnet overlap detection
- NAT translation assignment
- Conflict resolution UI
- Automated NAT rule generation

### Phase 6: Polish & Production
- Network topology visualizer
- Monitoring and metrics
- Configuration history and rollback
- Multi-topology support (mesh, hybrid)
- Comprehensive testing
- Documentation
- Security audit
- Performance optimization

---

## 17. Example Use Cases

### Use Case 1: Connecting Remote Offices with MikroTik Routers
- Office A (192.168.1.0/24) in New York - MikroTik CCR
- Office B (192.168.2.0/24) in London - MikroTik hEX
- Office C (192.168.3.0/24) in Tokyo - MikroTik RB5009
- Each office MikroTik configured via API
- All offices need to access shared services
- File server in Office A published to 10.0.5.10
- Configuration deployed automatically via REST API

### Use Case 2: Mixed Environment
- MikroTik router at main office (auto-deployed)
- Linux servers in cloud (manual Wireguard config)
- Developer laptops (standard Wireguard clients)
- Database server published to 10.0.5.20
- API server published to 10.0.5.21
- MikroTik gets automatic updates, others get config files

### Use Case 3: Large Scale Deployment
- 50+ MikroTik routers across customer sites
- Central management server
- Bulk deployment to all routers
- Automatic conflict resolution with NAT
- Monitoring dashboard for all sites
- Automated rollback on deployment failures

---

## 18. Non-Functional Requirements

### 18.1 Performance
- Support 100+ concurrent peers
- Configuration generation < 2 seconds per peer
- API response times < 500ms for most operations
- **MikroTik API calls < 5 seconds per router**
- **Concurrent deployments: up to 10 routers simultaneously**
- UI should be responsive on modest hardware

### 18.2 Reliability
- Database backups and restore procedures
- Configuration history for rollback
- Graceful handling of network failures
- **Automatic retry for failed MikroTik API calls**
- **Job queue persistence** (survive application restarts)
- No single point of failure (where possible)

### 18.3 Usability
- Intuitive UI for non-technical users
- Clear error messages and validation
- Comprehensive help documentation
- Wizard-style flows for complex operations
- **Real-time deployment progress indicators**
- **Clear MikroTik connection status**

### 18.4 Maintainability
- Modular, well-documented code
- Clear separation of concerns
- Automated tests with >80% coverage
- Easy to add support for new device types
- **MikroTik API client abstraction for easy updates**

### 18.5 Security
- Secure by default configuration
- Regular security updates
- Minimal attack surface
- Audit logging for compliance
- **Encrypted credential storage**
- **Secure API communication (HTTPS only)**

---

## 19. Constraints & Assumptions

### Constraints
- Must work with standard Wireguard implementations
- MikroTik RouterOS v7+ required for REST API
- Limited to IPv4 (IPv6 as future enhancement)
- Users must have API access to their MikroTik routers
- MikroTik routers must be reachable from management server

### Assumptions
- Users have administrative access to their devices
- MikroTik routers have REST API enabled
- Devices have internet connectivity for initial setup
- Network administrators understand basic REST API concepts
- MikroTik routers are running recent RouterOS versions

---

## 20. Glossary

- **WAN Overlay**: Virtual network layer created on top of the internet using Wireguard
- **Peer**: Any device participating in the Wireguard WAN
- **Tunnel IP**: IP address used within the Wireguard tunnel itself
- **Shared Services Subnet**: Special IP range for services exposed to all WAN participants
- **Published Service**: A service from a local network made accessible via the shared services subnet
- **Hub**: Central coordination point in hub-spoke topology
- **Mesh**: Topology where peers connect directly to each other
- **NAT Translation**: Remapping one IP address space to another to resolve conflicts
- **AllowedIPs**: Wireguard configuration parameter defining which IPs can be routed through a peer
- **MikroTik REST API**: HTTP-based API for managing MikroTik RouterOS devices
- **Deployment Job**: Asynchronous task for applying configuration to a device
- **Configuration Drift**: Discrepancy between desired and actual device configuration
- **Rollback**: Reverting to a previous known-good configuration after failed deployment

---

## 21. MikroTik API Reference

### 21.1 Authentication Examples

**Basic Authentication:**
```python
import requests
import base64

username = "admin"
password = "password"
credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://192.168.88.1/rest/interface/wireguard",
    headers=headers,
    verify=False  # For self-signed certificates
)
```

**Token Authentication (Recommended):**
```python
token = "your-api-token-here"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://192.168.88.1/rest/interface/wireguard",
    headers=headers,
    verify=False
)
```

### 21.2 Common API Patterns

**Query with Filter:**
```python
# Get all Wireguard peers managed by this application
response = requests.get(
    "https://192.168.88.1/rest/interface/wireguard/peers",
    params={"comment": "WAN-Overlay-Manager"},
    headers=headers
)
```

**Create Resource:**
```python
# Create new Wireguard interface
data = {
    "name": "wg-wan-overlay",
    "listen-port": 51820,
    "private-key": "base64-key",
    "comment": "WAN-Overlay-Manager:uuid"
}

response = requests.post(
    "https://192.168.88.1/rest/interface/wireguard",
    json=data,
    headers=headers
)

# Response includes the new resource ID
new_id = response.json()[".id"]
```

**Update Resource:**
```python
# Update peer's allowed IPs
resource_id = "*1"  # ID from query
data = {
    "allowed-address": "10.0.0.2/32,192.168.2.0/24"
}

response = requests.patch(
    f"https://192.168.88.1/rest/interface/wireguard/peers/{resource_id}",
    json=data,
    headers=headers
)
```

**Delete Resource:**
```python
# Remove peer
resource_id = "*1"

response = requests.delete(
    f"https://192.168.88.1/rest/interface/wireguard/peers/{resource_id}",
    headers=headers
)
```

### 21.3 Error Response Format

MikroTik API returns errors in this format:
```json
{
  "error": 400,
  "message": "failure: already have such entry",
  "detail": "interface wireguard name wg-wan-overlay already exists"
}
```

Application should parse these errors and provide user-friendly messages.

---

## 22. Deployment Checklist

Before deploying to production:

### 22.1 MikroTik Router Preparation
- [ ] Enable REST API on MikroTik
- [ ] Create dedicated API user
- [ ] Generate API token (optional but recommended)
- [ ] Configure SSL certificate or accept self-signed
- [ ] Allow API access from management server IP
- [ ] Test API connectivity with curl

### 22.2 Application Setup
- [ ] Deploy application backend
- [ ] Configure database connection
- [ ] Set up job queue (Redis/RabbitMQ)
- [ ] Configure encryption keys for credential storage
- [ ] Set up SSL/TLS for web interface
- [ ] Configure authentication (users, roles)
- [ ] Test MikroTik API connectivity

### 22.3 Network Configuration
- [ ] Ensure management server can reach MikroTik routers
- [ ] Configure firewalls to allow Wireguard ports
- [ ] Plan IP addressing scheme (tunnel IPs, shared services)
- [ ] Document network topology

### 22.4 Testing
- [ ] Test peer registration (all types)
- [ ] Test MikroTik API deployment
- [ ] Test service publishing
- [ ] Test conflict detection and resolution
- [ ] Test rollback functionality
- [ ] Verify non-destructive updates
- [ ] Load testing with multiple concurrent deployments

---

**End of Specification Document**

This comprehensive specification provides everything needed to build a Wireguard WAN overlay management application with full MikroTik REST API integration. The LLM agent can use this document to understand all requirements, data models, API interactions, and implementation details necessary for development.
