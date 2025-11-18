#!/usr/bin/env bash
#
# 통합 CTI 데이터 수집 및 ML 학습 파이프라인
# 1. 모든 모니터를 백그라운드에서 실행합니다.
# 2. 모든 공격을 포함하는 's_cti_data_collection_full' 시나리오를 실행합니다.
# 3. 시나리오 완료 후 ML 학습 파이프라인이 자동으로 실행됩니다.
#

set -e

# --- 1. 환경 설정 및 정리 ---
MONITORS=(
    "monitors/dvd_container_monitor.py"
    "monitors/dvd_telemetry_monitor.py"
    "monitors/network_traffic_monitor.py"
    "monitors/qos_monitor.py"
    "monitors/system_event_monitor.py"
)
SCENARIO_RUNNER="scenarios/dvd_scenario_runner.py"
SCENARIO_NAME="s_cti_data_collection_full"

#echo ">>> 기존 CTI 모니터 프로세스 정리 (clean restart)..."

# 실행 중인 모든 모니터 프로세스를 종료합니다.
# 경로를 기준으로 pkill을 사용하여 DVD 관련 프로세스만 종료합니다.
pkill -f 'python3 monitors/dvd_container_monitor.py' || true
pkill -f 'python3 monitors/dvd_telemetry_monitor.py' || true
pkill -f 'python3 monitors/network_traffic_monitor.py' || true
pkill -f 'python3 monitors/qos_monitor.py' || true
pkill -f 'python3 monitors/system_event_monitor.py' || true

# Bus 로그 디렉토리 생성 및 기존 로그 파일 초기화
BUS_DIR="./bus"
mkdir -p $BUS_DIR
find $BUS_DIR -type f -name 'bus_*.log' -delete || true
echo "Bus logs cleaned up: $BUS_DIR"

# --- 2. 모든 모니터 시작 (백그라운드) ---
echo ">>> 5가지 CTI 모니터링 스크립트 시작..."
PIDS=()
for monitor in "${MONITORS[@]}"; do
    if [ -f "$monitor" ]; then
        echo "  -> Starting $monitor in background..."
        # PYTHONUNBUFFERED=1로 실시간 로그 보장
        PYTHONUNBUFFERED=1 python3 "$monitor" &
        PIDS+=($!)
        sleep 0.5 
    else
        echo "  -> [SKIP] Monitor script not found: $monitor"
    fi
done

# 모니터가 초기화되고 연결할 시간을 확보합니다.
echo ">>> 모니터 초기화 시간 확보 (10초 대기)..."
sleep 10 

# --- 3. 통합 시나리오 실행 (데이터 수집 및 ML 파이프라인) ---
echo ">>> 통합 시나리오 실행: $SCENARIO_NAME"
echo ">>> 이 단계에서 모든 공격이 실행되고 데이터가 수집되며, 완료 후 ML 학습이 자동 실행됩니다."

if [ ! -f "$SCENARIO_RUNNER" ]; then
    echo "!!! [FATAL] 시나리오 실행 파일을 찾을 수 없습니다: $SCENARIO_RUNNER"
    exit 1
fi

python3 "$SCENARIO_RUNNER" --scenario "$SCENARIO_NAME"
SCENARIO_RC=$?

# --- 4. 최종 정리 ---
echo ">>> 시나리오 완료. 백그라운드 모니터 정리 (PID: ${PIDS[*]})."
for pid in "${PIDS[@]}"; do
    if kill -0 $pid 2>/dev/null; then
        kill $pid
    fi
done

echo ">>> CTI 데이터 수집 및 ML 파이프라인 완료. (시나리오 RC: $SCENARIO_RC)"
echo ">>> 학습 결과 파일은 ml/output/ 폴더에서 확인하세요."

exit $SCENARIO_RC