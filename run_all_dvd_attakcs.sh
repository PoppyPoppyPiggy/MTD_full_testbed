#!/bin/bash
# run_all_dvd_attacks.sh
# DVD 공격 스크립트 전체 순회 실행

set -e

# 기본 설정
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DVD_ATTACKS_DIR="$BASE_DIR/dvd_lite/dvd_attacks"

# 공통 모듈 로드 (DVD 테스트베드 색상 시스템 사용)
COLORS_FILE="$DVD_ATTACKS_DIR/common/colors.sh"
UTILS_FILE="$DVD_ATTACKS_DIR/common/utils.sh"

# 색상 모듈이 존재하면 로드, 없으면 기본 색상 정의
if [ -f "$COLORS_FILE" ]; then
    source "$COLORS_FILE"
    echo_info "DVD 공통 색상 모듈 로드됨"
else
    # 기본 색상 정의 (fallback)
    export RED='\033[0;31m'
    export GREEN='\033[0;32m'
    export YELLOW='\033[1;33m'
    export BLUE='\033[0;34m'
    export PURPLE='\033[0;35m'
    export CYAN='\033[0;36m'
    export WHITE='\033[1;37m'
    export BOLD='\033[1m'
    export UNDERLINE='\033[4m'
    export NC='\033[0m'
    
    # 기본 출력 함수들 정의
    echo_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
    echo_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
    echo_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
    echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }
    echo_title() { echo -e "${BOLD}${BLUE}$1${NC}"; }
fi

# 유틸리티 모듈이 존재하면 로드
if [ -f "$UTILS_FILE" ]; then
    source "$UTILS_FILE"
    echo_info "DVD 공통 유틸리티 모듈 로드됨"
fi

# 헤더 출력
echo_title "================================================================"
echo_title "             DVD 공격 스크립트 전체 순회 실행기"
echo_title "================================================================"
echo_info "Base Directory: $BASE_DIR"
echo_info "DVD Attacks Directory: $DVD_ATTACKS_DIR"

# DVD attacks 디렉토리 존재 확인
if [ ! -d "$DVD_ATTACKS_DIR" ]; then
    echo_error "DVD attacks 디렉토리를 찾을 수 없습니다: $DVD_ATTACKS_DIR"
    echo_warning "올바른 MTD_full_testbed 디렉토리에서 실행하고 있는지 확인해주세요."
    exit 1
fi

# 로그 및 결과 디렉토리 생성
LOG_DIR="$BASE_DIR/attack_logs"
OUTPUT_DIR="$BASE_DIR/attack_output"
RESULTS_DIR="$BASE_DIR/results"

mkdir -p "$LOG_DIR" "$OUTPUT_DIR" "$RESULTS_DIR"

# 실행 정보 표시
echo_info "실행 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo_info "로그 디렉토리: $LOG_DIR"
echo_info "출력 디렉토리: $OUTPUT_DIR"
echo_info "결과 디렉토리: $RESULTS_DIR"

# 사용법 출력 함수
show_help() {
    echo_title "사용법"
    echo "  $0 [옵션]"
    echo ""
    echo_info "옵션:"
    echo "  ${CYAN}list${NC}                     - 사용 가능한 공격 스크립트 목록 출력"
    echo "  ${CYAN}discover${NC}                 - 스크립트 발견 및 분석만 수행"
    echo "  ${CYAN}check${NC}                    - 환경 점검 실행"
    echo "  ${CYAN}all${NC}                      - 모든 공격 스크립트 실행 (기본값)"
    echo "  ${CYAN}<tactic1> <tactic2> ...${NC}  - 특정 전술만 실행"
    echo "  ${CYAN}help${NC}                     - 이 도움말 출력"
    echo ""
    echo_info "사용 가능한 전술:"
    echo "  • ${YELLOW}reconnaissance${NC}       - 정찰 공격"
    echo "  • ${YELLOW}protocol_tampering${NC}   - 프로토콜 조작"
    echo "  • ${YELLOW}denial_of_service${NC}    - 서비스 거부 공격"
    echo "  • ${YELLOW}injection${NC}            - 주입 공격"
    echo "  • ${YELLOW}exfiltration${NC}         - 데이터 유출"
    echo "  • ${YELLOW}firmware_attacks${NC}     - 펌웨어 공격"
    echo ""
    echo_info "예시:"
    echo "  ${GREEN}$0 list${NC}                                    # 스크립트 목록 확인"
    echo "  ${GREEN}$0 check${NC}                                   # 환경 점검"
    echo "  ${GREEN}$0 reconnaissance injection${NC}               # 특정 전술만 실행"
    echo "  ${GREEN}$0 all${NC}                                     # 모든 공격 실행"
}

# Python 스크립트 실행 함수
run_python_orchestrator() {
    local args="$1"
    
    echo_info "Python 오케스트레이터 실행 중..."
    echo_info "명령어: python3 $BASE_DIR/real_attack_orchestrator.py $args"
    
    # Python 경로 설정
    export PYTHONPATH="$BASE_DIR:$PYTHONPATH"
    
    # Python 스크립트 실행
    python3 "$BASE_DIR/real_attack_orchestrator.py" $args
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo_success "Python 오케스트레이터 실행 완료"
    else
        echo_error "Python 오케스트레이터 실행 실패 (종료 코드: $exit_code)"
    fi
    
    return $exit_code
}

# 결과 요약 출력 함수
show_results_summary() {
    echo_title "================================================================"
    echo_title "                        실행 결과 요약"
    echo_title "================================================================"
    
    # 최신 결과 파일 찾기
    LATEST_RESULT=$(find "$RESULTS_DIR" -name "dvd_attack_results_*.json" -type f -exec ls -t {} + | head -n 1 2>/dev/null)
    LATEST_IOC=$(find "$RESULTS_DIR" -name "dvd_iocs_*.csv" -type f -exec ls -t {} + | head -n 1 2>/dev/null)
    LATEST_SUMMARY=$(find "$RESULTS_DIR" -name "dvd_summary_*.txt" -type f -exec ls -t {} + | head -n 1 2>/dev/null)
    
    if [ -n "$LATEST_RESULT" ] && [ -f "$LATEST_RESULT" ]; then
        echo_info "최신 결과 파일: $LATEST_RESULT"
        
        # JSON에서 기본 정보 추출 (jq가 있는 경우)
        if command -v jq >/dev/null 2>&1; then
            echo_success "실행 완료: $(jq -r '.execution_info.total_scripts // "N/A"' "$LATEST_RESULT") 스크립트"
            echo_success "성공한 공격: $(jq -r '.execution_info.successful_attacks // "N/A"' "$LATEST_RESULT") 개"
            echo_success "수집된 IOCs: $(jq -r '.ioc_summary.total_iocs // "N/A"' "$LATEST_RESULT") 개"
        else
            echo_info "상세 정보는 결과 파일에서 확인하세요: $LATEST_RESULT"
        fi
    fi
    
    if [ -n "$LATEST_IOC" ] && [ -f "$LATEST_IOC" ]; then
        IOC_COUNT=$(wc -l < "$LATEST_IOC" 2>/dev/null || echo "0")
        echo_info "IOC 데이터: $LATEST_IOC ($IOC_COUNT 줄)"
    fi
    
    if [ -n "$LATEST_SUMMARY" ] && [ -f "$LATEST_SUMMARY" ]; then
        echo_info "요약 리포트: $LATEST_SUMMARY"
        echo ""
        echo_title "실행 요약:"
        head -20 "$LATEST_SUMMARY" | while IFS= read -r line; do
            echo "  $line"
        done
    fi
    
    echo_title "================================================================"
}

# 인자 처리
case "${1:-all}" in
    "help"|"-h"|"--help")
        show_help
        exit 0
        ;;
    "list")
        echo_info "사용 가능한 공격 스크립트 목록 조회 중..."
        run_python_orchestrator "--list"
        exit $?
        ;;
    "discover")
        echo_info "공격 스크립트 발견 및 분석 수행 중..."
        run_python_orchestrator "--dry-run"
        exit $?
        ;;
    "check")
        echo_info "환경 점검 실행 중..."
        if [ -f "$BASE_DIR/check_dvd_environment.py" ]; then
            python3 "$BASE_DIR/check_dvd_environment.py"
        else
            echo_warning "환경 점검 스크립트를 찾을 수 없습니다."
            echo_info "기본 점검을 수행합니다..."
            run_python_orchestrator "--list"
        fi
        exit $?
        ;;
    "all")
        echo_info "모든 공격 스크립트 실행 시작"
        echo_warning "이 작업은 시간이 오래 걸릴 수 있습니다..."
        
        if run_python_orchestrator ""; then
            show_results_summary
            echo_success "모든 공격 스크립트 실행 완료!"
        else
            echo_error "공격 스크립트 실행 중 오류가 발생했습니다."
            exit 1
        fi
        ;;
    *)
        # 특정 전술들 실행
        tactics=("$@")
        echo_info "특정 전술 실행: ${YELLOW}${tactics[*]}${NC}"
        echo_warning "선택된 전술만 실행됩니다..."
        
        tactics_args="--tactics ${tactics[*]}"
        if run_python_orchestrator "$tactics_args"; then
            show_results_summary
            echo_success "선택된 전술 실행 완료!"
        else
            echo_error "전술 실행 중 오류가 발생했습니다."
            exit 1
        fi
        ;;
esac