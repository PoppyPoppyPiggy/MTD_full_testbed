import os
import re
import shutil
import sys

# --- 설정 ---
# 이 스크립트 파일의 위치를 기준으로 경로를 설정합니다.
TOOLS_DIR = os.path.dirname(__file__)
LPC_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, '..'))

# MTD 인터페이스를 적용할 공격 스크립트들이 있는 디렉터리
ATTACKS_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki')
# 원본 스크립트를 백업할 디렉터리
BACKUP_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki_backup')

# 각 셸 스크립트에 삽입될 MTD 인터페이스 코드 템플릿 (sudo 문제를 해결한 최종 버전)
MTD_TEMPLATE = """
# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition
# This block dynamically queries the MTD interface for an active target.
# ==========================================================
echo "INFO: Querying MTD interface for active target..."

# --- Project Root Resolution ---
# 1. 현재 실행되는 쉘 스크립트의 실제 위치를 찾습니다.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# 2. 'dvd_lite' 폴더를 포함하는 프로젝트 루트 디렉토리를 찾습니다. (현재 위치에서 4단계 위)
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")
# -----------------------------

# PYTHONPATH 환경 변수 대신, 직접 프로젝트 루트로 이동하여 파이썬 모듈을 실행합니다.
# 이 방식은 'sudo'가 환경 변수를 초기화하는 문제를 우회할 수 있어 더 안정적입니다.
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
popd > /dev/null

if [ $? -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

# 콜론을 기준으로 IP와 PORT를 분리하여 변수에 저장합니다.
TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

echo "INFO: Active target acquired -> ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END
"""

def restore_from_backup():
    """백업 디렉토리에서 원본 스크립트를 복원합니다."""
    if not os.path.exists(BACKUP_DIR):
        print("ERROR: Backup directory not found. Cannot restore.")
        return False
    
    print(f"Restoring original scripts from '{os.path.basename(BACKUP_DIR)}'...")
    # 기존 공격 디렉토리 삭제
    if os.path.exists(ATTACKS_DIR):
        shutil.rmtree(ATTACKS_DIR)
    
    # 백업에서 원본으로 복사
    shutil.copytree(BACKUP_DIR, ATTACKS_DIR)
    print("Restore complete. The attack scripts are now in their original state.")
    return True

def create_backup():
    """안전을 위해 원본 공격 스크립트들을 백업합니다."""
    if os.path.exists(BACKUP_DIR):
        print(f"Backup directory already exists at: {os.path.basename(BACKUP_DIR)}")
        return
    
    print(f"Creating backup of original scripts in: {os.path.basename(BACKUP_DIR)}")
    shutil.copytree(ATTACKS_DIR, BACKUP_DIR)
    print("Backup complete.")

def find_injection_point(lines):
    """MTD 템플릿 코드를 삽입할 최적의 위치를 찾습니다."""
    injection_point = 1  # shebang (#!) 바로 다음 줄을 기본값으로 설정
    for i, line in enumerate(lines):
        if line.strip().startswith('#') or not line.strip():
            continue
        injection_point = i
        break
    return injection_point

def comment_out_and_replace_static_targets(lines):
    """기존의 정적 타겟 변수 선언을 주석 처리하고, 실행부를 동적 변수로 교체합니다."""
    modified_lines = []
    static_target_patterns = [
        re.compile(r'^\s*TARGET_IP\s*='),
        re.compile(r'^\s*TARGET_HOST\s*='),
        re.compile(r'^\s*DRONE_IP\s*='),
        re.compile(r'^\s*GCS_IP\s*=')
    ]
    hardcoded_ip_port_pattern = re.compile(r'\b\d{1,3}(\.\d{1,3}){3}:\d+\b')

    for line in lines:
        is_static_target_declaration = False
        for pattern in static_target_patterns:
            if pattern.search(line):
                modified_lines.append(f"# [MTD AUTOPATCH] {line.strip()}\n")
                is_static_target_declaration = True
                break
        if is_static_target_declaration:
            continue

        line = hardcoded_ip_port_pattern.sub(r'${TARGET_IP}:${TARGET_PORT}', line)
        modified_lines.append(line)
        
    return modified_lines

def process_script(script_path):
    """단일 공격 스크립트를 읽고, 수정하고, 다시 씁니다."""
    print(f"Processing: {os.path.basename(script_path)}...")
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if any("MTD_INTERFACE_START" in line for line in lines):
            print("  -> Already patched. Skipping.")
            return

        lines = comment_out_and_replace_static_targets(lines)
        injection_point = find_injection_point(lines)
        lines.insert(injection_point, MTD_TEMPLATE + "\n")
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        print("  -> Successfully patched.")

    except Exception as e:
        print(f"  -> ERROR: Could not process script. Reason: {e}")


def main():
    print("=====================================================")
    print(" MTD Interface Integration Automation Script ")
    print("=====================================================")
    
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        restore_from_backup()
        return
        
    if not os.path.exists(ATTACKS_DIR):
        print(f"Error: Attacks directory not found at '{ATTACKS_DIR}'")
        return
        
    create_backup()
    
    for filename in sorted(os.listdir(ATTACKS_DIR)):
        if filename.endswith(".sh"):
            script_path = os.path.join(ATTACKS_DIR, filename)
            process_script(script_path)
            
    print("\nAutomation complete.")
    print(f"Original files are backed up in '{os.path.basename(BACKUP_DIR)}'.")
    print("To restore original scripts, run: python3 tools/integrate_mtd_interface.py --restore")

if __name__ == "__main__":
    main()