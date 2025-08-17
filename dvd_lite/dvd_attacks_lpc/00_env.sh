#!/usr/bin/env bash
# 00_env.sh — MTD/FANET/HoneyDrone 공통 환경 (./ns3 런처 전제)
# 사용법: 프로젝트 어느 디렉터리에서든 `source /path/to/dvd_lite/dvd_attacks_lpc/00_env.sh`
# 주의: 반드시 "source"로 불러야 현재 셸에 export가 반영됨.

# ── 셸 모드 ────────────────────────────────────────────────────────────────
case $- in
  *i*) set -eo pipefail ;;   # interactive: -u 끔
  *)   set -euo pipefail ;;  # non-interactive: -u 켬
esac

# ── 0) 유틸 ────────────────────────────────────────────────────────────────
_realpath() { command -v realpath >/dev/null && realpath -m "$1" || python3 - <<PY "$1"
import os,sys; print(os.path.abspath(sys.argv[1]))
PY
}
log_i(){ printf '[ENV] %s\n' "$*" | tee -a "${BUS_LOG:-/dev/null}" >/dev/null; }
log_w(){ printf '[ENV][WARN] %s\n' "$*" | tee -a "${BUS_LOG:-/dev/null}" >/dev/null; }

# ── 1) 루트 경로 계산(파일 위치 기준) ─────────────────────────────────────
# 이 파일(00_env.sh)의 절대 경로
__ENV_DIR="$(_realpath "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

# LPC_ROOT: dvd_lite/dvd_attacks_lpc 디렉터리
export LPC_ROOT="${LPC_ROOT:-$__ENV_DIR}"

# MTD_ROOT: 저장소 루트 (LPC_ROOT에서 두 단계 위가 기본)
export MTD_ROOT="${MTD_ROOT:-$(_realpath "$LPC_ROOT/../..")}"

# ── 2) 로그/아웃풋 디렉터리 ───────────────────────────────────────────────
export LPC_LOG_DIR="${LPC_LOG_DIR:-$(_realpath "$LPC_ROOT/attack_output")}"
export BUS_LOG="${BUS_LOG:-$LPC_LOG_DIR/bus.log}"
mkdir -p "$LPC_LOG_DIR"; : > "$BUS_LOG" 2>/dev/null || true

# ── 3) ns-3 경로/옵션 (./ns3 런처 사용, waf 미사용) ──────────────────────
NS3_DEFAULT="$(_realpath "$MTD_ROOT/ns-3.45/ns-3-dev")"
# 사용자는 NS3 또는 NS3_ROOT 중 하나만 세팅해도 됨
export NS3="${NS3:-${NS3_ROOT:-$NS3_DEFAULT}}"
export NS3_BIN="$(_realpath "$NS3/ns3")"              # ns-3 런처
export NS3_SCRATCH="${NS3_SCRATCH:-scratch/drone_lpc_eval}"

if [[ -x "$NS3_BIN" ]]; then
  log_i "ns-3 launcher 발견: $NS3_BIN"
  log_i "예) (cd \"$NS3\" && ./ns3 run \"$NS3_SCRATCH --timeline=$LPC_LOG_DIR/effect_timeline.csv --out=$LPC_LOG_DIR/ns3_metrics.csv\")"
else
  log_w "ns-3 launcher 미발견: $NS3_BIN (빌드 또는 경로 확인 필요: clean/configure/build)"
fi

# ── 4) 선택: DVD 도커 네트워크(없으면 건너뜀) ────────────────────────────
export DVD_MAVLINK_PORT="${DVD_MAVLINK_PORT:-14550}"
export DVD_C_GCS="${DVD_C_GCS:-ground-control-station}"

_have_docker=false
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  _have_docker=true
fi

_get_ip(){ docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1" 2>/dev/null || true; }

if $_have_docker; then
  [[ -z "${GCS_IP:-}" ]] && GCS_IP="$(_get_ip "$DVD_C_GCS")"
fi
export GCS_IP
if [[ -n "${GCS_IP:-}" ]]; then
  export MAVLINK_GCS_ENDPOINT="udp://$GCS_IP:$DVD_MAVLINK_PORT"
  log_i "MAVLink GCS endpoint: $MAVLINK_GCS_ENDPOINT"
else
  log_w "MAVLink GCS endpoint 미설정 (컨테이너 또는 IP 확인)"
fi

# ── 5) 요약 출력 ──────────────────────────────────────────────────────────
log_i "MTD_ROOT=$MTD_ROOT"
log_i "LPC_ROOT=$LPC_ROOT"
log_i "LPC_LOG_DIR=$LPC_LOG_DIR"
log_i "NS3=$NS3"
log_i "NS3_BIN=$NS3_BIN"
log_i "NS3_SCRATCH=$NS3_SCRATCH"
log_i "BUS_LOG=$BUS_LOG"
log_i "환경 로드 완료."
