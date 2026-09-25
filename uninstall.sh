#!/usr/bin/env bash
# ==============================================================================
# NetMap - Uninstaller for Ubuntu Server
# ==============================================================================

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This script must be run as root (or with sudo).${NC}"
    exit 1
fi

echo -e "${YELLOW}Stopping and disabling netmap.service...${NC}"
systemctl stop netmap.service 2>/dev/null || true
systemctl disable netmap.service 2>/dev/null || true

if [ -f /etc/systemd/system/netmap.service ]; then
    rm -f /etc/systemd/system/netmap.service
    systemctl daemon-reload
fi

INSTALL_DIR="/opt/netmap"
if [ -d "$INSTALL_DIR" ]; then
    echo ""
    read -p "Do you want to delete the installation directory ($INSTALL_DIR) including database history? [y/N]: " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        echo -e "${GREEN}Removed ${INSTALL_DIR}.${NC}"
    else
        echo -e "${YELLOW}Preserved ${INSTALL_DIR}.${NC}"
    fi
fi

echo -e "${GREEN}NetMap service has been successfully uninstalled.${NC}"
