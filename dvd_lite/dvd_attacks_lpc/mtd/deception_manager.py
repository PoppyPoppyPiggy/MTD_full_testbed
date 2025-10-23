#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일명: dvd_lite/mtd/deception_manager.py
# 설명: 기본적인 MTD 제어 로직 (주기적 셔플링) 및 RL 기반 제어기의 기본 클래스

import os
import docker
import subprocess
import time
import json
import random
import signal
import sys
import threading
from typing import List, Dict, Any, Optional, Tuple

# --- 경로 설정 ---
# 이 파일의 위치를 기준으로 상위 디렉토리 경로 계산
LPC_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) # dvd_lite/dvd_attacks_lpc
SHARED_STATE_DIR = os.path.join(LPC_DIR, 'mtd', 'shared_state')
STATE_FILE = os.path.join(SHARED_STATE_DIR, 'mtd_state.json')

# --- 도커 및 네트워크 설정 ---
TARGET_CONTAINER_NAME = "flight-controller-lite"
DECOY_CONTAINER_NAME = "virtual-drone"
NETWORK_NAME = "simulator"
AVAILABLE_PORTS = [14550, 14551, 5760, 5600, 7777, 8888, 9000] # 예시 포트 목록

# --- 로거 설정 ---
# rl_driven_deception_manager 와 동일한 로거 사용 (ImportError 방지 위해 try-except)
sys.path.insert(0, LPC_DIR)
try:
    from bus.logger import log_bus_event
except ImportError:
    print("WARNING: bus.logger를 임포트할 수 없습니다. 이벤트는 stdout으로 출력됩니다.", file=sys.stderr)
    def log_bus_event(type: str, data: dict, source_override: str = "deception_manager"):
        record = {"ts": time.time(), "source": source_override, "type": type, "data": data}
        print(json.dumps(record))

# --- MTD 제어 스크립트 경로 ---
MTD_SCRIPT_PATH = os.path.join(LPC_DIR, 'mtd', 'scripts', 'mtd_nat.sh')

# ==============================================================================
# MTDController Base Class
# ==============================================================================
class MTDController:
    """
    MTD(Moving Target Defense)를 제어하는 기본 클래스.
    - 도커 컨테이너 IP/Port 관리
    - iptables/nftables를 이용한 트래픽 리디렉션 (mtd_nat.sh 사용)
    - 주기적인 엔드포인트 셔플링
    """
    def __init__(self, interval_seconds: int = 30):
        self.interval = interval_seconds
        self.client = None
        self.network = None
        self.target_containers: List[docker.models.containers.Container] = []
        self.decoy_container: Optional[docker.models.containers.Container] = None
        self.current_target: Optional[str] = None # "ip:port" 형식
        self.host_ip: Optional[str] = self._get_host_ip()
        self.stop_event = threading.Event()

    def _get_host_ip(self) -> Optional[str]:
        """호스트의 기본 IP 주소를 가져옵니다."""
        try:
            # 외부 연결을 시도하여 사용되는 IP 확인 (더 안정적인 방법)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            # 위 방법 실패 시 hostname -I 사용 (대체)
            try:
                return subprocess.check_output(['hostname', '-I']).decode('utf-8').strip().split()[0]
            except Exception:
                print("[경고] 호스트 IP 주소를 자동으로 찾을 수 없습니다.", file=sys.stderr)
                return None

    def initialize(self) -> bool:
        """Docker 클라이언트 초기화 및 컨테이너/네트워크 정보 가져오기"""
        print("[초기화] Docker 클라이언트 및 MTD 대상 검색 시작...")
        try:
            self.client = docker.from_env()
            self.network = self.client.networks.get(NETWORK_NAME)
            print(f"  - 네트워크 '{NETWORK_NAME}' 찾음.")

            all_containers = self.client.containers.list(filters={"network": NETWORK_NAME})
            self.target_containers = [c for c in all_containers if TARGET_CONTAINER_NAME in c.name]
            decoys = [c for c in all_containers if DECOY_CONTAINER_NAME in c.name]
            self.decoy_container = decoys[0] if decoys else None

            if not self.target_containers:
                print(f"⛔ 오류: 네트워크 '{NETWORK_NAME}' 내에서 '{TARGET_CONTAINER_NAME}' 이름의 타겟 컨테이너를 찾을 수 없습니다.", file=sys.stderr)
                return False
            if not self.decoy_container:
                print(f"[경고] 네트워크 '{NETWORK_NAME}' 내에서 '{DECOY_CONTAINER_NAME}' 이름의 디코이 컨테이너를 찾을 수 없습니다.", file=sys.stderr)

            print(f"  - 타겟 컨테이너 {len(self.target_containers)}개 찾음: {[c.name for c in self.target_containers]}")
            if self.decoy_container:
                 print(f"  - 디코이 컨테이너 찾음: {self.decoy_container.name}")
            print("✅ Docker 초기화 완료.")
            return True

        except docker.errors.NotFound:
            print(f"⛔ 오류: Docker 네트워크 '{NETWORK_NAME}'를 찾을 수 없습니다. 네트워크가 생성되었는지 확인하세요.", file=sys.stderr)
            return False
        except Exception as e:
            print(f"⛔ Docker 초기화 중 예기치 않은 오류 발생: {e}", file=sys.stderr)
            return False

    def _get_container_ip_port(self, container: docker.models.containers.Container) -> Optional[str]:
        """주어진 컨테이너의 IP 주소와 첫 번째 노출 포트를 반환합니다."""
        try:
            container.reload() # 최신 정보 가져오기
            network_settings = container.attrs.get('NetworkSettings', {})
            networks = network_settings.get('Networks', {})
            if NETWORK_NAME in networks:
                ip_address = networks[NETWORK_NAME].get('IPAddress')
                # 포트는 AVAILABLE_PORTS 목록에서 첫 번째 것을 사용 (실제 서비스 포트와 일치 가정)
                port = AVAILABLE_PORTS[0] if AVAILABLE_PORTS else None
                if ip_address and port:
                    return f"{ip_address}:{port}"
        except Exception as e:
            print(f"[경고] 컨테이너({container.name}) IP/Port 조회 중 오류: {e}", file=sys.stderr)
        return None

    def _get_random_target(self) -> Optional[str]:
        """사용 가능한 타겟 컨테이너 중 하나를 무작위로 선택하여 IP:Port 문자열 반환"""
        if not self.target_containers:
            return None
        
        valid_targets = []
        for container in self.target_containers:
            ip_port = self._get_container_ip_port(container)
            if ip_port:
                valid_targets.append(ip_port)

        if not valid_targets:
            print("[경고] 유효한 타겟 컨테이너 IP:Port를 찾을 수 없습니다.", file=sys.stderr)
            return None
            
        # 현재 타겟과 다른 타겟을 우선 선택
        available = [t for t in valid_targets if t != self.current_target]
        if not available: # 현재 타겟만 유효하거나 모든 타겟이 동일한 경우
             available = valid_targets

        return random.choice(available)

    def _run_mtd_script(self, command: str, new_target: str = "", old_target: str = "") -> bool:
        """mtd_nat.sh 스크립트를 실행합니다."""
        args = [MTD_SCRIPT_PATH, command]
        if new_target:
            args.append(new_target)
        if old_target:
            args.append(old_target)

        print(f"  [MTD 스크립트] 실행: {' '.join(args)}")
        try:
            # 환경 변수는 controller 스크립트에서 설정된 것을 사용한다고 가정
            result = subprocess.run(args, check=True, capture_output=True, text=True)
            # print(f"    - stdout: {result.stdout.strip()}")
            if result.stderr.strip():
                 print(f"    - stderr: {result.stderr.strip()}")
            return True
        except FileNotFoundError:
             print(f"⛔ 오류: MTD 스크립트 '{MTD_SCRIPT_PATH}'를 찾을 수 없습니다.", file=sys.stderr)
             return False
        except subprocess.CalledProcessError as e:
            print(f"❌ MTD 스크립트 실행 오류 (RC: {e.returncode}):", file=sys.stderr)
            print(f"   - 명령어: {' '.join(e.cmd)}", file=sys.stderr)
            print(f"   - stderr: {e.stderr.strip()}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"❌ MTD 스크립트 실행 중 예기치 않은 오류: {e}", file=sys.stderr)
            return False

    def _write_state(self, target: Optional[str]):
        """현재 MTD 타겟 상태를 파일에 기록합니다."""
        os.makedirs(SHARED_STATE_DIR, exist_ok=True)
        state_data = {
            "timestamp": time.time(),
            "current_target": target,
            "available_targets": [self._get_container_ip_port(c) for c in self.target_containers],
            "decoy_target": self._get_container_ip_port(self.decoy_container) if self.decoy_container else None
        }
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            print(f"❌ 상태 파일 쓰기 오류 ({STATE_FILE}): {e}", file=sys.stderr)

    def execute_mtd_shuffle(self):
        """MTD 엔드포인트를 무작위로 변경합니다."""
        old_target = self.current_target
        new_target = self._get_random_target()

        if new_target and new_target != old_target:
            print(f"🔄 MTD 셔플링 실행: {old_target} -> {new_target}")
            if self._run_mtd_script("swap", new_target, old_target or ""):
                self.current_target = new_target
                self._write_state(self.current_target)
                log_bus_event("mtd_switch", {"from": old_target, "to": new_target})
            else:
                print("❌ MTD 셔플링 실패.")
        elif new_target == old_target:
            print("  [정보] 선택된 새 타겟이 현재 타겟과 동일하여 셔플링을 건너<0xEB><0x9C><0x8D>니다.")
        else:
            print("❌ MTD 셔플링 실패: 유효한 새 타겟을 선택할 수 없습니다.")

    def _clear_all_redirections(self):
        """종료 시 모든 MTD 리디렉션 규칙을 정리합니다."""
        print("[정리] 모든 MTD 리디렉션 규칙 정리 시도...")
        # init 명령은 기존 체인을 flush하므로 정리 효과가 있음
        self._run_mtd_script("init")
        self._write_state(None) # 상태 파일 초기화
        log_bus_event("mtd_cleanup", {"action": "cleared_redirections"})

    def get_target_info(self) -> Tuple[Optional[str], Optional[int]]:
        """ 외부에서 현재 타겟 IP/Port를 조회할 수 있는 메소드 """
        if self.current_target and ":" in self.current_target:
            ip, port_str = self.current_target.split(":", 1)
            try:
                return ip, int(port_str)
            except ValueError:
                return None, None
        return None, None

    def run(self):
        """주기적으로 MTD 셔플링을 실행하는 메인 루프 (기본 동작)"""
        if not self.initialize():
            return

        # 초기 설정 (iptables/nftables)
        if not self._run_mtd_script("init"):
             print("❌ MTD 테이블 초기화 실패. 종료합니다.")
             return

        # 초기 셔플링 1회 실행
        self.execute_mtd_shuffle()

        while not self.stop_event.is_set():
            # interval 만큼 대기 (stop_event 감지)
            interrupted = self.stop_event.wait(timeout=self.interval)
            if interrupted: # 종료 신호 수신 시 루프 탈출
                break
            if not self.stop_event.is_set(): # 대기 시간 만료 시 MTD 실행
                self.execute_mtd_shuffle()

        print("\n🛑 기본 MTD Controller를 종료합니다.")
        self._clear_all_redirections()

    def shutdown(self, signum, frame):
        """종료 신호 처리"""
        print(f"[종료] 신호 {signal.Signals(signum).name} 수신. 정리 작업을 시작합니다...")
        if not self.stop_event.is_set():
            self.stop_event.set()
            # 메인 루프가 자연스럽게 종료되도록 잠시 대기
            time.sleep(1)
            # 확실한 정리를 위해 clear 함수 직접 호출 (run 루프 종료 후 실행될 수 있도록)
            # self._clear_all_redirections() # run 루프의 finally 블록에서 처리되므로 중복 호출 불필요


# ==============================================================================
# 기본 실행 로직 (rl_driven_deception_manager.py 와 충돌 방지)
# ==============================================================================
if __name__ == "__main__":
    # 이 파일이 직접 실행될 경우, 기본 주기적 MTD만 수행
    print("--- 기본 MTD Controller (주기적 셔플링) 모드 ---")
    parser = argparse.ArgumentParser(description="Basic MTD Controller (Periodic Shuffle)")
    parser.add_argument('--interval', type=int, default=30, help="MTD 셔플링 주기 (초)")
    args = parser.parse_args()

    controller = MTDController(interval_seconds=args.interval)

    # 종료 신호 핸들러 등록
    signal.signal(signal.SIGINT, controller.shutdown)
    signal.signal(signal.SIGTERM, controller.shutdown)

    controller.run()
