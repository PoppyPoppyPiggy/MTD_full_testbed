#!/bin/bash

# =============================================================================
# DVD MTD 지도학습 실행 래퍼 스크립트
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/run_supervised_learning.sh
# 목적: 지도학습 파이프라인의 편리한 실행을 위한 래퍼 스크립트
# 작성자: MTD Testbed Team
# =============================================================================
#!/bin/bash
# DVD MTD 지도학습 파이프라인 실행 스크립트
# 공격 데이터 수집 → 모델 훈련 → 평가 → 시각화

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 경로 설정
BASE_DIR="/home/kali/MTD/MTD_full_testbed"
DVD_LITE_DIR="$BASE_DIR/dvd_lite"
DATA_DIR="$DVD_LITE_DIR/data/supervised_learning"
RESULTS_DIR="$DVD_LITE_DIR/results"

# 로고 출력
print_header() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║               🤖 DVD MTD 지도학습 파이프라인 실행기 🤖                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${WHITE}논문 작성을 위한 통합 머신러닝 시스템${NC}"
}

# 시스템 요구사항 확인
check_requirements() {
    echo -e "${BLUE}🚀 빠른 시작 모드${NC}"
    echo -e "${CYAN}[*]${NC} 시스템 요구사항 확인 중..."
    
    # Python 확인
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        echo -e "${GREEN}[✓]${NC} Python 3 발견: $python_version"
    else
        echo -e "${RED}[✗]${NC} Python 3가 설치되지 않음"
        exit 1
    fi
    
    # 필수 Python 패키지 확인
    local packages=("pandas" "numpy" "sklearn" "matplotlib")
    for package in "${packages[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            echo -e "${GREEN}[✓]${NC} $package 패키지 설치됨"
        else
            echo -e "${YELLOW}[⚠]${NC} $package 패키지 누락 - 자동 설치 시도"
            pip3 install "$package" || echo -e "${RED}[✗]${NC} $package 설치 실패"
        fi
    done
    
    # 디렉토리 확인
    if [ -d "$DATA_DIR" ]; then
        echo -e "${GREEN}[✓]${NC} 지도학습 데이터 디렉토리 존재"
    else
        echo -e "${YELLOW}[*]${NC} 데이터 디렉토리 생성 중..."
        mkdir -p "$DATA_DIR"
    fi
    
    # 기존 훈련 데이터 확인
    local existing_files=$(find "$DATA_DIR" -name "*.json" -o -name "*.csv" | wc -l)
    if [ "$existing_files" -gt 0 ]; then
        echo -e "${GREEN}[✓]${NC} 기존 훈련 데이터 발견: ${existing_files}개 파일"
    else
        echo -e "${YELLOW}[*]${NC} 기존 훈련 데이터 없음 - 시뮬레이션 데이터 사용"
    fi
}

# 데이터 품질 검사
check_data_quality() {
    echo -e "${CYAN}[*]${NC} 데이터 품질 검사 중..."
    
    # 데이터 파일 현황
    local json_files=$(find "$DATA_DIR" -name "*.json" -o -name "*.jsonl" | wc -l)
    local csv_files=$(find "$DATA_DIR" -name "*.csv" | wc -l)
    
    echo -e "${BLUE}📊 데이터 파일 현황:${NC}"
    echo -e "  ${CYAN}•${NC} JSON/JSONL 파일: ${json_files}개"
    echo -e "  ${CYAN}•${NC} CSV 파일: ${csv_files}개"
    
    # 간단한 데이터 품질 검사
    if [ "$json_files" -gt 0 ] || [ "$csv_files" -gt 0 ]; then
        # Python으로 데이터 품질 검사
        python3 << 'EOF'
import os
import pandas as pd
import json
from pathlib import Path

data_dir = Path("/home/kali/MTD/MTD_full_testbed/dvd_lite/data/supervised_learning")
total_samples = 0
valid_samples = 0
feature_files = 0

try:
    for file_path in data_dir.glob("*.json"):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    total_samples += len(data)
                    valid_samples += len([d for d in data if isinstance(d, dict)])
                else:
                    total_samples += 1
                    valid_samples += 1 if isinstance(data, dict) else 0
                feature_files += 1
        except:
            continue
    
    for file_path in data_dir.glob("*.csv"):
        try:
            df = pd.read_csv(file_path)
            total_samples += len(df)
            valid_samples += len(df.dropna())
            feature_files += 1
        except:
            continue
    
    print(f"📈 데이터 품질:")
    print(f"  • 총 샘플: {total_samples}개")
    print(f"  • 유효 샘플: {valid_samples}개")
    print(f"  • 특성 파일: {feature_files}개")
    
    if valid_samples > 50:
        print("✅ 데이터 품질 양호")
        exit(0)
    else:
        print("⚠️ 데이터 품질 부족 - 시뮬레이션 데이터 사용")
        exit(1)
        
except Exception as e:
    print(f"❌ 데이터 품질 검사 오류: {e}")
    exit(1)
EOF
        local data_quality_result=$?
    else
        echo -e "${YELLOW}📈 데이터 품질: 기존 데이터 없음${NC}"
        local data_quality_result=1
    fi
    
    return $data_quality_result
}

# 공격 데이터 수집 (옵션)
collect_attack_data() {
    echo -e "${CYAN}[*]${NC} 실시간 공격 데이터 수집 중..."
    
    # 수정된 공격 스크립트 경로 (dvd_lite/master_attack_runner.sh)
    local attack_script="$DVD_LITE_DIR/master_attack_runner.sh"
    
    if [ -f "$attack_script" ] && [ -x "$attack_script" ]; then
        echo -e "${GREEN}[✓]${NC} 공격 스크립트 발견: $attack_script"
        
        # 백그라운드에서 공격 실행 (최대 60초)
        timeout 60 "$attack_script" --collect-training-data &
        local attack_pid=$!
        
        echo -e "${YELLOW}[*]${NC} 공격 데이터 수집 중... (PID: $attack_pid)"
        
        # 공격 완료 대기
        if wait $attack_pid 2>/dev/null; then
            echo -e "${GREEN}[✓]${NC} 공격 데이터 수집 완료"
            return 0
        else
            echo -e "${YELLOW}[⚠]${NC} 공격 데이터 수집 시간 초과 또는 실패"
            return 1
        fi
    else
        echo -e "${YELLOW}[⚠]${NC} 공격 스크립트 없음: $attack_script"
        echo -e "${CYAN}[*]${NC} 시뮬레이션 데이터로 진행"
        return 1
    fi
}

# 지도학습 파이프라인 실행
run_supervised_learning() {
    echo -e "${CYAN}[*]${NC} 기본 공격 탐지 모델을 훈련합니다..."
    echo -e "${CYAN}[*]${NC} 지도학습 파이프라인 실행 중..."
    echo -e "    ${WHITE}작업 유형: detection${NC}"
    echo -e "    ${WHITE}실행 모드: auto${NC}"
    
    # Python 파이프라인 실행
    cd "$DVD_LITE_DIR"
    
    if python3 -c "
from supervised_learning_pipeline import SupervisedLearningPipeline, TrainingConfig, LearningTask, ModelType
import asyncio

async def run():
    config = TrainingConfig(
        task_type=LearningTask.DETECTION,
        model_type=ModelType.RANDOM_FOREST,
        cross_validation=True,
        hyperparameter_tuning=False,
        feature_selection=True,
        save_model=True
    )
    
    pipeline = SupervisedLearningPipeline(config)
    results = await pipeline.run_pipeline()
    
    if results['success']:
        print(f'✅ 파이프라인 성공 - 정확도: {results[\"evaluation_results\"].get(\"accuracy\", 0):.3f}')
        return 0
    else:
        print(f'❌ 파이프라인 실패: {results.get(\"error\", \"Unknown error\")}')
        return 1

import sys
sys.exit(asyncio.run(run()))
" 2>/dev/null; then
        echo -e "${GREEN}[✓]${NC} 지도학습 파이프라인 실행 성공"
        return 0
    else
        echo -e "${RED}[✗]${NC} 지도학습 파이프라인 실행 실패"
        return 1
    fi
}

# 결과 시각화 생성
generate_visualization() {
    echo -e "${CYAN}[*]${NC} 결과 시각화를 생성합니다..."
    echo -e "${CYAN}[*]${NC} 결과 시각화 생성 중..."
    
    # 최신 결과 파일 찾기
    local latest_result=$(find "$RESULTS_DIR" -name "pipeline_results_*.json" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [ -n "$latest_result" ] && [ -f "$latest_result" ]; then
        echo -e "${GREEN}[✓]${NC} 결과 파일 발견: $(basename "$latest_result")"
        
        # 간단한 시각화 생성
        python3 << EOF
import json
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

try:
    with open('$latest_result', 'r') as f:
        results = json.load(f)
    
    # 기본 정보 출력
    print(f"📊 모델 성능:")
    print(f"  • 정확도: {results.get('evaluation_metrics', {}).get('accuracy', 0):.3f}")
    print(f"  • 특성 개수: {len(results.get('feature_columns', []))}")
    print(f"  • 훈련 샘플: {results.get('training_history', {}).get('training_samples', 0)}")
    
    # 특성 중요도 시각화 (상위 10개)
    feature_importance = results.get('feature_importance', {})
    if feature_importance:
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        
        if top_features:
            features, importance = zip(*top_features)
            
            plt.figure(figsize=(10, 6))
            plt.barh(features, importance)
            plt.title('상위 10개 특성 중요도')
            plt.xlabel('중요도')
            plt.tight_layout()
            
            viz_path = Path('$RESULTS_DIR') / 'feature_importance.png'
            plt.savefig(viz_path, dpi=300, bbox_inches='tight')
            print(f"📈 특성 중요도 차트 저장: {viz_path}")
    
    print("✅ 시각화 생성 완료")
    
except Exception as e:
    print(f"⚠️ 시각화 생성 실패: {e}")
EOF
    else
        echo -e "${YELLOW}⚠️${NC} 파이프라인 결과 파일이 없습니다."
    fi
    
    echo -e "${GREEN}✅ 시각화 생성 완료${NC}"
}

# 결과 요약 출력
print_summary() {
    echo
    echo -e "${GREEN}🎉 지도학습 파이프라인 실행 완료!${NC}"
    echo
    echo -e "${CYAN}📍 결과 위치:${NC}"
    echo -e "  ${WHITE}• 모델:${NC} $DVD_LITE_DIR/models/"
    echo -e "  ${WHITE}• 결과:${NC} $RESULTS_DIR/"
    echo -e "  ${WHITE}• 로그:${NC} $DVD_LITE_DIR/logs/"
    echo
    echo -e "${YELLOW}📋 다음 단계:${NC}"
    echo -e "  ${WHITE}1.${NC} 모델 성능 검토 및 하이퍼파라미터 튜닝"
    echo -e "  ${WHITE}2.${NC} 실시간 공격 탐지 시스템과 연동"
    echo -e "  ${WHITE}3.${NC} 추가 공격 데이터로 모델 재훈련"
    echo -e "  ${WHITE}4.${NC} 논문 작성을 위한 결과 분석"
    echo
}

# 메인 실행 함수
main() {
    print_header
    
    # 인자 처리
    local mode="${1:-auto}"
    local collect_data=false
    
    case "$mode" in
        "collect")
            collect_data=true
            ;;
        "quick")
            # 빠른 실행 모드
            ;;
        "auto"|*)
            # 기본 자동 모드
            ;;
    esac
    
    # 1단계: 시스템 요구사항 확인
    check_requirements
    
    # 2단계: 데이터 품질 검사
    if ! check_data_quality; then
        echo -e "${YELLOW}[*]${NC} 추가 데이터 수집 권장"
        collect_data=true
    fi
    
    # 3단계: 공격 데이터 수집 (옵션)
    if [ "$collect_data" = true ]; then
        collect_attack_data || echo -e "${YELLOW}[*]${NC} 기존 데이터로 진행"
    fi
    
    # 4단계: 지도학습 파이프라인 실행
    if run_supervised_learning; then
        # 5단계: 결과 시각화
        generate_visualization
        
        # 6단계: 결과 요약
        print_summary
        
        exit 0
    else
        echo -e "${RED}❌ 지도학습 파이프라인 실행 실패${NC}"
        exit 1
    fi
}

# 사용법 출력
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "사용법: $0 [mode]"
    echo
    echo "모드:"
    echo "  auto     자동 모드 (기본값)"
    echo "  collect  공격 데이터 수집 후 훈련"
    echo "  quick    빠른 실행 (최소 설정)"
    echo
    echo "예시:"
    echo "  $0 auto          # 기본 자동 실행"
    echo "  $0 collect       # 실시간 데이터 수집 후 훈련"
    echo "  $0 quick         # 빠른 테스트 실행"
    echo
    exit 0
fi

# 스크립트 실행
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi