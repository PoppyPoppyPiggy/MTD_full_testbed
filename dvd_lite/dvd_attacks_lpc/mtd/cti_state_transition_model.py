#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI-Driven RL-MTD State Transition Model Implementation
======================================================

상태 전이 모델:
S0 (Initial) → S1 (Recon) → S2 (Discovery) → S3 (Exploit) → S4 (Breach)
                ↓              ↓              ↓
               S5 (Defended) ←────────────────

공격자 프로파일 (L0-L4):
- L0: pdisc=0.15, pexploit=0.08 (Script Kiddie)
- L1: pdisc=0.25, pexploit=0.12 (Hobbyist)
- L2: pdisc=0.35, pexploit=0.20 (Professional)
- L3: pdisc=0.50, pexploit=0.30 (Expert)  
- L4: pdisc=0.65, pexploit=0.40 (APT)

MTD 방어 메커니즘:
- Network Shuffle: 스캔 중 IP/Port 변경 → S5 Defended
- Decoy: 가짜 서비스 탐지 → S5 Defended
- Service Swap: 실제 서비스 위치 변경 → confusion
- MTD 타이밍: 100ms 이내 실시간 대응

핵심 로직:
1. 공격자 스캔 시도 (pdisc 확률)
2. MTD 실시간 대응 (100ms 내)
3. Decoy 탐지 또는 Shuffle 효과 → S5 Defended
4. S5에서 다시 S1으로 복귀 (공격 재시작)
"""

import time
import random
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("StateTransitionModel")

# =============================================================================
# 상태 전이 모델 정의
# =============================================================================

class AttackState(Enum):
    """공격 상태"""
    S0_INITIAL = "S0_Initial"
    S1_RECON = "S1_Recon"  
    S2_DISCOVERY = "S2_Discovery"
    S3_EXPLOIT = "S3_Exploit"
    S4_BREACH = "S4_Breach"
    S5_DEFENDED = "S5_Defended"

# L0-L4 공격자 프로파일 (상태 전이 모델 정확 수치)
ATTACKER_PROFILES = {
    0: {  # L0: Script Kiddie
        "name": "Script Kiddie",
        "p_disc": 0.15,    # Discovery 확률
        "p_exploit": 0.08, # Exploit 확률
        "scan_speed": 1.0, # 스캔 속도 (초당 횟수)
        "detection_threshold": 0.3,  # 실제 서비스 판단 임계값
        "confusion_susceptibility": 0.9,  # MTD 혼란 취약성
    },
    1: {  # L1: Hobbyist
        "name": "Hobbyist", 
        "p_disc": 0.25,
        "p_exploit": 0.12,
        "scan_speed": 1.5,
        "detection_threshold": 0.25,
        "confusion_susceptibility": 0.7,
    },
    2: {  # L2: Professional
        "name": "Professional",
        "p_disc": 0.35,
        "p_exploit": 0.20,
        "scan_speed": 2.0,
        "detection_threshold": 0.20,
        "confusion_susceptibility": 0.5,
    },
    3: {  # L3: Expert
        "name": "Expert",
        "p_disc": 0.50,
        "p_exploit": 0.30,
        "scan_speed": 2.5,
        "detection_threshold": 0.15,
        "confusion_susceptibility": 0.3,
    },
    4: {  # L4: APT
        "name": "APT",
        "p_disc": 0.65,
        "p_exploit": 0.40,
        "scan_speed": 3.0,
        "detection_threshold": 0.10,
        "confusion_susceptibility": 0.15,
    },
}

# MTD 액션 타입
MTD_ACTIONS = {
    "shuffle": {"code": "a_shuffle", "response_time_ms": 50},
    "port_hop": {"code": "a_port", "response_time_ms": 30},
    "decoy": {"code": "a_decoy", "response_time_ms": 20},
    "swap": {"code": "a_swap", "response_time_ms": 80},
}

@dataclass
class AttackStep:
    """단일 공격 단계"""
    step_id: int
    timestamp: float
    current_state: AttackState
    attacker_level: int
    scan_target: str  # IP:Port
    scan_duration: float  # 스캔 시간 (초)
    mtd_response_time: Optional[float] = None  # MTD 대응 시간 (ms)
    mtd_action: Optional[str] = None
    detection_confidence: float = 0.0  # 실제 서비스 판단 신뢰도
    is_decoy: bool = False
    is_defended: bool = False
    transition_probability: float = 0.0


@dataclass  
class AttackSession:
    """공격 세션 (전체 공격 과정)"""
    session_id: str
    attacker_level: int
    start_time: float
    current_state: AttackState = AttackState.S0_INITIAL
    steps: List[AttackStep] = field(default_factory=list)
    total_scan_attempts: int = 0
    successful_discoveries: int = 0
    mtd_defenses_triggered: int = 0
    decoy_hits: int = 0
    breach_achieved: bool = False
    session_duration: float = 0.0


# =============================================================================
# 상태 전이 엔진 
# =============================================================================

class CTIStateTransitionEngine:
    """CTI 기반 상태 전이 엔진"""
    
    def __init__(self, mtd_controller=None):
        self.mtd_controller = mtd_controller
        self.active_sessions: Dict[str, AttackSession] = {}
        self.global_step = 0
        
        # MTD 실시간 대응 임계값 (100ms 이내)
        self.mtd_response_threshold_ms = 100
        
    def start_attack_session(self, attacker_level: int) -> str:
        """공격 세션 시작"""
        session_id = f"session_{self.global_step}_{int(time.time())}"
        
        session = AttackSession(
            session_id=session_id,
            attacker_level=attacker_level,
            start_time=time.time(),
            current_state=AttackState.S0_INITIAL
        )
        
        self.active_sessions[session_id] = session
        logger.info(f"🎯 Attack session started: {session_id} (L{attacker_level})")
        
        return session_id
    
    def step_attack_transition(self, session_id: str, mtd_state: Dict) -> Dict[str, Any]:
        """단일 스텝 상태 전이 실행"""
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session = self.active_sessions[session_id]
        profile = ATTACKER_PROFILES[session.attacker_level]
        
        # 현재 스텝 생성
        step = AttackStep(
            step_id=len(session.steps),
            timestamp=time.time(),
            current_state=session.current_state,
            attacker_level=session.attacker_level,
            scan_target=self._generate_scan_target(),
            scan_duration=1.0 / profile["scan_speed"]
        )
        
        # 상태별 전이 로직 실행
        transition_result = self._execute_state_transition(session, step, mtd_state)
        
        session.steps.append(step)
        session.current_state = transition_result["next_state"]
        self.global_step += 1
        
        return transition_result
    
    def _execute_state_transition(self, session: AttackSession, step: AttackStep, mtd_state: Dict) -> Dict[str, Any]:
        """상태 전이 실행 로직"""
        profile = ATTACKER_PROFILES[session.attacker_level]
        
        if step.current_state == AttackState.S0_INITIAL:
            return self._transition_s0_to_s1(session, step)
            
        elif step.current_state == AttackState.S1_RECON:
            return self._transition_s1_to_s2_or_s5(session, step, mtd_state, profile)
            
        elif step.current_state == AttackState.S2_DISCOVERY:
            return self._transition_s2_to_s3_or_s5(session, step, mtd_state, profile)
            
        elif step.current_state == AttackState.S3_EXPLOIT:
            return self._transition_s3_to_s4_or_s5(session, step, mtd_state, profile)
            
        elif step.current_state == AttackState.S5_DEFENDED:
            return self._transition_s5_to_s1(session, step)
            
        else:  # S4_BREACH
            return {"next_state": AttackState.S4_BREACH, "breach": True}
    
    def _transition_s0_to_s1(self, session: AttackSession, step: AttackStep) -> Dict[str, Any]:
        """S0 → S1: 초기화 → 정찰"""
        return {
            "next_state": AttackState.S1_RECON,
            "action": "start_reconnaissance", 
            "probability": 1.0
        }
    
    def _transition_s1_to_s2_or_s5(self, session: AttackSession, step: AttackStep, 
                                   mtd_state: Dict, profile: Dict) -> Dict[str, Any]:
        """S1 → S2 or S5: 정찰 → 발견 또는 방어됨"""
        
        # 1. 공격자 스캔 시도
        scan_success_prob = profile["p_disc"]
        scan_success = random.random() < scan_success_prob
        
        if not scan_success:
            # 스캔 실패 → 계속 S1
            return {"next_state": AttackState.S1_RECON, "action": "scan_failed"}
        
        # 2. MTD 실시간 대응 체크 (100ms 이내)
        mtd_response = self._check_mtd_response(mtd_state, "shuffle")
        
        if mtd_response["triggered"]:
            step.mtd_response_time = mtd_response["response_time_ms"]
            step.mtd_action = mtd_response["action"]
            step.is_defended = True
            
            # MTD 혼란 효과 적용
            confusion_factor = profile["confusion_susceptibility"] * mtd_response["intensity"]
            
            if confusion_factor > 0.5:  # 혼란 임계값
                session.mtd_defenses_triggered += 1
                return {
                    "next_state": AttackState.S5_DEFENDED,
                    "action": "mtd_confusion",
                    "mtd_response": mtd_response,
                    "confusion_factor": confusion_factor
                }
        
        # 3. 스캔 성공 → S2 Discovery
        session.total_scan_attempts += 1
        return {
            "next_state": AttackState.S2_DISCOVERY,
            "action": "discovery_attempt",
            "scan_success": True
        }
    
    def _transition_s2_to_s3_or_s5(self, session: AttackSession, step: AttackStep,
                                   mtd_state: Dict, profile: Dict) -> Dict[str, Any]:
        """S2 → S3 or S5: 발견 → 공격 또는 방어됨"""
        
        # 1. 실제 서비스 판단 과정
        detection_confidence = self._calculate_service_confidence(step, profile)
        step.detection_confidence = detection_confidence
        
        # 2. Decoy 체크
        decoy_hit = self._check_decoy_hit(step, mtd_state)
        
        if decoy_hit:
            step.is_decoy = True
            step.is_defended = True
            session.decoy_hits += 1
            
            return {
                "next_state": AttackState.S5_DEFENDED,
                "action": "decoy_detected",
                "decoy_hit": True
            }
        
        # 3. MTD Shuffle/Swap 중간 대응
        mtd_response = self._check_mtd_response(mtd_state, "swap")
        
        if mtd_response["triggered"]:
            step.mtd_response_time = mtd_response["response_time_ms"]
            step.mtd_action = mtd_response["action"]
            
            # Service Swap 혼란 효과
            swap_confusion = profile["confusion_susceptibility"] * mtd_response["intensity"] * 0.6
            
            if swap_confusion > 0.3:
                return {
                    "next_state": AttackState.S5_DEFENDED,
                    "action": "service_swap_confusion",
                    "mtd_response": mtd_response
                }
        
        # 4. 발견 성공 → S3 Exploit  
        if detection_confidence >= profile["detection_threshold"]:
            session.successful_discoveries += 1
            return {
                "next_state": AttackState.S3_EXPLOIT,
                "action": "exploit_attempt",
                "confidence": detection_confidence
            }
        else:
            # 신뢰도 부족 → 계속 S2
            return {
                "next_state": AttackState.S2_DISCOVERY,
                "action": "low_confidence",
                "confidence": detection_confidence
            }
    
    def _transition_s3_to_s4_or_s5(self, session: AttackSession, step: AttackStep,
                                   mtd_state: Dict, profile: Dict) -> Dict[str, Any]:
        """S3 → S4 or S5: 공격 → 침해 또는 방어됨"""
        
        # 1. Exploit 시도
        exploit_success_prob = profile["p_exploit"]
        exploit_success = random.random() < exploit_success_prob
        
        # 2. 최후 MTD 방어 (모든 액션)
        final_mtd_response = self._check_mtd_response(mtd_state, "all")
        
        if final_mtd_response["triggered"]:
            step.mtd_response_time = final_mtd_response["response_time_ms"]
            step.mtd_action = final_mtd_response["action"]
            
            # 최후 방어 성공률
            defense_success_prob = 0.6 * final_mtd_response["intensity"]
            
            if random.random() < defense_success_prob:
                return {
                    "next_state": AttackState.S5_DEFENDED,
                    "action": "final_defense",
                    "mtd_response": final_mtd_response
                }
        
        # 3. Exploit 성공 → S4 Breach
        if exploit_success:
            session.breach_achieved = True
            return {
                "next_state": AttackState.S4_BREACH,
                "action": "breach_success",
                "reward": -800  # 논문에서 breach reward
            }
        else:
            # Exploit 실패 → S5 Defended (실패도 일종의 방어)
            return {
                "next_state": AttackState.S5_DEFENDED,
                "action": "exploit_failed"
            }
    
    def _transition_s5_to_s1(self, session: AttackSession, step: AttackStep) -> Dict[str, Any]:
        """S5 → S1: 방어됨 → 정찰 (공격 재시작)"""
        return {
            "next_state": AttackState.S1_RECON,
            "action": "attack_restart",
            "reward": 500  # 논문에서 defend reward
        }
    
    def _check_mtd_response(self, mtd_state: Dict, action_type: str) -> Dict[str, Any]:
        """MTD 실시간 대응 체크 (100ms 이내)"""
        
        # MTD 컨트롤러 상태 기반 대응 판단
        mtd_active = mtd_state.get("mtd_active", False)
        diversity_score = mtd_state.get("diversity_score", 0.0)
        confusion_level = mtd_state.get("confusion_level", 0.0)
        
        # 대응 가능성 계산
        base_response_prob = diversity_score * 0.6 + confusion_level * 0.4
        
        if not mtd_active or base_response_prob < 0.1:
            return {"triggered": False, "response_time_ms": 0}
        
        # 액션별 대응 시간
        if action_type in MTD_ACTIONS:
            response_time = MTD_ACTIONS[action_type]["response_time_ms"]
        else:  # "all"
            response_time = 60  # 평균 대응 시간
        
        # 100ms 임계값 체크
        if response_time <= self.mtd_response_threshold_ms:
            return {
                "triggered": True,
                "action": action_type,
                "response_time_ms": response_time,
                "intensity": min(1.0, base_response_prob + random.uniform(0, 0.3))
            }
        
        return {"triggered": False, "response_time_ms": response_time}
    
    def _calculate_service_confidence(self, step: AttackStep, profile: Dict) -> float:
        """실제 서비스 판단 신뢰도 계산"""
        # 기본 탐지 능력
        base_confidence = profile["p_disc"]
        
        # 스캔 시간에 따른 보정 (더 오래 스캔할수록 신뢰도 증가)
        time_factor = min(1.0, step.scan_duration / 2.0)  # 2초 기준
        
        # 공격자 레벨에 따른 보정
        level_factor = 0.5 + (step.attacker_level * 0.125)  # L0:0.5 → L4:1.0
        
        # 최종 신뢰도
        confidence = base_confidence * time_factor * level_factor
        
        # 노이즈 추가
        noise = random.uniform(-0.1, 0.1)
        
        return max(0.0, min(1.0, confidence + noise))
    
    def _check_decoy_hit(self, step: AttackStep, mtd_state: Dict) -> bool:
        """Decoy 히트 체크"""
        decoy_count = mtd_state.get("decoy_count", 0)
        
        if decoy_count == 0:
            return False
        
        # Decoy 히트 확률 (디코이 수에 비례)
        decoy_hit_prob = min(0.4, decoy_count * 0.1)
        
        return random.random() < decoy_hit_prob
    
    def _generate_scan_target(self) -> str:
        """스캔 대상 IP:Port 생성"""
        ip_suffix = random.randint(2, 201)  # 200 IP 범위
        port = random.randint(1, 251)       # 251 Port 범위
        
        return f"10.13.0.{ip_suffix}:{port}"
    
    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """세션 메트릭 조회"""
        if session_id not in self.active_sessions:
            return {}
        
        session = self.active_sessions[session_id]
        session.session_duration = time.time() - session.start_time
        
        return {
            "session_id": session_id,
            "attacker_level": session.attacker_level,
            "current_state": session.current_state.value,
            "total_steps": len(session.steps),
            "total_scan_attempts": session.total_scan_attempts,
            "successful_discoveries": session.successful_discoveries,
            "mtd_defenses_triggered": session.mtd_defenses_triggered,
            "decoy_hits": session.decoy_hits,
            "breach_achieved": session.breach_achieved,
            "session_duration": session.session_duration,
            "discovery_rate": session.successful_discoveries / max(1, session.total_scan_attempts),
            "defense_effectiveness": session.mtd_defenses_triggered / max(1, len(session.steps)),
        }


# =============================================================================
# MTD 환경 연동 래퍼
# =============================================================================

class MTDStateTransitionWrapper:
    """MTD 환경과 상태 전이 모델 연동"""
    
    def __init__(self, mtd_controller=None):
        self.engine = CTIStateTransitionEngine(mtd_controller)
        self.current_session = None
        
    def reset(self, attacker_level: int = 2):
        """환경 리셋 + 새 공격 세션"""
        self.current_session = self.engine.start_attack_session(attacker_level)
        return self.current_session
    
    def step(self, mtd_state: Dict) -> Dict[str, Any]:
        """환경 스텝 + 상태 전이"""
        if not self.current_session:
            self.current_session = self.engine.start_attack_session(2)  # 기본 L2
        
        result = self.engine.step_attack_transition(self.current_session, mtd_state)
        
        # 환경 반환값 형식으로 변환
        return {
            "state_transition": result,
            "metrics": self.engine.get_session_metrics(self.current_session),
            "done": result.get("next_state") == AttackState.S4_BREACH,
            "defended": result.get("next_state") == AttackState.S5_DEFENDED,
            "reward": result.get("reward", 0)
        }


# =============================================================================
# 테스트 실행
# =============================================================================
if __name__ == "__main__":
    # 상태 전이 모델 테스트
    print("🎯 CTI State Transition Model Test")
    
    # 가상 MTD 상태
    test_mtd_state = {
        "mtd_active": True,
        "diversity_score": 0.7,
        "confusion_level": 0.5,
        "decoy_count": 2,
        "active_swap_count": 1,
    }
    
    # L2 Professional 공격자 테스트
    wrapper = MTDStateTransitionWrapper()
    session_id = wrapper.reset(attacker_level=2)
    
    print(f"\n📊 Testing L2 Professional Attack Session")
    
    for step in range(20):  # 20스텝 시뮬레이션
        result = wrapper.step(test_mtd_state)
        
        state_transition = result["state_transition"]
        metrics = result["metrics"]
        
        print(f"Step {step+1}: {state_transition.get('action', 'none')} → {state_transition['next_state']}")
        
        if result["done"]:
            print("🚨 BREACH ACHIEVED!")
            break
        elif result["defended"]:
            print("🛡️ DEFENDED - Restarting attack...")
    
    print(f"\n📈 Final Metrics:")
    final_metrics = wrapper.engine.get_session_metrics(session_id)
    for key, value in final_metrics.items():
        print(f"  {key}: {value}")