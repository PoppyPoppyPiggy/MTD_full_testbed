#!/usr/bin/env bash
# LPC Environment Defaults (safe-by-default)
set -euo pipefail

BASE="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]-$0}")" && pwd)"
export LPC_LOG_DIR="${LPC_LOG_DIR:-$BASE/attack_output}"
mkdir -p "$LPC_LOG_DIR"

# ===== SAFETY SWITCH =====
# 0: simulation-only (log + container-local shaping)
# 1: real effects (MUST be used only inside the DVD testbed)
export ALLOW_REAL_EFFECTS="${ALLOW_REAL_EFFECTS:-0}"
export LPC_MODE=$([ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ] && echo REAL || echo SIM)

# Actor role
export LPC_ACTOR="${LPC_ACTOR:-attacker}"

# DVD Docker targets (adjust to your compose names)
export DVD_C_GCS="${DVD_C_GCS:-ground-control-station}"
export DVD_TARGET_IF="${DVD_TARGET_IF:-eth0}"
export DVD_MAVLINK_HOST="${DVD_MAVLINK_HOST:-127.0.0.1}"
export DVD_MAVLINK_PORT="${DVD_MAVLINK_PORT:-14550}"
