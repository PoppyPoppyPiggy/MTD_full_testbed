# ~/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/00_env.sh
#!/usr/bin/env bash


# 기준 경로
export BASE="${BASE:-$PWD}"

# 산출물/로그
export OUT_DIR="${OUT_DIR:-$BASE/attack_output}"
mkdir -p "$OUT_DIR"
export DVD_LOG="${DVD_LOG:-$OUT_DIR/dvd.log}"

# 항상 log 함수를 보장
log() { printf '[%(%F_%T)T] %s\n' -1 "$*"; }
export -f log 2>/dev/null || true

# MAVLink 엔드포인트 기본값(필요시 덮어쓰기)
export MAV_EP="${MAV_EP:-udp:127.0.0.1:14550}"
export TARGET_EP="${TARGET_EP:-}"
