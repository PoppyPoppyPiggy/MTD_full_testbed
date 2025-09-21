#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import yaml
import argparse
import pandas as pd
from typing import List, Dict, Any

def parse_logs(log_path: str) -> List[Dict[str, Any]]:
    """JSONL 형식의 로그 파일을 파싱합니다."""
    events = []
    with open(log_path, 'r') as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events

def calculate_des(events: List[Dict[str, Any]], policy: Dict[str, Any]) -> Dict[str, float]:
    """로그와 정책을 기반으로 Deception Effectiveness Score (DES)를 계산합니다."""
    
    # --- 1. Security Score ---
    seeker_started_ts = next((e['ts'] for e in events if e.get('type') == 'seeker_started'), None)
    compromise_ts = next((e['ts'] for e in events if e.get('type') == 'lpc_attack_start'), None)
    
    tfc = (compromise_ts - seeker_started_ts) if seeker_started_ts and compromise_ts else 3600 # 최대값
    normalized_tfc = min(tfc / 3600.0, 1.0) # 1시간을 기준으로 정규화
    
    attack_success_events = [e for e in events if e.get('type') == 'attack_succeeded']
    asr = 1.0 if any(attack_success_events) else 0.0
    security_score = (1 - asr) * 0.5 + normalized_tfc * 0.5

    # --- 2. Deception Score ---
    mtd_swaps = [e for e in events if e.get('type') == 'mtd_target_swap']
    dummy_deactivations = [e for e in events if e.get('data', {}).get('action') == 'deactivate_to_virtual']
    
    # 공격자가 가상 드론에 머무른 시간 (간단한 추정)
    dwell_time = len(dummy_deactivations) * 5 # 스왑당 평균 5초 체류로 가정
    normalized_dwell_time = min(dwell_time / 300.0, 1.0) # 5분을 기준으로 정규화

    # 수집된 CTI 다양성 (공격 이벤트 종류)
    attack_event_types = {e['data'].get('attack_type') for e in events if e.get('type') == 'attack_started'}
    cti_richness = min(len(attack_event_types) / 5.0, 1.0) # 5종류 이상이면 만점
    
    deception_score = normalized_dwell_time * 0.5 + cti_richness * 0.5

    # --- 3. Cost Score ---
    action_costs = policy.get('des_scoring', {}).get('action_costs', {})
    total_action_cost = sum(action_costs.get(e['data'].get('reason'), 0) for e in mtd_swaps)
    normalized_action_cost = min(total_action_cost / 1000.0, 1.0) # 1000점을 기준으로 정규화
    
    cost_score = normalized_action_cost # 현재는 행동 비용만 고려

    # --- 최종 DES 계산 ---
    weights = policy.get('des_scoring', {}).get('weights', {'security': 0.5, 'deception': 0.3, 'cost': 0.2})
    des = (weights['security'] * security_score + 
           weights['deception'] * deception_score - 
           weights['cost'] * cost_score)

    return {
        "DES_Score": des,
        "Security_Score": security_score,
        "Deception_Score": deception_score,
        "Cost_Score": cost_score,
        "ASR": asr,
        "TFC_seconds": tfc,
        "Dwell_Time_estimated": dwell_time,
        "CTI_Richness_score": cti_richness
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate Deception Effectiveness Score (DES) from experiment logs.")
    parser.add_argument("--bus-log", default="../bus/bus.log", help="Path to the bus.log file.")
    parser.add_argument("--policy", default="../mtd/shared_state/mtd_policy.yaml", help="Path to the MTD policy file.")
    args = parser.parse_args()

    print(f"[*] 로그 파일 로딩: {args.bus_log}")
    events = parse_logs(args.bus_log)
    
    print(f"[*] 정책 파일 로딩: {args.policy}")
    with open(args.policy, 'r') as f:
        policy = yaml.safe_load(f)

    scores = calculate_des(events, policy)

    print("\n--- Deception Effectiveness Score (DES) Report ---")
    for key, value in scores.items():
        print(f"{key:<25}: {value:.4f}")
    print("--------------------------------------------------")

    # 결과를 JSON 파일로 저장
    with open("des_report.json", "w") as f:
        json.dump(scores, f, indent=2)
    print("\n[*] 결과가 des_report.json 파일로 저장되었습니다.")