#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/dvd_attacks_lpc}"
OUT="$BASE/attack_output"
mkdir -p "$OUT"

python3 "$BASE/tools/gen_effects_timeline.py"
python3 "$BASE/tools/lpc_metrics.py"
"$BASE/eval/run_eval.sh" || true

# (선택) 추론 훅
if [ -f "$BASE/defense/predict_once.py" ]; then
  python3 "$BASE/defense/predict_once.py" "$OUT/window_features.csv" || true
fi
