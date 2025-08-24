#!/usr/bin/env bash
# Apply TBF rate cap on container interface for limited duration.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/netem.sh"; . "$BASE/sh_core/metrics.sh"

: "${RATE_MBPS:=5}"
: "${DUR:=10}"

main(){
  log "[network_rate_cap] mode=$LPC_MODE rate=${RATE_MBPS}Mbps dur=${DUR}s target=$DVD_C_GCS/$DVD_TARGET_IF"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then rate_cap_apply "$DVD_C_GCS" "$RATE_MBPS"; fi
  bus_emit "net" "action=rate_cap target=$DVD_C_GCS if=$DVD_TARGET_IF rate_mbps=$RATE_MBPS"
  effect_emit "rate_limit_mbps=$RATE_MBPS"
  sleep "$DUR"
  rate_cap_clear "$DVD_C_GCS" || true
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "net_obs"
}
main "$@"
