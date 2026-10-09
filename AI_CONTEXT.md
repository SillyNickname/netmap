# NetMap - AI Context & Development Guide

> **Purpose**: This file contains critical architectural context, hard constraints, design patterns, testing conventions, and domain knowledge for AI assistants (and human developers) working on NetMap. Read this file before proposing or making changes.

---

## 1. Project Overview & Identity

- **Project Name**: NetMap (Network Tree Status Monitor)
- **Developer / Author**: Antigravity (Google DeepMind)
- **Requested & Commissioned by**: André Kajita (`kajita@univap.br`)
- **Institution**: Universidade do Vale do Paraíba (UNIVAP)
- **Repository**: `https://git.fve.edu.br/kajita/netmap.git`
- **Current Version**: `1.1.0` (Release tag: `1.1-rc8`)
- **Primary Use Case**: High-performance, lightweight, real-time ICMP ping and reachability status dashboard designed for Network Operations Centers (NOC), video walls (720p/1080p), and system administrators.

---

## 2. Absolute Architectural Constraints (DO NOT VIOLATE)

1. **NO DOCKER UNDER ANY CIRCUMSTANCE**:
   - The application must run **strictly natively** on Linux bare-metal or virtual machines.
   - Do **NOT** create `Dockerfile`, `docker-compose.yml`, container configs, or suggest containerized workflows.
   - Service daemons are managed via **systemd**, **SysVinit / LSB** (`/etc/init.d/netmap`), or **OpenRC** (`/etc/init.d/netmap`).

2. **REVERSE PROXY & SUBPATH COMPATIBILITY**:
   - NetMap frequently runs behind an Nginx reverse proxy under a specific URL prefix (e.g., `https://<domain>/netmap`).
   - The ASGI application uses `ReverseProxyPrefixMiddleware` (`netmap/main.py`) which inspects `X-Forwarded-Prefix`, `X-Forwarded-Proto`, and `X-Forwarded-For`.
   - In frontend code (`static/js/app.js`, `static/js/admin.js`), never hardcode absolute root paths like `fetch('/api/...')`. Always prefix endpoints with `APP_BASE` (initialized from `window.NETMAP_BASE`).
   - In HTML templates, always reference static files and endpoints using `{{ base_path }}/static/...`.

3. **COMMIT PROTOCOL & AUTHORSHIP**:
   - `COMMIT` is used as a staging file to prepare git commit messages; it must **NOT** be kept or committed into the repository directory.
   - Every file header must preserve the authorship:
     ```
     Developed by: Antigravity (Google DeepMind)
     Requested and commissioned by: Andre Kajita <kajita@univap.br>
     ```

4. **TEST SUITE INTEGRITY**:
   - All tests in `tests/test_api.py` and `tests/test_netmap.py` must pass (`PYTHONPATH=. .venv/bin/pytest -v`).

---

## 3. Technology Stack & Runtime

- **Runtime**: Python 3.8+ (isolated within Python virtual environment `.venv/`).
- **Web Framework**: FastAPI + Starlette + Uvicorn (ASGI event loop).
- **Template Engine**: Jinja2 (`templates/index.html`, `templates/admin.html`).
- **Databases**: SQLite (WAL mode enabled via `aiosqlite`):
  - `data/hosts.db`: Inventory, locations, tree hierarchies, groups, user credentials, sessions.
  - `data/history.db`: High-frequency time-series ping poll samples.
- **Frontend**: Pure modern vanilla JavaScript (ES6+), CSS3 Grid & Flexbox, HTML5 (no Node.js/Webpack build steps).
- **Supported Linux Distributions**:
  - Ubuntu (20.04, 22.04, 24.04+)
  - Debian (10, 11, 12+)
  - RHEL, CentOS, Rocky Linux, AlmaLinux, Fedora
  - openSUSE Leap / Tumbleweed / SLES
  - Alpine Linux (OpenRC)
  - Arch Linux

---

## 4. Codebase Directory Structure

```
netmap/
├── AI_CONTEXT.md             # This AI guidance and context file
├── DEPLOYMENT.md             # Multi-distro Linux production deployment manual
├── README.md                 # Comprehensive project documentation
├── install.sh                # Interactive and non-interactive multi-distro installer
├── uninstall.sh              # Service uninstaller & cleanup script
├── netmap.cfg                # Application configuration file (INI format)
├── netmap.service            # Systemd service unit definition
├── run.py                    # Server startup script (auto-detects and switches to .venv)
├── sample_hosts.csv          # Sample CSV format for bulk inventory import
├── netmap/
│   ├── __init__.py           # Package version and metadata
│   ├── config.py             # Config class: INI loader, default generator, live saver
│   ├── db.py                 # SQLite WAL connection managers, schema initialization, migrations
│   ├── auth.py               # Password hashing (bcrypt), session tokens, RBAC dependencies
│   ├── models.py             # Pydantic request models with strict bounds and regex
│   ├── ping_engine.py        # ICMP ping subprocess pool, zombie protection, group evaluation
│   ├── speedtest_daemon.py   # Standalone lightweight async HTTP speedtest daemon (raw streams)
│   ├── csv_handler.py        # CSV import/export with parent resolution and cycle checks
│   ├── main.py               # FastAPI app, ReverseProxyPrefixMiddleware, security headers
│   └── api/
│       ├── public.py         # Public read-only endpoints (topology, status, timeline, ranges)
│       ├── poll.py           # On-demand force-poll trigger endpoint
│       ├── auth.py           # Login, logout, session verification
│       ├── admin.py          # CRUD endpoints for hosts, groups, locations, settings, users
│       └── speedtest.py      # Speedtest endpoints: config, ping, download, upload, results
├── scripts/
│   ├── netmap-ctl            # Unified server management CLI (start, stop, restart, status, logs, nginx)
│   ├── netmap-speedtest-daemon # Standalone speedtest daemon launcher wrapper
│   ├── init.d/netmap         # SysVinit / LSB service script
│   ├── openrc/netmap         # OpenRC service script for Alpine Linux
│   ├── start.sh              # Direct start wrapper
│   ├── stop.sh               # Direct stop wrapper
│   ├── restart.sh            # Direct restart wrapper
│   └── status.sh             # Direct status wrapper
├── static/
│   ├── css/
│   │   ├── netmap.css        # Dashboard styling, dark NOC theme, compact/tall modes, badges
│   │   └── speedtest.css     # Speedometer gauge, animated needle, bar chart, and metrics
│   └── js/
│       ├── app.js            # Main dashboard SPA logic, tree rendering, timeline browser
│       ├── admin.js          # Admin portal SPA logic, table sorting, modals, CRUD, speedtest results
│       ├── speedtest.js      # Speedtest runner: ping, download, upload, gauge animation, graph
│       └── i18n.js           # Bilingual localization dictionary (pt-BR default, en)
├── templates/
│   ├── index.html            # Main dashboard HTML template
│   ├── admin.html            # Admin dashboard HTML template
│   └── speedtest.html        # Standalone Speedtest HTML template
└── tests/
    ├── test_api.py           # API integration tests using AsyncClient
    ├── test_netmap.py        # Core unit tests (config, ping engine, CSV, auth)
    └── test_speedtest.py     # Speedtest tests (cooldown, auth bypass, daemon, streaming)
```

---

## 5. Key Domain Logic & Feature Behaviors

### 5.1 Ping Engine (`netmap/ping_engine.py`)
- **Concurrency**: Governed by `asyncio.Semaphore(config.ping_threads)` (default: 20 parallel workers).
- **Execution**: Uses `asyncio.create_subprocess_exec` running system `ping -c <count> -W <timeout> <target>`.
- **Zombie & Leak Prevention**:
  - Pings have a strict timeout (`wait_for`).
  - If a ping overruns, `proc.kill()` (`SIGKILL`) is issued and awaited with `proc.wait()`.
  - Piped stdout/stderr streams are drained and closed to avoid lingering file descriptors.
- **Target Sanitization**:
  - `is_valid_target(target)` strictly checks targets against IPv4/IPv6 (`ipaddress` module) or RFC 1123 hostname regex (`re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?...')`). Leading dashes or shell control characters are rejected immediately.
- **Hourly History Pruning**:
  - Decoupled from the rapid polling loop; runs once every 60 minutes.
  - Automatically deletes history rows older than `retention_hours` (default: 48 hours).
- **Batch Processing**:
  - History queries chunk IDs in batches of 500 to stay well under SQLite parameter limits (`SQLITE_LIMIT_VARIABLE_NUMBER`).

### 5.2 Host Grouping & Composite Entities
- Multiple targets can be assigned to a `grouping` name.
- **Modes**:
  - `any`: Group is UP if **at least 1** member is reachable (Failover/HA mode).
  - `all`: Group is UP only if **all** members are reachable (Strict cluster mode).
- **Degraded Status**: Displayed in yellow when a subset of members is down.
- **Sparkline Averaging**: Group sparkline rounds show an aggregated composite square representing round availability.

### 5.3 6-Hour Instability Tracking
- Even if a host or group is currently UP, the system calculates its downtime percentage over the past 6 hours (`past_6h_downtime_pct` in `/api/public.py`).
- **Card Tints & Warning Thresholds**:
  - **Greenish-Yellow (Lime)**: `> 10%` downtime in the past 6 hours.
  - **Yellow**: `> 30%` downtime in the past 6 hours.
  - **Red**: `> 50%` downtime in the past 6 hours.
- **Location Bar Marker**: A lightning bolt badge (`⚡`) appears in the top location bar if any devices in that location experienced instability in the last 6 hours.

### 5.4 Location Bar Offline Warning Marks
- In the top location navigation bar, visual badges alert operators when devices within a site go down:
  - **Yellow dot/badge**: `< 50%` of devices in the location are offline.
  - **Red dot/badge**: `≥ 50%` of devices in the location are offline.

### 5.5 Collapsible Locations & Pinning
- Clicking a location header collapses the tree section into a single compact bar showing live counts: Total, Online, Degraded, and Offline.
- Toolbar includes **"Collapse All"** (`⇲`) and **"Expand All"** (`⇱`).
- Clicking the pin icon (`📌`) moves that location to the top of the list. Pinned states persist in browser `localStorage`.

### 5.6 Interactive Timeline Browser (`static/js/app.js`)
- Clicking any device card opens a slide-out historical timeline modal.
- **Windows**: Switchable between **6h**, **12h**, **24h**, and **48h**.
- **Time-Travel Navigation**: Buttons allow shifting backwards and forwards in time by **6h**, **12h**, or **24h** increments back to the earliest recorded poll timestamp in the database.
- **Intelligent Steady-State Compression**:
  - If a device maintains the same state across multiple consecutive polls, those polls are condensed into a single visual block with start and end timestamps visible on hover.
  - Prevents thousands of DOM elements from degrading browser performance on dense historical views.
- **Time Scale Ruler**: Visual ruler header at the top of the timeline displaying relative timestamp benchmarks across the viewing window.

### 5.7 Internationalization (`static/js/i18n.js`)
- Supported languages: Brazilian Portuguese (`pt-BR`, default) and English (`en`).
- Language toggle persists in `localStorage.getItem("netmap_lang")`.
- Dynamic UI updates use `data-i18n` attributes and `applyTranslations()`.

### 5.8 Network Speed Measurer & Standalone Daemon (`/speedtest`)
- **Fast.com / Speedtest.net Interface**:
  - Dedicated modern page (`templates/speedtest.html`, `static/css/speedtest.css`, `static/js/speedtest.js`).
  - Animated SVG speedometer gauge with dynamic rotating needle, glowing sweep arc, dual real-time readouts (**Mbps** and **MB/s**).
  - Time-series throughput bar chart updating in real time across the 5-second download and 5-second upload phases.
  - Latency (ping round-trip time) and jitter measurement.
- **Uncompressed & Unbuffered Streaming**:
  - Endpoints (`/api/speedtest/download`, `/api/speedtest/upload`) and the standalone daemon explicitly disable compression (`Content-Encoding: identity`, `Cache-Control: no-store, no-cache`) to ensure genuine network throughput measurement without CPU gzip inflation.
- **Visitor Cooldown Rule**:
  - Unauthenticated visitors are subject to a **2-hour cooldown** enforced on the server by client IP address (`speedtest_results` SQLite table).
  - Attempts within the cooldown window return HTTP 429 with `cooldown_remaining_seconds`.
  - Frontend displays a countdown timer and informs visitors when their cooldown expires.
- **Operator & Admin Privileges**:
  - Operators and Administrators have **zero cooldown** (unlimited tests).
  - Both Operator and Admin roles can access the **Speedtest Results** tab in the Admin Portal to view and search historical tests by client IP.
  - Administrators can delete individual speedtest records.
- **Configurable Target, Auto-Reload & Standalone Daemon**:
  - Target server URL configured in `netmap.cfg` (`server_url`) or via Admin Settings tab — clients cannot choose or tamper with the target server.
  - Can point to local NetMap engine or a remote probe running `scripts/netmap-speedtest-daemon` (`netmap/speedtest_daemon.py`).
  - `Config` automatically reloads on disk modification (mtime tracking), allowing live target changes without service restarts.
  - `getTargetBase()` intelligently handles relative subpaths (`/netmap/speedtest/target`, `/speedtest/target`), full URLs, and warns on Mixed Content.

---

## 6. Security & Hardening Protocols

1. **Input Validation**:
   - Pydantic models (`netmap/models.py`) with string lengths, numeric ranges, and regex constraints on all endpoints.
   - Max 10MB limit on file and form uploads.
2. **SQL Injection Defense**:
   - 100% parameterized queries using `aiosqlite` with `?` placeholders. No string concatenation for SQL queries.
3. **HTTP Security Headers**:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: SAMEORIGIN`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: geolocation=(), camera=(), microphone=()`
4. **Admin Lockout Protection**:
   - Deleting or demoting the last remaining user with the `admin` role is explicitly blocked with HTTP 400.
5. **Role-Based Access Control**:
   - **Public**: Read-only access to dashboard, historical metrics, and rate-limited speed testing (2h cooldown).
   - **Operator**: Authorized to trigger `/api/poll/force` and view/search speedtest results with 0 cooldown.
   - **Admin**: Full access to settings, inventory, users, CSV import/export, and speedtest record deletion.

---

## 7. Developer & Testing Workflows

### 7.1 Virtual Environment
The virtual environment is located at `.venv/`.
Activate it before running commands:
```bash
source .venv/bin/activate
```

### 7.2 Running Automated Tests
Always specify `PYTHONPATH=.` when invoking pytest:
```bash
PYTHONPATH=. .venv/bin/pytest -v
```
All 24 tests pass without regressions:
- `tests/test_api.py` (11 tests: public APIs, auth, grouping, reverse proxy subpaths, admin sorting, warning levels, collapse controls, instability, admin lockout, security headers).
- `tests/test_netmap.py` (6 tests: config load/save, bcrypt auth, target validation, CSV import/hierarchy, ping engine, CSV purge).
- `tests/test_speedtest.py` (7 tests: config & ping, download/upload streaming, visitor cooldown enforcement, operator/admin bypass & search, admin deletion, page route, standalone daemon protocol).

*(Note: `test_ping_engine_execution` executes a real ICMP ping to `127.0.0.1`; in sandboxed environments that block ICMP sockets, run with network permissions/unsandboxed).*

### 7.3 Running the Development Server
```bash
python3 run.py
# Or directly via Uvicorn:
uvicorn netmap.main:app --host 0.0.0.0 --port 8080
```

### 7.4 Service Management via `netmap-ctl`
```bash
./scripts/netmap-ctl start
./scripts/netmap-ctl status
./scripts/netmap-ctl restart
./scripts/netmap-ctl stop
./scripts/netmap-ctl logs
./scripts/netmap-ctl nginx
```

---

## 8. Common Pitfalls for AI Assistants

1. **Never introduce Docker**: The user has strictly and repeatedly prohibited Docker. Always provide native Linux installation, systemd, SysVinit, or OpenRC solutions.
2. **Never break reverse proxy subpaths**: Any newly introduced route or static asset reference must function whether served at `/` or `/netmap/` or any custom subpath.
3. **Always preserve file headers**: When editing existing files or creating new ones, include the project header with authorship and commissioning information.
4. **Commit messages**: Prepare git commit messages based on user instructions, using `COMMIT` only as a temporary message file that is not committed to git.
