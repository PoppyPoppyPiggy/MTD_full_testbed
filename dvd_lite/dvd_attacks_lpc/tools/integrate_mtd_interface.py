# dvd_lite/dvd_attacks_lpc/tools/integrate_mtd_interface.py

import os
import re
import shutil
import sys
import time

# --- 경로 설정 (스크립트 위치 기반으로 자동 설정) ---
TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, '..'))
ATTACKS_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki')
BACKUP_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki_backup')

# MTD 인터페이스 및 로깅 템플릿 (PYTHONPATH 문제 해결)
MTD_TEMPLATE = r"""
# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../..")

# --- Python Module Path FIX ---
# 파이썬이 우리 모듈을 찾을 수 있도록 프로젝트 루트를 PYTHONPATH에 추가합니다.
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
# MTD 인터페이스 모듈 직접 실행
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo "$TARGET_ADDR" | cut -d: -f1)
TARGET_PORT=14550 # SITL의 기본 UDP 포트

# 중앙 로거 함수 정의
log() {
    printf '[%(%F_T)T] %s\n' -1 "$*"
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c 'from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; import sys; log_bus_event(sys.argv[1], {"message": sys.argv[2]})' "$EVENT_TYPE" "$EVENT_DATA_STR"
    popd > /dev/null
}
# MTD_INTERFACE_END
"""

# (이전과 동일한 restore_from_backup, create_backup 등 나머지 함수들...)
def restore_from_backup():
    if not os.path.exists(BACKUP_DIR):
        print("❌ 오류: 백업 디렉토리가 없습니다. 복원할 수 없습니다.")
        return False
    print(f"🔄 '{os.path.basename(BACKUP_DIR)}'에서 원본 스크립트를 복원합니다...")
    if os.path.exists(ATTACKS_DIR): shutil.rmtree(ATTACKS_DIR)
    shutil.copytree(BACKUP_DIR, ATTACKS_DIR)
    print("✅ 복원이 완료되었습니다.")
    return True

def create_backup():
    if os.path.exists(BACKUP_DIR):
        print(f"이미 백업이 존재합니다: '{os.path.basename(BACKUP_DIR)}'")
        return
    print(f"📦 원본 스크립트를 '{os.path.basename(BACKUP_DIR)}'에 백업합니다...")
    shutil.copytree(ATTACKS_DIR, BACKUP_DIR)
    print("✅ 백업이 완료되었습니다.")

def find_injection_point(lines):
    for i, line in enumerate(lines[1:], start=1):
        if not line.strip().startswith('#') and line.strip():
            return i
    return len(lines)

def patch_script_logic(lines):
    modified_lines = []
    python_heredoc_pattern = re.compile(r"python3\s+-\s+.*<<'?PY'?")
    generic_cmd_pattern = re.compile(r'^\s*(sudo)?\s*(python3|nmap|hping3|arp-scan|netcat|nc|mavproxy.py)')
    ip_pattern = re.compile(r'\b\d{1,3}(\.\d{1,3}){3}\b')
    log_func_pattern = re.compile(r'log\(\)\s*\{')

    for line in lines:
        if log_func_pattern.search(line):
            continue
        if python_heredoc_pattern.search(line):
            modified_line = 'python3 - "${TARGET_IP}:${TARGET_PORT}" <<PY\n'
            modified_lines.append(modified_line)
            continue
        if generic_cmd_pattern.search(line):
            line = ip_pattern.sub(r'${TARGET_IP}', line)
        modified_lines.append(line)
    return modified_lines

def process_script(script_path):
    filename = os.path.basename(script_path)
    print(f"- 처리 중: {filename}...")
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if any("MTD_INTERFACE_START" in line for line in lines):
            print("  -> 이미 패치되었습니다. 건너뜁니다.")
            return
        lines = patch_script_logic(lines)
        injection_point = find_injection_point(lines)
        lines.insert(injection_point, MTD_TEMPLATE)
        with open(script_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("  -> ✅ 성공적으로 패치되었습니다.")
    except Exception as e:
        print(f"  -> ❌ 오류: 스크립트 처리 중 문제가 발생했습니다. 원인: {e}")

def main():
    print("=" * 53)
    print(" MTD 인터페이스 통합 스크립트 (PYTHONPATH 문제 해결)")
    print("=" * 53)
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        restore_from_backup()
        return
    create_backup()
    scripts_to_process = sorted([f for f in os.listdir(ATTACKS_DIR) if f.endswith(".sh")])
    if not scripts_to_process:
        print("\n⚠️ 경고: 패치할 공격 스크립트(.sh)가 없습니다.")
        return
    print("\n공격 스크립트 패치를 시작합니다...")
    for filename in scripts_to_process:
        script_path = os.path.join(ATTACKS_DIR, filename)
        process_script(script_path)
    print("\n모든 작업이 완료되었습니다.")
    print("원본으로 되돌리려면 아래 명령어를 실행하세요:")
    print("python3 dvd_lite/dvd_attacks_lpc/tools/integrate_mtd_interface.py --restore")

if __name__ == "__main__":
    main()