#!/usr/bin/env bash
set -exuo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPE="${1:-}"; [[ -f "$PIPE" ]] || { echo "Usage: $0 <pipeline.yml>" >&2; exit 2; }
export PYTHONUNBUFFERED=1
stdbuf -oL -eL python3 -u "$THIS_DIR/run_pipeline.py" "$PIPE"
