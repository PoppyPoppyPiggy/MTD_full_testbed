#!/usr/bin/env bash
# MAVLink packet injection / noise flood (lab-safe)
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${COUNT:=300}"
: "${SLEEP_MS:=10}"
: "${DUR:=3}"

main(){
  log "[mavlink_packet_injection] mode=$LPC_MODE count=$COUNT sleep_ms=$SLEEP_MS dur=$DUR"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    python3 "$BASE/interface/mavlink_noise.py" --host "$DVD_MAVLINK_HOST" --port "$DVD_MAVLINK_PORT" \
      --count "$COUNT" --sleep-ms "$SLEEP_MS" || true
    bus_emit "mavlink" "action=packet_injection count=$COUNT sleep_ms=$SLEEP_MS target=${DVD_MAVLINK_HOST}:${DVD_MAVLINK_PORT}"
  else
    bus_emit "mavlink" "action=packet_injection_sim count=$COUNT sleep_ms=$SLEEP_MS"
    effect_emit "jitter_ms=1"
  fi
  sleep "$DUR"
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "mavlink_obs"
}
main "$@"
