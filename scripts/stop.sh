#!/usr/bin/env bash
# NetMap Server Stop Script
# Developed by: Antigravity (Google DeepMind)
# Requested and commissioned by: Andre Kajita <kajita@univap.br>
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/netmap-ctl" stop "$@"
