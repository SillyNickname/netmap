# NetMap - Network Tree Status Monitor

NetMap is a high-performance, resource-efficient network status monitoring system built with Python and FastAPI. It periodically polls network targets with parallel pings (user-configurable thread concurrency) and displays their real-time and historical health in an at-a-glance, widescreen-optimized (720p/1080p) **left-to-right tree hierarchy**.

---

## 🌟 Key Features

- **Widescreen Left-to-Right Hierarchy**: Network nodes flow horizontally from root devices (gateways/routers) to distribution switches and leaf services, categorized by geographical Location.
- **Parallel Ping Engine**: Asynchronous ping workers with user-configurable concurrency limits (`ping_threads`) using non-blocking ICMP pinging.
- **30-Minute Micro-Graph / Sparkline**: Embedded in each host node card for immediate at-a-glance trend analysis.
- **24h+ Interactive Host Timeline**: Click any host card to view its uptime percentage, interactive time-series timeline, and downtime incident log.
- **Host Groupings & Aggregation**: Combine multiple hosts into a single health entity with configurable aggregation logic (`any` for HA/failover redundancy or `all` for strict cluster health).
- **Dual SQLite Database Architecture**:
  - `data/hosts.db`: Stores inventory, locations, parent-child tree hierarchy, groups, user credentials, and session tokens with WAL mode enabled.
  - `data/history.db`: Stores high-speed time-series ping history with automatic scheduled retention pruning (configurable retention limit, minimum 24h).
- **Public & Role-Protected Access**:
  - **Public Dashboard**: Read-only access to network tree and host timelines.
  - **Operators / Authenticated Users**: Can trigger on-demand "⚡ Force Poll" cycles.
  - **Administrators**: Password-protected management portal to edit inventory, configure groups, upload CSV files, adjust settings, and manage user accounts.
- **CSV Bulk Import & Export**: One-click import and export of network inventory with automatic resolution of parent hierarchies and groups.
- **External Configuration**: Full runtime control via `netmap.cfg` or the admin web interface.

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

[poller]
# Polling interval in seconds (default 60s)
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
Web-Node-01,192.168.1.10,HQ Datacenter,Dist-Switch-1,Web-Cluster,any,Primary web frontend
Web-Node-02,192.168.1.11,HQ Datacenter,Dist-Switch-1,Web-Cluster,any,Secondary web frontend
DB-Primary,192.168.1.20,HQ Datacenter,Dist-Switch-1,DB-Cluster,all,Database Primary
DB-Replica,192.168.1.21,HQ Datacenter,Dist-Switch-1,DB-Cluster,all,Database Replica
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
