#!/usr/bin/env bash
# 00_env.sh — MTD/FANET/HoneyDrone 공통 환경 (관대한 버전)
# 사용법: 프로젝트 어느 디렉터리에서든 `source /path/to/dvd_lite/dvd_attacks_lpc/00_env.sh`
# 주의: 반드시 "source"로 불러야 현재 셸에 export가 반영됨.

# ── 관대한 셸 모드 (개발 중에는 오류로 인한 터미널 종료 방지) ──────────────
# 개발 모드와 프로덕션 모드 구분
if [[ "${MTD_DEV_MODE:-1}" == "1" ]]; then
    # 개발 모드: 관대함
    set +e +u +o pipefail
    echo "[ENV] 개발 모드: 오류 시 터미널 종료 안함"
else
    # 프로덕션 모드: 엄격함
    case $- in
      *i*) set -eo pipefail ;;   # interactive: -u 끔
      *)   set -euo pipefail ;;  # non-interactive: -u 켬
    esac
    echo "[ENV] 프로덕션 모드: 엄격한 오류 처리"
fi

# ── 0) 유틸 ────────────────────────────────────────────────────────────────
_realpath() { 
    command -v realpath >/dev/null && realpath -m "$1" || python3 - <<PY "$1"
import os,sys; print(os.path.abspath(sys.argv[1]))
PY
}

log_i(){ printf '[ENV] %s\n' "$*" | tee -a "${BUS_LOG:-/dev/null}" >/dev/null; }
log_w(){ printf '[ENV][WARN] %s\n' "$*" | tee -a "${BUS_LOG:-/dev/null}" >/dev/null; }
log_e(){ printf '[ENV][ERROR] %s\n' "$*" | tee -a "${BUS_LOG:-/dev/null}" >&2; }

# ── 1) 루트 경로 계산(파일 위치 기준) ─────────────────────────────────────
# 이 파일(00_env.sh)의 절대 경로
__ENV_DIR="$(_realpath "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" 2>/dev/null || echo "$(pwd)")"

# LPC_ROOT: dvd_lite/dvd_attacks_lpc 디렉터리
export LPC_ROOT="${LPC_ROOT:-$__ENV_DIR}"

# MTD_ROOT: 저장소 루트 (LPC_ROOT에서 두 단계 위가 기본)
export MTD_ROOT="${MTD_ROOT:-$(_realpath "$LPC_ROOT/../.." 2>/dev/null || echo "${LPC_ROOT}/../..")}"

# ── 2) 로그/아웃풋 디렉터리 ───────────────────────────────────────────────
export LPC_LOG_DIR="${LPC_LOG_DIR:-$(_realpath "$LPC_ROOT/attack_output" 2>/dev/null || echo "$LPC_ROOT/attack_output")}"
export BUS_LOG="${BUS_LOG:-$LPC_LOG_DIR/bus.log}"

# 디렉토리 생성 (오류 무시)
mkdir -p "$LPC_LOG_DIR" 2>/dev/null || true
touch "$BUS_LOG" 2>/dev/null || true

# ── 3) ns-3 경로/옵션 (./ns3 런처 사용, waf 미사용) ──────────────────────
NS3_DEFAULT="$(_realpath "$MTD_ROOT/ns-3.45/ns-3-dev" 2>/dev/null || echo "$MTD_ROOT/ns-3.45/ns-3-dev")"

# 사용자는 NS3 또는 NS3_ROOT 중 하나만 세팅해도 됨
export NS3="${NS3:-${NS3_ROOT:-$NS3_DEFAULT}}"
export NS3_BIN="$(_realpath "$NS3/ns3" 2>/dev/null || echo "$NS3/ns3")"
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

# 도커 가용성 확인 (오류 무시)
have_docker=false
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  have_docker=true
fi

# IP 추출 함수 (오류 무시)
get_container_ip() { 
    docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1" 2>/dev/null || true
}

if [[ "$have_docker" == "true" ]]; then
  if [[ -z "${GCS_IP:-}" ]]; then
    GCS_IP="$(get_container_ip "$DVD_C_GCS" 2>/dev/null || true)"
  fi
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

# 개발 팁 출력
if [[ "${MTD_DEV_MODE:-1}" == "1" ]]; then
    echo ""
    echo "💡 개발 팁:"
    echo "  - 프로덕션 모드로 전환: export MTD_DEV_MODE=0"
    echo "  - 오류 모드 수동 조정: set +e (관대) / set -e (엄격)"
    echo "  - 실행 로그 확인: tail -f $BUS_LOG"
    echo ""
fi