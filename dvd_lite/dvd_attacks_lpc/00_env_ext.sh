#!/usr/bin/env bash
# source-safe env file (no set -e/-u/pipefail)

# --- locate this file path in any shell ---
if [ -n "${BASH_SOURCE:-}" ]; then
  _SRC="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  _SRC="${(%):-%x}"
else
  _SRC="$0"
fi
BASE="$(cd "$(dirname "$_SRC")" 2>/dev/null || pwd -P)"
[ -z "$BASE" ] || [ "$BASE" = "/" ] && BASE="$(pwd -P)"

# 로컬 오버라이드
[ -f "$BASE/00_env_local.sh" ] && . "$BASE/00_env_local.sh"

# 컨테이너 기본명 (없을 때만)
: "${DVD_C_GCS:=dvd_gcs}"
: "${DVD_C_CC:=dvd_companion}"
: "${DVD_C_FC:=dvd_flight}"
: "${DVD_C_SIM:=dvd_sim}"
: "${DVD_NET:=dvd_net}"

# ★ 출력 베이스: dvd_attacks_lpc/bus 고정(기존 OUT_DIR 값 무시)
OUT_DIR="$BASE/bus"
mkdir -p "$OUT_DIR"
export OUT_DIR

# 버스/로그 경로
export BUS_LOG="$OUT_DIR/bus.log"
export BUS_DVD_LOG="$OUT_DIR/bus_dvd.log"

# 캡처/스냅샷
export CAP_DIR="$OUT_DIR/captures"
export PCAP_DIR="$CAP_DIR/pcap"
export NS3_DIR="$OUT_DIR"
mkdir -p "$PCAP_DIR" "$NS3_DIR"

# 서비스 기본
: "${MAVLINK_HOST:=127.0.0.1}"; : "${MAVLINK_PORT:=14550}"
: "${RTSP_HOST:=127.0.0.1}";   : "${RTSP_PORT:=8554}"
: "${HTTP_CAM_HOST:=127.0.0.1}"; : "${HTTP_CAM_PORT:=8080}"

# LPC 프로파일
export LPC_PROFILE_DIR="${LPC_PROFILE_DIR:-$BASE/modules/attacks/lpc_profiles}"
export LPC_PROFILE_JSON="${LPC_PROFILE_JSON:-$LPC_PROFILE_DIR/attacks_lpc.json}"

# ns-3 바이너리
: "${NS3_BIN:=/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev/ns3}"
