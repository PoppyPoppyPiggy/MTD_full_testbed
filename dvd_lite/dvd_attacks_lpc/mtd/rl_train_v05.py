# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_export_policy_v05.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 7/8] 학습된 정책을 실전 배포용(v05)으로 내보내는 스크립트

- [v04 대비 변경점]
- v05 계약(rl_config_v05.py)을 임포트하여 meta.json 생성
"""

import os
import json
import torch
import numpy as np
from typing import List, Dict, Any

# 학습 환경과 동일한 정의를 가져옵니다.
from mtd.rl_model_v05 import MTDPolicyNet
from mtd.rl_config_v05 import (
    ACTION_PARAM_KEYS, ACTION_DIM,
    FEATURE_KEYS, OBS_DIM
)

def compute_feature_norms(state_history: np.ndarray) -> Dict[str, List[float]]:
    """ (N, OBS_DIM) 상태 이력으로 정규화 값 계산 """
    if state_history.ndim != 2 or state_history.shape[1] != OBS_DIM:
        raise ValueError(f"State history shape 오류. (N, {OBS_DIM}) 필요. 현재: {state_history.shape}")
    mean = state_history.mean(axis=0)
    std = state_history.std(axis=0) + 1e-8
    return {"mean": mean.tolist(), "std": std.tolist()}

def export_mtd_policy(
    policy_net: MTDPolicyNet,
    state_history: np.ndarray,
    save_dir: str,
    version: str = "ver_05"
) -> None:
    """
    학습된 정책과 메타데이터(v05)를 MTD_full_testbed 배포용 파일로 저장합니다.
    """
    os.makedirs(save_dir, exist_ok=True)
    
    base_name = f"mtd_policy_{version}"
    ckpt_path = os.path.join(save_dir, f"{base_name}.pth")
    meta_path = os.path.join(save_dir, f"{base_name}_meta.json")

    # 1. 모델 가중치(.pth) 저장 (Actor Net만)
    torch.save(policy_net.state_dict(), ckpt_path)

    # 2. 메타데이터(.json) 생성
    try:
        feature_norm = compute_feature_norms(state_history)
    except Exception as e:
        print(f"Warning: 정규화(norm) 값 계산 실패. 기본값(mean=0, std=1) 사용. \n{e}")
        feature_norm = {"mean": [0.0] * OBS_DIM, "std": [1.0] * OBS_DIM}

    meta = {
        "model_file": os.path.basename(ckpt_path),
        "version": version,
        "action_space_type": "continuous", # [v05]
        "obs_dim": OBS_DIM,                # 16
        "act_dim": ACTION_DIM,             # 6
        "feature_keys": FEATURE_KEYS,      # [v05] 16D 상태 벡터 순서
        "feature_norm": feature_norm,      # [v05] 16D 정규화 값
        "action_param_keys": ACTION_PARAM_KEYS # [v05] 6D 행동 파라미터 순서
    }

    # 3. 메타데이터(.json) 저장
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n[MTD 정책 내보내기 완료]")
    print(f"  - 가중치: {ckpt_path}")
    print(f"  - 메타  : {meta_path}")