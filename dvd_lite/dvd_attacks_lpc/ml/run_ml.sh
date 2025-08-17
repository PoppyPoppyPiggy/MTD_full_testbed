#!/usr/bin/env bash
set -euo pipefail
# 실행 위치: dvd_lite/dvd_attacks_lpc
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=${PYTHON:-python3}

echo "==[1/2] build dataset from attack_output =="
$PY ml/build_supervised.py \
  --attack-output ./attack_output \
  --outdir ../../supervised_data \
  --default-win "${WIN:-5}" \
  --blind "${BLIND:-2}"

echo "==[2/2] train baseline =="
$PY ml/train_baseline.py \
  --dataset ../../supervised_data/unified_dataset.parquet

echo "[DONE]"
