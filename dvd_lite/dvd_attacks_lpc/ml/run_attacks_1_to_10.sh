#!/bin/bash

# --- 설정 ---
# 각 공격을 실행할 시간 (초)
DURATION=60 
# 공격 사이의 대기 시간 (초)
DELAY=10
# orchestrator 스크립트 경로 (ml 디렉토리 기준)
ORCHESTRATOR_SCRIPT="../attack_orchestrator.py" 
# --- 설정 끝 ---

# event_mapping.json 기준 1번부터 10번까지의 공격 이름 목록
ATTACKS=(
    "gps-spoofing"                   # 1
    "communication-link-flooding"    # 2
    "mavlink-injection-attack"       # 3
    "attitude-spoofing"              # 4
    "battery-spoofing"               # 5
    # "camera-feed-eavesdropping"      # 6
    # "camera-feed-ros-topic-flooding" # 7
    # "camera-gimbal-takeover"         # 8
    # "companion-computer-discovery"   # 9
    # "companion-computer-takeover"    # 10
)

echo "Starting loop to run attacks 1-10 repeatedly."
echo "Duration per attack: ${DURATION}s, Delay between attacks: ${DELAY}s"
echo "Press Ctrl+C to stop the loop."

# 무한 반복 (Ctrl+C로 중지)
while true; do
    # 목록에 있는 각 공격 실행
    for attack_name in "${ATTACKS[@]}"; do
        echo ""
        echo "--- Starting attack: $attack_name ---"
        # orchestrator 스크립트 실행
        python3 "$ORCHESTRATOR_SCRIPT" start "$attack_name" -d "$DURATION"

        # 공격 실행 후 결과 확인 (선택적)
        # sleep 1 # orchestrator가 상태 업데이트할 시간 잠시 대기
        # python3 "$ORCHESTRATOR_SCRIPT" list 

        echo "--- Attack $attack_name finished. Waiting ${DELAY}s... ---"
        sleep "$DELAY"
    done

    echo "=== Completed one cycle of attacks 1-10. Starting next cycle... ==="
    # 필요시 사이클 사이에 추가 대기 시간 설정 가능
    # sleep 30 
done

echo "Loop stopped."
exit 0