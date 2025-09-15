import os
import re
import shutil
import sys
import time

# --- 설정 ---
TOOLS_DIR = os.path.dirname(__file__)
LPC_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, '..'))
ATTACKS_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki')
BACKUP_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki_backup')

# MTD 인터페이스 및 로깅 템플릿
MTD_TEMPLATE = """
# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

# 중앙 로거 함수 정의 (정확한 타임스탬프를 위해 쉘의 log 함수와 통합)
log() {{
    # 쉘 표준 로그 출력
    printf '[%(%F_%T)T] %s\\n' -1 "$*"

    # bus.log에 JSON 이벤트 로깅
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c "from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; log_bus_event('$EVENT_TYPE', {{'message': '$EVENT_DATA_STR'}})"
    popd > /dev/null
}}
# MTD_INTERFACE_END
"""

# (이전과 동일한 restore_from_backup, create_backup, find_injection_point 함수)
def restore_from_backup():
    if not os.path.exists(BACKUP_DIR):
        print("ERROR: Backup directory not found.")
        return False
    print(f"Restoring from '{os.path.basename(BACKUP_DIR)}'...")
    if os.path.exists(ATTACKS_DIR): shutil.rmtree(ATTACKS_DIR)
    shutil.copytree(BACKUP_DIR, ATTACKS_DIR)
    print("Restore complete.")
    return True

def create_backup():
    if os.path.exists(BACKUP_DIR):
        print(f"Backup directory already exists.")
        return
    print(f"Creating backup in: {os.path.basename(BACKUP_DIR)}")
    shutil.copytree(ATTACKS_DIR, BACKUP_DIR)
    print("Backup complete.")

def find_injection_point(lines):
    for i, line in enumerate(lines):
        if i > 0 and not line.strip().startswith('#') and line.strip():
            return i
    return 1

def patch_script_logic(lines):
    modified_lines = []
    # 파이썬 here-doc 실행 패턴
    python_heredoc_pattern = re.compile(r"python3\s+-\s+.*<<'?PY'?")
    # 일반적인 쉘 명령 실행 패턴
    generic_cmd_pattern = re.compile(r'^\s*(sudo)?\s*(python3|nmap|hping3|arp-scan|netcat|nc|mavproxy.py)')
    # 하드코딩된 IP 주소 패턴
    ip_pattern = re.compile(r'\b\d{1,3}(\.\d{1,3}){3}\b')
    # 기존 log 함수 정의 패턴
    log_func_pattern = re.compile(r'log\(\)\s*\{')

    for line in lines:
        # 기존 log() 함수 정의는 삭제 (MTD_TEMPLATE의 것으로 대체)
        if log_func_pattern.search(line):
            continue
        # 파이썬 here-doc 수정
        if python_heredoc_pattern.search(line):
            modified_line = 'python3 - "${TARGET_IP}:${TARGET_PORT}" <<PY\n'
            modified_lines.append(modified_line)
            continue
        # 일반 쉘 명령어의 하드코딩된 IP를 동적 변수로 교체
        if generic_cmd_pattern.search(line):
            line = ip_pattern.sub(r'${TARGET_IP}', line)
        modified_lines.append(line)
        
    return modified_lines

def process_script(script_path):
    filename = os.path.basename(script_path)
    print(f"Processing: {filename}...")
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if any("MTD_INTERFACE_START" in line for line in lines):
            print("  -> Already patched. Skipping.")
            return

        lines = patch_script_logic(lines)
        injection_point = find_injection_point(lines)
        lines.insert(injection_point, MTD_TEMPLATE)
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("  -> Successfully patched.")
    except Exception as e:
        print(f"  -> ERROR: Could not process script. Reason: {e}")

def main():
    print("=====================================================")
    print(" MTD Interface Integration Script (Orchestrator Ready)")
    print("=====================================================")
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        restore_from_backup()
        return
    create_backup()
    for filename in sorted(os.listdir(ATTACKS_DIR)):
        if filename.endswith(".sh"):
            script_path = os.path.join(ATTACKS_DIR, filename)
            process_script(script_path)
    print("\nAutomation complete.")
    print("To restore, run: python3 tools/integrate_mtd_interface.py --restore")

if __name__ == "__main__":
    main()