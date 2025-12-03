#!/usr/bin/env bash
#
# CTI 데이터 수집 및 ML 학습 통합 파이프라인 v2.0 (Fixed)
# ============================================================
# 1. 모든 모니터를 백그라운드에서 실행합니다.
# 2. 지정된 시나리오를 N회 반복 실행하여 데이터를 누적합니다.
# 3. 마지막에 한 번 Data Builder, Dataset Manager, Classifier Trainer를 실행합니다.
#
# ⭐️ 실행 권한: 반드시 'sudo'로 실행해야 권한 오류가 발생하지 않습니다.
#    (network_traffic_monitor.py의 pyshark는 root 권한 필요)
#
# 사용법:
#   sudo bash run_cti_data_pipeline.sh                     # 기본 (Core6 x 5회)
#   sudo bash run_cti_data_pipeline.sh quick_top5 3        # quick_top5 x 3회
#   sudo bash run_cti_data_pipeline.sh balanced_8 10       # balanced_8 x 10회
#

set -e

# =============================================================================
# 설정
# =============================================================================

# 시나리오 및 반복 횟수 (CLI 인자로 오버라이드 가능)
SCENARIO_NAME="${1:-s_cti_data_collection_core6}"
ITERATIONS="${2:-5}"

# 경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
ML_DIR="./ml"
OUTPUT_DIR="$ML_DIR/output"

PIDS=()

# =============================================================================
# 함수 정의
# =============================================================================

# 색상 출력
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Ctrl+C 및 종료 시 백그라운드 프로세스 정리
cleanup_on_exit() {
    echo -e "\n"
    log_warn "종료 신호 수신! 백그라운드 모니터 정리 중..."
    
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "  -> Terminating monitor PID $pid"
            kill "$pid" 2>/dev/null || true
            sleep 0.3
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "  -> PID $pid 강제 종료 (SIGKILL)"
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
    done
    
    # Python 모니터 프로세스 추가 정리
    pkill -f 'python3.*monitors/' 2>/dev/null || true
    
    log_success "백그라운드 프로세스 정리 완료."
    exit 130
}

trap cleanup_on_exit SIGINT SIGTERM

# =============================================================================
# 1. 사전 준비
# =============================================================================

echo "============================================================="
echo "  CTI 데이터 수집 및 ML 학습 파이프라인 v2.0"
echo "============================================================="
echo "  시나리오: $SCENARIO_NAME"
echo "  반복 횟수: $ITERATIONS"
echo "  작업 디렉토리: $SCRIPT_DIR"
echo "============================================================="
echo ""

# Root 권한 확인
if [ "$EUID" -ne 0 ]; then
    log_warn "Root 권한 없이 실행 중. network_traffic_monitor가 실패할 수 있습니다."
    log_warn "권장: sudo bash $0 $SCENARIO_NAME $ITERATIONS"
    echo ""
    read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 기존 모니터 프로세스 정리
log_info "기존 CTI 모니터 프로세스 정리..."
pkill -f 'python3.*monitors/' 2>/dev/null || true
sleep 1

# 기존 로그 파일 백업
if [ -d "$BUS_DIR" ] && [ "$(ls -A "$BUS_DIR" 2>/dev/null)" ]; then
    BACKUP_NAME="bus_backup_$(date +%Y%m%d_%H%M%S)"
    log_info "이전 bus 로그 백업: $BACKUP_NAME"
    mv "$BUS_DIR" "$BACKUP_NAME"
fi

mkdir -p "$BUS_DIR"
mkdir -p "$OUTPUT_DIR"
log_success "디렉토리 초기화 완료: $BUS_DIR, $OUTPUT_DIR"

# =============================================================================
# 2. 모니터 시작 (백그라운드)
# =============================================================================

echo ""
log_info "5가지 CTI 모니터링 스크립트 시작..."

for monitor in "${MONITORS[@]}"; do
    if [ -f "$monitor" ]; then
        log_info "  -> Starting: $monitor"
        
        # network_traffic_monitor는 특별 처리 (권한 문제 가능)
        if [[ "$monitor" == *"network_traffic"* ]]; then
            PYTHONUNBUFFERED=1 python3 "$monitor" 2>&1 | while read line; do
                echo "[NET] $line"
            done &
        else
            PYTHONUNBUFFERED=1 python3 "$monitor" &
        fi
        
        PIDS+=($!)
        sleep 0.5
    else
        log_warn "  -> [SKIP] 파일 없음: $monitor"
    fi
done

log_info "모니터 초기화 대기 (10초)..."
sleep 10
log_success "모니터 ${#PIDS[@]}개 시작 완료."

# =============================================================================
# 3. 시나리오 반복 실행
# =============================================================================

echo ""
echo "============================================================="
log_info "[CTI] $SCENARIO_NAME 시나리오 $ITERATIONS회 반복 실행"
echo "============================================================="

for ((i=1; i<=ITERATIONS; i++)); do
    echo ""
    log_info "━━━ [RUN $i / $ITERATIONS] $SCENARIO_NAME ━━━"
    
    # ⭐️ --skip-ml 옵션으로 시나리오 러너의 자동 ML 실행 방지
    if python3 "$SCENARIO_RUNNER" --scenario "$SCENARIO_NAME" --skip-ml; then
        log_success "[RUN $i] 완료"
    else
        log_error "[RUN $i] 실패 (종료 코드: $?)"
    fi
    
    if [ $i -lt $ITERATIONS ]; then
        log_info "다음 실행까지 5초 대기..."
        sleep 5
    fi
done

# =============================================================================
# 4. ML 학습 파이프라인 실행
# =============================================================================

echo ""
echo "============================================================="
log_info "🤖 [ML PIPELINE] ${ITERATIONS}회분 데이터로 분류기 학습"
echo "============================================================="

# 로그 파일 확인
echo ""
log_info "수집된 로그 파일 확인:"
ls -lh "$BUS_DIR"/*.log 2>/dev/null || log_warn "로그 파일 없음"
echo ""

# --- ML Step 1: Data Builder ---
log_info "[ML 1/3] Data Builder 실행 (로그 파싱 → 특징 벡터)..."

# ⭐️ data_builder.py의 실제 인자에 맞게 수정
# 옵션 1: --log-dir 사용 (모든 로그 파일 자동 탐색)
if python3 "$DATA_BUILDER" --log-dir "$BUS_DIR" --output-dir "$OUTPUT_DIR"; then
    log_success "Data Builder 완료"
else
    log_error "Data Builder 실패"
    # 대체 시도: 개별 파일 지정
    log_info "대체 방법 시도: 개별 로그 파일 병합..."
    
    # 모든 로그를 하나로 병합
    MERGED_LOG="$BUS_DIR/merged_all.log"
    cat "$BUS_DIR"/*.log > "$MERGED_LOG" 2>/dev/null || true
    
    python3 "$DATA_BUILDER" --log-file "$MERGED_LOG" --output-dir "$OUTPUT_DIR" || {
        log_error "Data Builder 최종 실패. 스크립트 종료."
        cleanup_on_exit
    }
fi

# --- ML Step 2: Dataset Manager ---
log_info "[ML 2/3] Dataset Manager 실행 (Train/Test 분할)..."

# ⭐️ dataset_manager.py 인자 확인 필요
if python3 "$DATASET_MANAGER" \
    --input-dir "$OUTPUT_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --test-size 0.2 \
    --smote; then
    log_success "Dataset Manager 완료"
else
    # 대체 인자 시도
    log_warn "기본 인자 실패, 대체 인자 시도..."
    python3 "$DATASET_MANAGER" \
        --processed-dir "$OUTPUT_DIR" \
        --test-size 0.2 || {
        log_error "Dataset Manager 실패"
    }
fi

# --- ML Step 3: Classifier Trainer ---
log_info "[ML 3/3] Classifier Trainer 실행 (모델 학습)..."

if python3 "$TRAIN_CLASSIFIER" \
    --input-dir "$OUTPUT_DIR" \
    --output-dir "$OUTPUT_DIR"; then
    log_success "Classifier Trainer 완료"
else
    # 대체 인자 시도
    log_warn "기본 인자 실패, 대체 인자 시도..."
    python3 "$TRAIN_CLASSIFIER" \
        --train-data "$OUTPUT_DIR/train_dataset.csv" \
        --test-data "$OUTPUT_DIR/test_dataset.csv" \
        --output-dir "$OUTPUT_DIR" || {
        log_error "Classifier Trainer 실패"
    }
fi

# =============================================================================
# 5. 결과 확인 및 정리
# =============================================================================

echo ""
echo "============================================================="
log_info "📊 학습 결과 확인"
echo "============================================================="

# 생성된 파일 목록
log_info "생성된 파일:"
ls -lh "$OUTPUT_DIR"/ 2>/dev/null || log_warn "출력 파일 없음"

# 모델 파일 확인
if [ -f "$OUTPUT_DIR/cti_classifier.joblib" ]; then
    log_success "✅ 모델 파일: $OUTPUT_DIR/cti_classifier.joblib"
fi

if [ -f "$OUTPUT_DIR/label_encoder.joblib" ]; then
    log_success "✅ 라벨 인코더: $OUTPUT_DIR/label_encoder.joblib"
fi

if [ -f "$OUTPUT_DIR/training_features.json" ]; then
    log_success "✅ 피처 목록: $OUTPUT_DIR/training_features.json"
fi

# 모니터 종료
echo ""
log_info "백그라운드 모니터 종료..."
for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
    fi
done
pkill -f 'python3.*monitors/' 2>/dev/null || true

echo ""
echo "============================================================="
log_success "🎉 CTI 데이터 수집 및 ML 파이프라인 완료!"
echo "============================================================="
echo ""
echo "  📁 로그 데이터: $BUS_DIR/"
echo "  📁 학습 결과:   $OUTPUT_DIR/"
echo ""
echo "  다음 단계:"
echo "    1. 모델 평가: python3 ml/evaluate_model.py"
echo "    2. CTI Agent 배포: python3 ml/cti_agent_deploy.py --mode cti_rule"
echo ""

exit 0