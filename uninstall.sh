#!/usr/bin/env bash
# ==============================================================================
# NetMap - Uninstaller Script
# Developed by: Antigravity (Google DeepMind)
# Requested and commissioned by: Andre Kajita <kajita@univap.br>
# ==============================================================================

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This script must be run as root (or with sudo).${NC}"
    exit 1
fi

echo -e "${YELLOW}Stopping NetMap service...${NC}"

# 1. Stop and disable systemd service if present
if command -v systemctl >/dev/null 2>&1; then
    systemctl stop netmap.service 2>/dev/null || true
    systemctl disable netmap.service 2>/dev/null || true
    if [ -f /etc/systemd/system/netmap.service ]; then
        rm -f /etc/systemd/system/netmap.service
        systemctl daemon-reload
    fi
fi

# 2. Stop and disable OpenRC / SysVinit service if present
if [ -f /etc/init.d/netmap ]; then
    if command -v rc-service >/dev/null 2>&1; then
        rc-service netmap stop 2>/dev/null || true
        rc-update del netmap default 2>/dev/null || true
    elif command -v update-rc.d >/dev/null 2>&1; then
        /etc/init.d/netmap stop 2>/dev/null || true
        update-rc.d -f netmap remove 2>/dev/null || true
    elif command -v chkconfig >/dev/null 2>&1; then
        /etc/init.d/netmap stop 2>/dev/null || true
        chkconfig --del netmap 2>/dev/null || true
    fi
    rm -f /etc/init.d/netmap
fi

# 3. Kill any remaining processes
pkill -f "run.py" 2>/dev/null || true

# 4. Remove CLI symlinks
rm -f /usr/local/bin/netmap /usr/local/bin/netmap-ctl

# 5. Clean installation directory
INSTALL_DIR="/opt/netmap"
if [ -d "$INSTALL_DIR" ]; then
    echo ""
    read -p "Do you want to delete the installation directory ($INSTALL_DIR) including database history? [y/N]: " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        echo -e "${GREEN}[✓] Removed ${INSTALL_DIR}.${NC}"
    else
        echo -e "${YELLOW}[INFO] Preserved ${INSTALL_DIR}.${NC}"
    fi
fi

echo -e "${GREEN}[✓] NetMap service has been successfully uninstalled.${NC}"
