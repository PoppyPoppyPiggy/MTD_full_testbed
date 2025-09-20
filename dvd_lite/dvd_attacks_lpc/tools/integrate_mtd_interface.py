#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import shutil
import sys

# --- 경로 설정 (스크립트 위치 기반으로 자동 설정) ---
TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, '..'))
ATTACKS_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki')
BACKUP_DIR = os.path.join(LPC_ROOT, 'modules', 'attacks_wiki_backup')

# --- MTD 인터페이스 템플릿 ---
# 오케스트레이터가 주입한 환경 변수가 존재하는지만 확인하는 간결한 템플릿입니다.
MTD_TEMPLATE = r"""
# MTD_INTERFACE_START
# =======================================================================
# MTD-aware Target Acquisition (from Orchestrator Environment)
# =======================================================================
# 이 스크립트는 attack_orchestrator.py에 의해 TARGET_IP와 TARGET_PORT 환경 변수가
# 설정될 것을 기대하고 실행됩니다.

if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "This script must be run via the attack_orchestrator.py" >&2
    exit 1
fi

echo "[INFO] Attack target acquired from orchestrator: ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END
"""

def restore_from_backup():
    """백업 디렉토리에서 원본 스크립트를 복원합니다."""
    if not os.path.exists(BACKUP_DIR):
        print(f"❌ 오류: 백업 디렉토리가 없습니다 '{BACKUP_DIR}'. 복원할 수 없습니다.")
        return False
    print(f"🔄 '{os.path.basename(BACKUP_DIR)}'에서 원본 스크립트를 복원합니다...")
    if os.path.exists(ATTACKS_DIR):
        shutil.rmtree(ATTACKS_DIR)
    shutil.copytree(BACKUP_DIR, ATTACKS_DIR)
    print("✅ 복원이 완료되었습니다.")
    return True

def create_backup():
    """기존 공격 스크립트 디렉토리를 백업합니다."""
    if not os.path.isdir(ATTACKS_DIR):
        print(f"❌ 오류: 공격 스크립트 디렉토리가 없습니다 '{ATTACKS_DIR}'.")
        sys.exit(1)
    if os.path.exists(BACKUP_DIR):
        print(f"ℹ️ 이미 백업이 존재합니다: '{os.path.basename(BACKUP_DIR)}'. 기존 백업을 사용합니다.")
        return
    print(f"📦 원본 스크립트를 '{os.path.basename(BACKUP_DIR)}'에 백업합니다...")
    shutil.copytree(ATTACKS_DIR, BACKUP_DIR)
    print("✅ 백업이 완료되었습니다.")

def find_injection_point(lines):
    """shebang 바로 다음, 주석이 아닌 첫 실행 코드 라인을 찾습니다."""
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() and not line.strip().startswith('#'):
            return i
    return len(lines)

def patch_script_logic(lines):
    """
    스크립트 라인을 분석하여 하드코딩된 IP/포트를 MTD 환경 변수로 교체합니다.
    """
    modified_lines = []
    # 공격 대상이 될 가능성이 높은 사설 IP 대역만 타겟으로 지정
    ip_pattern = re.compile(r'\b(10\.13\.0\.\d{1,3}|127\.0\.0\.1)\b')
    
    for line in lines:
        # 이미 MTD 변수가 포함된 라인은 변경하지 않음
        if '${TARGET_IP}' in line or '${TARGET_PORT}' in line:
            modified_lines.append(line)
            continue

        # 1. Python Here-doc ('python3 - <<PY') 처리 (가장 중요한 수정)
        # 'wiki_parse_attacks.py'는 Python 스크립트가 'ip:port' 형식의 단일 인자를 받도록 생성합니다.
        # 이 형식에 맞춰 단일 인자로 ${TARGET_IP}:${TARGET_PORT}를 전달합니다.
        if re.search(r"python3\s+-\s+.*<<'PY'?", line):
            modified_line = re.sub(
                r"python3\s+-.*<<'PY'?", 
                'python3 - "${TARGET_IP}:${TARGET_PORT}" <<\'PY\'', 
                line
            )
            modified_lines.append(modified_line)
            continue
            
        # 2. mavproxy, hping3 등 포트와 IP가 명확히 구분되는 명령어 처리
        # --master udp:10.13.0.3:14550 -> --master udp:${TARGET_IP}:${TARGET_PORT}
        line = re.sub(r'(--master(?:=|\s+))\w+:([0-9\.]+):(\d+)', r'\1udp:${TARGET_IP}:${TARGET_PORT}', line)
        # -p 14550 10.13.0.3 -> -p ${TARGET_PORT} ${TARGET_IP}
        line = re.sub(r'(-p\s+)\d+(\s+)' + ip_pattern.pattern, r'\1${TARGET_PORT}\2${TARGET_IP}', line)
        
        # 3. netcat(nc) 등 IP와 포트 순서가 중요한 명령어 처리
        # nc -u 10.13.0.3 14550 -> nc -u ${TARGET_IP} ${TARGET_PORT}
        line = re.sub(r'(nc\s+(?:-u\s+)?|ncat\s+(?:--udp\s+)?)' + ip_pattern.pattern + r'(\s+)\d+', r'\1${TARGET_IP}\2${TARGET_PORT}', line)

        # 4. 위에서 처리되지 않은 나머지 IP들을 일괄적으로 교체
        line = ip_pattern.sub(r'${TARGET_IP}', line)
        
        modified_lines.append(line)
        
    return modified_lines

def process_script(script_path):
    """단일 스크립트 파일을 읽고, 패치하고, 다시 씁니다."""
    filename = os.path.basename(script_path)
    print(f"- 처리 중: {filename}...")

    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if any("MTD_INTERFACE_START" in line for line in lines):
            print("  -> ℹ️ 이미 패치되었습니다. 건너뜁니다.")
            return

        injection_point = find_injection_point(lines)
        template_lines = (MTD_TEMPLATE + '\n').splitlines(keepends=True)
        
        # 템플릿 삽입 전/후로 라인 분리
        lines_before_injection = lines[:injection_point]
        lines_after_injection = lines[injection_point:]

        # 템플릿 이후 코드만 패치
        patched_logic = patch_script_logic(lines_after_injection)
        
        # 전체 코드 재조합
        final_lines = lines_before_injection + template_lines + patched_logic

        with open(script_path, 'w', encoding='utf-8') as f:
            f.writelines(final_lines)
            
        print("  -> ✅ 성공적으로 패치되었습니다.")

    except Exception as e:
        print(f"  -> ❌ 오류: '{filename}' 처리 중 문제가 발생했습니다. 원인: {e}", file=sys.stderr)
        # 오류 발생 시 원본으로 자동 롤백
        try:
            shutil.copyfile(os.path.join(BACKUP_DIR, filename), script_path)
            print(f"  -> 롤백: 원본 파일 '{filename}'을(를) 복원했습니다.")
        except Exception as e_rb:
            print(f"  -> ❌ 롤백 실패: {e_rb}", file=sys.stderr)

def main():
    print("=" * 60)
    print(" MTD-Aware Attack Script Patcher (v3.0 - Wiki Parser-Compatible)")
    print(" (Orchestrator-compatible Environment Variable Integration)")
    print("=" * 60)

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
    print(f"python3 {os.path.relpath(__file__)} --restore")

if __name__ == "__main__":
    main()