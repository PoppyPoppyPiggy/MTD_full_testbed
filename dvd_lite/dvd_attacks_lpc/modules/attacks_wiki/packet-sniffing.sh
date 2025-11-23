#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Packet-Sniffing.md
# Created: 2025-11-23 16:46:38
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=packet-sniffing src=Packet-Sniffing.md"
log "[BLOCK 1] type=shell"
git clone https://github.com/mavlink/mavlink.git --recursive
cd mavlink
python3 -m venv mavenv
source mavenv/bin/activate

log "[BLOCK 2] type=shell"
python3 -m pymavlink.tools.mavgen --lang=WLua --wire-protocol=2.0 --output=mavlink_2_common message_definitions/v1.0/ardupilotmega.xml

log "[BLOCK 3] type=shell"
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.HEX_DEC)

log "[BLOCK 4] type=shell"
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.DEC)

log "[BLOCK 5] type=shell"
local udp_dissector_table = DissectorTable.get("udp.port")
udp_dissector_table:add(${PORT_MAVLINK}, mavlink_proto)
udp_dissector_table:add(14580, mavlink_proto)
udp_dissector_table:add(18570, mavlink_proto)

log "[BLOCK 6] type=shell"
/usr/lib/x86_64-linux-gnu/wireshark
/usr/lib/aarch64-linux-gnu/wireshark
~/.local/lib/wireshark/plugins
~/.wireshark/plugins

log "[BLOCK 7] type=shell"
git clone https://github.com/mavlink/mavlink.git --recursive
cd mavlink
python3 -m venv mavenv
source mavenv/bin/activate

log "[BLOCK 8] type=shell"
python3 -m pymavlink.tools.mavgen --lang=WLua --wire-protocol=2.0 --output=mavlink_2_common message_definitions/v1.0/ardupilotmega.xml

log "[BLOCK 9] type=shell"
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.HEX_DEC)

log "[BLOCK 10] type=shell"
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.DEC)

log "[BLOCK 11] type=shell"
local udp_dissector_table = DissectorTable.get("udp.port")
udp_dissector_table:add(${PORT_MAVLINK}, mavlink_proto)
udp_dissector_table:add(14580, mavlink_proto)
udp_dissector_table:add(18570, mavlink_proto)

log "[BLOCK 12] type=shell"
/usr/lib/x86_64-linux-gnu/wireshark
/usr/lib/aarch64-linux-gnu/wireshark
~/.local/lib/wireshark/plugins
~/.wireshark/plugins

