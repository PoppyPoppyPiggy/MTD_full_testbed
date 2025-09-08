#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"; source ./00_env_ext.sh
WIN_S=${WIN_S:-5} CONF_TH=${CONF_TH:-0.6} DRY_RUN=${DRY_RUN:-1}
python3 tools/infer_attack_now.py
