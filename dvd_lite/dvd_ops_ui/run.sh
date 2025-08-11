#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv || true
. .venv/bin/activate
pip install --upgrade pip wheel
pip install flask
export FLASK_ENV=production
# DVD 컨테이너 필터 키워드 바꾸려면 아래 환경변수 사용:
# export DVD_NAME_FILTER="damn-vulnerable-drone"
exec python app.py
