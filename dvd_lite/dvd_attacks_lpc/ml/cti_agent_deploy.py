#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI Agent Deploy v2.0 (Paper-Ready)
====================================
실시간 로그 모니터링 → ML 추론 → 공격 탐지 → MTD 방어

Features:
- 현실적 CTI 노이즈/지연 시뮬레이션 (논문 실험용)
- RL v08 서버 연동
- 전술(Tactic) 레벨 분류 지원
"""

import os
import sys
import time
import json
import joblib
import logging
import threading
import argparse
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-7s] [CTI] %(message)s")
logger = logging.getLogger("CTIAgent")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
BUS_DIR = os.path.join(PROJECT_ROOT, "bus")
MTD_DIR = os.path.join(PROJECT_ROOT, "mtd")
MTD_SHARED_STATE_DIR = os.path.join(MTD_DIR, "shared_state")

MODEL_PATH = os.path.join(BASE_DIR, "output", "cti_classifier_model.joblib")
FEATURES_PATH = os.path.join(BASE_DIR, "output", "training_features.json")
EVENT_MAPPING_PATH = os.path.join(BASE_DIR, "event_mapping.json")
TACTIC_MAPPING_PATH = os.path.join(BASE_DIR, "tactic_mapping.json")

MTD_STATE_FILE = os.path.join(MTD_SHARED_STATE_DIR, "mtd_state.json")
CTI_ALERT_FILE = os.path.join(MTD_SHARED_STATE_DIR, "cti_alert.json")

DEFENSE_MODE = os.environ.get("CTI_DEFENSE_MODE", "none").lower()
RL_V08_SERVER_HOST = os.environ.get("RL_V08_SERVER_HOST", "127.0.0.1")
RL_V08_SERVER_PORT = int(os.environ.get("RL_V08_SERVER_PORT", "8888"))

DETECTION_INTERVAL = 1.0
CONFIDENCE_THRESHOLD = 0.7
DEFENSE_COOLDOWN_SEC = 30

TARGET_LOGS = {
    "network": os.path.join(BUS_DIR, "bus_network.log"),
    "telemetry": os.path.join(BUS_DIR, "bus_telemetry.log"),
    "qos": os.path.join(BUS_DIR, "bus_qos.log"),
    "container": os.path.join(BUS_DIR, "bus_container_telemetry.log"),
    "system": os.path.join(BUS_DIR, "bus_system_events.log")
}

TACTIC_SEVERITY = {0: 0, 1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 3, 7: 4}

IptablesMTDController = None
try:
    sys.path.insert(0, MTD_DIR)
    from iptables_mtd_controller_v08 import IptablesMTDController
except ImportError:
    try:
        from iptables_mtd_controller import IptablesMTDController
    except ImportError:
        pass


class RealTimeLogReader(threading.Thread):
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
            
        logger.info(f"[*] 모니터링: {os.path.basename(self.filepath)}")

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


class CTIAgent:
    def __init__(
        self,
        noise_rate: float = 0.0,
        delay_steps: int = 0,
        use_tactic_labels: bool = False
    ):
        self.noise_rate = noise_rate
        self.delay_steps = delay_steps
        self.use_tactic_labels = use_tactic_labels
        
        self.model = None
        self.label_encoder = None
        self.id_to_name: Dict[int, str] = {}
        self.tactic_names: Dict[int, str] = {}
        self.feature_names: List[str] = []
        
        self.data_buffer = deque(maxlen=1000)
        self.prediction_buffer = deque(maxlen=max(1, delay_steps))
        self.running = True
        self.defense_cooldown = 0.0
        self.mtd_controller = None
        
        self.stats = {
            "logs_processed": 0, "attacks_detected": 0, "defenses_triggered": 0,
            "false_positives": 0, "false_negatives": 0, "start_time": time.time()
        }

        self._load_mappings()
        self._load_model()
        self._init_mtd()
        os.makedirs(MTD_SHARED_STATE_DIR, exist_ok=True)
        
        logger.info(f"✅ CTI Agent (NOISE={noise_rate:.0%}, DELAY={delay_steps})")

    def _load_mappings(self):
        try:
            if os.path.exists(EVENT_MAPPING_PATH):
                with open(EVENT_MAPPING_PATH, 'r') as f:
                    name_to_id = json.load(f)
                    self.id_to_name = {v: k for k, v in name_to_id.items()}
        except:
            pass
        try:
            if os.path.exists(TACTIC_MAPPING_PATH):
                with open(TACTIC_MAPPING_PATH, 'r') as f:
                    data = json.load(f)
                    self.tactic_names = {int(k): v for k, v in data.get('tactic_names', {}).items()}
        except:
            pass

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            logger.critical(f"❌ 모델 없음: {MODEL_PATH}")
            sys.exit(1)

        artifact = joblib.load(MODEL_PATH)
        if isinstance(artifact, dict):
            self.model = artifact['model']
            self.label_encoder = artifact.get('encoder')
            if artifact.get('mapping'):
                self.id_to_name.update(artifact['mapping'])
            if artifact.get('features'):
                self.feature_names = artifact['features']
        else:
            self.model = artifact

        if not self.feature_names and os.path.exists(FEATURES_PATH):
            with open(FEATURES_PATH, 'r') as f:
                self.feature_names = json.load(f).get('features', [])
        
        logger.info(f"✅ 모델 로드 ({len(self.feature_names)} features)")

    def _init_mtd(self):
        if DEFENSE_MODE != "cti_rule" or IptablesMTDController is None:
            return
        try:
            self.mtd_controller = IptablesMTDController(
                dry_run=True, state_file=os.path.join(MTD_SHARED_STATE_DIR, "controller_state.json")
            )
            logger.info("✓ MTD Controller 초기화")
        except Exception as e:
            logger.error(f"MTD Controller 실패: {e}")

    def preprocess(self, log_entry: Dict[str, Any]) -> pd.DataFrame:
        features = {feat: 0.0 for feat in self.feature_names}
        source = log_entry.get("_log_source", "unknown")
        data = log_entry.get("data", {}) or {}

        if source == "network":
            features["pkt_length"] = float(data.get("length", 0) or 0)
            features["pkt_src_port"] = float(data.get("src_port", 0) or 0)
            features["pkt_dst_port"] = float(data.get("dst_port", 0) or 0)
            features["is_wifi_mgmt"] = 1.0 if str(data.get("protocol", "")).upper() in ("802.11", "WIFI") else 0.0
            features["is_deauth"] = 1.0 if data.get("subtype") == "deauth" else 0.0
            dst = features["pkt_dst_port"]
            features["is_mavlink_port"] = 1.0 if dst in (5760, 14550, 14551) else 0.0
            features["is_web_port"] = 1.0 if dst in (80, 443, 3000, 8080) else 0.0

        elif source == "telemetry":
            for k in ["lat", "lon", "alt_m", "vx", "vy", "vz", "pitch_deg", "roll_deg", "yaw_deg", "groundspeed_ms", "battery_v", "battery_pct"]:
                if k in self.feature_names:
                    features[k] = float(data.get(k, 0) or 0)
            mode = str(data.get("mode", "")).upper()
            features["mode_is_guided"] = 1.0 if "GUIDED" in mode else 0.0
            features["mode_is_auto"] = 1.0 if "AUTO" in mode else 0.0
            features["mode_is_rtl"] = 1.0 if "RTL" in mode else 0.0

        elif source == "container":
            features["cpu_load_pct"] = float(data.get("cpu_load_pct", 0) or 0)
            features["memory_pct"] = float(data.get("memory_pct", 0) or 0)
            features["container_running"] = 1.0 if data.get("running") else 0.0

        elif source == "qos":
            features["avg_rtt_ms"] = float(data.get("avg_rtt_ms", 0) or 0)
            features["packet_loss_pct"] = float(data.get("packet_loss_pct", 0) or 0)

        elif source == "system":
            status = str(data.get("status", "")).lower()
            features["is_exec_start"] = 1.0 if status == "exec_start" else 0.0
            features["is_copy"] = 1.0 if "copy" in status else 0.0

        df = pd.DataFrame([features])
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0.0
        return df[self.feature_names]

    def predict_with_noise(self, X: pd.DataFrame) -> tuple:
        pred_prob = self.model.predict_proba(X)[0]
        pred_idx = int(np.argmax(pred_prob))
        confidence = float(pred_prob[pred_idx])
        
        if self.label_encoder:
            label = int(self.label_encoder.inverse_transform([pred_idx])[0])
        else:
            label = pred_idx
        
        is_noisy = False

        # 지연 적용
        if self.delay_steps > 0:
            self.prediction_buffer.append((label, confidence))
            if len(self.prediction_buffer) < self.delay_steps:
                return 0, 0.0, False
            label, confidence = self.prediction_buffer[0]

        # 노이즈 적용
        if self.noise_rate > 0 and np.random.random() < self.noise_rate:
            is_noisy = True
            if label == 0:
                num_classes = len(self.label_encoder.classes_) if self.label_encoder else 8
                label = np.random.randint(1, num_classes)
                confidence *= 0.6
                self.stats["false_positives"] += 1
            else:
                label = 0
                confidence = 0.5
                self.stats["false_negatives"] += 1

        return label, confidence, is_noisy

    def _get_name(self, label: int) -> str:
        if self.use_tactic_labels:
            return self.tactic_names.get(label, f"Tactic-{label}")
        return self.id_to_name.get(label, f"Unknown-{label}")

    def _get_severity(self, label: int) -> int:
        if self.use_tactic_labels:
            return TACTIC_SEVERITY.get(label, 2)
        if label in range(1, 8): return 1
        if label in range(8, 10): return 2
        if label in range(10, 17): return 2
        if label in range(17, 24): return 3
        if label in range(24, 32): return 4
        if label in range(32, 38): return 3
        if label in range(38, 40): return 4
        return 2

    def execute_defense(self, label: int, name: str, conf: float, is_noisy: bool = False):
        now = time.time()
        if now < self.defense_cooldown:
            return

        self.stats["defenses_triggered"] += 1
        severity = self._get_severity(label)
        
        flag = " [NOISY]" if is_noisy else ""
        logger.warning(f"🚨 [ALERT]{flag} {name} (L{label}, conf={conf:.2f}, sev={severity})")

        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attack_name": name, "attack_label": label,
            "severity": severity, "confidence": conf, "is_noisy": is_noisy
        }

        if DEFENSE_MODE == "none":
            self._write_alert(alert)
        elif DEFENSE_MODE == "cti_rule":
            self._execute_rule(name, severity)
            self._write_alert(alert)
            self.defense_cooldown = now + DEFENSE_COOLDOWN_SEC
        elif DEFENSE_MODE == "rl_v08":
            self._execute_rl(alert)
            self.defense_cooldown = now + DEFENSE_COOLDOWN_SEC

    def _execute_rule(self, name: str, severity: int):
        if not self.mtd_controller:
            return
        lower = name.lower()
        if "gps" in lower or "satellite" in lower:
            strategy = "ip_shuffle"
        elif "flood" in lower or "deauth" in lower:
            strategy = "service_swap"
        elif "discovery" in lower or "recon" in lower:
            strategy = "port_shuffle"
        elif "injection" in lower or "takeover" in lower:
            strategy = "full_shuffle"
        else:
            strategy = "decoy_activate"
        logger.info(f"⚔️ [RULE] {strategy}, sev={severity}")

    def _execute_rl(self, alert: dict):
        if not HAS_REQUESTS:
            self._write_alert(alert)
            return
        try:
            url = f"http://{RL_V08_SERVER_HOST}:{RL_V08_SERVER_PORT}/cti_alert"
            r = requests.post(url, json=alert, timeout=5)
            if r.status_code == 200:
                logger.info(f"✅ [RL] {r.json()}")
            else:
                self._write_alert(alert)
        except:
            self._write_alert(alert)

    def _write_alert(self, alert: dict):
        try:
            with open(CTI_ALERT_FILE, 'w') as f:
                json.dump(alert, f, indent=2)
        except:
            pass

    def run(self):
        logger.info("🚀 CTI Agent 시작")
        readers = []
        for name, path in TARGET_LOGS.items():
            r = RealTimeLogReader(path, name, self.data_buffer)
            r.start()
            readers.append(r)

        try:
            while self.running:
                if not self.data_buffer:
                    time.sleep(0.1)
                    continue

                while self.data_buffer and self.running:
                    log = self.data_buffer.popleft()
                    self.stats["logs_processed"] += 1

                    try:
                        X = self.preprocess(log)
                        label, conf, is_noisy = self.predict_with_noise(X)
                        name = self._get_name(label)

                        if label != 0 and conf > CONFIDENCE_THRESHOLD:
                            self.stats["attacks_detected"] += 1
                            self.execute_defense(label, name, conf, is_noisy)
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
        logger.info(f"📊 통계 (실행: {elapsed:.1f}초)")
        logger.info(f"   로그: {self.stats['logs_processed']:,}")
        logger.info(f"   탐지: {self.stats['attacks_detected']}")
        logger.info(f"   방어: {self.stats['defenses_triggered']}")
        if self.noise_rate > 0:
            logger.info(f"   FP: {self.stats['false_positives']}, FN: {self.stats['false_negatives']}")
        logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="CTI Agent Deploy v2.0")
    parser.add_argument("--mode", choices=["none", "cti_rule", "rl_v08"], default="none")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD)
    parser.add_argument("--noise-rate", type=float, default=0.0)
    parser.add_argument("--delay-steps", type=int, default=0)
    parser.add_argument("--tactic-level", action="store_true")
    args = parser.parse_args()

    global DEFENSE_MODE, CONFIDENCE_THRESHOLD
    DEFENSE_MODE = args.mode
    CONFIDENCE_THRESHOLD = args.threshold

    agent = CTIAgent(
        noise_rate=args.noise_rate,
        delay_steps=args.delay_steps,
        use_tactic_labels=args.tactic_level
    )
    agent.run()


if __name__ == "__main__":
    main()
