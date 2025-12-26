#!/usr/bin/env bash
#
# CTI 데이터 수집 및 ML 학습 통합 파이프라인 v2.1 (Fixed)
# ============================================================
# 수정 사항:
#   - ML 스크립트 인자 호환성 수정
#   - --skip-ml → --no-ml 변경
#   - 경로 자동 탐지 개선
#
# 사용법:
#   sudo bash run_cti_data_pipeline.sh                     # 기본 (cti_core8 x 3회)
#   sudo bash run_cti_data_pipeline.sh cti_balanced 5      # cti_balanced x 5회
#

set -e

# =============================================================================
# 설정
# =============================================================================

SCENARIO_NAME="${1:-cti_core8}"
ITERATIONS="${2:-3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 모니터 스크립트 경로 (유연하게 탐색)
MONITOR_DIR=""
if [ -d "$SCRIPT_DIR/monitors" ]; then
    MONITOR_DIR="$SCRIPT_DIR/monitors"
elif [ -d "$SCRIPT_DIR/../monitors" ]; then
    MONITOR_DIR="$SCRIPT_DIR/../monitors"
fi

MONITORS=(
    "dvd_container_monitor.py"
    "dvd_telemetry_monitor.py"
    "network_traffic_monitor.py"
    "qos_monitor.py"
    "system_event_monitor.py"
)

# ML/시나리오 스크립트 경로
SCENARIO_RUNNER=""
if [ -f "$SCRIPT_DIR/scenarios/dvd_scenario_runner.py" ]; then
    SCENARIO_RUNNER="$SCRIPT_DIR/scenarios/dvd_scenario_runner.py"
elif [ -f "$SCRIPT_DIR/dvd_scenario_runner.py" ]; then
    SCENARIO_RUNNER="$SCRIPT_DIR/dvd_scenario_runner.py"
fi

ML_DIR=""
if [ -d "$SCRIPT_DIR/ml" ]; then
    ML_DIR="$SCRIPT_DIR/ml"
elif [ -d "$SCRIPT_DIR/../ml" ]; then
    ML_DIR="$SCRIPT_DIR/../ml"
fi

DATA_BUILDER="$ML_DIR/data_builder.py"
DATASET_MANAGER="$ML_DIR/dataset_manager.py"
TRAIN_CLASSIFIER="$ML_DIR/train_classifier.py"

BUS_DIR="$SCRIPT_DIR/bus"
OUTPUT_DIR="$ML_DIR/output"
PROCESSED_DIR="$ML_DIR/processed_data"

PIDS=()

# =============================================================================
# 색상 출력
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# 종료 핸들러
# =============================================================================

cleanup_on_exit() {
    echo -e "\n"
    log_warn "종료 신호 수신! 백그라운드 모니터 정리 중..."
    
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "  -> Terminating PID $pid"
            kill "$pid" 2>/dev/null || true
            sleep 0.3
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
    done
    
    pkill -f 'python3.*monitor' 2>/dev/null || true
    
    log_success "백그라운드 프로세스 정리 완료."
    exit 130
}

trap cleanup_on_exit SIGINT SIGTERM

# =============================================================================
# 1. 사전 준비
# =============================================================================

echo "============================================================="
echo "  CTI 데이터 수집 및 ML 학습 파이프라인 v2.1"
echo "============================================================="
echo "  시나리오: $SCENARIO_NAME"
echo "  반복 횟수: $ITERATIONS"
echo "  작업 디렉토리: $SCRIPT_DIR"
echo "  모니터 디렉토리: $MONITOR_DIR"
echo "  ML 디렉토리: $ML_DIR"
echo "============================================================="
echo ""

# 필수 파일 확인
if [ -z "$ML_DIR" ] || [ ! -d "$ML_DIR" ]; then
    log_error "ML 디렉토리를 찾을 수 없습니다!"
    exit 1
fi

if [ -z "$SCENARIO_RUNNER" ] || [ ! -f "$SCENARIO_RUNNER" ]; then
    log_error "시나리오 러너를 찾을 수 없습니다!"
    log_info "예상 경로: scenarios/dvd_scenario_runner.py"
    exit 1
fi

# Root 권한 확인
if [ "$EUID" -ne 0 ]; then
    log_warn "Root 권한 없이 실행 중. network_traffic_monitor가 실패할 수 있습니다."
    read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 기존 모니터 프로세스 정리
log_info "기존 CTI 모니터 프로세스 정리..."
pkill -f 'python3.*monitor' 2>/dev/null || true
sleep 1

# 기존 로그 파일 백업
if [ -d "$BUS_DIR" ] && [ "$(ls -A "$BUS_DIR" 2>/dev/null)" ]; then
    BACKUP_NAME="${BUS_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    log_info "이전 bus 로그 백업: $BACKUP_NAME"
    mv "$BUS_DIR" "$BACKUP_NAME"
fi

mkdir -p "$BUS_DIR"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$PROCESSED_DIR"
log_success "디렉토리 초기화 완료"

# =============================================================================
# 2. 모니터 시작 (백그라운드)
# =============================================================================

echo ""
log_info "CTI 모니터링 스크립트 시작..."

if [ -n "$MONITOR_DIR" ] && [ -d "$MONITOR_DIR" ]; then
    for monitor_name in "${MONITORS[@]}"; do
        monitor_path="$MONITOR_DIR/$monitor_name"
        if [ -f "$monitor_path" ]; then
            log_info "  -> Starting: $monitor_name"
            
            # 환경 변수 설정하여 bus 디렉토리 지정
            BUS_DIR="$BUS_DIR" PYTHONUNBUFFERED=1 python3 "$monitor_path" &
            PIDS+=($!)
            sleep 0.5
        else
            log_warn "  -> [SKIP] 파일 없음: $monitor_path"
        fi
    done
    
    log_info "모니터 초기화 대기 (10초)..."
    sleep 10
    log_success "모니터 ${#PIDS[@]}개 시작 완료."
else
    log_warn "모니터 디렉토리 없음. 모니터 없이 진행합니다."
    log_warn "수동으로 모니터를 시작하거나, 기존 로그를 사용하세요."
fi

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
    
    # ⭐️ --no-ml 옵션 사용 (내 코드와 호환)
    if python3 "$SCENARIO_RUNNER" --scenario "$SCENARIO_NAME" --no-ml; then
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
log_info "[ML 1/3] Data Builder 실행..."

if [ -f "$DATA_BUILDER" ]; then
    # ⭐️ 수정된 인자: --log-dir (내 코드와 호환)
    if python3 "$DATA_BUILDER" --log-dir "$BUS_DIR" --output-dir "$PROCESSED_DIR"; then
        log_success "Data Builder 완료"
    else
        log_error "Data Builder 실패"
        
        # 대체 시도: 개별 로그 파일 병합
        log_info "대체 방법: 로그 병합 후 재시도..."
        MERGED_LOG="$BUS_DIR/merged_all.log"
        cat "$BUS_DIR"/*.log > "$MERGED_LOG" 2>/dev/null || true
        
        python3 "$DATA_BUILDER" --log-file "$MERGED_LOG" --output-dir "$PROCESSED_DIR" || {
            log_error "Data Builder 최종 실패."
            cleanup_on_exit
        }
    fi
else
    log_error "Data Builder 스크립트 없음: $DATA_BUILDER"
    cleanup_on_exit
fi

# --- ML Step 2: Dataset Manager ---
log_info "[ML 2/3] Dataset Manager 실행..."

if [ -f "$DATASET_MANAGER" ]; then
    # ⭐️ 수정된 인자: --processed-dir (내 코드와 호환)
    if python3 "$DATASET_MANAGER" \
        --processed-dir "$PROCESSED_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --test-size 0.2; then
        log_success "Dataset Manager 완료"
    else
        log_warn "기본 실행 실패, SMOTE 없이 재시도..."
        python3 "$DATASET_MANAGER" \
            --processed-dir "$PROCESSED_DIR" \
            --output-dir "$OUTPUT_DIR" \
            --test-size 0.2 || {
            log_error "Dataset Manager 실패"
        }
    fi
else
    log_error "Dataset Manager 스크립트 없음: $DATASET_MANAGER"
fi

# --- ML Step 3: Classifier Trainer ---
log_info "[ML 3/3] Classifier Trainer 실행..."

if [ -f "$TRAIN_CLASSIFIER" ]; then
    # ⭐️ 수정된 인자: --train-data, --test-data (내 코드와 호환)
    if python3 "$TRAIN_CLASSIFIER" \
        --train-data "$OUTPUT_DIR/train_dataset.csv" \
        --test-data "$OUTPUT_DIR/test_dataset.csv" \
        --model-output "$OUTPUT_DIR/cti_classifier_model.joblib" \
        --features-output "$OUTPUT_DIR/training_features.json" \
        --report-output "$OUTPUT_DIR/classification_report.json"; then
        log_success "Classifier Trainer 완료"
    else
        log_warn "상세 옵션 실패, 기본값으로 재시도..."
        python3 "$TRAIN_CLASSIFIER" || {
            log_error "Classifier Trainer 실패"
        }
    fi
else
    log_error "Train Classifier 스크립트 없음: $TRAIN_CLASSIFIER"
fi

# =============================================================================
# 5. 결과 확인 및 정리
# =============================================================================

echo ""
echo "============================================================="
log_info "📊 학습 결과 확인"
echo "============================================================="

log_info "생성된 파일:"
ls -lh "$OUTPUT_DIR"/ 2>/dev/null || log_warn "출력 파일 없음"

# 핵심 파일 확인
[ -f "$OUTPUT_DIR/cti_classifier_model.joblib" ] && log_success "✅ 모델: cti_classifier_model.joblib"
[ -f "$OUTPUT_DIR/training_features.json" ] && log_success "✅ 피처: training_features.json"
[ -f "$OUTPUT_DIR/classification_report.json" ] && log_success "✅ 리포트: classification_report.json"
[ -f "$OUTPUT_DIR/confusion_matrix_best.png" ] && log_success "✅ CM: confusion_matrix_best.png"

# 모니터 종료
echo ""
log_info "백그라운드 모니터 종료..."
for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
done
pkill -f 'python3.*monitor' 2>/dev/null || true

echo ""
echo "============================================================="
log_success "🎉 CTI 데이터 수집 및 ML 파이프라인 완료!"
echo "============================================================="
echo ""
echo "  📁 로그 데이터: $BUS_DIR/"
echo "  📁 처리된 데이터: $PROCESSED_DIR/"
echo "  📁 학습 결과: $OUTPUT_DIR/"
echo ""
echo "  다음 단계:"
echo "    1. CTI Agent 배포:"
echo "       python3 $ML_DIR/cti_agent_deploy.py --mode cti_rule"
echo ""
echo "    2. 노이즈/지연 실험:"
echo "       python3 $ML_DIR/cti_agent_deploy.py --mode rl_v08 --noise-rate 0.15 --delay-steps 2"
echo ""

exit 0