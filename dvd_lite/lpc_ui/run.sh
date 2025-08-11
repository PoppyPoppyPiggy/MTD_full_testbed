#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv || true
. .venv/bin/activate
pip install --upgrade pip wheel
pip install flask
export FLASK_ENV=production
exec python app.py
