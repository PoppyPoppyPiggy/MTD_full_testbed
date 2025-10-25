#!/usr/bin/env python3

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import random
import yaml
# Use timezone-aware UTC time
from datetime import datetime, timezone
from threading import Thread, Event
from typing import Dict, List, Optional, Tuple
import re # Import regex module

# --- 경로 설정 ---
# 이 스크립트 파일의 위치를 기준으로 상대 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 기본값 설정 (명령행 인수로 덮어쓸 수 있음)
DEFAULT_BUS_LOG_PATH = os.path.join(BASE_DIR, 'bus.log')
DEFAULT_MTD_STATE_PATH = os.path.join(BASE_DIR, 'mtd/shared_state/mtd_state.json')
DEFAULT_ATTACK_MODULES_DIR = os.path.join(BASE_DIR, 'modules/attacks')
DEFAULT_TARGETS_FILE = os.path.join(DEFAULT_ATTACK_MODULES_DIR, 'targets/targets.yml')

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AttackOrchestrator")

# 전역 변수로 BUS_LOG_PATH 관리 (명령행 인수로 수정 가능)
BUS_LOG_PATH = DEFAULT_BUS_LOG_PATH

# --- Helper Functions ---

def log_to_bus(event_type: str, data: Dict):
    """Logs a structured message to the central bus log file."""
    log_entry = {
        # Use timezone-aware UTC time
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "source": "attack_orchestrator",
        "event_type": event_type,
        "data": data
    }
    try:
        # BUS_LOG_PATH는 전역 변수 사용
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        # Avoid logging recursion if bus log itself fails
        print(f"[ERROR] Failed to write to bus log ({BUS_LOG_PATH}): {e}", file=sys.stderr)
        # logger.error(f"Failed to write to bus log ({BUS_LOG_PATH}): {e}") # Avoid potential recursion

def load_targets(targets_file: str) -> Dict:
    """Loads target definitions from the YAML file."""
    abs_path = os.path.abspath(targets_file)
    try:
        with open(abs_path, 'r') as f:
            targets = yaml.safe_load(f)
            # Check if targets is None OR if 'targets' key doesn't exist or is None/empty
            if targets is None or not targets.get('targets'):
                logger.warning(f"Targets file ({abs_path}) is empty, invalid, or missing the top-level 'targets:' key with entries.")
                return {}
            logger.info(f"Loaded targets from {abs_path}")
            return targets.get('targets', {}) # Return the dictionary under the 'targets' key
    except FileNotFoundError:
        logger.error(f"Targets file not found: {abs_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing targets file {abs_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading targets file {abs_path}: {e}")
        return {}

def read_mtd_state(mtd_state_file: str) -> Dict:
    """Reads the current MTD state from the JSON file."""
    abs_path = os.path.abspath(mtd_state_file)
    try:
        with open(abs_path, 'r') as f:
            state = json.load(f)
            logger.debug(f"Read MTD state from {abs_path}: {state}")
            # Ensure active_rules key exists and is a list
            if 'active_rules' not in state or not isinstance(state.get('active_rules'), list):
                logger.warning(f"MTD state file {abs_path} missing or has invalid 'active_rules' list. Assuming empty list.")
                state['active_rules'] = [] # Ensure it's always a list
            return state
    except FileNotFoundError:
        logger.warning(f"MTD state file not found: {abs_path}. Assuming default/initial state (no active MTD rules).")
        return {"active_rules": []} # 파일이 없으면 활성 규칙 리스트가 없는 것으로 간주
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding MTD state file {abs_path}: {e}. Assuming default state.")
        return {"active_rules": []}
    except Exception as e:
        logger.error(f"Error reading MTD state file {abs_path}: {e}. Assuming default state.")
        return {"active_rules": []}

def resolve_target_address(target_name: str, targets_config: Dict, mtd_state: Dict) -> Optional[Tuple[str, str]]:
    """
    Resolves the actual IP address and port for a target name, considering MTD state
    based on the 'active_rules' list in mtd_state.json.
    Returns (ip, port) or None if resolution fails.
    """
    if not targets_config:
        # This warning is now potentially redundant due to check in load_targets, but keep as safety
        logger.error("Targets configuration is empty (load_targets likely failed). Cannot resolve target.")
        return None
    if target_name not in targets_config:
        logger.error(f"Target name '{target_name}' not found in targets configuration keys: {list(targets_config.keys())}")
        return None

    target_info = targets_config[target_name]
    default_ip = target_info.get('ip')
    default_port = str(target_info.get('port', '')) # Ensure port is string, handle missing port

    if not default_ip or not default_port:
        logger.error(f"Target '{target_name}' definition in config is missing IP or Port: ip={default_ip}, port={default_port}")
        return None

    # Start with default values
    current_ip = default_ip
    current_port = default_port

    # active_rules should be guaranteed to be a list by read_mtd_state
    active_rules = mtd_state.get('active_rules', [])
    logger.debug(f"Resolving target '{target_name}' (default: {default_ip}:{default_port}) with {len(active_rules)} active MTD rules.")

    applied_rule = None
    for rule in reversed(active_rules): # Check newest rules first
        rule_type = rule.get('type')
        original_rule_ip = rule.get('original_ip')
        original_rule_port_str = str(rule.get('original_port', ''))

        # Check for port shuffling DNAT rule matching original IP and Port
        if rule_type == 'port_shuffling' and original_rule_ip == default_ip and original_rule_port_str == default_port:
            # The 'new_ip' in port_shuffling usually refers to the *entry point* IP for the DNAT rule.
            # We should attack this new_ip and new_port.
            new_ip = rule.get('new_ip') # IP the attacker should target
            new_port_str = str(rule.get('new_port', '')) # Port the attacker should target
            if new_ip and new_port_str: # Ensure both new IP and new Port are present
                current_ip = new_ip
                current_port = new_port_str
                applied_rule = rule
                logger.info(f"MTD Applied (Port Shuffle): Target '{target_name}' ({default_ip}:{default_port}) should now be targeted at {current_ip}:{current_port}")
                break # Found the most recent matching rule
            else:
                logger.warning(f"Port shuffling rule for {default_ip}:{default_port} is incomplete (missing new_ip or new_port): {rule}")


        # Check for NAT rule matching original IP
        elif rule_type == 'nat' and original_rule_ip == default_ip:
             # NAT rule maps NEW_IP -> ORIGINAL_IP. Attacker should target NEW_IP.
             new_ip = rule.get('new_ip')
             if new_ip:
                 current_ip = new_ip
                 # Port remains the original default port for simple NAT
                 applied_rule = rule
                 logger.info(f"MTD Applied (NAT): Target '{target_name}' ({default_ip}:{default_port}) IP redirected. Should now be targeted at {current_ip}:{current_port}")
                 break # Found the most recent matching rule
             else:
                  logger.warning(f"NAT rule for {default_ip} is incomplete (missing new_ip): {rule}")


    if not applied_rule:
        logger.info(f"No applicable MTD rules found for target '{target_name}'. Using default target address: {current_ip}:{current_port}")

    resolved_address = (current_ip, current_port)
    logger.debug(f"Resolved target '{target_name}' final address: {resolved_address}")
    return resolved_address


# --- AttackRunner Thread ---

class AttackRunner(Thread):
    def __init__(self, attack_script_path: str, duration: int, targets_config: Dict, mtd_state_file: str, params: Optional[List[str]] = None):
        super().__init__()
        self.attack_script_path = attack_script_path
        self.duration = duration
        self.targets_config = targets_config
        self.mtd_state_file = mtd_state_file # Store the path
        self.params = params if params else []
        self.process = None
        self._stop_event = Event()
        self.attack_name = os.path.basename(attack_script_path).replace('.sh', '')
        self.resolved_targets = {}
        self.start_time = None
        self.return_code = None

    def run(self):
        """Executes the attack script."""
        # Check script existence and permissions
        if not os.path.exists(self.attack_script_path):
             logger.error(f"Attack script path does not exist: {self.attack_script_path}")
             # Log failure and return early
             log_to_bus("attack_failed_to_start", {
                 "attack_name": self.attack_name, "script": self.attack_script_path, "error": "Script path not found."
             })
             return
        if not os.access(self.attack_script_path, os.X_OK):
             # Log warning but attempt execution with /bin/bash anyway
             logger.warning(f"Attack script is not marked executable: {self.attack_script_path}. Will attempt execution via /bin/bash.")
             # No need to return here, just warn.

        # --- MTD State Synchronization ---
        # Read the state file *just before* execution
        mtd_state = read_mtd_state(self.mtd_state_file)

        # --- Target Resolution and Environment Variable Setup ---
        env = os.environ.copy()
        target_names_in_script = self.extract_target_names_from_script()
        resolved_any_target = False

        log_data_start = {
            "attack_name": self.attack_name,
            "script": os.path.basename(self.attack_script_path), # Log only script name
            "duration_requested": self.duration,
            "params_provided": self.params,
            "resolved_targets": {}
        }

        # Check if targets_config is valid before resolving
        if not self.targets_config:
             logger.error("Cannot resolve targets because targets configuration failed to load or is empty.")
             # Log failure and return early
             log_to_bus("attack_failed_to_start", {
                "attack_name": self.attack_name, "script": os.path.basename(self.attack_script_path),
                "error": "Targets configuration empty or invalid."
             })
             return


        for target_name in target_names_in_script:
            # Pass the freshly read mtd_state
            resolved = resolve_target_address(target_name, self.targets_config, mtd_state)
            if resolved:
                ip_var = f"TARGET_{target_name.upper()}_IP"
                port_var = f"TARGET_{target_name.upper()}_PORT"
                env[ip_var] = resolved[0]
                env[port_var] = resolved[1]
                logger.info(f"Setting Env for '{target_name}': {ip_var}={resolved[0]}, {port_var}={resolved[1]}")
                self.resolved_targets[target_name] = f"{resolved[0]}:{resolved[1]}"
                log_data_start["resolved_targets"][target_name] = self.resolved_targets[target_name]
                resolved_any_target = True
            else:
                logger.warning(f"Could not resolve target '{target_name}' for script {self.attack_script_path}. Script might fail or use defaults.")
                log_data_start["resolved_targets"][target_name] = "resolution_failed"

        # Resolve default 'drone' target if TARGET_IP/PORT are used but 'drone' wasn't explicitly extracted
        if 'drone' in self.targets_config and 'drone' not in target_names_in_script:
             # Check if script content actually uses generic TARGET_IP/PORT
             try:
                 with open(self.attack_script_path, 'r', encoding='utf-8', errors='ignore') as f:
                     content = f.read()
                     # Check for $TARGET_IP, ${TARGET_IP}, $TARGET_PORT, ${TARGET_PORT}
                     if re.search(r'\$\{?TARGET_(IP|PORT)\}?', content):
                         resolved_default = resolve_target_address('drone', self.targets_config, mtd_state)
                         if resolved_default:
                             if 'TARGET_IP' not in env: # Set only if not already set by specific target
                                 env['TARGET_IP'] = resolved_default[0]
                                 logger.info(f"Setting Default Env (drone): TARGET_IP={resolved_default[0]}")
                             if 'TARGET_PORT' not in env:
                                 env['TARGET_PORT'] = resolved_default[1]
                                 logger.info(f"Setting Default Env (drone): TARGET_PORT={resolved_default[1]}")
                             # Log this resolution attempt
                             log_key = "default_drone(fallback)"
                             self.resolved_targets[log_key] = f"{resolved_default[0]}:{resolved_default[1]}"
                             log_data_start["resolved_targets"][log_key] = self.resolved_targets[log_key]
                         else:
                              logger.warning("Script uses generic TARGET_IP/PORT, but failed to resolve default 'drone' target.")
             except Exception as e:
                 logger.error(f"Error checking script content for default targets: {e}")


        # --- Execute Attack ---
        # Using /bin/bash explicitly can be more portable if scripts lack shebang or exec permission
        command = ["/bin/bash", self.attack_script_path] + self.params
        logger.info(f"Starting attack '{self.attack_name}': {' '.join(command)}")

        # Log attack start event just before starting the process
        log_to_bus("attack_started", log_data_start)
        self.start_time = time.time()

        stdout_log = ""
        stderr_log = ""

        try:
            self.process = subprocess.Popen(
                command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line buffered
                universal_newlines=True,
                encoding='utf-8', # Specify encoding
                errors='replace' # Handle potential decoding errors
            )
            logger.debug(f"Attack '{self.attack_name}' process started (PID: {self.process.pid}).")

            # Wait for duration or stop event
            remaining_time = self.duration
            while remaining_time > 0 and not self._stop_event.is_set():
                 wait_interval = min(remaining_time, 0.5) # Check every 0.5s or less
                 try:
                     # Use timeout in wait() to check if process finished
                     self.process.wait(timeout=wait_interval)
                     # If wait doesn't raise TimeoutExpired, process finished
                     logger.info(f"Attack process '{self.attack_name}' finished early (before duration).")
                     break # Exit the wait loop
                 except subprocess.TimeoutExpired:
                     pass # Process still running, continue waiting
                 remaining_time -= wait_interval

            # --- Stop or wait for Attack to finish naturally ---
            # Check if process is *still* running after the loop (duration ended or stop requested)
            if self.process.poll() is None:
                if self._stop_event.is_set():
                    logger.info(f"Stop requested. Terminating attack: {self.attack_name} (PID: {self.process.pid})")
                else: # Duration ended
                    logger.info(f"Duration ({self.duration}s) ended. Terminating attack: {self.attack_name} (PID: {self.process.pid})")

                self.process.terminate() # Try SIGTERM first
                try:
                    # Wait a short time for graceful termination and capture output
                    stdout_log, stderr_log = self.process.communicate(timeout=5)
                    logger.info(f"Attack '{self.attack_name}' terminated gracefully.")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing attack process {self.attack_name} (PID: {self.process.pid}) after terminate timeout.")
                    self.process.kill() # Force kill with SIGKILL
                    # Capture output after kill (might be incomplete)
                    stdout_log, stderr_log = self.process.communicate()
            else:
                 # Process had already finished before/during the loop, capture remaining output
                 stdout_log, stderr_log = self.process.communicate()
                 logger.debug(f"Attack '{self.attack_name}' had already finished, capturing output.")

            # Log captured output snippets regardless of how it finished
            logger.debug(f"Attack {self.attack_name} final STDOUT snippet:\n{stdout_log[:500]}...")
            logger.debug(f"Attack {self.attack_name} final STDERR snippet:\n{stderr_log[:500]}...")


        except FileNotFoundError as e: # Catch if /bin/bash or script itself is missing at Popen time
            logger.error(f"Failed to execute command '{' '.join(command)}': {e}")
            stderr_log = f"Execution Error: {e}"
            self.return_code = -1 # Indicate failure
        except Exception as e:
            logger.error(f"Error during attack execution or termination '{self.attack_name}': {e}", exc_info=True)
            # Try to capture stderr even on error
            if self.process and self.process.poll() is None:
                 try: # Quick attempt to kill and get output
                     self.process.kill()
                     _, stderr_rem = self.process.communicate(timeout=1)
                     stderr_log += stderr_rem
                 except: pass # Ignore errors during cleanup
            stderr_log += f"\nOrchestrator Error: {e}"
            self.return_code = -1 # Indicate orchestrator-level error
        finally:
            actual_duration = time.time() - self.start_time if self.start_time else 0
            # Get return code if process existed and return_code wasn't set by an exception
            if self.process and self.return_code is None:
                 self.return_code = self.process.returncode

            logger.info(f"Attack '{self.attack_name}' finished. Duration: {actual_duration:.2f}s, Return Code: {self.return_code}.")
            # Log attack end to bus
            log_data_end = {
                "attack_name": self.attack_name,
                "script": os.path.basename(self.attack_script_path),
                "duration_actual": round(actual_duration, 2),
                "return_code": self.return_code,
                "stopped_by_request": self._stop_event.is_set(),
                "stdout_snippet": stdout_log[:500] + ('...' if len(stdout_log) > 500 else ''),
                "stderr_snippet": stderr_log[:500] + ('...' if len(stderr_log) > 500 else '')
            }
            log_to_bus("attack_stopped", log_data_end)


    def stop(self):
        """Signals the attack thread to stop."""
        if not self._stop_event.is_set():
            logger.info(f"Stop signal received for attack: {self.attack_name}")
            self._stop_event.set()
        else:
            logger.debug(f"Stop signal already sent for attack: {self.attack_name}")
        # Actual termination happens in the run loop checks

    def extract_target_names_from_script(self) -> List[str]:
        """
        Extracts target variable names (e.g., TARGET_DRONE_IP) used in the shell script.
        Improved regex to handle different variable usage patterns like $VAR and ${VAR}.
        Returns a list of unique target base names (e.g., ['drone', 'gcs']).
        """
        target_names = set()
        if not self.attack_script_path or not os.path.exists(self.attack_script_path):
            logger.error(f"Cannot extract targets, script path invalid: {self.attack_script_path}")
            return []
        try:
            with open(self.attack_script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Regex V3: More robustly find TARGET_NAME_IP/PORT, including defaults like TARGET_IP/PORT
                # Looks for optional _{NAME}_ part.
                matches = re.findall(r'\$\{?TARGET(?:_([A-Z0-9_]+))?_(?:IP|PORT)\}?', content)
                found_generic = False
                for name_part in matches:
                    if name_part: # If NAME part was captured (e.g., TARGET_DRONE_IP -> DRONE)
                        target_names.add(name_part.lower())
                    else: # If NAME part was NOT captured (e.g. TARGET_IP, TARGET_PORT)
                         found_generic = True

                # If generic $TARGET_IP / $TARGET_PORT were found AND 'drone' is a configured target,
                # assume it refers to 'drone'. Add 'drone' only if not already added specifically.
                if found_generic and 'drone' in self.targets_config and 'drone' not in target_names:
                     logger.debug("Found generic $TARGET_IP/PORT usage, assuming target 'drone'.")
                     target_names.add('drone')

        except Exception as e:
            logger.error(f"Failed to read or parse script {self.attack_script_path} for targets: {e}")

        logger.debug(f"Extracted potential target names from {self.attack_name}: {list(target_names)}")
        return list(target_names)


# --- AttackOrchestrator Class ---

class AttackOrchestrator:
    def __init__(self, targets_file: str = DEFAULT_TARGETS_FILE,
                 mtd_state_file: str = DEFAULT_MTD_STATE_PATH,
                 attack_modules_dir: str = DEFAULT_ATTACK_MODULES_DIR,
                 bus_log_file: str = DEFAULT_BUS_LOG_PATH): # Add bus_log_file parameter

        # Update global BUS_LOG_PATH if provided
        global BUS_LOG_PATH
        BUS_LOG_PATH = os.path.abspath(bus_log_file) # Ensure absolute path for global

        # Store absolute paths internally
        self.targets_file_abs = os.path.abspath(targets_file)
        self.mtd_state_file_abs = os.path.abspath(mtd_state_file)
        self.attack_modules_dir_abs = os.path.abspath(attack_modules_dir)
        # Derive wiki path relative to the *attack* modules dir
        # Be careful if attack_modules_dir is the root project dir
        parent_dir = os.path.dirname(self.attack_modules_dir_abs)
        self.attack_wiki_dir_abs = os.path.abspath(os.path.join(parent_dir, 'modules/attacks_wiki')) # Adjusted path assumption

        logger.info(f"Initializing Attack Orchestrator:")
        logger.info(f"  Targets File: {self.targets_file_abs}")
        logger.info(f"  MTD State File: {self.mtd_state_file_abs}")
        logger.info(f"  Attack Modules Dir: {self.attack_modules_dir_abs}")
        logger.info(f"  Attack Wiki Dir: {self.attack_wiki_dir_abs}")
        logger.info(f"  Bus Log File: {BUS_LOG_PATH}") # Use global


        self.targets_config = load_targets(self.targets_file_abs)
        # Log warning here if config is empty, AFTER load_targets tried and potentially logged error
        if not self.targets_config:
            logger.warning(f"Initialized with empty targets configuration. Target resolution will likely fail.")

        self.running_attacks: Dict[str, AttackRunner] = {} # Track running attacks by name

    def find_attack_script(self, attack_name: str) -> Optional[str]:
        """Finds the full path to an attack script in primary or wiki directories."""
        script_filename = f"{attack_name}.sh"

        # Check primary attack directory first
        path_primary = os.path.join(self.attack_modules_dir_abs, script_filename)
        logger.debug(f"Checking for script at: {path_primary}")
        if os.path.isfile(path_primary):
            # logger.info(f"Found attack script at: {path_primary}") # Reduce verbosity
            return path_primary

        # Check wiki attacks directory as fallback
        path_wiki = os.path.join(self.attack_wiki_dir_abs, script_filename)
        logger.debug(f"Checking for script at: {path_wiki}")
        if os.path.isfile(path_wiki):
            # logger.info(f"Found attack script at: {path_wiki}") # Reduce verbosity
            return path_wiki

        logger.error(f"Attack script '{script_filename}' not found in primary '{self.attack_modules_dir_abs}' or wiki '{self.attack_wiki_dir_abs}' directories.")
        return None

    def find_all_attack_scripts(self) -> Dict[str, str]:
        """Finds all available attack scripts and returns a dict {name: path}."""
        scripts = {}
        # Scan primary directory
        try:
            if os.path.isdir(self.attack_modules_dir_abs):
                for f in os.listdir(self.attack_modules_dir_abs):
                    full_path = os.path.join(self.attack_modules_dir_abs, f)
                    if f.endswith('.sh') and not f.startswith('_') and os.path.isfile(full_path):
                        name = f.replace('.sh', '')
                        scripts[name] = full_path
            else:
                 logger.error(f"Primary attack directory is not a valid directory: {self.attack_modules_dir_abs}")
        except OSError as e:
             logger.error(f"Cannot access primary attack directory {self.attack_modules_dir_abs}: {e}")

        # Scan wiki directory, don't overwrite primary if name clashes
        try:
             if os.path.isdir(self.attack_wiki_dir_abs):
                 for f in os.listdir(self.attack_wiki_dir_abs):
                     full_path = os.path.join(self.attack_wiki_dir_abs, f)
                     if f.endswith('.sh') and not f.startswith('_') and os.path.isfile(full_path):
                         name = f.replace('.sh', '')
                         if name not in scripts: # Add only if not found in primary
                             scripts[name] = full_path
             else:
                  logger.warning(f"Wiki attack directory is not a valid directory: {self.attack_wiki_dir_abs}")
        except OSError as e:
            logger.warning(f"Cannot access wiki attack directory {self.attack_wiki_dir_abs}: {e}")

        logger.info(f"Found {len(scripts)} available attack scripts.")
        return scripts


    def start_attack(self, attack_name: str, duration: int, params: Optional[List[str]] = None) -> Optional[AttackRunner]:
        """Starts a specific attack. Returns the runner thread or None."""
        # Check if already running (thread alive)
        if attack_name in self.running_attacks:
            runner = self.running_attacks[attack_name]
            if runner.is_alive():
                logger.warning(f"Attack '{attack_name}' seems to be already running (Thread active).")
                return None # Indicate it wasn't started now
            else:
                 logger.info(f"Found previous tracker for '{attack_name}', but thread is finished. Starting new instance.")
                 # Allow restarting by removing the old entry before creating a new one
                 del self.running_attacks[attack_name]


        attack_script_path = self.find_attack_script(attack_name)
        if not attack_script_path:
            log_to_bus("attack_failed_to_start", {
                 "attack_name": attack_name,
                 "duration_requested": duration,
                 "params_provided": params if params else [],
                 "error": "Attack script not found."
            })
            return None # Indicate failure

        logger.info(f"Initiating attack '{attack_name}' from '{attack_script_path}' for {duration} seconds.")
        # Pass necessary absolute paths to the runner
        runner = AttackRunner(
            attack_script_path,
            duration,
            self.targets_config,
            self.mtd_state_file_abs, # Pass absolute path
            params
        )
        self.running_attacks[attack_name] = runner
        runner.start()
        logger.info(f"Attack '{attack_name}' thread started.")
        return runner # Return the thread


    def stop_attack(self, attack_name: str):
        """Stops a specific running attack."""
        runner = self.running_attacks.get(attack_name)
        if runner and runner.is_alive():
            logger.info(f"Attempting to stop attack: {attack_name}")
            runner.stop() # Signal the thread to stop
            runner.join(timeout=10) # Wait for thread to finish (with timeout)
            if runner.is_alive():
                logger.warning(f"Attack thread {attack_name} did not terminate gracefully after join timeout.")
                # Process might still be running, though thread might exit soon.
            else:
                logger.info(f"Attack thread {attack_name} terminated.")
            # Remove after attempting to stop and join
            if attack_name in self.running_attacks: # Check again
                del self.running_attacks[attack_name]
        elif runner: # Runner exists but is not alive (already finished)
             logger.info(f"Attack '{attack_name}' was already finished. Removing tracker.")
             if attack_name in self.running_attacks:
                 del self.running_attacks[attack_name]
        else:
            logger.warning(f"Attack '{attack_name}' not found in running attacks list.")


    def list_attacks(self):
        """Lists available and running attacks."""
        available_scripts = self.find_all_attack_scripts()
        available_names = sorted(list(available_scripts.keys()))

        # Check which attacks are actually running by checking thread status
        # Cleanup finished threads first
        self.cleanup_finished_attacks()
        running_names = sorted(list(self.running_attacks.keys())) # Keys are names of running threads

        print("\n=== Attack Status ===")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Available attacks:")
        if available_names:
            for name in available_names:
                # Indicate source directory more clearly
                script_path = available_scripts[name]
                if self.attack_modules_dir_abs and script_path.startswith(self.attack_modules_dir_abs):
                     source_dir = "primary"
                elif self.attack_wiki_dir_abs and script_path.startswith(self.attack_wiki_dir_abs):
                     source_dir = "wiki"
                else:
                     source_dir = "unknown" # Should not happen if paths are correct
                print(f"  - {name:<40} (source: {source_dir})") # Aligned output
        else:
             print("  (No attack scripts found)")


        print("\nRunning attacks:")
        if running_names:
            for name in running_names:
                pid_info = ""
                runner = self.running_attacks.get(name) # Should exist if in running_names after cleanup
                if runner and runner.process:
                    # Check if process is still alive (poll() returns None if running)
                    if runner.process.poll() is None:
                         pid_info = f" (PID: {runner.process.pid})"
                    else:
                         # Include exit code if known
                         rc = runner.return_code if runner.return_code is not None else runner.process.poll()
                         pid_info = f" (PID: {runner.process.pid} - Exited {rc})"
                elif runner:
                     pid_info = " (Thread running, process info unavailable)"
                else: # Should not happen after cleanup
                     pid_info = " (Tracker exists, but thread missing?)"

                print(f"  - {name}{pid_info}")
        else:
            print("  (None)")
        print("=====================")

    def cleanup_finished_attacks(self):
         """Removes trackers for threads that have finished."""
         # Use list comprehension to avoid modifying dict while iterating
         finished_attacks = [
             name for name, runner in self.running_attacks.items()
             if not runner.is_alive()
         ]
         if finished_attacks:
             logger.debug(f"Cleaning up finished attack trackers: {finished_attacks}")
             for name in finished_attacks:
                 if name in self.running_attacks: # Check if still exists before deleting
                     # Ensure join is called even if missed, non-blocking
                     try:
                         self.running_attacks[name].join(timeout=0.1)
                     except Exception: pass # Ignore errors on final join attempt
                     del self.running_attacks[name]


    def stop_all_attacks(self):
        """Stops all running attacks."""
        # Cleanup first to avoid trying to stop already finished ones
        self.cleanup_finished_attacks()

        if not self.running_attacks:
            logger.info("No attacks currently running to stop.")
            return

        logger.info(f"Stopping all {len(self.running_attacks)} tracked attacks...")
        attack_names = list(self.running_attacks.keys()) # Copy keys before iterating
        threads_to_join = []

        for attack_name in attack_names:
            runner = self.running_attacks.get(attack_name)
            # Check is_alive() again, cleanup might have missed concurrent finish
            if runner and runner.is_alive():
                logger.info(f"Sending stop signal to: {attack_name}")
                runner.stop()
                threads_to_join.append((attack_name, runner))
            elif runner: # Not alive, cleanup missed it? Remove now.
                logger.debug(f"Removing tracker for already finished attack during stop-all: {attack_name}")
                del self.running_attacks[attack_name]

        if not threads_to_join:
            logger.info("No active threads needed stopping.")
            return

        logger.info(f"Waiting for {len(threads_to_join)} attack threads to terminate...")
        # Wait for all signaled threads to finish
        for name, runner in threads_to_join:
            runner.join(timeout=10) # Wait with timeout
            if runner.is_alive():
                 logger.warning(f"Attack thread {name} did not terminate gracefully after stop-all.")
            else:
                 logger.info(f"Attack thread {name} terminated successfully.")
            # Remove tracker after joining attempt
            if name in self.running_attacks:
                 del self.running_attacks[name]

        logger.info("Finished stopping all attacks.")
        self.list_attacks() # Show status after stopping


# --- Main Execution Logic ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orchestrate drone attack simulations.")
    # Global arguments
    parser.add_argument("--targets-file", default=DEFAULT_TARGETS_FILE, help=f"Path to the targets YAML file (default: {DEFAULT_TARGETS_FILE})")
    parser.add_argument("--mtd-state-file", default=DEFAULT_MTD_STATE_PATH, help=f"Path to the MTD state JSON file (default: {DEFAULT_MTD_STATE_PATH})")
    parser.add_argument("--attack-modules-dir", default=DEFAULT_ATTACK_MODULES_DIR, help=f"Base directory for attack modules (default: {DEFAULT_ATTACK_MODULES_DIR})")
    parser.add_argument("--bus-log-file", default=DEFAULT_BUS_LOG_PATH, help=f"Path to the bus log file (default: {DEFAULT_BUS_LOG_PATH})")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List available attacks and running instances.")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a specific attack.")
    start_parser.add_argument("attack_name", help="Name of the attack to start (e.g., 'gps-spoofing').")
    start_parser.add_argument("-d", "--duration", type=int, default=60, help="Duration to run the attack in seconds (default: 60).")
    start_parser.add_argument("-p", "--params", nargs='*', help="Optional parameters to pass to the attack script.")

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop a running attack instance.")
    stop_parser.add_argument("attack_name", help="Name of the attack to stop.")

    # Stop-all command
    stop_all_parser = subparsers.add_parser("stop-all", help="Stop all running attack instances.")

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor running attacks and clean up finished ones.")
    monitor_parser.add_argument("-i", "--interval", type=int, default=5, help="Interval in seconds to check running attacks (default: 5).")

    # --- Run-all command ---
    run_all_parser = subparsers.add_parser("run-all", help="Run all available attacks sequentially.")
    run_all_parser.add_argument("-d", "--duration", type=int, default=30, help="Duration for each attack in seconds (default: 30).")
    # run_all_parser.add_argument("--exclude", nargs='*', help="List of attack names to exclude.") # Optional: add exclude functionality later

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        # Set level for the specific logger used in this script
        logger.setLevel(logging.DEBUG)
        # Optionally set the root logger level if other libraries log verbosely
        # logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    # --- Instantiate Orchestrator ---
    # Pass paths from args to the constructor
    # Make sure to pass the bus_log_file path as well
    orchestrator = AttackOrchestrator(
        targets_file=args.targets_file,
        mtd_state_file=args.mtd_state_file,
        attack_modules_dir=args.attack_modules_dir,
        bus_log_file=args.bus_log_file # Pass the potentially overridden bus log path
    )

    try:
        # --- Command Handling ---
        if args.command == "list":
            orchestrator.list_attacks()
        elif args.command == "start":
            orchestrator.start_attack(args.attack_name, args.duration, args.params)
            # Give a moment for the thread to start and log initial messages
            time.sleep(0.5)
            orchestrator.list_attacks() # Show status after starting
        elif args.command == "stop":
            orchestrator.stop_attack(args.attack_name)
            time.sleep(1.5) # Give time for termination
            orchestrator.list_attacks()
        elif args.command == "stop-all":
            orchestrator.stop_all_attacks()
            time.sleep(1.5)
            orchestrator.list_attacks()
        elif args.command == "monitor":
            logger.info("Starting monitor mode. Press Ctrl+C to exit.")
            while True:
                orchestrator.list_attacks()
                # cleanup_finished_attacks is called within list_attacks now
                time.sleep(args.interval)
        # --- Handle run-all command ---
        elif args.command == "run-all":
            attack_scripts = orchestrator.find_all_attack_scripts()
            attack_names = sorted(list(attack_scripts.keys())) # Get names and sort

            if not attack_names:
                logger.info("No attacks found to run.")
                sys.exit(0)

            logger.info(f"Found {len(attack_names)} attacks. Starting sequentially (duration: {args.duration}s each)...")

            for attack_name in attack_names:
                # Optional: Add exclude logic here if implemented
                # if args.exclude and attack_name in args.exclude:
                #     logger.info(f"--- Skipping excluded attack: {attack_name} ---")
                #     continue

                logger.info(f"\n--- Starting attack: {attack_name} ---")
                try:
                    # Start the attack (returns the thread)
                    runner_thread = orchestrator.start_attack(attack_name, args.duration, params=None) # No params for run-all simplicity

                    if runner_thread:
                        # Wait for the thread to finish or timeout
                        logger.info(f"Waiting for '{attack_name}' to complete or run for {args.duration}s...")
                        # Join with a timeout slightly longer than the duration
                        runner_thread.join(timeout=args.duration + 10) # Add buffer time

                        if runner_thread.is_alive():
                            logger.warning(f"Attack '{attack_name}' thread still alive after timeout. Attempting stop...")
                            orchestrator.stop_attack(attack_name) # Request stop
                            # No need to join again here, stop_attack handles join
                        else:
                            # Access return code after thread finishes
                            rc = runner_thread.return_code
                            logger.info(f"Attack '{attack_name}' completed (Return Code: {rc}).")

                        # Ensure cleanup happens even if stop was needed (cleanup is also called in list_attacks)
                        # orchestrator.cleanup_finished_attacks() # Might be redundant if list_attacks is called often

                    else:
                         # start_attack already logs errors if it fails to start
                         logger.error(f"Skipping wait for '{attack_name}' as it failed to start.")

                    time.sleep(2) # Short pause between attacks

                except Exception as e:
                    logger.error(f"Error occurred while running or waiting for attack '{attack_name}': {e}", exc_info=True)
                    # Decide if we should continue with the next attack or stop
                    # continue # Continue to next attack
                    logger.warning(f"Attempting to continue with the next attack after error.")


            logger.info("\n--- Finished running all attacks sequentially. ---")


    except KeyboardInterrupt:
        logger.info("Interrupted by user. Stopping all attacks...")
        orchestrator.stop_all_attacks()
        sys.exit(0)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        logger.info("Attempting to stop all attacks due to error...")
        orchestrator.stop_all_attacks()
        sys.exit(1)
    finally:
        # Ensure cleanup runs at the very end if not interrupted before stop_all_attacks finishes
        orchestrator.cleanup_finished_attacks()
        if len(orchestrator.running_attacks) > 0:
             # This might list threads that are in the process of being stopped by stop_all_attacks
             logger.warning(f"{len(orchestrator.running_attacks)} attack trackers remain. Threads might be stopping.")
             # Give stop_all_attacks a bit more time?
             time.sleep(2)
             orchestrator.cleanup_finished_attacks() # Final cleanup attempt
             if len(orchestrator.running_attacks) > 0:
                  logger.error(f"Could not cleanly stop all attack threads: {list(orchestrator.running_attacks.keys())}")

