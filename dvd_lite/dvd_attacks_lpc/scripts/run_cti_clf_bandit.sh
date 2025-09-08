#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$BASE"; source ./00_env_ext.sh
echo "[1/4] CTI 윈도우 피처 갱신"; python3 tools/make_window_features.py
echo "[2/4] 지도학습 분류기 학습";  python3 ml/train_attack_clf.py || true
echo "[3/4] 임팩트 리포트 집계";     python3 tools/summarize_metrics.py || true
echo "[4/4] 밴딧 정책 산출";         python3 rl/rl_mtd_offline.py
echo "DONE. models @ bus/models/"
