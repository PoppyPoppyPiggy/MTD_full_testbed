#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import math
import yaml
import os
import sys
from collections import Counter

# --- 경로 설정 ---
LPC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUS_LOG_PATH = os.path.join(LPC_ROOT, "bus", "bus.log")
POLICY_FILE_PATH = os.path.join(LPC_ROOT, "mtd", "shared_state", "mtd_policy.yaml")

def calculate_metrics(log_file, policy_file):
    with open(policy_file, 'r') as f:
        policy = yaml.safe_load(f)

    events =
    with open(log_file, 'r') as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # 1. 보안성 (Defense Success Rate, R_succ)
    attack_events = [e for e in events if e.get("type") == "attack_detected"]
    total_attacks = len(attack_events)
    successful_attacks = sum(1 for e in attack_events if e.get("data", {}).get("is_success"))
    compromises = sum(1 for e in attack_events if e.get("data", {}).get("is_success") and e.get("data", {}).get("is_real_asset"))
    
    r_succ = 1 - (compromises / total_attacks) if total_attacks > 0 else 1.0

    # 2. 기민성 (Agility - Shuffling S, Diversity D)
    swap_events = [e for e in events if e.get("type") == "mtd_target_swap"]
    if swap_events:
        start_time = swap_events['timestamp']
        end_time = swap_events[-1]['timestamp']
        duration_sec = end_time - start_time
        f_shuffle = len(swap_events) / duration_sec if duration_sec > 0 else 0
    else:
        f_shuffle = 0

    ip_space_size = len(policy.get('decoy_pool',))
    port_space_size = len(policy.get('port_pool',))
    p_space = ip_space_size * port_space_size
    s_shuffle = f_shuffle * math.log2(p_space) if p_space > 1 else 0

    # 다양성(D)은 사용된 방어 전략(태세)의 분포로 계산
    posture_events = [e['data']['to'] for e in events if e.get("type") == "mtd_posture_change"]
    posture_counts = Counter(posture_events)
    total_decisions = len(posture_events)
    diversity = 0
    if total_decisions > 0:
        for count in posture_counts.values():
            p_i = count / total_decisions
            diversity -= p_i * math.log2(p_i)

    # 3. 비용 (Defense Cost, C_def) - 시뮬레이션에서는 가정치 사용
    # 실제로는 성능 측정 필요. 예: 셔플링 시 5% 성능 저하 가정
    c_def = 0.05 * f_shuffle # 셔플링 빈도에 비례한다고 가정

    # 4. 기만성 (Deception Efficiency, eta_dec)
    attacks_on_real = sum(1 for e in attack_events if e.get("data", {}).get("is_real_asset"))
    attacks_on_decoy = total_attacks - attacks_on_real
    eta_dec = attacks_on_decoy / total_attacks if total_attacks > 0 else 0

    # 최종 DES 점수 계산
    weights = policy.get('des_scoring', {}).get('weights', {})
    des_score = (weights.get('security', 0.4) * r_succ +
                 weights.get('agility', 0.2) * (s_shuffle / 10 + diversity) / 2 + # 정규화
                 weights.get('cost', 0.2) * (1 - c_def) +
                 weights.get('deception', 0.2) * eta_dec)

    return {
        "Security (R_succ)": r_succ,
        "Agility (S_shuffle)": s_shuffle,
        "Agility (Diversity D)": diversity,
        "Cost (C_def)": c_def,
        "Deception (eta_dec)": eta_dec,
        "Total_Attacks": total_attacks,
        "Successful_Attacks_on_Real": compromises,
        "Overall_DES_Score": des_score
    }

if __name__ == "__main__":
    if not os.path.exists(BUS_LOG_PATH):
        print(f"로그 파일({BUS_LOG_PATH})을 찾을 수 없습니다.")
        sys.exit(1)
    
    metrics = calculate_metrics(BUS_LOG_PATH, POLICY_FILE_PATH)
    print("\n--- MTD 성능 평가 결과 ---")
    for key, value in metrics.items():
        print(f"{key:<30}: {value:.4f}")
    print("--------------------------")