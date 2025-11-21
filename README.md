# WireWAN

### WireGuard WAN Overlay Network Manager

[![Vibe Coded](https://img.shields.io/badge/Vibe-Coded-blueviolet?style=for-the-badge&logo=artificial-intelligence&logoColor=white)](https://en.wikipedia.org/wiki/Vibe_coding)
[![Built with Claude](https://img.shields.io/badge/Built%20with-Claude-cc785c?style=for-the-badge&logo=anthropic&logoColor=white)](https://claude.ai)
[![Powered by Codex](https://img.shields.io/badge/Powered%20by-Codex-10a37f?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/codex)

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.2-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![WireGuard](https://img.shields.io/badge/WireGuard-VPN-88171a?style=flat-square&logo=wireguard&logoColor=white)](https://wireguard.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## About This Project

**WireWAN** is a web application for creating and managing WireGuard-based overlay networks across multiple sites, with automatic configuration deployment to MikroTik routers via their REST API.

### Built Entirely with AI

This project was **100% vibe coded** - written entirely through conversations with AI assistants:

- **[Claude](https://claude.ai)** (Anthropic) - Architecture, backend implementation, security review
- **[Codex](https://openai.com/codex)** (OpenAI) - Code generation and iteration

No line of code was written manually. This project serves as a demonstration of what's possible when leveraging AI for full-stack application development - from initial architecture decisions through implementation, testing, and security hardening.

> *"Vibe coding"* - The practice of building software through natural language conversations with AI, describing what you want and iterating on the results.

---

## What Does It Do?

WireWAN solves the complexity of managing WireGuard VPN networks across multiple locations. Instead of manually configuring each router and keeping configurations in sync, WireWAN provides:

| Feature | Description |
|---------|-------------|
| **Centralized Management** | Single dashboard for all your WireGuard peers and networks |
| **Automatic IP Allocation** | No more spreadsheets - tunnel IPs assigned automatically |
| **Config Generation** | Creates WireGuard configs for any device type |
| **MikroTik Auto-Deploy** | Push configurations directly to RouterOS 7+ devices |
| **Conflict Detection** | Warns when subnets overlap, suggests NAT solutions |
| **Network Visualization** | Interactive topology map of your overlay network |
| **Deployment History** | Track what was deployed, when, with rollback capability |

### Use Cases

- **Multi-site business networks** - Connect offices, warehouses, remote workers
- **Homelab enthusiasts** - Link home servers, VPS instances, cloud resources
- **MSPs/IT consultants** - Manage client networks from a single interface
- **IoT deployments** - Secure connectivity for distributed devices

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      WireWAN Server                          │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React + TypeScript)  │  Backend (FastAPI)        │
│  ├─ Dashboard & Topology View   │  ├─ REST API              │
│  ├─ Peer Management UI          │  ├─ MikroTik API Client   │
│  ├─ Deployment Job Monitor      │  ├─ WireGuard Key Gen     │
│  └─ D3.js Network Graph         │  └─ Config Generator      │
├─────────────────────────────────────────────────────────────┤
│              SQLite / PostgreSQL Database                    │
│         (Encrypted credentials, config history)              │
└─────────────────────────────────────────────────────────────┘
              │                              │
              │ RouterOS REST API           │ Generated .conf files
              ▼                              ▼
     ┌─────────────────┐            ┌─────────────────┐
     │ MikroTik        │            │ Other Devices   │
     │ Routers         │            │ (Linux, etc.)   │
     │ (auto-deploy)   │            │ (manual apply)  │
     └─────────────────┘            └─────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10+ (managed via [UV](https://docs.astral.sh/uv/))
- Node.js 18+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/wirewan.git
cd wirewan

# Run setup (installs Python and Node dependencies)
./run.sh setup

# Start the backend (terminal 1)
./run.sh backend

# Start the frontend (terminal 2)
./run.sh frontend
```

Open **http://localhost:3000** in your browser.

### Docker Deployment

```bash
# Generate required secrets first
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('ENCRYPTION_SALT=' + secrets.token_urlsafe(16))"
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# Create .env file with generated values, then:
docker-compose up -d
```

---

## Security Configuration

### Required Environment Variables

WireWAN requires three security-related environment variables. The application **will not start** without them.

| Variable | Purpose | Generate With |
|----------|---------|---------------|
| `ENCRYPTION_KEY` | Encrypts stored credentials & private keys | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ENCRYPTION_SALT` | Unique salt for key derivation | `python -c "import secrets; print(secrets.token_urlsafe(16))"` |
| `SECRET_KEY` | Signs JWT authentication tokens | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

### Setup

Add to `backend/.env`:

```bash
ENCRYPTION_KEY=your-generated-key-here
ENCRYPTION_SALT=your-generated-salt-here
SECRET_KEY=your-generated-secret-here
```

### Important Warnings

- **Never change these values after storing data** - encrypted credentials become unrecoverable
- **Back up these values securely** - treat them like database passwords
- **Use unique values per installation** - never copy between deployments

---

## Security Considerations

> **Target Audience:** This application is designed for use by a **single trusted party** or small team managing their own infrastructure. It is not designed for multi-tenant SaaS deployment.

### Implemented Security Measures

| Measure | Implementation |
|---------|----------------|
| Credential Encryption | Fernet symmetric encryption with PBKDF2 key derivation |
| Password Hashing | bcrypt via passlib |
| Authentication | JWT tokens with configurable expiration |
| Input Validation | Pydantic schemas with CIDR/port validators |
| SQL Injection Prevention | SQLAlchemy ORM with parameterized queries |
| Audit Logging | MikroTik API calls logged for troubleshooting |
| Key Generation | Cryptographically secure X25519 for WireGuard keys |

### Known Limitations (Acceptable for Target Use Case)

The following items were identified during security review but are **intentional trade-offs** for the target use case of single-party/trusted deployment:

| Item | Status | Rationale |
|------|--------|-----------|
| **No rate limiting** | Not implemented | Single trusted user; add nginx rate limiting if exposed |
| **7-day JWT expiration** | By design | Convenience for trusted operators; reduce if needed in config |
| **localStorage token storage** | Acceptable | XSS risk minimal for single-user; no sensitive multi-tenant data |
| **Debug mode default** | Development convenience | Set `DEBUG=false` in production `.env` |
| **MikroTik SSL verification off by default** | Usability | Most homelabs use self-signed certs; enable `verify_cert` for production |
| **CORS localhost only** | Development default | Configure `CORS_ORIGINS` for production domains |
| **First user becomes admin** | Bootstrap mechanism | Appropriate for single-party deployment |

### Production Hardening Checklist

If deploying in a more security-sensitive environment:

- [ ] Set `DEBUG=false`
- [ ] Configure production `CORS_ORIGINS`
- [ ] Put behind reverse proxy with HTTPS (nginx, Caddy, Traefik)
- [ ] Enable MikroTik `verify_cert=true` with proper certificates
- [ ] Reduce `ACCESS_TOKEN_EXPIRE_MINUTES` if desired
- [ ] Set up regular database backups
- [ ] Consider PostgreSQL instead of SQLite for concurrent access

---

## How It Works

### MikroTik Integration

WireWAN connects to MikroTik routers via the RouterOS REST API (port 443):

```
WireWAN ──HTTPS──> MikroTik REST API
                        │
                        ├── Creates WireGuard interface
                        ├── Configures peers with public keys
                        ├── Assigns tunnel IP addresses
                        ├── Adds routes to peer subnets
                        ├── Configures firewall rules
                        └── Sets up NAT if needed
```

**Requirements:**
- RouterOS 7.0+
- HTTPS enabled (`/ip service set www-ssl disabled=no`)
- API user with full permissions

### Other Devices

For non-MikroTik devices, WireWAN generates standard WireGuard configuration files:

- **`.conf` files** - For `wg-quick` on Linux/macOS/Windows
- **`.rsc` scripts** - For manual paste into MikroTik terminal

---

## Network Topologies

### Mesh (Default)
```
    A ──── B
    │ ╲  ╱ │
    │  ╲╱  │
    │  ╱╲  │
    │ ╱  ╲ │
    C ──── D
```
Every peer connects to every other peer. Best for small networks (<10 peers).

### Hub and Spoke
```
        A
        │
    B ─ HUB ─ C
        │
        D
```
All traffic routes through a central hub. Best for larger networks or NAT scenarios.

### Hybrid
Hub-and-spoke with selective direct connections between specific peers.

---

## API Documentation

Interactive API docs available at **http://localhost:8000/docs** (Swagger UI)

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/wan` | List all WAN networks |
| `POST` | `/api/wan` | Create a new WAN network |
| `GET` | `/api/peers/wan/{id}` | List peers in a WAN |
| `POST` | `/api/peers/wan/{id}` | Add peer to a WAN |
| `GET` | `/api/peers/{id}/config` | Download WireGuard config |
| `POST` | `/api/peers/{id}/mikrotik/test-connection` | Test router connectivity |
| `POST` | `/api/peers/{id}/mikrotik/deploy` | Deploy config to router |
| `GET` | `/api/jobs` | List deployment jobs |

---

## Tech Stack

### Backend
- **FastAPI** - Async Python web framework
- **SQLAlchemy 2.0** - Async ORM with type hints
- **Pydantic v2** - Data validation and settings
- **librouteros** - MikroTik API client
- **cryptography** - Fernet encryption, X25519 keys
- **python-jose** - JWT token handling

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tooling
- **TanStack Query** - Server state management
- **D3.js** - Network topology visualization
- **Tailwind CSS** - Styling

### Infrastructure
- **Docker** - Containerization
- **SQLite** - Default database (PostgreSQL supported)
- **Prometheus** - Metrics endpoint

---

## Troubleshooting

### MikroTik Connection Failed

1. Verify HTTPS is enabled: `/ip service print`
2. Check credentials work in WebFig
3. Ensure port 443 is accessible from WireWAN server
4. Confirm RouterOS version is 7.0+

### Peers Can't Establish Tunnel

1. Verify public endpoints are correct and reachable
2. Check UDP port forwarding through NAT
3. Confirm firewall allows WireGuard port
4. Validate public keys match on both sides

### Subnet Conflict Warnings

Options:
1. Renumber one of the conflicting subnets
2. Enable NAT translation in WireWAN
3. Mark subnet as "not routed" to exclude from overlay

---

## Contributing

This project was created as an AI coding demonstration. Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

This project exists thanks to the capabilities of modern AI assistants. Special thanks to:

- **Anthropic's Claude** - For thoughtful architecture discussions and security analysis
- **OpenAI's Codex** - For rapid code generation and iteration
- The **WireGuard** project - For creating an elegant VPN protocol
- **MikroTik** - For RouterOS and its comprehensive API

---

<p align="center">
  <i>Built with AI, for humans managing networks.</i>
</p>
