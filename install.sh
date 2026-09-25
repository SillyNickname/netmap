#!/usr/bin/env bash
# ==============================================================================
# NetMap - Automated Installer for Ubuntu Server
# ==============================================================================
# This script installs all required system packages via apt, configures a
# dedicated Python virtual environment, sets up NetMap, and registers a
# systemd service for automatic background execution.
#
# Usage:
#   sudo ./install.sh              # Installs to /opt/netmap (Recommended)
#   sudo ./install.sh --in-place   # Installs in current directory
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  NetMap - Ubuntu Server Automated Deployment Script  ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Root Check
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This script must be run as root (or with sudo).${NC}"
    echo "Usage: sudo ./install.sh"
    exit 1
fi

# 2. Ubuntu / Debian Check
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_NAME=$NAME
    OS_VER=$VERSION_ID
else
    echo -e "${RED}[ERROR] Cannot detect operating system distribution.${NC}"
    exit 1
fi

echo -e "${GREEN}[INFO] Detected OS: ${OS_NAME} ${OS_VER}${NC}"

# 3. Determine Installation Directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/netmap"

if [[ "$1" == "--in-place" ]]; then
    INSTALL_DIR="$SCRIPT_DIR"
    echo -e "${YELLOW}[INFO] Installing in-place at: ${INSTALL_DIR}${NC}"
else
    echo -e "${YELLOW}[INFO] Target installation directory: ${INSTALL_DIR}${NC}"
fi

# 4. Install System Dependencies via apt
echo -e "\n${BLUE}[1/5] Updating apt repositories and installing system packages...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    iputils-ping \
    curl \
    ca-certificates

echo -e "${GREEN}[✓] System packages successfully installed.${NC}"

# 5. Copy Application Files (if not in-place)
echo -e "\n${BLUE}[2/5] Preparing application directory...${NC}"
if [[ "$INSTALL_DIR" != "$SCRIPT_DIR" ]]; then
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/data"

    # Copy files
    cp -r "$SCRIPT_DIR/netmap" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/static" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/templates" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/run.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/sample_hosts.csv" "$INSTALL_DIR/"

    # Preserve existing configuration if present
    if [ -f "$INSTALL_DIR/netmap.cfg" ]; then
        echo -e "${YELLOW}[INFO] Existing netmap.cfg found. Preserving configuration.${NC}"
    else
        cp "$SCRIPT_DIR/netmap.cfg" "$INSTALL_DIR/netmap.cfg"
    fi
else
    mkdir -p "$INSTALL_DIR/data"
fi

# Ensure proper permissions
chmod -R 755 "$INSTALL_DIR"
chmod 777 "$INSTALL_DIR/data" 2>/dev/null || true

echo -e "${GREEN}[✓] Files installed at ${INSTALL_DIR}.${NC}"

# 6. Setup Python Virtual Environment and Pip Libraries
echo -e "\n${BLUE}[3/5] Setting up Python virtual environment and installing libraries...${NC}"
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    python3 -m venv "$INSTALL_DIR/.venv"
fi

# Upgrade pip and install required libraries
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo -e "${GREEN}[✓] Python libraries installed in ${INSTALL_DIR}/.venv.${NC}"

# 7. Configure and Register systemd Service
echo -e "\n${BLUE}[4/5] Registering systemd background service (netmap.service)...${NC}"
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

echo -e "${GREEN}[✓] systemd service registered, enabled, and started.${NC}"

# 8. Verification
echo -e "\n${BLUE}[5/5] Verifying service health...${NC}"
sleep 2

PORT=8080
if [ -f "$INSTALL_DIR/netmap.cfg" ]; then
    CFG_PORT=$(grep -E '^\s*port\s*=' "$INSTALL_DIR/netmap.cfg" | awk -F'=' '{print $2}' | tr -d ' ')
    if [ -n "$CFG_PORT" ]; then
        PORT="$CFG_PORT"
    fi
fi

if systemctl is-active --quiet netmap; then
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}  ✓ NetMap Successfully Deployed and Running!         ${NC}"
    echo -e "${GREEN}======================================================${NC}"
    echo ""
    echo -e "Web Interface:      ${BLUE}http://$(hostname -I | awk '{print $1}'):${PORT}/${NC}"
    echo -e "Painel Admin:       ${BLUE}http://$(hostname -I | awk '{print $1}'):${PORT}/admin${NC}"
    echo ""
    echo -e "Contas Padrão / Default Credentials:"
    echo -e "  Admin:    ${YELLOW}admin${NC} / ${YELLOW}admin123${NC} (Acesso completo / Full access)"
    echo -e "  Operador: ${YELLOW}operator${NC} / ${YELLOW}operator123${NC} (Forçar varredura / Force poll)"
    echo ""
    echo -e "Comandos de Gerenciamento / Service Commands:"
    echo -e "  Status:   sudo systemctl status netmap"
    echo -e "  Reiniciar: sudo systemctl restart netmap"
    echo -e "  Parar:    sudo systemctl stop netmap"
    echo -e "  Logs:     sudo journalctl -u netmap -f"
    echo ""
    echo -e "Configuração / Config File:"
    echo -e "  Arquivo:  ${INSTALL_DIR}/netmap.cfg"
    echo -e "${GREEN}======================================================${NC}"
else
    echo -e "${RED}[WARNING] Service started but not active yet. Check logs with: journalctl -u netmap -e${NC}"
fi
