# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/controller_cti_policy.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[수정 3/8] CTI 정책 JSON 컨트롤러 (v04)

- [v03 대비 변경점]
- set_policy(name) -> set_policy_parameters(aggression, duration)로 변경
- RL 에이전트의 연속적인 파라미터 값을 실제 CTI 정책 값으로 변환(map)합니다.
"""
import os
import json
import logging
import numpy as np

class CtiPolicyController:
    """
    ml/cti_agent.py 가 참조하는 cti_policy.json 파일을 관리합니다.
    """
    def __init__(self, policy_file_path: str, logger: logging.Logger = None):
        self.policy_file_path = policy_file_path
        self.logger = logger or logging.getLogger(__name__)
        
        # 파라미터 매핑 범위 정의
        # (RL 출력 0.0~1.0) -> (실제 값)
        # aggression: (0.0=느슨 -> 0.7) ~ (1.0=공격적 -> 0.1) (역방향 매핑)
        self.aggression_range = (0.7, 0.1)  
        # duration: (0.0=Timer -> 300s) ~ (1.0=Aggressive -> -1(영구))
        self.duration_range = (300.0, -1.0) 

        self.logger.info(f"CTI 정책 컨트롤러(v04) 초기화. 정책 파일: {self.policy_file_path}")

    def _map_value(self, val_0_to_1: float, range_min: float, range_max: float) -> float:
        """ (0.0~1.0) 사이의 val 값을 (min~max) 범위로 선형 보간 """
        return range_min + (range_max - range_min) * val_0_to_1

    def set_policy_parameters(self, aggression_param: float, duration_param: float) -> bool:
        """
        RL의 연속 파라미터(0.0~1.0)를 받아 CTI 정책 JSON 파일을 덮어씁니다.
        
        :param aggression_param: (0.0~1.0) 블랙리스트 공격성
        :param duration_param: (0.0~1.0) 블랙리스트 지속 시간
        """
        
        # 1. 파라미터 -> 실제 값으로 변환
        detection_threshold = self._map_value(aggression_param, self.aggression_range[0], self.aggression_range[1])
        ban_duration_sec = self._map_value(duration_param, self.duration_range[0], self.duration_range[1])
        
        # (범위 보정 및 타입 변환)
        detection_threshold = float(np.clip(detection_threshold, 0.05, 1.0))
        ban_duration_sec = int(ban_duration_sec)
        # 1.0(영구)에 가까운 값은 -1로 확실히 변환
        if duration_param > 0.95:
            ban_duration_sec = -1
        
        policy_data = {
            "detection_threshold": detection_threshold,
            "ban_duration_sec": ban_duration_sec
        }
        
        try:
            # 2. CTI 에이전트가 읽을 JSON 파일 쓰기
            with open(self.policy_file_path, 'w') as f:
                json.dump(policy_data, f, indent=2)
            self.logger.info(f"CTI 정책 변경 성공: {policy_data} (파일: {self.policy_file_path})")
            return True
        except Exception as e:
            self.logger.error(f"CTI 정책 파일 쓰기 실패: {e}")
            return False
        