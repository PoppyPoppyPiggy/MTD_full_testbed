#!/usr/bin/env bash
#
# CTI 데이터 수집 및 ML 학습 통합 파이프라인 (Core 6 - 5회 반복 버전)
# 1. 모든 모니터를 백그라운드에서 실행합니다.
# 2. Core 6 시나리오를 5회 반복 실행하여 bus.log에 데이터를 누적합니다.
# 3. 마지막에 한 번 Data Builder, Dataset Manager, Classifier Trainer를 실행합니다.
#
# ⭐️ 실행 권한: 반드시 'sudo'로 실행해야 권한 오류(Errno 13)가 발생하지 않습니다.
#

# 스크립트 실행 중 오류 발생 시 즉시 종료
set -e

# --- 1. 환경 및 경로 설정 ---
MONITORS=(
    "monitors/dvd_container_monitor.py"
    "monitors/dvd_telemetry_monitor.py"
    "monitors/network_traffic_monitor.py"
    "monitors/qos_monitor.py"
    "monitors/system_event_monitor.py"
)
SCENARIO_RUNNER="./scenarios/dvd_scenario_runner.py"

DATA_BUILDER="./ml/data_builder.py"
DATASET_MANAGER="./ml/dataset_manager.py"
TRAIN_CLASSIFIER="./ml/train_classifier.py"

BUS_DIR="./bus"
PIDS=() 

# --- Ctrl+C 및 종료 시 백그라운드 프로세스 정리 함수 (SIGINT/SIGTERM 대응) ---
cleanup_on_exit() {
    echo -e "\n>>> Ctrl+C (SIGINT) 수신! 백그라운드 모니터 정리 시작..."
    for pid in "${PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            echo "  -> Terminating monitor PID $pid"
            kill $pid 2>/dev/null
            sleep 0.5
            if kill -0 $pid 2>/dev/null; then
                echo "  -> PID $pid 응답 없음. 강제 종료 (SIGKILL)."
                kill -9 $pid 2>/dev/null
            fi
        fi
    done
    echo ">>> 백그라운드 모니터 프로세스 정리 완료."
    exit 130
}

# SIGINT (Ctrl+C)와 SIGTERM에 정리 함수 연결
trap cleanup_on_exit SIGINT SIGTERM

echo ">>> 기존 CTI 모니터 프로세스 정리 및 로그 백업..."
pkill -f 'python3 monitors/' || true # 모든 모니터 정리

# 기존 로그 파일 백업 및 새 폴더 생성
if [ -d "$BUS_DIR" ]; then
    if [ "$(ls -A "$BUS_DIR" 2>/dev/null)" ]; then
        BACKUP_NAME="bus_backup_$(date +%Y%m%d_%H%M%S)"
        echo ">>> 이전 bus 로그를 다음으로 백업합니다: $BACKUP_NAME"
        mv "$BUS_DIR" "$BACKUP_NAME"
    fi
fi
mkdir -p "$BUS_DIR"
echo "새 bus logs directory 생성 및 초기화 완료: $BUS_DIR"


# --- 2. 모든 모니터 시작 (백그라운드) ---
echo ">>> 5가지 CTI 모니터링 스크립트 시작..."
for monitor in "${MONITORS[@]}"; do
    if [ -f "$monitor" ]; then
        echo "  -> Starting $monitor in background..."
        PYTHONUNBUFFERED=1 python3 "$monitor" &
        PIDS+=($!) # PID 배열에 추가 (Ctrl+C 처리를 위해)
        sleep 0.5 
    else
        echo "  -> [SKIP] Monitor script not found: $monitor"
    fi
done

echo ">>> 모니터 초기화 시간 확보 (10초 대기)..."
sleep 10 

# --- 3. Core 6 시나리오 5회 반복 실행 ---
# 반복 횟수 설정
ITERATIONS=5
SCENARIO_NAME="s_cti_data_collection_core6"

echo -e "\n============================================================="
echo ">>> [CTI] $SCENARIO_NAME 시나리오 $ITERATIONS 회 반복 실행 시작"
echo "============================================================="

for ((i=1; i<=ITERATIONS; i++)); do
    echo -e "\n--- [RUN $i / $ITERATIONS] Starting Scenario: $SCENARIO_NAME ---"
    python3 "$SCENARIO_RUNNER" --scenario "$SCENARIO_NAME"
    echo "--- [RUN $i] 완료. 5초 대기 후 다음 실행. ---"
    sleep 5
done

# --- 4. ML 학습 파이프라인 실행 (데이터 취합) ---
# 이 단계는 모든 시나리오 반복이 끝난 후 한 번만 실행됩니다.
# 데이터는 ./bus/bus.log에 계속 누적되어 있습니다.

echo -e "\n============================================================="
echo "🤖 [ML PIPELINE] 5회분 데이터 취합 및 분류기 학습 시작"
echo "============================================================="

# 절대 경로 설정을 위해 python3 실행 시 경로 주의
ML_DIR=$(realpath ./ml)
PROCESSED_DIR="$ML_DIR/processed_data"

echo "[ML 1/3] Data Builder 실행 (로그 병합 및 특징 벡터 생성)..."
# bus.log 전체를 읽어서 처리합니다.
python3 "$DATA_BUILDER" --mode "batch" --log-file "./bus/bus.log" --output-dir "$PROCESSED_DIR"
echo "✅ Data Builder 완료."

echo "[ML 2/3] Dataset Manager 실행 (훈련/테스트 데이터셋 분할)..."
# 🔥 중요: 생성된 CSV가 있는 절대 경로를 전달합니다.
python3 "$DATASET_MANAGER" --test-size 0.2 --processed-dir "$PROCESSED_DIR" --output-dir "$ML_DIR/output"
echo "✅ Dataset Manager 완료."

echo "[ML 3/3] Classifier Trainer 실행 (모델 훈련 및 평가)..."
# 학습 및 테스트 데이터 경로도 명시적으로 전달 (선택 사항이지만 안전함)
python3 "$TRAIN_CLASSIFIER" --train-data "$ML_DIR/output/train_dataset.csv" --test-data "$ML_DIR/output/test_dataset.csv" --output-dir "$ML_DIR/output"
echo "✅ Classifier Trainer 완료."

# --- 5. 최종 정리 (모니터 종료) ---
echo -e "\n>>> 모든 작업 완료. 백그라운드 모니터 정리."
for pid in "${PIDS[@]}"; do
    if kill -0 $pid 2>/dev/null; then
        echo "  -> Sending TERM to monitor PID $pid"
        kill $pid 2>/dev/null
    fi
done

echo ">>> CTI 데이터 수집 및 ML 파이프라인 최종 완료."
echo ">>> 학습 결과 파일은 ml/output/ 폴더에서 확인하세요."

exit 0