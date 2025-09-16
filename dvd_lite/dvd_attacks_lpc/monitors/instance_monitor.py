# monitors/instance_monitor.py

import os
import time
import json
import datetime
import pathlib
from collections import defaultdict

# --- 경로 설정 ---
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BUS_DIR = PROJECT_ROOT / 'dvd_lite' / 'dvd_attacks_lpc' / 'bus'
INSTANCE_LOG_PATH = BUS_DIR / 'bus_dvd_instances.log'
OUTPUT_LOG_PATH = BUS_DIR / 'bus_dvd.log' # 다른 로그와 함께 bus_dvd.log에 기록

# --- 모니터링 설정 ---
SUMMARY_INTERVAL_SEC = 5.0  # 요약 정보 로깅 주기
ALERT_CPU_THRESHOLD = 80.0  # CPU 사용량 경고 임계치 (%)
ALERT_MEM_THRESHOLD = 800.0 # 메모리 사용량 경고 임계치 (MB)

def tail_file(file_path):
    """파일의 새로운 라인을 지속적으로 읽어오는 제너레이터."""
    if not os.path.exists(file_path):
        print(f"로그 파일({file_path})을 찾을 수 없어 1초마다 다시 확인합니다.")
        while not os.path.exists(file_path):
            time.sleep(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        # 파일의 끝으로 이동
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line

def write_output_log(record: dict):
    """모니터링 결과를 출력 로그 파일에 기록합니다."""
    try:
        with open(OUTPUT_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except IOError as e:
        print(f"❌ 출력 로그 쓰기 오류: {e}")

def check_for_alerts(instance_id: str, last_state: dict, current_state: dict):
    """이전 상태와 현재 상태를 비교하여 경고 이벤트를 생성합니다."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # HEALTH 상태가 ERROR로 변경된 경우
    last_health = last_state.get('health', {}).get('status', 'OK')
    current_health = current_state.get('health', {}).get('status', 'OK')
    if last_health == 'OK' and current_health != 'OK':
        alert = {
            "timestamp": now, "source": "instance_monitor", "type": "instance_alert",
            "level": "CRITICAL", "instance_id": instance_id,
            "reason": "health_status_degraded",
            "detail": f"Status changed from {last_health} to {current_health}. Reason: {current_state.get('health', {}).get('reason')}"
        }
        print(f"🚨 ALERT: {alert['reason']} for {instance_id}")
        write_output_log(alert)

    # CPU 사용량 임계치 초과
    cpu_pct = current_state.get('runtime', {}).get('cpu_pct', 0)
    if cpu_pct > ALERT_CPU_THRESHOLD:
        alert = {
            "timestamp": now, "source": "instance_monitor", "type": "instance_alert",
            "level": "WARNING", "instance_id": instance_id,
            "reason": "high_cpu_usage",
            "detail": f"CPU usage is {cpu_pct:.1f}% (Threshold: {ALERT_CPU_THRESHOLD}%)"
        }
        print(f"🚨 ALERT: {alert['reason']} for {instance_id}")
        write_output_log(alert)

def main():
    """인스턴스 하트비트 로그를 감시하고 요약 및 경고를 생성합니다."""
    print("--- 인스턴스 중앙 관제 모니터 시작 ---")
    print(f"감시 대상 로그: {INSTANCE_LOG_PATH}")
    print(f"출력 로그: {OUTPUT_LOG_PATH}")
    
    # 각 인스턴스 ID 별로 최신 상태와 이전 상태를 저장
    latest_states = {}
    last_summary_time = time.monotonic()

    try:
        for line in tail_file(INSTANCE_LOG_PATH):
            try:
                hb = json.loads(line)
                if hb.get('type') != 'instance_heartbeat':
                    continue
                
                inst_id = hb.get('instance', {}).get('instance_id')
                if not inst_id:
                    continue
                
                # 경고 검사 (이전 상태가 있는 경우에만)
                if inst_id in latest_states:
                    check_for_alerts(inst_id, latest_states[inst_id], hb)

                # 최신 상태 업데이트
                latest_states[inst_id] = hb

            except json.JSONDecodeError:
                continue

            # 주기적으로 전체 인스턴스 상태 요약 로그 기록
            now = time.monotonic()
            if now - last_summary_time > SUMMARY_INTERVAL_SEC:
                summary_data = {}
                for inst_id, state in latest_states.items():
                    summary_data[inst_id] = {
                        "role": state.get('instance', {}).get('role'),
                        "cpu_pct": state.get('runtime', {}).get('cpu_pct'),
                        "mem_rss_mb": state.get('runtime', {}).get('mem_rss_mb'),
                        "health": state.get('health', {}).get('status', 'OK'),
                    }
                
                summary_log = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "source": "instance_monitor",
                    "type": "instance_summary",
                    "instances": summary_data
                }
                write_output_log(summary_log)
                last_summary_time = now

    except KeyboardInterrupt:
        print("\n사용자 요청으로 모니터링을 중지합니다.")
    except Exception as e:
        print(f"\n❌ 치명적 오류 발생: {e}")

if __name__ == "__main__":
    main()
