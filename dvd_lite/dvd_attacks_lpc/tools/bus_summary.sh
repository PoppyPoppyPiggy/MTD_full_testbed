#!/usr/bin/env bash
LOG="${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/attack_output/bus.log}"
echo "== bus summary =="
awk '
  /\[telemetry_trickle_jam\]/ {tj++}
  /\[mavlink_param_drift\]/   {md++}
  END{
    printf("telemetry_trickle_jam: %d\n", tj+0);
    printf("mavlink_param_drift:  %d\n", md+0);
  }
' "$LOG"
