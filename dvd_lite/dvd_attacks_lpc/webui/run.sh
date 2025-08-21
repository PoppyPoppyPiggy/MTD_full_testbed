#!/bin/bash

# MTD 드론 보안 테스트베드 WebUI 실행 스크립트

set -e

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

WEBUI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WEBUI_DIR"

log_info "MTD 드론 보안 테스트베드 WebUI 시작"

# Python 가상환경 확인
if [ -f "../venv/bin/activate" ]; then
    log_info "Python 가상환경 활성화"
    source ../venv/bin/activate
else
    log_warning "Python 가상환경을 찾을 수 없습니다. 전역 환경을 사용합니다."
fi

# 필수 패키지 설치
log_info "필수 패키지 확인 및 설치"
pip install flask flask-socketio > /dev/null 2>&1 || true

# WebUI 서버 시작
log_info "WebUI 서버 시작 중..."
cd backend
python app.py

log_success "WebUI 서버가 중지되었습니다."
