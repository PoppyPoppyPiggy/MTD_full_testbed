# dvd_lite/dvd_attacks_lpc/tools/generate_attack_profiles.py

import os
import json
import re

# --- 경로 문제 해결을 위한 최종 버전 ---
# 이 스크립트 파일의 실제 위치에 대한 절대 경로를 찾습니다.
try:
    # __file__ 변수는 이 스크립트 파일의 경로를 나타냅니다.
    # ex: /home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/tools/generate_attack_profiles.py
    SCRIPT_REAL_PATH = os.path.realpath(__file__)
    
    # 이 스크립트가 있는 'tools' 디렉토리의 경로를 얻습니다.
    # ex: /home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/tools
    TOOLS_DIR = os.path.dirname(SCRIPT_REAL_PATH)
    
    # 'tools'에서 세 단계 위로 올라가 프로젝트 루트 디렉토리('MTD_full_testbed/')를 찾습니다.
    # os.path.dirname()을 세 번 호출합니다.
    # 1. .../dvd_attacks_lpc/
    # 2. .../dvd_lite/
    # 3. /home/kali/MTD_full_testbed/
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(TOOLS_DIR)))

except NameError:
    # 스크립트가 아닌 대화형 환경에서 실행될 경우, 현재 작업 디렉토리를 기준으로 합니다.
    # 이 경우, 프로젝트 루트에서 실행해야 정확합니다.
    PROJECT_ROOT = os.getcwd()
    print("⚠️ 경고: __file__을 찾을 수 없습니다. 현재 디렉토리를 프로젝트 루트로 가정합니다.")
    print(f"현재 디렉토리: {PROJECT_ROOT}")


# 이제 모든 경로를 올바르게 계산된 프로젝트 루트로부터의 절대 경로로 안전하게 생성합니다.
ATTACKS_WIKI_DIR = os.path.join(PROJECT_ROOT, 'dvd_lite', 'dvd_attacks_lpc', 'modules', 'attacks_wiki')
WIKI_DOCS_DIR = os.path.join(PROJECT_ROOT, 'Damn-Vulnerable-Drone.wiki')
OUTPUT_PATH = os.path.join(ATTACKS_WIKI_DIR, 'attack_profiles.json')
# --- 경로 설정 완료 ---


# LPC 공격으로 분류할 키워드
LPC_KEYWORDS = ['slow', 'trickle', 'poll', 'noise', 'scan', 'tease', 'exfil']

# 각 공격에 대한 성공 조건을 미리 상세하게 정의 (한국어)
# 'value'는 비교 기준값입니다. 예를 들어 attitude_unstable의 value는 불안정으로 판단할 roll/pitch의 최대 절대값(라디안)입니다.
PREDEFINED_SUCCESS_CONDITIONS = {
    "attitude-spoofing.sh": {
        "condition": { "source": "bus_dvd.log", "metric": "attitude_unstable", "value": 1.0, "window_seconds": 15 }
    },
    "battery-spoofing.sh": {
        "condition": { "source": "bus_dvd.log", "metric": "battery_remaining", "operator": "<=", "value": 5, "window_seconds": 10 }
    },
    "communication-link-flooding.sh": {
        "condition": { "source": "bus_dvd.log", "metric": "system_status", "operator": "==", "value": "MAV_STATE_CRITICAL", "window_seconds": 20 }
    },
    "critical-error-spoofing.sh": {
        "condition": { "source": "bus_dvd.log", "metric": "system_status", "operator": "==", "value": "MAV_STATE_FLIGHT_TERMINATION", "window_seconds": 10 }
    },
    "flight-termination.sh": {
        "condition": { "source": "bus_dvd.log", "metric": "armed", "operator": "==", "value": False, "window_seconds": 5 }
    },
    "gps-spoofing.sh": {
        "condition": { "source": "bus_dvd.log", "metric": "position_drift_m", "operator": ">=", "value": 15, "window_seconds": 20 }
    },
    "waypoint-injection.sh": {
        "condition": { "source": "bus.log", "metric": "mission_items_uploaded", "operator": ">=", "value": 3, "window_seconds": 25 }
    },
    "gps_slow_spoof.sh": {
        "type": "LPC", "required_duration_seconds": 45,
        "condition": { "source": "bus_dvd.log", "metric": "position_drift_m", "operator": ">=", "value": 20, "window_seconds": 60 }
    },
    "mavlink_mission_trickle.sh": {
        "type": "LPC", "required_duration_seconds": 90,
        "condition": { "source": "bus.log", "metric": "mission_items_uploaded", "operator": ">=", "value": 5, "window_seconds": 120 }
    }
}

def parse_wiki_description(attack_name):
    """위키 파일(.md)에서 공격 설명을 파싱합니다."""
    md_name = attack_name.replace('.sh', '.md').replace('-', ' ').title().replace(' ', '-')
    md_path = os.path.join(WIKI_DOCS_DIR, md_name)

    if not os.path.exists(md_path):
        return f"{attack_name}에 대한 위키 문서를 찾을 수 없습니다. 설명을 수동으로 추가해주세요."

    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'^#.*?$.*?\n\n(.*?)\n\n', content, re.MULTILINE | re.DOTALL)
            if match:
                description = match.group(1).strip().replace('\n', ' ')
                description = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', description)
                return description
            return "위키에서 설명을 자동으로 추출하지 못했습니다."
    except Exception as e:
        return f"위키 파일 파싱 오류: {e}"

def main():
    """메인 프로필 생성 함수"""
    print("--- 공격 프로필 생성기 시작 ---")
    print(f"프로젝트 루트: {PROJECT_ROOT}")
    print(f"공격 스크립트 검색 경로: {ATTACKS_WIKI_DIR}")
    print(f"위키 문서 검색 경로: {WIKI_DOCS_DIR}")
    
    attack_profiles = {}
    
    if not os.path.isdir(ATTACKS_WIKI_DIR):
        print(f"❌ 오류: 공격 스크립트 디렉토리를 찾을 수 없습니다. 경로가 올바른지 확인하세요.")
        return

    attack_files = sorted([f for f in os.listdir(ATTACKS_WIKI_DIR) if f.endswith('.sh')])
    if not attack_files:
        print(f"⚠️ 경고: {ATTACKS_WIKI_DIR} 에서 실행할 공격 스크립트(.sh)를 찾지 못했습니다.")
        return

    for attack_file in attack_files:
        profile = PREDEFINED_SUCCESS_CONDITIONS.get(attack_file, {})
        
        profile["description"] = parse_wiki_description(attack_file)
        
        if "type" not in profile:
            is_lpc = any(keyword in attack_file.lower() for keyword in LPC_KEYWORDS)
            profile['type'] = 'LPC' if is_lpc else 'IMMEDIATE'

        if profile['type'] == 'LPC' and 'required_duration_seconds' not in profile:
            profile['required_duration_seconds'] = 60

        if 'condition' not in profile:
            profile['condition'] = {
                "source": "bus.log", "metric": "unknown_success_metric",
                "value": "please_define", "window_seconds": 30
            }

        attack_profiles[attack_file] = profile

    try:
        # 출력 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(attack_profiles, f, indent=4, ensure_ascii=False)
        print(f"\n✅ 공격 프로필 생성이 완료되었습니다. 총 {len(attack_profiles)}개의 공격이 정의되었습니다.")
        print(f"   -> 결과 파일: {OUTPUT_PATH}")
    except IOError as e:
        print(f"\n❌ 오류: 프로필 파일을 저장할 수 없습니다: {e}")

if __name__ == "__main__":
    main()