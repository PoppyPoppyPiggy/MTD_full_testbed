#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
. "$BASE/00_env_ext.sh"

# 예시: 랜덤 포트 산출(인용 안전)
NEW_PORT="$(python3 - <<'PY'
import random
print(random.randint(20000, 40000))
PY
)"
echo "MTD port shuffle -> $NEW_PORT" >> "$BUS_LOG"
sleep 1
