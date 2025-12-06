#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RL-Driven Deception Manager v08 - 실제 테스트베드 배포용
=========================================================

학습된 RL 정책을 실제 테스트베드에서 실행하는 매니저.
iptables MTD Controller와 연동하여 실시간 방어 수행.

주요 기능:
1. 학습된 PPO 정책 로드 및 실행
2. 실시간 상태 수집 (MAVLink, 네트워크 모니터링)
3. iptables MTD Controller 연동
4. CTI Agent 연동 (선택적)
5. 로깅 및 메트릭 수집

저자: MTD-RL Research Team
버전: 0.8.3
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
    to_serializable,
)
from iptables_mtd_controller_v08 import IptablesMTDController

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [RL-Manager] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RLDeceptionManager")


# =============================================================================
# Actor-Critic Network (rl_train_v08.py에서 복사)
# =============================================================================
if TORCH_AVAILABLE:
    class ActorCritic(nn.Module):
        """Actor-Critic 네트워크"""

        def __init__(
            self,
            state_dim: int,
            action_dim: int,
            hidden_size: int = 256,
            num_layers: int = 2,
        ):
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

        def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            features = self.shared(state)
            action_mean = self.actor(features)
            value = self.critic(features)
            return action_mean, value

        def act(
            self,
            state: torch.Tensor,
            deterministic: bool = True,
        ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
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
# State Collector
# =============================================================================
@dataclass
class RealTimeState:
    """실시간 상태 데이터"""
    timestamp: float = field(default_factory=time.time)
    
    # 공격 탐지 관련
    scan_detected: bool = False
    scan_rate: float = 0.0
    suspicious_ips: List[str] = field(default_factory=list)
    blocked_ips: List[str] = field(default_factory=list)
    
    # 서비스 상태
    services_up: int = 6
    services_discovered: int = 0
    critical_exposed: bool = False
    
    # MTD 상태
    diversity_score: float = 0.0
    redundancy_score: float = 0.0
    confusion_level: float = 0.0
    active_decoys: int = 0
    active_swaps: int = 0
    
    # 네트워크 상태
    network_latency_ms: float = 0.0
    packet_loss_rate: float = 0.0
    
    # CTI 관련
    cti_alert: bool = False
    cti_threat_level: float = 0.0
    cti_attack_type: Optional[str] = None


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
        
        self.state_history: deque = deque(maxlen=100)
        self.last_state = RealTimeState()
        
        self._lock = threading.Lock()
    
    def collect_state(self) -> RealTimeState:
        """현재 상태 수집"""
        with self._lock:
            state = RealTimeState()
            
            # MTD Controller에서 상태 가져오기
            mtd_state = self.mtd_controller.get_mtd_state_for_attacker()
            state.diversity_score = mtd_state.get("diversity_score", 0.0)
            state.redundancy_score = mtd_state.get("redundancy_score", 0.0)
            state.confusion_level = mtd_state.get("confusion_level", 0.0)
            state.active_decoys = mtd_state.get("decoy_count", 0)
            state.active_swaps = mtd_state.get("active_swap_count", 0)
            
            stats = self.mtd_controller.get_statistics()
            state.blocked_ips = list(self.mtd_controller.blacklist.keys())
            
            # CTI 파일에서 위협 정보 로드
            if self.cti_file and self.cti_file.exists():
                try:
                    with open(self.cti_file, 'r') as f:
                        cti_data = json.load(f)
                    state.cti_alert = cti_data.get("alert", False)
                    state.cti_threat_level = cti_data.get("threat_level", 0.0)
                    state.cti_attack_type = cti_data.get("attack_type")
                except Exception as e:
                    logger.warning(f"Failed to read CTI file: {e}")
            
            # 네트워크 모니터 파일에서 스캔 탐지 정보 로드
            if self.network_monitor_file and self.network_monitor_file.exists():
                try:
                    with open(self.network_monitor_file, 'r') as f:
                        net_data = json.load(f)
                    state.scan_detected = net_data.get("scan_detected", False)
                    state.scan_rate = net_data.get("scan_rate", 0.0)
                    state.suspicious_ips = net_data.get("suspicious_ips", [])
                    state.services_discovered = net_data.get("services_discovered", 0)
                    state.critical_exposed = net_data.get("critical_exposed", False)
                except Exception as e:
                    logger.warning(f"Failed to read network monitor file: {e}")
            
            self.last_state = state
            self.state_history.append(state)
            
            return state
    
    def get_state_vector(self) -> np.ndarray:
        """RL 정책 입력용 상태 벡터 생성 (17차원)"""
        state = self.collect_state()
        
        # 스캔 비율 추정
        scanned_ratio = min(1.0, state.scan_rate / 0.2) if state.scan_detected else 0.0
        
        # 서비스 발견 비율
        discovered_ratio = state.services_discovered / 6.0
        
        # 익스플로잇 진행도 추정
        exploit_progress = 0.0
        if state.cti_threat_level > 0.5:
            exploit_progress = (state.cti_threat_level - 0.5) * 2
        
        # 침투 진행도
        compromise_progress = 0.0
        if state.cti_attack_type in ["lateral_movement", "data_exfiltration"]:
            compromise_progress = 0.5
        if state.cti_attack_type == "command_control":
            compromise_progress = 1.0
        
        # 에너지 (공격자 지속성 추정)
        energy = max(0.0, 1.0 - len(state.blocked_ips) * 0.1)
        
        # 마지막 셔플/스왑 이후 시간
        last_action = self.mtd_controller.stats.last_action_time or time.time()
        steps_since_shuffle = min(1.0, (time.time() - last_action) / 300)
        
        last_swap = self.mtd_controller.stats.last_swap_time or time.time()
        steps_since_swap = min(1.0, (time.time() - last_swap) / 300)
        
        # 상태 벡터 구성 (17차원)
        state_vector = np.array([
            scanned_ratio,                          # 0: search_space_scanned_ratio
            discovered_ratio,                       # 1: services_discovered_ratio
            float(state.critical_exposed),          # 2: critical_discovered
            exploit_progress,                       # 3: exploitation_progress
            compromise_progress,                    # 4: compromise_progress
            state.diversity_score,                  # 5: current_diversity
            state.redundancy_score,                 # 6: current_redundancy
            state.active_decoys / 4.0,              # 7: decoy_engagement_rate
            energy,                                 # 8: energy_remaining_ratio
            state.active_swaps / 3.0,               # 9: swap_active_ratio
            steps_since_shuffle,                    # 10: steps_since_shuffle
            steps_since_swap,                       # 11: steps_since_swap
            min(1.0, state.scan_rate / 0.2),        # 12: attacker_scan_rate
            0.5,                                    # 13: last_shuffle_intensity
            0.5,                                    # 14: last_port_hop_intensity
            0.5,                                    # 15: last_decoy_ratio
            0.5,                                    # 16: last_swap_intensity
        ], dtype=np.float32)
        
        return state_vector


# =============================================================================
# Action Executor
# =============================================================================
class ActionExecutor:
    """RL 액션 실행기"""
    
    def __init__(self, mtd_controller: IptablesMTDController):
        self.mtd_controller = mtd_controller
        self.last_action = np.zeros(ACTION_DIM)
        self.action_history: List[Dict] = []
    
    def execute_action(
        self,
        action: np.ndarray,
        state: RealTimeState,
    ) -> Dict[str, Any]:
        """RL 액션을 실제 MTD 명령으로 변환 및 실행"""
        scaled = scale_action(action)
        result = {
            "timestamp": time.time(),
            "action_raw": action.tolist(),
            "action_scaled": scaled.tolist(),
            "executed": [],
            "total_cost": 0.0,
        }
        
        # 1. Network Shuffle
        shuffle_intensity = scaled[0]
        if shuffle_intensity > 0.25:
            services = ["fc_mavlink", "cc_sitl", "gcs_mavlink"]
            for svc in services:
                if self.mtd_controller.shuffle_network(svc, shuffle_intensity):
                    result["executed"].append(f"shuffle:{svc}")
            result["total_cost"] += shuffle_intensity * 0.25
        
        # 2. Port Hop
        port_hop_intensity = scaled[1]
        if port_hop_intensity > 0.35:
            for svc in ["fc_mavlink", "gcs_mavlink"]:
                if self.mtd_controller.port_hop(svc, port_hop_intensity):
                    result["executed"].append(f"port_hop:{svc}")
            result["total_cost"] += port_hop_intensity * 0.15
        
        # 3. Decoy Activation
        decoy_ratio = scaled[2]
        if decoy_ratio > 0.4:
            decoy_count = max(1, int(decoy_ratio * 3))
            decoys = self.mtd_controller.activate_decoy("fc_mavlink", decoy_count)
            if decoys:
                result["executed"].append(f"decoy:{len(decoys)}")
            result["total_cost"] += decoy_ratio * 0.12
        
        # 4. Blacklist
        blacklist_aggression = scaled[3]
        blacklist_duration = scaled[4]
        if blacklist_aggression > 0.6 and state.suspicious_ips:
            for ip in state.suspicious_ips[:3]:
                duration = 60 + blacklist_duration * 240
                if self.mtd_controller.add_to_blacklist(ip, duration):
                    result["executed"].append(f"blacklist:{ip}")
            result["total_cost"] += blacklist_aggression * 0.08
        
        # 5. Service Swap
        swap_intensity = scaled[5]
        swap_target = scaled[6]
        if swap_intensity > 0.30:
            if swap_target > 0.5:
                # Critical 서비스와 디코이 스왑
                success, cost = self.mtd_controller.swap_with_decoy(
                    "fc_mavlink", swap_intensity
                )
                if success:
                    result["executed"].append("swap:fc_mavlink<->decoy")
                    result["total_cost"] += cost.get("total", 0)
            else:
                # 일반 서비스 스왑
                success, cost = self.mtd_controller.service_swap(
                    "cc_sitl", "sim_sitl", swap_intensity
                )
                if success:
                    result["executed"].append("swap:cc_sitl<->sim_sitl")
                    result["total_cost"] += cost.get("total", 0)
        
        self.last_action = action.copy()
        self.action_history.append(result)
        
        return result


# =============================================================================
# RL Deception Manager
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
            raise RuntimeError("PyTorch is required for RL Deception Manager")
        
        self.device = device
        self.decision_interval = decision_interval
        self.log_dir = Path(log_dir) if log_dir else None
        
        # MTD Controller
        self.mtd_controller = mtd_controller
        
        # State Collector
        self.state_collector = StateCollector(
            mtd_controller=mtd_controller,
            cti_file=cti_file,
            network_monitor_file=network_monitor_file,
        )
        
        # Action Executor
        self.action_executor = ActionExecutor(mtd_controller)
        
        # RL Policy 로드
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        self._load_policy(model_path)
        
        # 실행 상태
        self.running = False
        self.step_count = 0
        self.total_cost = 0.0
        self.metrics_history: List[Dict] = []
        
        # 로그 디렉토리 생성
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"RLDeceptionManager initialized (model={model_path})")
    
    def _load_policy(self, model_path: str):
        """정책 모델 로드"""
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=True)
        
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
        else:
            self.policy.load_state_dict(checkpoint)
        
        self.policy.eval()
        logger.info(f"✅ Policy loaded from {model_path}")
    
    def get_action(self, state_vector: np.ndarray) -> np.ndarray:
        """RL 정책에서 액션 가져오기"""
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state_vector).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
        return action.cpu().numpy().squeeze()
    
    def step(self) -> Dict[str, Any]:
        """한 스텝 실행"""
        self.step_count += 1
        self.mtd_controller.set_step(self.step_count)
        
        # 1. 상태 수집
        state_vector = self.state_collector.get_state_vector()
        current_state = self.state_collector.last_state
        
        # 2. RL 정책으로 액션 결정
        action = self.get_action(state_vector)
        
        # 3. 액션 실행
        result = self.action_executor.execute_action(action, current_state)
        
        # 4. 메트릭 기록
        self.total_cost += result["total_cost"]
        
        metrics = {
            "step": self.step_count,
            "timestamp": time.time(),
            "state": asdict(current_state),
            "action": result,
            "mtd_stats": self.mtd_controller.get_statistics(),
            "cumulative_cost": self.total_cost,
        }
        self.metrics_history.append(metrics)
        
        # 5. 로깅
        if result["executed"]:
            logger.info(
                f"Step {self.step_count}: "
                f"Executed {len(result['executed'])} actions: {result['executed']}"
            )
        
        return metrics
    
    def run(self, max_steps: Optional[int] = None):
        """메인 실행 루프"""
        self.running = True
        logger.info("Starting RL Deception Manager...")
        
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                if max_steps and self.step_count >= max_steps:
                    logger.info(f"Reached max steps ({max_steps})")
                    break
                
                metrics = self.step()
                
                # MTD 상태 파일 업데이트
                self.mtd_controller.save_mtd_state_json("/tmp/mtd_state.json")
                
                time.sleep(self.decision_interval)
        
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """종료 처리"""
        self.running = False
        logger.info("Shutting down RL Deception Manager...")
        
        # 메트릭 저장
        if self.log_dir and self.metrics_history:
            metrics_file = self.log_dir / f"metrics_{int(time.time())}.json"
            with open(metrics_file, 'w') as f:
                json.dump(self.metrics_history, f, indent=2, default=to_serializable)
            logger.info(f"Metrics saved to {metrics_file}")
        
        # 통계 출력
        stats = self.mtd_controller.get_statistics()
        logger.info(f"Final Statistics:")
        logger.info(f"  Total steps: {self.step_count}")
        logger.info(f"  Total cost: {self.total_cost:.2f}")
        logger.info(f"  Shuffles: {stats['total_shuffles']}")
        logger.info(f"  Service swaps: {stats['total_service_swaps']}")
        logger.info(f"  Decoy hits: {stats['total_decoy_hits']}")
        
        # MTD 정리
        self.mtd_controller.cleanup()
        
        logger.info("Shutdown complete")


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="RL-Driven Deception Manager v08.3")
    
    parser.add_argument(
        "--model", type=str, required=True,
        help="Path to trained RL model"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Run in dry-run mode (no actual iptables changes)"
    )
    parser.add_argument(
        "--interval", type=float, default=5.0,
        help="Decision interval in seconds"
    )
    parser.add_argument(
        "--max-steps", type=int, default=None,
        help="Maximum number of steps (None for infinite)"
    )
    parser.add_argument(
        "--cti-file", type=str, default=None,
        help="Path to CTI alert file"
    )
    parser.add_argument(
        "--network-monitor-file", type=str, default=None,
        help="Path to network monitor file"
    )
    parser.add_argument(
        "--log-dir", type=str, default="logs/rl_manager",
        help="Directory for log files"
    )
    parser.add_argument(
        "--state-file", type=str, default=None,
        help="Path to MTD state file"
    )
    
    args = parser.parse_args()
    
    # MTD Controller 생성
    mtd_controller = IptablesMTDController(
        dry_run=args.dry_run,
        state_file=args.state_file,
    )
    
    # Manager 생성 및 실행
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
