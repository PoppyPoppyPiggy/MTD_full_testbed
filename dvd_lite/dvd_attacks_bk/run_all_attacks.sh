#!/bin/bash
# DVD 전체 공격 시나리오 실행 스크립트 (수정된 버전)

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_LOG="$LOG_BASE_DIR/master_attack_$(date +%Y%m%d_%H%M%S).log"
MASTER_IOC="/tmp/master_iocs_$(date +%Y%m%d_%H%M%S).txt"

print_attack_header "🎯 DVD 전체 공격 시나리오 실행기 🎯"

main() {
    log_info "DVD 전체 공격 시나리오 시작..."
    
    echo "# DVD 마스터 IOC 파일" > "$MASTER_IOC"
    echo "# 생성 시간: $(date)" >> "$MASTER_IOC"
    echo "MASTER_ATTACK_START:$(date +%s)" >> "$MASTER_IOC"
    
    # 공격 전술 순서 (실제 공격 시나리오 순서)
    local tactics=(
        "reconnaissance"
        "protocol_tampering"
        "denial_of_service"
        "injection"
        "exfiltration"
        "firmware_attacks"
    )
    
    local success_count=0
    local total_tactics=${#tactics[@]}
    
    for tactic in "${tactics[@]}"; do
        local tactic_script="$SCRIPT_DIR/$tactic/run_${tactic}.sh"
        
        log_info "🎯 전술 실행: $tactic"
        
        if [ -f "$tactic_script" ] && [ -x "$tactic_script" ]; then
            if timeout 300 "$tactic_script" >> "$MASTER_LOG" 2>&1; then
                log_success "$tactic 전술 완료"
                echo "TACTIC_SUCCESS:$tactic:$(date +%s)" >> "$MASTER_IOC"
                success_count=$((success_count + 1))
                
                # IOC 파일 수집
                local tactic_ioc="/tmp/${tactic}_iocs.txt"
                if [ -f "$tactic_ioc" ]; then
                    echo "# === $tactic IOCs ===" >> "$MASTER_IOC"
                    cat "$tactic_ioc" >> "$MASTER_IOC"
                    echo "" >> "$MASTER_IOC"
                fi
            else
                log_error "$tactic 전술 실패"
                echo "TACTIC_FAILED:$tactic:$(date +%s)" >> "$MASTER_IOC"
            fi
        else
            log_error "$tactic 스크립트를 찾을 수 없습니다: $tactic_script"
            echo "TACTIC_MISSING:$tactic:$(date +%s)" >> "$MASTER_IOC"
        fi
        
        # 전술 간 대기 시간
        if [ "$tactic" != "firmware_attacks" ]; then
            log_info "다음 전술까지 30초 대기..."
            sleep 30
        fi
    done
    
    echo "MASTER_ATTACK_COMPLETE:$(date +%s)" >> "$MASTER_IOC"
    echo "MASTER_SUCCESS_RATE:${success_count}/${total_tactics}" >> "$MASTER_IOC"
    
    log_info "=== DVD 공격 시나리오 완료 ==="
    log_info "성공한 전술: ${success_count}/${total_tactics}"
    log_info "마스터 로그: $MASTER_LOG"
    log_info "마스터 IOC: $MASTER_IOC"
    
    # 최종 결과 JSON 생성
    generate_attack_json "master_attack_scenario" "success" "$MASTER_IOC"
}

main "$@"
