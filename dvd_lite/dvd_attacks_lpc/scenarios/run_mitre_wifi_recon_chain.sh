#!/usr/bin/env bash
set -exuo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONUNBUFFERED=1
stdbuf -oL -eL python3 -u "$THIS_DIR/run_pipeline.py" "$THIS_DIR/pipelines/mitre_wifi_recon_chain.yml"
