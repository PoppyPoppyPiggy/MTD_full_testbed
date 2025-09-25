import yaml
import random
import numpy as np
import os
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class ExperimentConfig:
    """실험 설정을 체계적으로 관리하고 재현성을 보장합니다."""
    experiment_name: str
    random_seed: int = 42
    
    # 데이터셋 관련 설정
    flight_scenarios: List[str] = field(default_factory=list)
    attack_types: List[str] = field(default_factory=list)
    
    # 모델 관련 설정
    model_type: str = 'ensemble'
    model_parameters: Dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, config_path: str):
        """YAML 파일로부터 설정을 로드합니다."""
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)

    def set_random_seeds(self):
        """모든 라이브러리의 랜덤 시드를 고정하여 실험 재현성을 보장합니다."""
        random.seed(self.random_seed)
        np.random.seed(self.random_seed)
        os.environ['PYTHONHASHSEED'] = str(self.random_seed)
        # TensorFlow/PyTorch 등의 시드 설정도 여기에 추가 가능
        print(f"[*] 모든 랜덤 시드를 {self.random_seed}로 고정했습니다.")

# 예시 YAML 파일: experiment_config.yaml
"""
experiment_name: "GPS_Spoofing_vs_Ensemble_Model_v1"
random_seed: 42
flight_scenarios:
  - "hovering"
  - "waypoint_mission"
attack_types:
  - "gps-spoofing.sh"
  - "attitude-spoofing.sh"
model_type: "ensemble"
model_parameters:
  rf:
    n_estimators: 150
  gb:
    learning_rate: 0.05
"""