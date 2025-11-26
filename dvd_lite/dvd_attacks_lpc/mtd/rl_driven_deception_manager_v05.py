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
from .rl_config_v05 import FEATURE_KEYS, STATE_DIM, ACTION_DIM, FEATURE_NORM_METADATA, ACT_THRESHOLDS, ACTION_PARAM_KEYS

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

    def select_multi_action(self, obs_dict: Dict[str, float]) -> Dict[str, Any]:
        """
        [IMPROVEMENT] Multi-Action Selection
        Returns a dictionary of actions based on thresholds instead of a single ID.
        """
        obs_vec = self.preprocess_obs(obs_dict)
        obs_tensor = torch.as_tensor(obs_vec, dtype=torch.float32).to(self.device).unsqueeze(0)
        
        with torch.no_grad():
            action_raw, _, _ = self.agent.get_action_and_value(obs_tensor)
            action_np = action_raw.cpu().numpy().squeeze()
            
        # Map Continuous Output [-1, 1] to [0, 1]
        def _scale(idx):
            return 0.5 * (action_np[idx] + 1.0)
            
        # Create Action Dictionary
        action_dict = {
            "shuffle_intensity": _scale(2),
            "decoy_ratio": _scale(5),
            "blacklist_aggression": _scale(3),
            "blacklist_duration": _scale(4),
            "dnat_target_focus": _scale(0),
            "dnat_decoy_focus": _scale(1)
        }
        
        # Determine Boolean Flags based on Thresholds
        flags = {
            "do_shuffle": action_dict["shuffle_intensity"] >= ACT_THRESHOLDS["SHUFFLE"],
            "active_decoy": action_dict["decoy_ratio"] >= ACT_THRESHOLDS["DECOY_ACTIVE"],
            "active_blacklist": action_dict["blacklist_aggression"] >= ACT_THRESHOLDS["BL_ACTIVE"]
        }
        
        return {**action_dict, **flags}

class RLDrivenDeceptionManager:
    def __init__(self, config_path: str | Path, dry_run: bool = True):
        self.config = MTDConfig.load(config_path)
        self.state_store = MTDStateStore(self.config.state_file)
        # Note: IPTablesMTDController needs update to handle dict input!
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

        # Build Observation
        obs = {
            "cti_alert_rate": float(cti.threat_level),
            "uptime_ratio": 1.0 - float(qos.loss_rate),
            "breach_success_rate": 1.0 if cti.is_breach else 0.0
        }
        
        # [IMPROVEMENT] Get Multi-Action Dict
        multi_action = self.policy.select_multi_action(obs)
        
        # Apply Multi-Action via Controller
        # NOTE: apply_action in controller must be updated to accept dict
        metrics = self.iptables.apply_action(multi_action, state)
        
        state.step += 1
        self.state_store.save(state)
        return metrics

    def finalize_episode(self) -> Dict[str, Any]:
        summary, _ = self.scoring.export_last_episode()
        return summary