#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$BASE/00_env_ext.sh"
ACTION="${1:-none}"
ROLE="${2:-gcs}"; SVC="${3:-mavlink}"
case "$ACTION" in
  none)
    echo "$(date +%s),MTD_REVERT,action=none" >> "$BUS_LOG"
    bash modules/mtd/mtd_tc_filter.sh revert "$ROLE" "$SVC" || true
    ;;
  tc_soft)
    echo "$(date +%s),MTD_APPLY,action=tc_soft,loss_pct=1,delay_ms=2,jitter_ms=1,dup_pct=0" >> "$BUS_LOG"
    bash modules/mtd/mtd_tc_filter.sh apply "$ROLE" "$SVC" || true
    ;;
  tc_med)
    echo "$(date +%s),MTD_APPLY,action=tc_med,loss_pct=2.5,delay_ms=5,jitter_ms=2,dup_pct=0.5" >> "$BUS_LOG"
    bash modules/mtd/mtd_tc_filter.sh apply "$ROLE" "$SVC" || true
    ;;
  tc_hard)
    echo "$(date +%s),MTD_APPLY,action=tc_hard,loss_pct=5,delay_ms=8,jitter_ms=3,dup_pct=1" >> "$BUS_LOG"
    bash modules/mtd/mtd_tc_filter.sh apply "$ROLE" "$SVC" || true
    ;;
  *)
    echo "unknown action: $ACTION" >&2; exit 2;;
esac
