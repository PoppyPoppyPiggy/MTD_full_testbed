#!/usr/bin/env bash
set -euo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$THIS_DIR/run_pipeline.py" "$THIS_DIR/pipelines/mitre_wifi_recon_chain.yml"
