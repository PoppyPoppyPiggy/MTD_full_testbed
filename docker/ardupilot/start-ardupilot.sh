#!/bin/bash
set -e

echo "ArduPilot SITL 시작 중..."

cd /ardupilot

# 매개변수 파일 확인
if [ -f /configs/copter.parm ]; then
    echo "매개변수 파일 로드: /configs/copter.parm"
    PARAMS_FILE="/configs/copter.parm"
else
    PARAMS_FILE=""
fi

# SITL 실행
python3 Tools/autotest/sim_vehicle.py \
    --vehicle=${SITL_VEHICLE:-copter} \
    --location=${SITL_LOCATION:-KSFO} \
    --instance=${SITL_INSTANCE:-0} \
    --speedup=${SITL_SPEEDUP:-1} \
    --out=0.0.0.0:14550 \
    --out=0.0.0.0:14551 \
    --console \
    --map \
    ${PARAMS_FILE:+--load-module $PARAMS_FILE} \
    --no-rebuild
