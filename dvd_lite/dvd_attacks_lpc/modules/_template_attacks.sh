# 공통 템플릿
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"
