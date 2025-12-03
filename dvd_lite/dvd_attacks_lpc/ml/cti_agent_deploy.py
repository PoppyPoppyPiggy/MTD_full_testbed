#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI Agent Deploy (Fixed & Complete Version)
============================================
실시간 로그 모니터링 → ML 추론 → 공격 탐지 → MTD 방어 실행

수정 사항:
1. 공격명 정규화 함수 추가 (data_builder.py와 동기화)
2. 피처 추출 로직 data_builder.py와 완전 일치
3. RL v08 모드 HTTP 서버 연동 활성화
4. mtd_state.json 업데이트 로직 추가
5. IptablesMTDController 통합
"""

import os
import sys
import time
import json
import joblib
import logging
import threading
import requests
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# --- 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [CTI-Agent] %(message)s"
)
logger = logging.getLogger("CTIAgent")

# --- 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
BUS_DIR = os.path.join(PROJECT_ROOT, "bus")
MTD_DIR = os.path.join(PROJECT_ROOT, "mtd")
MTD_SHARED_STATE_DIR = os.path.join(MTD_DIR, "shared_state")

# 모델 및 설정 파일 경로
MODEL_PATH = os.path.join(BASE_DIR, "output", "cti_classifier_model.joblib")
FEATURES_PATH = os.path.join(BASE_DIR, "output", "training_features.json")
EVENT_MAPPING_PATH = os.path.join(BASE_DIR, "event_mapping.json")

# MTD 상태 파일 경로
MTD_STATE_FILE = os.path.join(MTD_SHARED_STATE_DIR, "mtd_state.json")
CTI_ALERT_FILE = os.path.join(MTD_SHARED_STATE_DIR, "cti_alert.json")

# --- 방어 모드 설정 ---
DEFENSE_MODE = os.environ.get("CTI_DEFENSE_MODE", "none").lower()

# RL v08 서버 설정
RL_V08_SERVER_HOST = os.environ.get("RL_V08_SERVER_HOST", "127.0.0.1")
RL_V08_SERVER_PORT = int(os.environ.get("RL_V08_SERVER_PORT", "8888"))

# --- iptables MTD Controller ---
IptablesMTDController = None
try:
    sys.path.insert(0, MTD_DIR)
    from iptables_mtd_controller_v08 import IptablesMTDController
    logger.info("✓ IptablesMTDController v08 로드 성공")
except ImportError:
    try:
        from iptables_mtd_controller import IptablesMTDController
        logger.info("✓ IptablesMTDController 로드 성공")
    except ImportError as e:
        logger.warning(f"⚠ IptablesMTDController 로드 실패: {e}")

# --- 모니터링할 로그 파일 ---
TARGET_LOGS = {
    "network": os.path.join(BUS_DIR, "bus_network.log"),
    "telemetry": os.path.join(BUS_DIR, "bus_telemetry.log"),
    "qos": os.path.join(BUS_DIR, "bus_qos.log"),
    "container": os.path.join(BUS_DIR, "bus_container_telemetry.log"),
    "system": os.path.join(BUS_DIR, "bus_system_events.log")
}

# --- 설정 상수 ---
DETECTION_INTERVAL = 1.0
CONFIDENCE_THRESHOLD = 0.7
DEFENSE_COOLDOWN_SEC = 30

# --- 공격 심각도 매핑 ---
ATTACK_SEVERITY_MAP = {
    # Reconnaissance (Level 1)
    "wifi-analysis-_-cracking": 1,
    "drone-discovery": 1,
    "companion-computer-discovery": 1,
    "ground-control-station-discovery": 1,
    "drone-gps-_-telemetry-detection": 1,
    
    # Tampering - Basic (Level 2)
    "attitude-spoofing": 2,
    "battery-spoofing": 2,
    "vfr-hud-spoofing": 2,
    
    # GPS/Navigation (Level 3)
    "gps-spoofing": 3,
    "gps-data-injection": 3,
    "gps-offset-glitching": 3,
    "satellite-spoofing": 3,
    
    # DoS (Level 3)
    "wifi-deauth-attack": 3,
    "communication-link-flooding": 3,
    "geofencing-attack": 3,
    
    # Injection - Critical (Level 4)
    "waypoint-injection": 4,
    "return-to-home-point-override": 4,
    "camera-gimbal-takeover": 4,
    "ground-control-station-spoofing": 4,
    "critical-error-spoofing": 4,
    "emergency-status-spoofing": 4,
    
    # Denial / Termination (Level 5)
    "flight-termination": 5,
    "denial-of-takeoff": 5,
    
    # Exfiltration (Level 2)
    "wifi-client-data-leak": 2,
    "flight-log-extraction": 2,
    "mission-extraction": 2,
}


# =============================================================================
# 공격명 정규화 함수 (data_builder.py와 동일)
# =============================================================================

def normalize_attack_name(name: str) -> str:
    """공격명 정규화"""
    if not name:
        return name
    if name.endswith('.sh'):
        name = name[:-3]
    return name.strip()


def get_attack_name_variants(name: str) -> List[str]:
    """공격명의 가능한 변형들 반환"""
    variants = [name]
    if '-_-' in name:
        variants.append(name.replace('-_-', '-'))
    else:
        parts = name.split('-')
        for i in range(1, len(parts)):
            variant = '-'.join(parts[:i]) + '-_-' + '-'.join(parts[i:])
            variants.append(variant)
    return variants


# =============================================================================
# 실시간 로그 리더
# =============================================================================

class RealTimeLogReader(threading.Thread):
    """로그 파일 실시간 읽기 스레드"""
    
    def __init__(self, filepath: str, log_type: str, data_queue: deque):
        super().__init__()
        self.filepath = filepath
        self.log_type = log_type
        self.data_queue = data_queue
        self.running = True
        self.daemon = True

    def run(self):
        while self.running and not os.path.exists(self.filepath):
            time.sleep(1)
        if not self.running:
            return
            
        logger.info(f"[*] 모니터링 시작: {os.path.basename(self.filepath)}")

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                f.seek(0, os.SEEK_END)
                while self.running:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    try:
                        data = json.loads(line.strip())
                        data['_log_source'] = self.log_type
                        self.data_queue.append(data)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.error(f"Reader error ({self.log_type}): {e}")

    def stop(self):
        self.running = False


# =============================================================================
# CTI Agent
# =============================================================================

class CTIAgent:
    """CTI 기반 공격 탐지 및 방어 에이전트"""
    
    def __init__(self):
        self.model = None
        self.label_encoder = None
        self.id_to_name: Dict[int, str] = {}
        self.name_to_id: Dict[str, int] = {}
        self.feature_names: List[str] = []
        
        self.data_buffer = deque(maxlen=1000)
        self.running = True
        self.defense_cooldown = 0.0
        
        self.mtd_controller = None
        
        self.stats = {
            "logs_processed": 0,
            "attacks_detected": 0,
            "defenses_triggered": 0,
            "start_time": time.time()
        }

        self._load_event_mapping()
        self._load_model()
        self._init_mtd_controller()
        self._ensure_dirs()
        
        logger.info(f"✅ CTI Agent 초기화 완료 (DEFENSE_MODE={DEFENSE_MODE})")

    def _ensure_dirs(self):
        os.makedirs(MTD_SHARED_STATE_DIR, exist_ok=True)

    def _load_event_mapping(self):
        try:
            if os.path.exists(EVENT_MAPPING_PATH):
                with open(EVENT_MAPPING_PATH, 'r', encoding='utf-8') as f:
                    self.name_to_id = json.load(f)
                    self.id_to_name = {v: k for k, v in self.name_to_id.items()}
                logger.info(f"✓ Event mapping 로드: {len(self.name_to_id)} 항목")
        except Exception as e:
            logger.error(f"Event mapping 로드 실패: {e}")

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            logger.critical(f"❌ 모델 파일 없음: {MODEL_PATH}")
            sys.exit(1)

        try:
            artifact = joblib.load(MODEL_PATH)
            if isinstance(artifact, dict):
                self.model = artifact['model']
                self.label_encoder = artifact.get('encoder')
                if artifact.get('mapping'):
                    self.id_to_name.update(artifact['mapping'])
            else:
                self.model = artifact

            if os.path.exists(FEATURES_PATH):
                with open(FEATURES_PATH, 'r') as f:
                    self.feature_names = json.load(f).get('features', [])
            elif hasattr(self.model, 'feature_names_in_'):
                self.feature_names = list(self.model.feature_names_in_)
            
            logger.info(f"✅ 모델 로드 완료 ({len(self.feature_names)} features)")
        except Exception as e:
            logger.critical(f"❌ 모델 로드 실패: {e}")
            sys.exit(1)

    def _init_mtd_controller(self):
        if DEFENSE_MODE != "cti_rule":
            return
        if IptablesMTDController is None:
            logger.error("❌ cti_rule 모드인데 IptablesMTDController 없음")
            return
        try:
            state_file = os.path.join(MTD_SHARED_STATE_DIR, "controller_state.json")
            self.mtd_controller = IptablesMTDController(
                dry_run=True,
                state_file=state_file
            )
            logger.info("✓ MTD Controller 초기화 완료")
        except Exception as e:
            logger.error(f"MTD Controller 초기화 실패: {e}")

    # =========================================================================
    # 피처 추출 (data_builder.py와 동일)
    # =========================================================================
    def preprocess_log_to_features(self, log_entry: Dict[str, Any]) -> pd.DataFrame:
        """로그 → 피처 벡터 변환"""
        features = {feat: 0.0 for feat in self.feature_names}
        
        source = log_entry.get("_log_source", "unknown")
        data = log_entry.get("data", {}) or {}

        # ---- network_traffic_monitor ----
        if source == "network":
            features["pkt_length"] = float(data.get("length", 0) or 0)
            features["pkt_src_port"] = float(data.get("src_port", 0) or 0)
            features["pkt_dst_port"] = float(data.get("dst_port", 0) or 0)
            
            protocol = str(data.get("protocol", "")).upper()
            features["is_wifi_mgmt"] = 1.0 if protocol in ("802.11", "WIFI", "WLAN") else 0.0
            features["is_deauth"] = 1.0 if data.get("subtype") == "deauth" else 0.0
            features["is_disassoc"] = 1.0 if data.get("subtype") == "disassoc" else 0.0
            
            dst_port = features["pkt_dst_port"]
            features["is_mavlink_port"] = 1.0 if dst_port in (5760, 14550, 14551) else 0.0
            features["is_web_port"] = 1.0 if dst_port in (80, 443, 3000, 8080) else 0.0
            features["is_ftp_port"] = 1.0 if dst_port in (20, 21) else 0.0
            features["is_ssh_port"] = 1.0 if dst_port == 22 else 0.0

        # ---- dvd_telemetry_monitor ----
        elif source == "telemetry":
            features["lat"] = float(data.get("lat", 0) or 0)
            features["lon"] = float(data.get("lon", 0) or 0)
            features["alt_m"] = float(data.get("alt_m", 0) or 0)
            features["relative_alt_m"] = float(data.get("relative_alt_m", 0) or 0)
            features["vx"] = float(data.get("vx", 0) or 0)
            features["vy"] = float(data.get("vy", 0) or 0)
            features["vz"] = float(data.get("vz", 0) or 0)
            features["pitch_deg"] = float(data.get("pitch_deg", 0) or 0)
            features["roll_deg"] = float(data.get("roll_deg", 0) or 0)
            features["yaw_deg"] = float(data.get("yaw_deg", 0) or 0)
            features["groundspeed_ms"] = float(data.get("groundspeed_ms", 0) or 0)
            features["battery_v"] = float(data.get("battery_v", 0) or 0)
            features["battery_pct"] = float(data.get("battery_pct", 0) or 0)
            
            mode = str(data.get("mode", "")).upper()
            features["mode_is_guided"] = 1.0 if "GUIDED" in mode else 0.0
            features["mode_is_auto"] = 1.0 if "AUTO" in mode else 0.0
            features["mode_is_rtl"] = 1.0 if "RTL" in mode else 0.0
            features["mode_is_stabilize"] = 1.0 if "STABILIZE" in mode else 0.0

        # ---- dvd_container_monitor ----
        elif source == "container":
            features["cpu_load_pct"] = float(data.get("cpu_load_pct", 0) or 0)
            features["memory_pct"] = float(data.get("memory_pct", 0) or 0)
            features["net_rx_bytes"] = float(data.get("network_rx_bytes", 0) or 0)
            features["net_tx_bytes"] = float(data.get("network_tx_bytes", 0) or 0)
            features["disk_read_bytes"] = float(data.get("disk_read_bytes", 0) or 0)
            features["disk_write_bytes"] = float(data.get("disk_write_bytes", 0) or 0)
            features["container_running"] = 1.0 if data.get("running") else 0.0
            
            c_name = str(data.get("container_name", "")).lower()
            features["is_gcs_container"] = 1.0 if "ground-control" in c_name else 0.0
            features["is_fc_container"] = 1.0 if "flight-controller" in c_name else 0.0

        # ---- qos_monitor ----
        elif source == "qos":
            features["avg_rtt_ms"] = float(data.get("avg_rtt_ms", 0) or 0)
            features["packet_loss_pct"] = float(data.get("packet_loss_pct", 0) or 0)
            features["cpu_load_pct"] = float(data.get("cpu_load_pct", 0) or 0)
            
            cumulative = data.get("system_resources_cumulative") or {}
            features["mem_percent"] = float(cumulative.get("memory_percent", 0) or 0)
            
            rates = data.get("system_resources_rates") or {}
            features["disk_read_bps"] = float(rates.get("disk_read_bps", 0) or 0)
            features["disk_write_bps"] = float(rates.get("disk_write_bps", 0) or 0)
            features["net_sent_bps"] = float(rates.get("net_sent_bps", 0) or 0)
            features["net_recv_bps"] = float(rates.get("net_recv_bps", 0) or 0)

        # ---- docker_event_monitor ----
        elif source == "system":
            status = str(data.get("status", "")).lower()
            features["is_exec_start"] = 1.0 if status == "exec_start" else 0.0
            features["is_copy"] = 1.0 if "copy" in status or "archive" in status else 0.0
            features["is_die"] = 1.0 if status == "die" else 0.0

        # DataFrame 생성
        df = pd.DataFrame([features])
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0.0
        
        return df[self.feature_names]

    # =========================================================================
    # 공격명 조회 (정규화 포함)
    # =========================================================================
    def _get_attack_name(self, label_id: int) -> str:
        """라벨 ID → 공격명"""
        name = self.id_to_name.get(label_id)
        if name:
            return name
        return f"Unknown-{label_id}"
    
    def _get_severity(self, attack_name: str) -> int:
        """공격명 → 심각도 (변형 검색 포함)"""
        normalized = normalize_attack_name(attack_name)
        
        if normalized in ATTACK_SEVERITY_MAP:
            return ATTACK_SEVERITY_MAP[normalized]
        
        for variant in get_attack_name_variants(normalized):
            if variant in ATTACK_SEVERITY_MAP:
                return ATTACK_SEVERITY_MAP[variant]
        
        return 2  # 기본값

    # =========================================================================
    # 방어 실행
    # =========================================================================
    def execute_defense(self, attack_label: int, attack_name: str, confidence: float):
        """공격 탐지 시 방어 실행"""
        current_time = time.time()
        
        if current_time < self.defense_cooldown:
            return

        self.stats["defenses_triggered"] += 1
        severity = self._get_severity(attack_name)
        
        logger.warning(f"🚨 [ALERT] 공격 탐지!")
        logger.warning(f"   Type: {attack_name} (ID: {attack_label})")
        logger.warning(f"   Confidence: {confidence:.3f}, Severity: Level {severity}")

        mtd_strategy = self._determine_strategy(attack_name)

        if DEFENSE_MODE == "none":
            logger.info("🔍 [MODE=none] 탐지만 수행")
            self._write_alert(attack_name, attack_label, confidence, severity)
            
        elif DEFENSE_MODE == "cti_rule":
            self._execute_cti_rule(attack_name, mtd_strategy, severity)
            self.defense_cooldown = current_time + DEFENSE_COOLDOWN_SEC
            
        elif DEFENSE_MODE == "rl_v08":
            self._execute_rl_v08(attack_name, attack_label, severity, confidence)
            self.defense_cooldown = current_time + DEFENSE_COOLDOWN_SEC

    def _determine_strategy(self, attack_name: str) -> str:
        """공격 유형별 MTD 전략"""
        lower = attack_name.lower()
        if "gps" in lower or "satellite" in lower:
            return "ip_shuffle"
        elif "flood" in lower or "deauth" in lower:
            return "service_swap"
        elif "discovery" in lower or "scan" in lower:
            return "port_shuffle"
        elif "injection" in lower or "takeover" in lower:
            return "full_shuffle"
        elif "exfil" in lower or "extraction" in lower or "leak" in lower:
            return "decoy_activate"
        return "random"

    def _execute_cti_rule(self, attack_name: str, strategy: str, severity: int):
        """규칙 기반 MTD"""
        if not self.mtd_controller:
            logger.error("❌ MTD Controller 없음")
            return
        
        logger.info(f"⚔️ [CTI_RULE] {strategy}, severity={severity}")
        
        try:
            intensity = min(0.3 + (severity * 0.15), 1.0)
            
            if strategy in ("ip_shuffle", "full_shuffle"):
                self.mtd_controller.shuffle_network("fc_mavlink", intensity=intensity)
                self.mtd_controller.shuffle_network("gcs_mavlink", intensity=intensity)
            if strategy in ("port_shuffle", "full_shuffle"):
                self.mtd_controller.port_hop("cc_mavlink", intensity=intensity)
            if strategy in ("service_swap", "decoy_activate", "full_shuffle"):
                self.mtd_controller.activate_decoy("fc_mavlink")

            self._update_mtd_state(strategy, severity)
            logger.info("✅ MTD 실행 완료")
        except Exception as e:
            logger.error(f"❌ MTD 실행 실패: {e}")

    def _execute_rl_v08(self, attack_name: str, label: int, severity: int, confidence: float):
        """RL v08 서버 연동"""
        logger.info(f"⚔️ [RL_V08] HTTP 요청: {RL_V08_SERVER_HOST}:{RL_V08_SERVER_PORT}")
        
        alert_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attack_name": attack_name,
            "attack_label": label,
            "severity": severity,
            "confidence": confidence,
        }

        try:
            url = f"http://{RL_V08_SERVER_HOST}:{RL_V08_SERVER_PORT}/cti_alert"
            response = requests.post(url, json=alert_data, timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ [RL_V08] 응답: {response.json()}")
            else:
                logger.warning(f"⚠ [RL_V08] 응답 오류: {response.status_code}")
                self._write_alert(attack_name, label, confidence, severity)
        except requests.exceptions.ConnectionError:
            logger.warning("⚠ [RL_V08] 연결 실패 - 파일 fallback")
            self._write_alert(attack_name, label, confidence, severity)
        except Exception as e:
            logger.error(f"❌ [RL_V08] 오류: {e}")

    def _write_alert(self, attack_name: str, label: int, confidence: float, severity: int):
        """CTI 알림 파일 저장"""
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attack_name": attack_name,
            "attack_label": label,
            "confidence": confidence,
            "severity": severity,
        }
        try:
            with open(CTI_ALERT_FILE, 'w') as f:
                json.dump(alert, f, indent=2)
        except Exception as e:
            logger.error(f"Alert 저장 실패: {e}")

    def _update_mtd_state(self, strategy: str, severity: int):
        """MTD 상태 업데이트"""
        try:
            state = {}
            if os.path.exists(MTD_STATE_FILE):
                with open(MTD_STATE_FILE, 'r') as f:
                    state = json.load(f)
            
            state["last_update"] = datetime.now(timezone.utc).isoformat()
            state["last_strategy"] = strategy
            state["last_severity"] = severity
            state["defense_count"] = state.get("defense_count", 0) + 1
            
            with open(MTD_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"MTD 상태 업데이트 실패: {e}")

    # =========================================================================
    # 메인 루프
    # =========================================================================
    def run(self):
        logger.info("🚀 CTI Agent 시작")

        readers = []
        for name, path in TARGET_LOGS.items():
            reader = RealTimeLogReader(path, name, self.data_buffer)
            reader.start()
            readers.append(reader)

        try:
            while self.running:
                if not self.data_buffer:
                    time.sleep(0.1)
                    continue

                while self.data_buffer and self.running:
                    log_entry = self.data_buffer.popleft()
                    self.stats["logs_processed"] += 1

                    try:
                        X_input = self.preprocess_log_to_features(log_entry)
                        pred_prob = self.model.predict_proba(X_input)[0]
                        pred_idx = int(np.argmax(pred_prob))
                        confidence = float(pred_prob[pred_idx])

                        if self.label_encoder:
                            pred_label_id = int(self.label_encoder.inverse_transform([pred_idx])[0])
                        else:
                            pred_label_id = pred_idx

                        attack_name = self._get_attack_name(pred_label_id)

                        if attack_name.lower() not in ('normal', 'unknown-0') and \
                           confidence > CONFIDENCE_THRESHOLD:
                            self.stats["attacks_detected"] += 1
                            self.execute_defense(pred_label_id, attack_name, confidence)

                    except Exception as e:
                        logger.debug(f"추론 오류: {e}")

                time.sleep(DETECTION_INTERVAL)

        except KeyboardInterrupt:
            logger.info("\n🛑 종료")
        finally:
            self.running = False
            for r in readers:
                r.stop()
            self._print_stats()

    def _print_stats(self):
        elapsed = time.time() - self.stats["start_time"]
        logger.info("=" * 50)
        logger.info(f"📊 실행 통계")
        logger.info(f"   시간: {elapsed:.1f}초")
        logger.info(f"   로그: {self.stats['logs_processed']:,}")
        logger.info(f"   탐지: {self.stats['attacks_detected']}")
        logger.info(f"   방어: {self.stats['defenses_triggered']}")
        logger.info("=" * 50)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["none", "cti_rule", "rl_v08"])
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD)
    args = parser.parse_args()

    global DEFENSE_MODE, CONFIDENCE_THRESHOLD
    if args.mode:
        DEFENSE_MODE = args.mode
    CONFIDENCE_THRESHOLD = args.threshold

    agent = CTIAgent()
    agent.run()


if __name__ == "__main__":
    main()














