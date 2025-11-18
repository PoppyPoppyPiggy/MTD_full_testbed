#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_export_policy_v05.py

- 학습된 MTDPolicyNet 파라미터(.pth)와
  상태 정규화 정보(feature_norm), FEATURE_KEYS/ACTION_PARAM_KEYS 메타를
  JSON으로 저장.
- 테스트베드에서 이 메타를 그대로 읽어들여 인퍼런스하면,
  학습/실환경 입력 의미가 동일해진다.
"""

import json
import os
from typing import Sequence, Dict, Any

import numpy as np
import torch

from rl_config_v05 import FEATURE_KEYS, ACTION_PARAM_KEYS, OBS_DIM, ACTION_DIM


def compute_feature_norms(state_history: Sequence[np.ndarray]) -> Dict[str, Dict[str, float]]:
    """
    state_history: (N, OBS_DIM) 형태의 numpy 배열 리스트
    FEATURE_KEYS 순서에 맞춰 평균/표준편차 계산.
    """
    if not state_history:
        # 데이터를 못 모았을 경우 기본값
        return {
            key: {"mean": 0.0, "std": 1.0}
            for key in FEATURE_KEYS
        }

    states = np.stack(state_history, axis=0)
    assert states.shape[1] == OBS_DIM

    norms: Dict[str, Dict[str, float]] = {}
    for i, key in enumerate(FEATURE_KEYS):
        col = states[:, i]
        mean = float(np.mean(col))
        std = float(np.std(col) + 1e-6)
        norms[key] = {"mean": mean, "std": std}

    return norms


def export_mtd_policy(
    policy_net: torch.nn.Module,
    state_history: Sequence[np.ndarray],
    save_dir: str,
    version: str = "ver_05",
) -> None:
    """
    정책 파라미터 + 메타데이터를 저장.

    Outputs:
        save_dir/mtd_policy_{version}.pth
        save_dir/mtd_policy_{version}_meta.json
    """
    os.makedirs(save_dir, exist_ok=True)

    # 1) 모델 저장 (CPU 호환)
    policy_cpu = policy_net.to("cpu")
    model_path = os.path.join(save_dir, f"mtd_policy_{version}.pth")
    torch.save(policy_cpu.state_dict(), model_path)

    # 2) feature_norm 계산
    feature_norm = compute_feature_norms(state_history)

    # 3) 메타 JSON 생성
    meta: Dict[str, Any] = {
        "version": version,
        "model_path": os.path.basename(model_path),
        "obs_dim": OBS_DIM,
        "action_dim": ACTION_DIM,
        "feature_keys": FEATURE_KEYS,
        "action_param_keys": ACTION_PARAM_KEYS,
        "feature_norm": feature_norm,
        "semantic_contract": {
            "description": (
                "This policy was trained in NetworkEnv v0.5. "
                "Inputs must be normalized using feature_norm over FEATURE_KEYS, "
                "and actions are interpreted as continuous parameters in [-1,1], "
                "scaled to [0,1] before mapping to DNAT/shuffle/blacklist semantics."
            ),
        },
    }

    meta_path = os.path.join(save_dir, f"mtd_policy_{version}_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"[+] Saved policy: {model_path}")
    print(f"[+] Saved meta:   {meta_path}")
