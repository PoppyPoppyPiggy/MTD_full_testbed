#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
source "$BASE/00_env.sh"
mkdir -p "$LPC_LOG_DIR"

# 프리셋 적용
[[ -f "$BASE/scenarios/presets.env" ]] && source "$BASE/scenarios/presets.env"

SC="$1"; shift || true
# (선택) MTD 로그 감시 백그라운드
# ( "$BASE/sh_core/lpc_hooks.sh" watch_mtd_events ) &

while IFS= read -r line; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  ( cd "$BASE" && eval "$line" ) &
done < "$SC"

wait
echo "[run_scenario] done: $SC"
