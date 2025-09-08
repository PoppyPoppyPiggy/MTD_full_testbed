#!/usr/bin/env bash
if [ -n "${BASH_VERSION:-}" ]; then set -euo pipefail; fi
THIS_FILE="${BASH_SOURCE[0]}"
BASE="$(cd "$(dirname "$THIS_FILE")" && pwd)"
export BASE

OUT_DIR="$BASE/bus"; export OUT_DIR
mkdir -p "$OUT_DIR" "$OUT_DIR/captures/pcap" "$OUT_DIR/snapshots" "$OUT_DIR/_charts"

# 단일 수집지: JSONL 두 개로 단순화
export BUS_LOG="$OUT_DIR/bus.log"
export DVD_JSONL="$OUT_DIR/dvd.jsonl"
export MTD_JSONL="$OUT_DIR/mtd.jsonl"
touch "$BUS_LOG" "$DVD_JSONL" "$MTD_JSONL"

echo "ENV OK  base=$BASE"
echo "OUT_DIR=$OUT_DIR"
echo "BUS_LOG=$BUS_LOG"
echo "DVD_JSONL=$DVD_JSONL"
