#!/usr/bin/env bash
# 컬러 tail -f
LOG="${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/attack_output/bus.log}"
tput sgr0 >/dev/null 2>&1 || true
tail -F "$LOG" | awk '
  function color(c){printf "\033[" c "m"}
  /telemetry_trickle_jam/ {color("36"); print; color("0"); next}
  /mavlink_param_drift/   {color("35"); print; color("0"); next}
  /\[LPC\]/               {color("90"); print; color("0"); next}
  {print}
'
