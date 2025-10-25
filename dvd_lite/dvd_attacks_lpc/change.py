import os
import re
import shutil
import logging
from typing import List, Tuple

# --- 설정 ---
# attack_orchestrator.py 와 동일한 BASE_DIR 사용
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ATTACK_DIRS = [
    os.path.join(BASE_DIR, 'modules/attacks'),
    os.path.join(BASE_DIR, 'modules/attacks_wiki')
]
# targets.yml 파일 경로 (기본 타겟 이름 및 기본값 참조용)
TARGETS_FILE = os.path.join(BASE_DIR, 'modules/attacks/targets/targets.yml')

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ScriptModifier")

# --- 기본값 로드 (targets.yml 에서) ---
DEFAULT_TARGET_VALUES = {}
try:
    import yaml
    abs_targets_path = os.path.abspath(TARGETS_FILE)
    if os.path.exists(abs_targets_path):
        with open(abs_targets_path, 'r') as f:
            targets_yaml = yaml.safe_load(f)
            if targets_yaml and 'targets' in targets_yaml:
                for name, info in targets_yaml['targets'].items():
                    ip = info.get('ip')
                    port = info.get('port')
                    if ip:
                        DEFAULT_TARGET_VALUES[f"TARGET_{name.upper()}_IP"] = ip
                    if port:
                        DEFAULT_TARGET_VALUES[f"TARGET_{name.upper()}_PORT"] = str(port)
                logger.info(f"Loaded default target values from {abs_targets_path}")
            else:
                logger.warning(f"Could not parse 'targets' section in {abs_targets_path}")
    else:
        logger.warning(f"Targets file not found at {abs_targets_path}, using generic defaults.")
except ImportError:
    logger.warning("PyYAML not installed. Cannot load default values from targets.yml.")
except Exception as e:
    logger.error(f"Error loading targets file {TARGETS_FILE}: {e}")

# Fallback defaults if file loading fails or target is missing
GENERIC_DEFAULTS = {
    "TARGET_IP": "10.0.0.1",
    "TARGET_PORT": "14550",
    "TARGET_DRONE_IP": "10.0.0.1",
    "TARGET_DRONE_PORT": "14550",
    "TARGET_GCS_IP": "10.0.0.2",
    "TARGET_GCS_PORT": "14550", # Assuming GCS might use same port? Adjust if needed
    "TARGET_CAMERA_IP": "10.0.0.3", # Example
    "TARGET_CAMERA_PORT": "554", # Example RTSP port
    "TARGET_COMPANION_IP": "10.0.0.4", # Example
    "TARGET_COMPANION_PORT": "80" # Example Web UI port
}

def get_default_value(env_var_name: str) -> str:
    """Get default value for environment variable."""
    # Prioritize values from targets.yml
    if env_var_name in DEFAULT_TARGET_VALUES:
        return DEFAULT_TARGET_VALUES[env_var_name]
    # Use generic defaults if not found
    if env_var_name in GENERIC_DEFAULTS:
        return GENERIC_DEFAULTS[env_var_name]
    # Fallback for unknown variables
    logger.warning(f"No default value found for {env_var_name}, using empty string.")
    return ""


# --- 수정 로직 ---

def modify_script_content(content: str) -> Tuple[str, bool]:
    """Applies modifications to the script content."""
    modified = False
    lines = content.splitlines()
    new_lines = []
    processed_variables = set() # Track variables already processed by specific patterns

    # --- 1. 파라미터 처리 코드 추가 (스크립트 초반, shebang 다음) ---
    shebang_found = False
    param_code_added = False
    param_code = [
        "",
        "# --- Process Command Line Arguments ---",
        "# Example: Assign first arg to INTENSITY, default 'medium'",
        '# INTENSITY="${1:-medium}"',
        "# Example: Assign second arg to DURATION_SECONDS, default '30'",
        '# DURATION_SECONDS="${2:-30}"',
        '# echo "Parameters: Intensity=$INTENSITY, Duration=$DURATION_SECONDS"',
        '# Add more parameter processing as needed for the specific script',
        "# ------------------------------------",
        ""
    ]
    # Check if similar parameter processing already exists
    has_existing_param_code = any(re.search(r'^\s*#.*Process Command Line Arguments.*', line) or \
                                 re.search(r'^\s*\w+="\$\{?\d[:=-]', line) for line in lines)

    for i, line in enumerate(lines):
        new_lines.append(line)
        if line.strip().startswith("#!"):
            shebang_found = True
            if not has_existing_param_code and not param_code_added:
                new_lines.extend(param_code)
                param_code_added = True
                modified = True
                logger.debug("Added parameter processing template.")

    # If no shebang, add param code at the beginning (less ideal)
    if not shebang_found and not has_existing_param_code and not param_code_added:
        new_lines = param_code + new_lines
        param_code_added = True
        modified = True
        logger.debug("Added parameter processing template at the beginning (no shebang found).")


    # --- 2. 환경 변수 대체 (가장 일반적인 패턴부터) ---
    current_lines = new_lines # Process lines potentially modified by param code addition
    new_lines = [] # Reset for variable replacement processing

    # Regex patterns
    # Pattern 1: VAR="<IP_ADDRESS>" or VAR='<IP_ADDRESS>'
    ip_pattern = r'^(\s*)(\w+)=(["\']?)((?:[0-9]{1,3}\.){3}[0-9]{1,3})\3(\s*#.*)?$'
    # Pattern 2: VAR=<PORT> (numeric)
    port_pattern = r'^(\s*)(\w+)=([0-9]{2,5})(\s*#.*)?$'
    # Pattern 3: Explicit target variables like TARGET_HOST, MAV_PROXY_IP etc.
    specific_var_pattern = r'^(\s*)(TARGET_HOST|TARGET_IP|DRONE_IP|MAV_PROXY_IP|GCS_IP|CAMERA_IP|COMPANION_IP)=(["\']?)((?:[0-9]{1,3}\.){3}[0-9]{1,3})\3(\s*#.*)?$'
    specific_port_pattern = r'^(\s*)(TARGET_PORT|DRONE_PORT|MAV_PROXY_PORT|GCS_PORT|CAMERA_PORT|COMPANION_PORT)=([0-9]{2,5})(\s*#.*)?$'

    # Combine IP/Port patterns for easier checking
    ip_regex = re.compile(ip_pattern)
    port_regex = re.compile(port_pattern)
    specific_ip_regex = re.compile(specific_var_pattern)
    specific_port_regex = re.compile(specific_port_pattern)


    for line in current_lines:
        original_line = line
        processed = False

        # --- Check Specific Patterns First ---
        match_specific_ip = specific_ip_regex.match(line)
        if match_specific_ip and match_specific_ip.group(2) not in processed_variables:
            indent, var_name, quote, old_ip, comment = match_specific_ip.groups()
            comment = comment if comment else ""
            # Determine appropriate TARGET_<NAME>_IP variable
            target_name = "DRONE" # Default guess
            if "GCS" in var_name: target_name = "GCS"
            elif "CAMERA" in var_name: target_name = "CAMERA"
            elif "COMPANION" in var_name: target_name = "COMPANION"
            # Use TARGET_IP for generic names
            elif var_name in ["TARGET_HOST", "TARGET_IP"]: target_name = None

            env_var = f"TARGET_{target_name}_IP" if target_name else "TARGET_IP"
            default_val = get_default_value(env_var)
            new_line = f'{indent}{var_name}="${{{env_var}:-{default_val}}}"{comment}'
            new_lines.append(new_line)
            processed_variables.add(var_name) # Mark as processed
            modified = True
            processed = True
            logger.debug(f"Replaced specific IP: {var_name} -> {env_var}")

        match_specific_port = specific_port_regex.match(line)
        if not processed and match_specific_port and match_specific_port.group(2) not in processed_variables:
            indent, var_name, old_port, comment = match_specific_port.groups()
            comment = comment if comment else ""
            # Determine appropriate TARGET_<NAME>_PORT variable
            target_name = "DRONE" # Default guess
            if "GCS" in var_name: target_name = "GCS"
            elif "CAMERA" in var_name: target_name = "CAMERA"
            elif "COMPANION" in var_name: target_name = "COMPANION"
            elif var_name == "TARGET_PORT": target_name = None # Use generic TARGET_PORT

            env_var = f"TARGET_{target_name}_PORT" if target_name else "TARGET_PORT"
            default_val = get_default_value(env_var)
            new_line = f'{indent}{var_name}="${{{env_var}:-{default_val}}}"{comment}'
            new_lines.append(new_line)
            processed_variables.add(var_name) # Mark as processed
            modified = True
            processed = True
            logger.debug(f"Replaced specific Port: {var_name} -> {env_var}")


        # --- Check Generic IP/Port Patterns (if not processed by specific patterns) ---
        match_ip = ip_regex.match(line)
        # Avoid replacing common network/mask definitions, only likely target IPs
        potential_ip = match_ip.group(4) if match_ip else None
        is_likely_target_ip = potential_ip and (potential_ip.startswith('10.') or potential_ip.startswith('192.168.') or potential_ip.startswith('172.1'))

        if not processed and match_ip and is_likely_target_ip and match_ip.group(2) not in processed_variables:
            indent, var_name, quote, old_ip, comment = match_ip.groups()
            comment = comment if comment else ""
            # Heuristic: Guess the target type based on variable name or assume DRONE/GENERIC
            env_var = "TARGET_IP" # Default to generic
            if "DRONE" in var_name.upper(): env_var = "TARGET_DRONE_IP"
            elif "GCS" in var_name.upper(): env_var = "TARGET_GCS_IP"
            # Add more heuristics if needed

            default_val = get_default_value(env_var)
            new_line = f'{indent}{var_name}="${{{env_var}:-{default_val}}}"{comment}'
            new_lines.append(new_line)
            modified = True
            processed = True
            logger.debug(f"Replaced generic IP: {var_name} -> {env_var}")

        match_port = port_regex.match(line)
        # Check if the port is a common service port likely to be a target
        potential_port = int(match_port.group(3)) if match_port else 0
        is_likely_target_port = potential_port in [80, 443, 554, 14550, 14551, 5760, 5762, 5763, 8080, 22, 21, 23] # Add more?

        if not processed and match_port and is_likely_target_port and match_port.group(2) not in processed_variables:
            indent, var_name, old_port, comment = match_port.groups()
            comment = comment if comment else ""
             # Heuristic: Guess the target type based on variable name or assume DRONE/GENERIC
            env_var = "TARGET_PORT" # Default to generic
            if "DRONE" in var_name.upper(): env_var = "TARGET_DRONE_PORT"
            elif "GCS" in var_name.upper(): env_var = "TARGET_GCS_PORT"
            # Add more heuristics if needed

            default_val = get_default_value(env_var)
            new_line = f'{indent}{var_name}="${{{env_var}:-{default_val}}}"{comment}'
            new_lines.append(new_line)
            modified = True
            processed = True
            logger.debug(f"Replaced generic Port: {var_name} -> {env_var}")

        # If no pattern matched, keep the original line
        if not processed:
            new_lines.append(original_line)

    return "\n".join(new_lines), modified

def process_script(script_path: str):
    """Reads, modifies, and writes back a single script file."""
    logger.info(f"Processing script: {script_path}")
    try:
        # Create backup
        backup_path = script_path + ".bak"
        shutil.copy2(script_path, backup_path)
        logger.debug(f"Backup created: {backup_path}")

        # Read content
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            original_content = f.read()

        # Modify content
        modified_content, was_modified = modify_script_content(original_content)

        # Write back if modified
        if was_modified:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            logger.info(f"Modified: {script_path}")
        else:
            logger.info(f"No changes needed: {script_path}")
            # Optionally remove backup if no changes were made
            # os.remove(backup_path)

    except Exception as e:
        logger.error(f"Failed to process script {script_path}: {e}", exc_info=True)


# --- Main Loop ---
if __name__ == "__main__":
    found_scripts: List[str] = []
    for attack_dir in ATTACK_DIRS:
        abs_attack_dir = os.path.abspath(attack_dir)
        if not os.path.isdir(abs_attack_dir):
            logger.warning(f"Attack directory not found: {abs_attack_dir}")
            continue

        logger.info(f"Scanning directory: {abs_attack_dir}")
        for root, _, files in os.walk(abs_attack_dir):
            for file in files:
                if file.endswith(".sh"):
                    script_path = os.path.join(root, file)
                    found_scripts.append(script_path)

    if not found_scripts:
        logger.info("No .sh script files found in the specified directories.")
    else:
        logger.info(f"Found {len(found_scripts)} script files to process.")
        # Confirmation step (optional but recommended)
        # confirm = input(f"Proceed with modifying {len(found_scripts)} scripts? (y/N): ")
        # if confirm.lower() != 'y':
        #     logger.info("Operation cancelled by user.")
        #     sys.exit(0)

        for script in found_scripts:
            process_script(script)

        logger.info("Script modification process complete. Please review the changes.")
