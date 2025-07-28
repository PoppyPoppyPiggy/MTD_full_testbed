#!/bin/bash
# quick_start.sh - Quick Start Script for DVD Attacks
# Path: /home/kali/MTD/MTD_full_testbed/quick_start.sh

source "$(dirname "$0")/dvd_lite/dvd_attacks/common/colors.sh"

echo -e "${CYAN}🚀 DVD Quick Start${NC}"
echo "=================="
echo ""

echo -e "${BLUE}1. DVD 시스템 상태 확인...${NC}"
ping -c 1 10.13.0.5 >/dev/null 2>&1 && echo -e "${GREEN}✅ Simulator Online${NC}" || echo -e "${RED}❌ Simulator Offline${NC}"
ping -c 1 10.13.0.2 >/dev/null 2>&1 && echo -e "${GREEN}✅ Flight Controller Online${NC}" || echo -e "${RED}❌ Flight Controller Offline${NC}"
ping -c 1 10.13.0.3 >/dev/null 2>&1 && echo -e "${GREEN}✅ Companion Computer Online${NC}" || echo -e "${RED}❌ Companion Computer Offline${NC}"
ping -c 1 10.13.0.4 >/dev/null 2>&1 && echo -e "${GREEN}✅ Ground Control Online${NC}" || echo -e "${RED}❌ Ground Control Offline${NC}"

echo ""
echo -e "${BLUE}2. 필수 도구 확인...${NC}"
for tool in nmap airmon-ng airodump-ng curl python3; do
    if command -v "$tool" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ $tool${NC}"
    else
        echo -e "${RED}❌ $tool (missing)${NC}"
    fi
done

echo ""
echo -e "${YELLOW}3. 빠른 정찰 공격 실행 (자동)...${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Root 권한이 필요합니다. sudo로 실행하세요.${NC}"
    exit 1
fi

# Run automatic reconnaissance
echo -e "${PURPLE}📡 자동 정찰 모드 시작...${NC}"

# Change to script directory for execution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Execute main reconnaissance with option 6 (run all)
echo "6" | sudo "$SCRIPT_DIR/run_reconnaissance.sh" 2>/dev/null || {
    echo -e "${YELLOW}❌ 자동 실행 실패. 수동 모드로 전환...${NC}"
    echo ""
    echo -e "${CYAN}💡 수동 실행 방법:${NC}"
    echo "sudo $SCRIPT_DIR/run_reconnaissance.sh"
    echo ""
    echo -e "${CYAN}🎯 개별 공격 실행:${NC}"
    echo "sudo $SCRIPT_DIR/dvd_lite/dvd_attacks/reconnaissance/wifi_discovery.sh"
    echo "sudo $SCRIPT_DIR/dvd_lite/dvd_attacks/reconnaissance/mavlink_discovery.sh"
    echo "sudo $SCRIPT_DIR/dvd_lite/dvd_attacks/reconnaissance/component_enum.sh"
    echo "sudo $SCRIPT_DIR/dvd_lite/dvd_attacks/reconnaissance/camera_discovery.sh"
}

echo ""
echo -e "${GREEN}🎉 Quick Start 완료!${NC}"
echo -e "${CYAN}📋 다음 단계:${NC}"
echo "• 결과 확인: $SCRIPT_DIR/view_results.sh"
echo "• 상세 실행: sudo $SCRIPT_DIR/run_reconnaissance.sh"
echo "• 로그 위치: $SCRIPT_DIR/attack_logs/"
echo "• 리포트 위치: $SCRIPT_DIR/attack_output/"