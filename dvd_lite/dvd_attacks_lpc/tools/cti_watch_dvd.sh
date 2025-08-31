#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/tools/cti_watch_dvd.sh
# DVD 컨테이너(GCS/CC/FC/SIM)의 IP/포트/브리지 상태를 주기적으로 스냅샷.
set -euo pipefail
. "$(dirname "$0")/log_event.sh"
INTERVAL="${1:-1s}"

STATE="$(mktemp)"; trap 'rm -f "$STATE"' EXIT

function snap_json() {
  # 컨테이너 목록은 환경에 맞게 조정
  local arr=(dvd_gcs dvd_cc dvd_fc dvd_sim)
  echo "{"; for c in "${arr[@]}"; do
    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$c" 2>/dev/null || echo "")
    # MAVLink/서비스 포트(UDP listen) 수집
    ports=$(docker exec "$c" sh -lc "ss -lunH | awk '{print \$5}' | awk -F: '{print \$NF}' | sort -n | tr '\n' ','" 2>/dev/null || echo "")
    br=$(docker exec "$c" sh -lc "brctl show 2>/dev/null | awk 'NR>1{print \$1\":\"\$4}' | tr '\n' ','" 2>/dev/null || echo "")
    printf '"%s":{"ip":"%s","udp":"%s","bridge":"%s"},' "$c" "$ip" "$ports" "$br"
  done | sed 's/,$//'
  echo "}"
}

function diff_and_log() {
  local old="$1" new="$2"
  # ip 변화
  for c in dvd_gcs dvd_cc dvd_fc dvd_sim; do
    old_ip=$(jq -r --arg c "$c" '.[$c].ip // empty' "$old" 2>/dev/null || true)
    new_ip=$(jq -r --arg c "$c" '.[$c].ip // empty' "$new" 2>/dev/null || true)
    if [[ -n "$old_ip" && -n "$new_ip" && "$old_ip" != "$new_ip" ]]; then
      log_event cti type=ip_change src="$c" old="$old_ip" new="$new_ip"
    fi
    old_ports=$(jq -r --arg c "$c" '.[$c].udp // empty' "$old" 2>/dev/null || true)
    new_ports=$(jq -r --arg c "$c" '.[$c].udp // empty' "$new" 2>/dev/null || true)
    if [[ -n "$old_ports" && -n "$new_ports" && "$old_ports" != "$new_ports" ]]; then
      log_event cti type=port_change src="$c" udp_old="$old_ports" udp_new="$new_ports"
    fi
    old_br=$(jq -r --arg c "$c" '.[$c].bridge // empty' "$old" 2>/dev/null || true)
    new_br=$(jq -r --arg c "$c" '.[$c].bridge // empty' "$new" 2>/dev/null || true)
    if [[ -n "$old_br" && -n "$new_br" && "$old_br" != "$new_br" ]]; then
      log_event cti type=bridge_change src="$c" old="$old_br" new="$new_br"
    fi
  done
}

# 루프
prev="$(mktemp)"
snap_json > "$prev"
while true; do
  sleep "$INTERVAL"
  now="$(mktemp)"; snap_json > "$now"
  diff_and_log "$prev" "$now"
  mv "$now" "$prev"
done
