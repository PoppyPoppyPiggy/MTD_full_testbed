#!/usr/bin/env bash
#
# CTI 데이터 수집 및 ML 학습 통합 파이프라인
# 1. 모든 모니터를 백그라운드에서 실행합니다. (Ctrl+C 시 자동 종료)
# 2. 5개의 CTI 수집 시나리오 (s1 ~ s5)를 순차적으로 실행합니다.
# 3. 모든 로그를 취합하여 Data Builder, Dataset Manager, Classifier Trainer를 순차 실행합니다.
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
CTI_SCENARIOS=("s1_cti_recon_tampering" "s2_cti_adv_tampering_injection" "s3_cti_dos_injection" "s4_cti_exfil_advanced" "s5_cti_normal")
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

# ⭐️ [수정] 기존 로그 파일 백업 및 새 폴더 생성
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

# --- 3. CTI 데이터 수집 시나리오 순차 실행 ---
echo -e "\n============================================================="
echo ">>> CTI 데이터 수집 시나리오 순차 실행 시작"
echo "============================================================="

for scenario in "${CTI_SCENARIOS[@]}"; do
    echo -e "\n--- [SCENARIO START] Running: $scenario ---"
    python3 "$SCENARIO_RUNNER" --scenario "$scenario"
    echo "--- [SCENARIO END] $scenario 완료. 5초 대기. ---"
    sleep 5
done

# --- 4. ML 학습 파이프라인 실행 (CTI Agent 역할) ---
# 이 단계는 모니터가 여전히 백그라운드에서 실행 중일 때 수행됩니다.
echo -e "\n============================================================="
echo "🤖 [ML PIPELINE] 데이터 취합 및 분류기 학습 시작"
echo "============================================================="

echo "[ML 1/3] Data Builder 실행 (로그 병합 및 특징 벡터 생성)..."
python3 "$DATA_BUILDER" --mode "batch"
echo "✅ Data Builder 완료."

echo "[ML 2/3] Dataset Manager 실행 (훈련/테스트 데이터셋 분할)..."
python3 "$DATASET_MANAGER" --test-size 0.2
echo "✅ Dataset Manager 완료."

echo "[ML 3/3] Classifier Trainer 실행 (모델 훈련 및 평가)..."
python3 "$TRAIN_CLASSIFIER"
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
```

## 실행 방법

위 스크립트를 `run_cti_data_pipeline.sh`로 저장하고, **반드시 `sudo`를 사용하여 실행**하십시오.

```bash
# DVD_ATTACKS_LPC 디렉토리에서 실행
sudo python3 run_cti_data_pipeline.sh