#!/usr/bin/env bash
# === 절대 경로 ===
export MTD_ROOT="/home/kali/MTD/MTD_full_testbed"
export LPC_ROOT="$MTD_ROOT/dvd_lite/dvd_attacks_lpc"
export LPC_LOG_DIR="$LPC_ROOT/attack_output"
mkdir -p "$LPC_LOG_DIR"

# === DVD 네트워크/역할 기본값(README/Wiki 기준) ===
export DVD_INFRA_NET="10.13.0.0/24"
export DVD_WIFI_NET="192.168.13.0/24"
export DVD_IP_FC="10.13.0.2"      # Flight Controller(SITL)
export DVD_IP_CC="10.13.0.3"      # Companion
export DVD_IP_GCS="10.13.0.4"     # Ground Control
export DVD_IP_SIM="10.13.0.5"     # Simulator(Web UI 8000)

export DVD_WEB_CONSOLE_PORT=8000
export DVD_MAVLINK_PORT=14550     # 통상 GCS 수신
export DVD_MAVLINK_PORT_ALT=14551 # 서브링크(옵션)
export DVD_RTSP_PORT=8554         # 카메라(관행)

# === 컨테이너 이름(수동 override 가능) ===
: "${DVD_C_GCS:=}"
: "${DVD_C_CC:=}"
: "${DVD_C_FC:=}"

find_c_by_hint(){ docker ps --format '{{.Names}}' | grep -iE "$1" | head -n1; }

# 자동탐지(없으면 빈값 유지 → 모듈이 효과만 시뮬)
[[ -z "$DVD_C_GCS" ]] && DVD_C_GCS="$(find_c_by_hint 'gcs|qgc|mavproxy')"
[[ -z "$DVD_C_CC"  ]] && DVD_C_CC="$(find_c_by_hint 'companion|cc')"
[[ -z "$DVD_C_FC"  ]] && DVD_C_FC="$(find_c_by_hint 'sitl|ardupilot|fc')"

export DVD_C_GCS DVD_C_CC DVD_C_FC

# === 공통 MTD 로그 소스 ===
export MTD_LOG="$MTD_ROOT/mtd_testbed.log"
