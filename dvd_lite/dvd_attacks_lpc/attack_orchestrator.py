#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 설명: 드론 공격 시뮬레이션을 오케스트레이션하고 MTD 상태 파일을 직접 참조하여 타겟 주소를 동적으로 결정합니다. (targets.yml 의존성 제거)

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import random
# import yaml # YAML 파일 더 이상 사용 안 함
import pathlib
from datetime import datetime, timezone
from threading import Thread, Event
from typing import Dict, List, Optional, Tuple
import re
import signal # [추가] Graceful exit for run-selected loop

# --- 경로 설정 ---
BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_BUS_LOG_PATH = BASE_DIR / 'bus/bus.log'
DEFAULT_MTD_STATE_PATH = BASE_DIR / 'mtd/shared_state/mtd_state.json' # MTD 상태 파일 경로가 중요해짐
DEFAULT_ATTACK_MODULES_DIR = BASE_DIR / 'modules/attacks'
# DEFAULT_TARGETS_FILE 제거

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-7s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("AttackOrchestrator")

BUS_LOG_PATH = pathlib.Path(DEFAULT_BUS_LOG_PATH)

# --- [추가] Global flag for run-selected loop ---
#_run_selected_loop_active = True

# --- Helper Functions ---

def log_to_bus(event_type: str, data: Dict):
    """Logs a structured message to the central bus log file."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "source": "attack_orchestrator",
        "event_type": event_type,
        "data": data
    }
    try:
        # Ensure log directory exists (consider moving to init if frequent writes cause issues)
        BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BUS_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to write to bus log ({BUS_LOG_PATH}): {e}. Check file permissions and path.", file=sys.stderr)

# load_targets 함수 제거

def read_mtd_state(mtd_state_file: pathlib.Path) -> Dict:
    """Reads the current MTD state from the JSON file."""
    default_state = {
        "active_rules": [], "current_target": None, "available_targets": [],
        "decoy_target": None, "timestamp": 0.0
    }
    if not mtd_state_file.is_file():
        logger.warning(f"MTD state file not found: {mtd_state_file}. Returning default empty state.")
        return default_state
    try:
        with open(mtd_state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        logger.debug(f"Read MTD state from {mtd_state_file}: {state}")
        # Validate and set defaults (simplified)
        state.setdefault('active_rules', [])
        state.setdefault('current_target', None)
        state.setdefault('available_targets', [])
        state.setdefault('decoy_target', None)
        state.setdefault('timestamp', 0.0)
        # Basic format check
        if state['current_target'] and ':' not in str(state['current_target']):
            logger.warning(f"Invalid format 'current_target': {state['current_target']}. Setting to None.")
            state['current_target'] = None
        state['available_targets'] = [t for t in state.get('available_targets', []) if isinstance(t, str) and ':' in t]
        return state
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON in MTD state file {mtd_state_file}: {e}. Returning default state.")
        return default_state
    except Exception as e:
        logger.error(f"Error reading MTD state file {mtd_state_file}: {e}. Returning default state.", exc_info=True)
        return default_state

def get_ip_from_container_name(container_name_part: str) -> Optional[str]:
    """Runs docker inspect to find the IP of a container matching the name part in the 'simulator' network."""
    network_name = "simulator"
    try:
        cmd = ["docker", "ps", "--filter", f"name={container_name_part}", "--filter", f"network={network_name}", "--format", "{{.ID}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        container_ids = result.stdout.strip().splitlines()
        if not container_ids:
            logger.warning(f"No running container found with name containing '{container_name_part}' in network '{network_name}'.")
            return None
        if len(container_ids) > 1:
            logger.warning(f"Multiple containers found for name '{container_name_part}'. Using the first one: {container_ids[0]}")
        container_id = container_ids[0]
        cmd_inspect = ["docker", "inspect", "-f", f"{{{{json .NetworkSettings.Networks.{network_name}.IPAddress}}}}", container_id]
        result_inspect = subprocess.run(cmd_inspect, capture_output=True, text=True, check=True, timeout=10)
        ip_address = json.loads(result_inspect.stdout.strip())
        if ip_address:
            logger.debug(f"Found IP {ip_address} for container '{container_name_part}' (ID: {container_id}) in network '{network_name}'.")
            return ip_address
        else:
            logger.warning(f"Could not extract IP address for container {container_id} in network '{network_name}'.")
            return None
    except subprocess.TimeoutExpired as e:
        logger.error(f"Docker command timed out while getting IP for '{container_name_part}': {e}")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running docker command: {' '.join(e.cmd)}\nStderr: {e.stderr}")
        return None
    except FileNotFoundError:
        logger.error("Docker command not found. Is Docker installed and in PATH?")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting container IP for '{container_name_part}': {e}", exc_info=True)
        return None

def resolve_target_address_from_mtd(target_name: str, mtd_state: Dict) -> Optional[Tuple[str, str]]:
    """Resolves IP and port for a target name using mtd_state.json and Docker inspect fallback."""
    logger.debug(f"Attempting to resolve address for target '{target_name}' using MTD state.")
    current_ip, current_port = None, None
    resolution_source = "mtd_state"

    if target_name == 'drone':
        mtd_current = mtd_state.get('current_target')
        if mtd_current and ':' in mtd_current:
            try:
                ip, port_str = mtd_current.split(':', 1)
                current_ip, current_port = ip, str(int(port_str))
                resolution_source = "mtd_state[current_target]"
                logger.info(f"Resolved 'drone' from MTD current: {current_ip}:{current_port}")
            except ValueError:
                logger.error(f"Could not parse MTD 'current_target' for drone: {mtd_current}")
                resolution_source = "mtd_state[current_target]_parse_error"
        else:
            logger.warning("MTD state lacks valid 'current_target' for 'drone'.")
            resolution_source = "mtd_state[current_target]_missing"

    elif target_name in ['gcs', 'httpcam']:
        port_map = {'gcs': "5760", 'httpcam': "8080"}
        container_map = {'gcs': "ground-control-station", 'httpcam': "companion-computer"}
        default_port = port_map[target_name]
        container_name_part = container_map[target_name]
        found_target = None
        for target in mtd_state.get('available_targets', []):
            if target.endswith(f":{default_port}"):
                found_target = target
                break
        if found_target:
            current_ip, current_port = found_target.split(':', 1)
            resolution_source = f"mtd_state[available_targets]:{default_port}"
            logger.info(f"Resolved '{target_name}' from MTD available (port {default_port}): {current_ip}:{current_port}")
        else:
            logger.warning(f"'{target_name}' (port {default_port}) not in mtd_state[available]. Falling back to Docker inspect for '{container_name_part}'.")
            target_ip = get_ip_from_container_name(container_name_part)
            if target_ip:
                current_ip, current_port = target_ip, default_port
                resolution_source = f"docker_inspect({container_name_part})"
                logger.info(f"Resolved '{target_name}' via Docker inspect: {current_ip}:{current_port}")
            else:
                logger.error(f"Failed to resolve '{target_name}' from MTD or Docker.")
                resolution_source = f"failed_{target_name}_resolution"
    else:
        logger.warning(f"Target '{target_name}' resolution logic not implemented. Skipping.")
        resolution_source = "unknown_target_name"

    if not current_ip or not current_port:
        logger.error(f"Failed to resolve IP/Port for '{target_name}'. Last source: {resolution_source}.")
        return None

    resolved_address = (current_ip, current_port)
    logger.info(f"Resolved '{target_name}' final address: {resolved_address} (Source: {resolution_source})")
    return resolved_address

# --- AttackRunner Thread ---

class AttackRunner(Thread):
    def __init__(self, attack_script_path: str, duration: int, mtd_state_file: pathlib.Path, params: Optional[List[str]] = None):
        super().__init__()
        self.attack_script_path = attack_script_path
        self.duration = duration
        self.mtd_state_file = mtd_state_file
        self.params = params if params else []
        self.process: Optional[subprocess.Popen] = None
        self._stop_event = Event()
        self.attack_name = pathlib.Path(attack_script_path).stem
        self.resolved_targets: Dict[str, str] = {}
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.return_code: Optional[int] = None
        self.stdout_log = ""
        self.stderr_log = ""
        self.resolution_failed = False # Track if any target resolution failed

    def run(self):
        script_path = pathlib.Path(self.attack_script_path)
        if not script_path.is_file():
            logger.error(f"Attack script path invalid: {script_path}")
            log_to_bus("attack_failed_to_start", {"attack_name": self.attack_name, "error": "Script path invalid."})
            return

        # --- MTD State Sync & Target Resolution ---
        logger.debug(f"Reading MTD state for {self.attack_name}")
        mtd_state = read_mtd_state(self.mtd_state_file)
        env = os.environ.copy()
        target_names_in_script = self.extract_target_names_from_script()
        resolved_targets_log: Dict[str, str] = {}
        self.resolution_failed = False # Reset flag

        if not mtd_state.get('current_target') and 'drone' in target_names_in_script:
             logger.critical(f"MTD state lacks 'current_target' needed by '{script_path.name}'. Aborting.")
             log_to_bus("attack_failed_to_start", {"attack_name": self.attack_name, "error": "Missing MTD 'current_target'."})
             return

        for target_name in target_names_in_script:
            resolved = resolve_target_address_from_mtd(target_name, mtd_state)
            if resolved:
                ip_var, port_var = f"TARGET_{target_name.upper()}_IP", f"TARGET_{target_name.upper()}_PORT"
                env[ip_var], env[port_var] = resolved[0], resolved[1]
                logger.info(f"Set Env for '{target_name}': {ip_var}={resolved[0]}, {port_var}={resolved[1]}")
                self.resolved_targets[target_name] = f"{resolved[0]}:{resolved[1]}"
                resolved_targets_log[target_name] = self.resolved_targets[target_name]
            else:
                logger.error(f"Failed to resolve '{target_name}' for {script_path.name}. Attack may fail.")
                resolved_targets_log[target_name] = "resolution_failed"
                self.resolution_failed = True # Mark failure

        # Fallback for generic TARGET_IP/PORT using 'drone'
        if 'drone' not in target_names_in_script:
            try:
                content = script_path.read_text(encoding='utf-8', errors='ignore')
                if re.search(r'\$\{?TARGET_(IP|PORT)\}?', content):
                    resolved_default = resolve_target_address_from_mtd('drone', mtd_state)
                    if resolved_default:
                        if 'TARGET_IP' not in env: env['TARGET_IP'] = resolved_default[0]
                        if 'TARGET_PORT' not in env: env['TARGET_PORT'] = resolved_default[1]
                        log_key = "default(mtd_drone)"
                        self.resolved_targets[log_key] = f"{resolved_default[0]}:{resolved_default[1]}"
                        resolved_targets_log[log_key] = self.resolved_targets[log_key]
                        logger.info(f"Set Default Env (via drone MTD): IP={resolved_default[0]}, PORT={resolved_default[1]}")
                    elif not self.resolution_failed: # Only error if specific drone wasn't already marked failed
                        logger.error(f"Script uses generic TARGET_*, fallback via MTD 'drone' failed.")
                        self.resolution_failed = True # Mark potential issue
            except Exception as e:
                logger.error(f"Error reading script {script_path.name} for default targets: {e}")

        log_data_start = {
            "attack_name": self.attack_name, "script": script_path.name,
            "duration_requested": self.duration, "params_provided": self.params,
            "resolved_targets": resolved_targets_log,
            "resolution_failed": self.resolution_failed
        }

        # --- Execute Attack ---
        bash_path = "/bin/bash"
        if not os.path.exists(bash_path):
             logger.critical(f"'{bash_path}' not found.")
             log_to_bus("attack_failed_to_start", {"attack_name": self.attack_name, "error": "Bash not found."})
             return

        command = [bash_path, str(script_path)] + self.params
        logger.info(f"Starting '{self.attack_name}' [Thread:{self.native_id}]: {' '.join(command)}")
        log_to_bus("attack_started", log_data_start)
        self.start_time = time.monotonic()

        try:
            self.process = subprocess.Popen(
                command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1, universal_newlines=True, encoding='utf-8', errors='replace'
            )
            logger.info(f"Launched '{self.attack_name}' (PID: {self.process.pid}). Waiting {self.duration}s...")
            try:
                # Wait for duration, unless stopped early
                self.stdout_log, self.stderr_log = "", ""
                stdout_lines, stderr_lines = [], []
                wait_start = time.monotonic()
                while time.monotonic() - wait_start < self.duration:
                    if self._stop_event.is_set():
                        logger.info(f"Stop event received for '{self.attack_name}' (PID: {self.process.pid}). Terminating early.")
                        self.process.terminate()
                        break
                    try:
                        # Non-blocking check if process finished
                        self.return_code = self.process.poll()
                        if self.return_code is not None:
                             logger.info(f"'{self.attack_name}' (PID: {self.process.pid}) finished early naturally. RC={self.return_code}.")
                             break # Exit wait loop if process finished
                        time.sleep(0.1) # Small sleep to avoid busy-waiting
                    except Exception as poll_err:
                        logger.error(f"Error polling process {self.process.pid}: {poll_err}")
                        break # Exit loop on error
                else:
                    # Loop finished without break (duration expired or stop event)
                    if not self._stop_event.is_set():
                         logger.info(f"Duration ({self.duration}s) ended for '{self.attack_name}' (PID: {self.process.pid}). Terminating...")
                         self.process.terminate()

                # Collect remaining output after terminate/natural exit
                try:
                     stdout_rem, stderr_rem = self.process.communicate(timeout=5) # Wait for streams to close
                     self.stdout_log = "".join(stdout_lines) + stdout_rem
                     self.stderr_log = "".join(stderr_lines) + stderr_rem
                     self.return_code = self.process.returncode
                     logger.info(f"'{self.attack_name}' (PID: {self.process.pid}) communication finished. Final RC={self.return_code}.")
                except subprocess.TimeoutExpired:
                     logger.warning(f"Force killing '{self.attack_name}' (PID: {self.process.pid}) after SIGTERM+communicate timeout.")
                     self.process.kill()
                     stdout_rem, stderr_rem = self.process.communicate() # Should be quick after kill
                     self.stdout_log = "".join(stdout_lines) + stdout_rem
                     self.stderr_log = "".join(stderr_lines) + stderr_rem
                     self.return_code = self.process.returncode # Capture final RC after kill
                     logger.warning(f"'{self.attack_name}' (PID: {self.process.pid}) force killed. Final RC={self.return_code}.")
                except Exception as comm_err:
                     logger.error(f"Error during final communicate for '{self.attack_name}' (PID: {self.process.pid}): {comm_err}", exc_info=True)
                     if self.return_code is None: self.return_code = self.process.poll() # Try polling one last time

            except Exception as run_err: # Catch errors during the main wait/poll loop
                logger.error(f"Error during execution/wait for '{self.attack_name}' (PID: {self.process.pid if self.process else 'N/A'}): {run_err}", exc_info=True)
                if self.process and self.process.poll() is None:
                     logger.warning(f"Attempting to kill runaway process {self.process.pid} due to error.")
                     try: self.process.kill(); self.process.communicate() # Clean up
                     except: pass
                if self.return_code is None: self.return_code = -1 # Indicate error during run

            logger.debug(f"STDOUT ({self.attack_name}):\n{self.stdout_log[:500]}{'...' if len(self.stdout_log) > 500 else ''}")
            logger.debug(f"STDERR ({self.attack_name}):\n{self.stderr_log[:500]}{'...' if len(self.stderr_log) > 500 else ''}")

        except (FileNotFoundError, PermissionError) as e:
            logger.critical(f"Failed to execute command '{' '.join(command)}': {e}")
            log_to_bus("attack_failed_to_start", {"attack_name": self.attack_name, "error": str(e)})
            self.return_code = -1
            return
        except Exception as e:
            logger.error(f"Unexpected error launching '{self.attack_name}': {e}", exc_info=True)
            log_to_bus("attack_failed_to_start", {"attack_name": self.attack_name, "error": f"Launch exception: {e}"})
            self.return_code = -1
            return
        finally:
            self.end_time = time.monotonic()
            actual_duration = self.end_time - self.start_time if self.start_time else 0
            if self.return_code is None: # Should be set, but fallback
                self.return_code = self.process.poll() if self.process else -2
            logger.info(f"'{self.attack_name}' finished. Duration: {actual_duration:.2f}s, RC: {self.return_code}.")
            log_data_end = {
                "attack_name": self.attack_name, "script": script_path.name,
                "duration_actual": round(actual_duration, 2), "return_code": self.return_code,
                "stopped_by_request": self._stop_event.is_set(),
                "stdout_snippet": (self.stdout_log[:500] + ('...' if len(self.stdout_log) > 500 else '')) if self.stdout_log else "",
                "stderr_snippet": (self.stderr_log[:500] + ('...' if len(self.stderr_log) > 500 else '')) if self.stderr_log else "",
                "resolution_failed_at_start": self.resolution_failed # Log if resolution failed earlier
            }
            log_to_bus("attack_stopped", log_data_end)

    def stop(self):
        if not self._stop_event.is_set():
            logger.info(f"Stop signal received for thread: {self.attack_name}")
            self._stop_event.set()
            # Termination logic moved inside run() to handle timing correctly

    def extract_target_names_from_script(self) -> List[str]:
        target_names = set()
        script_path = pathlib.Path(self.attack_script_path)
        if not script_path.is_file(): return []
        try:
            content = script_path.read_text(encoding='utf-8', errors='ignore')
            # Look for TARGET_NAME_IP or TARGET_NAME_PORT patterns
            matches = re.findall(r'\$\{?TARGET(?:_([A-Z0-9_]+))?_(?:IP|PORT)\}?', content)
            found_generic = bool(re.search(r'\$\{?TARGET_(?:IP|PORT)\}?', content))
            for name_part in matches:
                if name_part: target_names.add(name_part.lower())
            # If generic vars found, assume 'drone' is needed implicitly
            if found_generic and 'drone' not in target_names:
                logger.debug(f"Generic $TARGET_IP/PORT found in {self.attack_name}, adding 'drone'.")
                target_names.add('drone')
        except Exception as e:
            logger.error(f"Failed to read/parse script {script_path} for targets: {e}")
        logger.debug(f"Extracted targets from {self.attack_name}: {list(target_names)}")
        return list(target_names)

# --- AttackOrchestrator Class ---

class AttackOrchestrator:
    def __init__(self, mtd_state_file: str = str(DEFAULT_MTD_STATE_PATH),
                 attack_modules_dir: str = str(DEFAULT_ATTACK_MODULES_DIR),
                 bus_log_file: str = str(DEFAULT_BUS_LOG_PATH)):
        global BUS_LOG_PATH
        BUS_LOG_PATH = pathlib.Path(bus_log_file).resolve()
        self.mtd_state_file_abs = pathlib.Path(mtd_state_file).resolve()
        self.attack_modules_dir_abs = pathlib.Path(attack_modules_dir).resolve()
        # Derive wiki path relative to modules dir parent
        modules_dir = self.attack_modules_dir_abs.parent
        self.attack_wiki_dir_abs = (modules_dir / 'attacks_wiki').resolve()

        logger.info("Initializing Attack Orchestrator:")
        logger.info(f"  MTD State File:     {self.mtd_state_file_abs}")
        logger.info(f"  Attack Modules Dir: {self.attack_modules_dir_abs}")
        logger.info(f"  Attack Wiki Dir:    {self.attack_wiki_dir_abs}")
        logger.info(f"  Bus Log File:       {BUS_LOG_PATH}")

        if not self.mtd_state_file_abs.is_file():
            logger.critical(f"CRITICAL: MTD state file '{self.mtd_state_file_abs}' not found!")
        if not self.attack_modules_dir_abs.is_dir():
            logger.warning(f"Primary attack dir not found: {self.attack_modules_dir_abs}")
        if not self.attack_wiki_dir_abs.is_dir():
            logger.warning(f"Wiki attack dir not found: {self.attack_wiki_dir_abs}")

        self.running_attacks: Dict[str, AttackRunner] = {}

    def find_attack_script(self, attack_name: str) -> Optional[pathlib.Path]:
        script_filename = f"{attack_name}.sh"
        path_primary = self.attack_modules_dir_abs / script_filename
        if path_primary.is_file(): return path_primary
        path_wiki = self.attack_wiki_dir_abs / script_filename
        if path_wiki.is_file(): return path_wiki
        logger.error(f"Script '{script_filename}' not found in primary or wiki dirs.")
        return None

    def find_all_attack_scripts(self) -> Dict[str, pathlib.Path]:
        scripts: Dict[str, pathlib.Path] = {}
        for dir_path in [self.attack_modules_dir_abs, self.attack_wiki_dir_abs]:
            if not dir_path.is_dir(): continue
            try:
                for item in dir_path.iterdir():
                    if item.is_file() and item.suffix == '.sh' and not item.name.startswith('_'):
                        name = item.stem
                        if name not in scripts: scripts[name] = item # Primary takes precedence
            except OSError as e:
                logger.error(f"Cannot access attack directory {dir_path}: {e}")
        logger.info(f"Discovered {len(scripts)} available attack scripts.")
        return scripts

    def start_attack(self, attack_name: str, duration: int, params: Optional[List[str]] = None) -> Optional[AttackRunner]:
        self.cleanup_finished_attacks()
        if attack_name in self.running_attacks:
            logger.warning(f"Attack '{attack_name}' already running or tracker exists.")
            return None # Avoid starting duplicates
        attack_script_path_obj = self.find_attack_script(attack_name)
        if not attack_script_path_obj:
            log_to_bus("attack_failed_to_start", {"attack_name": attack_name, "error": "Script not found."})
            return None
        logger.info(f"Initiating '{attack_name}' from '{attack_script_path_obj}' for {duration}s.")
        runner = AttackRunner(str(attack_script_path_obj), duration, self.mtd_state_file_abs, params)
        self.running_attacks[attack_name] = runner
        try:
            runner.start()
            logger.info(f"Attack '{attack_name}' thread ({runner.native_id}) started.")
            return runner
        except RuntimeError as e:
            logger.error(f"Failed to start thread for '{attack_name}': {e}", exc_info=True)
            if attack_name in self.running_attacks: del self.running_attacks[attack_name] # Clean up tracker
            log_to_bus("attack_failed_to_start", {"attack_name": attack_name, "error": f"Thread start failed: {e}"})
            return None

    def stop_attack(self, attack_name: str, wait_timeout: int = 10):
        runner = self.running_attacks.get(attack_name)
        if runner and runner.is_alive():
            logger.info(f"Stopping '{attack_name}' (Thread:{runner.native_id}, PID:{runner.process.pid if runner.process else 'N/A'})...")
            runner.stop()
            runner.join(timeout=wait_timeout)
            if runner.is_alive():
                logger.warning(f"Thread '{attack_name}' ({runner.native_id}) didn't stop gracefully after {wait_timeout}s.")
                # Force kill logic is now inside runner's finally block
            else:
                logger.info(f"Thread '{attack_name}' stopped.")
        elif runner: # Already finished
             logger.info(f"Tracker found for '{attack_name}', but thread already finished.")
        else:
             logger.warning(f"No active runner found for '{attack_name}' to stop.")
        # Always clean up tracker if it exists
        if attack_name in self.running_attacks:
            del self.running_attacks[attack_name]

    def list_attacks(self, show_paths: bool = False):
        self.cleanup_finished_attacks()
        available_scripts = self.find_all_attack_scripts()
        available_names = sorted(list(available_scripts.keys()))
        running_names = sorted([name for name, r in self.running_attacks.items() if r.is_alive()]) # Only list truly running

        print("\n" + "="*20 + " Attack Status " + "="*20)
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
        print(f"MTD State File: {self.mtd_state_file_abs}")
        print("-" * 60) # Adjusted separator length

        print(f"Available Attacks ({len(available_names)}):")
        if available_names:
            for name in available_names:
                script_path = available_scripts[name]
                source_dir = "other"
                try: # Use relative_to for cleaner source check
                    if script_path.is_relative_to(self.attack_modules_dir_abs): source_dir = "primary"
                    elif script_path.is_relative_to(self.attack_wiki_dir_abs): source_dir = "wiki"
                except ValueError: # Fallback for different drives or complex paths
                    if str(script_path).startswith(str(self.attack_modules_dir_abs)): source_dir = "primary"
                    elif str(script_path).startswith(str(self.attack_wiki_dir_abs)): source_dir = "wiki"
                path_str = f" ({script_path.relative_to(BASE_DIR)})" if show_paths and BASE_DIR in script_path.parents else ""
                print(f"  - {name:<35} (Source: {source_dir}){path_str}")
        else:
            print("  (No attack scripts found)")

        print(f"\nRunning Attacks ({len(running_names)}):")
        if running_names:
            for name in running_names:
                pid_info = " (Starting...)"
                runner = self.running_attacks.get(name) # Should exist if in running_names
                if runner and runner.is_alive():
                     elapsed = time.monotonic() - runner.start_time if runner.start_time else 0.0
                     if runner.process and runner.process.poll() is None:
                          pid_info = f" (PID: {runner.process.pid}, Running for {elapsed:.1f}s)"
                     else: # Process might not have started yet or already exited while thread is cleaning up
                          pid_info = f" (Thread: {runner.native_id}, Running for {elapsed:.1f}s, Process state uncertain)"
                print(f"  - {name:<35}{pid_info}")
        else:
            print("  (None currently running)")
        print("=" * 60)

    def cleanup_finished_attacks(self):
        finished_attacks = [name for name, runner in self.running_attacks.items() if not runner.is_alive()]
        if finished_attacks:
            logger.debug(f"Cleaning up finished trackers: {finished_attacks}")
            for name in finished_attacks:
                if name in self.running_attacks: del self.running_attacks[name]

    def stop_all_attacks(self):
        running_names = [name for name, runner in self.running_attacks.items() if runner.is_alive()]
        if not running_names:
            logger.info("No attacks currently running to stop.")
            return
        logger.info(f"Stopping all {len(running_names)} running attacks: {running_names}")
        threads_to_join: List[Tuple[str, AttackRunner]] = []
        for name in running_names:
            runner = self.running_attacks.get(name)
            if runner and runner.is_alive():
                runner.stop()
                threads_to_join.append((name, runner))

        wait_timeout_total = 15
        logger.info(f"Waiting up to {wait_timeout_total}s for {len(threads_to_join)} threads...")
        start_wait = time.monotonic()
        for name, runner in threads_to_join:
            remaining_time = max(0, wait_timeout_total - (time.monotonic() - start_wait))
            runner.join(timeout=remaining_time)
            if not runner.is_alive(): logger.info(f"Thread '{name}' stopped.")
            else: logger.warning(f"Thread '{name}' did not stop gracefully.")
            if name in self.running_attacks: del self.running_attacks[name] # Clean up tracker

        remaining = [name for name, r in self.running_attacks.items() if r.is_alive()]
        if remaining: logger.error(f"{len(remaining)} threads may still be running: {remaining}")
        logger.info("Finished stopping all attacks.")
        self.cleanup_finished_attacks() # Final cleanup

# --- [추가] Signal handler for run-selected loop ---
def _handle_sigint_run_selected(signum, frame):
    global _run_selected_loop_active
    logger.info("\nCtrl+C received. Stopping run-selected loop after current attack finishes...")
    _run_selected_loop_active = False # Signal the loop to stop

# --- Main Execution Logic ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attack Orchestrator (MTD State Driven)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    global_group = parser.add_argument_group('Global Configuration')
    global_group.add_argument("--mtd-state-file", default=str(DEFAULT_MTD_STATE_PATH), help=f"Path to MTD state JSON (default: %(default)s)")
    global_group.add_argument("--attack-modules-dir", default=str(DEFAULT_ATTACK_MODULES_DIR), help=f"Base directory for attacks (default: %(default)s)")
    global_group.add_argument("--bus-log-file", default=str(DEFAULT_BUS_LOG_PATH), help=f"Path to bus log (default: %(default)s)")
    global_group.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logging.")

    subparsers = parser.add_subparsers(dest="command", required=True, title="Available Commands")

    list_parser = subparsers.add_parser("list", help="List available and running attacks.")
    list_parser.add_argument("--show-paths", action="store_true", help="Display script paths.")

    start_parser = subparsers.add_parser("start", help="Start a specific attack.")
    start_parser.add_argument("attack_name", help="Name of the attack script (without .sh).")
    start_parser.add_argument("-d", "--duration", type=int, default=60, metavar='SEC', help="Attack duration (default: 60s).")
    start_parser.add_argument("-p", "--params", nargs='*', default=[], metavar='PARAM', help="Parameters for the attack script.")

    stop_parser = subparsers.add_parser("stop", help="Stop a running attack.")
    stop_parser.add_argument("attack_name", help="Name of the attack to stop.")

    stop_all_parser = subparsers.add_parser("stop-all", help="Stop ALL running attacks.")

    monitor_parser = subparsers.add_parser("monitor", help="Continuously monitor attacks (use list).")
    monitor_parser.add_argument("-i", "--interval", type=int, default=10, metavar='SEC', help="Check interval (default: 10s).")

    run_all_parser = subparsers.add_parser("run-all", help="Run all available attacks sequentially (ONCE).")
    run_all_parser.add_argument("-d", "--duration", type=int, default=30, metavar='SEC', help="Duration per attack (default: 30s).")
    run_all_parser.add_argument("--exclude", nargs='*', default=[], metavar='NAME', help="Attack names to exclude.")
    run_all_parser.add_argument("--shuffle", action="store_true", help="Randomize attack order.")
    run_all_parser.add_argument("--delay", type=int, default=5, metavar='SEC', help="Delay between attacks (default: 5s).")

    # --- [추가] run-selected Subparser ---
    run_selected_parser = subparsers.add_parser("run-selected", help="Run a specific list of attacks repeatedly.")
    run_selected_parser.add_argument("attack_names", nargs='+', help="Names of the attack scripts to run (without .sh).")
    run_selected_parser.add_argument("-d", "--duration", type=int, default=60, metavar='SEC', help="Duration per attack (default: 60s).")
    run_selected_parser.add_argument("--shuffle", action="store_true", help="Randomize attack order within each cycle.")
    run_selected_parser.add_argument("--delay", type=int, default=5, metavar='SEC', help="Delay between attacks (default: 5s).")
    # --- [추가 끝] ---

    args = parser.parse_args()

    # Set logging level
    if args.verbose: logger.setLevel(logging.DEBUG)
    else: logger.setLevel(logging.INFO)

    # Instantiate Orchestrator
    try:
        orchestrator = AttackOrchestrator(
            mtd_state_file=args.mtd_state_file,
            attack_modules_dir=args.attack_modules_dir,
            bus_log_file=args.bus_log_file
        )
    except Exception as init_err:
        logger.critical(f"Failed to initialize AttackOrchestrator: {init_err}", exc_info=True)
        sys.exit(1)

    # Command Handling
    exit_code = 0
    original_sigint_handler = signal.getsignal(signal.SIGINT) # Store original handler

    try:
        if args.command == "list":
            orchestrator.list_attacks(show_paths=args.show_paths)
        elif args.command == "start":
            runner = orchestrator.start_attack(args.attack_name, args.duration, args.params)
            if not runner: exit_code = 1
            # Keep running in background, no list needed here
        elif args.command == "stop":
            orchestrator.stop_attack(args.attack_name)
            time.sleep(0.5); orchestrator.list_attacks() # Show status after stop attempt
        elif args.command == "stop-all":
            orchestrator.stop_all_attacks()
        elif args.command == "monitor":
            logger.info(f"Monitor mode: Listing attacks every {args.interval}s. Press Ctrl+C to exit.")
            while True: orchestrator.list_attacks(); time.sleep(args.interval)
        elif args.command == "run-all":
            # --- (run-all logic remains the same, executing ONCE) ---
            attack_scripts = orchestrator.find_all_attack_scripts()
            attack_names = sorted(list(attack_scripts.keys()))
            if not attack_names: logger.info("No attacks found."); sys.exit(0)
            excluded_attacks = set(args.exclude)
            attacks_to_run = [name for name in attack_names if name not in excluded_attacks]
            if not attacks_to_run: logger.info("All available attacks excluded."); sys.exit(0)
            if excluded_attacks: logger.info(f"Excluding: {', '.join(sorted(list(excluded_attacks)))}")
            if args.shuffle: logger.info("Shuffling order."); random.shuffle(attacks_to_run)
            total_attacks = len(attacks_to_run)
            logger.info(f"Starting sequential run of {total_attacks} attack(s) ONCE... (Dur={args.duration}s, Delay={args.delay}s)")
            run_results = {}
            for i, attack_name in enumerate(attacks_to_run, 1):
                logger.info("\n" + f"--- [{i}/{total_attacks}] Starting Attack: {attack_name} ---")
                runner_thread = orchestrator.start_attack(attack_name, args.duration, params=None)
                if runner_thread:
                    wait_join_timeout = args.duration + 15 # Allow extra time for shutdown
                    runner_thread.join(timeout=wait_join_timeout)
                    if runner_thread.is_alive():
                        logger.warning(f"'{attack_name}' timed out after {wait_join_timeout}s. Stopping forcibly...")
                        orchestrator.stop_attack(attack_name, 5) # Force stop
                        run_results[attack_name] = "TIMEOUT_FORCED_STOP"
                    else:
                        rc = runner_thread.return_code
                        logger.info(f"'{attack_name}' completed (RC: {rc}).")
                        run_results[attack_name] = rc
                        if rc != 0: exit_code = 1 # Mark failure on non-zero RC
                else:
                    logger.error(f"Skipping wait for '{attack_name}' (failed to start).")
                    run_results[attack_name] = "FAILED_TO_START"
                    exit_code = 1 # Mark failure
                if i < total_attacks and args.delay > 0:
                    logger.info(f"Waiting {args.delay}s...")
                    time.sleep(args.delay)
            logger.info("\n" + "--- Finished Sequential Attack Run ---"); logger.info("Summary:")
            max_len = max((len(name) for name in run_results.keys()), default=10)
            for name, result in run_results.items(): logger.info(f"  - {name:<{max_len}} : {result}")

        # --- [추가] run-selected Logic ---
        elif args.command == "run-selected":
            available_scripts = orchestrator.find_all_attack_scripts()
            selected_attacks = []
            invalid_attacks = []
            for name in args.attack_names:
                if name in available_scripts:
                    selected_attacks.append(name)
                else:
                    invalid_attacks.append(name)

            if invalid_attacks:
                logger.error(f"Invalid attack names provided: {', '.join(invalid_attacks)}")
            if not selected_attacks:
                logger.error("No valid attacks selected to run.")
                sys.exit(1)

            logger.info(f"Starting REPEATED run for selected attacks: {', '.join(selected_attacks)}")
            logger.info(f"Duration per attack: {args.duration}s, Delay between attacks: {args.delay}s")
            if args.shuffle: logger.info("Shuffling order within each cycle.")
            logger.info("Press Ctrl+C to stop the loop gracefully after the current attack finishes.")

            # Setup signal handler for graceful exit
            signal.signal(signal.SIGINT, _handle_sigint_run_selected)
            global _run_selected_loop_active
            _run_selected_loop_active = True
            cycle_count = 0

            while _run_selected_loop_active:
                cycle_count += 1
                logger.info(f"\n=== Starting Cycle {cycle_count} ===")
                current_run_order = selected_attacks[:] # Copy the list
                if args.shuffle:
                    random.shuffle(current_run_order)
                    logger.info(f"Cycle {cycle_count} order: {', '.join(current_run_order)}")

                for i, attack_name in enumerate(current_run_order, 1):
                    if not _run_selected_loop_active: break # Check flag before starting next attack

                    logger.info(f"--- [Cycle {cycle_count}, {i}/{len(current_run_order)}] Starting: {attack_name} ---")
                    runner_thread = orchestrator.start_attack(attack_name, args.duration, params=None)

                    if runner_thread:
                        # Wait for the attack duration + grace period
                        # We don't use join here because we need the loop to check _run_selected_loop_active
                        wait_start_time = time.monotonic()
                        wait_join_timeout = args.duration + 15 # Timeout slightly longer than duration
                        while runner_thread.is_alive() and time.monotonic() - wait_start_time < wait_join_timeout:
                             if not _run_selected_loop_active:
                                  # If Ctrl+C was pressed during the attack, signal the runner to stop
                                  logger.info(f"Stopping current attack '{attack_name}' due to loop exit request...")
                                  orchestrator.stop_attack(attack_name, 5) # Request stop and wait briefly
                                  break # Exit inner wait loop
                             time.sleep(0.2) # Check periodically

                        # If loop finished and thread is still alive (timed out or wasn't stopped by Ctrl+C handler)
                        if runner_thread.is_alive():
                            logger.warning(f"'{attack_name}' might have timed out or failed to stop. Forcibly stopping...")
                            orchestrator.stop_attack(attack_name, 5) # Force stop attempt

                        # Log completion regardless of how it stopped
                        rc = runner_thread.return_code if hasattr(runner_thread, 'return_code') else 'N/A'
                        logger.info(f"--- Attack '{attack_name}' finished (RC: {rc}) ---")

                    else:
                        logger.error(f"Failed to start '{attack_name}' in cycle {cycle_count}.")
                        # Optionally add a delay even if start fails
                        # time.sleep(args.delay)

                    # Delay before next attack, but only if the loop should continue
                    if _run_selected_loop_active and i < len(current_run_order) and args.delay > 0:
                         logger.info(f"Waiting {args.delay}s...")
                         # Use time.sleep but check flag periodically for faster exit on Ctrl+C
                         delay_start = time.monotonic()
                         while time.monotonic() - delay_start < args.delay:
                              if not _run_selected_loop_active: break
                              time.sleep(min(0.5, args.delay - (time.monotonic() - delay_start)))


                if not _run_selected_loop_active:
                     logger.info("Loop exit requested. Finishing.")
                     break # Exit the main while loop
                else:
                     logger.info(f"=== Completed Cycle {cycle_count}. ===")
                     # Optional extra delay between full cycles?
                     # time.sleep(30)


    except KeyboardInterrupt:
        # This will now primarily catch Ctrl+C if it happens outside the run-selected loop
        # or if the signal handler in run-selected fails for some reason.
        logger.info("\nKeyboardInterrupt received. Stopping all running attacks...")
        orchestrator.stop_all_attacks()
        exit_code = 130
    except Exception as e:
        logger.critical(f"Unexpected critical error: {e}", exc_info=True)
        logger.info("Attempting to stop all attacks...")
        orchestrator.stop_all_attacks()
        exit_code = 1
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_sigint_handler)
        orchestrator.cleanup_finished_attacks() # Final cleanup
        if orchestrator.running_attacks:
            logger.warning(f"Orchestrator exiting, but trackers remain for: {list(orchestrator.running_attacks.keys())}. Processes might be orphaned.")
        logger.info("Attack Orchestrator finished.")
        sys.exit(exit_code)