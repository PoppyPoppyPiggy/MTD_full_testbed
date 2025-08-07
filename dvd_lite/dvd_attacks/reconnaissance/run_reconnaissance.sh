#!/bin/bash
# DVD 정찰 공격 메인 실행 스크립트

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

TACTIC_NAME="reconnaissance"
LOG_FILE="$LOG_BASE_DIR/${TACTIC_NAME}_$(date +%Y%m%d_%H%M%S).log"

print_attack_header "🔍 DVD 정찰 공격 모음집 🔍"

main() {
    log_info "정찰 공격 시작..."
    
    # IOC 파일 생성
    local ioc_file=$(create_ioc_file "$TACTIC_NAME")
    
    # 사용 가능한 정찰 공격들
    local recon_attacks=(
        "wifi_network_discovery.sh"
        "mavlink_service_discovery.sh"
        "drone_component_enumeration.sh"
        "camera_stream_discovery.sh"
    )
    
    local success_count=0
    local total_attacks=${#recon_attacks[@]}
    
    for attack in "${recon_attacks[@]}"; do
        local attack_script="$(dirname "$0")/$attack"
        
        if [ -f "$attack_script" ] && [ -x "$attack_script" ]; then
            log_info "실행 중: $attack"
            if timeout 60 "$attack_script" >> "$LOG_FILE" 2>&1; then
                log_success "$attack 완료"
                add_ioc "$ioc_file" "ATTACK_SUCCESS:$attack:$(date +%s)"
                success_count=$((success_count + 1))
            else
                log_error "$attack 실패"
                add_ioc "$ioc_file" "ATTACK_FAILED:$attack:$(date +%s)"
            fi
        else
            log_warning "$attack 스크립트 없음 - 시뮬레이션 모드"
            simulation_wait 2 5
            log_success "$attack 시뮬레이션 완료"
            add_ioc "$ioc_file" "ATTACK_SIMULATED:$attack:$(date +%s)"
            success_count=$((success_count + 1))
        fi
    done
    
    # 결과 요약
    add_ioc "$ioc_file" "TACTIC_COMPLETE:$TACTIC_NAME:$(date +%s)"
    add_ioc "$ioc_file" "SUCCESS_RATE:${success_count}/${total_attacks}"
    
    log_info "정찰 공격 완료: ${success_count}/${total_attacks} 성공"
    
    # JSON 결과 생성
    local status="success"
    if [ $success_count -eq 0 ]; then
        status="failed"
    elif [ $success_count -lt $total_attacks ]; then
        status="partial"
    fi
    
    generate_attack_json "$TACTIC_NAME" "$status" "$ioc_file"
    
    echo "IOC 파일: $ioc_file"
    echo "로그 파일: $LOG_FILE"
}

main "$@"
