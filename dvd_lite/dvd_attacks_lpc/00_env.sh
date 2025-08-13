#!/usr/bin/env bash
# 00_env.sh — MTD/FANET/HoneyDrone 테스트베드 공통 환경 (DVD 연동 확장판)
# - 로그/디렉터리 보장
# - Docker 컨테이너 자동 탐지 → IP/포트 바인딩 환경변수 설정
# - NS-3 경로/실행 편의 변수
# - MTD 이벤트/버스 로깅/UDP 테스트 유틸

set -euo pipefail

############################
# 1) 기본 경로/로그 보장
############################
export MTD_ROOT="${MTD_ROOT:-/home/kali/MTD/MTD_full_testbed}"
export LPC_ROOT="${LPC_ROOT:-$MTD_ROOT/dvd_lite/dvd_attacks_lpc}"
export LPC_LOG_DIR="${LPC_LOG_DIR:-$LPC_ROOT/attack_output}"
export BUS_LOG="${BUS_LOG:-$LPC_LOG_DIR/bus.log}"

mkdir -p "$LPC_LOG_DIR"
# 기존 로그는 보존(초기화하고 싶으면 : > "$BUS_LOG")
touch "$BUS_LOG"

# 편의 PATH
export PATH="$LPC_ROOT:$LPC_ROOT/tools:$PATH"

log_i(){ printf '[ENV] %s\n' "$*" | tee -a "$BUS_LOG" >/dev/null; }
log_w(){ printf '[ENV][WARN] %s\n' "$*" | tee -a "$BUS_LOG" >/dev/null; }
log_e(){ printf '[ENV][ERR] %s\n' "$*" | tee -a "$BUS_LOG" >/dev/null; }

############################
# 2) NS-3 경로/옵션
############################
export NS3="${NS3:-$MTD_ROOT/ns-3.45/ns-3-dev}"
export NS3_WAF="$NS3/waf"
export NS3_SCRATCH_BIN="scratch/drone_lpc_eval"  # waf --run "scratch/drone_lpc_eval ..."
if [[ ! -x "$NS3_WAF" ]]; then
  log_w "ns-3 waf($NS3_WAF) 미발견: ns-3 평가 시 안전 더미 결과로 대체됩니다."
fi

############################
# 3) DVD 네트워크/포트 기본값
############################
export DVD_INFRA_NET="${DVD_INFRA_NET:-10.13.0.0/24}"
export DVD_WIFI_NET="${DVD_WIFI_NET:-192.168.13.0/24}"
export DVD_WEB_CONSOLE_PORT="${DVD_WEB_CONSOLE_PORT:-8000}"
export DVD_MAVLINK_PORT="${DVD_MAVLINK_PORT:-14550}"
export DVD_MAVLINK_PORT_ALT="${DVD_MAVLINK_PORT_ALT:-14551}"
export DVD_RTSP_PORT="${DVD_RTSP_PORT:-8554}"

# Compose 기본 컨테이너 명(없으면 자동 탐지 로직이 대체)
export DVD_C_GCS="${DVD_C_GCS:-ground-control-station}"
export DVD_C_CC="${DVD_C_CC:-companion-computer}"
export DVD_C_FC="${DVD_C_FC:-flight-controller}"
export DVD_C_SIM="${DVD_C_SIM:-simulator}"

############################
# 4) Docker 컨테이너 자동 탐지 + IP 해석
############################
have_docker=false
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    have_docker=true
  else
    log_w "docker 데몬 접근 불가. 컨테이너 기반 연동은 생략됩니다."
  fi
else
  log_w "docker 명령이 없습니다. 컨테이너 기반 연동은 생략됩니다."
fi

find_c_by_hint(){
  local hint="$1"
  docker ps --format '{{.Names}}' 2>/dev/null | grep -iE "$hint" | head -n1 || true
}

# 이름 후보 자동 보정(사용자 커스텀 환경을 위해 느슨한 탐지)
if $have_docker; then
  [[ -z "$(docker ps --format '{{.Names}}' | grep -Fx "$DVD_C_GCS" || true)" ]] && \
    DVD_C_GCS="$(find_c_by_hint 'gcs|qgc|mavproxy|ground-control')"
  [[ -z "$(docker ps --format '{{.Names}}' | grep -Fx "$DVD_C_CC" || true)" ]] && \
    DVD_C_CC="$(find_c_by_hint 'companion|cc|companion-computer')"
  [[ -z "$(docker ps --format '{{.Names}}' | grep -Fx "$DVD_C_FC" || true)" ]] && \
    DVD_C_FC="$(find_c_by_hint 'sitl|ardupilot|fc|flight-controller')"
  [[ -z "$(docker ps --format '{{.Names}}' | grep -Fx "$DVD_C_SIM" || true)" ]] && \
    DVD_C_SIM="$(find_c_by_hint 'sim|simulator|ui')"
fi

get_ip(){
  local cname="$1"
  [[ -z "$cname" ]] && { echo ""; return; }
  docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$cname" 2>/dev/null || echo ""
}

DVD_IP_GCS="${DVD_IP_GCS:-}"
DVD_IP_CC="${DVD_IP_CC:-}"
DVD_IP_FC="${DVD_IP_FC:-}"
DVD_IP_SIM="${DVD_IP_SIM:-}"

if $have_docker; then
  [[ -z "$DVD_IP_GCS" && -n "$DVD_C_GCS" ]] && DVD_IP_GCS="$(get_ip "$DVD_C_GCS")"
  [[ -z "$DVD_IP_CC"  && -n "$DVD_C_CC"  ]] && DVD_IP_CC="$(get_ip "$DVD_C_CC")"
  [[ -z "$DVD_IP_FC"  && -n "$DVD_C_FC"  ]] && DVD_IP_FC="$(get_ip "$DVD_C_FC")"
  [[ -z "$DVD_IP_SIM" && -n "$DVD_C_SIM" ]] && DVD_IP_SIM="$(get_ip "$DVD_C_SIM")"
fi

# 최종 엔드포인트(가능한 경우 컨테이너 IP 우선)
export GCS_IP="${DVD_IP_GCS:-${GCS_IP:-}}"
export CC_IP="${DVD_IP_CC:-${CC_IP:-}}"
export FC_IP="${DVD_IP_FC:-${FC_IP:-}}"
export SIM_IP="${DVD_IP_SIM:-${SIM_IP:-}}"

# MAVLink 엔드포인트 문자열(예: udp://<ip>:14550)
export MAVLINK_GCS_ENDPOINT="${MAVLINK_GCS_ENDPOINT:-$([[ -n "${GCS_IP:-}" ]] && echo "udp://$GCS_IP:$DVD_MAVLINK_PORT" || echo "")}"

############################
# 5) MTD 이벤트/유틸 함수
############################
MTD_EVENT_FILE="$LPC_ROOT/.mtd_event"

mtd_event(){  # 예: mtd_event ip_shuffle
  local ev="${1:-}"; [[ -z "$ev" ]] && { log_e "mtd_event: 이벤트명이 필요합니다"; return 1; }
  echo "$ev" > "$MTD_EVENT_FILE"
  log_i "MTD 이벤트 주입: $ev"
}

mtd_bus(){    # 예: mtd_bus "note key=val"
  local msg="$*"
  local ts; ts="$(date '+%F %T')"
  echo "[$ts] [mtd_env] $msg" | tee -a "$BUS_LOG" >/dev/null
}

mtd_udp_test(){ # GCS UDP 포트 간단 확인용: mtd_udp_test [bytes]
  local bytes="${1:-\xFE}"
  if [[ -z "${GCS_IP:-}" ]]; then
    log_w "GCS_IP가 비어 있어 UDP 테스트 생략"; return 1
  fi
  ( echo -ne "$bytes" | nc -u -w1 "$GCS_IP" "$DVD_MAVLINK_PORT" ) && \
    log_i "GCS($GCS_IP:$DVD_MAVLINK_PORT) UDP 송신 테스트 완료" || \
    log_w "GCS UDP 송신 테스트 실패(네트워크/방화벽 확인)"
}

############################
# 6) 요약 출력
############################
log_i "MTD_ROOT=$MTD_ROOT"
log_i "LPC_ROOT=$LPC_ROOT"
log_i "BUS_LOG=$BUS_LOG"
if $have_docker; then
  log_i "Docker OK. 컨테이너 탐지:"
  printf '  - GCS: %-28s IP=%s\n' "${DVD_C_GCS:-<none>}" "${GCS_IP:-<none>}"
  printf '  - CC : %-28s IP=%s\n' "${DVD_C_CC:-<none>}"  "${CC_IP:-<none>}"
  printf '  - FC : %-28s IP=%s\n' "${DVD_C_FC:-<none>}"  "${FC_IP:-<none>}"
  printf '  - SIM: %-28s IP=%s\n' "${DVD_C_SIM:-<none>}" "${SIM_IP:-<none>}"
else
  log_w "Docker 사용 불가. 컨테이너 연동 기능 비활성."
fi

if [[ -n "${MAVLINK_GCS_ENDPOINT:-}" ]]; then
  log_i "MAVLink GCS endpoint: $MAVLINK_GCS_ENDPOINT"
else
  log_w "MAVLink GCS endpoint 미설정 (GCS 컨테이너/아이피 확인 필요)"
fi

if [[ -x "$NS3_WAF" ]]; then
  log_i "ns-3 waf 발견: $NS3_WAF"
  log_i "ns-3 실행 예: (cd \"$NS3\" && ./waf --run \"$NS3_SCRATCH_BIN --timeline=$LPC_LOG_DIR/effect_timeline.csv --out=$LPC_LOG_DIR/ns3_metrics.csv\")"
else
  log_w "ns-3 waf 미발견: NS-3 실행은 생략/더미 결과 사용"
fi

# 마지막 한 줄: 쉘에서 소스됐음을 알림
log_i "환경 로드 완료."
