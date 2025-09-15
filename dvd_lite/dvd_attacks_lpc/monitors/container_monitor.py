import docker
import json
import os
import sys
import time
import subprocess

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
from bus.logger import log_dvd_event, log_bus_event

# --- 설정 ---
# MAVProxy가 통신하는 TCP 포트 (DVD 시뮬레이터 기본 설정)
FC_TCP_PORT = 9003
MONITOR_INTERVAL_SECONDS = 3

def get_fc_telemetry(container_name):
    """
    docker exec를 이용해 컨테이너 내부에서 MAVProxy를 실행,
    비행 컨트롤러(FC)의 핵심 텔레메트리를 JSON으로 추출합니다.
    """
    # MAVProxy 스크립트: 상태를 한번만 출력하고 종료
    mavproxy_command = (
        "from pymavlink import mavutil; "
        "import json; "
        "mav = mavutil.mavlink_connection('tcp:127.0.0.1:%d'); "
        "msg = mav.recv_match(type=['HEARTBEAT', 'SYS_STATUS', 'ATTITUDE'], blocking=True, timeout=3); "
        "if msg: print(json.dumps(msg.to_dict()));"
    ) % FC_TCP_PORT
    
    docker_command = [
        "docker", "exec", container_name,
        "python3", "-c", mavproxy_command
    ]
    
    try:
        result = subprocess.run(docker_command, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout:
            # 성공적으로 JSON을 받아오면 파싱하여 반환
            return json.loads(result.stdout)
        else:
            return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None

def main():
    """컨테이너 모니터를 시작합니다."""
    container_name = "flight-controller-lite"
    print(f"DVD 컨테이너 모니터 v2 ({container_name}) 시작... (Ctrl+C로 종료)")
    log_bus_event('container_monitor_start', {'version': 'v2', 'target': container_name})

    while True:
        telemetry = get_fc_telemetry(container_name)
        
        if telemetry:
            # bus_dvd.log에 FC의 상세 텔레메트리 기록
            log_dvd_event(container_name, telemetry)
            msg_type = telemetry.get('mavpackettype')
            if msg_type == 'SYS_STATUS':
                battery_remaining = telemetry.get('battery_remaining', -1)
                print(f"[{time.ctime()}] {container_name}: 배터리 {battery_remaining}%")
            elif msg_type == 'HEARTBEAT':
                system_status = telemetry.get('system_status', -1)
                print(f"[{time.ctime()}] {container_name}: 시스템 상태 {system_status}")
        
        time.sleep(MONITOR_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n컨테이너 모니터 종료.")
        log_bus_event('container_monitor_stop', {})