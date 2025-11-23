#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attack Orchestrator (Slim)
- MTD 상태(mtd_state.json)를 읽어 타겟 IP:PORT를 해석
- 공격 스크립트(.sh)를 일정 시간 동안 실행
- 명령: list / start / stop / stop-all
"""

import argparse
import json
import logging
import os
import pathlib
import random
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from threading import Event, Thread
from typing import Dict, List, Optional, Tuple
import re

# --- 기본 경로 설정 ---
BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_BUS_LOG_PATH = BASE_DIR / "bus" / "bus.log"
DEFAULT_MTD_STATE_PATH = BASE_DIR / "mtd" / "shared_state" / "mtd_state.json"
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
    - DataBuilder는 log_entry["type"] 필드를 기준으로 상태머신/레이블링을 수행하므로,
      반드시 "type" 필드를 채워야 한다.
    - event_type 필드는 호환/디버깅용으로 그대로 유지.
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
        # ✅ DataBuilder가 보는 필드
        "type": event_type,
        # (옵션) 호환용 – 나중에 분석할 때 event_type도 그대로 볼 수 있게 유지
        "event_type": event_type,
        "data": data,
    }

    try:
        with open(BUS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"bus.log 쓰기 실패: {e}", exc_info=True)


def read_mtd_state(mtd_state_file: pathlib.Path) -> Dict:
    """mtd_state.json 읽기 (기본값 방어 포함)"""
    default = {
        "active_rules": [],
        "current_target": None,
        "available_targets": [],
        "decoy_target": None,
        "timestamp": 0.0,
    }
    if not mtd_state_file.is_file():
        logger.warning(f"MTD state file not found: {mtd_state_file}")
        return default

    try:
        with open(mtd_state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        state.setdefault("active_rules", [])
        state.setdefault("current_target", None)
        state.setdefault("available_targets", [])
        state.setdefault("decoy_target", None)
        state.setdefault("timestamp", 0.0)

        # current_target 형식 검증
        ct = state.get("current_target")
        if ct and ":" not in str(ct):
            logger.warning(f"Invalid current_target format: {ct}")
            state["current_target"] = None

        # available_targets: "IP:PORT" 형식만 남김
        state["available_targets"] = [
            t
            for t in state.get("available_targets", [])
            if isinstance(t, str) and ":" in t
        ]
        return state
    except Exception as e:
        logger.error(f"Failed to read MTD state: {e}", exc_info=True)
        return default


def get_ip_from_container_name(container_name_part: str) -> Optional[str]:
    """docker ps + inspect 로 simulator 네트워크 IP 조회"""
    network_name = "simulator"
    try:
        cmd = [
            "docker",
            "ps",
            "--filter",
            f"name={container_name_part}",
            "--filter",
            f"network={network_name}",
            "--format",
            "{{.ID}}",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=10
        )
        container_ids = result.stdout.strip().splitlines()
        if not container_ids:
            logger.warning(
                f"No container for name={container_name_part} in network={network_name}"
            )
            return None

        container_id = container_ids[0]
        cmd_inspect = [
            "docker",
            "inspect",
            "-f",
            f"{{{{json .NetworkSettings.Networks.{network_name}.IPAddress}}}}",
            container_id,
        ]
        result_inspect = subprocess.run(
            cmd_inspect, capture_output=True, text=True, check=True, timeout=10
        )
        ip = json.loads(result_inspect.stdout.strip())
        if ip:
            return ip
        return None
    except Exception as e:
        logger.error(f"get_ip_from_container_name error: {e}")
        return None


def resolve_target_address_from_mtd(
    target_name: str, mtd_state: Dict
) -> Optional[Tuple[str, str]]:
    """
    drone / gcs / httpcam 에 대해 IP,PORT 튜플 반환
    - drone: current_target 사용
    - gcs/httpcam: available_targets 포트 기반 + docker fallback
    """
    if target_name == "drone":
        ct = mtd_state.get("current_target")
        if ct and ":" in ct:
            ip, port = ct.split(":", 1)
            return ip, str(int(port))
        logger.warning("MTD current_target is missing or invalid for 'drone'")
        return None

    if target_name in ("gcs", "httpcam"):
        port_map = {"gcs": "5760", "httpcam": "8080"}
        container_map = {
            "gcs": "ground-control-station",
            "httpcam": "companion-computer",
        }
        port = port_map[target_name]
        for t in mtd_state.get("available_targets", []):
            if t.endswith(f":{port}"):
                ip, p = t.split(":", 1)
                return ip, p

        # fallback: docker inspect
        ip = get_ip_from_container_name(container_map[target_name])
        if ip:
            return ip, port
        logger.error(f"Failed to resolve {target_name} (port {port})")
        return None

    logger.warning(f"Unknown target_name: {target_name}")
    return None


# ---------------------------------------------------------------------------
# AttackRunner
# ---------------------------------------------------------------------------

class AttackRunner(Thread):
    """실제 .sh 공격 스크립트를 일정 시간 동안 실행"""

    def __init__(
        self,
        attack_script_path: pathlib.Path,
        duration: int,
        mtd_state_file: pathlib.Path,
        params: Optional[List[str]] = None,
    ):
        super().__init__()
        self.attack_script_path = attack_script_path
        self.duration = duration
        self.mtd_state_file = mtd_state_file
        self.params = params or []
        self.process: Optional[subprocess.Popen] = None
        self._stop_event = Event()

        self.attack_name = attack_script_path.stem
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.return_code: Optional[int] = None
        self.stdout_snippet = ""
        self.stderr_snippet = ""
        self.resolution_failed = False

    def run(self):
        script_path = self.attack_script_path

        if not script_path.is_file():
            logger.error(f"Attack script not found: {script_path}")
            log_to_bus(
                "attack_failed_to_start",
                {
                    "attack_name": self.attack_name,
                    "error": "Script path invalid",
                },
            )
            return

        # --- 스크립트 내용 및 MTD 상태 로드 ---
        try:
            content = script_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to read script {script_path}: {e}")
            content = ""

        mtd_state = read_mtd_state(self.mtd_state_file)
        env = os.environ.copy()
        resolved_targets: Dict[str, str] = {}

        # --- 타겟 이름 추출 ---
        target_names = self.extract_target_names_from_script(content)
        uses_generic = bool(re.search(r"\$\{?TARGET_(IP|PORT)\}?", content))

        # 1) drone / generic 처리
        need_drone = "drone" in target_names or uses_generic
        if need_drone:
            resolved = resolve_target_address_from_mtd("drone", mtd_state)
            if not resolved:
                self.resolution_failed = True
                logger.critical(
                    f"[{self.attack_name}] drone target required but "
                    f"MTD current_target is missing."
                )
                log_to_bus(
                    "attack_failed_to_start",
                    {
                        "attack_name": self.attack_name,
                        "error": "Missing MTD current_target for drone",
                    },
                )
                return

            ip, port = resolved
            env["TARGET_IP"], env["TARGET_PORT"] = ip, port
            env["TARGET_DRONE_IP"], env["TARGET_DRONE_PORT"] = ip, port
            env.setdefault("TARGET_SERVICE", "DRONE_MAVLINK")
            resolved_targets["drone"] = f"{ip}:{port}"
            if "drone" in target_names:
                target_names.remove("drone")
            logger.info(
                f"[{self.attack_name}] drone resolved: {ip}:{port} "
                f"(TARGET_IP/TARGET_PORT set)"
            )

        # 2) 나머지(gcs/httpcam 등)
        for name in list(target_names):
            resolved = resolve_target_address_from_mtd(name, mtd_state)
            if resolved:
                ip, port = resolved
                env[f"TARGET_{name.upper()}_IP"] = ip
                env[f"TARGET_{name.upper()}_PORT"] = port
                resolved_targets[name] = f"{ip}:{port}"
                logger.info(
                    f"[{self.attack_name}] {name} resolved: {ip}:{port}"
                )
            else:
                self.resolution_failed = True
                logger.error(
                    f"[{self.attack_name}] failed to resolve target '{name}'"
                )

        # 시작 로그
        log_to_bus(
            "attack_started",
            {
                "attack_name": self.attack_name,
                "script": str(script_path),
                "duration_requested": self.duration,
                "params": self.params,
                "resolved_targets": resolved_targets,
                "resolution_failed": self.resolution_failed,
            },
        )

        # --- 공격 실행 ---
        bash_path = "/bin/bash"
        if not os.path.exists(bash_path):
            logger.critical("Bash not found at /bin/bash")
            log_to_bus(
                "attack_failed_to_start",
                {"attack_name": self.attack_name, "error": "bash not found"},
            )
            return

        cmd = [bash_path, str(script_path)] + self.params
        script_cwd = str(script_path.parent)  # 상대경로 문제 방지 핵심 포인트

        logger.info(
            f"[{self.attack_name}] starting: {' '.join(cmd)} (cwd={script_cwd})"
        )

        self.start_time = time.monotonic()
        try:
            self.process = subprocess.Popen(
                cmd,
                env=env,
                cwd=script_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            logger.critical(f"Failed to spawn process: {e}", exc_info=True)
            log_to_bus(
                "attack_failed_to_start",
                {"attack_name": self.attack_name, "error": str(e)},
            )
            return

        # duration 동안 폴링 + stop 이벤트 체크
        try:
            while True:
                if self._stop_event.is_set() and self.process.poll() is None:
                    logger.info(f"[{self.attack_name}] stop requested, terminating...")
                    self.process.terminate()

                rc = self.process.poll()
                if rc is not None:
                    self.return_code = rc
                    break

                elapsed = time.monotonic() - self.start_time
                if elapsed >= self.duration and self.process.poll() is None:
                    logger.info(
                        f"[{self.attack_name}] duration {self.duration}s elapsed. "
                        f"terminating..."
                    )
                    self.process.terminate()

                time.sleep(0.2)

            # 출력 수집
            try:
                stdout, stderr = self.process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"[{self.attack_name}] process stuck after terminate, killing..."
                )
                self.process.kill()
                stdout, stderr = self.process.communicate()

            self.stdout_snippet = (stdout or "")[:400]
            self.stderr_snippet = (stderr or "")[:400]

        finally:
            self.end_time = time.monotonic()
            if self.return_code is None and self.process:
                self.return_code = self.process.poll()

            duration_real = (
                self.end_time - self.start_time if self.start_time else 0.0
            )
            logger.info(
                f"[{self.attack_name}] finished. "
                f"RC={self.return_code}, duration={duration_real:.2f}s"
            )
            if self.return_code not in (0, None):
                logger.warning(
                    f"[{self.attack_name}] stderr snippet:\n{self.stderr_snippet}"
                )

            log_to_bus(
                "attack_stopped",
                {
                    "attack_name": self.attack_name,
                    "script": str(script_path),
                    "duration_actual": round(duration_real, 2),
                    "return_code": self.return_code,
                    "stopped_by_request": self._stop_event.is_set(),
                    "stdout_snippet": self.stdout_snippet,
                    "stderr_snippet": self.stderr_snippet,
                    "resolution_failed_at_start": self.resolution_failed,
                },
            )

    def stop(self):
        self._stop_event.set()

    @staticmethod
    def extract_target_names_from_script(content: str) -> List[str]:
        """
        스크립트 내용에서 TARGET_<NAME>_IP / TARGET_<NAME>_PORT 패턴의 NAME 추출
        - generic $TARGET_IP / $TARGET_PORT 은 별도로 uses_generic 로 판단
        """
        names = set()
        for match in re.findall(
            r"\$\{?TARGET_([A-Z0-9_]+)_(?:IP|PORT)\}?", content
        ):
            # generic IP/PORT는 여기선 걸러냄
            if match in ("IP", "PORT"):
                continue
            names.add(match.lower())
        return list(names)


# ---------------------------------------------------------------------------
# AttackOrchestrator
# ---------------------------------------------------------------------------

class AttackOrchestrator:
    def __init__(
        self,
        mtd_state_file: str,
        attack_core_dir: str,
        attack_wiki_dir: str,
        bus_log_file: str,
    ):
        global BUS_LOG_PATH
        BUS_LOG_PATH = pathlib.Path(bus_log_file).resolve()

        self.mtd_state_file = pathlib.Path(mtd_state_file).resolve()
        self.attack_core_dir = pathlib.Path(attack_core_dir).resolve()
        self.attack_wiki_dir = pathlib.Path(attack_wiki_dir).resolve()

        logger.info("Initializing Attack Orchestrator (Slim)")
        logger.info(f"  MTD State File: {self.mtd_state_file}")
        logger.info(f"  Attack Core Dir: {self.attack_core_dir}")
        logger.info(f"  Attack Wiki Dir: {self.attack_wiki_dir}")
        logger.info(f"  Bus Log File: {BUS_LOG_PATH}")

        self.running_attacks: Dict[str, AttackRunner] = {}

    # --- 스크립트 검색 ---

    def find_attack_script(self, attack_name: str) -> Optional[pathlib.Path]:
        script_name = f"{attack_name}.sh"
        core = self.attack_core_dir / script_name
        wiki = self.attack_wiki_dir / script_name

        if core.is_file():
            return core
        if wiki.is_file():
            return wiki

        logger.error(f"Attack script '{script_name}' not found.")
        return None

    def find_all_attack_scripts(self) -> Dict[str, pathlib.Path]:
        scripts: Dict[str, pathlib.Path] = {}
        for d in (self.attack_core_dir, self.attack_wiki_dir):
            if not d.is_dir():
                continue
            for item in d.iterdir():
                if item.is_file() and item.suffix == ".sh" and not item.name.startswith(
                    "_"
                ):
                    scripts.setdefault(item.stem, item)
        return scripts

    # --- 공격 관리 ---

    def start_attack(
        self, attack_name: str, duration: int, params: Optional[List[str]] = None
    ) -> Optional[AttackRunner]:
        if attack_name in self.running_attacks:
            runner = self.running_attacks[attack_name]
            if runner.is_alive():
                logger.warning(f"Attack '{attack_name}' is already running.")
                return None
            else:
                del self.running_attacks[attack_name]

        script_path = self.find_attack_script(attack_name)
        if not script_path:
            log_to_bus(
                "attack_failed_to_start",
                {"attack_name": attack_name, "error": "Script not found"},
            )
            return None

        runner = AttackRunner(
            script_path,
            duration,
            self.mtd_state_file,
            params=params or [],
        )
        self.running_attacks[attack_name] = runner
        runner.start()
        logger.info(
            f"Attack '{attack_name}' thread started (Thread ID={runner.ident})"
        )
        return runner

    def stop_attack(self, attack_name: str, wait_timeout: int = 5):
        runner = self.running_attacks.get(attack_name)
        if not runner:
            logger.warning(f"No running attack named '{attack_name}'")
            return
        if not runner.is_alive():
            logger.info(f"Attack '{attack_name}' already finished.")
            del self.running_attacks[attack_name]
            return

        logger.info(f"Stopping attack '{attack_name}' ...")
        runner.stop()
        runner.join(timeout=wait_timeout)
        if runner.is_alive():
            logger.warning(f"Attack '{attack_name}' did not stop cleanly.")
        else:
            logger.info(f"Attack '{attack_name}' stopped.")
        del self.running_attacks[attack_name]

    def stop_all_attacks(self):
        names = list(self.running_attacks.keys())
        if not names:
            logger.info("No running attacks to stop.")
            return
        logger.info(f"Stopping all attacks: {names}")
        for name in names:
            self.stop_attack(name)

    def list_attacks(self, show_paths: bool = False):
        scripts = self.find_all_attack_scripts()
        running = {
            name: r for name, r in self.running_attacks.items() if r.is_alive()
        }

        print("\n" + "=" * 20 + " Attack Status " + "=" * 20)
        print(
            f"Timestamp: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
        )
        print(f"MTD State File: {self.mtd_state_file}")
        print("-" * 60)

        print(f"Available Attacks ({len(scripts)}):")
        if scripts:
            for name, path in sorted(scripts.items()):
                src = (
                    "core"
                    if self.attack_core_dir in path.parents
                    else "wiki"
                )
                if show_paths and BASE_DIR in path.parents:
                    rel = path.relative_to(BASE_DIR)
                    print(f"  - {name:<30} ({src}, {rel})")
                else:
                    print(f"  - {name:<30} ({src})")
        else:
            print("  (no scripts)")

        print(f"\nRunning Attacks ({len(running)}):")
        if running:
            for name, r in running.items():
                elapsed = (
                    time.monotonic() - r.start_time
                    if r.start_time
                    else 0.0
                )
                print(
                    f"  - {name:<30} (thread={r.ident}, elapsed={elapsed:.1f}s)"
                )
        else:
            print("  (none)")
        print("=" * 60)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Attack Orchestrator (MTD-driven, slim version)"
    )
    parser.add_argument(
        "--mtd-state-file",
        default=str(DEFAULT_MTD_STATE_PATH),
        help="Path to mtd_state.json",
    )
    parser.add_argument(
        "--attack-core-dir",
        default=str(DEFAULT_ATTACK_CORE_DIR),
        help="Path to modules/attacks",
    )
    parser.add_argument(
        "--attack-wiki-dir",
        default=str(DEFAULT_ATTACK_WIKI_DIR),
        help="Path to modules/attacks_wiki",
    )
    parser.add_argument(
        "--bus-log-file",
        default=str(DEFAULT_BUS_LOG_PATH),
        help="Path to bus log file",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable DEBUG logging"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_list = subparsers.add_parser("list", help="List available/running attacks")
    p_list.add_argument(
        "--show-paths", action="store_true", help="Show script relative paths"
    )

    p_start = subparsers.add_parser(
        "start", help="Start a specific attack (and wait until it finishes)"
    )
    p_start.add_argument("attack_name", help="Attack name (without .sh)")
    p_start.add_argument(
        "-d",
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)",
    )
    p_start.add_argument(
        "-p",
        "--params",
        nargs="*",
        default=[],
        help="Extra params for the attack script",
    )

    p_stop = subparsers.add_parser("stop", help="Stop a running attack")
    p_stop.add_argument("attack_name", help="Attack name to stop")

    subparsers.add_parser("stop-all", help="Stop all running attacks")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    orch = AttackOrchestrator(
        mtd_state_file=args.mtd_state_file,
        attack_core_dir=args.attack_core_dir,
        attack_wiki_dir=args.attack_wiki_dir,
        bus_log_file=args.bus_log_file,
    )

    if args.command == "list":
        orch.list_attacks(show_paths=args.show_paths)
        return 0

    elif args.command == "start":
        runner = orch.start_attack(args.attack_name, args.duration, args.params)
        if not runner:
            return 1

        # 여기서 끝날 때까지 기다리기 때문에
        # "trackers remain..." 경고 안 나옴
        runner.join()
        rc = runner.return_code
        logger.info(
            f"[main] Attack '{args.attack_name}' finished with RC={rc}"
        )
        return 0 if rc == 0 else 1

    elif args.command == "stop":
        orch.stop_attack(args.attack_name)
        orch.list_attacks()
        return 0

    elif args.command == "stop-all":
        orch.stop_all_attacks()
        orch.list_attacks()
        return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt, exiting.")
        sys.exit(130)
