import json
import os
import sys
import time
import subprocess

# 프로젝트 루트 경로 설정
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
from bus.logger import log_bus_event

# MTD 상태 파일 경로
STATE_FILE_PATH = os.path.join(PROJECT_ROOT, 'mtd', 'shared_state', 'mtd_state.json')
# Prober가 스캔할 IP 대역
SCAN_SUBNET = "10.13.0.0/24"
# Prober가 찾으려는 서비스 포트
TARGET_PORT = 14550
# 스캔 주기 (초)
PROBE_INTERVAL = 5

def get_current_target_from_state():
    """MTD 상태 파일에서 현재 타겟을 읽어옵니다."""
    try:
        with open(STATE_FILE_PATH, 'r') as f:
            return json.load(f).get("current_target")
    except:
        return None

def probe_network():
    """
    네트워크를 스캔하여 활성화된 타겟을 찾습니다.
    (실제로는 nmap과 같은 정교한 도구를 사용해야 하지만, 여기서는 시뮬레이션을 위해 간단히 구현)
    """
    log_bus_event('prober_scan_started', {'subnet': SCAN_SUBNET, 'port': TARGET_PORT})
    print(f"[{time.ctime()}] PROBER: MTD 변경 감지! 네트워크 스캔 시작 ({SCAN_SUBNET})...")

    # --- 시뮬레이션 로직 ---
    # 실제 환경에서는 `nmap` 이나 `ping`을 사용해야 합니다.
    # 여기서는 단순히 현재 MTD 상태 파일의 타겟이 무엇인지 '훔쳐보는' 방식으로 시뮬레이션합니다.
    time.sleep(3) # 스캔하는 척 시간 지연

    new_target_full = get_current_target_from_state()
    if new_target_full:
        new_target_ip = new_target_full.split(':')[0]
        print(f"[{time.ctime()}] PROBER: 스캔 성공! 새로운 활성 타겟을 찾음: {new_target_ip}")
        log_bus_event('prober_scan_success', {'found_ip': new_target_ip})
        return new_target_ip
    else:
        print(f"[{time.ctime()}] PROBER: 스캔 실패. 타겟을 찾을 수 없음.")
        log_bus_event('prober_scan_failed', {})
        return None


def main():
    """Prober 메인 루프"""
    print("지능형 공격자 Prober 시작... (Ctrl+C로 종료)")
    log_bus_event('prober_started', {})
    last_known_target_ip = None

    while True:
        current_target_full = get_current_target_from_state()
        if not current_target_full:
            time.sleep(PROBE_INTERVAL)
            continue

        current_target_ip = current_target_full.split(':')[0]

        # 최초 실행 시, 현재 타겟을 인지
        if last_known_target_ip is None:
            last_known_target_ip = current_target_ip
            print(f"[{time.ctime()}] PROBER: 초기 타겟 인지 -> {last_known_target_ip}")
            log_bus_event('prober_initial_target_acquired', {'target': last_known_target_ip})

        # MTD가 발생했는지 확인 (ping 테스트로 대체)
        # PING 10.13.0.3 (10.13.0.3) 56(84) bytes of data. ... 1 packets transmitted, 0 received, 100% packet loss
        # `ping` 명령어의 결과에서 '100% packet loss' 문자열이 있으면 타겟이 사라진 것으로 간주
        response = subprocess.run(['ping', '-c', '1', last_known_target_ip], capture_output=True, text=True)
        if "100% packet loss" in response.stdout or response.returncode != 0:
             # 타겟이 사라졌으므로, 네트워크를 다시 스캔하여 새 타겟을 찾음
            new_ip = probe_network()
            if new_ip:
                last_known_target_ip = new_ip
        else:
             print(f"[{time.ctime()}] PROBER: 타겟 {last_known_target_ip} 정상 응답. 대기...")


        time.sleep(PROBE_INTERVAL)

if __name__ == "__main__":
    main()