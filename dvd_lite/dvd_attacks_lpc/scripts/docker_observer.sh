#!/usr/bin/env bash
set -Eeuo pipefail

usage() { echo "usage: $0 <out_dir> <stage:pre|post>"; exit 2; }

OUT_DIR="${1:-}"; STAGE="${2:-}"
[[ -n "$OUT_DIR" && -n "$STAGE" ]] || usage
mkdir -p "$OUT_DIR"

STAMP="$(date +'%Y%m%d_%H%M%S')"
OUT="${OUT_DIR}/docker_${STAGE}_${STAMP}.txt"

if command -v docker >/dev/null 2>&1; then
  {
    echo "### docker ps -a"; docker ps -a
    echo; echo "### docker stats --no-stream"; docker stats --no-stream || true
    echo; echo "### docker network ls"; docker network ls
    echo; echo "### docker images"; docker images
  } | tee "$OUT" >/dev/null
else
  echo "[docker_observer] docker not found, skipping." | tee "$OUT" >/dev/null
fi
