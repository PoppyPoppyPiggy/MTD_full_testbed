#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RL-Driven Deception Manager v09 - 수정 버전
============================================
numpy float32 JSON 직렬화 오류 수정

수정 사항:
1. to_serializable 함수 추가하여 numpy 타입 변환
2. save_mtd_state_json 호출 시 예외 처리 추가
3. MetricsLogger에서 numpy 타입 자동 변환
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

import numpy as np

# PyTorch
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not available")

# Local imports
from rl_config_v08 import (
    ACTION_DIM,
    ACTION_PARAM_KEYS,
    FEATURE_KEYS,
    STATE_DIM,
    MTDConfig,
    scale_action,
)
from iptables_mtd_controller_v08 import IptablesMTDController

# IEEE Figure Utils
try:
    from ieee_figure_utils import setup_ieee_style
    import matplotlib.pyplot as plt
    IEEE_FIGURES_AVAILABLE = True
except ImportError:
    IEEE_FIGURES_AVAILABLE = False

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [MTD-Controller] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RLDeceptionManager")


# =============================================================================
# Numpy JSON Serialization Helper (핵심 수정)
# =============================================================================
def to_serializable(obj: Any) -> Any:
    """
    numpy 타입을 JSON 직렬화 가능한 Python native 타입으로 변환
    
    이 함수가 float32 오류의 핵심 해결책입니다.
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.float32, np.float64, np.floating)):
        return float(obj)
    elif isinstance(obj, (np.int32, np.int64, np.integer)):
        return int(obj)
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    elif hasattr(obj, '__dict__'):
        return to_serializable(obj.__dict__)
    return obj


class NumpyJSONEncoder(json.JSONEncoder):
    """numpy 타입을 처리하는 커스텀 JSON 인코더"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.float32, np.float64, np.floating)):
            return float(obj)
        elif isinstance(obj, (np.int32, np.int64, np.integer)):
            return int(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)


# =============================================================================
# Actor-Critic Network
# =============================================================================
if TORCH_AVAILABLE:
    class ActorCritic(nn.Module):
        def __init__(self, state_dim: int, action_dim: int, hidden_size: int = 256, num_layers: int = 2):
            super().__init__()
            self.state_dim = state_dim
            self.action_dim = action_dim

            layers = []
            input_dim = state_dim
            for i in range(num_layers):
                layers.extend([
                    nn.Linear(input_dim, hidden_size),
                    nn.LayerNorm(hidden_size),
                    nn.ReLU(),
                ])
                input_dim = hidden_size
            self.shared = nn.Sequential(*layers)

            self.actor = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, action_dim),
                nn.Tanh(),
            )
            self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)
            self.critic = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
            )

        def forward(self, state):
            features = self.shared(state)
            return self.actor(features), self.critic(features)

        def act(self, state, deterministic: bool = True):
            action_mean, value = self.forward(state)
            if deterministic:
                return action_mean, torch.zeros(1), value
            from torch.distributions import Normal
            std = torch.exp(self.log_std)
            dist = Normal(action_mean, std)
            action = dist.sample()
            action = torch.clamp(action, -1, 1)
            log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)
            return action, log_prob, value


# =============================================================================
# Real-Time State
# =============================================================================
@dataclass
class RealTimeState:
    """실시간 상태 데이터"""
    timestamp: float = field(default_factory=time.time)
    scan_detected: bool = False
    scan_rate: float = 0.0
    suspicious_ips: List[str] = field(default_factory=list)
    blocked_ips: List[str] = field(default_factory=list)
    services_up: int = 6
    services_discovered: int = 0
    critical_exposed: bool = False
    diversity_score: float = 0.0
    redundancy_score: float = 0.0
    confusion_level: float = 0.0
    active_decoys: int = 0
    active_swaps: int = 0
    network_latency_ms: float = 0.0
    cti_alert: bool = False
    cti_threat_level: float = 0.0
    cti_attack_type: Optional[str] = None


# =============================================================================
# State Collector
# =============================================================================
class StateCollector:
    """실시간 상태 수집기"""
    
    def __init__(
        self,
        mtd_controller: IptablesMTDController,
        cti_file: Optional[str] = None,
        network_monitor_file: Optional[str] = None,
    ):
        self.mtd_controller = mtd_controller
        self.cti_file = Path(cti_file) if cti_file else None
        self.network_monitor_file = Path(network_monitor_file) if network_monitor_file else None
        self.state_history: deque = deque(maxlen=1000)
        self.last_state = RealTimeState()
        self._lock = threading.Lock()
    
    def collect_state(self) -> RealTimeState:
        """현재 상태 수집"""
        with self._lock:
            state = RealTimeState()
            
            # MTD Controller 상태
            mtd_state = self.mtd_controller.get_mtd_state_for_attacker()
            state.diversity_score = float(mtd_state.get("diversity_score", 0.0))
            state.redundancy_score = float(mtd_state.get("redundancy_score", 0.0))
            state.confusion_level = float(mtd_state.get("confusion_level", 0.0))
            state.active_decoys = int(mtd_state.get("decoy_count", 0))
            state.active_swaps = int(mtd_state.get("active_swap_count", 0))
            state.blocked_ips = list(self.mtd_controller.blacklist.keys())
            
            # CTI 파일
            if self.cti_file and self.cti_file.exists():
                try:
                    with open(self.cti_file, 'r') as f:
                        cti_data = json.load(f)
                    state.cti_alert = cti_data.get("alert", False)
                    state.cti_threat_level = float(cti_data.get("threat_level", 0.0))
                    state.cti_attack_type = cti_data.get("attack_type")
                except Exception as e:
                    logger.warning(f"CTI file read error: {e}")
            
            # 네트워크 모니터 파일
            if self.network_monitor_file and self.network_monitor_file.exists():
                try:
                    with open(self.network_monitor_file, 'r') as f:
                        net_data = json.load(f)
                    state.scan_detected = net_data.get("scan_detected", False)
                    state.scan_rate = float(net_data.get("scan_rate", 0.0))
                    state.suspicious_ips = net_data.get("suspicious_ips", [])
                    state.services_discovered = int(net_data.get("services_discovered", 0))
                    state.critical_exposed = net_data.get("critical_exposed", False)
                except Exception as e:
                    logger.warning(f"Network monitor file read error: {e}")
            
            self.last_state = state
            self.state_history.append(state)
            
            return state
    
    def get_state_vector(self) -> np.ndarray:
        """RL 정책 입력용 상태 벡터 (17차원)"""
        state = self.collect_state()
        
        scanned_ratio = min(1.0, state.scan_rate / 0.2) if state.scan_detected else 0.0
        discovered_ratio = state.services_discovered / 6.0
        exploit_progress = max(0, (state.cti_threat_level - 0.5) * 2) if state.cti_threat_level > 0.5 else 0.0
        
        compromise_progress = 0.0
        if state.cti_attack_type in ["lateral_movement", "data_exfiltration"]:
            compromise_progress = 0.5
        if state.cti_attack_type == "command_control":
            compromise_progress = 1.0
        
        energy = max(0.0, 1.0 - len(state.blocked_ips) * 0.1)
        
        last_action = self.mtd_controller.stats.last_action_time or time.time()
        steps_since_shuffle = min(1.0, (time.time() - last_action) / 300)
        
        last_swap = self.mtd_controller.stats.last_swap_time or time.time()
        steps_since_swap = min(1.0, (time.time() - last_swap) / 300)
        
        return np.array([
            scanned_ratio,
            discovered_ratio,
            float(state.critical_exposed),
            exploit_progress,
            compromise_progress,
            state.diversity_score,
            state.redundancy_score,
            state.active_decoys / 4.0,
            energy,
            state.active_swaps / 3.0,
            steps_since_shuffle,
            steps_since_swap,
            min(1.0, state.scan_rate / 0.2),
            0.5, 0.5, 0.5, 0.5,  # Last action intensities (placeholder)
        ], dtype=np.float32)


# =============================================================================
# Action Executor
# =============================================================================
class ActionExecutor:
    """RL 액션 실행기"""
    
    def __init__(self, mtd_controller: IptablesMTDController):
        self.mtd_controller = mtd_controller
        self.action_history: List[Dict] = []
    
    def execute_action(self, action: np.ndarray, state: RealTimeState) -> Dict[str, Any]:
        """액션 실행"""
        scaled = scale_action(action)
        result = {
            "timestamp": time.time(),
            "action_raw": [float(x) for x in action],  # numpy -> float 변환
            "action_scaled": [float(x) for x in scaled],  # numpy -> float 변환
            "executed": [],
            "total_cost": 0.0,
        }
        
        # Shuffle
        if scaled[0] > 0.25:
            for svc in ["fc_mavlink", "cc_sitl", "gcs_mavlink"]:
                if self.mtd_controller.shuffle_network(svc, float(scaled[0])):
                    result["executed"].append(f"shuffle:{svc}")
            result["total_cost"] += float(scaled[0]) * 0.25
        
        # Port Hop
        if scaled[1] > 0.35:
            for svc in ["fc_mavlink", "gcs_mavlink"]:
                if self.mtd_controller.port_hop(svc, float(scaled[1])):
                    result["executed"].append(f"port_hop:{svc}")
            result["total_cost"] += float(scaled[1]) * 0.15
        
        # Decoy
        if scaled[2] > 0.4:
            decoy_count = max(1, int(scaled[2] * 3))
            decoys = self.mtd_controller.activate_decoy("fc_mavlink", decoy_count)
            if decoys:
                result["executed"].append(f"decoy:{len(decoys)}")
            result["total_cost"] += float(scaled[2]) * 0.12
        
        # Blacklist
        if scaled[3] > 0.6 and state.suspicious_ips:
            for ip in state.suspicious_ips[:3]:
                duration = 60 + float(scaled[4]) * 240
                if self.mtd_controller.add_to_blacklist(ip, duration):
                    result["executed"].append(f"blacklist:{ip}")
            result["total_cost"] += float(scaled[3]) * 0.08
        
        # Service Swap
        if scaled[5] > 0.30:
            if scaled[6] > 0.5:
                success, cost = self.mtd_controller.swap_with_decoy("fc_mavlink", float(scaled[5]))
                if success:
                    result["executed"].append("swap:fc_mavlink<->decoy")
                    result["total_cost"] += float(cost.get("total", 0))
            else:
                success, cost = self.mtd_controller.service_swap("cc_sitl", "sim_sitl", float(scaled[5]))
                if success:
                    result["executed"].append("swap:cc_sitl<->sim_sitl")
                    result["total_cost"] += float(cost.get("total", 0))
        
        self.action_history.append(result)
        return result


# =============================================================================
# Metrics Logger (수정됨)
# =============================================================================
class MetricsLogger:
    """메트릭 로깅 및 시각화 - numpy 타입 자동 변환"""
    
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_history: List[Dict] = []
        self.step_times: List[float] = []
        self.costs: List[float] = []
        self.diversity_scores: List[float] = []
        self.actions_executed: List[int] = []
    
    def log_step(self, step: int, state: RealTimeState, action_result: Dict, mtd_stats: Dict):
        """스텝 메트릭 기록 - 모든 값을 Python native 타입으로 변환"""
        metrics = {
            "step": int(step),
            "timestamp": float(time.time()),
            "diversity_score": float(state.diversity_score),
            "redundancy_score": float(state.redundancy_score),
            "confusion_level": float(state.confusion_level),
            "active_decoys": int(state.active_decoys),
            "active_swaps": int(state.active_swaps),
            "blocked_ips": len(state.blocked_ips),
            "scan_detected": bool(state.scan_detected),
            "cti_threat_level": float(state.cti_threat_level),
            "action_cost": float(action_result["total_cost"]),
            "actions_executed": len(action_result["executed"]),
            "total_shuffles": int(mtd_stats.get("total_shuffles", 0)),
            "total_swaps": int(mtd_stats.get("total_service_swaps", 0)),
            "total_decoy_hits": int(mtd_stats.get("total_decoy_hits", 0)),
        }
        
        self.metrics_history.append(metrics)
        self.step_times.append(metrics["timestamp"])
        self.costs.append(action_result["total_cost"])
        self.diversity_scores.append(state.diversity_score)
        self.actions_executed.append(len(action_result["executed"]))
    
    def save_metrics(self):
        """메트릭 JSON 저장 - NumpyJSONEncoder 사용"""
        path = self.log_dir / f"deployment_metrics_{int(time.time())}.json"
        
        # 저장 전 모든 데이터를 serializable하게 변환
        serializable_history = to_serializable(self.metrics_history)
        
        with open(path, 'w') as f:
            json.dump(serializable_history, f, indent=2, cls=NumpyJSONEncoder)
        logger.info(f"Metrics saved: {path}")
        return path
    
    def generate_deployment_figures(self):
        """배포 세션 요약 그래프 생성"""
        if not IEEE_FIGURES_AVAILABLE or len(self.metrics_history) < 2:
            return
        
        setup_ieee_style()
        
        fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.5))
        
        steps = list(range(len(self.metrics_history)))
        
        # (a) Diversity Score
        ax = axes[0, 0]
        ax.plot(steps, self.diversity_scores, color='#0072B2', linewidth=1.0)
        ax.fill_between(steps, self.diversity_scores, alpha=0.3, color='#0072B2')
        ax.set_xlabel('Step')
        ax.set_ylabel('Diversity Score')
        ax.set_title('(a) Configuration Diversity')
        ax.set_ylim(0, 1)
        
        # (b) Cumulative Cost
        ax = axes[0, 1]
        cumulative_cost = np.cumsum(self.costs)
        ax.plot(steps, cumulative_cost, color='#E69F00', linewidth=1.0)
        ax.set_xlabel('Step')
        ax.set_ylabel('Cumulative Cost')
        ax.set_title('(b) MTD Cost Over Time')
        
        # (c) Actions per Step
        ax = axes[1, 0]
        ax.bar(steps, self.actions_executed, color='#009E73', alpha=0.7)
        ax.set_xlabel('Step')
        ax.set_ylabel('Actions Executed')
        ax.set_title('(c) MTD Actions per Step')
        
        # (d) Threat Level & Confusion
        ax = axes[1, 1]
        threat_levels = [m.get('cti_threat_level', 0) for m in self.metrics_history]
        confusion_levels = [m.get('confusion_level', 0) for m in self.metrics_history]
        ax.plot(steps, threat_levels, color='#D73027', linewidth=1.0, label='Threat Level')
        ax.plot(steps, confusion_levels, color='#4575B4', linewidth=1.0, label='Attacker Confusion')
        ax.set_xlabel('Step')
        ax.set_ylabel('Level')
        ax.set_title('(d) Threat vs Confusion')
        ax.legend(loc='upper right', fontsize=7)
        ax.set_ylim(0, 1)
        
        plt.tight_layout()
        
        path = self.log_dir / f"deployment_summary_{int(time.time())}.png"
        plt.savefig(path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Deployment summary figure saved: {path}")
        return path


# =============================================================================
# RL Deception Manager (수정됨)
# =============================================================================
class RLDeceptionManager:
    """RL 기반 Deception 매니저"""
    
    def __init__(
        self,
        model_path: str,
        mtd_controller: IptablesMTDController,
        cti_file: Optional[str] = None,
        network_monitor_file: Optional[str] = None,
        decision_interval: float = 5.0,
        log_dir: Optional[str] = None,
        device: str = "cpu",
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required")
        
        self.device = device
        self.decision_interval = decision_interval
        self.log_dir = log_dir or "logs/deployment"
        
        self.mtd_controller = mtd_controller
        self.state_collector = StateCollector(mtd_controller, cti_file, network_monitor_file)
        self.action_executor = ActionExecutor(mtd_controller)
        self.metrics_logger = MetricsLogger(self.log_dir)
        
        # Policy 로드
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        self._load_policy(model_path)
        
        self.running = False
        self.step_count = 0
        self.total_cost = 0.0
        
        logger.info(f"RLDeceptionManager initialized (model={model_path})")
    
    def _load_policy(self, model_path: str):
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
        else:
            self.policy.load_state_dict(checkpoint)
        self.policy.eval()
        logger.info(f"✅ Policy loaded: {model_path}")
    
    def get_action(self, state_vector: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state_vector).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
        return action.cpu().numpy().squeeze()
    
    def step(self) -> Dict[str, Any]:
        """한 스텝 실행"""
        self.step_count += 1
        self.mtd_controller.set_step(self.step_count)
        
        state_vector = self.state_collector.get_state_vector()
        current_state = self.state_collector.last_state
        
        action = self.get_action(state_vector)
        result = self.action_executor.execute_action(action, current_state)
        
        self.total_cost += result["total_cost"]
        
        mtd_stats = self.mtd_controller.get_statistics()
        self.metrics_logger.log_step(self.step_count, current_state, result, mtd_stats)
        
        if result["executed"]:
            logger.info(f"Step {self.step_count}: Executed {len(result['executed'])} actions")
        
        return {"step": self.step_count, "actions": result["executed"], "cost": result["total_cost"]}
    
    def _save_mtd_state_safe(self, filepath: str):
        """MTD 상태를 안전하게 JSON으로 저장 (numpy 타입 변환 포함)"""
        try:
            # MTD 상태 가져오기
            state = self.mtd_controller.get_mtd_state_for_attacker()
            
            # numpy 타입을 Python native 타입으로 변환
            serializable_state = to_serializable(state)
            
            with open(filepath, 'w') as f:
                json.dump(serializable_state, f, indent=2, cls=NumpyJSONEncoder)
                
        except Exception as e:
            logger.warning(f"Failed to save MTD state: {e}")
    
    def run(self, max_steps: Optional[int] = None):
        """메인 루프 (수정됨)"""
        self.running = True
        logger.info("Starting RL Deception Manager...")
        
        def signal_handler(sig, frame):
            logger.info("Shutdown signal received")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                if max_steps and self.step_count >= max_steps:
                    logger.info(f"Reached max steps ({max_steps})")
                    break
                
                self.step()
                
                # 핵심 수정: 안전한 JSON 저장 메서드 사용
                self._save_mtd_state_safe("/tmp/mtd_state.json")
                
                time.sleep(self.decision_interval)
        
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """종료 처리"""
        self.running = False
        logger.info("Shutting down...")
        
        # 메트릭 저장
        self.metrics_logger.save_metrics()
        
        # 그래프 생성
        if IEEE_FIGURES_AVAILABLE:
            self.metrics_logger.generate_deployment_figures()
        
        # 통계 출력
        stats = self.mtd_controller.get_statistics()
        logger.info(f"Final Statistics:")
        logger.info(f"  Total steps: {self.step_count}")
        logger.info(f"  Total cost: {self.total_cost:.2f}")
        logger.info(f"  Shuffles: {stats['total_shuffles']}")
        logger.info(f"  Service swaps: {stats['total_service_swaps']}")
        logger.info(f"  Decoy hits: {stats['total_decoy_hits']}")
        
        self.mtd_controller.cleanup()
        logger.info("Shutdown complete")


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="RL-Driven Deception Manager v09 (Fixed)")
    parser.add_argument("--model", type=str, required=True, help="Path to trained model")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry-run mode")
    parser.add_argument("--interval", type=float, default=5.0, help="Decision interval (sec)")
    parser.add_argument("--max-steps", type=int, default=None, help="Max steps")
    parser.add_argument("--cti-file", type=str, default=None)
    parser.add_argument("--network-monitor-file", type=str, default=None)
    parser.add_argument("--log-dir", type=str, default="logs/deployment")
    parser.add_argument("--state-file", type=str, default=None)
    
    args = parser.parse_args()
    
    mtd_controller = IptablesMTDController(dry_run=args.dry_run, state_file=args.state_file)
    
    manager = RLDeceptionManager(
        model_path=args.model,
        mtd_controller=mtd_controller,
        cti_file=args.cti_file,
        network_monitor_file=args.network_monitor_file,
        decision_interval=args.interval,
        log_dir=args.log_dir,
    )
    
    manager.run(max_steps=args.max_steps)


if __name__ == "__main__":
    main()