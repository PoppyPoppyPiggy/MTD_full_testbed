#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import datetime
import subprocess
import re
import numpy as np # ### <<< CHANGED ###

# --- 경로 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_unified.log')

# --- 환경 변수 ---
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')
TARGET_IP = os.environ.get('TARGET_IP', "10.13.0.3")
SOURCE_IP = os.environ.get('MY_IP_ADDRESS', "10.13.0.4")
PING_INTERVAL_SEC = 5

def write_jsonl(record: dict):
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"❌ [QoS Monitor] 로그 파일 쓰기 오류: {e}", file=sys.stderr)

### <<< CHANGED ###
def get_ping_stats(target_ip: str) -> (float, float, float):
    """지정된 IP로 ping을 보내 RTT, 패킷 손실률, 지터를 반환합니다."""
    try:
        result = subprocess.run(
            ["ping", "-c", "10", "-i", "0.2", "-W", "2", target_ip],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout
        
        # RTT와 패킷 손실률 추출
        rtt_match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/([\d.]+)", output)
        avg_rtt = float(rtt_match.group(1)) if rtt_match else -1.0
        mdev_rtt = float(rtt_match.group(2)) if rtt_match else -1.0 # mdev is a good proxy for jitter

        loss_match = re.search(r"(\d+)% packet loss", output)
        packet_loss = float(loss_match.group(1)) if loss_match else 100.0

        return avg_rtt, packet_loss, mdev_rtt

    except (subprocess.TimeoutExpired, Exception):
        return -1.0, 100.0, -1.0
### <<< END CHANGED ###

def main():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    print(f"[QoS Monitor] 네트워크 품질 측정을 시작합니다 -> {LOG_FILE_PATH}")
    print(f"✅ [QoS Monitor] 현재 공격 라벨: {CURRENT_ATTACK_LABEL}")
    
    while True:
        try:
            avg_rtt, packet_loss, jitter = get_ping_stats(TARGET_IP) # ### <<< CHANGED ###
            
            record = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "ts": time.time(),
                "source": "qos_monitor",
                "type": "network_qos",
                "data": {
                    "target_ip": TARGET_IP,
                    "source_ip": SOURCE_IP,
                    "avg_rtt_ms": avg_rtt,
                    "packet_loss_pct": packet_loss,
                    "jitter_ms": jitter # ### <<< CHANGED ###
                }
            }
            write_jsonl(record)
            print(f"[QoS Monitor] Target: {TARGET_IP}, RTT: {avg_rtt:.2f} ms, Loss: {packet_loss:.1f}%, Jitter: {jitter:.2f} ms")
            
            time.sleep(PING_INTERVAL_SEC)
            
        except KeyboardInterrupt:
            print("\n[QoS Monitor] 사용자 요청으로 모니터링을 중지합니다.")
            break
        except Exception as e:
            print(f"❌ [QoS Monitor] 처리 중 예외 발생: {e}", file=sys.stderr)
            time.sleep(2)

if __name__ == "__main__":
    main()