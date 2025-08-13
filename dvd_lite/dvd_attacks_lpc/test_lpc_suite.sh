#!/usr/bin/env bash
set -euo pipefail
echo "=== LPC 공격 모듈 통합 테스트 ==="
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"
source 00_env.sh

TEST_OUTPUT="test_output/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEST_OUTPUT"

modules=( "wifi_slow_scan" "telemetry_trickle_jam" "mavlink_param_drift" "gps_slow_spoof" "power_route_bias" "service_enum_probe" )

for m in "${modules[@]}"; do
  echo "테스트: $m"
  for intensity in low medium high; do
    echo "  강도: $intensity"
    timeout 10s env DUR=8 INTENSITY="$intensity" "modules/${m}.sh" || true
    sleep 1
  done
done

echo "다중 시나리오"
timeout 90s scenarios/S_lpc_multi.pipeline || true

cp attack_output/* "$TEST_OUTPUT/" 2>/dev/null || true
echo "결과: $TEST_OUTPUT"
wc -l "$TEST_OUTPUT/bus.log" 2>/dev/null || echo "로그 없음"
echo "=== 테스트 종료 ==="
