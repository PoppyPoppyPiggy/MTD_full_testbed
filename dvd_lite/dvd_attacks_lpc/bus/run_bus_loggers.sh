#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-$PWD}"
export BASE

# venv PATH 우선
if [[ -d "$BASE/mtd_env/bin" ]]; then
  export PATH="$BASE/mtd_env/bin:$PATH"
fi

# 의존 설치
python3 -m pip install -q pyyaml scapy || true

# 버스 로깅 시작(백그라운드)
nohup python3 "$BASE/bus/logger_bus.py" \
  --iface auto \
  --listen-cidr "10.13.0.0/24" \
  --gcs "10.13.0.4:14550" \
  --out "$BASE/attack_output/bus.log" \
  >"$BASE/attack_output/logger_bus.stdout" 2>&1 &

# DVD 의사결정 로깅 시작(적용은 로그만; 실제 iptables 적용하려면 --apply)
nohup python3 "$BASE/bus/logger_dvd.py" \
  --base "$BASE" \
  --policy "$BASE/configs/mtd_policy.yaml" \
  --bus "$BASE/attack_output/bus.log" \
  --out "$BASE/attack_output/bus_dvd.log" \
  >"$BASE/attack_output/logger_dvd.stdout" 2>&1 &
echo "[✓] loggers started. tail -f $BASE/attack_output/bus.log $BASE/attack_output/bus_dvd.log"
