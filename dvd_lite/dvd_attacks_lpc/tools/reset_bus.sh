#!/usr/bin/env bash
set -Eeuo pipefail
BASE="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc"

# 안전 가드: 경로 확인
case "$BASE" in
  */dvd_attacks_lpc) ;;
  *) echo "[ABORT] BASE guard failed: $BASE"; exit 2;;
esac

TS="$(date +%Y%m%d_%H%M%S)"
cd "$BASE"

# 1) 기존 bus 백업
if [ -d bus ]; then
  tar -czf "bus_backup_${TS}.tar.gz" bus || true
  echo "[ARCHIVE] -> $BASE/bus_backup_${TS}.tar.gz"
fi

# 2) 흔적 제거
rm -rf bus || true
rm -rf scripts/bus || true    # 잘못된 OUT_DIR 오염 방지
mkdir -p bus/captures/pcap

# 3) 로그 파일 프리시드(있으면 덮어쓰기)
: > bus/bus.log
: > bus/bus_dvd.log

echo "[RESET DONE] Fresh bus at: $BASE/bus"
