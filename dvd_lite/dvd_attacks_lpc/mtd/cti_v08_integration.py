#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI Integration Module v08 - Cyber Threat Intelligence 연동
============================================================

MITRE ATT&CK 기반 위협 분류 및 MTD 권고 생성.
실시간 네트워크 트래픽 분석 및 위협 레벨 평가.

주요 기능:
1. MITRE ATT&CK 매핑
2. 위협 레벨 평가 (0-1)
3. MTD 권고 생성
4. 실시간 알림 시스템

저자: MTD-RL Research Team
버전: 0.8.3
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [CTI] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CTIIntegration")


# =============================================================================
# MITRE ATT&CK Mapping
# =============================================================================
class AttackPhase(Enum):
    """공격 단계"""
    RECONNAISSANCE = "reconnaissance"
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


# MITRE ATT&CK 기법 매핑 (드론/UAS 관련)
MITRE_TECHNIQUES = {
    # Reconnaissance
    "T1595": {
        "name": "Active Scanning",
        "phase": AttackPhase.RECONNAISSANCE,
        "severity": 0.3,
        "indicators": ["port_scan", "service_enum", "nmap"],
        "mtd_recommendation": ["shuffle", "decoy"],
    },
    "T1592": {
        "name": "Gather Victim Host Information",
        "phase": AttackPhase.RECONNAISSANCE,
        "severity": 0.25,
        "indicators": ["banner_grab", "version_scan"],
        "mtd_recommendation": ["shuffle"],
    },
    
    # Initial Access
    "T1190": {
        "name": "Exploit Public-Facing Application",
        "phase": AttackPhase.INITIAL_ACCESS,
        "severity": 0.7,
        "indicators": ["exploit_attempt", "cve_exploit", "mavlink_inject"],
        "mtd_recommendation": ["shuffle", "swap", "blacklist"],
    },
    "T1133": {
        "name": "External Remote Services",
        "phase": AttackPhase.INITIAL_ACCESS,
        "severity": 0.6,
        "indicators": ["ssh_brute", "mavlink_auth_fail"],
        "mtd_recommendation": ["blacklist", "port_hop"],
    },
    
    # Execution
    "T1059": {
        "name": "Command and Scripting Interpreter",
        "phase": AttackPhase.EXECUTION,
        "severity": 0.75,
        "indicators": ["command_injection", "shell_spawn"],
        "mtd_recommendation": ["shuffle", "swap", "blacklist"],
    },
    
    # Discovery
    "T1046": {
        "name": "Network Service Discovery",
        "phase": AttackPhase.DISCOVERY,
        "severity": 0.4,
        "indicators": ["service_scan", "port_scan"],
        "mtd_recommendation": ["shuffle", "decoy"],
    },
    "T1082": {
        "name": "System Information Discovery",
        "phase": AttackPhase.DISCOVERY,
        "severity": 0.35,
        "indicators": ["system_enum", "uname"],
        "mtd_recommendation": ["decoy"],
    },
    
    # Lateral Movement
    "T1021": {
        "name": "Remote Services",
        "phase": AttackPhase.LATERAL_MOVEMENT,
        "severity": 0.8,
        "indicators": ["lateral_ssh", "pivot"],
        "mtd_recommendation": ["shuffle", "swap", "blacklist"],
    },
    
    # Command and Control
    "T1571": {
        "name": "Non-Standard Port",
        "phase": AttackPhase.COMMAND_CONTROL,
        "severity": 0.7,
        "indicators": ["c2_beacon", "unusual_port"],
        "mtd_recommendation": ["shuffle", "port_hop", "blacklist"],
    },
    "T1573": {
        "name": "Encrypted Channel",
        "phase": AttackPhase.COMMAND_CONTROL,
        "severity": 0.65,
        "indicators": ["encrypted_c2", "tls_unusual"],
        "mtd_recommendation": ["blacklist"],
    },
    
    # UAS/Drone Specific
    "T1659": {
        "name": "GPS Spoofing",
        "phase": AttackPhase.IMPACT,
        "severity": 0.9,
        "indicators": ["gps_anomaly", "position_jump"],
        "mtd_recommendation": ["shuffle", "swap"],
    },
    "T1660": {
        "name": "MAVLink Injection",
        "phase": AttackPhase.EXECUTION,
        "severity": 0.85,
        "indicators": ["mavlink_inject", "command_spoof"],
        "mtd_recommendation": ["shuffle", "swap", "blacklist"],
    },
    "T1661": {
        "name": "Sensor Spoofing",
        "phase": AttackPhase.IMPACT,
        "severity": 0.85,
        "indicators": ["sensor_anomaly", "imu_drift"],
        "mtd_recommendation": ["swap"],
    },
}


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class ThreatIndicator:
    """위협 지표"""
    indicator_type: str
    value: str
    confidence: float = 0.5
    source: str = "network_monitor"
    timestamp: float = field(default_factory=time.time)
    related_ip: Optional[str] = None
    related_port: Optional[int] = None


@dataclass
class ThreatAlert:
    """위협 알림"""
    alert_id: str
    technique_id: str
    technique_name: str
    phase: AttackPhase
    severity: float
    confidence: float
    indicators: List[ThreatIndicator]
    mtd_recommendations: List[str]
    timestamp: float = field(default_factory=time.time)
    source_ip: Optional[str] = None
    target_service: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "technique_id": self.technique_id,
            "technique_name": self.technique_name,
            "phase": self.phase.value,
            "severity": self.severity,
            "confidence": self.confidence,
            "indicators": [asdict(i) for i in self.indicators],
            "mtd_recommendations": self.mtd_recommendations,
            "timestamp": self.timestamp,
            "source_ip": self.source_ip,
            "target_service": self.target_service,
        }


@dataclass
class CTIState:
    """CTI 상태"""
    alert: bool = False
    threat_level: float = 0.0
    attack_type: Optional[str] = None
    attack_phase: Optional[str] = None
    active_alerts: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# CTI Agent
# =============================================================================
class CTIAgent:
    """CTI Agent - 위협 인텔리전스 분석"""
    
    def __init__(
        self,
        output_file: Optional[str] = None,
        alert_threshold: float = 0.4,
        decay_rate: float = 0.95,
    ):
        self.output_file = Path(output_file) if output_file else None
        self.alert_threshold = alert_threshold
        self.decay_rate = decay_rate
        
        self.indicators: List[ThreatIndicator] = []
        self.alerts: List[ThreatAlert] = []
        self.active_alerts: Dict[str, ThreatAlert] = {}
        
        self.threat_level = 0.0
        self.attack_phase = None
        self.alert_counter = 0
        
        logger.info(f"CTI Agent initialized (threshold={alert_threshold})")
    
    def add_indicator(self, indicator: ThreatIndicator) -> List[ThreatAlert]:
        """위협 지표 추가 및 분석"""
        self.indicators.append(indicator)
        
        # 지표 매칭
        new_alerts = []
        for tech_id, tech_info in MITRE_TECHNIQUES.items():
            for pattern in tech_info["indicators"]:
                if pattern in indicator.indicator_type or pattern in indicator.value:
                    alert = self._create_alert(
                        technique_id=tech_id,
                        technique_info=tech_info,
                        indicator=indicator,
                    )
                    new_alerts.append(alert)
                    self.alerts.append(alert)
                    self.active_alerts[alert.alert_id] = alert
                    
                    logger.warning(
                        f"[ALERT] {tech_info['name']} detected! "
                        f"(severity={tech_info['severity']:.2f}, "
                        f"phase={tech_info['phase'].value})"
                    )
        
        # 위협 레벨 업데이트
        self._update_threat_level()
        
        # 상태 파일 업데이트
        self._save_state()
        
        return new_alerts
    
    def _create_alert(
        self,
        technique_id: str,
        technique_info: Dict,
        indicator: ThreatIndicator,
    ) -> ThreatAlert:
        """알림 생성"""
        self.alert_counter += 1
        
        return ThreatAlert(
            alert_id=f"CTI-{self.alert_counter:05d}",
            technique_id=technique_id,
            technique_name=technique_info["name"],
            phase=technique_info["phase"],
            severity=technique_info["severity"],
            confidence=indicator.confidence,
            indicators=[indicator],
            mtd_recommendations=technique_info["mtd_recommendation"],
            source_ip=indicator.related_ip,
        )
    
    def _update_threat_level(self):
        """위협 레벨 업데이트"""
        # 기존 위협 레벨 감쇠
        self.threat_level *= self.decay_rate
        
        # 활성 알림의 심각도 반영
        if self.active_alerts:
            max_severity = max(a.severity for a in self.active_alerts.values())
            avg_confidence = sum(a.confidence for a in self.active_alerts.values()) / len(self.active_alerts)
            
            self.threat_level = max(
                self.threat_level,
                max_severity * avg_confidence
            )
            
            # 가장 심각한 공격 단계 결정
            phases = [a.phase for a in self.active_alerts.values()]
            phase_order = list(AttackPhase)
            max_phase = max(phases, key=lambda p: phase_order.index(p))
            self.attack_phase = max_phase
        
        self.threat_level = min(1.0, self.threat_level)
    
    def get_state(self) -> CTIState:
        """현재 CTI 상태 반환"""
        is_alert = self.threat_level >= self.alert_threshold
        
        # MTD 권고 집계
        recommendations = set()
        for alert in self.active_alerts.values():
            recommendations.update(alert.mtd_recommendations)
        
        return CTIState(
            alert=is_alert,
            threat_level=self.threat_level,
            attack_type=self.attack_phase.value if self.attack_phase else None,
            attack_phase=self.attack_phase.value if self.attack_phase else None,
            active_alerts=[a.alert_id for a in self.active_alerts.values()],
            recommended_actions=list(recommendations),
        )
    
    def _save_state(self):
        """상태 파일 저장"""
        if not self.output_file:
            return
        
        state = self.get_state()
        state_dict = asdict(state)
        
        try:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_file, 'w') as f:
                json.dump(state_dict, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save CTI state: {e}")
    
    def process_network_event(
        self,
        event_type: str,
        source_ip: str,
        dest_port: int,
        details: Optional[Dict] = None,
    ) -> List[ThreatAlert]:
        """네트워크 이벤트 처리"""
        indicator = ThreatIndicator(
            indicator_type=event_type,
            value=f"{source_ip}:{dest_port}",
            confidence=0.6,
            source="network_monitor",
            related_ip=source_ip,
            related_port=dest_port,
        )
        
        return self.add_indicator(indicator)
    
    def process_mavlink_event(
        self,
        event_type: str,
        source_ip: str,
        message_type: str,
        details: Optional[Dict] = None,
    ) -> List[ThreatAlert]:
        """MAVLink 이벤트 처리"""
        severity_map = {
            "command_inject": 0.9,
            "auth_failure": 0.5,
            "unusual_command": 0.6,
            "replay_attack": 0.8,
        }
        
        confidence = severity_map.get(event_type, 0.5)
        
        indicator = ThreatIndicator(
            indicator_type=f"mavlink_{event_type}",
            value=message_type,
            confidence=confidence,
            source="mavlink_monitor",
            related_ip=source_ip,
        )
        
        return self.add_indicator(indicator)
    
    def get_mtd_boost_factor(self) -> float:
        """MTD 부스트 팩터 계산 (RL 정책 조정용)"""
        if self.threat_level < 0.3:
            return 1.0
        elif self.threat_level < 0.5:
            return 1.2
        elif self.threat_level < 0.7:
            return 1.4
        else:
            return 1.6
    
    def get_priority_services(self) -> List[str]:
        """우선 보호 서비스 목록"""
        # 공격 단계에 따라 우선순위 결정
        if self.attack_phase in [AttackPhase.RECONNAISSANCE, AttackPhase.DISCOVERY]:
            return ["fc_mavlink", "gcs_mavlink"]
        elif self.attack_phase in [AttackPhase.INITIAL_ACCESS, AttackPhase.EXECUTION]:
            return ["fc_mavlink", "cc_sitl", "gcs_mavlink"]
        elif self.attack_phase in [AttackPhase.LATERAL_MOVEMENT, AttackPhase.COMMAND_CONTROL]:
            return ["fc_mavlink", "cc_sitl", "gcs_mavlink", "sim_sitl"]
        else:
            return ["fc_mavlink"]
    
    def cleanup_old_alerts(self, max_age_sec: float = 300):
        """오래된 알림 정리"""
        now = time.time()
        expired = [
            alert_id for alert_id, alert in self.active_alerts.items()
            if now - alert.timestamp > max_age_sec
        ]
        
        for alert_id in expired:
            del self.active_alerts[alert_id]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired alerts")
            self._update_threat_level()
            self._save_state()


# =============================================================================
# Network Monitor Integration
# =============================================================================
class NetworkMonitorIntegration:
    """네트워크 모니터 연동"""
    
    def __init__(
        self,
        cti_agent: CTIAgent,
        monitor_file: Optional[str] = None,
        output_file: Optional[str] = None,
    ):
        self.cti_agent = cti_agent
        self.monitor_file = Path(monitor_file) if monitor_file else None
        self.output_file = Path(output_file) if output_file else None
        
        self.last_check_time = 0
        self.processed_events: Set[str] = set()
    
    def check_for_events(self) -> List[ThreatAlert]:
        """새 이벤트 확인"""
        if not self.monitor_file or not self.monitor_file.exists():
            return []
        
        try:
            with open(self.monitor_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read monitor file: {e}")
            return []
        
        alerts = []
        
        # 스캔 탐지
        if data.get("scan_detected"):
            for ip in data.get("suspicious_ips", []):
                event_id = f"scan_{ip}_{int(time.time())}"
                if event_id not in self.processed_events:
                    new_alerts = self.cti_agent.process_network_event(
                        event_type="port_scan",
                        source_ip=ip,
                        dest_port=0,
                    )
                    alerts.extend(new_alerts)
                    self.processed_events.add(event_id)
        
        # 서비스 발견
        if data.get("services_discovered", 0) > 0:
            event_id = f"discovery_{int(time.time())}"
            if event_id not in self.processed_events:
                new_alerts = self.cti_agent.process_network_event(
                    event_type="service_enum",
                    source_ip=data.get("suspicious_ips", ["unknown"])[0] if data.get("suspicious_ips") else "unknown",
                    dest_port=14550,
                )
                alerts.extend(new_alerts)
                self.processed_events.add(event_id)
        
        # Critical 노출
        if data.get("critical_exposed"):
            event_id = f"critical_{int(time.time())}"
            if event_id not in self.processed_events:
                new_alerts = self.cti_agent.process_network_event(
                    event_type="critical_discovery",
                    source_ip=data.get("suspicious_ips", ["unknown"])[0] if data.get("suspicious_ips") else "unknown",
                    dest_port=14550,
                )
                alerts.extend(new_alerts)
                self.processed_events.add(event_id)
        
        # 출력 파일 업데이트
        self._save_output()
        
        return alerts
    
    def _save_output(self):
        """출력 파일 저장"""
        if not self.output_file:
            return
        
        state = self.cti_agent.get_state()
        
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": state.alert,
            "threat_level": state.threat_level,
            "attack_type": state.attack_type,
            "attack_phase": state.attack_phase,
            "active_alerts": state.active_alerts,
            "recommended_actions": state.recommended_actions,
            "mtd_boost_factor": self.cti_agent.get_mtd_boost_factor(),
            "priority_services": self.cti_agent.get_priority_services(),
        }
        
        try:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_file, 'w') as f:
                json.dump(output, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save output: {e}")


# =============================================================================
# CLI
# =============================================================================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="CTI Integration Module v08.3")
    
    parser.add_argument(
        "--output", type=str, default="/tmp/cti_state.json",
        help="Output file for CTI state"
    )
    parser.add_argument(
        "--monitor-file", type=str, default="/tmp/network_monitor.json",
        help="Network monitor input file"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.4,
        help="Alert threshold"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Run test scenario"
    )
    
    args = parser.parse_args()
    
    cti_agent = CTIAgent(
        output_file=args.output,
        alert_threshold=args.threshold,
    )
    
    if args.test:
        print("\n=== CTI Integration Test ===\n")
        
        # 테스트 시나리오
        print("1. Simulating port scan...")
        cti_agent.process_network_event(
            event_type="port_scan",
            source_ip="192.168.1.100",
            dest_port=14550,
        )
        
        print("\n2. Simulating service enumeration...")
        cti_agent.process_network_event(
            event_type="service_enum",
            source_ip="192.168.1.100",
            dest_port=5760,
        )
        
        print("\n3. Simulating MAVLink injection attempt...")
        cti_agent.process_mavlink_event(
            event_type="command_inject",
            source_ip="192.168.1.100",
            message_type="COMMAND_LONG",
        )
        
        print("\n4. Current CTI State:")
        state = cti_agent.get_state()
        print(f"   Alert: {state.alert}")
        print(f"   Threat Level: {state.threat_level:.2f}")
        print(f"   Attack Phase: {state.attack_phase}")
        print(f"   Active Alerts: {len(state.active_alerts)}")
        print(f"   Recommendations: {state.recommended_actions}")
        print(f"   MTD Boost Factor: {cti_agent.get_mtd_boost_factor():.2f}")
        print(f"   Priority Services: {cti_agent.get_priority_services()}")
        
        print(f"\n✅ CTI state saved to {args.output}")
    
    else:
        # 실시간 모니터링 모드
        monitor = NetworkMonitorIntegration(
            cti_agent=cti_agent,
            monitor_file=args.monitor_file,
            output_file=args.output,
        )
        
        logger.info("Starting CTI monitoring...")
        
        while True:
            try:
                alerts = monitor.check_for_events()
                cti_agent.cleanup_old_alerts()
                time.sleep(5)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break


if __name__ == "__main__":
    main()
