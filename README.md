# NetMap - Network Tree Status Monitor

NetMap is a high-performance, resource-efficient network status monitoring system built with Python and FastAPI. It periodically polls network targets with parallel ICMP pings (user-configurable concurrency) and displays their real-time and historical health in an at-a-glance, widescreen-optimized (720p/1080p) **left-to-right tree hierarchy**.

---

## 🌟 Key Features

### 🖥️ Visualization & Dashboard
- **Widescreen Left-to-Right Hierarchy**: Network nodes flow horizontally from root devices (gateways/routers) to distribution switches and leaf services, categorized by geographical Location.
- **Ultra-Compact (20px) vs Tall Modes**: Switch between an ultra-dense 20px uniform card mode (ideal for large multi-site NOC video walls) and a comfortable Tall mode with visible IP badges and latency stats.
- **Collapsible Location Sections**: Click any location name header to collapse or expand its entire tree into a compact single row displaying live online, degraded, and offline counters. Includes **"⇲ Collapse All"** and **"⇱ Expand All"** toolbar controls.
- **Location Pinning**: Click the pin icon (`📌`) on any location card to pin priority sites to the top of your dashboard. Pins persist across browser sessions in `localStorage`.
- **Location Bar Warning Marks**: Visual warning badges in the top location bar alert operators when devices in a site go offline (Yellow badge when <50% of devices are down; Red badge when ≥50% are down).
- **6-Hour Instability Tracking**: Even when a host or group is currently UP, recent downtime in the past 6 hours is tracked and highlighted with color-coded warning styles and a lightning bolt (`⚡`) indicator in the location bar:
  - **Greenish-Yellow (Lime)**: > 10% downtime in the past 6 hours.
  - **Yellow**: > 30% downtime in the past 6 hours.
  - **Red**: > 50% downtime in the past 6 hours.
- **Bilingual Interface**: Full, seamless localization in Brazilian Portuguese (`pt-BR`, default) and English (`en`).

### 📊 Micro-Graphs & Time-Series History
- **30-Minute Micro-Graph (Sparkline)**: Embedded directly inside every host and group card, showing individual polling cycles with color-coded status blocks.
- **Interactive Timeline Browser**: Click any host card to inspect its uptime percentage, interactive time-series timeline, and incident logs:
  - **Configurable Time Windows**: Switch between **6h**, **12h**, **24h**, and **48h** analysis windows.
  - **Time Travel & Pagination**: Navigate backwards and forwards in time to the earliest record stored in the database.
  - **Intelligent State Compression**: Automatically condenses long periods of unchanging availability into clean overview blocks with start and end timestamps displayed on mouse hover.
  - **Time Scale Bar**: Visual timeline header showing relative timestamps across the viewing window.

### 👥 Host Grouping & Aggregation
- Combine multiple redundant hosts into a single composite entity on the tree (e.g. server clusters, dual-homed firewalls, ISP uplinks):
  - **`any` mode**: Group is considered UP if at least one member is online (Failover/HA).
  - **`all` mode**: Group is considered UP only if ALL members are online (Strict cluster).
  - **Degraded (Yellow)**: Group is visually highlighted as partially up when a subset of members are offline.
  - **Averaged Group Sparklines**: Member metrics are aggregated into uniform rounds reflecting composite availability.

### ⚡ Parallel Ping Engine & Efficiency
- **Non-blocking ICMP Subprocess Pool**: Parallel ping workers bounded by an `asyncio.Semaphore` with configurable concurrency (`ping_threads`).
- **Zombie Process & Leak Protection**: Subprocesses that exceed timeout limits are explicitly terminated (`SIGKILL`) and awaited to prevent orphaned zombie processes or file descriptor leaks.
- **Efficient Hourly Retention Pruning**: History cleanup is decoupled from frequent poll loops, running once per hour to minimize SQLite disk write churn.
- **Safe Batch Querying**: Large inventory queries are automatically chunked in batches of 500 to prevent hitting SQLite parameter limits (`SQLITE_LIMIT_VARIABLE_NUMBER`).

### 🔒 Security, Hardening & Data Integrity
- **Dual SQLite Database Architecture with WAL Mode**:
  - `data/hosts.db`: Stores inventory, locations, parent-child tree hierarchy, groups, user credentials, and session tokens with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) and foreign key enforcement (`PRAGMA foreign_keys=ON;`).
  - `data/history.db`: High-speed time-series ping history with indexing on `(host_id, timestamp DESC)` and automatic retention pruning.
- **Strict Input Sanitization & Bounds**:
  - Pydantic models enforce string lengths and numeric boundaries on all incoming API payloads.
  - IP and hostname targets are validated against strict IPv4/IPv6 parsers and FQDN regex rules, blocking command flag injection and control characters.
  - Safe HTML escaping across all DOM renderers without raw string interpolation in inline event handlers.
  - CSV file and form field uploads are constrained with a 10MB maximum payload limit to prevent memory exhaustion.
- **Admin Lockout Protection**: The system prevents deleting or demoting the last administrator account, ensuring the admin portal is never accidentally locked.
- **HTTP Security Headers**: Outgoing responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Role-Based Access Control**:
  - **Public**: Read-only dashboard and timeline inspection.
  - **Operator**: Authorized to trigger immediate on-demand polling cycles ("⚡ Force Poll").
  - **Admin**: Full control over host inventory, groups, CSV import/export, system settings, and user management.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Server
```bash
python3 run.py
```
Or directly using Uvicorn:
```bash
uvicorn netmap.main:app --host 0.0.0.0 --port 8080
```

### 3. Open in Browser
- **Public Network Dashboard**: `http://localhost:8080/`
- **Administration Portal**: `http://localhost:8080/admin`

---

## 📦 Ubuntu Server Deployment (Production)

For automated deployment on **Ubuntu Server** without Docker, run the zero-configuration installer:

```bash
sudo ./install.sh
```

This automated script uses Ubuntu's native `apt` package manager to install system dependencies (`python3`, `python3-pip`, `python3-venv`, `iputils-ping`), builds an isolated virtual environment with `pip`, and registers a background daemon service (`netmap.service`) via `systemd` with automatic restart on boot.

For detailed manual instructions, Nginx reverse proxy configurations (both domain root and `/netmap/` subpath), and firewall rules, see [DEPLOYMENT.md](file:///Extra/git/netmap/DEPLOYMENT.md).

---

## 🔐 Default Credentials

| Username | Password | Role | Permissions |
|---|---|---|---|
| `admin` | `admin123` | Administrator | Full access: host editing, CSV import, configuration, force poll |
| `operator` | `operator123` | Operator | Can trigger manual **Force Poll** from the main dashboard |

*(You can change passwords or add new users anytime from the Admin Portal > Users tab).*

---

## ⚙️ Configuration (`netmap.cfg`)

All variables can be edited either directly in `netmap.cfg` or dynamically in the Web Admin Portal (**Settings** tab):

```ini
[server]
host = 0.0.0.0
port = 8080
secret_key = netmap-secret-key-change-in-production
url_prefix = 

[poller]
# Polling interval in seconds (default 60s, min 5s)
interval_seconds = 60
# Number of parallel ping workers / threads (default 20)
ping_threads = 20
# Ping timeout in seconds (default 2s)
ping_timeout = 2
# Number of packets per ping (default 1)
ping_count = 1

[history]
# History retention in hours (minimum 24h, default 48h)
retention_hours = 48

[database]
hosts_db = data/hosts.db
history_db = data/history.db
```

---

## 📂 CSV Import Format

You can bulk-import hosts from the Admin Portal (`/admin` > **CSV Import / Export** tab) or using `sample_hosts.csv`:

```csv
name,ip_address,location,parent,grouping,group_mode,description
Core-Router-HQ,192.168.1.1,HQ Datacenter,,,any,Main Gateway
Dist-Switch-1,192.168.1.2,HQ Datacenter,Core-Router-HQ,,,Distribution Switch 1
Dist-Switch-2,192.168.1.3,HQ Datacenter,Core-Router-HQ,,,Distribution Switch 2
Web-Node-01,192.168.1.10,HQ Datacenter,Dist-Switch-1,Web-Cluster,any,Primary web frontend
Web-Node-02,192.168.1.11,HQ Datacenter,Dist-Switch-1,Web-Cluster,any,Secondary web frontend
DB-Primary,192.168.1.20,HQ Datacenter,Dist-Switch-2,DB-Cluster,all,Database Primary
DB-Replica,192.168.1.21,HQ Datacenter,Dist-Switch-2,DB-Cluster,all,Database Replica
```

- **parent**: Can be either the host's numerical ID or exact parent name. The importer automatically resolves relationships regardless of row ordering.
- **group_mode**:
  - `any`: At least one host in the group is UP $\rightarrow$ Group is UP (Failover/HA).
  - `all`: All hosts in the group must be UP $\rightarrow$ Group is UP (Strict cluster).

---

## 🧪 Running Automated Tests

Run the test suite with pytest:
```bash
source .venv/bin/activate
PYTHONPATH=. pytest -v
```
