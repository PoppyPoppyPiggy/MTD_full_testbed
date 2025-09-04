#!/usr/bin/env bash
# source-safe env file (no set -e/-u/pipefail; safe in bash/zsh/posix)

# --- locate this file path in any shell ---
if [ -n "${BASH_SOURCE:-}" ]; then
  _SRC="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  # zsh: ${(%):-%x} -> current sourced file
  _SRC="${(%):-%x}"
else
  # generic fallback
  _SRC="$0"
fi
BASE="$(cd "$(dirname "$_SRC")" 2>/dev/null || pwd -P)"

# --- load local overrides detected by scripts/dvd_detect.sh (if exists) ---
if [ -f "$BASE/00_env_local.sh" ]; then
  . "$BASE/00_env_local.sh"
fi

# --- defaults (only if not already set) ---
: "${DVD_C_GCS:=dvd_gcs}"
: "${DVD_C_CC:=dvd_companion}"
: "${DVD_C_FC:=dvd_flight}"
: "${DVD_C_SIM:=dvd_sim}"
: "${DVD_NET:=dvd_net}"

# outputs
OUT_DIR="${OUT_DIR:-$BASE/attack_output}"
[ -d "$OUT_DIR" ] || mkdir -p "$OUT_DIR"
export BUS_LOG="${BUS_LOG:-$OUT_DIR/bus.log}"
export BUS_DVD_LOG="${BUS_DVD_LOG:-$OUT_DIR/bus_dvd.log}"

# captures
export CAP_DIR="${CAP_DIR:-$OUT_DIR/captures}"
export PCAP_DIR="${PCAP_DIR:-$CAP_DIR/pcap}"
export NS3_DIR="${NS3_DIR:-$OUT_DIR}"
[ -d "$PCAP_DIR" ] || mkdir -p "$PCAP_DIR"
[ -d "$NS3_DIR" ] || mkdir -p "$NS3_DIR"

# services (override in 00_env_local.sh if needed)
: "${MAVLINK_HOST:=127.0.0.1}"
: "${MAVLINK_PORT:=14550}"
: "${RTSP_HOST:=127.0.0.1}"
: "${RTSP_PORT:=8554}"
: "${HTTP_CAM_HOST:=127.0.0.1}"
: "${HTTP_CAM_PORT:=8080}"

# lpc profiles
export LPC_PROFILE_DIR="${LPC_PROFILE_DIR:-$BASE/modules/attacks/lpc_profiles}"
export LPC_PROFILE_JSON="${LPC_PROFILE_JSON:-$LPC_PROFILE_DIR/attacks_lpc.json}"

# ns-3 binary
: "${NS3_BIN:=/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev/ns3}"

# done (no exit/return; no shell option changes)
