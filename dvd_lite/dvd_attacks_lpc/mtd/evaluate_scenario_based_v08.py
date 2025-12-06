#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실제 시나리오 기반 MTD 비교 평가 (v08) - 수정본
==============================================

수정사항:
1. STATE_DIM 17차원 호환 (Service Swap 추가)
2. WandB 로깅 지원
3. Diversity/Redundancy/Shuffle 상세 메트릭

비교 대상:
1. No MTD: 방어 없음 (baseline)
2. Static MTD: 고정 주기 셔플
3. Heuristic MTD + CTI: 규칙 기반 + CTI Agent
4. RL MTD + CTI: 학습된 RL 정책 + CTI Agent

측정 지표:
- S_MTD: 종합 MTD 효과성 점수
- Defense Success Rate: 방어 성공률
- MTTD: Mean Time To Detect
- MTTR: Mean Time To Respond
- Cost: MTD 비용
- Diversity/Redundancy/Shuffle 메트릭

저자: MTD-RL Research Team
버전: 0.8.1
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import subprocess
import threading
import signal

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# 로컬 모듈
try:
    from rl_config_v08 import STATE_DIM, ACTION_DIM, ACTION_PARAM_KEYS, MTDConfig, FEATURE_KEYS
    from iptables_mtd_controller_v08 import IptablesMTDController
    HAS_LOCAL = True
except ImportError:
    HAS_LOCAL = False
    STATE_DIM = 17  # 기본값
    ACTION_DIM = 7
    print("⚠️ Local modules not found, using defaults")

# PyTorch
try:
    import torch
    from rl_train_v08 import ActorCritic
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# WandB
try:
    import wandb
    HAS_WANDB = True
except ImportError:
    HAS_WANDB = False

# 로깅
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("MTD-Eval")


# =============================================================================
# 설정
# =============================================================================

# 경로
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "mtd_rl_v08" else SCRIPT_DIR

# 공격 시나리오 정의
ATTACK_SCENARIOS = {
    "reconnaissance": {
        "name": "정찰 시나리오",
        "attacks": [
            ("drone-discovery", 30),
            ("companion-computer-discovery", 30),
            ("ground-control-station-discovery", 30),
        ],
        "seeker_levels": [0, 1],
        "description": "네트워크 스캔 및 서비스 탐색",
    },
    "gps_spoofing": {
        "name": "GPS 스푸핑 시나리오",
        "attacks": [
            ("gps-spoofing", 60),
            ("gps-data-injection", 45),
            ("satellite-spoofing", 45),
        ],
        "seeker_levels": [2, 3],
        "description": "위치 정보 위변조 공격",
    },
    "command_injection": {
        "name": "명령 주입 시나리오",
        "attacks": [
            ("waypoint-injection", 45),
            ("return-to-home-point-override", 45),
            ("camera-gimbal-takeover", 30),
        ],
        "seeker_levels": [2, 3],
        "description": "드론 제어 명령 주입",
    },
    "dos_attack": {
        "name": "DoS 공격 시나리오",
        "attacks": [
            ("communication-link-flooding", 60),
            ("wifi-deauth-attack", 45),
        ],
        "seeker_levels": [1, 2],
        "description": "서비스 거부 공격",
    },
    "data_exfiltration": {
        "name": "데이터 유출 시나리오",
        "attacks": [
            ("flight-log-extraction", 45),
            ("mission-extraction", 45),
            ("wifi-client-data-leak", 30),
        ],
        "seeker_levels": [1, 2],
        "description": "민감 정보 유출",
    },
    "critical_attack": {
        "name": "치명적 공격 시나리오",
        "attacks": [
            ("flight-termination", 30),
            ("denial-of-takeoff", 30),
            ("geofencing-attack", 45),
        ],
        "seeker_levels": [3, 4],
        "description": "비행 안전 위협",
    },
    "mixed_apt": {
        "name": "APT 복합 시나리오",
        "attacks": [
            ("drone-discovery", 20),
            ("gps-spoofing", 40),
            ("waypoint-injection", 30),
            ("flight-log-extraction", 30),
        ],
        "seeker_levels": [3, 4],
        "description": "다단계 APT 공격",
    },
}


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class AttackEvent:
    """공격 이벤트"""
    timestamp: float
    attack_name: str
    severity: int  # 1-4
    detected: bool = False
    blocked: bool = False
    detection_time: Optional[float] = None
    response_time: Optional[float] = None


@dataclass
class EvaluationMetrics:
    """평가 지표"""
    scenario_name: str
    mtd_mode: str
    seeker_level: int
    
    # 방어 성능
    attacks_total: int = 0
    attacks_detected: int = 0
    attacks_blocked: int = 0
    breaches: int = 0
    
    # 시간 지표
    total_duration: float = 0.0
    mttd: float = 0.0  # Mean Time To Detect
    mttr: float = 0.0  # Mean Time To Respond
    
    # MTD 지표
    s_mtd_score: float = 0.0
    diversity_avg: float = 0.0
    diversity_min: float = 1.0
    diversity_max: float = 0.0
    redundancy_avg: float = 0.0
    shuffle_count: int = 0
    port_hop_count: int = 0
    swap_count: int = 0
    decoy_hits: int = 0
    decoy_activations: int = 0
    
    # 비용 지표
    mtd_cost: float = 0.0
    service_availability: float = 1.0
    
    # 상세 로그
    events: List[Dict] = field(default_factory=list)
    diversity_history: List[float] = field(default_factory=list)
    redundancy_history: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['defense_rate'] = self.attacks_blocked / max(1, self.attacks_total)
        d['detection_rate'] = self.attacks_detected / max(1, self.attacks_total)
        # List 필드는 평균만 저장
        d['diversity_history'] = len(self.diversity_history)
        d['redundancy_history'] = len(self.redundancy_history)
        return d


# =============================================================================
# MTD 전략 클래스
# =============================================================================

class BaseMTDStrategy:
    """MTD 전략 베이스"""
    name = "Base"
    
    def __init__(self, controller: IptablesMTDController):
        self.controller = controller
        self.step = 0
        self.last_shuffle_step = 0
    
    def reset(self):
        self.step = 0
        self.last_shuffle_step = 0
    
    def on_step(self, state: Dict) -> Dict[str, Any]:
        """매 스텝 호출, 액션 반환"""
        raise NotImplementedError
    
    def on_cti_alert(self, alert: Dict) -> Dict[str, Any]:
        """CTI 알림 시 호출"""
        return {}


class NoMTDStrategy(BaseMTDStrategy):
    """No MTD - 방어 없음"""
    name = "No MTD"
    
    def on_step(self, state: Dict) -> Dict[str, Any]:
        self.step += 1
        return {"action": "none"}


class StaticMTDStrategy(BaseMTDStrategy):
    """Static MTD - 고정 주기 셔플"""
    name = "Static MTD"
    
    def __init__(self, controller: IptablesMTDController, shuffle_period: int = 30):
        super().__init__(controller)
        self.shuffle_period = shuffle_period
    
    def on_step(self, state: Dict) -> Dict[str, Any]:
        self.step += 1
        action = {"action": "none"}
        
        if self.step % self.shuffle_period == 0:
            # 모든 서비스 셔플
            shuffled = self.controller.shuffle_all_services(intensity=0.6)
            self.last_shuffle_step = self.step
            action = {
                "action": "shuffle",
                "intensity": 0.6,
                "services_shuffled": shuffled,
            }
            logger.debug(f"[Static] Periodic shuffle at step {self.step}")
        
        return action


class HeuristicCTIMTDStrategy(BaseMTDStrategy):
    """Heuristic + CTI MTD - 규칙 기반 + CTI 연동"""
    name = "Heuristic+CTI MTD"
    
    def __init__(self, controller: IptablesMTDController):
        super().__init__(controller)
        self.threat_level = 0.0
        self.cti_cooldown = 0
    
    def reset(self):
        super().reset()
        self.threat_level = 0.0
        self.cti_cooldown = 0
    
    def on_step(self, state: Dict) -> Dict[str, Any]:
        self.step += 1
        action = {"action": "none"}
        
        # 쿨다운 감소
        if self.cti_cooldown > 0:
            self.cti_cooldown -= 1
        
        # 위협 레벨 감쇠
        self.threat_level *= 0.95
        
        # 상태 기반 규칙
        scan_rate = state.get("scan_rate", 0)
        suspicious_conns = state.get("suspicious_connections", 0)
        diversity = self.controller.get_diversity_score()
        
        # Rule 1: 주기적 셔플 (45 step)
        if self.step - self.last_shuffle_step >= 45:
            self.controller.shuffle_all_services(intensity=0.4)
            self.last_shuffle_step = self.step
            action = {"action": "shuffle", "intensity": 0.4, "reason": "periodic"}
        
        # Rule 2: 스캔 감지 시 셔플
        if scan_rate > 5 and self.step - self.last_shuffle_step >= 10:
            self.controller.shuffle_all_services(intensity=0.6)
            self.last_shuffle_step = self.step
            action = {"action": "shuffle", "intensity": 0.6, "reason": "scan_detected"}
        
        # Rule 3: 의심 연결 시 디코이
        if suspicious_conns > 3:
            self.controller.activate_decoy("fc_mavlink", decoy_count=1)
            action["decoy"] = True
            action["decoy_count"] = 1
        
        # Rule 4: 다양성 낮으면 셔플
        if diversity < 0.3:
            self.controller.shuffle_all_services(intensity=0.5)
            self.last_shuffle_step = self.step
            action = {"action": "shuffle", "intensity": 0.5, "reason": "low_diversity"}
        
        return action
    
    def on_cti_alert(self, alert: Dict) -> Dict[str, Any]:
        """CTI 알림 처리"""
        if self.cti_cooldown > 0:
            return {"action": "cooldown"}
        
        alert_level = alert.get("level", 1)
        attack_type = alert.get("type", "unknown")
        
        self.threat_level = max(self.threat_level, alert_level / 4.0)
        
        action = {"action": "cti_response", "alert_level": alert_level}
        
        if alert_level >= 3:
            # 높은 위협: 전면 대응
            self.controller.shuffle_all_services(intensity=0.9)
            self.controller.activate_decoy("fc_mavlink", decoy_count=2)
            self.controller.activate_decoy("gcs_mavlink", decoy_count=1)
            self.cti_cooldown = 15
            self.last_shuffle_step = self.step
            action["intensity"] = 0.9
            action["decoys"] = 3
            logger.info(f"[Heuristic+CTI] High threat response: {attack_type}")
            
        elif alert_level >= 2:
            # 중간 위협
            self.controller.shuffle_all_services(intensity=0.7)
            self.controller.activate_decoy("cc_sitl", decoy_count=1)
            self.cti_cooldown = 10
            self.last_shuffle_step = self.step
            action["intensity"] = 0.7
            action["decoys"] = 1
            
        else:
            # 낮은 위협
            self.controller.shuffle_network("fc_mavlink", intensity=0.5)
            self.cti_cooldown = 5
            action["intensity"] = 0.5
        
        return action


class RLCTIMTDStrategy(BaseMTDStrategy):
    """RL + CTI MTD - 학습된 정책 + CTI 연동"""
    name = "RL+CTI MTD"
    
    def __init__(
        self, 
        controller: IptablesMTDController,
        model_path: str,
        cti_boost: float = 1.3,
    ):
        super().__init__(controller)
        self.model_path = model_path
        self.cti_boost = cti_boost
        self.policy = None
        self.device = "cpu"
        self.cti_alert_active = False
        self.cti_cooldown = 0
        
        self._load_policy()
    
    def _load_policy(self):
        """학습된 정책 로드"""
        if not HAS_TORCH:
            logger.error("PyTorch not available")
            return
        
        if not os.path.exists(self.model_path):
            logger.error(f"Model not found: {self.model_path}")
            return
        
        try:
            checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=True)
            self.policy = ActorCritic(STATE_DIM, ACTION_DIM)
            
            if "policy" in checkpoint:
                self.policy.load_state_dict(checkpoint["policy"])
            elif "model_state_dict" in checkpoint:
                self.policy.load_state_dict(checkpoint["model_state_dict"])
            else:
                self.policy.load_state_dict(checkpoint)
            
            self.policy.eval()
            logger.info(f"[RL+CTI] Policy loaded: {self.model_path} (STATE_DIM={STATE_DIM})")
        except Exception as e:
            logger.error(f"Failed to load policy: {e}")
            self.policy = None
    
    def _build_state_vector(self, state: Dict) -> np.ndarray:
        """
        상태 딕셔너리 → 상태 벡터 (17차원)
        
        rl_config_v08.py의 FEATURE_KEYS와 일치해야 함:
        1. search_space_scanned_ratio
        2. services_discovered_ratio
        3. critical_discovered
        4. exploitation_progress
        5. compromise_progress
        6. current_diversity
        7. current_redundancy
        8. decoy_engagement_rate
        9. energy_remaining_ratio
        10. swap_active_ratio         # [NEW]
        11. steps_since_shuffle
        12. steps_since_swap          # [NEW]
        13. attacker_scan_rate
        14. last_shuffle_intensity
        15. last_port_hop_intensity
        16. last_decoy_ratio
        17. last_swap_intensity       # [NEW]
        """
        diversity = self.controller.get_diversity_score()
        redundancy = self.controller.get_redundancy_score() if hasattr(self.controller, 'get_redundancy_score') else 0.0
        confusion = self.controller.get_confusion_level() if hasattr(self.controller, 'get_confusion_level') else 0.0
        
        # 활성 스왑 비율
        active_swaps = len(self.controller.active_swaps) if hasattr(self.controller, 'active_swaps') else 0
        swap_active_ratio = min(1.0, active_swaps / 3.0)  # 최대 3개 기준 정규화
        
        # 마지막 스왑 이후 스텝
        last_swap_step = 0
        for mapping in self.controller.service_mappings.values():
            if hasattr(mapping, 'last_swap_step'):
                last_swap_step = max(last_swap_step, mapping.last_swap_step)
        steps_since_swap = (self.step - last_swap_step) / 50.0 if last_swap_step > 0 else 1.0
        
        return np.array([
            state.get("scanned_ratio", 0.0),
            state.get("services_discovered", 0.0),
            state.get("critical_discovered", 0.0),
            state.get("exploit_progress", 0.0),
            state.get("compromise_progress", 0.0),
            diversity,
            redundancy,
            state.get("decoy_hits", 0.0) / 10.0,
            state.get("energy", 1.0),
            swap_active_ratio,                              # [NEW] 10번째
            state.get("steps_since_shuffle", 0) / 50.0,
            steps_since_swap,                               # [NEW] 12번째
            state.get("scan_rate", 0.0) / 20.0,
            state.get("last_shuffle", 0.0),
            state.get("last_port_hop", 0.0),
            state.get("last_decoy", 0.0),
            confusion,                                      # [NEW] 17번째 (last_swap_intensity 대신 confusion 사용)
        ], dtype=np.float32)
    
    def _execute_action(self, action: np.ndarray) -> Dict[str, Any]:
        """
        액션 실행 (7차원)
        
        ACTION_PARAM_KEYS:
        0. shuffle_intensity
        1. port_hop_intensity
        2. decoy_ratio
        3. blacklist_aggression
        4. blacklist_duration
        5. service_swap_intensity    # [NEW]
        6. service_swap_target       # [NEW]
        """
        # [-1, 1] → [0, 1]
        scaled = (action + 1) / 2
        
        result = {"action": "rl_policy"}
        
        # shuffle_intensity
        if scaled[0] > 0.3:
            shuffled = self.controller.shuffle_all_services(intensity=float(scaled[0]))
            self.last_shuffle_step = self.step
            result["shuffle"] = float(scaled[0])
            result["shuffle_count"] = shuffled
        
        # port_hop_intensity
        if scaled[1] > 0.4:
            self.controller.port_hop("cc_web", intensity=float(scaled[1]))
            result["port_hop"] = float(scaled[1])
        
        # decoy_ratio
        if scaled[2] > 0.5:
            count = max(1, int(scaled[2] * 3))
            self.controller.activate_decoy("fc_mavlink", decoy_count=count)
            result["decoys"] = count
        
        # blacklist_aggression
        if scaled[3] > 0.6:
            result["blacklist_ready"] = float(scaled[3])
        
        # service_swap_intensity [NEW]
        if len(scaled) > 5 and scaled[5] > 0.35:
            # 스왑 대상 선택 (scaled[6])
            if hasattr(self.controller, 'service_swap'):
                if scaled[6] > 0.5:
                    # Critical 우선: fc_mavlink ↔ decoy
                    success, cost = self.controller.swap_with_decoy("fc_mavlink", intensity=float(scaled[5]))
                else:
                    # 랜덤: cc_sitl ↔ sim_sitl
                    success, cost = self.controller.service_swap("cc_sitl", "sim_sitl", intensity=float(scaled[5]))
                
                if success:
                    result["swap"] = float(scaled[5])
                    result["swap_cost"] = cost.get("total", 0)
        
        return result
    
    def on_step(self, state: Dict) -> Dict[str, Any]:
        self.step += 1
        self.controller.set_step(self.step)
        
        if self.cti_cooldown > 0:
            self.cti_cooldown -= 1
        
        if self.policy is None:
            return {"action": "no_policy"}
        
        # 상태 벡터 구성 (17차원)
        state_vec = self._build_state_vector(state)
        state_tensor = torch.from_numpy(state_vec).unsqueeze(0)
        
        # 정책 추론
        with torch.no_grad():
            action_mean, _ = self.policy(state_tensor)
            action = action_mean.squeeze(0).numpy()
        
        # CTI 부스트
        if self.cti_alert_active:
            action = np.clip(action * self.cti_boost, -1, 1)
            self.cti_alert_active = False
        
        # 액션 실행
        return self._execute_action(action)
    
    def on_cti_alert(self, alert: Dict) -> Dict[str, Any]:
        """CTI 알림 → 다음 스텝에 부스트 적용"""
        alert_level = alert.get("level", 1)
        
        if alert_level >= 2 and self.cti_cooldown == 0:
            self.cti_alert_active = True
            self.cti_cooldown = 10
            logger.info(f"[RL+CTI] Alert received (level={alert_level}), boost activated")
        
        return {"action": "cti_boost_scheduled", "level": alert_level}


# =============================================================================
# 공격 시뮬레이터 (시나리오 기반)
# =============================================================================

class AttackSimulator:
    """공격 시나리오 시뮬레이터"""
    
    def __init__(
        self,
        scenario_name: str,
        seeker_level: int,
        real_execution: bool = False,
    ):
        self.scenario = ATTACK_SCENARIOS.get(scenario_name, ATTACK_SCENARIOS["reconnaissance"])
        self.seeker_level = seeker_level
        self.real_execution = real_execution
        
        self.events: List[AttackEvent] = []
        self.current_attack_idx = 0
        self.step = 0
        self.attack_in_progress = False
        self.attack_start_step = 0
        
        logger.info(f"[Attacker] Scenario: {scenario_name}, Level: {seeker_level}")
    
    def reset(self):
        self.events = []
        self.current_attack_idx = 0
        self.step = 0
        self.attack_in_progress = False
        self.attack_start_step = 0
    
    def _get_attack_severity(self, attack_name: str) -> int:
        """공격 심각도 결정"""
        severity_map = {
            "drone-discovery": 1,
            "companion-computer-discovery": 1,
            "ground-control-station-discovery": 1,
            "gps-spoofing": 3,
            "gps-data-injection": 3,
            "satellite-spoofing": 3,
            "waypoint-injection": 3,
            "return-to-home-point-override": 3,
            "camera-gimbal-takeover": 2,
            "communication-link-flooding": 2,
            "wifi-deauth-attack": 2,
            "flight-log-extraction": 2,
            "mission-extraction": 2,
            "wifi-client-data-leak": 2,
            "flight-termination": 4,
            "denial-of-takeoff": 4,
            "geofencing-attack": 3,
        }
        return severity_map.get(attack_name, 2)
    
    def step_attack(self) -> Optional[AttackEvent]:
        """한 스텝 진행, 공격 이벤트 반환"""
        self.step += 1
        
        attacks = self.scenario["attacks"]
        if self.current_attack_idx >= len(attacks):
            return None  # 모든 공격 완료
        
        attack_name, duration = attacks[self.current_attack_idx]
        
        # 새 공격 시작
        if not self.attack_in_progress:
            self.attack_in_progress = True
            self.attack_start_step = self.step
            
            event = AttackEvent(
                timestamp=time.time(),
                attack_name=attack_name,
                severity=self._get_attack_severity(attack_name),
            )
            self.events.append(event)
            
            logger.info(f"[Attacker] Starting: {attack_name} (duration={duration}s)")
            
            # 실제 실행 (옵션)
            if self.real_execution:
                self._execute_real_attack(attack_name, duration)
            
            return event
        
        # 공격 진행 중 → 종료 체크
        if self.step - self.attack_start_step >= duration:
            self.attack_in_progress = False
            self.current_attack_idx += 1
            logger.info(f"[Attacker] Completed: {attack_name}")
        
        return None
    
    def _execute_real_attack(self, attack_name: str, duration: int):
        """실제 공격 실행 (attack_orchestrator 호출)"""
        try:
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "attack_orchestrator.py"),
                "start", attack_name,
                "-d", str(duration),
            ]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"Failed to execute attack: {e}")
    
    def get_state(self) -> Dict:
        """현재 공격 상태 반환"""
        return {
            "step": self.step,
            "attack_in_progress": self.attack_in_progress,
            "attacks_completed": self.current_attack_idx,
            "total_attacks": len(self.scenario["attacks"]),
            "current_attack": self.scenario["attacks"][self.current_attack_idx][0] 
                             if self.current_attack_idx < len(self.scenario["attacks"]) else None,
        }


# =============================================================================
# CTI 시뮬레이터
# =============================================================================

class CTISimulator:
    """CTI Agent 시뮬레이터"""
    
    def __init__(self, detection_delay: int = 3, detection_prob: float = 0.8):
        self.detection_delay = detection_delay
        self.detection_prob = detection_prob
        self.pending_detections: List[Tuple[int, AttackEvent]] = []
    
    def reset(self):
        self.pending_detections = []
    
    def on_attack_start(self, event: AttackEvent, current_step: int):
        """공격 시작 시 탐지 예약"""
        if np.random.random() < self.detection_prob:
            detect_step = current_step + self.detection_delay
            self.pending_detections.append((detect_step, event))
    
    def check_detections(self, current_step: int) -> List[Dict]:
        """탐지된 알림 확인"""
        alerts = []
        remaining = []
        
        for detect_step, event in self.pending_detections:
            if current_step >= detect_step:
                event.detected = True
                event.detection_time = time.time()
                
                alerts.append({
                    "type": event.attack_name,
                    "level": event.severity,
                    "timestamp": event.detection_time,
                })
            else:
                remaining.append((detect_step, event))
        
        self.pending_detections = remaining
        return alerts


# =============================================================================
# 평가 실행기
# =============================================================================

class EvaluationRunner:
    """MTD 평가 실행기"""
    
    def __init__(
        self,
        mtd_strategy: BaseMTDStrategy,
        scenario_name: str,
        seeker_level: int,
        max_steps: int = 300,
        real_execution: bool = False,
    ):
        self.strategy = mtd_strategy
        self.scenario_name = scenario_name
        self.seeker_level = seeker_level
        self.max_steps = max_steps
        
        # 컴포넌트
        self.attacker = AttackSimulator(scenario_name, seeker_level, real_execution)
        self.cti = CTISimulator(
            detection_delay=max(1, 5 - seeker_level),
            detection_prob=0.7 + seeker_level * 0.05,
        )
        
        # 메트릭
        self.metrics = EvaluationMetrics(
            scenario_name=scenario_name,
            mtd_mode=mtd_strategy.name,
            seeker_level=seeker_level,
        )
        
        # 상태
        self.step = 0
        self.running = False
    
    def _simulate_defense_outcome(self, event: AttackEvent) -> bool:
        """방어 결과 시뮬레이션"""
        diversity = self.strategy.controller.get_diversity_score()
        decoy_count = len(self.strategy.controller.decoys)
        
        # 스왑 보호 효과
        swap_protection = 0.0
        if hasattr(self.strategy.controller, 'get_swap_protection_factor'):
            for svc_name in self.strategy.controller.service_mappings:
                swap_protection = max(swap_protection, 
                    self.strategy.controller.get_swap_protection_factor(svc_name))
        
        # 기본 방어 확률 (MTD 여부에 따라 차별화)
        if self.strategy.name == "No MTD":
            base_prob = 0.15
        else:
            base_prob = 0.25
        
        # 다양성 보너스
        diversity_bonus = diversity * 0.3
        
        # 디코이 보너스
        decoy_bonus = min(decoy_count * 0.1, 0.2)
        
        # 스왑 보호 보너스
        swap_bonus = swap_protection * 0.2
        
        # Seeker 레벨 패널티
        seeker_penalty = self.seeker_level * 0.1
        
        defense_prob = base_prob + diversity_bonus + decoy_bonus + swap_bonus - seeker_penalty
        defense_prob = max(0.1, min(0.9, defense_prob))
        
        return np.random.random() < defense_prob
    
    def run_episode(self) -> EvaluationMetrics:
        """에피소드 실행"""
        self.running = True
        self.strategy.reset()
        self.attacker.reset()
        self.cti.reset()
        self.step = 0
        
        start_time = time.time()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting: {self.scenario_name} | {self.strategy.name} | Level {self.seeker_level}")
        logger.info(f"{'='*60}")
        
        try:
            while self.running and self.step < self.max_steps:
                self.step += 1
                
                # 1. 공격자 스텝
                attack_event = self.attacker.step_attack()
                if attack_event:
                    self.metrics.attacks_total += 1
                    self.cti.on_attack_start(attack_event, self.step)
                
                # 2. CTI 탐지 확인
                alerts = self.cti.check_detections(self.step)
                for alert in alerts:
                    self.metrics.attacks_detected += 1
                    self.strategy.on_cti_alert(alert)
                
                # 3. MTD 스텝
                state = {
                    "scan_rate": self.step * 0.1 if self.attacker.attack_in_progress else 0,
                    "suspicious_connections": 2 if self.attacker.attack_in_progress else 0,
                    "steps_since_shuffle": self.step - self.strategy.last_shuffle_step,
                    "decoy_hits": self.metrics.decoy_hits,
                    "energy": 1.0 - self.metrics.mtd_cost / 100,
                    "scanned_ratio": min(1.0, self.step / 200),
                    "services_discovered": len(self.attacker.events) / 10.0,
                    "critical_discovered": 0.0,
                    "exploit_progress": 0.0,
                    "compromise_progress": 0.0,
                }
                
                action_result = self.strategy.on_step(state)
                
                # 비용 및 MTD 액션 카운트
                if action_result.get("action") in ["shuffle", "rl_policy"]:
                    intensity = action_result.get("intensity", action_result.get("shuffle", 0))
                    self.metrics.mtd_cost += intensity * 0.3
                    if action_result.get("shuffle") or action_result.get("shuffle_count"):
                        self.metrics.shuffle_count += 1
                
                if action_result.get("port_hop"):
                    self.metrics.port_hop_count += 1
                    self.metrics.mtd_cost += action_result["port_hop"] * 0.2
                
                if action_result.get("decoys", 0) > 0:
                    self.metrics.decoy_activations += action_result["decoys"]
                    self.metrics.mtd_cost += action_result["decoys"] * 0.15
                
                if action_result.get("swap"):
                    self.metrics.swap_count += 1
                    self.metrics.mtd_cost += action_result.get("swap_cost", 0.4)
                
                # 4. 다양성/중복성 기록
                diversity = self.strategy.controller.get_diversity_score()
                self.metrics.diversity_history.append(diversity)
                self.metrics.diversity_min = min(self.metrics.diversity_min, diversity)
                self.metrics.diversity_max = max(self.metrics.diversity_max, diversity)
                
                if hasattr(self.strategy.controller, 'get_redundancy_score'):
                    redundancy = self.strategy.controller.get_redundancy_score()
                    self.metrics.redundancy_history.append(redundancy)
                
                # 5. 방어 결과 평가
                if self.attacker.events:
                    last_event = self.attacker.events[-1]
                    if last_event.detected and not last_event.blocked:
                        if self._simulate_defense_outcome(last_event):
                            last_event.blocked = True
                            last_event.response_time = time.time()
                            self.metrics.attacks_blocked += 1
                
                # 모든 공격 완료 체크
                if (self.attacker.current_attack_idx >= len(self.attacker.scenario["attacks"]) 
                    and not self.attacker.attack_in_progress):
                    logger.info("All attacks completed")
                    break
                
                # 실제 실행 시 딜레이
                if self.attacker.real_execution:
                    time.sleep(1.0)
        
        except KeyboardInterrupt:
            logger.info("Interrupted")
        
        finally:
            self.running = False
        
        # 메트릭 최종 계산
        self.metrics.total_duration = time.time() - start_time
        self.metrics.diversity_avg = np.mean(self.metrics.diversity_history) if self.metrics.diversity_history else 0.0
        self.metrics.redundancy_avg = np.mean(self.metrics.redundancy_history) if self.metrics.redundancy_history else 0.0
        
        # MTTD, MTTR 계산
        detection_times = [e.detection_time - e.timestamp 
                         for e in self.attacker.events if e.detection_time]
        response_times = [e.response_time - e.detection_time 
                         for e in self.attacker.events if e.response_time]
        
        self.metrics.mttd = np.mean(detection_times) if detection_times else float('inf')
        self.metrics.mttr = np.mean(response_times) if response_times else float('inf')
        
        # S_MTD 계산
        defense_rate = self.metrics.attacks_blocked / max(1, self.metrics.attacks_total)
        detect_rate = self.metrics.attacks_detected / max(1, self.metrics.attacks_total)
        
        self.metrics.s_mtd_score = (
            0.35 * defense_rate +
            0.20 * detect_rate +
            0.15 * self.metrics.diversity_avg +
            0.10 * self.metrics.redundancy_avg +
            0.10 * (1.0 - min(self.metrics.mtd_cost / 50, 1.0)) +
            0.10 * self.metrics.service_availability
        )
        
        # 이벤트 로그
        self.metrics.events = [asdict(e) for e in self.attacker.events]
        
        logger.info(f"\n--- Results ---")
        logger.info(f"S_MTD: {self.metrics.s_mtd_score:.3f}")
        logger.info(f"Defense Rate: {defense_rate:.2%}")
        logger.info(f"Detection Rate: {detect_rate:.2%}")
        logger.info(f"Diversity Avg: {self.metrics.diversity_avg:.3f}")
        logger.info(f"Redundancy Avg: {self.metrics.redundancy_avg:.3f}")
        logger.info(f"Shuffle Count: {self.metrics.shuffle_count}")
        logger.info(f"Swap Count: {self.metrics.swap_count}")
        logger.info(f"MTD Cost: {self.metrics.mtd_cost:.2f}")
        
        return self.metrics


# =============================================================================
# 전체 평가 실행
# =============================================================================

def run_full_evaluation(
    model_path: str,
    scenarios: List[str],
    seeker_levels: List[int],
    episodes_per_config: int = 3,
    output_dir: str = "eval_results",
    dry_run: bool = True,
    use_wandb: bool = False,
    wandb_project: str = "mtd-eval-v08",
    wandb_name: Optional[str] = None,
):
    """전체 평가 실행"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # WandB 초기화
    if use_wandb and HAS_WANDB:
        run_name = wandb_name or f"eval-{datetime.now():%m%d-%H%M}"
        wandb.init(
            project=wandb_project,
            name=run_name,
            config={
                "model_path": model_path,
                "scenarios": scenarios,
                "seeker_levels": seeker_levels,
                "episodes_per_config": episodes_per_config,
            }
        )
    
    # MTD 컨트롤러
    controller = IptablesMTDController(dry_run=dry_run)
    
    # 전략 목록
    strategies = [
        ("No MTD", NoMTDStrategy(controller)),
        ("Static MTD", StaticMTDStrategy(controller, shuffle_period=30)),
        ("Heuristic+CTI", HeuristicCTIMTDStrategy(controller)),
    ]
    
    if HAS_TORCH and os.path.exists(model_path):
        strategies.append(("RL+CTI", RLCTIMTDStrategy(controller, model_path)))
    else:
        logger.warning(f"RL model not available: {model_path}")
    
    all_results = []
    
    # 실험 실행
    total_experiments = len(scenarios) * len(seeker_levels) * len(strategies) * episodes_per_config
    current_exp = 0
    
    for scenario_name in scenarios:
        for seeker_level in seeker_levels:
            for strategy_name, strategy in strategies:
                
                logger.info(f"\n{'#'*60}")
                logger.info(f"# {scenario_name} | {strategy_name} | Level {seeker_level}")
                logger.info(f"{'#'*60}")
                
                for ep in range(episodes_per_config):
                    current_exp += 1
                    
                    # 컨트롤러 리셋
                    controller.cleanup()
                    controller._initialize_services()
                    
                    runner = EvaluationRunner(
                        mtd_strategy=strategy,
                        scenario_name=scenario_name,
                        seeker_level=seeker_level,
                        max_steps=300,
                    )
                    
                    metrics = runner.run_episode()
                    metrics_dict = metrics.to_dict()
                    metrics_dict["episode"] = ep
                    all_results.append(metrics_dict)
                    
                    # WandB 로깅
                    if use_wandb and HAS_WANDB:
                        wandb.log({
                            "experiment": current_exp,
                            "scenario": scenario_name,
                            "mtd_mode": strategy_name,
                            "seeker_level": seeker_level,
                            "episode": ep,
                            "s_mtd": metrics.s_mtd_score,
                            "defense_rate": metrics_dict["defense_rate"],
                            "detection_rate": metrics_dict["detection_rate"],
                            "diversity_avg": metrics.diversity_avg,
                            "redundancy_avg": metrics.redundancy_avg,
                            "shuffle_count": metrics.shuffle_count,
                            "swap_count": metrics.swap_count,
                            "mtd_cost": metrics.mtd_cost,
                        })
                    
                    print(f"[{current_exp}/{total_experiments}] {scenario_name} | {strategy_name} | L{seeker_level} | Ep{ep} | S_MTD: {metrics.s_mtd_score:.3f}")
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON
    results_file = output_path / f"eval_results_{timestamp}.json"
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    logger.info(f"\nResults saved: {results_file}")
    
    # 시각화
    plot_results(all_results, output_path, timestamp)
    
    # WandB 종료
    if use_wandb and HAS_WANDB:
        wandb.finish()
    
    return all_results


def plot_results(results: List[Dict], output_dir: Path, timestamp: str):
    """결과 시각화"""
    
    try:
        import pandas as pd
        df = pd.DataFrame(results)
    except ImportError:
        logger.warning("pandas not available, skipping plots")
        return
    
    # 1. MTD 모드별 비교
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    
    # S_MTD by Mode
    ax = axes[0, 0]
    mode_smtd = df.groupby('mtd_mode')['s_mtd_score'].mean().sort_values(ascending=False)
    colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c'][:len(mode_smtd)]
    mode_smtd.plot(kind='bar', ax=ax, color=colors)
    ax.set_title('S_MTD Score by MTD Mode', fontsize=12)
    ax.set_ylabel('S_MTD Score')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    
    # Defense Rate by Mode and Level
    ax = axes[0, 1]
    pivot = df.pivot_table(values='defense_rate', index='mtd_mode', columns='seeker_level', aggfunc='mean')
    pivot.plot(kind='bar', ax=ax)
    ax.set_title('Defense Rate by Mode and Seeker Level', fontsize=12)
    ax.set_ylabel('Defense Rate')
    ax.legend(title='Seeker Level')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    
    # Diversity by Mode
    ax = axes[0, 2]
    mode_div = df.groupby('mtd_mode')['diversity_avg'].mean().sort_values(ascending=False)
    mode_div.plot(kind='bar', ax=ax, color='#27ae60')
    ax.set_title('Average Diversity by MTD Mode', fontsize=12)
    ax.set_ylabel('Diversity')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    
    # Cost vs Effectiveness
    ax = axes[1, 0]
    for mode in df['mtd_mode'].unique():
        mode_data = df[df['mtd_mode'] == mode]
        ax.scatter(mode_data['mtd_cost'], mode_data['s_mtd_score'], label=mode, alpha=0.7, s=50)
    ax.set_xlabel('MTD Cost')
    ax.set_ylabel('S_MTD Score')
    ax.set_title('Cost-Effectiveness Analysis', fontsize=12)
    ax.legend()
    
    # Shuffle/Swap Counts
    ax = axes[1, 1]
    mtd_actions = df.groupby('mtd_mode')[['shuffle_count', 'swap_count']].mean()
    mtd_actions.plot(kind='bar', ax=ax)
    ax.set_title('MTD Actions (Shuffle vs Swap)', fontsize=12)
    ax.set_ylabel('Count')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    
    # Scenario Performance
    ax = axes[1, 2]
    scenario_perf = df.pivot_table(values='s_mtd_score', index='scenario_name', columns='mtd_mode', aggfunc='mean')
    scenario_perf.plot(kind='bar', ax=ax)
    ax.set_title('Performance by Scenario', fontsize=12)
    ax.set_ylabel('S_MTD Score')
    ax.legend(title='MTD Mode', bbox_to_anchor=(1.05, 1))
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_dir / f"eval_comparison_{timestamp}.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Plot saved: {output_dir / f'eval_comparison_{timestamp}.png'}")
    
    # 2. 상세 테이블 출력
    summary = df.groupby(['mtd_mode', 'seeker_level']).agg({
        's_mtd_score': ['mean', 'std'],
        'defense_rate': 'mean',
        'detection_rate': 'mean',
        'diversity_avg': 'mean',
        'redundancy_avg': 'mean',
        'shuffle_count': 'mean',
        'swap_count': 'mean',
        'mtd_cost': 'mean',
    }).round(3)
    
    print("\n" + "="*100)
    print("EVALUATION SUMMARY (Diversity/Redundancy/Shuffle)")
    print("="*100)
    print(summary.to_string())
    print("="*100)
    
    # Summary CSV 저장
    summary.to_csv(output_dir / f"summary_{timestamp}.csv")


# =============================================================================
# 메인
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="MTD Scenario-based Evaluation v08")
    
    parser.add_argument("--model", "-m", default="checkpoints_v08/best.pt",
                       help="RL 모델 경로")
    parser.add_argument("--scenarios", "-s", nargs="+", 
                       default=["reconnaissance", "gps_spoofing", "dos_attack"],
                       choices=list(ATTACK_SCENARIOS.keys()),
                       help="평가 시나리오")
    parser.add_argument("--levels", "-l", nargs="+", type=int, default=[1, 2, 3],
                       help="Seeker 레벨")
    parser.add_argument("--episodes", "-e", type=int, default=3,
                       help="설정당 에피소드 수")
    parser.add_argument("--output", "-o", default="eval_results",
                       help="결과 저장 디렉토리")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="실제 iptables 변경 없이 테스트")
    parser.add_argument("--real", action="store_true",
                       help="실제 공격 실행 (주의!)")
    
    # WandB 인자
    parser.add_argument("--wandb", action="store_true",
                       help="WandB 로깅 활성화")
    parser.add_argument("--wandb-project", type=str, default="mtd-eval-v08",
                       help="WandB 프로젝트 이름")
    parser.add_argument("--wandb-name", type=str, default=None,
                       help="WandB run 이름")
    
    args = parser.parse_args()
    
    # dry_run 반전 (--real 옵션)
    dry_run = not args.real
    
    print("\n" + "="*60)
    print("MTD Scenario-based Evaluation v08.1")
    print("="*60)
    print(f"Model: {args.model}")
    print(f"Scenarios: {args.scenarios}")
    print(f"Seeker Levels: {args.levels}")
    print(f"Episodes per config: {args.episodes}")
    print(f"Dry Run: {dry_run}")
    print(f"WandB: {args.wandb}")
    print(f"STATE_DIM: {STATE_DIM}, ACTION_DIM: {ACTION_DIM}")
    print("="*60 + "\n")
    
    results = run_full_evaluation(
        model_path=args.model,
        scenarios=args.scenarios,
        seeker_levels=args.levels,
        episodes_per_config=args.episodes,
        output_dir=args.output,
        dry_run=dry_run,
        use_wandb=args.wandb,
        wandb_project=args.wandb_project,
        wandb_name=args.wandb_name,
    )
    
    print(f"\nTotal experiments: {len(results)}")


if __name__ == "__main__":
    main()