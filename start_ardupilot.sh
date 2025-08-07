#!/bin/bash
# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_ardupilot.sh
# ArduPilot SITL 시작 스크립트

ARDUPILOT_DIR="./ardupilot"
VENV_PATH="./mtd_env"

echo "🛩️ ArduPilot SITL 시작 중..."

# 가상환경 활성화
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    echo "✅ 가상환경 활성화됨"
fi

if [ -d "$ARDUPILOT_DIR" ]; then
    cd "$ARDUPILOT_DIR"
    
    if [ -f "Tools/autotest/sim_vehicle.py" ]; then
        echo "SITL 시작: ArduCopter"
        python Tools/autotest/sim_vehicle.py \
            --vehicle=ArduCopter \
            --aircraft=test \
            --location=KSFO \
            --out=127.0.0.1:14550 \
            --out=127.0.0.1:14551 \
            --console \
            --no-rebuild &
        
        SITL_PID=$!
        echo $SITL_PID > /tmp/ardupilot_sitl.pid
        echo "✅ ArduPilot SITL 시작됨 (PID: $SITL_PID)"
        
        sleep 15
        echo "🚁 ArduPilot SITL 준비 완료"
    else
        echo "❌ sim_vehicle.py를 찾을 수 없습니다"
        exit 1
    fi
else
    echo "❌ ArduPilot 디렉토리를 찾을 수 없습니다"
    exit 1
fi
