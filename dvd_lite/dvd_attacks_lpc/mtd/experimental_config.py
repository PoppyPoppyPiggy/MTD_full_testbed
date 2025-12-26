#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment Config v2.0 (Paper-Ready)
=====================================
논문 실험을 위한 설정 파일

CTI 노이즈/지연 실험, 전술 레벨 분류 등 지원
"""

import os
from typing import Dict, Any, List

# --- 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CHECKPOINTS_DIR = os.path.join(BASE_DIR, "checkpoints")


# =============================================================================
# 전술(Tactic) 정의 - MITRE ATT&CK 정렬
# =============================================================================

TACTIC_DEFINITIONS = {
    0: {
        "name": "Normal",
        "description": "정상 상태",
        "severity": 0,
        "mtd_response": None
    },
    1: {
        "name": "Reconnaissance",
        "description": "정찰 - 네트워크/시스템 정보 수집",
        "severity": 1,
        "mtd_response": "port_shuffle",
        "attacks": [
            "wifi-analysis-cracking",
            "drone-discovery", 
            "companion-computer-discovery",
            "ground-control-station-discovery",
            "drone-gps-telemetry-detection",
            "protocol-fingerprinting",
            "packet-sniffing"
        ]
    },
    2: {
        "name": "Credential Access",
        "description": "인증 접근 - 로그인 정보 탈취",
        "severity": 2,
        "mtd_response": "service_swap",
        "attacks": [
            "companion-computer-web-ui-login-brute-force",
            "companion-computer-takeover"
        ]
    },
    3: {
        "name": "Tampering",
        "description": "변조 - 센서/상태 데이터 조작",
        "severity": 2,
        "mtd_response": "ip_shuffle",
        "attacks": [
            "attitude-spoofing",
            "battery-spoofing",
            "gps-spoofing",
            "critical-error-spoofing",
            "emergency-status-spoofing",
            "vfr-hud-spoofing",
            "system-status-spoofing"
        ]
    },
    4: {
        "name": "DoS/Disruption",
        "description": "서비스 거부 - 통신/기능 방해",
        "severity": 3,
        "mtd_response": "full_shuffle",
        "attacks": [
            "wifi-deauth-attack",
            "geofencing-attack",
            "gps-offset-glitching",
            "flight-termination",
            "denial-of-takeoff",
            "communication-link-flooding",
            "camera-feed-ros-topic-flooding"
        ]
    },
    5: {
        "name": "Command Injection",
        "description": "명령 주입 - 비인가 제어 명령 삽입",
        "severity": 4,
        "mtd_response": "full_shuffle",
        "attacks": [
            "ground-control-station-spoofing",
            "camera-gimbal-takeover",
            "gps-data-injection",
            "return-to-home-point-override",
            "waypoint-injection",
            "satellite-spoofing",
            "mavlink-injection-attack",
            "flight-mode-injection"
        ]
    },
    6: {
        "name": "Exfiltration",
        "description": "데이터 유출 - 민감 정보 추출",
        "severity": 3,
        "mtd_response": "decoy_activate",
        "attacks": [
            "wifi-client-data-leak",
            "flight-log-extraction",
            "mission-extraction",
            "parameter-extraction",
            "ftp-eavesdropping",
            "camera-feed-eavesdropping"
        ]
    },
    7: {
        "name": "Persistence",
        "description": "지속성 - 시스템 영구 접근",
        "severity": 4,
        "mtd_response": "full_shuffle",
        "attacks": [
            "firmware-decompile",
            "firmware-modding"
        ]
    }
}


# =============================================================================
# CTI 실험 시나리오 (논문용)
# =============================================================================

CTI_EXPERIMENT_SCENARIOS = {
    # 이상적 조건 (기준선)
    "ideal": {
        "name": "Ideal CTI",
        "description": "완벽한 CTI - 노이즈/지연 없음",
        "cti_noise": 0.0,
        "cti_delay": 0,
        "attacker_boost": 1.0,
    },
    
    # 현실적 조건 (논문 메인 결과)
    "realistic": {
        "name": "Realistic CTI",
        "description": "현실적 CTI - 15% 노이즈, 2스텝 지연",
        "cti_noise": 0.15,
        "cti_delay": 2,
        "attacker_boost": 1.0,
    },
    
    # 저품질 CTI
    "degraded": {
        "name": "Degraded CTI",
        "description": "저품질 CTI - 25% 노이즈, 3스텝 지연",
        "cti_noise": 0.25,
        "cti_delay": 3,
        "attacker_boost": 1.0,
    },
    
    # 적대적 환경
    "adversarial": {
        "name": "Adversarial",
        "description": "적대적 환경 - 노이즈 + 강화된 공격자",
        "cti_noise": 0.20,
        "cti_delay": 2,
        "attacker_boost": 1.3,  # 공격자 30% 강화
    },
    
    # CTI 없음 (Ablation)
    "no_cti": {
        "name": "No CTI",
        "description": "CTI 비활성화 (RL만)",
        "cti_noise": 1.0,  # 100% 노이즈 = 랜덤
        "cti_delay": 0,
        "attacker_boost": 1.0,
    },
}


# =============================================================================
# 공격자 프로파일 (Multi-Level Threat Actor Model)
# =============================================================================

ATTACKER_PROFILES = {
    0: {
        "name": "Script Kiddie",
        "scan_rate": 0.03,
        "p_disc": 0.15,
        "p_exploit": 0.08,
        "kappa": 1.00,
        "description": "자동화 도구 사용, 기본 스킬"
    },
    1: {
        "name": "Hobbyist",
        "scan_rate": 0.05,
        "p_disc": 0.25,
        "p_exploit": 0.12,
        "kappa": 0.92,
        "description": "기본 해킹 지식, 수동 탐색"
    },
    2: {
        "name": "Professional",
        "scan_rate": 0.08,
        "p_disc": 0.35,
        "p_exploit": 0.20,
        "kappa": 0.84,
        "description": "전문 해커, 맞춤형 도구"
    },
    3: {
        "name": "Expert",
        "scan_rate": 0.12,
        "p_disc": 0.50,
        "p_exploit": 0.30,
        "kappa": 0.76,
        "description": "보안 전문가, 제로데이 활용"
    },
    4: {
        "name": "APT",
        "scan_rate": 0.15,
        "p_disc": 0.65,
        "p_exploit": 0.40,
        "kappa": 0.68,
        "description": "국가 수준, 무제한 리소스"
    },
}

# 강화된 공격자 프로파일 (변별력 확보용)
ATTACKER_PROFILES_ENHANCED = {
    0: {"name": "Script Kiddie", "scan_rate": 0.03, "p_disc": 0.15, "p_exploit": 0.08, "kappa": 1.00},
    1: {"name": "Hobbyist",      "scan_rate": 0.05, "p_disc": 0.25, "p_exploit": 0.12, "kappa": 0.92},
    2: {"name": "Professional",  "scan_rate": 0.08, "p_disc": 0.35, "p_exploit": 0.20, "kappa": 0.84},
    3: {"name": "Expert",        "scan_rate": 0.15, "p_disc": 0.60, "p_exploit": 0.40, "kappa": 0.72},  # 강화
    4: {"name": "APT",           "scan_rate": 0.20, "p_disc": 0.75, "p_exploit": 0.55, "kappa": 0.60},  # 강화
}


# =============================================================================
# MTD 액션 효과 계수
# =============================================================================

MTD_ACTION_COEFFICIENTS = {
    "service_swap": {
        "alpha": 0.45,
        "description": "서비스 스왑 - 가장 효과적, 공격자 지식 무효화",
        "citation": "Hong & Kim 2016"
    },
    "network_shuffle": {
        "alpha": 0.35,
        "description": "네트워크 셔플 - IP/토폴로지 변경",
        "citation": "Jafarian et al. 2015"
    },
    "port_hop": {
        "alpha": 0.20,
        "description": "포트 호핑 - 포트 번호 변경",
        "citation": "Luo et al. 2015"
    },
    "decoy_activate": {
        "alpha": 0.15,
        "description": "디코이 활성화 - 허니팟/페이크 서비스",
        "citation": "Albanese et al. 2013"
    },
}


# =============================================================================
# 평가 메트릭 정의
# =============================================================================

EVALUATION_METRICS = {
    "s_mtd": {
        "name": "Defense Effectiveness Score",
        "description": "종합 방어 효과 점수 (0-1)",
        "formula": "S_MTD = w_asr*ASR + w_cdi*CDI + w_ned*NED + w_des*DES",
        "higher_is_better": True
    },
    "breach_rate": {
        "name": "Breach Rate",
        "description": "침투 성공률 (%)",
        "higher_is_better": False
    },
    "mttc": {
        "name": "Mean Time to Compromise",
        "description": "평균 침투 소요 시간 (steps)",
        "higher_is_better": True
    },
    "cer": {
        "name": "Cost Efficiency Ratio",
        "description": "비용 효율 비율 (S_MTD / Cost)",
        "higher_is_better": True
    },
    "cdi": {
        "name": "Configuration Diversity Index",
        "description": "설정 다양성 지수 (0-1)",
        "higher_is_better": True
    },
    "asr": {
        "name": "Attack Surface Reduction",
        "description": "공격 표면 감소율 (0-1)",
        "higher_is_better": True
    },
}


# =============================================================================
# 실험 실행 함수
# =============================================================================

def get_experiment_config(scenario_name: str) -> Dict[str, Any]:
    """실험 시나리오 설정 반환"""
    if scenario_name not in CTI_EXPERIMENT_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    return CTI_EXPERIMENT_SCENARIOS[scenario_name]


def get_attacker_profile(level: int, enhanced: bool = False) -> Dict[str, Any]:
    """공격자 프로파일 반환"""
    profiles = ATTACKER_PROFILES_ENHANCED if enhanced else ATTACKER_PROFILES
    if level not in profiles:
        raise ValueError(f"Unknown attacker level: {level}")
    return profiles[level]


def get_tactic_info(tactic_id: int) -> Dict[str, Any]:
    """전술 정보 반환"""
    if tactic_id not in TACTIC_DEFINITIONS:
        return {"name": f"Unknown-{tactic_id}", "severity": 2}
    return TACTIC_DEFINITIONS[tactic_id]


def print_experiment_summary():
    """실험 설정 요약 출력"""
    print("=" * 60)
    print("📊 Experiment Configuration Summary")
    print("=" * 60)
    
    print("\n[Tactics]")
    for tid, tinfo in TACTIC_DEFINITIONS.items():
        if tid == 0:
            continue
        print(f"  {tid}. {tinfo['name']}: {len(tinfo.get('attacks', []))} attacks")
    
    print("\n[CTI Scenarios]")
    for sname, sinfo in CTI_EXPERIMENT_SCENARIOS.items():
        print(f"  - {sname}: noise={sinfo['cti_noise']:.0%}, delay={sinfo['cti_delay']}")
    
    print("\n[Attacker Levels]")
    for level, profile in ATTACKER_PROFILES.items():
        print(f"  L{level}: {profile['name']} (p_exploit={profile['p_exploit']:.0%})")
    
    print("=" * 60)


if __name__ == "__main__":
    print_experiment_summary()