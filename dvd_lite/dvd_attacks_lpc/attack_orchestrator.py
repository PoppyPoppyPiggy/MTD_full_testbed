import os
import sys
import time
import subprocess
import json
import argparse

# 프로젝트 루트 경로 설정
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
from bus.logger import log_bus_event

# --- 설정 ---
STATE_FILE_PATH = os.path.join(PROJECT_ROOT, 'mtd', 'shared_state', 'mtd_state.json')
ATTACKS_DIR = os.path.join(PROJECT_ROOT, 'modules', 'attacks_wiki')
PROBE_INTERVAL = 5

def get_available_attacks():
    """attacks_wiki 디렉토리에서 실행 가능한 공격 스크립트 목록을 반환합니다."""
    return sorted([f for f in os.listdir(ATTACKS_DIR) if f.endswith('.sh')])

def get_current_target_from_state():
    """MTD 상태 파일에서 현재 타겟을 읽어옵니다."""
    try:
        with open(STATE_FILE_PATH, 'r') as f:
            return json.load(f).get("current_target")
    except Exception:
        return None

def main(attack_script_name):
    """지정된 공격 스크립트로 오케스트레이터를 실행합니다."""
    attack_script_path = os.path.join(ATTACKS_DIR, attack_script_name)
    if not os.path.exists(attack_script_path):
        print(f"에러: 공격 스크립트 '{attack_script_name}'를 찾을 수 없습니다.")
        print("사용 가능한 공격 목록:")
        for script in get_available_attacks():
            print(f" - {script}")
        sys.exit(1)

    print(f"🚀 공격 오케스트레이터 시작 (공격: {attack_script_name})... (Ctrl+C로 종료)")
    log_bus_event('orchestrator_started', {'attack_script': attack_script_name})
    
    current_attack_process = None
    last_known_target = None

    while True:
        active_target = get_current_target_from_state()
        if not active_target:
            print(".. MTD 상태 정보를 기다리는 중 ..")
            time.sleep(PROBE_INTERVAL)
            continue

        if active_target != last_known_target:
            print(f"\n🔥 MTD 변경 감지! 새로운 타겟: {active_target}")
            last_known_target = active_target

            if current_attack_process:
                print(f"✋ 이전 공격 프로세스(PID: {current_attack_process.pid})를 중지합니다.")
                # 프로세스 그룹 전체를 종료하여 자식 프로세스까지 모두 정리
                try:
                    os.killpg(os.getpgid(current_attack_process.pid), subprocess.signal.SIGTERM)
                    current_attack_process.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    os.killpg(os.getpgid(current_attack_process.pid), subprocess.signal.SIGKILL)
                log_bus_event('attack_stopped_by_orchestrator', {'script': attack_script_name})

            print(f"💥 새로운 타겟 {active_target}으로 공격을 시작합니다...")
            # preexec_fn=os.setsid를 사용하여 독립적인 프로세스 그룹 생성
            current_attack_process = subprocess.Popen(
                ['sudo', 'bash', attack_script_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                preexec_fn=os.setsid
            )
            log_bus_event('attack_started_by_orchestrator', {'script': attack_script_name, 'target': active_target})
        
        else:
            print(f"✅ 타겟({active_target}) 변경 없음. 공격 유지...")

        time.sleep(PROBE_INTERVAL)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MTD Aware Attack Orchestrator")
    parser.add_argument("attack_script", nargs='?', default=None, help="실행할 공격 스크립트 이름 (예: attitude-spoofing.sh)")
    args = parser.parse_args()

    if not args.attack_script:
        print("사용법: python3 attack_orchestrator.py <공격_스크립트_이름>")
        print("\n사용 가능한 공격 목록:")
        for script in get_available_attacks():
            print(f" - {script}")
        sys.exit(0)

    try:
        main(args.attack_script)
    except KeyboardInterrupt:
        print("\n👋 공격 오케스트레이터 종료.")
        log_bus_event('orchestrator_stopped', {})