# dvd_lite/dvd_attacks_lpc/utils/instance_heartbeat.py

import os
import time
import json
import socket
import psutil
import datetime
import pathlib
import threading

# --- 경로 설정 ---
# 이 파일의 위치(.../utils/)에서 세 단계 위로 올라가 프로젝트 루트를 찾습니다.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BUS_DIR = PROJECT_ROOT / 'dvd_lite' / 'dvd_attacks_lpc' / 'bus'
LOG_PATH = BUS_DIR / 'bus_dvd_instances.log'

def _get_container_id():
    """Linux 환경에서 현재 프로세스의 컨테이너 ID를 조회합니다."""
    # /proc/self/cgroup 파일을 읽어 Docker 또는 k8s 환경의 cgroup 경로에서 ID 추출
    cgroup_path = '/proc/self/cgroup'
    if os.path.exists(cgroup_path):
        try:
            with open(cgroup_path) as f:
                for line in f:
                    if 'docker' in line or 'kubepods' in line:
                        return line.strip().split('/')[-1][:12]
        except Exception:
            pass
    return None

def _emit_beat(role: str):
    """실제 하트비트 데이터를 생성하고 로그 파일에 기록하는 내부 함수."""
    p = psutil.Process()
    inst_id = os.getenv('DVD_INSTANCE_ID', f"{role}-{os.getpid()}")
    version = os.getenv('DVD_VERSION', '0.1.0') # 기본 버전
    git_sha = os.getenv('DVD_GIT_SHA', None)
    host = socket.gethostname()
    cid = _get_container_id()

    try:
        # psutil.cpu_percent()는 첫 호출 시 의미 없는 값을 반환하므로 초기화
        psutil.cpu_percent(interval=None)
        
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            rec = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": role,
                "type": "instance_heartbeat",
                "instance": {
                    "instance_id": inst_id,
                    "role": role,
                    "version": version,
                    "git_sha": git_sha,
                    "hostname": host,
                    "container_id": cid
                },
                "runtime": {
                    "pid": p.pid,
                    "uptime_sec": int(time.time() - p.create_time()),
                    "cpu_pct": psutil.cpu_percent(interval=None),
                    "mem_rss_mb": round(p.memory_info().rss / (1024*1024), 2),
                    "open_fds": p.num_fds() if hasattr(p, "num_fds") else None,
                    "threads": p.num_threads(),
                },
                # 아래 값들은 해당 인스턴스가 환경 변수로 설정해야 함 (선택 사항)
                "queues": {
                    "in": int(os.getenv('Q_IN', '0')),
                    "out": int(os.getenv('Q_OUT', '0')),
                    "drop_total": int(os.getenv('Q_DROP', '0')),
                },
                "health": {
                    "status": os.getenv('HEALTH_STATUS', 'OK'),
                    "reason": os.getenv('HEALTH_REASON', None),
                }
            }
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"[{role}] 하트비트 로그 기록 실패: {e}", flush=True)

def start_heartbeat_thread(role: str, interval_sec: float = 2.0):
    """
    지정된 역할(role)로 하트비트를 주기적으로 보내는 스레드를 시작합니다.
    
    사용 예시:
    from dvd_lite.dvd_attacks_lpc.utils.instance_heartbeat import start_heartbeat_thread
    start_heartbeat_thread("my_service_name")
    """
    os.makedirs(BUS_DIR, exist_ok=True)
    
    def heartbeater():
        while True:
            _emit_beat(role)
            time.sleep(interval_sec)

    # 메인 스레드가 종료될 때 함께 종료되도록 daemon=True 설정
    thread = threading.Thread(target=heartbeater, daemon=True)
    thread.start()
    print(f"✅ [{role}] 인스턴스 하트비트 스레드 시작 (주기: {interval_sec}초)")
    return thread

# 이 파일을 직접 실행하여 테스트할 수 있습니다.
if __name__ == '__main__':
    print("인스턴스 하트비트 유틸리티 테스트 시작...")
    print(f"로그 파일 위치: {LOG_PATH}")
    test_thread = start_heartbeat_thread("test_instance", 1.0)
    try:
        # 5초 동안 실행 후 종료
        time.sleep(5)
        print("테스트 종료.")
    except KeyboardInterrupt:
        pass
