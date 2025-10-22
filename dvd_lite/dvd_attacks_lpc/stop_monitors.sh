#!/bin/bash
#
# stop_monitors_root.sh
#
# [중요] 이 스크립트는 반드시 'sudo'로 실행해야 합니다.
# 'monitors/' 디렉토리에서 실행된 모든 파이썬 모니터 프로세스를 종료합니다.
#

# --- 1. 루트 권한 확인 ---
if [[ $EUID -ne 0 ]]; then
   echo "❌ [오류] 이 스크립트는 반드시 루트 권한(sudo)으로 실행해야 합니다." 
   echo "   (e.g., sudo ./stop_monitors_root.sh)"
   exit 1
fi

MONITOR_DIR="monitors"

echo "[*] 'monitors/' 디렉토리에서 실행된 모든 Python 모니터를 종료합니다..."

# pkill -f 옵션으로 'python3 monitors/' 문자열을 포함하는 모든 프로세스 종료
pkill -f "python3 $MONITOR_DIR/"

sleep 1
echo "✅ 모든 모니터가 종료되었습니다."
