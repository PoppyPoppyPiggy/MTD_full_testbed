#!/usr/bin/env bash
set -euo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YAML="${1:-$THIS_DIR/pipelines/user_defined_template.yml}"
python3 "$THIS_DIR/run_pipeline.py" "$YAML"
