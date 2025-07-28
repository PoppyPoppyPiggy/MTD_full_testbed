#!/bin/bash
# setup_directories.sh - DVD Attack Tools Directory Structure Setup
# 이 스크립트를 먼저 실행하여 디렉토리 구조를 생성하세요

echo "🔧 DVD Attack Tools 디렉토리 구조 생성 중..."

# Base directory
BASE_DIR="/home/kali/MTD/MTD_full_testbed"

# Create directory structure
echo "📁 디렉토리 생성..."
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/reconnaissance"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/common"
mkdir -p "$BASE_DIR/attack_logs"
mkdir -p "$BASE_DIR/attack_output"
mkdir -p "$BASE_DIR/iocs"

echo "✅ 디렉토리 생성 완료:"
echo "├── $BASE_DIR/"
echo "│   ├── dvd_lite/dvd_attacks/"
echo "│   │   ├── reconnaissance/"
echo "│   │   └── common/"
echo "│   ├── attack_logs/"
echo "│   ├── attack_output/"
echo "│   └── iocs/"

# Set permissions
echo "🔐 권한 설정..."
chmod 755 "$BASE_DIR"
chmod 755 "$BASE_DIR/dvd_lite"
chmod 755 "$BASE_DIR/dvd_lite/dvd_attacks"
chmod 755 "$BASE_DIR/dvd_lite/dvd_attacks/reconnaissance"
chmod 755 "$BASE_DIR/dvd_lite/dvd_attacks/common"
chmod 755 "$BASE_DIR/attack_logs"
chmod 755 "$BASE_DIR/attack_output"
chmod 755 "$BASE_DIR/iocs"

echo ""
echo "🎯 다음 단계:"
echo "1. 각 파일을 해당 경로에 저장하세요:"
echo "   • colors.sh → $BASE_DIR/dvd_lite/dvd_attacks/common/"
echo "   • utils.sh → $BASE_DIR/dvd_lite/dvd_attacks/common/"
echo "   • wifi_discovery.sh → $BASE_DIR/dvd_lite/dvd_attacks/reconnaissance/"
echo "   • mavlink_discovery.sh → $BASE_DIR/dvd_lite/dvd_attacks/reconnaissance/"
echo "   • component_enum.sh → $BASE_DIR/dvd_lite/dvd_attacks/reconnaissance/"
echo "   • camera_discovery.sh → $BASE_DIR/dvd_lite/dvd_attacks/reconnaissance/"
echo "   • run_reconnaissance.sh → $BASE_DIR/"
echo "   • quick_start.sh → $BASE_DIR/"
echo ""
echo "2. 실행 권한 부여:"
echo "   chmod +x $BASE_DIR/*.sh"
echo "   chmod +x $BASE_DIR/dvd_lite/dvd_attacks/reconnaissance/*.sh"
echo ""
echo "3. 실행:"
echo "   sudo $BASE_DIR/quick_start.sh"

echo ""
echo "✅ 디렉토리 구조 생성 완료!"