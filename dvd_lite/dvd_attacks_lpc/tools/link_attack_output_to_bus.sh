#!/usr/bin/env bash
set -Eeuo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"

mkdir -p bus
# attack_output이 실디렉토리면 내용 sync 후 교체
if [ -d attack_output ] && [ ! -L attack_output ]; then
  rsync -a attack_output/ bus/ || true
  rm -rf attack_output
fi
# 없으면 그대로 링크 생성
ln -snf bus attack_output

# 최종 확인
echo "[OK] attack_output -> $(readlink -f attack_output)"
ls -ld attack_output
