#!/usr/bin/env bash
# zsh/bash 모두 호환. set -e/-u가 걸려 있어도 안전하게 동작
set -o pipefail

# 리포지토리 루트
if [[ -z "${DVD_BASE:-}" ]]; then
  DVD_BASE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
fi
export DVD_BASE

# 산출물 루트 → bus/
export OUT_DIR="${OUT_DIR:-$DVD_BASE/bus}"
export BUS_LOG="${BUS_LOG:-$OUT_DIR/bus.log}"
export BUS_DVD_LOG="${BUS_DVD_LOG:-$OUT_DIR/bus_dvd.log}"
mkdir -p "$OUT_DIR" "$OUT_DIR/captures/pcap" "$OUT_DIR/snapshots" "$OUT_DIR/pcap"
chmod -R a+rwX "$OUT_DIR" >/dev/null 2>&1 || true

# 자동 감지값이 있으면 로드
if [[ -f "$DVD_BASE/00_env_local.sh" ]]; then
  # shellcheck disable=SC1090
  source "$DVD_BASE/00_env_local.sh"
fi

# 컨테이너/네트워크 기본값 (lite 버전 기준)
export DVD_C_GCS="${DVD_C_GCS:-ground-control-station-lite}"
export DVD_C_CC="${DVD_C_CC:-companion-computer-lite}"
export DVD_C_FC="${DVD_C_FC:-flight-controller-lite}"
export DVD_C_SIM="${DVD_C_SIM:-simulator-lite}"
# ★ 문제 원인: DVD_NET이 비어 있을 수 있음 → 기본값 보장
export DVD_NET="${DVD_NET:-simulator}"

# PATH 보강
export PATH="$DVD_BASE/scripts:$DVD_BASE/modules/attacks:$DVD_BASE/modules/mtd:$DVD_BASE/modules/probe:$PATH"

# (옵션) 요약
if [[ "${ENV_SILENT:-0}" != "1" ]]; then
  echo "ENV OK  base=$DVD_BASE"
  echo "OUT_DIR=$OUT_DIR"
  echo "BUS_LOG=$BUS_LOG"
  echo "BUS_DVD_LOG=$BUS_DVD_LOG"
  echo "DVD_NET=$DVD_NET"
fi
