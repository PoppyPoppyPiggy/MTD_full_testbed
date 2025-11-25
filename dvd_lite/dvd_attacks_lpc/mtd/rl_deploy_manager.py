# Directory: dvd_lite/dvd_attacks_lpc/mtd/
# Filename: rl_deploy_manager.py

import time
import os
import numpy as np
import joblib
from stable_baselines3 import PPO

# rl_config_v06.py가 같은 디렉토리에 있어야 합니다.
from .rl_config_v06 import RL_CONFIG, FEATURE_KEYS
from .mtd_state_store import MTDStateStore
from .iptables_channel_switch import IptablesChannelSwitcher

class RLDecoyManager:
    """
    학습된 RL 모델을 로드하여 실제 환경(Testbed)에서 Inference를 수행하고,
    IPtables를 제어하여 MTD(채널 변조 등)를 수행하는 매니저 클래스입니다.
    """
    def __init__(self, model_path, cti_model_path=None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 1. Load RL Policy Model
        # 모델 경로는 mtd 디렉토리 기준 상대 경로 혹은 절대 경로여야 합니다.
        full_model_path = os.path.join(self.base_dir, model_path)
        if not os.path.exists(full_model_path):
            # 경로 문제 발생 시 상위 디렉토리도 확인 (Saved models 위치에 따라 조정)
            full_model_path = os.path.join(self.base_dir, "..", model_path)
            if not os.path.exists(full_model_path):
                raise FileNotFoundError(f"RL Model not found at {full_model_path}")
        
        print(f"[RL-Manager] Loading PPO Model from {full_model_path}...")
        self.model = PPO.load(full_model_path)
        
        # 2. Load CTI Model (Optional, for state preprocessing)
        self.cti_model = None
        if cti_model_path:
            cti_full_path = os.path.join(self.base_dir, cti_model_path)
            if os.path.exists(cti_full_path):
                print(f"[RL-Manager] Loading CTI Model from {cti_full_path}...")
                self.cti_model = joblib.load(cti_full_path)

        # 3. Initialize Components
        self.state_store = MTDStateStore()
        self.channel_switcher = IptablesChannelSwitcher()
        
        self.last_action_time = 0
        self.action_cooldown = 2.0 # MTD 너무 자주 수행 방지 (시스템 안정성)

    def _preprocess_observation(self, raw_metrics):
        """
        시스템 메트릭을 RL 모델이 이해할 수 있는 정규화된 Observation 벡터로 변환합니다.
        RL_CONFIG.FEATURE_KEYS 순서를 엄격히 따릅니다.
        """
        # FEATURE_KEYS = [
        #    "cti_alert_rate", "blacklist_size_ratio", "uptime_ratio", ...
        # ]
        
        obs = np.zeros(RL_CONFIG.STATE_DIM, dtype=np.float32)
        
        # 1. CTI Alert Rate (from metrics or CTI model prediction)
        # 실제 환경에서는 CTI 에이전트의 예측값이나 모니터링된 alert rate를 사용
        obs[0] = raw_metrics.get('cti_score', 0.0)
        
        # 2. Blacklist Ratio
        max_bl_size = 1000 # 예시 값
        obs[1] = min(raw_metrics.get('blacklist_count', 0) / max_bl_size, 1.0)
        
        # 3. Uptime Ratio
        obs[2] = raw_metrics.get('uptime', 1.0)
        
        # 4. Breach Success Rate (누적 통계)
        obs[3] = raw_metrics.get('breach_rate', 0.0)
        
        # ... 나머지 Feature들도 metrics에서 가져와 매핑 ...
        
        # Normalize to [0, 1]
        obs = np.clip(obs, 0, 1)
        return obs

    def run_loop(self, interval=1.0):
        print("[RL-Manager] Starting Defense Loop...")
        
        while True:
            try:
                # 1. 상태 수집 (Shared State File 읽기)
                current_metrics = self.state_store.get_latest_metrics()
                obs = self._preprocess_observation(current_metrics)
                
                # 2. RL 모델 추론 (Deterministic=True 권장 for deployment)
                # 학습된 정책에 따라 최적의 행동 결정
                action, _states = self.model.predict(obs, deterministic=True)
                
                # 3. 행동 수행 판단 (Action 0은 보통 No-Op)
                # Action Space 정의 (rl_config_v06.py ACTION_PARAM_KEYS 참고):
                # 이 예제에서는 Discrete Action으로 매핑하거나, Continuous 값을 Thresholding 함.
                # 여기서는 편의상 Action Index가 반환된다고 가정하고 분기 처리합니다.
                
                current_time = time.time()
                
                # 쿨다운 체크 및 Action 유효성 검사
                if action > 0 and (current_time - self.last_action_time > self.action_cooldown):
                    print(f"[RL-Manager] Threat Detected! Executing MTD Action: {action}")
                    self._execute_mitigation(action)
                    self.last_action_time = current_time
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("[RL-Manager] Stopping...")
                break
            except Exception as e:
                print(f"[RL-Manager] Error in loop: {e}")
                time.sleep(1)

    def _execute_mitigation(self, action_idx):
        """
        RL Action Index를 실제 시스템 명령(Iptables)으로 변환합니다.
        """
        # Note: 실제 PPO Output이 Continuous라면 np.argmax 등을 쓰거나 
        # MultiDiscrete의 경우 분기 로직이 달라질 수 있습니다.
        
        if action_idx == 1:
            # IP Shuffle (NAT Table Rotation)
            self.channel_switcher.rotate_ip()
        elif action_idx == 2:
            # Port Hopping
            self.channel_switcher.rotate_port()
        elif action_idx == 3:
            # Switch to Alternate Channel (Backup Node Logic)
            # 공격이 심할 경우, 사전에 정의된 '안전 채널'로 GCS 통신을 강제 이동
            print("[RL-Manager] CRITICAL: Switching to Secure Backup Channel")
            self.channel_switcher.activate_backup_channel()
        elif action_idx == 4:
            # Decoy Reinforcement or Blacklist Aggression
            print("[RL-Manager] Deploying Decoy / Updating Blacklist")
            # self.decoy_manager.add_decoy() # 추가 구현 필요 시 호출

if __name__ == "__main__":
    # 실행 예시: 저장된 모델 파일명 지정
    # Docker 컨테이너 내부 경로 주의 (/mtd_full_testbed/dvd_lite/dvd_attacks_lpc/...)
    manager = RLDecoyManager(
        model_path="saved_models/ppo_mtd_agent_final.zip" 
    )
    manager.run_loop()