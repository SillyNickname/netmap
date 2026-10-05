#!/usr/bin/env bash
# ==============================================================================
# NetMap - Automated Installer & Production Service Setup
# Developed by: Antigravity (Google DeepMind)
# Requested and commissioned by: Andre Kajita <kajita@univap.br>
# ==============================================================================
# This script installs all required system packages, builds an isolated Python
# virtual environment, configures IP binding, port, and reverse proxy URL prefix,
# registers system service daemons, and provides control scripts.
#
# Supported Distributions:
#   - Ubuntu Server (20.04, 22.04, 24.04+)
#   - Debian (10, 11, 12+)
#   - Red Hat Enterprise Linux / CentOS / Rocky Linux / AlmaLinux / Fedora
#   - openSUSE / SLES
#   - Arch Linux
#   - Alpine Linux
#
# Usage:
#   sudo ./install.sh [OPTIONS]
#
# Options:
#   --host <IP>        Bind IP address (default: 0.0.0.0)
#   --port <PORT>      TCP Port number (default: 8080)
#   --prefix <PATH>    URL subpath prefix (default: /netmap, or empty for root)
#   --dir <DIR>        Installation directory (default: /opt/netmap)
#   --in-place         Install in current directory instead of /opt/netmap
#   -y, --yes          Non-interactive mode (use defaults or specified arguments)
#   -h, --help         Show this help message
# ==============================================================================

set -e

# ANSI Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================================${NC}"
echo -e "${BLUE}  NetMap - High-Performance Network Status Monitor Installer        ${NC}"
echo -e "${BLUE}====================================================================${NC}"

# Allow viewing help without root
for arg in "$@"; do
    if [ "$arg" = "-h" ] || [ "$arg" = "--help" ]; then
        echo "Usage: sudo $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --host <IP>        Bind IP address (default: 0.0.0.0)"
        echo "  --port <PORT>      TCP Port number (default: 8080)"
        echo "  --prefix <PATH>    URL subpath prefix (default: /netmap, or empty for root)"
        echo "  --dir <PATH>       Installation directory (default: /opt/netmap)"
        echo "  --in-place         Install in current directory"
        echo "  -y, --yes          Non-interactive mode (do not prompt for inputs)"
        echo "  -h, --help         Show this help message"
        exit 0
    fi
done

# 1. Root Check
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This installation script must be run as root (or with sudo).${NC}"
    echo "Usage: sudo ./install.sh [OPTIONS]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 2. Defaults
BIND_HOST=""
BIND_PORT=""
URL_PREFIX=""
INSTALL_DIR="/opt/netmap"
IN_PLACE=false
NON_INTERACTIVE=false

# 3. Parse Command-Line Options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            BIND_HOST="$2"
            shift 2
            ;;
        --port)
            BIND_PORT="$2"
            shift 2
            ;;
        --prefix)
            URL_PREFIX="$2"
            shift 2
            ;;
        --dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --in-place)
            IN_PLACE=true
            INSTALL_DIR="$SCRIPT_DIR"
            shift
            ;;
        -y|--yes|--non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        -h|--help)
            echo "Usage: sudo $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --host <IP>        Bind IP address (default: 0.0.0.0)"
            echo "  --port <PORT>      TCP Port number (default: 8080)"
            echo "  --prefix <PATH>    URL subpath prefix (default: /netmap, or empty for root)"
            echo "  --dir <PATH>       Installation directory (default: /opt/netmap)"
            echo "  --in-place         Install in current directory"
            echo "  -y, --yes          Non-interactive mode (do not prompt for inputs)"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}[ERROR] Unknown option: $1${NC}"
            echo "Run 'sudo $0 --help' for usage details."
            exit 1
            ;;
    esac
done

# 4. Interactive Configuration Prompts (if not non-interactive and running in terminal)
if [ "$NON_INTERACTIVE" = false ] && [ -t 0 ]; then
    echo -e "\n${BOLD}--- Network & Reverse Proxy Configuration ---${NC}"
    echo "Configure the network binding and URL path where NetMap will run."
    echo ""

    # IP Binding
    if [ -z "$BIND_HOST" ]; then
        read -p "IP Binding address (0.0.0.0 for all interfaces, 127.0.0.1 for local Nginx only) [0.0.0.0]: " USER_HOST
        BIND_HOST="${USER_HOST:-0.0.0.0}"
    fi

    # Port
    if [ -z "$BIND_PORT" ]; then
        read -p "Port number to listen on [8080]: " USER_PORT
        BIND_PORT="${USER_PORT:-8080}"
    fi

    # URL Prefix
    if [ -z "$URL_PREFIX" ]; then
        read -p "URL subpath prefix for Nginx (e.g., /netmap, or empty for domain root) [/netmap]: " USER_PREFIX
        URL_PREFIX="${USER_PREFIX:-/netmap}"
    fi
fi

# Apply fallbacks for any remaining unset variables
BIND_HOST="${BIND_HOST:-0.0.0.0}"
BIND_PORT="${BIND_PORT:-8080}"
if [ -z "$URL_PREFIX" ] && [ "$NON_INTERACTIVE" = true ]; then
    URL_PREFIX="/netmap"
fi

# Clean up URL prefix: ensure leading slash if not empty, strip trailing slashes
if [ -n "$URL_PREFIX" ]; then
    [[ "$URL_PREFIX" != /* ]] && URL_PREFIX="/$URL_PREFIX"
    URL_PREFIX="${URL_PREFIX%/}"
fi

echo -e "\n${CYAN}[CONFIG] Selected Installation Settings:${NC}"
echo -e "  Installation Directory: ${YELLOW}${INSTALL_DIR}${NC}"
echo -e "  Server IP Binding:      ${YELLOW}${BIND_HOST}${NC}"
echo -e "  Server Port:            ${YELLOW}${BIND_PORT}${NC}"
echo -e "  URL Subpath Prefix:     ${YELLOW}${URL_PREFIX:-(none - domain root)}${NC}"

# 5. OS & Package Manager Detection
echo -e "\n${BLUE}[1/6] Detecting operating system and installing system packages...${NC}"

PKG_MANAGER=""
if command -v apt-get >/dev/null 2>&1; then
    PKG_MANAGER="apt"
elif command -v dnf >/dev/null 2>&1; then
    PKG_MANAGER="dnf"
elif command -v yum >/dev/null 2>&1; then
    PKG_MANAGER="yum"
elif command -v zypper >/dev/null 2>&1; then
    PKG_MANAGER="zypper"
elif command -v pacman >/dev/null 2>&1; then
    PKG_MANAGER="pacman"
elif command -v apk >/dev/null 2>&1; then
    PKG_MANAGER="apk"
fi

case "$PKG_MANAGER" in
    apt)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get install -y python3 python3-pip python3-venv iputils-ping curl ca-certificates
        PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
        if [ -n "$PY_VER" ]; then
            apt-get install -y "python${PY_VER}-venv" 2>/dev/null || true
        fi
        apt-get install -y python3-full 2>/dev/null || true
        ;;
    dnf|yum)
        $PKG_MANAGER install -y python3 python3-pip iputils curl ca-certificates
        ;;
    zypper)
        zypper --non-interactive install python3 python3-pip iputils curl ca-certificates
        ;;
    pacman)
        pacman -Sy --noconfirm python python-pip iputils curl ca-certificates
        ;;
    apk)
        apk update
        apk add python3 py3-pip iputils curl ca-certificates bash
        ;;
    *)
        echo -e "${YELLOW}[WARN] Could not identify package manager. Ensuring python3 and ping are available...${NC}"
        if ! command -v python3 >/dev/null 2>&1 || ! command -v ping >/dev/null 2>&1; then
            echo -e "${RED}[ERROR] python3 and ping are required. Please install them and re-run.${NC}"
            exit 1
        fi
        ;;
esac

echo -e "${GREEN}[✓] System packages successfully prepared.${NC}"

# 6. Copy Application Files
echo -e "\n${BLUE}[2/6] Preparing application directory (${INSTALL_DIR})...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"

if [[ "$INSTALL_DIR" != "$SCRIPT_DIR" ]]; then
    cp -r "$SCRIPT_DIR/netmap" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/static" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/templates" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/scripts" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/run.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/sample_hosts.csv" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/netmap.service" "$INSTALL_DIR/" 2>/dev/null || true

    if [ -f "$INSTALL_DIR/netmap.cfg" ]; then
        echo -e "${YELLOW}[INFO] Existing netmap.cfg found. Preserving configuration settings.${NC}"
    else
        cp "$SCRIPT_DIR/netmap.cfg" "$INSTALL_DIR/netmap.cfg"
    fi
else
    # In-place installation
    if [ ! -f "$INSTALL_DIR/netmap.cfg" ]; then
        cp "$SCRIPT_DIR/netmap.cfg" "$INSTALL_DIR/netmap.cfg" 2>/dev/null || true
    fi
fi

# Ensure scripts directory exists and scripts are executable
mkdir -p "$INSTALL_DIR/scripts"
chmod -R 755 "$INSTALL_DIR"
chmod -R +x "$INSTALL_DIR/scripts"
chmod 777 "$INSTALL_DIR/data" 2>/dev/null || true

echo -e "${GREEN}[✓] Files successfully placed at ${INSTALL_DIR}.${NC}"

# 7. Setup Python Virtual Environment and Dependencies
echo -e "\n${BLUE}[3/6] Setting up isolated Python virtual environment...${NC}"
if [ -d "$INSTALL_DIR/.venv" ] && [ ! -f "$INSTALL_DIR/.venv/bin/python3" ]; then
    rm -rf "$INSTALL_DIR/.venv"
fi

if [ ! -d "$INSTALL_DIR/.venv" ]; then
    if ! python3 -m venv "$INSTALL_DIR/.venv" 2>/dev/null; then
        echo -e "${YELLOW}[WARN] Attempting venv creation with --without-pip...${NC}"
        python3 -m venv --without-pip "$INSTALL_DIR/.venv"
    fi
fi

VENV_PY="$INSTALL_DIR/.venv/bin/python3"

# Ensure pip is working in venv
if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    echo -e "${YELLOW}[INFO] Bootstrapping pip inside virtual environment...${NC}"
    if ! "$VENV_PY" -m ensurepip --default-pip >/dev/null 2>&1; then
        curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
        "$VENV_PY" /tmp/get-pip.py
        rm -f /tmp/get-pip.py
    fi
fi

echo -e "${BLUE}[INFO] Installing Python dependencies from requirements.txt...${NC}"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r "$INSTALL_DIR/requirements.txt"

echo -e "${GREEN}[✓] Python virtual environment ready.${NC}"

# 8. Configure netmap.cfg with chosen Host, Port, and URL Prefix
echo -e "\n${BLUE}[4/6] Updating configuration (netmap.cfg)...${NC}"
"$VENV_PY" -c "
import configparser
cfg_path = '$INSTALL_DIR/netmap.cfg'
parser = configparser.ConfigParser()
parser.read(cfg_path)
if not parser.has_section('server'):
    parser.add_section('server')
parser.set('server', 'host', '$BIND_HOST')
parser.set('server', 'port', '$BIND_PORT')
parser.set('server', 'url_prefix', '$URL_PREFIX')
if not parser.has_option('server', 'secret_key'):
    import secrets
    parser.set('server', 'secret_key', secrets.token_hex(24))
with open(cfg_path, 'w') as f:
    parser.write(f)
"
echo -e "${GREEN}[✓] netmap.cfg configured (Host: ${BIND_HOST}, Port: ${BIND_PORT}, Prefix: '${URL_PREFIX}').${NC}"

# 9. Register System Service & Global Control CLI
echo -e "\n${BLUE}[5/6] Registering service and control scripts...${NC}"

# Create global symlinks for 'netmap' and 'netmap-ctl'
ln -sf "$INSTALL_DIR/scripts/netmap-ctl" /usr/local/bin/netmap
ln -sf "$INSTALL_DIR/scripts/netmap-ctl" /usr/local/bin/netmap-ctl

SERVICE_TYPE="standalone"

# A. Systemd (Ubuntu, Debian, RHEL, CentOS, Rocky, Alma, Fedora, openSUSE, Arch)
if [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
    SERVICE_TYPE="systemd"
    SERVICE_FILE="/etc/systemd/system/netmap.service"

    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=NetMap - Network Tree Status Monitor
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/.venv/bin/python3 ${INSTALL_DIR}/run.py
Restart=always
RestartSec=5s

# Security and system limits
LimitNOFILE=65536
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=netmap

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable netmap.service
    systemctl restart netmap.service
    echo -e "${GREEN}[✓] Registered and started systemd service: netmap.service${NC}"

# B. OpenRC (Alpine Linux, Gentoo)
elif [ -f /sbin/openrc-run ] && command -v rc-service >/dev/null 2>&1; then
    SERVICE_TYPE="openrc"
    cp "$INSTALL_DIR/scripts/openrc/netmap" /etc/init.d/netmap
    chmod +x /etc/init.d/netmap
    rc-update add netmap default 2>/dev/null || true
    rc-service netmap restart 2>/dev/null || true
    echo -e "${GREEN}[✓] Registered and started OpenRC service: /etc/init.d/netmap${NC}"

# C. SysVinit / LSB (Debian legacy, Devuan, SysV)
elif [ -d /etc/init.d ]; then
    SERVICE_TYPE="sysvinit"
    cp "$INSTALL_DIR/scripts/init.d/netmap" /etc/init.d/netmap
    chmod +x /etc/init.d/netmap
    if command -v update-rc.d >/dev/null 2>&1; then
        update-rc.d netmap defaults 2>/dev/null || true
    elif command -v chkconfig >/dev/null 2>&1; then
        chkconfig --add netmap 2>/dev/null || true
    fi
    /etc/init.d/netmap restart 2>/dev/null || true
    echo -e "${GREEN}[✓] Registered and started SysVinit service: /etc/init.d/netmap${NC}"
else
    echo -e "${YELLOW}[INFO] Starting via background daemon script...${NC}"
    "$INSTALL_DIR/scripts/netmap-ctl" start
fi

# 10. Verify Service Health
echo -e "\n${BLUE}[6/6] Verifying service status...${NC}"
sleep 2

PROXY_TARGET_HOST="$BIND_HOST"
if [ "$PROXY_TARGET_HOST" = "0.0.0.0" ]; then
    PROXY_TARGET_HOST="127.0.0.1"
fi

SERVICE_OK=false
if [ "$SERVICE_TYPE" = "systemd" ]; then
    if systemctl is-active --quiet netmap; then
        SERVICE_OK=true
    fi
else
    if [ -f "$INSTALL_DIR/data/netmap.pid" ] && kill -0 "$(cat "$INSTALL_DIR/data/netmap.pid")" 2>/dev/null; then
        SERVICE_OK=true
    fi
fi

echo -e "\n${GREEN}====================================================================${NC}"
if [ "$SERVICE_OK" = true ]; then
    echo -e "${GREEN}  ✓ NetMap Successfully Deployed and Running!                       ${NC}"
else
    echo -e "${YELLOW}  ⚠ NetMap service is starting up...                                ${NC}"
fi
echo -e "${GREEN}====================================================================${NC}"

LOCAL_URL="http://${PROXY_TARGET_HOST}:${BIND_PORT}${URL_PREFIX}/"
ADMIN_URL="http://${PROXY_TARGET_HOST}:${BIND_PORT}${URL_PREFIX}/admin"

echo -e "\n${BOLD}Direct Access (Local):${NC}"
echo -e "  Dashboard:     ${CYAN}${LOCAL_URL}${NC}"
echo -e "  Admin Portal:  ${CYAN}${ADMIN_URL}${NC}"

echo -e "\n${BOLD}Default Credentials:${NC}"
echo -e "  Administrator: ${YELLOW}admin${NC} / ${YELLOW}admin123${NC} (Full access)"
echo -e "  Operator:      ${YELLOW}operator${NC} / ${YELLOW}operator123${NC} (Force poll only)"

echo -e "\n${BOLD}Service Control Commands (Usable from anywhere):${NC}"
echo -e "  Start:         ${YELLOW}sudo netmap start${NC}    (or sudo systemctl start netmap)"
echo -e "  Stop:          ${YELLOW}sudo netmap stop${NC}     (or sudo systemctl stop netmap)"
echo -e "  Restart:       ${YELLOW}sudo netmap restart${NC}  (or sudo systemctl restart netmap)"
echo -e "  Status:        ${YELLOW}sudo netmap status${NC}   (or sudo systemctl status netmap)"
echo -e "  Logs:          ${YELLOW}sudo netmap logs${NC}     (or sudo journalctl -u netmap -f)"

echo -e "\n${CYAN}====================================================================${NC}"
echo -e "${CYAN}  Nginx Reverse Proxy Configuration (Copy & Paste)                  ${NC}"
echo -e "${CYAN}====================================================================${NC}"
echo -e "To expose NetMap under ${BOLD}https://<your-domain>${URL_PREFIX:-/netmap}${NC}, add this block"
echo -e "inside your existing Nginx ${BOLD}server { ... }${NC} configuration:"
echo ""

EFFECTIVE_PREFIX="${URL_PREFIX:-/netmap}"
cat <<EOF
# Redirect ${EFFECTIVE_PREFIX} without trailing slash to ${EFFECTIVE_PREFIX}/
location = ${EFFECTIVE_PREFIX} {
    return 301 ${EFFECTIVE_PREFIX}/;
}

# Proxy traffic to NetMap backend
location ${EFFECTIVE_PREFIX}/ {
    proxy_pass http://${PROXY_TARGET_HOST}:${BIND_PORT}/;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Forwarded-Prefix ${EFFECTIVE_PREFIX};

    # WebSocket and HTTP/1.1 support
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";

    # Timeouts
    proxy_connect_timeout 60s;
    proxy_read_timeout 120s;
}
EOF

echo ""
echo -e "${YELLOW}After adding the block, test and reload Nginx:${NC}"
echo -e "  ${BOLD}sudo nginx -t && sudo systemctl reload nginx${NC}"
echo -e "${CYAN}====================================================================${NC}\n"
