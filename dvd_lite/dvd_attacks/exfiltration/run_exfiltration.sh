#!/bin/bash
# DVD 데이터 탈취 공격 메인 실행 스크립트

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

TACTIC_NAME="exfiltration"
LOG_FILE="$LOG_BASE_DIR/${TACTIC_NAME}_$(date +%Y%m%d_%H%M%S).log"

print_attack_header "🕵️ DVD 데이터 탈취 공격 모음집 🕵️"

main() {
    log_info "데이터 탈취 공격 시작..."
    
    local ioc_file=$(create_ioc_file "$TACTIC_NAME")
    
    # 시뮬레이션 공격 실행
    log_info "데이터 탈취 공격 시뮬레이션 실행 중..."
    simulation_wait 5 15
    
    add_ioc "$ioc_file" "ATTACK_SIMULATED:exfiltration_simulation:$(date +%s)"
    add_ioc "$ioc_file" "TACTIC_COMPLETE:$TACTIC_NAME:$(date +%s)"
    add_ioc "$ioc_file" "SUCCESS_RATE:1/1"
    
    log_success "데이터 탈취 공격 시뮬레이션 완료"
    
    generate_attack_json "$TACTIC_NAME" "success" "$ioc_file"
    
    echo "IOC 파일: $ioc_file"
    echo "로그 파일: $LOG_FILE"
}

main "$@"
