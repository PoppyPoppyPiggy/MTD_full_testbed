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

# --- 경로 설정 ---
BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_BUS_LOG_PATH = BASE_DIR / 'bus.log'
DEFAULT_MTD_STATE_PATH = BASE_DIR / 'mtd/shared_state/mtd_state.json' # MTD 상태 파일 경로가 중요해짐
DEFAULT_ATTACK_MODULES_DIR = BASE_DIR / 'modules/attacks'
# DEFAULT_TARGETS_FILE 제거

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-7s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("AttackOrchestrator")

BUS_LOG_PATH = pathlib.Path(DEFAULT_BUS_LOG_PATH)

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
        with open(BUS_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to write to bus log ({BUS_LOG_PATH}): {e}. Check file permissions and path.", file=sys.stderr)

# load_targets 함수 제거

def read_mtd_state(mtd_state_file: pathlib.Path) -> Dict:
    """Reads the current MTD state from the JSON file."""
    # 기본 상태 구조 정의 (current_target과 available_targets 포함)
    default_state = {
        "active_rules": [],
        "current_target": None,
        "available_targets": [], # 사용 가능한 모든 타겟 목록 (ip:port 형식)
        "decoy_target": None,
        "timestamp": 0.0
    }

    if not mtd_state_file.is_file():
        logger.warning(f"MTD state file not found: {mtd_state_file}. Returning default empty state.")
        return default_state

    try:
        with open(mtd_state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
            logger.debug(f"Read MTD state from {mtd_state_file}: {state}")

            # 필수 키 확인 및 기본값 설정
            if 'active_rules' not in state or not isinstance(state.get('active_rules'), list):
                # logger.warning(f"MTD state file {mtd_state_file} missing or invalid 'active_rules'. Correcting to empty list.")
                state['active_rules'] = []
            if 'current_target' not in state:
                # logger.debug(f"MTD state file {mtd_state_file} missing 'current_target'. Setting to None.")
                state['current_target'] = None
            if 'available_targets' not in state or not isinstance(state.get('available_targets'), list):
                 # logger.warning(f"MTD state file {mtd_state_file} missing or invalid 'available_targets'. Correcting to empty list.")
                 state['available_targets'] = []
            if 'decoy_target' not in state:
                 state['decoy_target'] = None
            if 'timestamp' not in state:
                 state['timestamp'] = 0.0


            # current_target 형식 검증 (ip:port)
            if state['current_target'] and ':' not in state['current_target']:
                 logger.warning(f"Invalid format for 'current_target' in MTD state: {state['current_target']}. Expected 'ip:port'. Setting to None.")
                 state['current_target'] = None

            # available_targets 형식 검증 (list of "ip:port")
            valid_available = []
            for target in state.get('available_targets', []):
                if isinstance(target, str) and ':' in target:
                    valid_available.append(target)
                else:
                    logger.warning(f"Ignoring invalid entry in 'available_targets': {target}")
            state['available_targets'] = valid_available


            return state
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON in MTD state file {mtd_state_file}: {e}. Returning default state.")
        return default_state
    except Exception as e:
        logger.error(f"Error reading MTD state file {mtd_state_file}: {e}. Returning default state.", exc_info=True)
        return default_state

def get_ip_from_container_name(container_name_part: str) -> Optional[str]:
    """Runs docker inspect to find the IP of a container matching the name part in the 'simulator' network."""
    network_name = "simulator" # TODO: Make this configurable if needed
    try:
        # 필터링하여 정확한 컨테이너 찾기 시도
        cmd = [
            "docker", "ps",
            "--filter", f"name={container_name_part}",
            "--filter", f"network={network_name}",
            "--format", "{{.ID}}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        container_ids = result.stdout.strip().splitlines()

        if not container_ids:
            logger.warning(f"No running container found with name containing '{container_name_part}' in network '{network_name}'.")
            return None
        if len(container_ids) > 1:
            logger.warning(f"Multiple containers found for name '{container_name_part}'. Using the first one: {container_ids[0]}")

        container_id = container_ids[0]

        # 찾은 ID로 IP 주소 가져오기
        cmd_inspect = [
            "docker", "inspect",
            "-f", f"{{{{json .NetworkSettings.Networks.{network_name}.IPAddress}}}}",
            container_id
        ]
        result_inspect = subprocess.run(cmd_inspect, capture_output=True, text=True, check=True)
        ip_address = json.loads(result_inspect.stdout.strip())

        if ip_address:
            logger.debug(f"Found IP {ip_address} for container '{container_name_part}' (ID: {container_id}) in network '{network_name}'.")
            return ip_address
        else:
            logger.warning(f"Could not extract IP address for container {container_id} in network '{network_name}'.")
            return None

    except subprocess.CalledProcessError as e:
        logger.error(f"Error running docker command: {e.cmd}")
        logger.error(f"Stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        logger.error("Docker command not found. Is Docker installed and in PATH?")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting container IP for '{container_name_part}': {e}", exc_info=True)
        return None


def resolve_target_address_from_mtd(target_name: str, mtd_state: Dict) -> Optional[Tuple[str, str]]:
    """
    Resolves IP and port for a target name primarily using mtd_state.json.
    - 'drone' uses mtd_state['current_target'].
    - Others ('gcs', 'httpcam') try to find matching IP in mtd_state['available_targets']
      or fall back to docker inspect based on naming convention.
    Returns (ip, port) or None if resolution fails.
    """
    logger.debug(f"Attempting to resolve address for target '{target_name}' using MTD state.")
    current_ip = None
    current_port = None
    resolution_source = "mtd_state"

    if target_name == 'drone':
        mtd_current = mtd_state.get('current_target')
        if mtd_current and ':' in mtd_current:
            try:
                ip, port_str = mtd_current.split(':', 1)
                current_ip = ip
                current_port = str(int(port_str)) # Validate port is numeric and convert back to string
                resolution_source = "mtd_state[current_target]"
                logger.info(f"Resolved 'drone' target from MTD current_target: {current_ip}:{current_port}")
            except ValueError:
                logger.error(f"Could not parse IP/Port from MTD 'current_target' for drone: {mtd_current}")
                resolution_source = "mtd_state[current_target]_parse_error"
        else:
            logger.warning(f"MTD state does not have a valid 'current_target' for 'drone'.")
            resolution_source = "mtd_state[current_target]_missing"

    elif target_name == 'gcs':
        # Try finding in available_targets (assuming GCS uses a specific port like 5760)
        gcs_port = "5760" # Default GCS port assumption
        found_gcs = None
        for target in mtd_state.get('available_targets', []):
             if target.endswith(f":{gcs_port}"):
                  found_gcs = target
                  break
        if found_gcs:
            current_ip, current_port = found_gcs.split(':', 1)
            resolution_source = f"mtd_state[available_targets]:{gcs_port}"
            logger.info(f"Resolved 'gcs' target from MTD available_targets (port {gcs_port}): {current_ip}:{current_port}")
        else:
            # Fallback to docker inspect using container name convention
            logger.warning(f"GCS (port {gcs_port}) not found in mtd_state[available_targets]. Falling back to Docker inspect for 'ground-control-station'.")
            container_name_part = "ground-control-station" # Assumed name part
            gcs_ip = get_ip_from_container_name(container_name_part)
            if gcs_ip:
                 current_ip = gcs_ip
                 current_port = gcs_port # Use assumed port
                 resolution_source = f"docker_inspect({container_name_part})"
                 logger.info(f"Resolved 'gcs' target via Docker inspect: {current_ip}:{current_port}")
            else:
                 logger.error(f"Failed to resolve 'gcs' target from MTD state or Docker inspect.")
                 resolution_source = "failed_gcs_resolution"

    elif target_name == 'httpcam':
        # Try finding in available_targets (assuming httpcam uses port 8080)
        http_port = "8080" # Default httpcam port assumption
        found_http = None
        for target in mtd_state.get('available_targets', []):
             if target.endswith(f":{http_port}"):
                  found_http = target
                  break
        if found_http:
            current_ip, current_port = found_http.split(':', 1)
            resolution_source = f"mtd_state[available_targets]:{http_port}"
            logger.info(f"Resolved 'httpcam' target from MTD available_targets (port {http_port}): {current_ip}:{current_port}")
        else:
             # Fallback to docker inspect using container name convention
            logger.warning(f"HTTP Cam (port {http_port}) not found in mtd_state[available_targets]. Falling back to Docker inspect for 'companion-computer'.")
            container_name_part = "companion-computer" # Assumed name part hosting the camera feed
            cam_ip = get_ip_from_container_name(container_name_part)
            if cam_ip:
                 current_ip = cam_ip
                 current_port = http_port # Use assumed port
                 resolution_source = f"docker_inspect({container_name_part})"
                 logger.info(f"Resolved 'httpcam' target via Docker inspect: {current_ip}:{current_port}")
            else:
                 logger.error(f"Failed to resolve 'httpcam' target from MTD state or Docker inspect.")
                 resolution_source = "failed_httpcam_resolution"

    else:
        # Handle other potential targets if needed, perhaps defaulting to drone or failing
        logger.warning(f"Target '{target_name}' is not 'drone', 'gcs', or 'httpcam'. Resolution logic not implemented. Skipping.")
        resolution_source = "unknown_target_name"


    # Final check
    if not current_ip or not current_port:
        logger.error(f"Failed to resolve a valid IP/Port for target '{target_name}'. Last source attempt: {resolution_source}.")
        return None

    resolved_address = (current_ip, current_port)
    logger.info(f"Resolved target '{target_name}' final address: {resolved_address} (Source: {resolution_source})")
    return resolved_address


# --- AttackRunner Thread ---

class AttackRunner(Thread):
    # targets_config removed from constructor
    def __init__(self, attack_script_path: str, duration: int, mtd_state_file: pathlib.Path, params: Optional[List[str]] = None):
        super().__init__()
        self.attack_script_path = attack_script_path
        self.duration = duration
        # self.targets_config = None # No longer needed
        self.mtd_state_file = mtd_state_file # Store the Path object
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

    def run(self):
        """Executes the attack script using MTD state for target resolution."""
        script_path = pathlib.Path(self.attack_script_path)
        if not script_path.is_file():
             logger.error(f"Attack script path does not exist or is not a file: {script_path}")
             log_to_bus("attack_failed_to_start", {
                 "attack_name": self.attack_name, "script": str(script_path), "error": "Script path not found or invalid."
             })
             return

        can_execute = os.access(script_path, os.X_OK)
        if not can_execute:
             logger.warning(f"Attack script is not marked executable: {script_path}. Execution will proceed via '/bin/bash'.")

        # --- MTD State Synchronization ---
        logger.debug(f"Reading MTD state from {self.mtd_state_file} before starting {self.attack_name}")
        mtd_state = read_mtd_state(self.mtd_state_file)

        # --- Target Resolution and Environment Variable Setup ---
        env = os.environ.copy()
        # Extract target names needed by the script
        target_names_in_script = self.extract_target_names_from_script()
        resolved_targets_log: Dict[str, str] = {}
        resolution_successful = True # Flag to track if all needed targets were resolved

        log_data_start = {
            "attack_name": self.attack_name,
            "script": script_path.name,
            "duration_requested": self.duration,
            "params_provided": self.params,
            "resolved_targets": resolved_targets_log
        }

        # Check if MTD state has at least a current_target (essential for 'drone')
        if not mtd_state.get('current_target') and 'drone' in target_names_in_script:
             logger.critical(f"CRITICAL: MTD state file {self.mtd_state_file} is missing 'current_target', which is required by script '{script_path.name}'. Attack cannot start.")
             log_to_bus("attack_failed_to_start", {
                "attack_name": self.attack_name, "script": script_path.name,
                "error": "Required 'drone' target cannot be resolved due to missing 'current_target' in MTD state."
             })
             return # Cannot proceed without drone target if needed

        # Resolve targets based on MTD state
        for target_name in target_names_in_script:
            # Use the new resolution function
            resolved = resolve_target_address_from_mtd(target_name, mtd_state)
            if resolved:
                ip_var = f"TARGET_{target_name.upper()}_IP"
                port_var = f"TARGET_{target_name.upper()}_PORT"
                env[ip_var] = resolved[0]
                env[port_var] = resolved[1]
                logger.info(f"Setting Env for '{target_name}': {ip_var}={resolved[0]}, {port_var}={resolved[1]}")
                self.resolved_targets[target_name] = f"{resolved[0]}:{resolved[1]}"
                resolved_targets_log[target_name] = self.resolved_targets[target_name]
            else:
                logger.error(f"Failed to resolve target '{target_name}' using MTD state for script {script_path.name}. Attack might fail.")
                resolved_targets_log[target_name] = "resolution_failed"
                resolution_successful = False
                # Decide whether to abort if resolution fails. For now, we continue.
                # if target_name == 'drone': # If drone is essential and failed...
                #     log_to_bus(...) return

        # Resolve generic TARGET_IP/PORT using 'drone' target from MTD state
        if 'drone' not in target_names_in_script: # Only if not explicitly handled
             try:
                 content = script_path.read_text(encoding='utf-8', errors='ignore')
                 if re.search(r'\$\{?TARGET_(IP|PORT)\}?', content):
                     logger.debug(f"Script {script_path.name} uses generic TARGET_IP/PORT. Attempting fallback resolution for 'drone' using MTD state.")
                     resolved_default = resolve_target_address_from_mtd('drone', mtd_state)
                     if resolved_default:
                         if 'TARGET_IP' not in env:
                             env['TARGET_IP'] = resolved_default[0]
                             logger.info(f"Setting Default Env (via drone MTD): TARGET_IP={resolved_default[0]}")
                         if 'TARGET_PORT' not in env:
                             env['TARGET_PORT'] = resolved_default[1]
                             logger.info(f"Setting Default Env (via drone MTD): TARGET_PORT={resolved_default[1]}")
                         log_key = "default_target(mtd_drone_fallback)"
                         self.resolved_targets[log_key] = f"{resolved_default[0]}:{resolved_default[1]}"
                         resolved_targets_log[log_key] = self.resolved_targets[log_key]
                     else:
                          logger.error(f"Script {script_path.name} uses generic TARGET_IP/PORT, but fallback resolution for 'drone' via MTD state failed.")
                          # This could be critical if the script relies on these generic vars
                          resolution_successful = False # Mark as potentially problematic
             except Exception as e:
                 logger.error(f"Error reading script content {script_path.name} for default targets: {e}")


        # --- Execute Attack ---
        bash_path = "/bin/bash"
        if not os.path.exists(bash_path):
             # ... (bash check as before) ...
            logger.critical(f"CRITICAL: '{bash_path}' not found...")
            log_to_bus("attack_failed_to_start", {
                "attack_name": self.attack_name, "script": script_path.name,
                "error": f"'{bash_path}' interpreter not found."
            })
            return

        command = [bash_path, str(script_path)] + self.params
        logger.info(f"Starting attack '{self.attack_name}' [PID:{os.getpid()}-{self.native_id}]: {' '.join(command)}")

        log_to_bus("attack_started", log_data_start)
        self.start_time = time.monotonic()

        # --- Popen and Communicate logic (largely unchanged from previous version) ---
        try:
            self.process = subprocess.Popen(
                command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1, universal_newlines=True, encoding='utf-8', errors='replace'
            )
            logger.info(f"Attack '{self.attack_name}' process launched (PID: {self.process.pid}). Waiting for {self.duration}s...")

            try:
                self.stdout_log, self.stderr_log = self.process.communicate(timeout=self.duration)
                self.return_code = self.process.returncode
                logger.info(f"Attack process '{self.attack_name}' (PID: {self.process.pid}) finished naturally. RC={self.return_code}.")
            except subprocess.TimeoutExpired:
                logger.info(f"Duration ({self.duration}s) ended for '{self.attack_name}' (PID: {self.process.pid}). Terminating...")
                self.process.terminate()
                try:
                    stdout_rem, stderr_rem = self.process.communicate(timeout=5)
                    self.stdout_log += stdout_rem
                    self.stderr_log += stderr_rem
                    self.return_code = self.process.returncode
                    logger.info(f"Attack '{self.attack_name}' (PID: {self.process.pid}) terminated gracefully. RC={self.return_code}.")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing '{self.attack_name}' (PID: {self.process.pid}) after SIGTERM timeout.")
                    self.process.kill()
                    stdout_rem, stderr_rem = self.process.communicate()
                    self.stdout_log += stdout_rem
                    self.stderr_log += stderr_rem
                    self.return_code = self.process.returncode
                    logger.warning(f"Attack '{self.attack_name}' (PID: {self.process.pid}) force killed. RC={self.return_code}.")
            except Exception as comm_err:
                 # ... (error handling during communicate) ...
                 logger.error(f"Error communicating with process for '{self.attack_name}' ...", exc_info=True)
                 # ...

            logger.debug(f"Attack {self.attack_name} STDOUT snippet:\n{self.stdout_log[:500]}{'...' if len(self.stdout_log) > 500 else ''}")
            logger.debug(f"Attack {self.attack_name} STDERR snippet:\n{self.stderr_log[:500]}{'...' if len(self.stderr_log) > 500 else ''}")

        except FileNotFoundError as e:
            # ... (error handling for Popen) ...
            logger.critical(f"CRITICAL: Failed to execute command '{' '.join(command)}': {e}")
            # ...
            return # Ensure return here
        except PermissionError as e:
            # ... (error handling for Popen) ...
            logger.critical(f"CRITICAL: Permission denied executing command '{' '.join(command)}': {e}")
            # ...
            return # Ensure return here
        except Exception as e:
            # ... (general error handling during execution) ...
            logger.error(f"Unexpected error during attack execution '{self.attack_name}': {e}", exc_info=True)
            # ...

        finally:
            self.end_time = time.monotonic()
            actual_duration = self.end_time - self.start_time if self.start_time else 0
            if self.return_code is None:
                 self.return_code = self.process.poll() if self.process else -2

            logger.info(f"Attack '{self.attack_name}' finished. Duration: {actual_duration:.2f}s, Return Code: {self.return_code}.")
            log_data_end = {
                "attack_name": self.attack_name, "script": script_path.name,
                "duration_actual": round(actual_duration, 2), "return_code": self.return_code,
                "stopped_by_request": self._stop_event.is_set(),
                "stdout_snippet": self.stdout_log[:500] + ('...' if len(self.stdout_log) > 500 else '') if self.stdout_log else "",
                "stderr_snippet": self.stderr_log[:500] + ('...' if len(self.stderr_log) > 500 else '') if self.stderr_log else ""
            }
            log_to_bus("attack_stopped", log_data_end)


    def stop(self):
        # ... (stop method remains the same) ...
        """Signals the attack thread and its subprocess to stop."""
        if not self._stop_event.is_set():
            logger.info(f"Stop signal received for attack thread: {self.attack_name}")
            self._stop_event.set() # Signal the thread's wait loop to exit

            # Additionally, try to terminate the subprocess directly
            if self.process and self.process.poll() is None:
                logger.info(f"Attempting to terminate subprocess (PID: {self.process.pid}) for attack: {self.attack_name}")
                try:
                    self.process.terminate() # Send SIGTERM to the bash process
                    # Note: communicate() in run() will handle waiting/killing if necessary
                except Exception as e:
                    logger.error(f"Error sending terminate signal to process {self.process.pid}: {e}")
        else:
            logger.debug(f"Stop signal already processing for attack: {self.attack_name}")


    def extract_target_names_from_script(self) -> List[str]:
        # ... (extract_target_names_from_script method remains largely the same, but remove self.targets_config check inside) ...
        """
        Extracts target variable names (e.g., TARGET_DRONE_IP) used in the shell script.
        Returns a list of unique target base names (e.g., ['drone', 'gcs']).
        """
        target_names = set()
        script_path = pathlib.Path(self.attack_script_path)
        if not script_path.is_file():
            logger.error(f"Cannot extract targets, script path invalid or not a file: {script_path}")
            return []
        try:
            content = script_path.read_text(encoding='utf-8', errors='ignore')
            matches = re.findall(r'\$\{?TARGET(?:_([A-Z0-9_]+))?_(?:IP|PORT)\}?', content)
            found_generic = bool(re.search(r'\$\{?TARGET_(?:IP|PORT)\}?', content))

            for name_part in matches:
                if name_part:
                    target_names.add(name_part.lower())

            # If generic vars found, assume 'drone' is needed, even if targets_config is absent
            if found_generic and 'drone' not in target_names:
                 logger.debug(f"Found generic $TARGET_IP/PORT usage in {self.attack_name}, adding 'drone' to required targets.")
                 target_names.add('drone')

        except Exception as e:
            logger.error(f"Failed to read or parse script {script_path} for targets: {e}")

        logger.debug(f"Extracted potential target names from {self.attack_name}: {list(target_names)}")
        return list(target_names)


# --- AttackOrchestrator Class ---

class AttackOrchestrator:
    # Remove targets_file from constructor default and args
    def __init__(self, mtd_state_file: str = str(DEFAULT_MTD_STATE_PATH),
                 attack_modules_dir: str = str(DEFAULT_ATTACK_MODULES_DIR),
                 bus_log_file: str = str(DEFAULT_BUS_LOG_PATH)):

        global BUS_LOG_PATH
        BUS_LOG_PATH = pathlib.Path(bus_log_file).resolve()

        # self.targets_file_abs removed
        self.mtd_state_file_abs = pathlib.Path(mtd_state_file).resolve()
        self.attack_modules_dir_abs = pathlib.Path(attack_modules_dir).resolve()

        # Corrected Wiki Path Calculation
        modules_dir = self.attack_modules_dir_abs.parent
        if modules_dir.name == 'modules':
            self.attack_wiki_dir_abs = (modules_dir / 'attacks_wiki').resolve()
        else:
             logger.warning(f"Parent directory '{modules_dir.name}' is not 'modules'. Assuming 'attacks_wiki' is sibling.")
             self.attack_wiki_dir_abs = (self.attack_modules_dir_abs.parent / 'attacks_wiki').resolve()

        logger.info(f"Initializing Attack Orchestrator:")
        # logger.info(f"  Targets File:       (Not used, relying on MTD state)") # Indicate change
        logger.info(f"  MTD State File:     {self.mtd_state_file_abs}")
        logger.info(f"  Attack Modules Dir: {self.attack_modules_dir_abs}")
        logger.info(f"  Attack Wiki Dir:    {self.attack_wiki_dir_abs}")
        logger.info(f"  Bus Log File:       {BUS_LOG_PATH}")

        # self.targets_config removed - no longer loaded at init
        # Check MTD state file existence at init for early warning
        if not self.mtd_state_file_abs.is_file():
             logger.critical(f"CRITICAL WARNING: MTD state file '{self.mtd_state_file_abs}' not found. Target resolution will likely fail.")

        if not self.attack_modules_dir_abs.is_dir():
             logger.warning(f"Primary attack directory not found: {self.attack_modules_dir_abs}")
        if not self.attack_wiki_dir_abs.is_dir():
             logger.warning(f"Wiki attack directory not found: {self.attack_wiki_dir_abs}")

        self.running_attacks: Dict[str, AttackRunner] = {}

    def find_attack_script(self, attack_name: str) -> Optional[pathlib.Path]:
        # ... (find_attack_script remains the same) ...
        """Finds the full path (as Path object) to an attack script."""
        script_filename = f"{attack_name}.sh"

        # Check primary attack directory first
        path_primary = self.attack_modules_dir_abs / script_filename
        logger.debug(f"Checking for script at: {path_primary}")
        if path_primary.is_file():
            logger.debug(f"Found attack script in primary directory: {path_primary}")
            return path_primary

        # Check wiki attacks directory as fallback
        path_wiki = self.attack_wiki_dir_abs / script_filename
        logger.debug(f"Checking for script at: {path_wiki}")
        if path_wiki.is_file():
            logger.debug(f"Found attack script in wiki directory: {path_wiki}")
            return path_wiki

        logger.error(f"Attack script '{script_filename}' not found in primary '{self.attack_modules_dir_abs}' or wiki '{self.attack_wiki_dir_abs}' directories.")
        return None

    def find_all_attack_scripts(self) -> Dict[str, pathlib.Path]:
        # ... (find_all_attack_scripts remains the same) ...
        """Finds all available attack scripts and returns a dict {name: Path object}."""
        scripts: Dict[str, pathlib.Path] = {}

        # Scan primary directory
        try:
            if self.attack_modules_dir_abs.is_dir():
                for item in self.attack_modules_dir_abs.iterdir():
                    if item.is_file() and item.suffix == '.sh' and not item.name.startswith('_'):
                        name = item.stem # Name without extension
                        scripts[name] = item
            else:
                 pass # Already warned in __init__
        except OSError as e:
             logger.error(f"Cannot access primary attack directory {self.attack_modules_dir_abs}: {e}")

        # Scan wiki directory, don't overwrite primary if name clashes
        try:
             if self.attack_wiki_dir_abs.is_dir():
                 for item in self.attack_wiki_dir_abs.iterdir():
                     if item.is_file() and item.suffix == '.sh' and not item.name.startswith('_'):
                         name = item.stem
                         if name not in scripts: # Add only if not found in primary
                             scripts[name] = item
             else:
                  pass # Already warned in __init__
        except OSError as e:
            logger.warning(f"Cannot access wiki attack directory {self.attack_wiki_dir_abs}: {e}")

        logger.info(f"Discovered {len(scripts)} available attack scripts.")
        return scripts

    # Remove targets_config dependency from start_attack
    def start_attack(self, attack_name: str, duration: int, params: Optional[List[str]] = None) -> Optional[AttackRunner]:
        self.cleanup_finished_attacks()

        if attack_name in self.running_attacks and self.running_attacks[attack_name].is_alive():
             logger.warning(f"Attack '{attack_name}' is already running...")
             return None
        elif attack_name in self.running_attacks: # Cleanup finished instance
             logger.info(f"Found finished tracker for '{attack_name}'. Starting new instance.")
             del self.running_attacks[attack_name]

        attack_script_path_obj = self.find_attack_script(attack_name)
        if not attack_script_path_obj:
            log_to_bus("attack_failed_to_start", {"attack_name": attack_name, "error": "Attack script not found."})
            return None

        attack_script_path_str = str(attack_script_path_obj)
        logger.info(f"Initiating attack '{attack_name}' from '{attack_script_path_str}' for {duration} seconds.")

        # Pass only mtd_state_file_abs to the runner
        runner = AttackRunner(
            attack_script_path_str,
            duration,
            self.mtd_state_file_abs, # Pass Path object
            params
        )
        self.running_attacks[attack_name] = runner
        try:
            runner.start()
            logger.info(f"Attack '{attack_name}' thread ({runner.native_id}) started.")
            return runner
        except RuntimeError as e:
             # ... (error handling for thread start) ...
            logger.error(f"Failed to start thread for attack '{attack_name}': {e}", exc_info=True)
            # ...
            return None


    def stop_attack(self, attack_name: str, wait_timeout: int = 10):
        # ... (stop_attack remains the same) ...
        """Stops a specific running attack thread and its process."""
        runner = self.running_attacks.get(attack_name)
        if runner and runner.is_alive():
            logger.info(f"Attempting to stop attack: {attack_name} (Thread: {runner.native_id}, Process: {runner.process.pid if runner.process else 'N/A'})")
            runner.stop() # Signal the thread and process to stop
            logger.debug(f"Waiting up to {wait_timeout}s for '{attack_name}' thread to join...")
            runner.join(timeout=wait_timeout) # Wait for thread to finish
            if runner.is_alive():
                logger.warning(f"Attack thread {attack_name} ({runner.native_id}) did not terminate gracefully after {wait_timeout}s join timeout. Process might still be orphaned if kill failed.")
                if runner.process and runner.process.poll() is None:
                     logger.warning(f"Force killing process {runner.process.pid} again.")
                     try: runner.process.kill()
                     except: pass
            else:
                logger.info(f"Attack thread {attack_name} ({runner.native_id}) terminated.")

            if attack_name in self.running_attacks:
                logger.debug(f"Removing tracker for stopped/finished attack: {attack_name}")
                del self.running_attacks[attack_name]

        elif runner:
             logger.info(f"Attack '{attack_name}' was already finished. Removing tracker.")
             if attack_name in self.running_attacks:
                 del self.running_attacks[attack_name]
        else:
            logger.warning(f"Attack '{attack_name}' not found in running attacks list or already cleaned up.")


    def list_attacks(self, show_paths: bool = False):
        # ... (list_attacks largely the same, remove targets file status) ...
        self.cleanup_finished_attacks()
        available_scripts = self.find_all_attack_scripts()
        available_names = sorted(list(available_scripts.keys()))
        running_names = sorted(list(self.running_attacks.keys()))

        print("\n" + "="*20 + " Attack Status " + "="*20)
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
        # print(f"Targets File: (Not used)") # Indicate targets file is not primary source
        print(f"MTD State File: {self.mtd_state_file_abs}")
        print("-" * (40 + len(" Attack Status ")))

        print(f"Available Attacks ({len(available_names)}):")
        if available_names:
            for name in available_names:
                # ... (source dir logic) ...
                script_path = available_scripts[name]
                try:
                     if script_path.is_relative_to(self.attack_modules_dir_abs): source_dir = "primary"
                     elif script_path.is_relative_to(self.attack_wiki_dir_abs): source_dir = "wiki"
                     else: source_dir = "other"
                except ValueError: # Fallback for older Python
                     if str(script_path).startswith(str(self.attack_modules_dir_abs)): source_dir = "primary"
                     elif str(script_path).startswith(str(self.attack_wiki_dir_abs)): source_dir = "wiki"
                     else: source_dir = "other"

                path_str = f" ({script_path.relative_to(BASE_DIR)})" if show_paths else ""
                print(f"  - {name:<35} (Source: {source_dir}){path_str}")
        else:
             print("  (No attack scripts found in specified directories)")

        print(f"\nRunning Attacks ({len(running_names)}):")
        if running_names:
            for name in running_names:
                # ... (PID and status info logic) ...
                pid_info = " (Starting...)"
                start_time_str = "N/A"
                runner = self.running_attacks.get(name)
                if runner:
                    elapsed = 0.0
                    if runner.start_time:
                         elapsed = time.monotonic() - runner.start_time
                         start_time_str = f"{elapsed:.1f}s ago"
                    if runner.process:
                        process_rc = runner.process.poll()
                        if process_rc is None: pid_info = f" (PID: {runner.process.pid}, Running for {elapsed:.1f}s)"
                        else:
                             rc = runner.return_code if runner.return_code is not None else process_rc
                             actual_duration = runner.end_time - runner.start_time if runner.end_time and runner.start_time else elapsed
                             pid_info = f" (PID: {runner.process.pid}, Exited={rc}, Ran for ~{actual_duration:.1f}s)"
                    elif runner.is_alive(): pid_info = f" (Thread: {runner.native_id}, Process starting or unavailable)"
                    else: pid_info = f" (Thread: {runner.native_id} - Finished, Process info lost?)"
                print(f"  - {name:<35}{pid_info}")
        else:
            print("  (None currently running)")
        print("=" * (40 + len(" Attack Status ")))

    def cleanup_finished_attacks(self):
        # ... (cleanup_finished_attacks remains the same) ...
        finished_attacks = [name for name, runner in self.running_attacks.items() if not runner.is_alive()]
        if finished_attacks:
             logger.debug(f"Cleaning up finished attack trackers: {finished_attacks}")
             for name in finished_attacks:
                 if name in self.running_attacks:
                     runner = self.running_attacks[name]
                     try:
                         if runner.is_alive(): runner.join(timeout=0.5)
                     except Exception as e: logger.error(f"Error during final join for '{name}': {e}")
                     del self.running_attacks[name]

    def stop_all_attacks(self):
        # ... (stop_all_attacks remains the same) ...
        self.cleanup_finished_attacks()
        running_threads = list(self.running_attacks.items())
        if not running_threads:
            logger.info("No attacks currently running to stop.")
            return

        logger.info(f"Stopping all {len(running_threads)} tracked running attacks...")
        threads_to_join: List[Tuple[str, AttackRunner]] = []

        for attack_name, runner in running_threads:
            if runner.is_alive():
                logger.info(f"Sending stop signal to: {attack_name} (Thread: {runner.native_id})")
                runner.stop()
                threads_to_join.append((attack_name, runner))
            elif attack_name in self.running_attacks: # Cleanup missed
                 del self.running_attacks[attack_name]

        if not threads_to_join:
            logger.info("No active threads needed stopping after re-check.")
            return

        wait_timeout_total = 15
        logger.info(f"Waiting up to {wait_timeout_total}s for {len(threads_to_join)} threads...")
        start_wait = time.monotonic()

        for name, runner in threads_to_join:
            remaining_time = wait_timeout_total - (time.monotonic() - start_wait)
            if remaining_time <= 0: break
            join_timeout = max(1, remaining_time / len(threads_to_join))
            runner.join(timeout=join_timeout)
            if not runner.is_alive(): logger.info(f"Thread {name} terminated.")
            else: logger.warning(f"Thread {name} did not terminate gracefully.")
            if name in self.running_attacks: del self.running_attacks[name]

        remaining_runners = [r for r in threads_to_join if r[1].is_alive()]
        if remaining_runners: logger.error(f"{len(remaining_runners)} threads did not stop: {[r[0] for r in remaining_runners]}.")

        logger.info("Finished stopping all attacks.")
        self.list_attacks()


# --- Main Execution Logic ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attack Orchestrator (MTD State Driven)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    global_group = parser.add_argument_group('Global Configuration')
    # Remove --targets-file argument
    global_group.add_argument("--mtd-state-file", default=str(DEFAULT_MTD_STATE_PATH),
                              help=f"Path to the MTD state JSON file (REQUIRED, default: %(default)s)")
    global_group.add_argument("--attack-modules-dir", default=str(DEFAULT_ATTACK_MODULES_DIR),
                              help=f"Base directory for primary attack modules (default: %(default)s)")
    global_group.add_argument("--bus-log-file", default=str(DEFAULT_BUS_LOG_PATH),
                              help=f"Path to the central bus log file (default: %(default)s)")
    global_group.add_argument("-v", "--verbose", action="store_true", help="Enable detailed DEBUG logging.")

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

    monitor_parser = subparsers.add_parser("monitor", help="Continuously monitor attacks.")
    monitor_parser.add_argument("-i", "--interval", type=int, default=10, metavar='SEC', help="Check interval (default: 10s).")

    run_all_parser = subparsers.add_parser("run-all", help="Run all available attacks sequentially.")
    run_all_parser.add_argument("-d", "--duration", type=int, default=30, metavar='SEC', help="Duration per attack (default: 30s).")
    run_all_parser.add_argument("--exclude", nargs='*', default=[], metavar='NAME', help="Attack names to exclude.")
    run_all_parser.add_argument("--shuffle", action="store_true", help="Randomize attack order.")
    run_all_parser.add_argument("--delay", type=int, default=5, metavar='SEC', help="Delay between attacks (default: 5s).")

    args = parser.parse_args()

    # --- Set logging level ---
    if args.verbose: logger.setLevel(logging.DEBUG)
    else: logger.setLevel(logging.INFO)

    # --- Instantiate Orchestrator ---
    try:
        # Pass only necessary args (targets_file removed)
        orchestrator = AttackOrchestrator(
            mtd_state_file=args.mtd_state_file,
            attack_modules_dir=args.attack_modules_dir,
            bus_log_file=args.bus_log_file
        )
    except Exception as init_err:
        logger.critical(f"Failed to initialize AttackOrchestrator: {init_err}", exc_info=True)
        sys.exit(1)

    # --- Command Handling (remains largely the same, logic relies on orchestrator methods) ---
    exit_code = 0
    try:
        if args.command == "list":
            orchestrator.list_attacks(show_paths=args.show_paths)
        elif args.command == "start":
            runner = orchestrator.start_attack(args.attack_name, args.duration, args.params)
            if runner: time.sleep(0.5); orchestrator.list_attacks()
            else: logger.error(f"Failed to start attack '{args.attack_name}'."); exit_code = 1
        elif args.command == "stop":
            orchestrator.stop_attack(args.attack_name); time.sleep(1.0); orchestrator.list_attacks()
        elif args.command == "stop-all":
            orchestrator.stop_all_attacks()
        elif args.command == "monitor":
            logger.info(f"Starting monitor mode (Interval: {args.interval}s). Press Ctrl+C to exit.")
            while True: orchestrator.list_attacks(); time.sleep(args.interval)
        elif args.command == "run-all":
            attack_scripts = orchestrator.find_all_attack_scripts()
            attack_names = sorted(list(attack_scripts.keys()))
            if not attack_names: logger.info("No attacks found."); sys.exit(0)

            excluded_attacks = set(args.exclude)
            attacks_to_run = [name for name in attack_names if name not in excluded_attacks]
            if not attacks_to_run: logger.info("All attacks excluded."); sys.exit(0)
            if excluded_attacks: logger.info(f"Excluding: {', '.join(sorted(list(excluded_attacks)))}")
            if args.shuffle: logger.info("Shuffling order."); random.shuffle(attacks_to_run)

            total_attacks = len(attacks_to_run)
            logger.info(f"Starting sequential run of {total_attacks} attack(s)... (Dur={args.duration}s, Delay={args.delay}s)")
            run_results = {}

            for i, attack_name in enumerate(attacks_to_run, 1):
                logger.info("\n" + f"--- [{i}/{total_attacks}] Starting Attack: {attack_name} ---")
                try:
                    runner_thread = orchestrator.start_attack(attack_name, args.duration, params=None)
                    if runner_thread:
                        logger.info(f"Waiting for '{attack_name}' (Dur: {args.duration}s)...")
                        wait_join_timeout = args.duration + 15
                        runner_thread.join(timeout=wait_join_timeout)
                        if runner_thread.is_alive():
                            logger.warning(f"'{attack_name}' timed out. Stopping..."); orchestrator.stop_attack(attack_name, 5); run_results[attack_name] = "TIMEOUT_STOPPED"
                        else: rc = runner_thread.return_code; logger.info(f"'{attack_name}' completed (RC: {rc})."); run_results[attack_name] = rc
                    else: logger.error(f"Skipping wait for '{attack_name}' (failed to start)."); run_results[attack_name] = "FAILED_TO_START"

                    if i < total_attacks: logger.info(f"Waiting {args.delay}s..."); time.sleep(args.delay)
                except Exception as e:
                    logger.error(f"Orchestrator error during '{attack_name}': {e}", exc_info=True); run_results[attack_name] = "ORCHESTRATOR_ERROR"
                    orchestrator.stop_attack(attack_name, 5); time.sleep(args.delay)

            logger.info("\n" + "--- Finished Sequential Attack Run ---"); logger.info("Summary:")
            max_len = max(len(name) for name in run_results.keys()) if run_results else 10
            for name, result in run_results.items(): logger.info(f"  - {name:<{max_len}} : {result}")
            if any(isinstance(rc, int) and rc != 0 for rc in run_results.values()) or \
               any(isinstance(rc, str) and rc not in ["TIMEOUT_STOPPED", 0] for rc in run_results.values()): # Treat 0 also as success string if needed
                 exit_code = 1

    except KeyboardInterrupt:
        logger.info("\nKeyboardInterrupt. Stopping all attacks..."); orchestrator.stop_all_attacks(); sys.exit(130)
    except Exception as e:
        logger.critical(f"Unexpected critical error: {e}", exc_info=True); logger.info("Attempting stop-all..."); orchestrator.stop_all_attacks(); exit_code = 1
    finally:
        orchestrator.cleanup_finished_attacks()
        if orchestrator.running_attacks: logger.warning(f"{len(orchestrator.running_attacks)} trackers remain: {list(orchestrator.running_attacks.keys())}")
        logger.info("Attack Orchestrator finished."); sys.exit(exit_code)

