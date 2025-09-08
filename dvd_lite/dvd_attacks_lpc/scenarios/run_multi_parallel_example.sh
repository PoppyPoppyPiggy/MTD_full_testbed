#!/usr/bin/env bash
set -euo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$THIS_DIR/run_pipeline.py" "$THIS_DIR/pipelines/multi_parallel_example.yml"
