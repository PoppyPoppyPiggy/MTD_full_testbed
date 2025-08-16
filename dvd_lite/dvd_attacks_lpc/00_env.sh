#!/usr/bin/env bash
# 00_env.sh — MTD/FANET/HoneyDrone 테스트베드 공통 환경 (ns3 런처판)
case $- in
  *i*) set -eo pipefail ;;   # interactive shell: no -u
  *)   set -euo pipefail ;;  # non-interactive: strict
esac

############################
# 1) 기본 경로/로그
############################
export MTD_ROOT="${MTD_ROOT:-/home/kali/MTD/MTD_full_testbed}"
export LPC_ROOT="${LPC_ROOT:-$MTD_ROOT/dvd_lite/dvd_attacks_lpc}"
export LPC_LOG_DIR="${LPC_LOG_DIR:-$LPC_ROOT/attack_output}"
export BUS_LOG="${BUS_LOG:-$LPC_LOG_DIR/bus.log}"
mkdir -p "$LPC_LOG_DIR"; touch "$BUS_LOG"

log_i(){ printf '[ENV] %s\n' "$*" | tee -a "$BUS_LOG" >/dev/null; }
log_w(){ printf '[ENV][WARN] %s\n' "$*" | tee -a "$BUS_LOG" >/dev/null; }

############################
# 2) NS-3 경로/옵션 (./ns3 런처 사용)
############################
# 사용자가 NS3 또는 NS3_ROOT 둘 중 하나만 세팅해도 동작
NS3_DEFAULT="$MTD_ROOT/ns-3.45/ns-3-dev"
export NS3="${NS3:-${NS3_ROOT:-$NS3_DEFAULT}}"
export NS3_BIN="$NS3/ns3"                 # ← waf 말고 ns3 런처
export NS3_SCRATCH="scratch/drone_lpc_eval"

if [[ -x "$NS3_BIN" ]]; then
  log_i "ns-3 launcher 발견: $NS3_BIN"
  log_i "예) (cd \"$NS3\" && ./ns3 run \"$NS3_SCRATCH --timeline=$LPC_LOG_DIR/effect_timeline.csv --out=$LPC_LOG_DIR/ns3_metrics.csv\")"
else
  log_w "ns-3 launcher 미발견: $NS3_BIN (빌드 또는 경로 확인 필요)"
fi

############################
# 3) DVD 네트워크/컨테이너(생략 가능)
############################
export DVD_MAVLINK_PORT="${DVD_MAVLINK_PORT:-14550}"
export DVD_C_GCS="${DVD_C_GCS:-ground-control-station}"
have_docker=false
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  have_docker=true
fi
get_ip(){ docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1" 2>/dev/null || true; }
if $have_docker; then
  [[ -z "${GCS_IP:-}" ]] && GCS_IP="$(get_ip "$DVD_C_GCS")"
fi
export GCS_IP
if [[ -n "${GCS_IP:-}" ]]; then
  export MAVLINK_GCS_ENDPOINT="udp://$GCS_IP:$DVD_MAVLINK_PORT"
  log_i "MAVLink GCS endpoint: $MAVLINK_GCS_ENDPOINT"
else
  log_w "MAVLink GCS endpoint 미설정 (컨테이너 또는 IP 확인)"
fi

log_i "MTD_ROOT=$MTD_ROOT"
log_i "LPC_ROOT=$LPC_ROOT"
log_i "BUS_LOG=$BUS_LOG"
log_i "환경 로드 완료."
