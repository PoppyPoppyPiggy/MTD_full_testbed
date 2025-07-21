# dvd_lite/dvd_attacks/exfiltration/flight_logs.py
"""
비행 로그 추출 공격 - 개선된 버전
실제 드론 로그 시스템 타겟팅
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from datetime import datetime, timedelta
from ..core.attack_base import BaseAttack, AttackType

class FlightLogExtraction(BaseAttack):
    """비행 로그 추출 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.EXFILTRATION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """드론 비행 기록 및 운영 데이터 탈취"""
        await asyncio.sleep(4.8)
        
        # 실제 드론 로그 파일 시스템
        log_file_system = {
            "flight_controller_logs": [
                {
                    "filename": f"arducopter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin",
                    "type": "binary_flight_data",
                    "size_mb": random.uniform(15, 85),
                    "contains": [
                        "gps_coordinates", "altitude_data", "attitude_data",
                        "battery_status", "motor_outputs", "sensor_readings",
                        "control_inputs", "failsafe_events", "parameter_changes"
                    ],
                    "sensitivity": "critical",
                    "retention_days": 30,
                    "location": "/var/log/ardupilot/"
                },
                {
                    "filename": f"mission_log_{datetime.now().strftime('%Y%m%d')}.tlog",
                    "type": "telemetry_log",
                    "size_mb": random.uniform(5, 25),
                    "contains": [
                        "mavlink_messages", "gcs_commands", "status_updates",
                        "waypoint_data", "mission_progress", "operator_inputs"
                    ],
                    "sensitivity": "high",
                    "retention_days": 90,
                    "location": "/home/pi/mission_planner/"
                }
            ],
            "companion_computer_logs": [
                {
                    "filename": f"camera_metadata_{datetime.now().strftime('%Y%m%d')}.log",
                    "type": "imaging_data",
                    "size_mb": random.uniform(2, 15),
                    "contains": [
                        "image_timestamps", "gps_exif_data", "camera_settings",
                        "gimbal_positions", "recording_sessions"
                    ],
                    "sensitivity": "medium",
                    "retention_days": 60,
                    "location": "/opt/camera/logs/"
                },
                {
                    "filename": "system_events.log",
                    "type": "system_log",
                    "size_mb": random.uniform(8, 40),
                    "contains": [
                        "boot_sequences", "service_starts", "error_messages",
                        "network_events", "user_logins", "command_history"
                    ],
                    "sensitivity": "medium",
                    "retention_days": 30,
                    "location": "/var/log/"
                },
                {
                    "filename": f"network_traffic_{datetime.now().strftime('%Y%m%d')}.pcap",
                    "type": "network_capture",
                    "size_mb": random.uniform(50, 200),
                    "contains": [
                        "mavlink_traffic", "video_streams", "telemetry_data",
                        "control_commands", "diagnostic_data"
                    ],
                    "sensitivity": "high",
                    "retention_days": 7,
                    "location": "/opt/network/captures/"
                }
            ],
            "ground_station_logs": [
                {
                    "filename": f"qgc_console_{datetime.now().strftime('%Y%m%d')}.log",
                    "type": "gcs_log",
                    "size_mb": random.uniform(3, 20),
                    "contains": [
                        "operator_actions", "mission_planning", "parameter_modifications",
                        "flight_mode_changes", "alert_messages"
                    ],
                    "sensitivity": "high",
                    "retention_days": 180,
                    "location": "/home/operator/QGroundControl/logs/"
                },
                {
                    "filename": "operator_session.log",
                    "type": "session_log",
                    "size_mb": random.uniform(1, 8),
                    "contains": [
                        "login_sessions", "command_sequences", "decision_records",
                        "communication_logs", "emergency_procedures"
                    ],
                    "sensitivity": "critical",
                    "retention_days": 365,
                    "location": "/var/log/operator/"
                }
            ]
        }
        
        # 접근 방법 및 기법
        access_methods = [
            {
                "method": "ftp_exploitation",
                "description": "Exploit weak FTP credentials",
                "success_rate": 0.75,
                "requirements": ["network_access", "credential_weakness"],
                "stealth_level": "medium",
                "accessible_locations": ["/var/log/", "/home/pi/", "/opt/"]
            },
            {
                "method": "ssh_key_theft",
                "description": "Stolen or weak SSH keys",
                "success_rate": 0.6,
                "requirements": ["ssh_access", "key_management_weakness"],
                "stealth_level": "high",
                "accessible_locations": ["/var/log/", "/home/", "/opt/", "/root/"]
            },
            {
                "method": "sd_card_physical_access",
                "description": "Physical SD card extraction",
                "success_rate": 0.95,
                "requirements": ["physical_access", "storage_media"],
                "stealth_level": "low",
                "accessible_locations": ["all_storage"]
            },
            {
                "method": "web_interface_exploitation",
                "description": "Companion computer web interface vulnerability",
                "success_rate": 0.55,
                "requirements": ["web_vulnerability", "authentication_bypass"],
                "stealth_level": "medium",
                "accessible_locations": ["/opt/", "/var/log/"]
            },
            {
                "method": "mavlink_file_request",
                "description": "MAVLink file transfer protocol abuse",
                "success_rate": 0.4,
                "requirements": ["mavlink_access", "file_transfer_enabled"],
                "stealth_level": "high",
                "accessible_locations": ["/var/log/ardupilot/"]
            },
            {
                "method": "usb_autorun_exploitation",
                "description": "USB storage device with autorun payload",
                "success_rate": 0.7,
                "requirements": ["physical_usb_access", "autorun_enabled"],
                "stealth_level": "medium",
                "accessible_locations": ["/media/", "/mnt/"]
            }
        ]
        
        # 공격 실행 시뮬레이션
        chosen_method = random.choice(access_methods)
        extracted_logs = []
        
        # 각 로그 카테고리에서 파일 추출 시도
        for category, log_files in log_file_system.items():
            for log_file in log_files:
                if self._can_access_location(log_file["location"], chosen_method):
                    if random.random() < chosen_method["success_rate"]:
                        extraction_result = self._extract_log_file(log_file, chosen_method)
                        extracted_logs.append(extraction_result)
        
        # 정보 가치 분석
        intelligence_analysis = self._analyze_intelligence_value(extracted_logs)
        
        # 작전 보안 영향 평가
        opsec_impact = self._assess_operational_security_impact(extracted_logs)
        
        # 포렌식 흔적 분석
        forensic_traces = self._analyze_forensic_traces(chosen_method, extracted_logs)
        
        # IOC 생성
        iocs = self._generate_extraction_iocs(extracted_logs, chosen_method)
        
        success = len(extracted_logs) > 0
        
        details = {
            "log_file_system": log_file_system,
            "access_method": chosen_method,
            "extracted_logs": extracted_logs,
            "intelligence_analysis": intelligence_analysis,
            "operational_security_impact": opsec_impact,
            "forensic_traces": forensic_traces,
            "data_exfiltration_channels": self._get_exfiltration_channels(),
            "persistence_mechanisms": self._get_persistence_mechanisms(),
            "success_rate": chosen_method["success_rate"] if success else 0.1
        }
        
        return success, iocs, details
    
    def _can_access_location(self, location: str, method: Dict) -> bool:
        """접근 방법에 따른 위치 접근 가능성 확인"""
        accessible_locations = method["accessible_locations"]
        
        if "all_storage" in accessible_locations:
            return True
        
        return any(location.startswith(accessible_loc) for accessible_loc in accessible_locations)
    
    def _extract_log_file(self, log_file: Dict, method: Dict) -> Dict[str, Any]:
        """개별 로그 파일 추출"""
        extraction_time = self._calculate_extraction_time(log_file["size_mb"], method)
        
        return {
            **log_file,
            "extraction_method": method["method"],
            "extraction_time_seconds": extraction_time,
            "extraction_timestamp": datetime.now().isoformat(),
            "integrity_verified": random.choice([True, False]),
            "encryption_status": self._check_encryption_status(log_file),
            "exfiltration_size_mb": log_file["size_mb"] * random.uniform(0.9, 1.0),  # 압축 고려
            "exfiltration_success": True,
            "data_corruption": random.random() < 0.05  # 5% 손상 확률
        }
    
    def _calculate_extraction_time(self, size_mb: float, method: Dict) -> float:
        """추출 시간 계산"""
        # 접근 방법별 전송 속도 (MB/s)
        transfer_speeds = {
            "ftp_exploitation": random.uniform(2, 8),
            "ssh_key_theft": random.uniform(5, 15),
            "sd_card_physical_access": random.uniform(20, 50),
            "web_interface_exploitation": random.uniform(1, 5),
            "mavlink_file_request": random.uniform(0.5, 2),
            "usb_autorun_exploitation": random.uniform(10, 30)
        }
        
        speed = transfer_speeds.get(method["method"], 5.0)
        base_time = size_mb / speed
        
        # 네트워크 지연 및 처리 오버헤드 추가
        overhead_factor = random.uniform(1.2, 2.5)
        
        return base_time * overhead_factor
    
    def _check_encryption_status(self, log_file: Dict) -> Dict[str, Any]:
        """로그 파일 암호화 상태 확인"""
        # 민감도에 따른 암호화 확률
        encryption_probability = {
            "critical": 0.7,
            "high": 0.5,
            "medium": 0.3,
            "low": 0.1
        }
        
        is_encrypted = random.random() < encryption_probability.get(log_file["sensitivity"], 0.3)
        
        if is_encrypted:
            return {
                "encrypted": True,
                "encryption_type": random.choice(["AES-256", "GPG", "LUKS", "dm-crypt"]),
                "key_strength": random.choice(["weak", "medium", "strong"]),
                "decryption_attempts": random.randint(0, 5),
                "decryption_success": random.choice([True, False])
            }
        else:
            return {
                "encrypted": False,
                "plaintext_accessible": True
            }
    
    def _analyze_intelligence_value(self, extracted_logs: List[Dict]) -> Dict[str, Any]:
        """정보 가치 분석"""
        if not extracted_logs:
            return {"intelligence_value": "none"}
        
        # 정보 유형별 분류
        intelligence_categories = {
            "operational_intelligence": [],
            "technical_intelligence": [],
            "tactical_intelligence": [],
            "strategic_intelligence": []
        }
        
        for log in extracted_logs:
            content_types = log.get("contains", [])
            
            if any(keyword in content_types for keyword in ["gps_coordinates", "waypoint_data", "mission_progress"]):
                intelligence_categories["operational_intelligence"].append(log)
            
            if any(keyword in content_types for keyword in ["sensor_readings", "system_events", "network_events"]):
                intelligence_categories["technical_intelligence"].append(log)
            
            if any(keyword in content_types for keyword in ["control_inputs", "operator_actions", "emergency_procedures"]):
                intelligence_categories["tactical_intelligence"].append(log)
            
            if any(keyword in content_types for keyword in ["decision_records", "mission_planning", "parameter_changes"]):
                intelligence_categories["strategic_intelligence"].append(log)
        
        # 정보 가치 점수 계산
        total_size = sum([log["size_mb"] for log in extracted_logs])
        critical_logs = len([log for log in extracted_logs if log["sensitivity"] == "critical"])
        high_value_logs = len([log for log in extracted_logs if log["sensitivity"] in ["critical", "high"]])
        
        value_score = min(100, (high_value_logs * 20) + (total_size * 0.5) + (critical_logs * 30))
        
        return {
            "intelligence_value": "high" if value_score > 70 else "medium" if value_score > 40 else "low",
            "value_score": value_score,
            "intelligence_categories": intelligence_categories,
            "total_data_size_mb": total_size,
            "critical_information_count": critical_logs,
            "actionable_intelligence": self._identify_actionable_intelligence(extracted_logs),
            "intelligence_timeline": self._create_intelligence_timeline(extracted_logs)
        }
    
    def _identify_actionable_intelligence(self, logs: List[Dict]) -> List[Dict[str, Any]]:
        """실행 가능한 정보 식별"""
        actionable_items = []
        
        for log in logs:
            content_types = log.get("contains", [])
            
            if "gps_coordinates" in content_types:
                actionable_items.append({
                    "type": "location_intelligence",
                    "description": "Flight paths and sensitive locations",
                    "operational_use": "route_planning_and_surveillance",
                    "security_impact": "high"
                })
            
            if "operator_actions" in content_types:
                actionable_items.append({
                    "type": "behavioral_intelligence",
                    "description": "Operator patterns and procedures",
                    "operational_use": "social_engineering_and_prediction",
                    "security_impact": "medium"
                })
            
            if "parameter_changes" in content_types:
                actionable_items.append({
                    "type": "configuration_intelligence",
                    "description": "System configuration and vulnerabilities",
                    "operational_use": "exploit_development",
                    "security_impact": "high"
                })
            
            if "network_events" in content_types:
                actionable_items.append({
                    "type": "network_intelligence",
                    "description": "Communication patterns and protocols",
                    "operational_use": "traffic_analysis_and_interception",
                    "security_impact": "medium"
                })
        
        return actionable_items
    
    def _create_intelligence_timeline(self, logs: List[Dict]) -> Dict[str, Any]:
        """정보 타임라인 생성"""
        now = datetime.now()
        timeline_events = []
        
        for log in logs:
            retention_days = log.get("retention_days", 30)
            oldest_data = now - timedelta(days=retention_days)
            
            timeline_events.append({
                "log_file": log["filename"],
                "data_timespan": f"{oldest_data.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
                "retention_period": f"{retention_days} days",
                "intelligence_freshness": "current" if retention_days <= 7 else "recent" if retention_days <= 30 else "historical"
            })
        
        return {
            "timeline_events": timeline_events,
            "total_timespan_days": max([log.get("retention_days", 0) for log in logs]),
            "freshness_analysis": self._analyze_data_freshness(logs)
        }
    
    def _analyze_data_freshness(self, logs: List[Dict]) -> Dict[str, Any]:
        """데이터 신선도 분석"""
        current_data = len([log for log in logs if log.get("retention_days", 0) <= 7])
        recent_data = len([log for log in logs if 7 < log.get("retention_days", 0) <= 30])
        historical_data = len([log for log in logs if log.get("retention_days", 0) > 30])
        
        return {
            "current_intelligence": current_data,
            "recent_intelligence": recent_data,
            "historical_intelligence": historical_data,
            "intelligence_relevance": "high" if current_data > 0 else "medium" if recent_data > 0 else "low"
        }
    
    def _assess_operational_security_impact(self, logs: List[Dict]) -> Dict[str, Any]:
        """작전 보안 영향 평가"""
        if not logs:
            return {"opsec_impact": "none"}
        
        # 노출된 정보 유형별 보안 영향
        exposed_elements = {
            "flight_routes": False,
            "operator_identities": False,
            "communication_protocols": False,
            "security_procedures": False,
            "technical_specifications": False,
            "mission_details": False
        }
        
        for log in logs:
            content_types = log.get("contains", [])
            
            if any(item in content_types for item in ["gps_coordinates", "waypoint_data"]):
                exposed_elements["flight_routes"] = True
            
            if any(item in content_types for item in ["operator_actions", "user_logins", "decision_records"]):
                exposed_elements["operator_identities"] = True
            
            if any(item in content_types for item in ["mavlink_messages", "network_events"]):
                exposed_elements["communication_protocols"] = True
            
            if any(item in content_types for item in ["emergency_procedures", "failsafe_events"]):
                exposed_elements["security_procedures"] = True
            
            if any(item in content_types for item in ["sensor_readings", "parameter_changes"]):
                exposed_elements["technical_specifications"] = True
            
            if any(item in content_types for item in ["mission_progress", "mission_planning"]):
                exposed_elements["mission_details"] = True
        
        # 전체 보안 영향 계산
        exposure_count = sum(exposed_elements.values())
        critical_exposures = [k for k, v in exposed_elements.items() if v and k in ["operator_identities", "security_procedures", "mission_details"]]
        
        if len(critical_exposures) > 1:
            impact_level = "critical"
        elif exposure_count > 3:
            impact_level = "high"
        elif exposure_count > 1:
            impact_level = "medium"
        else:
            impact_level = "low"
        
        return {
            "opsec_impact_level": impact_level,
            "exposed_elements": exposed_elements,
            "critical_exposures": critical_exposures,
            "compromise_assessment": self._assess_compromise_level(exposed_elements),
            "mitigation_urgency": "immediate" if impact_level == "critical" else "high" if impact_level == "high" else "normal"
        }
    
    def _assess_compromise_level(self, exposed: Dict[str, bool]) -> Dict[str, Any]:
        """타협 수준 평가"""
        compromise_indicators = {
            "mission_compromise": exposed["flight_routes"] and exposed["mission_details"],
            "personnel_compromise": exposed["operator_identities"],
            "technical_compromise": exposed["communication_protocols"] and exposed["technical_specifications"],
            "operational_compromise": exposed["security_procedures"] and exposed["mission_details"]
        }
        
        active_compromises = [k for k, v in compromise_indicators.items() if v]
        
        return {
            "compromise_indicators": compromise_indicators,
            "active_compromises": active_compromises,
            "overall_compromise_level": "severe" if len(active_compromises) > 2 else "moderate" if len(active_compromises) > 0 else "minimal"
        }
    
    def _analyze_forensic_traces(self, method: Dict, logs: List[Dict]) -> Dict[str, Any]:
        """포렌식 흔적 분석"""
        traces = {
            "access_logs": [],
            "file_system_traces": [],
            "network_traces": [],
            "temporal_traces": []
        }
        
        # 접근 방법별 흔적
        if method["method"] in ["ftp_exploitation", "ssh_key_theft"]:
            traces["access_logs"].extend([
                "authentication_logs",
                "connection_timestamps", 
                "session_duration_records"
            ])
            traces["network_traces"].extend([
                "source_ip_addresses",
                "connection_patterns",
                "data_transfer_volumes"
            ])
        
        if method["method"] == "sd_card_physical_access":
            traces["file_system_traces"].extend([
                "access_time_modifications",
                "file_copy_artifacts",
                "removable_media_logs"
            ])
        
        # 추출된 파일별 흔적
        for log in logs:
            traces["file_system_traces"].append(f"accessed_file:{log['filename']}")
            traces["temporal_traces"].append(f"extraction_time:{log['extraction_timestamp']}")
        
        return {
            "forensic_traces": traces,
            "evidence_retention_time": self._calculate_evidence_retention(),
            "attribution_difficulty": method["stealth_level"],
            "detection_timeline": self._estimate_detection_timeline(method, len(logs))
        }
    
    def _calculate_evidence_retention(self) -> Dict[str, str]:
        """증거 보관 시간 계산"""
        return {
            "system_logs": "30-90 days",
            "access_logs": "180 days",
            "network_logs": "7-30 days",
            "file_system_metadata": "until_overwritten",
            "backup_systems": "1-12 months"
        }
    
    def _estimate_detection_timeline(self, method: Dict, log_count: int) -> Dict[str, Any]:
        """탐지 타임라인 추정"""
        base_detection_time = {
            "high": random.uniform(0.5, 4),    # hours
            "medium": random.uniform(4, 24),   # hours  
            "low": random.uniform(24, 168)     # hours
        }[method["stealth_level"]]
        
        # 추출된 로그 수에 따른 조정
        if log_count > 5:
            base_detection_time *= 0.5  # 더 빠른 탐지
        elif log_count > 10:
            base_detection_time *= 0.3
        
        return {
            "estimated_detection_time_hours": base_detection_time,
            "detection_probability_24h": min(0.9, 0.1 + (log_count * 0.05)),
            "detection_probability_7d": min(0.95, 0.3 + (log_count * 0.03))
        }
    
    def _get_exfiltration_channels(self) -> List[Dict[str, Any]]:
        """데이터 유출 채널"""
        return [
            {
                "channel": "encrypted_tunnel",
                "description": "SSH/VPN encrypted data transfer",
                "stealth": "high",
                "bandwidth": "medium"
            },
            {
                "channel": "dns_tunneling", 
                "description": "Data exfiltration via DNS queries",
                "stealth": "very_high",
                "bandwidth": "low"
            },
            {
                "channel": "steganography",
                "description": "Data hidden in image/video files",
                "stealth": "very_high", 
                "bandwidth": "low"
            },
            {
                "channel": "cloud_storage",
                "description": "Upload to compromised cloud accounts",
                "stealth": "medium",
                "bandwidth": "high"
            },
            {
                "channel": "removable_media",
                "description": "Physical USB/SD card transfer",
                "stealth": "low",
                "bandwidth": "very_high"
            }
        ]
    
    def _get_persistence_mechanisms(self) -> List[Dict[str, Any]]:
        """지속성 메커니즘"""
        return [
            {
                "mechanism": "scheduled_extraction",
                "description": "Cron jobs for periodic log harvesting",
                "detection_difficulty": "medium"
            },
            {
                "mechanism": "log_rotation_hijacking",
                "description": "Intercept logs during rotation process",
                "detection_difficulty": "high"
            },
            {
                "mechanism": "real_time_monitoring",
                "description": "Monitor and exfiltrate logs as they're written",
                "detection_difficulty": "low"
            },
            {
                "mechanism": "backup_interception", 
                "description": "Compromise backup processes",
                "detection_difficulty": "medium"
            }
        ]
    
    def _generate_extraction_iocs(self, logs: List[Dict], method: Dict) -> List[str]:
        """로그 추출 IOC 생성"""
        iocs = []
        
        # 접근 방법 관련 IOC
        iocs.extend([
            f"LOG_EXTRACTION_METHOD:{method['method']}",
            f"ACCESS_METHOD_STEALTH:{method['stealth_level']}"
        ])
        
        # 추출된 파일 관련 IOC
        for log in logs:
            iocs.extend([
                f"LOG_FILE_EXTRACTED:{log['filename']}",
                f"LOG_TYPE_STOLEN:{log['type']}",
                f"DATA_SENSITIVITY:{log['sensitivity']}",
                f"EXTRACTION_SIZE_MB:{log['exfiltration_size_mb']:.1f}"
            ])
            
            # 중요한 로그의 경우 특별 IOC
            if log["sensitivity"] in ["critical", "high"]:
                iocs.append(f"SENSITIVE_LOG_COMPROMISED:{log['filename']}")
            
            # 암호화된 데이터 처리
            encryption_status = log.get("encryption_status", {})
            if encryption_status.get("encrypted") and encryption_status.get("decryption_success"):
                iocs.append(f"ENCRYPTED_LOG_DECRYPTED:{log['filename']}")
        
        # 전체 공격 규모 IOC
        total_size = sum([log["exfiltration_size_mb"] for log in logs])
        iocs.extend([
            f"TOTAL_DATA_EXFILTRATED_MB:{total_size:.1f}",
            f"LOG_FILES_COMPROMISED_COUNT:{len(logs)}"
        ])
        
        if total_size > 100:  # 100MB 이상
            iocs.append("LARGE_SCALE_DATA_THEFT")
        
        if len([log for log in logs if log["sensitivity"] == "critical"]) > 0:
            iocs.append("CRITICAL_INTELLIGENCE_COMPROMISED")
        
        return iocs