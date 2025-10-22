#!/bin/bash
#
# start_monitors_root.sh (v2 - Root & VEnv)
#
# [중요] 이 스크립트는 반드시 'sudo'로 실행해야 합니다. (e.g., sudo ./start_monitors_root.sh)
# 1. 루트 권한인지 확인합니다.
# 2. Python 가상 환경(mtd_env)을 활성화합니다.
# 3. 'monitors/' 디렉토리의 모든 스크립트를 백그라운드로 실행합니다.
#

# --- 1. 루트 권한 확인 ---
if [[ $EUID -ne 0 ]]; then
   echo "❌ [오류] 이 스크립트는 반드시 루트 권한(sudo)으로 실행해야 합니다." 
   echo "   (e.g., sudo ./start_monitors_root.sh)"
   exit 1
fi

# --- 2. 환경 변수 설정 ---
# 스크립트가 실행되는 현재 디렉토리 (dvd_lite/dvd_attacks_lpc)
BASE_DIR=$(pwd)
# 활성화할 가상 환경 경로 (사용자 로그 기준)
VENV_PATH="$BASE_DIR/mtd_env/bin/activate"

MONITOR_DIR="monitors"
LOG_DIR="logs/monitors"

# --- 3. 가상 환경 활성화 ---
if [ ! -f "$VENV_PATH" ]; then
    echo "❌ [오류] Python 가상 환경을 찾을 수 없습니다: $VENV_PATH"
    exit 1
fi
echo "[*] Python 가상 환경($VENV_PATH)을 활성화합니다..."
source "$VENV_PATH"

# 4. 로그 디렉토리 생성
mkdir -p $LOG_DIR
echo "[*] 모니터 로그는 $LOG_DIR 디렉토리에 저장됩니다."

# 5. 실행할 모니터 목록 (ls 결과 기준)
MONITORS=(
    "container_monitor.py"
    "dvd_monitor.py"
    "dvd_telemetry_monitor.py"
    "network_traffic_monitor.py"
    "qos_monitor.py"
    "system_event_monitor.py"
)

# 6. 이전 모니터 프로세스 종료
echo "[*] 이전 모니터 프로세스를 종료합니다..."
# pkill -f 를 사용해야 'python3 monitors/...' 경로 전체로 정확히 종료 가능
pkill -f "python3 $MONITOR_DIR/"
sleep 1

# 7. 모든 모니터를 백그라운드에서 실행
echo "[*] 모든 모니터를 시작합니다..."
for monitor in "${MONITORS[@]}"; do
    log_name=$(basename "$monitor" .py)
    
    # [중요] python3가 아닌 'python'을 사용할 경우, venv의 python을 사용하도록 수정
    # (일반적으로 venv 활성화 시 'python3'는 venv의 것을 가리킴)
    python3 "$MONITOR_DIR/$monitor" > "$LOG_DIR/$log_name.log" 2>&1 &
    
    echo "  -> [PID $!] $monitor 시작됨."
done

echo "------------------------------------------------"
echo "✅ 모든 모니터가 루트 권한으로 백그라운드에서 실행 중입니다."
echo "   - 실행 확인: 'pgrep -lf monitors'"
echo "   - 실시간 로그 확인 (권장): 'tail -f $LOG_DIR/network_traffic_monitor.log'"
echo "   - 전체 종료: 'sudo ./stop_monitors_root.sh' 실행"
