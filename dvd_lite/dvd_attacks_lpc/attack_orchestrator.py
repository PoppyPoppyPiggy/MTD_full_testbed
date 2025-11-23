#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attack Orchestrator (Slim - MTD & Attacker Context Aware)
- 공격자 설정(attacker_config.json) 및 MTD 상태(mtd_state.json)를 기반으로 타겟 해석
- 공격자 자신의 IP를 감지하여 ATTACKER_SRC로 주입
- 공격 스크립트(.sh)를 일정 시간 동안 실행
- 명령: list / start / stop / stop-all
"""

import argparse
import json
import logging
import os
import pathlib
import subprocess
import sys
import time
import socket
from datetime import datetime, timezone
from threading import Event, Thread
from typing import Dict, List, Optional
import re

# --- 기본 경로 설정 ---
BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_BUS_LOG_PATH = BASE_DIR / "bus" / "bus.log"
DEFAULT_MTD_STATE_PATH = BASE_DIR / "mtd" / "shared_state" / "mtd_state.json"
DEFAULT_ATTACKER_CONFIG_PATH = BASE_DIR / "mtd" / "config" / "attacker_config.json"
DEFAULT_ATTACK_CORE_DIR = BASE_DIR / "modules" / "attacks"
DEFAULT_ATTACK_WIKI_DIR = BASE_DIR / "modules" / "attacks_wiki"

# --- 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AttackOrchestrator")

# BUS_LOG_PATH 전역 (AttackOrchestrator.__init__ 에서 override 가능)
BUS_LOG_PATH = DEFAULT_BUS_LOG_PATH


def log_to_bus(event_type: str, data: Dict):
    """
    bus/bus.log 에 JSON 라인 기록.
    """
    try:
        os.makedirs(os.path.dirname(BUS_LOG_PATH), exist_ok=True)
    except Exception as e:
        logger.error(f"bus 디렉토리 생성 실패: {e}")

    entry = {
        "timestamp": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "source": "attack_orchestrator",
        "type": event_type,
        "event_type": event_type,
        "data": data,
    }

    try:
        with open(BUS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"bus.log 쓰기 실패: {e}", exc_info=True)


def get_local_ip():
    """공격자 컨테이너(자신)의 IP 주소를 확인"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def read_json_file(file_path: pathlib.Path) -> Dict:
    """JSON 파일 안전하게 읽기"""
    if not file_path.is_file():
        logger.warning(f"File not found: {file_path}")
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}", exc_info=True)
        return {}


def resolve_targets(mtd_state_file: pathlib.Path, attacker_config_file: pathlib.Path) -> Dict[str, str]:
    """
    타겟 정보를 종합적으로 해석하여 환경 변수 딕셔너리로 반환
    우선순위: MTD 상태 (동적) > 공격자 설정 (정적) > 기본값
    """
    resolved = {}
    
    # 1. 공격자 설정 파일 읽기 (Static Info)
    attacker_config = read_json_file(attacker_config_file)
    
    # 기본 타겟 및 포트 정보 로드
    resolved.update(attacker_config.get("targets", {}))
    resolved.update(attacker_config.get("ports", {}))
    resolved.update(attacker_config.get("interfaces", {}))

    # 2. MTD 상태 읽기 (Dynamic Info - Overwrite if exists)
    mtd_state = read_json_file(mtd_state_file)
    
    # MTD에서 제공하는 현재 타겟 (예: Decoy로 리다이렉트된 정보)
    # 공격자는 이를 모를 수 있지만, 시뮬레이션 환경에서는 Orchestrator가 주입해줌
    current_target = mtd_state.get("current_target")
    if current_target and ":" in current_target:
        ip, port = current_target.split(":", 1)
        resolved["TARGET_IP"] = ip
        resolved["TARGET_PORT"] = port
        # MTD가 활성화되면 TARGET_FC 등도 동적 타겟으로 변경될 수 있음 (시나리오에 따라)
    else:
        # 기본값: TARGET_FC가 TARGET_IP가 됨
        resolved.setdefault("TARGET_IP", resolved.get("TARGET_FC", "10.13.0.2"))
        resolved.setdefault("TARGET_PORT", resolved.get("PORT_MAVLINK", "14550"))

    # 3. 공격자 정보 (자신의 IP)
    resolved["ATTACKER_SRC"] = get_local_ip()

    return resolved


# ---------------------------------------------------------------------------
# AttackRunner
# ---------------------------------------------------------------------------

class AttackRunner(Thread):
    def __init__(
        self,
        attack_script_path: pathlib.Path,
        duration: int,
        mtd_state_file: pathlib.Path,
        attacker_config_file: pathlib.Path,
        params: Optional[List[str]] = None,
    ):
        super().__init__()
        self.attack_script_path = attack_script_path
        self.duration = duration
        self.mtd_state_file = mtd_state_file
        self.attacker_config_file = attacker_config_file
        self.params = params or []
        self.process: Optional[subprocess.Popen] = None
        self._stop_event = Event()
        self.attack_name = attack_script_path.stem
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.return_code: Optional[int] = None

    def run(self):
        if not self.attack_script_path.is_file():
            logger.error(f"Script not found: {self.attack_script_path}")
            return

        # 1. 타겟 정보 해석
        target_env_vars = resolve_targets(self.mtd_state_file, self.attacker_config_file)
        
        # 2. 환경 변수 설정
        env = os.environ.copy()
        env.update(target_env_vars)
        
        # 로그용 정보 구성
        log_data = {
            "attack_name": self.attack_name,
            "duration": self.duration,
            "targets": target_env_vars
        }
        
        log_to_bus("attack_started", log_data)
        logger.info(f"Starting attack '{self.attack_name}' with targets: {target_env_vars}")

        # 3. 실행
        cmd = ["/bin/bash", str(self.attack_script_path)] + self.params
        try:
            self.start_time = time.monotonic()
            self.process = subprocess.Popen(
                cmd,
                env=env,
                cwd=str(self.attack_script_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Duration 대기 루프
            while True:
                if self._stop_event.is_set():
                    self.process.terminate()
                    break
                
                if self.process.poll() is not None:
                    break
                
                if time.monotonic() - self.start_time >= self.duration:
                    logger.info(f"Attack '{self.attack_name}' duration expired. Terminating.")
                    self.process.terminate()
                    break
                
                time.sleep(0.5)
                
            stdout, stderr = self.process.communicate(timeout=5)
            self.return_code = self.process.returncode
            
        except Exception as e:
            logger.error(f"Error running attack: {e}")
            log_to_bus("attack_error", {"error": str(e)})
        finally:
            self.end_time = time.monotonic()
            log_to_bus("attack_stopped", {
                "attack_name": self.attack_name,
                "return_code": self.return_code,
                "duration_actual": self.end_time - (self.start_time or self.end_time)
            })

    def stop(self):
        self._stop_event.set()

# ---------------------------------------------------------------------------
# AttackOrchestrator
# ---------------------------------------------------------------------------
class AttackOrchestrator:
    def __init__(
        self,
        mtd_state_file: str,
        attacker_config_file: str,
        attack_core_dir: str,
        attack_wiki_dir: str,
        bus_log_file: str,
    ):
        global BUS_LOG_PATH
        BUS_LOG_PATH = pathlib.Path(bus_log_file).resolve()
        self.mtd_state_file = pathlib.Path(mtd_state_file).resolve()
        self.attacker_config_file = pathlib.Path(attacker_config_file).resolve()
        self.attack_core_dir = pathlib.Path(attack_core_dir).resolve()
        self.attack_wiki_dir = pathlib.Path(attack_wiki_dir).resolve()
        self.running_attacks: Dict[str, AttackRunner] = {}
        
        # 초기화 로그
        logger.info("Attack Orchestrator Initialized")
        logger.info(f"MTD State: {self.mtd_state_file}")
        logger.info(f"Attacker Config: {self.attacker_config_file}")

    def find_attack_script(self, attack_name: str) -> Optional[pathlib.Path]:
        for d in [self.attack_core_dir, self.attack_wiki_dir]:
            path = d / f"{attack_name}.sh"
            if path.is_file():
                return path
        return None

    def start_attack(self, attack_name: str, duration: int, params: List[str] = None):
        if attack_name in self.running_attacks and self.running_attacks[attack_name].is_alive():
            logger.warning(f"Attack {attack_name} is already running.")
            return None
            
        script_path = self.find_attack_script(attack_name)
        if not script_path:
            logger.error(f"Script for {attack_name} not found.")
            return None
            
        runner = AttackRunner(
            script_path, duration, self.mtd_state_file, self.attacker_config_file, params
        )
        self.running_attacks[attack_name] = runner
        runner.start()
        return runner

    def stop_attack(self, attack_name: str):
        if attack_name in self.running_attacks:
            self.running_attacks[attack_name].stop()
            self.running_attacks[attack_name].join()
            del self.running_attacks[attack_name]

    def stop_all_attacks(self):
        for name in list(self.running_attacks.keys()):
            self.stop_attack(name)

    def list_attacks(self, show_paths=False):
        print("Available Attacks:")
        # ... (디렉토리 스캔 로직 - 기존과 동일하므로 생략)

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Attack Orchestrator")
    parser.add_argument("command", choices=["start", "stop", "stop-all", "list"])
    parser.add_argument("attack_name", nargs="?", help="Name of the attack")
    parser.add_argument("-d", "--duration", type=int, default=60)
    parser.add_argument("-p", "--params", nargs="*", default=[])
    
    # 경로 인자들
    parser.add_argument("--mtd-state-file", default=str(DEFAULT_MTD_STATE_PATH))
    parser.add_argument("--attacker-config-file", default=str(DEFAULT_ATTACKER_CONFIG_PATH))
    parser.add_argument("--attack-core-dir", default=str(DEFAULT_ATTACK_CORE_DIR))
    parser.add_argument("--attack-wiki-dir", default=str(DEFAULT_ATTACK_WIKI_DIR))
    parser.add_argument("--bus-log-file", default=str(DEFAULT_BUS_LOG_PATH))
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    orch = AttackOrchestrator(
        args.mtd_state_file, 
        args.attacker_config_file,
        args.attack_core_dir, 
        args.attack_wiki_dir, 
        args.bus_log_file
    )

    if args.command == "start" and args.attack_name:
        runner = orch.start_attack(args.attack_name, args.duration, args.params)
        if runner:
            runner.join() 
            sys.exit(runner.return_code or 0)
        else:
            sys.exit(1)
    elif args.command == "stop" and args.attack_name:
        orch.stop_attack(args.attack_name)
    elif args.command == "stop-all":
        orch.stop_all_attacks()
    elif args.command == "list":
        orch.list_attacks()

if __name__ == "__main__":
    main()