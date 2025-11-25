# Directory: dvd_lite/dvd_attacks_lpc/mtd/
# Filename: rl_driven_deception_manager_v05.py

from __future__ import annotations
import logging
import os
import torch
import numpy as np
from pathlib import Path
from typing import Any, Dict

from .mtd_config import MTDConfig
from .mtd_state_store import MTDStateStore, MTDState
from .iptables_mtd_controller import IPTablesMTDController
from .cti_status_reader import CtiStatusReader
from .qos_monitor import QoSMonitor
from .mtd_scoring import MTDScoring

from .rl_model_v05 import PPOAgent
from .rl_config_v06 import FEATURE_KEYS, STATE_DIM, ACTION_DIM, FEATURE_NORM_METADATA

log = logging.getLogger(__name__)

class RLPolicyInterface:
    def __init__(self, model_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        self.agent = PPOAgent(state_dim=STATE_DIM, action_dim=ACTION_DIM, device=self.device)
        
        if os.path.exists(model_path):
            log.info(f"Loading RL Model from {model_path}")
            self.agent.load_policy(model_path)
        else:
            log.error(f"Model not found at {model_path}")

    def preprocess_obs(self, raw_obs: Dict[str, float]) -> np.ndarray:
        vec = [raw_obs.get(key, 0.0) for key in FEATURE_KEYS]
        return np.clip(np.array(vec, dtype=np.float32), 0.0, 1.0)

    def select_action(self, obs_dict: Dict[str, float]) -> int:
        obs_vec = self.preprocess_obs(obs_dict)
        obs_tensor = torch.as_tensor(obs_vec, dtype=torch.float32).to(self.device).unsqueeze(0)
        
        with torch.no_grad():
            action, _, _ = self.agent.get_action_and_value(obs_tensor)
            action_np = action.cpu().numpy().squeeze()
            
        # Action Mapping Logic (Continuous -> Discrete ID for IPTables Controller)
        # 0: No-op, 1: IP Shuffle, 2: Port Shuffle, 3: Decoy
        shuffle_intensity = action_np[2]
        decoy_ratio = action_np[5]
        
        if shuffle_intensity > 0.7: return 1
        elif shuffle_intensity > 0.4: return 2
        elif decoy_ratio > 0.5: return 3
        else: return 0

class RLDrivenDeceptionManager:
    def __init__(self, config_path: str | Path, dry_run: bool = True):
        self.config = MTDConfig.load(config_path)
        self.state_store = MTDStateStore(self.config.state_file)
        self.iptables = IPTablesMTDController(self.config, self.state_store, dry_run)
        self.cti_reader = CtiStatusReader(self.config.cti_status_file)
        self.qos_monitor = QoSMonitor(self.state_store)
        self.scoring = MTDScoring(self.state_store, self.config.metrics_log)

        model_path = os.path.join(os.path.dirname(__file__), "../../runs/final_policy.pth")
        self.policy = RLPolicyInterface(model_path=model_path)

    def step(self):
        state = self.state_store.load()
        cti = self.cti_reader.read()
        qos = self.qos_monitor.sample(cti.src_ip)

        # Build Observation from real metrics
        obs = {
            "cti_alert_rate": float(cti.threat_level),
            "uptime_ratio": 1.0 - float(qos.loss_rate),
            "breach_success_rate": 1.0 if cti.is_breach else 0.0
        }
        
        action_id = self.policy.select_action(obs)
        action = self.config.actions[action_id] if action_id < len(self.config.actions) else self.config.actions[0]
        
        metrics = self.iptables.apply_action(action, state)
        state.step += 1
        self.state_store.save(state)
        return metrics

    def finalize_episode(self) -> Dict[str, Any]:
        summary, _ = self.scoring.export_last_episode()
        return summary