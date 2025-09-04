#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"
LEVEL="${1:-low}"
TARGETS_YML="$BASE/modules/attacks/targets/targets.yml"

SUBNET="$(python3 "$BASE/modules/attacks/resolve_target.py" "$TARGETS_YML" gcs | jq -r '.subnet')"
[ -z "$SUBNET" ] && SUBNET="172.18.0.0/16"

case "$LEVEL" in
  low)  MINRATE=10;  WAIT=10 ;;
  mid|med)  MINRATE=50;  WAIT=6 ;;
  high) MINRATE=120; WAIT=3 ;;
  *)    MINRATE=30;  WAIT=8 ;;
esac

echo "[$(date +%s)] BUS ATK ATTACK_START wifi_slow_scan subnet=$SUBNET minrate=$MINRATE" >> "$BUS_LOG"

for i in $(seq 1 3); do
  nmap -Pn -T2 --min-rate $MINRATE -sS --max-retries 1 --host-timeout 10s "$SUBNET" >/dev/null 2>&1 || true
  sleep "$WAIT"
done

echo "[$(date +%s)] BUS ATK ATTACK_END wifi_slow_scan" >> "$BUS_LOG"
