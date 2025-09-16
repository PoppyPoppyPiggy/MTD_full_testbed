# tools/evaluate_attack_success.py

import json
import argparse
import os
import math
from datetime import datetime, timedelta

# --- 경로 설정 ---
SCRIPT_REAL_PATH = os.path.realpath(__file__)
TOOLS_DIR = os.path.dirname(SCRIPT_REAL_PATH)
LPC_DIR = os.path.join(os.path.dirname(TOOLS_DIR), 'dvd_attacks_lpc')
BUS_DIR = os.path.join(LPC_DIR, 'bus')
ATTACKS_DIR = os.path.join(LPC_DIR, 'modules', 'attacks_wiki')
# --- 경로 설정 완료 ---

def parse_iso_timestamp(ts_str):
    """ISO 8601 형식의 문자열을 datetime 객체로 변환합니다."""
    if not ts_str: return None
    try:
        if '+' not in ts_str and 'Z' not in ts_str.upper():
            ts_str += 'Z'
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except ValueError:
        return None

def load_log_file(log_path):
    """JSONL 로그 파일을 로드하여 리스트로 반환합니다."""
    events = []
    if not os.path.exists(log_path):
        return events
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line)
                event['timestamp_dt'] = parse_iso_timestamp(event.get('timestamp'))
                if event['timestamp_dt']:
                    events.append(event)
            except (json.JSONDecodeError, KeyError):
                continue
    return events

def haversine(lat1, lon1, lat2, lon2):
    """두 위도/경도 지점 간의 거리를 미터(m) 단위로 계산합니다."""
    R = 6371000  # 지구 반지름 (미터)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def check_operator(val1, op, val2):
    """문자열 연산자에 따라 두 값을 비교합니다."""
    if val1 is None: return False
    ops = {
        '==': val1 == val2, '!=': val1 != val2,
        '>=': val1 >= val2, '<=': val1 <= val2,
        '>': val1 > val2, '<': val1 < val2
    }
    return ops.get(op, False)

def check_success_condition(start_event, all_events, profile):
    """공격 성공 조건을 만족하는지 종합적으로 판단합니다."""
    condition = profile.get('condition', {})
    if not condition: return False, "NO_CONDITION_DEFINED"

    start_time = start_event['timestamp_dt']
    window_sec = condition.get('window_seconds', 30)
    end_time = start_time + timedelta(seconds=window_sec)
    
    # 공격의 실제 종료 시간 (MTD 또는 정상 종료) 찾기
    end_event = next((e for e in all_events if e['timestamp_dt'] > start_time and e.get('type') in ['attack_stop', 'mtd_start']), None)

    # LPC 공격의 경우, 최소 실행 시간을 만족했는지 먼저 확인
    if profile.get('type') == 'LPC':
        required_sec = profile.get('required_duration_seconds', 60)
        if end_event and end_event.get('type') == 'mtd_start':
            actual_duration = (end_event['timestamp_dt'] - start_time).total_seconds()
            if actual_duration < required_sec:
                return False, f"LPC_INTERRUPTED_BY_MTD (ran for {actual_duration:.1f}s, required {required_sec}s)"

    initial_pos = None
    
    for event in all_events:
        if not (start_time <= event['timestamp_dt'] <= end_time):
            continue
        
        # 성공 조건 달성 전 MTD 이벤트가 발생했다면 공격은 실패
        if event.get('type') == 'mtd_start':
            return False, "INTERRUPTED_BY_MTD"
        
        # 로그 소스 및 이벤트 타입 확인
        event_data = event.get('data', {})
        is_dvd_log_event = condition['source'] == 'bus_dvd.log' and event.get('type') == 'drone_state'
        
        if is_dvd_log_event:
            metric, op, value = condition['metric'], condition.get('operator', '=='), condition['value']

            # 복합 메트릭 계산
            if metric == 'position_drift_m' and all(k in event_data for k in ['lat', 'lon']):
                if initial_pos is None:
                    initial_pos = (event_data['lat'], event_data['lon'])
                drift = haversine(initial_pos[0], initial_pos[1], event_data['lat'], event_data['lon'])
                if check_operator(drift, op, value):
                    return True, f"SUCCESS: Position drift {drift:.1f}m {op} {value}m"
            
            elif metric == 'attitude_unstable' and all(k in event_data for k in ['roll', 'pitch']):
                if abs(event_data['roll']) > value or abs(event_data['pitch']) > value:
                    return True, f"SUCCESS: Attitude unstable"
            
            # 단순 메트릭 확인
            elif metric in event_data:
                if check_operator(event_data[metric], op, value):
                    return True, f"SUCCESS: {metric} ({event_data[metric]}) {op} {value}"

    return False, "CONDITION_NOT_MET_IN_WINDOW"

def main():
    parser = argparse.ArgumentParser(description="로그 파일과 프로필을 기반으로 공격 성공 여부를 평가합니다.")
    parser.add_argument('--bus-log', default=os.path.join(BUS_DIR, 'bus.log'), help="bus.log 파일 경로")
    parser.add_argument('--dvd-log', default=os.path.join(BUS_DIR, 'bus_dvd.log'), help="bus_dvd.log 파일 경로")
    parser.add_argument('--profiles', default=os.path.join(ATTACKS_DIR, 'attack_profiles.json'), help="attack_profiles.json 파일 경로")
    parser.add_argument('--output', default='evaluation_summary.json', help="평가 결과 요약 파일 저장 경로")
    args = parser.parse_args()

    try:
        with open(args.profiles, 'r', encoding='utf-8') as f:
            attack_profiles = json.load(f)
    except FileNotFoundError:
        print(f"❌ 오류: 공격 프로필 파일을 찾을 수 없습니다: {args.profiles}")
        return

    bus_events = load_log_file(args.bus_log)
    dvd_events = load_log_file(args.dvd_log)
    all_events = sorted(bus_events + dvd_events, key=lambda x: x['timestamp_dt'])
    
    evaluation_results = {}
    attack_start_events = [e for e in all_events if e.get('type') == 'attack_start']

    if not attack_start_events:
        print("분석할 'attack_start' 이벤트가 로그 파일에 없습니다.")
        return

    for start_event in attack_start_events:
        attack_name = start_event.get('data', {}).get('attack_name')
        profile = attack_profiles.get(attack_name)
        
        print(f"\n--- '{attack_name}' 공격 평가 (시작 시간: {start_event['timestamp']}) ---")
        if not profile:
            print("  - 프로필을 찾을 수 없어 평가를 건너뜁니다.")
            continue
            
        is_successful, reason = check_success_condition(start_event, all_events, profile)
        
        print(f"  - 평가 결과: {'✅ 성공' if is_successful else '❌ 실패'}")
        print(f"  - 사유: {reason}")

        evaluation_results[start_event['timestamp']] = {
            "attack_name": attack_name, "start_time": start_event['timestamp'],
            "profile": profile, "is_successful": is_successful, "reason": reason
        }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(evaluation_results, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ 평가 완료. 결과가 {args.output} 파일에 저장되었습니다.")

if __name__ == "__main__":
    main()