#!/bin/bash
#
# start_monitors.sh
#
# 'monitors/' 디렉토리 내의 모든 파이썬 모니터 스크립트를
# 백그라운드에서 동시에 실행합니다.
#
# [중요] 이 스크립트는 'dvd_lite/dvd_attacks_lpc' 디렉토리에서 실행해야 합니다.
#

# 1. 디렉토리 정의
MONITOR_DIR="monitors"
# 로그를 저장할 디렉토리
LOG_DIR="logs/monitors"

# 2. 로그 디렉토리 생성
# -p 플래그는 디렉토리가 이미 존재해도 오류를 발생시키지 않습니다.
mkdir -p $LOG_DIR
echo "모니터 로그는 $LOG_DIR 디렉토리에 저장됩니다."

# 3. 실행할 모니터 목록 (제공된 'ls' 목록 기준)
MONITORS=(
    "container_monitor.py"
    "dvd_monitor.py"
    "dvd_telemetry_monitor.py"
    "network_traffic_monitor.py"
    "qos_monitor.py"
    "system_event_monitor.py"
)

# 4. (선택) 이전에 실행 중이던 모니터가 있다면 종료
echo "이전 모니터 프로세스를 종료합니다..."
# pkill -f 를 사용하여 커맨드 라인 전체(경로 포함)를 기준으로 프로세스 종료
pkill -f "python3 $MONITOR_DIR/"
sleep 1 # 종료 대기

# 5. 모든 모니터를 백그라운드에서 실행
echo "모든 모니터를 시작합니다..."
for monitor in "${MONITORS[@]}"; do
    # 로그 파일 이름을 스크립트 이름에서 .py를 제외하고 만듭니다.
    log_name=$(basename "$monitor" .py)
    
    # 스크립트 실행:
    # > "$LOG_DIR/$log_name.log" : 표준 출력(stdout)을 로그 파일로 리디렉션
    # 2>&1 : 표준 에러(stderr)를 표준 출력(stdout)과 같은 위치(로그 파일)로 리디렉션
    # & : 프로세스를 백그라운드에서 실행
    python3 "$MONITOR_DIR/$monitor" > "$LOG_DIR/$log_name.log" 2>&1 &
    
    # 백그라운드 작업의 프로세스 ID(PID) 출력
    echo "  -> [PID $!] $monitor 시작됨."
done

echo "------------------------------------------------"
echo "✅ 모든 모니터가 백그라운드에서 실행 중입니다."
echo "   - 실행 확인: 'jobs -l' 또는 'pgrep -lf monitors'"
echo "   - 실시간 로그 확인: 'tail -f $LOG_DIR/<스크립트명>.log'"
echo "   - 전체 종료: './stop_monitors.sh' 실행"
