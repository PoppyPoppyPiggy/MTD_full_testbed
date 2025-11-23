#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
attack_code_refactor.py
- modules/attacks_wiki/*.sh 파일들을 스캔하여 하드코딩된 IP/Port를 역할별 환경변수로 정교하게 치환합니다.
- Docker Compose 정의에 기반한 역할 매핑:
  - 10.13.0.2 (Flight Controller) -> ${TARGET_FC} / target_fc
  - 10.13.0.3 (Companion Computer) -> ${TARGET_CC} / target_cc
  - 10.13.0.4 (GCS) -> ${TARGET_GCS} / target_gcs
  - 10.13.0.5 (Simulator) -> ${TARGET_SIM} / target_sim
  - 10.13.0.6 (Attacker Self IP) -> ${ATTACKER_SRC} / attacker_src
  - 127.0.0.1 (Localhost/Generic) -> ${TARGET_IP} / target_ip
- 서비스 포트 매핑:
  - 14550 (MAVLink) -> ${PORT_MAVLINK}
  - 5760 (SITL TCP) -> ${PORT_SITL}
  - 554 (RTSP) -> ${PORT_RTSP}
  - 11311 (ROS) -> ${PORT_ROS}
"""

import os
import re
import sys
from pathlib import Path

# 경로 설정
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ATTACKS_DIR = SCRIPT_DIR.parent / "modules" / "attacks_wiki"

# ---------------------------------------------------------
# 1. 치환 규칙 정의 (우선순위 중요: 구체적인 IP부터 매칭)
# 구조: (Regex Pattern, Shell Var, Python Env Getter Code)
# ---------------------------------------------------------
REPLACEMENTS = [
    # --- Specific Roles (Docker IPs) ---
    (r"10\.13\.0\.2", "${TARGET_FC}", "os.environ.get('TARGET_FC', '10.13.0.2')"),
    (r"10\.13\.0\.3", "${TARGET_CC}", "os.environ.get('TARGET_CC', '10.13.0.3')"),
    (r"10\.13\.0\.4", "${TARGET_GCS}", "os.environ.get('TARGET_GCS', '10.13.0.4')"),
    (r"10\.13\.0\.5", "${TARGET_SIM}", "os.environ.get('TARGET_SIM', '10.13.0.5')"),
    
    # --- Attacker Self IP ---
    # 공격자가 자기 자신을 지칭하는 경우 (예: bind address 등)
    (r"10\.13\.0\.6", "${ATTACKER_SRC}", "os.environ.get('ATTACKER_SRC', '10.13.0.6')"),
    
    # --- WiFi Interfaces ---
    (r"192\.168\.13\.1", "${TARGET_CC_WIFI}", "os.environ.get('TARGET_CC_WIFI', '192.168.13.1')"),
    
    # --- Fallbacks / Generic ---
    # 127.0.0.1은 보통 로컬 테스트용이므로 일반 TARGET_IP로 매핑하되, 기본값 유지
    (r"127\.0\.0\.1", "${TARGET_IP}", "os.environ.get('TARGET_IP', '127.0.0.1')"),
    
    # --- Ports ---
    # 숫자만 매칭되면 위험하므로, 앞뒤 경계(\b) 처리 또는 문맥 고려 필요하지만
    # 공격 스크립트 특성상 해당 숫자는 포트일 확률이 매우 높음.
    (r"\b14550\b", "${PORT_MAVLINK}", "int(os.environ.get('PORT_MAVLINK', '14550'))"),
    (r"\b5760\b",  "${PORT_SITL}",    "int(os.environ.get('PORT_SITL', '5760'))"),
    (r"\b554\b",   "${PORT_RTSP}",    "int(os.environ.get('PORT_RTSP', '554'))"),
    (r"\b3000\b",  "${PORT_WEB}",     "int(os.environ.get('PORT_WEB', '3000'))"),
    (r"\b11311\b", "${PORT_ROS}",     "int(os.environ.get('PORT_ROS', '11311'))"),
]

def refactor_content(content: str) -> str:
    """
    전체 파일 내용을 받아서 Shell 부분과 Python 부분을 구분하여 리팩토링 수행
    """
    # Python Here-doc 블록 분리 (python3 - <<'PY' ... PY)
    # 정규식으로 블록을 캡처하고, 나머지는 Shell로 처리
    parts = re.split(r"(python3\s+-\s+<<'PY'.*?^PY$)", content, flags=re.DOTALL | re.MULTILINE)
    
    new_parts = []
    
    for part in parts:
        if part.strip().startswith("python3 - <<'PY'"):
            # === Python Block 처리 ===
            py_code = part
            
            # 1. String literal replacement logic updated
            # Instead of blindly replacing inside strings which causes syntax errors like:
            # 'udp:127.0.0.1:int(os.environ...)'
            # We will handle string literals more carefully.

            # Simple logic: Only replace exact matches in string literals if they are just the IP
            # For port numbers, do NOT replace if they are inside quotes (e.g., '14550') unless it's an assignment.
            
            # However, fixing the specific error seen:
            # The error line is: ep = ... 'udp:127.0.0.1:14550'
            # We should replace this entire string with an f-string construction or avoid touching this specific prologue line
            # if we can't do it safely.
            
            # Better strategy for Python block:
            # 1. Replace full IP string literals: "10.13.0.2" -> os.environ.get('...', '...')
            # 2. Replace integer literals: 14550 -> int(os.environ.get('...', '...'))
            # 3. SKIP replacement if the text is part of a larger string like "udp:127.0.0.1:14550"
            #    UNLESS we parse it properly.
            
            # To act essentially, we will iterate replacements but be careful about context.
            
            for pat, _, py_env_code in REPLACEMENTS:
                # 1. Exact IP String Literals: "10.13.0.2" or '10.13.0.2'
                # We replace the whole string literal with the code
                if "int(" not in py_env_code: # It's an IP replacement
                    py_code = re.sub(f"['\"]{pat}['\"]", py_env_code, py_code)

                # 2. Integer Ports
                # Only replace if it looks like an integer (not inside quotes)
                # Use lookarounds to ensure it's not inside quotes is hard with simple regex.
                # Instead, we'll rely on the fact that ports are usually passed as ints in these scripts
                # OR they are separate args.
                
                if "int(" in py_env_code:
                    # Replace: port = 14550  --> port = int(os.environ...)
                    # Avoid replacing inside '14550' string
                    
                    # Look for number not surrounded by quotes.
                    # This regex matches the number ONLY if it is NOT preceded or followed by a quote
                    # simplified check: word boundary is usually enough for code like `port = 14550`
                    
                    # But wait, the specific error was inside `os.environ.get(..., 'udp:127.0.0.1:14550')`
                    # The 14550 here IS inside quotes.
                    # We should AVOID touching the prologue code if possible, or fix the regex to not touch
                    # numbers inside existing string literals if they are part of a colon-separated string.
                    
                    # Strategy: Do NOT replace numbers if they are preceded by a colon inside a string?
                    # Easier fix: Just don't touch the prologue lines.
                    pass 
            
            # Apply Port replacements specifically for assignments or standalone usage
            for pat_raw, _, py_env_code in REPLACEMENTS:
                if "int(" in py_env_code:
                     # Only replace ` 14550 ` or `=14550` or `(14550` etc.
                     # Exclude if part of a string like :14550
                     
                     # Regex: (lookbehind for space, =, (, [) PAT (lookahead for space, comma, ), ], newline)
                     # This prevents matching inside 'udp:127.0.0.1:14550'
                     
                     # Clean pattern from raw string
                     clean_pat = pat_raw.replace(r"\b", "")
                     
                     safe_pattern = r"(?<=[\s=\(\[,])" + clean_pat + r"(?=[\s,\)\]]|$)"
                     py_code = re.sub(safe_pattern, py_env_code, py_code)

            new_parts.append(py_code)
            
        else:
            # === Shell Block 처리 ===
            sh_code = part
            for pat, sh_var, _ in REPLACEMENTS:
                # Shell에서는 단순히 해당 패턴을 ${VAR}로 변경
                sh_code = re.sub(pat, sh_var, sh_code)
                
                # CIDR 패턴 처리 (예: 10.13.0.0/24)
                if "10.13.0" in pat:
                     sh_code = sh_code.replace("10.13.0.0/24", "${TARGET_SUBNET:-10.13.0.0/24}")
            
            new_parts.append(sh_code)

    return "".join(new_parts)

def refactor_file(file_path: Path):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return

    refactored = refactor_content(content)

    if content != refactored:
        try:
            file_path.write_text(refactored, encoding="utf-8")
            print(f"[UPDATED] {file_path.name}")
        except Exception as e:
            print(f"[ERROR] Failed to write {file_path}: {e}")
    else:
        print(f"[SKIP] {file_path.name} (No matching patterns found)")

def main():
    if not ATTACKS_DIR.exists():
        print(f"[ERROR] Directory not found: {ATTACKS_DIR}")
        sys.exit(1)

    print(f"Scanning directory: {ATTACKS_DIR}")
    print("Refactoring hardcoded IPs/Ports to role-based env vars...")
    print("Mappings applied based on docker-compose-lite.yaml:")
    for pat, var, _ in REPLACEMENTS:
        print(f"  - {pat} -> {var}")
    
    for sh_file in sorted(ATTACKS_DIR.glob("*.sh")):
        refactor_file(sh_file)
        
    print("\nRefactoring complete. Please verify the scripts.")

if __name__ == "__main__":
    main()