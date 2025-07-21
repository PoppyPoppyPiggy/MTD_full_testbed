# dvd_lite/dvd_attacks/protocol_tampering/rf_jamming.py
"""
무선 주파수 재밍 공격 (Damn Vulnerable Drone 기반)
"""
import asyncio
import random
import math
from typing import Tuple, List, Dict, Any

from ..core.attack_base import BaseAttack, AttackType

class RadioFrequencyJamming(BaseAttack):
    """무선 주파수 재밍 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.PROTOCOL_TAMPERING
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """드론 통신 주파수 간섭 및 신호 차단"""
        await asyncio.sleep(3.8)
        
        # DVD 환경의 주요 통신 주파수들
        dvd_frequency_bands = {
            "wifi_2_4ghz": {
                "range": "2400-2485 MHz",
                "center_frequency": 2442.5,  # Channel 6 center
                "protocols": ["802.11 WiFi", "MAVLink over WiFi"],
                "channels": [1, 6, 11],  # Non-overlapping channels
                "bandwidth": 20,  # MHz
                "power_level": -30,  # dBm typical
                "usage": "Primary data link for DVD environment",
                "jamming_effectiveness": 0.9
            },
            "wifi_5ghz": {
                "range": "5150-5875 MHz", 
                "center_frequency": 5500,
                "protocols": ["802.11ac WiFi", "High-bandwidth video"],
                "channels": [36, 40, 44, 48, 149, 153, 157, 161],
                "bandwidth": 80,  # MHz
                "power_level": -25,  # dBm
                "usage": "Secondary/backup communication",
                "jamming_effectiveness": 0.85
            },
            "gps_l1": {
                "range": "1575.42 MHz ±2 MHz",
                "center_frequency": 1575.42,
                "protocols": ["GPS L1 C/A", "GLONASS G1"],
                "bandwidth": 2,  # MHz
                "power_level": -130,  # dBm (very weak)
                "usage": "Primary navigation signal",
                "jamming_effectiveness": 0.95,
                "signal_type": "spread_spectrum"
            },
            "gps_l2": {
                "range": "1227.60 MHz ±10 MHz", 
                "center_frequency": 1227.60,
                "protocols": ["GPS L2C", "GLONASS G2"],
                "bandwidth": 20,  # MHz
                "power_level": -130,  # dBm
                "usage": "Dual-frequency navigation",
                "jamming_effectiveness": 0.90,
                "signal_type": "spread_spectrum"
            },
            "ism_433mhz": {
                "range": "433.05-434.79 MHz",
                "center_frequency": 433.92,
                "protocols": ["Long Range RC", "Telemetry"],
                "bandwidth": 1.74,  # MHz
                "power_level": -10,  # dBm
                "usage": "Long range control backup",
                "jamming_effectiveness": 0.8
            },
            "ism_915mhz": {
                "range": "902-928 MHz",
                "center_frequency": 915,
                "protocols": ["900MHz Telemetry", "RC Control"],
                "bandwidth": 26,  # MHz
                "power_level": -5,  # dBm
                "usage": "Regional telemetry (US)",
                "jamming_effectiveness": 0.85
            }
        }
        
        # 재밍 장비 및 방법들
        jamming_equipment = [
            {
                "device": "HackRF One",
                "frequency_range": "1 MHz - 6 GHz",
                "max_power": "15 dBm",
                "bandwidth": "20 MHz",
                "cost": "$300",
                "portability": "high",
                "effectiveness": 0.7,
                "detection_risk": "medium"
            },
            {
                "device": "BladeRF 2.0",
                "frequency_range": "47 MHz - 6 GHz", 
                "max_power": "17 dBm",
                "bandwidth": "56 MHz",
                "cost": "$700",
                "portability": "medium",
                "effectiveness": 0.8,
                "detection_risk": "medium"
            },
            {
                "device": "USRP B210",
                "frequency_range": "70 MHz - 6 GHz",
                "max_power": "20 dBm",
                "bandwidth": "56 MHz", 
                "cost": "$2000",
                "portability": "medium",
                "effectiveness": 0.85,
                "detection_risk": "low"
            },
            {
                "device": "Commercial GPS Jammer",
                "frequency_range": "1570-1580 MHz",
                "max_power": "30 dBm",
                "bandwidth": "10 MHz",
                "cost": "$50",
                "portability": "very_high",
                "effectiveness": 0.95,
                "detection_risk": "high",
                "specialized": "GPS only"
            },
            {
                "device": "WiFi Deauther (ESP8266)",
                "frequency_range": "2400-2485 MHz",
                "max_power": "20 dBm",
                "bandwidth": "20 MHz",
                "cost": "$10",
                "portability": "very_high", 
                "effectiveness": 0.6,
                "detection_risk": "low",
                "specialized": "WiFi only"
            }
        ]
        
        # 재밍 기법들
        jamming_techniques = [
            {
                "technique": "broadband_noise_jamming",
                "description": "Wideband white noise across target frequency",
                "power_efficiency": 0.3,
                "detection_difficulty": "easy",
                "effective_range": "100-500m",
                "counter_resistance": "low"
            },
            {
                "technique": "swept_jamming",
                "description": "Frequency sweeping across target band",
                "power_efficiency": 0.5,
                "detection_difficulty": "medium", 
                "effective_range": "200-800m",
                "counter_resistance": "medium"
            },
            {
                "technique": "protocol_aware_jamming", 
                "description": "Target specific protocol patterns",
                "power_efficiency": 0.8,
                "detection_difficulty": "hard",
                "effective_range": "500-1500m",
                "counter_resistance": "high"
            },
            {
                "technique": "reactive_jamming",
                "description": "Jam only when target transmission detected",
                "power_efficiency": 0.9,
                "detection_difficulty": "very_hard",
                "effective_range": "300-1000m", 
                "counter_resistance": "very_high"
            },
            {
                "technique": "deceptive_jamming",
                "description": "Inject false signals mimicking legitimate traffic",
                "power_efficiency": 0.7,
                "detection_difficulty": "extremely_hard",
                "effective_range": "100-500m",
                "counter_resistance": "extremely_high"
            }
        ]
        
        # 재밍 공격 시뮬레이션
        chosen_equipment = random.choice(jamming_equipment)
        chosen_technique = random.choice(jamming_techniques)
        
        # 타겟 주파수 선택 (DVD 환경에서는 주로 WiFi와 GPS)
        primary_targets = ["wifi_2_4ghz", "gps_l1"]
        if random.random() > 0.3:  # 70% 확률로 추가 타겟
            primary_targets.append(random.choice(["wifi_5ghz", "gps_l2", "ism_915mhz"]))
        
        jamming_results = {}
        total_effectiveness = 0
        
        for target_band in primary_targets:
            band_info = dvd_frequency_bands[target_band]
            
            # 재밍 효과 계산
            base_effectiveness = band_info["jamming_effectiveness"]
            equipment_modifier = chosen_equipment["effectiveness"]
            technique_modifier = self._get_technique_effectiveness(chosen_technique, band_info)
            distance_modifier = self._calculate_distance_effect()
            power_modifier = self._calculate_power_effect(chosen_equipment, band_info)
            
            final_effectiveness = (
                base_effectiveness * 
                equipment_modifier * 
                technique_modifier * 
                distance_modifier * 
                power_modifier
            )
            
            # 재밍 성공 여부
            jamming_success = random.random() < final_effectiveness
            
            jamming_result = {
                "target_band": target_band,
                "center_frequency": band_info["center_frequency"],
                "protocols_affected": band_info["protocols"],
                "jamming_success": jamming_success,
                "effectiveness_score": final_effectiveness,
                "power_required": self._calculate_required_power(band_info, chosen_technique),
                "jamming_duration": random.uniform(30, 300),  # seconds
                "side_effects": self._calculate_side_effects(target_band),
                "detection_indicators": self._generate_detection_indicators(target_band, chosen_technique)
            }
            
            jamming_results[target_band] = jamming_result
            if jamming_success:
                total_effectiveness += final_effectiveness
        
        # DVD 환경에서의 영향 분석
        dvd_impact = self._analyze_dvd_impact(jamming_results)
        
        # 대응 방안 분석
        countermeasures = self._analyze_countermeasures(jamming_results, chosen_technique)
        
        # IOC 생성
        iocs = []
        for band, result in jamming_results.items():
            iocs.append(f"RF_JAMMING:{band}")
            iocs.append(f"FREQUENCY_JAMMED:{result['center_frequency']}")
            
            for protocol in result["protocols_affected"]:
                iocs.append(f"PROTOCOL_JAMMED:{protocol}")
            
            if result["jamming_success"]:
                iocs.append(f"SUCCESSFUL_JAMMING:{band}")
                
                if band in ["gps_l1", "gps_l2"]:
                    iocs.append("GPS_NAVIGATION_DENIED")
                elif "wifi" in band:
                    iocs.append("WIFI_COMMUNICATION_BLOCKED")
                
                if result["effectiveness_score"] > 0.8:
                    iocs.append(f"HIGH_IMPACT_JAMMING:{band}")
        
        # 장비 및 기법 IOC
        iocs.extend([
            f"JAMMING_EQUIPMENT:{chosen_equipment['device']}",
            f"JAMMING_TECHNIQUE:{chosen_technique['technique']}",
            f"POWER_LEVEL:{chosen_equipment['max_power']}",
            f"DETECTION_RISK:{chosen_equipment['detection_risk']}"
        ])
        
        # DVD 특정 IOC
        if dvd_impact["communication_disrupted"]:
            iocs.append("DVD_COMMUNICATION_DISRUPTED")
        if dvd_impact["navigation_compromised"]:
            iocs.append("DVD_NAVIGATION_COMPROMISED")
        if dvd_impact["mission_abort_triggered"]:
            iocs.append("DVD_MISSION_ABORT")
        
        success = any(result["jamming_success"] for result in jamming_results.values())
        
        details = {
            "target_frequency_bands": dvd_frequency_bands,
            "jamming_equipment": chosen_equipment,
            "jamming_technique": chosen_technique,
            "jamming_results": jamming_results,
            "dvd_impact_analysis": dvd_impact,
            "countermeasures": countermeasures,
            "legal_considerations": {
                "illegal_in_most_countries": True,
                "fcc_violations": ["Intentional interference", "Unlicensed transmission"],
                "potential_penalties": ["Heavy fines", "Equipment confiscation", "Criminal charges"]
            },
            "effectiveness_score": total_effectiveness / len(primary_targets) if primary_targets else 0,
            "detection_probability": self._calculate_detection_probability(chosen_equipment, chosen_technique),
            "success_rate": sum(1 for r in jamming_results.values() if r["jamming_success"]) / len(jamming_results)
        }
        
        return success, iocs, details
    
    def _get_technique_effectiveness(self, technique: Dict, band_info: Dict) -> float:
        """재밍 기법의 주파수 대역별 효과"""
        technique_name = technique["technique"]
        
        # GPS 신호는 매우 약하므로 모든 기법이 효과적
        if "gps" in band_info.get("usage", "").lower():
            return 1.0
        
        # WiFi는 기법에 따라 효과 차이
        if "wifi" in band_info.get("usage", "").lower():
            effectiveness_map = {
                "broadband_noise_jamming": 0.7,
                "swept_jamming": 0.8,
                "protocol_aware_jamming": 0.95,
                "reactive_jamming": 0.9,
                "deceptive_jamming": 0.85
            }
            return effectiveness_map.get(technique_name, 0.7)
        
        return 0.8  # 기본값
    
    def _calculate_distance_effect(self) -> float:
        """거리에 따른 재밍 효과 계산"""
        # DVD 환경에서는 비교적 가까운 거리 가정
        distance = random.uniform(10, 100)  # meters
        
        # 자유공간 경로손실: FSPL = 20*log10(d) + 20*log10(f) + 32.44
        # 간단화된 거리 효과 모델
        if distance <= 50:
            return 1.0
        elif distance <= 100:
            return 0.8
        elif distance <= 200:
            return 0.6
        else:
            return 0.4
    
    def _calculate_power_effect(self, equipment: Dict, band_info: Dict) -> float:
        """장비 출력에 따른 효과 계산"""
        equipment_power = float(equipment["max_power"].replace(" dBm", ""))
        target_power = band_info["power_level"]
        
        # 신호 대 재밍 비율 (SJR) 계산
        sjr_db = target_power - equipment_power
        
        # SJR에 따른 재밍 효과
        if sjr_db < -20:  # 재밍 신호가 20dB 이상 강함
            return 1.0
        elif sjr_db < -10:
            return 0.9
        elif sjr_db < 0:
            return 0.7
        else:
            return 0.5
    
    def _calculate_required_power(self, band_info: Dict, technique: Dict) -> str:
        """필요 재밍 출력 계산"""
        base_power = 20  # dBm
        
        # GPS는 신호가 약하므로 낮은 출력으로도 재밍 가능
        if "gps" in band_info.get("usage", "").lower():
            base_power = 10
        
        # 기법에 따른 출력 조정
        efficiency = technique["power_efficiency"]
        required_power = base_power / efficiency
        
        return f"{required_power:.1f} dBm"
    
    def _calculate_side_effects(self, target_band: str) -> List[str]:
        """재밍으로 인한 부작용"""
        side_effects = []
        
        if "wifi" in target_band:
            side_effects.extend([
                "Nearby WiFi networks disrupted",
                "Bluetooth interference possible",
                "Microwave oven-like interference"
            ])
        
        if "gps" in target_band:
            side_effects.extend([
                "GPS receivers in area affected",
                "Emergency services GPS disrupted",
                "Aviation navigation interference"
            ])
        
        # 광대역 재밍의 경우 추가 부작용
        if random.random() > 0.6:
            side_effects.extend([
                "Radio broadcast interference",
                "Cellular service degradation",
                "IoT device connectivity issues"
            ])
        
        return side_effects
    
    def _generate_detection_indicators(self, target_band: str, technique: Dict) -> List[str]:
        """재밍 탐지 지표"""
        indicators = [
            "Sudden signal strength increase in target band",
            "Communication timeout events",
            "Increased bit error rates"
        ]
        
        if "wifi" in target_band:
            indicators.extend([
                "WiFi disconnection events",
                "Decreased throughput",
                "Association failures"
            ])
        
        if "gps" in target_band:
            indicators.extend([
                "GPS signal loss",
                "Position accuracy degradation", 
                "Time synchronization errors"
            ])
        
        # 기법별 특정 지표
        if technique["technique"] == "deceptive_jamming":
            indicators.append("False signal patterns detected")
        elif technique["technique"] == "reactive_jamming":
            indicators.append("Intermittent interference patterns")
        
        return indicators
    
    def _analyze_dvd_impact(self, jamming_results: Dict) -> Dict[str, Any]:
        """DVD 환경에서의 재밍 영향 분석"""
        impact = {
            "communication_disrupted": False,
            "navigation_compromised": False,
            "video_stream_affected": False,
            "mavlink_connection_lost": False,
            "mission_abort_triggered": False,
            "failsafe_activated": False
        }
        
        # WiFi 재밍 영향
        wifi_jammed = any(
            result["jamming_success"] 
            for band, result in jamming_results.items() 
            if "wifi" in band
        )
        
        if wifi_jammed:
            impact.update({
                "communication_disrupted": True,
                "video_stream_affected": True,
                "mavlink_connection_lost": True
            })
            
            # 심각한 재밍의 경우 미션 중단
            if any(r["effectiveness_score"] > 0.8 for r in jamming_results.values()):
                impact["mission_abort_triggered"] = True
        
        # GPS 재밍 영향
        gps_jammed = any(
            result["jamming_success"]
            for band, result in jamming_results.items()
            if "gps" in band
        )
        
        if gps_jammed:
            impact.update({
                "navigation_compromised": True,
                "failsafe_activated": True
            })
            
            # GPS 완전 차단시 RTL 모드 활성화 불가
            if jamming_results.get("gps_l1", {}).get("effectiveness_score", 0) > 0.9:
                impact["mission_abort_triggered"] = True
        
        return impact
    
    def _analyze_countermeasures(self, jamming_results: Dict, technique: Dict) -> Dict[str, Any]:
        """재밍 대응 방안 분석"""
        return {
            "immediate_responses": [
                "Switch to backup communication channel",
                "Activate autonomous failsafe mode",
                "Reduce altitude and find safe landing zone",
                "Enable INS/dead reckoning navigation"
            ],
            "technical_countermeasures": [
                "Frequency hopping spread spectrum",
                "Directional antennas for interference rejection",
                "Multi-constellation GNSS receivers", 
                "Backup inertial navigation systems",
                "Mesh networking for redundancy"
            ],
            "detection_methods": [
                "RF spectrum analysis",
                "Signal strength monitoring",
                "Communication quality metrics",
                "Jamming signature recognition"
            ],
            "prevention_strategies": [
                "Operate in different frequency bands",
                "Use encrypted and authenticated protocols",
                "Implement anti-jamming antennas",
                "Deploy multiple redundant links"
            ],
            "effectiveness_against_current_attack": self._evaluate_countermeasure_effectiveness(technique)
        }
    
    def _evaluate_countermeasure_effectiveness(self, technique: Dict) -> Dict[str, float]:
        """현재 공격에 대한 대응 방안 효과"""
        technique_name = technique["technique"]
        
        effectiveness = {
            "frequency_hopping": 0.8,
            "directional_antennas": 0.6,
            "backup_systems": 0.9,
            "detection_systems": 0.7
        }
        
        # 기법별 대응 효과 조정
        if technique_name == "protocol_aware_jamming":
            effectiveness["frequency_hopping"] = 0.9
        elif technique_name == "reactive_jamming":
            effectiveness["detection_systems"] = 0.4
        elif technique_name == "deceptive_jamming":
            effectiveness["directional_antennas"] = 0.3
        
        return effectiveness
    
    def _calculate_detection_probability(self, equipment: Dict, technique: Dict) -> float:
        """재밍 탐지 확률 계산"""
        base_detection = {
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2,
            "very_low": 0.1
        }.get(equipment["detection_risk"], 0.5)
        
        # 기법에 따른 탐지 난이도 조정
        technique_stealth = {
            "broadband_noise_jamming": 0.2,
            "swept_jamming": 0.4,
            "protocol_aware_jamming": 0.7,
            "reactive_jamming": 0.8,
            "deceptive_jamming": 0.9
        }.get(technique["technique"], 0.5)
        
        # DVD 환경에서는 모니터링이 제한적이므로 탐지 확률 감소
        dvd_modifier = 0.7
        
        return base_detection * (1 - technique_stealth) * dvd_modifier