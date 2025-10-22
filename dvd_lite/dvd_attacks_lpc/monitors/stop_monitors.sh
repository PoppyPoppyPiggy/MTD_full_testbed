#!/bin/bash
#
# stop_monitors.sh
#
# 'monitors/' 디렉토리에서 실행된 모든 파이썬 모니터 프로세스를 종료합니다.
#

MONITOR_DIR="monitors"

echo "Finding and stopping all Python monitors running from $MONITOR_DIR/ ..."

# pkill -f 옵션은 전체 커맨드 라인 경로에서 "python3 monitors/" 문자열을
# 포함하는 모든 프로세스를 찾아 종료(SIGTERM)합니다.
# 이는 다른 파이썬 프로세스를 건드리지 않는 안전한 방법입니다.
pkill -f "python3 $MONITOR_DIR/"

sleep 1
echo "✅ 모든 모니터가 종료되었습니다."
