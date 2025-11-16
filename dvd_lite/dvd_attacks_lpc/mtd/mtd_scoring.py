#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 4/8, v05 통합 수정] MTD 학술 지표 계산 모듈

기술 보고서 "MTD-RL을 위한 이중 지표 프레임워크" V.B 섹션에 따라,
PPO 훈련 루프(rl_train_v05.py)의 `Callback` 또는 `if done:` 블록에서 직접
호출할 수 있는 순수 함수형 MTD 지표 계산기.

- 입력: 에피소드 동안 수집된 info 딕셔너리 리스트 (episode_accumulator)
- 출력: S_D, R_A_norm, C_M, S_MTD_norm 등 8개의 정규화된 학술 지표
- 특징: T_A=0, N_A=0 등 엣지 케이스를 NaN 또는 1.0으로 올바르게 처리
"""

import numpy as np
from typing import List, Dict

def calculate_metrics(episode_accumulator: List[dict],
                      w_s_d: float = 0.5,
                      w_r_a: float = 0.3,
                      w_c_m: float = 0.2) -> Dict[str, float]:
    """
    기술 보고서(MTD-RL 이중 지표 프레임워크) 섹션 V.B 기반 구현.
    에피소드의 info 리스트로부터 MTD 학술 지표(v02)를 계산합니다.
    
    Info Contract (기술 보고서 섹션 III.B):
    - cost (float): 정규화된 MTD 비용 (0.0 ~ 1.0 권장)
    - is_attack_ground_truth (bool): 실제 공격 발생 여부 (Ground Truth)
    - is_attacker_on_decoy (bool): 공격자가 디코이에 유인되었는지 여부
    - is_breach_successful (bool): 실제 자산 침투 성공 여부
    - did_reconfigure (bool): MTD 재구성 수행 여부
    """

    # 1. 기반 카운터 집계 (Table 2 로직)
    T = len(episode_accumulator)
    T_A = sum(1 for step in episode_accumulator if step.get('is_attack_ground_truth', False))
    T_D = sum(1 for step in episode_accumulator
              if step.get('is_attack_ground_truth', False) and step.get('is_attacker_on_decoy', False))
    N_A = sum(1 for step in episode_accumulator if step.get('is_breach_successful', False))
    N_R = sum(1 for step in episode_accumulator if step.get('did_reconfigure', False))
    
    # 2. 엣지 케이스 처리 (Case 3: T == 0)
    if T == 0:
        # 에피소드가 0 스텝에서 종료된 비정상 케이스
        return {
            'T': 0.0, 'T_A': 0.0, 'T_D': 0.0, 'N_A': 0.0, 'N_R': 0.0,
            'S_D': np.nan, 'C_M': np.nan, 'R_A_norm': np.nan, 'S_MTD_norm': np.nan
        }

    # 3. 핵심 지표 계산
    
    # S_D (Deception Success) - Case 1: T_A == 0 (평화로운 에피소드) 처리
    # T_A=0 이면 0/0 이므로, NaN (Not a Number)가 통계적으로 올바른 값
    S_D = (T_D / T_A) if T_A > 0 else np.nan
    
    # R_A_norm (Resilience) - Case 2: N_A == 0 (완벽 방어) 처리
    # N_A=0 이면 침투 0회, 완벽한 회복탄력성(1.0)으로 간주
    R_A_norm = 1.0 if N_A == 0 else np.tanh(N_R / N_A)
    
    # C_M (Cost) - T > 0은 보장됨. cost는 info에서 [0, 1]로 정규화되었다고 가정.
    total_cost = sum(step.get('cost', 0.0) for step in episode_accumulator)
    C_M = total_cost / T
    
    # 4. 통합 점수 계산 (S_MTD_norm)
    # S_D가 NaN인 경우(평화로운 에피소드), S_MTD도 NaN으로 처리
    if np.isnan(S_D):
        S_MTD_norm = np.nan
    else:
        # 기술 보고서 IV.E의 정규화된 수식
        S_MTD_norm = (w_s_d * S_D) + (w_r_a * R_A_norm) - (w_c_m * C_M)

    # 5. 결과 반환 (8개 값)
    return {
        'T': float(T),
        'T_A': float(T_A),
        'T_D': float(T_D),
        'N_A': float(N_A),
        'N_R': float(N_R),
        'S_D': S_D,
        'C_M': C_M,
        'R_A_norm': R_A_norm,
        'S_MTD_norm': S_MTD_norm
    }