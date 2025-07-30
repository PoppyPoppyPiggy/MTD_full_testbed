#!/bin/bash

# =============================================================================
# DVD Attack Results Viewer
# =============================================================================
# 파일: view_results.sh  
# 목적: DVD 공격 테스트 결과 조회 및 분석 도구
# 작성자: MTD Testbed Team
# =============================================================================

# 스크립트 디렉토리 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"

# 공통 모듈 로드
source "$BASE_DIR/dvd_lite/dvd_attacks/common/colors.sh" 2>/dev/null || {
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    BLUE='\033[0;34m'; PURPLE='\033[0;35m'; CYAN='\033[0;36m'
    BOLD='\033[1m'; NC='\033[0m'
}

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    📊 DVD Attack Results Viewer 📊                     ║"
    echo "║                        Comprehensive Analysis Tool                       ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Base Directory: ${BASE_DIR}${NC}"
    echo -e "${BLUE}Current Time: $(date)${NC}"
    echo ""
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}DVD Attack Results Viewer${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS] [COMMAND]

${YELLOW}Commands:${NC}
    summary                 Show attack execution summary
    logs                    View recent attack logs
    reports                 Show generated reports
    iocs                    Display IOCs (Indicators of Compromise)
    timeline                Show attack timeline
    stats                   Display execution statistics
    search PATTERN          Search through logs and reports
    cleanup                 Clean old files (older than 7 days)

${YELLOW}Options:${NC}
    -h, --help              Show this help message
    -n, --lines NUM         Number of lines to display (default: 20)
    -d, --days NUM          Show results from last N days (default: 1)
    -f, --format FORMAT     Output format (text, json, csv)
    -o, --output FILE       Save output to file
    -v, --verbose           Verbose output
    -q, --quiet             Quiet mode

${YELLOW}Examples:${NC}
    $0 summary              # Show execution summary
    $0 logs -n 50           # Show last 50 log lines
    $0 search "GPS"         # Search for GPS-related entries
    $0 iocs -d 7            # Show IOCs from last 7 days
    $0 reports --format json # Show reports in JSON format

${YELLOW}Directories:${NC}
    • Logs: ${BASE_DIR}/attack_logs/
    • Reports: ${BASE_DIR}/attack_output/
    • IOCs: ${BASE_DIR}/iocs/
    • Master Reports: ${BASE_DIR}/reports/

EOF
}

# 실행 요약 표시
show_summary() {
    echo -e "${BOLD}${GREEN}📋 DVD Attack Execution Summary${NC}"
    echo "================================="
    echo ""
    
    # 최근 실행 정보
    local recent_logs=($(find "$BASE_DIR/attack_logs" -name "*.log" -mtime -${DAYS} 2>/dev/null | sort -t_ -k2 -r | head -5))
    local recent_reports=($(find "$BASE_DIR/reports" -name "*.json" -mtime -${DAYS} 2>/dev/null | sort -t_ -k2 -r | head -3))
    
    echo -e "${CYAN}최근 실행 기록 (${DAYS}일 이내):${NC}"
    
    if [ ${#recent_logs[@]} -eq 0 ]; then
        echo -e "${YELLOW}  • 최근 실행 기록이 없습니다${NC}"
    else
        echo -e "${BLUE}  • 총 ${#recent_logs[@]}개의 로그 파일 발견${NC}"
        for log in "${recent_logs[@]}"; do
            local log_name=$(basename "$log")
            local log_date=$(stat -c %y "$log" 2>/dev/null | cut -d' ' -f1)
            local log_size=$(du -h "$log" 2>/dev/null | cut -f1)
            echo -e "${GREEN}    ✓ ${log_name} (${log_date}, ${log_size})${NC}"
        done
    fi
    
    echo ""
    echo -e "${CYAN}최근 리포트:${NC}"
    
    if [ ${#recent_reports[@]} -eq 0 ]; then
        echo -e "${YELLOW}  • 최근 리포트가 없습니다${NC}"
    else
        for report in "${recent_reports[@]}"; do
            local report_name=$(basename "$report")
            local report_date=$(stat -c %y "$report" 2>/dev/null | cut -d' ' -f1)
            echo -e "${GREEN}    ✓ ${report_name} (${report_date})${NC}"
            
            # JSON 리포트에서 기본 정보 추출
            if command -v jq >/dev/null 2>&1 && [ -f "$report" ]; then
                local success_rate=$(jq -r '.dvd_comprehensive_attack_report.summary_statistics.success_rate_percentage // .summary_statistics.success_rate_percentage // "N/A"' "$report" 2>/dev/null)
                local total_attacks=$(jq -r '.dvd_comprehensive_attack_report.summary_statistics.total_attacks_executed // .summary_statistics.total_attacks_executed // "N/A"' "$report" 2>/dev/null)
                echo -e "${BLUE}      → 성공률: ${success_rate}%, 총 공격: ${total_attacks}개${NC}"
            fi
        done
    fi
    
    echo ""
    
    # 디렉토리 통계
    show_directory_stats
    
    echo ""
    
    # 시스템 상태
    show_system_status
}

# 디렉토리 통계 표시
show_directory_stats() {
    echo -e "${CYAN}📁 디렉토리 통계:${NC}"
    
    local dirs=("attack_logs" "attack_output" "iocs" "reports")
    
    for dir in "${dirs[@]}"; do
        local full_path="$BASE_DIR/$dir"
        if [ -d "$full_path" ]; then
            local file_count=$(find "$full_path" -type f 2>/dev/null | wc -l)
            local dir_size=$(du -sh "$full_path" 2>/dev/null | cut -f1)
            echo -e "${BLUE}  • ${dir}: ${file_count}개 파일, ${dir_size}${NC}"
        else
            echo -e "${RED}  • ${dir}: 디렉토리 없음${NC}"
        fi
    done
}

# 시스템 상태 표시
show_system_status() {
    echo -e "${CYAN}🔍 DVD 시스템 상태:${NC}"
    
    local dvd_components=(
        "10.13.0.5:Simulator"
        "10.13.0.2:Flight Controller"
        "10.13.0.3:Companion Computer"
        "10.13.0.4:Ground Control"
        "10.13.0.6:QGroundControl"
    )
    
    local online_count=0
    
    for component in "${dvd_components[@]}"; do
        local ip=$(echo "$component" | cut -d':' -f1)
        local name=$(echo "$component" | cut -d':' -f2)
        
        if ping -c 1 -W 2 "$ip" >/dev/null 2>&1; then
            echo -e "${GREEN}  ✅ ${name} (${ip})${NC}"
            online_count=$((online_count + 1))
        else
            echo -e "${RED}  ❌ ${name} (${ip})${NC}"
        fi
    done
    
    local total_components=${#dvd_components[@]}
    local availability=$((online_count * 100 / total_components))
    
    echo -e "${BLUE}  📊 시스템 가용성: ${online_count}/${total_components} (${availability}%)${NC}"
}

# 로그 조회
show_logs() {
    echo -e "${BOLD}${YELLOW}📄 Recent Attack Logs${NC}"
    echo "====================="
    echo ""
    
    local log_files=($(find "$BASE_DIR/attack_logs" -name "*.log" -mtime -${DAYS} 2>/dev/null | sort -t_ -k2 -r))
    
    if [ ${#log_files[@]} -eq 0 ]; then
        echo -e "${YELLOW}최근 ${DAYS}일 이내의 로그 파일이 없습니다.${NC}"
        return
    fi
    
    echo -e "${CYAN}발견된 로그 파일들:${NC}"
    for ((i=0; i<${#log_files[@]} && i<10; i++)); do
        local log_file="${log_files[$i]}"
        local log_name=$(basename "$log_file")
        local log_size=$(du -h "$log_file" 2>/dev/null | cut -f1)
        echo -e "${BLUE}$((i+1)). ${log_name} (${log_size})${NC}"
    done
    
    echo ""
    echo -e "${YELLOW}어떤 로그를 보시겠습니까? (1-${#log_files[@]}, 또는 'a' 전체):${NC}"
    read -r log_choice
    
    case $log_choice in
        [1-9]|10)
            if [ "$log_choice" -le ${#log_files[@]} ]; then
                local selected_log="${log_files[$((log_choice-1))]}"
                echo -e "${CYAN}[*] ${selected_log} 내용 (최근 ${LINES}줄):${NC}"
                echo "═══════════════════════════════════════════════════════════════════════════"
                tail -n "$LINES" "$selected_log" | while IFS= read -r line; do
                    # 로그 레벨에 따른 색상 적용
                    if [[ $line =~ \[ERROR\] ]]; then
                        echo -e "${RED}$line${NC}"
                    elif [[ $line =~ \[SUCCESS\]|\[✓\] ]]; then
                        echo -e "${GREEN}$line${NC}"
                    elif [[ $line =~ \[WARNING\]|\[!\] ]]; then
                        echo -e "${YELLOW}$line${NC}"
                    elif [[ $line =~ \[\*\] ]]; then
                        echo -e "${CYAN}$line${NC}"
                    else
                        echo "$line"
                    fi
                done
            else
                echo -e "${RED}잘못된 선택입니다.${NC}"
            fi
            ;;
        "a"|"A"|"all")
            echo -e "${CYAN}[*] 모든 로그 파일 요약:${NC}"
            for log_file in "${log_files[@]}"; do
                echo -e "${BLUE}=== $(basename "$log_file") ===${NC}"
                tail -n 5 "$log_file"
                echo ""
            done
            ;;
        *)
            echo -e "${RED}잘못된 선택입니다.${NC}"
            ;;
    esac
}

# 리포트 조회
show_reports() {
    echo -e "${BOLD}${BLUE}📊 Generated Reports${NC}"
    echo "==================="
    echo ""
    
    local report_files=($(find "$BASE_DIR" -name "*.json" -path "*/attack_output/*" -o -path "*/reports/*" -mtime -${DAYS} 2>/dev/null | sort -t_ -k2 -r))
    
    if [ ${#report_files[@]} -eq 0 ]; then
        echo -e "${YELLOW}최근 ${DAYS}일 이내의 리포트가 없습니다.${NC}"
        return
    fi
    
    echo -e "${CYAN}발견된 리포트들:${NC}"
    for ((i=0; i<${#report_files[@]} && i<10; i++)); do
        local report_file="${report_files[$i]}"
        local report_name=$(basename "$report_file")
        local report_size=$(du -h "$report_file" 2>/dev/null | cut -f1)
        echo -e "${BLUE}$((i+1)). ${report_name} (${report_size})${NC}"
    done
    
    echo ""
    echo -e "${YELLOW}어떤 리포트를 보시겠습니까? (1-${#report_files[@]}):${NC}"
    read -r report_choice
    
    if [[ $report_choice =~ ^[1-9][0-9]*$ ]] && [ "$report_choice" -le ${#report_files[@]} ]; then
        local selected_report="${report_files[$((report_choice-1))]}"
        echo -e "${CYAN}[*] ${selected_report} 내용:${NC}"
        echo "═══════════════════════════════════════════════════════════════════════════"
        
        if [ "$FORMAT" = "json" ]; then
            if command -v jq >/dev/null 2>&1; then
                jq '.' "$selected_report" 2>/dev/null || cat "$selected_report"
            else
                cat "$selected_report"
            fi
        else
            # 사람이 읽기 쉬운 형태로 표시
            if command -v jq >/dev/null 2>&1; then
                echo -e "${GREEN}공격 실행 정보:${NC}"
                jq -r '.dvd_comprehensive_attack_report.execution_metadata // .execution_metadata // {}' "$selected_report" 2>/dev/null | while IFS=: read -r key value; do
                    if [ -n "$key" ] && [ -n "$value" ]; then
                        echo -e "${BLUE}  • ${key}: ${value}${NC}"
                    fi
                done
                
                echo ""
                echo -e "${GREEN}공격 통계:${NC}"
                local success_rate=$(jq -r '.dvd_comprehensive_attack_report.summary_statistics.success_rate_percentage // .summary_statistics.success_rate_percentage // "N/A"' "$selected_report" 2>/dev/null)
                local total_attacks=$(jq -r '.dvd_comprehensive_attack_report.summary_statistics.total_attacks_executed // .summary_statistics.total_attacks_executed // "N/A"' "$selected_report" 2>/dev/null)
                local total_iocs=$(jq -r '.dvd_comprehensive_attack_report.summary_statistics.total_iocs_generated // .summary_statistics.total_iocs_generated // "N/A"' "$selected_report" 2>/dev/null)
                
                echo -e "${BLUE}  • 성공률: ${success_rate}%${NC}"
                echo -e "${BLUE}  • 총 공격 수: ${total_attacks}${NC}"
                echo -e "${BLUE}  • 생성된 IOCs: ${total_iocs}${NC}"
            else
                cat "$selected_report"
            fi
        fi
    else
        echo -e "${RED}잘못된 선택입니다.${NC}"
    fi
}

# IOC 조회
show_iocs() {
    echo -e "${BOLD}${RED}🔍 Indicators of Compromise (IOCs)${NC}"
    echo "=================================="
    echo ""
    
    local ioc_files=($(find "$BASE_DIR/iocs" -name "*.txt" -mtime -${DAYS} 2>/dev/null | sort -t_ -k2 -r))
    
    if [ ${#ioc_files[@]} -eq 0 ]; then
        echo -e "${YELLOW}최근 ${DAYS}일 이내의 IOC 파일이 없습니다.${NC}"
        return
    fi
    
    echo -e "${CYAN}IOC 파일 통계:${NC}"
    local total_iocs=0
    
    for ioc_file in "${ioc_files[@]}"; do
        local ioc_name=$(basename "$ioc_file")
        local ioc_count=$(wc -l < "$ioc_file" 2>/dev/null)
        total_iocs=$((total_iocs + ioc_count))
        echo -e "${BLUE}  • ${ioc_name}: ${ioc_count}개 IOC${NC}"
    done
    
    echo ""
    echo -e "${GREEN}총 IOC 수: ${total_iocs}개${NC}"
    echo ""
    
    # IOC 카테고리별 분석
    echo -e "${CYAN}IOC 카테고리 분석:${NC}"
    
    local categories=()
    for ioc_file in "${ioc_files[@]}"; do
        if [ -f "$ioc_file" ]; then
            while IFS= read -r line; do
                if [[ $line =~ ^([A-Z_]+): ]]; then
                    local category="${BASH_REMATCH[1]}"
                    categories+=("$category")
                fi
            done < "$ioc_file"
        fi
    done
    
    # 카테고리 빈도 계산
    if [ ${#categories[@]} -gt 0 ]; then
        printf '%s\n' "${categories[@]}" | sort | uniq -c | sort -nr | head -10 | while read -r count category; do
            echo -e "${BLUE}  • ${category}: ${count}개${NC}"
        done
    fi
    
    echo ""
    echo -e "${YELLOW}최근 IOC 샘플 (최근 ${LINES}개):${NC}"
    
    # 모든 IOC 파일을 합쳐서 최근 것들 표시
    local temp_ioc="/tmp/combined_iocs_$$"
    cat "${ioc_files[@]}" 2>/dev/null | tail -n "$LINES" > "$temp_ioc"
    
    while IFS= read -r ioc_line; do
        if [[ $ioc_line =~ (GPS|BATTERY|ATTITUDE|MAVLINK) ]]; then
            echo -e "${RED}  ⚠️ ${ioc_line}${NC}"
        elif [[ $ioc_line =~ (SUCCESS|COMPLETED) ]]; then
            echo -e "${GREEN}  ✅ ${ioc_line}${NC}"
        else
            echo -e "${CYAN}  • ${ioc_line}${NC}"
        fi
    done < "$temp_ioc"
    
    rm -f "$temp_ioc"
}

# 타임라인 표시
show_timeline() {
    echo -e "${BOLD}${PURPLE}📅 Attack Execution Timeline${NC}"
    echo "============================="
    echo ""
    
    # 로그 파일들에서 타임스탬프 추출
    local timeline_data="/tmp/timeline_$$"
    
    find "$BASE_DIR/attack_logs" -name "*.log" -mtime -${DAYS} 2>/dev/null | while read -r log_file; do
        local attack_type=$(basename "$(dirname "$log_file")")
        grep -E '\[.*\]|\d{4}-\d{2}-\d{2}' "$log_file" 2>/dev/null | head -20 | while IFS= read -r line; do
            echo "${attack_type}|${line}"
        done
    done | sort > "$timeline_data"
    
    if [ -s "$timeline_data" ]; then
        echo -e "${CYAN}최근 공격 활동 타임라인:${NC}"
        echo ""
        
        while IFS='|' read -r attack_type log_line; do
            # 타임스탬프 추출 시도
            if [[ $log_line =~ [0-9]{4}-[0-9]{2}-[0-9]{2}[[:space:]]+[0-9]{2}:[0-9]{2}:[0-9]{2} ]]; then
                local timestamp="${BASH_REMATCH[0]}"
                echo -e "${BLUE}${timestamp}${NC} ${YELLOW}[${attack_type}]${NC} ${log_line}"
            else
                echo -e "${PURPLE}[${attack_type}]${NC} ${log_line}"
            fi
        done < "$timeline_data" | head -n "$LINES"
    else
        echo -e "${YELLOW}타임라인 데이터가 없습니다.${NC}"
    fi
    
    rm -f "$timeline_data"
}

# 통계 표시
show_stats() {
    echo -e "${BOLD}${GREEN}📈 Execution Statistics${NC}"
    echo "======================="
    echo ""
    
    # 파일 수 통계
    echo -e "${CYAN}파일 통계 (${DAYS}일 이내):${NC}"
    
    local log_count=$(find "$BASE_DIR/attack_logs" -name "*.log" -mtime -${DAYS} 2>/dev/null | wc -l)
    local report_count=$(find "$BASE_DIR" -name "*.json" -path "*/attack_output/*" -o -path "*/reports/*" -mtime -${DAYS} 2>/dev/null | wc -l)
    local ioc_count=$(find "$BASE_DIR/iocs" -name "*.txt" -mtime -${DAYS} 2>/dev/null | wc -l)
    
    echo -e "${BLUE}  • 로그 파일: ${log_count}개${NC}"
    echo -e "${BLUE}  • 리포트: ${report_count}개${NC}"
    echo -e "${BLUE}  • IOC 파일: ${ioc_count}개${NC}"
    
    echo ""
    
    # 공격 카테고리별 통계
    echo -e "${CYAN}공격 카테고리별 활동:${NC}"
    
    local attack_dirs=("reconnaissance" "protocol_tampering" "denial_of_service" "injection" "exfiltration" "firmware_attacks")
    
    for attack_dir in "${attack_dirs[@]}"; do
        local category_logs=$(find "$BASE_DIR/attack_logs/$attack_dir" -name "*.log" -mtime -${DAYS} 2>/dev/null | wc -l)
        local category_reports=$(find "$BASE_DIR/attack_output/$attack_dir" -name "*.json" -mtime -${DAYS} 2>/dev/null | wc -l)
        
        if [ $category_logs -gt 0 ] || [ $category_reports -gt 0 ]; then
            echo -e "${BLUE}  • ${attack_dir}: ${category_logs}개 로그, ${category_reports}개 리포트${NC}"
        fi
    done
    
    echo ""
    
    # 디스크 사용량
    echo -e "${CYAN}디스크 사용량:${NC}"
    local total_size=$(du -sh "$BASE_DIR" 2>/dev/null | cut -f1)
    echo -e "${BLUE}  • 총 사용량: ${total_size}${NC}"
    
    local log_size=$(du -sh "$BASE_DIR/attack_logs" 2>/dev/null | cut -f1)
    local output_size=$(du -sh "$BASE_DIR/attack_output" 2>/dev/null | cut -f1)
    local ioc_size=$(du -sh "$BASE_DIR/iocs" 2>/dev/null | cut -f1)
    
    echo -e "${BLUE}  • 로그: ${log_size}${NC}"
    echo -e "${BLUE}  • 출력: ${output_size}${NC}"
    echo -e "${BLUE}  • IOCs: ${ioc_size}${NC}"
}

# 검색 기능
search_content() {
    local pattern="$1"
    
    echo -e "${BOLD}${YELLOW}🔍 Searching for: ${pattern}${NC}"
    echo "========================="
    echo ""
    
    if [ -z "$pattern" ]; then
        echo -e "${RED}검색어를 입력하세요.${NC}"
        return 1
    fi
    
    local search_dirs=("$BASE_DIR/attack_logs" "$BASE_DIR/attack_output" "$BASE_DIR/iocs" "$BASE_DIR/reports")
    local found_count=0
    
    for search_dir in "${search_dirs[@]}"; do
        if [ -d "$search_dir" ]; then
            echo -e "${CYAN}${search_dir}에서 검색 중...${NC}"
            
            while IFS= read -r -d '' file; do
                if grep -l -i "$pattern" "$file" >/dev/null 2>&1; then
                    found_count=$((found_count + 1))
                    local rel_path=$(realpath --relative-to="$BASE_DIR" "$file")
                    echo -e "${GREEN}  ✓ ${rel_path}${NC}"
                    
                    # 매칭 라인 표시 (최대 3줄)
                    grep -i -n --color=never "$pattern" "$file" 2>/dev/null | head -3 | while IFS= read -r line; do
                        echo -e "${BLUE}    ${line}${NC}"
                    done
                    echo ""
                fi
            done < <(find "$search_dir" -type f \( -name "*.log" -o -name "*.json" -o -name "*.txt" \) -mtime -${DAYS} -print0 2>/dev/null)
        fi
    done
    
    echo -e "${CYAN}검색 완료: ${found_count}개 파일에서 발견${NC}"
}

# 정리 기능
cleanup_old_files() {
    echo -e "${BOLD}${YELLOW}🧹 Cleaning Old Files${NC}"
    echo "===================="
    echo ""
    
    local cleanup_days=7
    echo -e "${YELLOW}${cleanup_days}일 이전 파일들을 정리하시겠습니까? (y/N)${NC}"
    read -r confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}정리 중...${NC}"
        
        local cleaned_count=0
        local cleanup_dirs=("$BASE_DIR/attack_logs" "$BASE_DIR/attack_output" "$BASE_DIR/iocs" "$BASE_DIR/temp")
        
        for cleanup_dir in "${cleanup_dirs[@]}"; do
            if [ -d "$cleanup_dir" ]; then
                local files_to_clean=($(find "$cleanup_dir" -type f -mtime +${cleanup_days} 2>/dev/null))
                
                for file in "${files_to_clean[@]}"; do
                    if [ -f "$file" ]; then
                        local rel_path=$(realpath --relative-to="$BASE_DIR" "$file")
                        echo -e "${BLUE}  삭제: ${rel_path}${NC}"
                        rm -f "$file"
                        cleaned_count=$((cleaned_count + 1))
                    fi
                done
            fi
        done
        
        echo ""
        echo -e "${GREEN}정리 완료: ${cleaned_count}개 파일 삭제${NC}"
        
        # 빈 디렉토리 정리
        find "$BASE_DIR" -type d -empty -delete 2>/dev/null
    else
        echo -e "${YELLOW}정리를 취소했습니다.${NC}"
    fi
}

# 메인 함수
main() {
    # 기본값 설정
    LINES=20
    DAYS=1
    FORMAT="text"
    OUTPUT_FILE=""
    COMMAND=""
    
    # 인자 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_usage
                exit 0
                ;;
            -n|--lines)
                LINES="$2"
                shift 2
                ;;
            -d|--days)
                DAYS="$2"
                shift 2
                ;;
            -f|--format)
                FORMAT="$2"
                shift 2
                ;;
            -o|--output)
                OUTPUT_FILE="$2"
                shift 2
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            -q|--quiet)
                exec > /dev/null 2>&1
                shift
                ;;
            summary|logs|reports|iocs|timeline|stats|cleanup)
                COMMAND="$1"
                shift
                ;;
            search)
                COMMAND="search"
                SEARCH_PATTERN="$2"
                shift 2
                ;;
            *)
                echo -e "${RED}[!] 알 수 없는 옵션: $1${NC}"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # 출력 리다이렉트 설정
    if [ -n "$OUTPUT_FILE" ]; then
        exec > "$OUTPUT_FILE"
    fi
    
    # 헤더 출력
    print_header
    
    # 명령 실행
    case $COMMAND in
        "summary")
            show_summary
            ;;
        "logs")
            show_logs
            ;;
        "reports")
            show_reports
            ;;
        "iocs")
            show_iocs
            ;;
        "timeline")
            show_timeline
            ;;
        "stats")
            show_stats
            ;;
        "search")
            search_content "$SEARCH_PATTERN"
            ;;
        "cleanup")
            cleanup_old_files
            ;;
        "")
            # 대화형 모드
            while true; do
                echo -e "${CYAN}선택하세요:${NC}"
                echo -e "${BLUE}1)${NC} Summary  ${BLUE}2)${NC} Logs     ${BLUE}3)${NC} Reports"
                echo -e "${BLUE}4)${NC} IOCs     ${BLUE}5)${NC} Timeline ${BLUE}6)${NC} Stats"
                echo -e "${BLUE}7)${NC} Search   ${BLUE}8)${NC} Cleanup  ${BLUE}q)${NC} Quit"
                echo ""
                read -p "선택 (1-8, q): " choice
                
                case $choice in
                    1) show_summary ;;
                    2) show_logs ;;
                    3) show_reports ;;
                    4) show_iocs ;;
                    5) show_timeline ;;
                    6) show_stats ;;
                    7) 
                        echo -n "검색어 입력: "
                        read -r search_term
                        search_content "$search_term"
                        ;;
                    8) cleanup_old_files ;;
                    q|Q) exit 0 ;;
                    *) echo -e "${RED}잘못된 선택입니다.${NC}" ;;
                esac
                
                echo ""
                echo -e "${YELLOW}계속하려면 Enter를 누르세요...${NC}"
                read -r
                print_header
            done
            ;;
        *)
            echo -e "${RED}[!] 알 수 없는 명령: $COMMAND${NC}"
            print_usage
            exit 1
            ;;
    esac
    
    if [ -n "$OUTPUT_FILE" ]; then
        echo -e "${GREEN}결과가 ${OUTPUT_FILE}에 저장되었습니다.${NC}" >&2
    fi
}

# 스크립트 실행
main "$@"