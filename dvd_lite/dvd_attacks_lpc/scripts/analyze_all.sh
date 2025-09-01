#!/usr/bin/env bash
set -Eeuo pipefail

: "${ATK_DIR:?ATK_DIR not set}"

ROOT="${ATK_DIR}"

# 전체 트리 스캔 → 차트 및 스코어 산출
python3 "${ATK_DIR}/tools/mtd_analyzer.py" --root "${ROOT}" --save-charts

echo "[analyze_all] done."
