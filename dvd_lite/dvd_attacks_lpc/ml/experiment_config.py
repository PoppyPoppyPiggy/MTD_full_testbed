#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment Config v2.0 (Paper-Ready)
=====================================
논문 실험 설정 - 전술/공격자/CTI 시나리오
"""

import os
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# =============================================================================
# 전술(Tactic) 정의 - MITRE ATT&CK 정렬
# =============================================================================

TACTIC_DEFINITIONS = {
    0: {"name": "Normal", "severity": 0, "mtd_response": None, "attacks": []},
    1: {
        "name": "Reconnaissance", "severity": 1, "mtd_response": "port_shuffle",
        "attacks": ["wifi-analysis-cracking", "drone-discovery", "companion-computer-discovery",
                   "ground-control-station-discovery", "drone-gps-telemetry-detection",
                   "protocol-fingerprinting", "packet-sniffing"]
    },
    2: {
        "name": "Credential Access", "severity": 2, "mtd_response": "service_swap",
        "attacks": ["companion-computer-web-ui-login-brute-force", "companion-computer-takeover"]
    },
    3: {
        "name": "Tampering", "severity": 2, "mtd_response": "ip_shuffle",
        "attacks": ["attitude-spoofing", "battery-spoofing", "gps-spoofing",
                   "critical-error-spoofing", "emergency-status-spoofing",
                   "vfr-hud-spoofing", "system-status-spoofing"]
    },
    4: {
        "name": "DoS", "severity": 3, "mtd_response": "full_shuffle",
        "attacks": ["wifi-deauth-attack", "geofencing-attack", "gps-offset-glitching",
                   "flight-termination", "denial-of-takeoff", "communication-link-flooding",
                   "camera-feed-ros-topic-flooding"]
    },
    5: {
        "name": "Command Injection", "severity": 4, "mtd_response": "full_shuffle",
        "attacks": ["ground-control-station-spoofing", "camera-gimbal-takeover", "gps-data-injection",
                   "return-to-home-point-override", "waypoint-injection", "satellite-spoofing",
                   "mavlink-injection-attack", "flight-mode-injection"]
    },
    6: {
        "name": "Exfiltration", "severity": 3, "mtd_response": "decoy_activate",
        "attacks": ["wifi-client-data-leak", "flight-log-extraction", "mission-extraction",
                   "parameter-extraction", "ftp-eavesdropping", "camera-feed-eavesdropping"]
    },
    7: {
        "name": "Persistence", "severity": 4, "mtd_response": "full_shuffle",
        "attacks": ["firmware-decompile", "firmware-modding"]
    }
}

# =============================================================================
# CTI 실험 시나리오
# =============================================================================

CTI_SCENARIOS = {
    "ideal": {"name": "Ideal", "cti_noise": 0.0, "cti_delay": 0, "attacker_boost": 1.0},
    "realistic": {"name": "Realistic", "cti_noise": 0.15, "cti_delay": 2, "attacker_boost": 1.0},
    "degraded": {"name": "Degraded", "cti_noise": 0.25, "cti_delay": 3, "attacker_boost": 1.0},
    "adversarial": {"name": "Adversarial", "cti_noise": 0.20, "cti_delay": 2, "attacker_boost": 1.3},
    "no_cti": {"name": "No CTI", "cti_noise": 1.0, "cti_delay": 0, "attacker_boost": 1.0},
}

# =============================================================================
# 공격자 프로파일 (MLTAM)
# =============================================================================

ATTACKER_PROFILES = {
    0: {"name": "Script Kiddie", "scan_rate": 0.03, "p_disc": 0.15, "p_exploit": 0.08, "kappa": 1.00},
    1: {"name": "Hobbyist", "scan_rate": 0.05, "p_disc": 0.25, "p_exploit": 0.12, "kappa": 0.92},
    2: {"name": "Professional", "scan_rate": 0.08, "p_disc": 0.35, "p_exploit": 0.20, "kappa": 0.84},
    3: {"name": "Expert", "scan_rate": 0.12, "p_disc": 0.50, "p_exploit": 0.30, "kappa": 0.76},
    4: {"name": "APT", "scan_rate": 0.15, "p_disc": 0.65, "p_exploit": 0.40, "kappa": 0.68},
}

ATTACKER_PROFILES_ENHANCED = {
    0: {"name": "Script Kiddie", "scan_rate": 0.03, "p_disc": 0.15, "p_exploit": 0.08, "kappa": 1.00},
    1: {"name": "Hobbyist", "scan_rate": 0.05, "p_disc": 0.25, "p_exploit": 0.12, "kappa": 0.92},
    2: {"name": "Professional", "scan_rate": 0.08, "p_disc": 0.35, "p_exploit": 0.20, "kappa": 0.84},
    3: {"name": "Expert", "scan_rate": 0.15, "p_disc": 0.60, "p_exploit": 0.40, "kappa": 0.72},
    4: {"name": "APT", "scan_rate": 0.20, "p_disc": 0.75, "p_exploit": 0.55, "kappa": 0.60},
}

# =============================================================================
# MTD 액션 계수
# =============================================================================

MTD_COEFFICIENTS = {
    "service_swap": {"alpha": 0.45, "cite": "Hong & Kim 2016"},
    "network_shuffle": {"alpha": 0.35, "cite": "Jafarian et al. 2015"},
    "port_hop": {"alpha": 0.20, "cite": "Luo et al. 2015"},
    "decoy_activate": {"alpha": 0.15, "cite": "Albanese et al. 2013"},
}

# =============================================================================
# 메트릭 정의
# =============================================================================

METRICS = {
    "s_mtd": {"name": "Defense Score", "higher_is_better": True},
    "breach_rate": {"name": "Breach Rate", "higher_is_better": False},
    "mttc": {"name": "Mean Time to Compromise", "higher_is_better": True},
    "cer": {"name": "Cost Efficiency Ratio", "higher_is_better": True},
    "cdi": {"name": "Config Diversity Index", "higher_is_better": True},
    "asr": {"name": "Attack Surface Reduction", "higher_is_better": True},
}

# =============================================================================
# 유틸리티 함수
# =============================================================================

def get_tactic(tactic_id: int) -> Dict[str, Any]:
    return TACTIC_DEFINITIONS.get(tactic_id, {"name": f"Unknown-{tactic_id}", "severity": 2})

def get_attacker(level: int, enhanced: bool = False) -> Dict[str, Any]:
    profiles = ATTACKER_PROFILES_ENHANCED if enhanced else ATTACKER_PROFILES
    return profiles.get(level, ATTACKER_PROFILES[2])

def get_scenario(name: str) -> Dict[str, Any]:
    return CTI_SCENARIOS.get(name, CTI_SCENARIOS["realistic"])

def print_summary():
    print("=" * 60)
    print("📊 Experiment Config Summary")
    print("=" * 60)
    print(f"\n[Tactics] {len(TACTIC_DEFINITIONS) - 1}개")
    for tid, t in TACTIC_DEFINITIONS.items():
        if tid == 0: continue
        print(f"  {tid}. {t['name']}: {len(t.get('attacks', []))} attacks")
    print(f"\n[CTI Scenarios] {len(CTI_SCENARIOS)}개")
    for k, v in CTI_SCENARIOS.items():
        print(f"  - {k}: noise={v['cti_noise']:.0%}, delay={v['cti_delay']}")
    print(f"\n[Attacker Levels] {len(ATTACKER_PROFILES)}개")
    for lv, p in ATTACKER_PROFILES.items():
        print(f"  L{lv}: {p['name']} (p_exploit={p['p_exploit']:.0%})")
    print("=" * 60)


if __name__ == "__main__":
    print_summary()
