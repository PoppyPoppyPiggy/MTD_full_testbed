#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI Agent v2.0 (Paper-Ready)
=============================
CTI 분류기 추론 모듈 - 로그 → 공격 분류
"""

import os
import json
import joblib
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CTIAgent")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "output", "cti_classifier_model.joblib")
FEATURES_PATH = os.path.join(BASE_DIR, "output", "training_features.json")
EVENT_MAPPING_PATH = os.path.join(BASE_DIR, "event_mapping.json")
TACTIC_MAPPING_PATH = os.path.join(BASE_DIR, "tactic_mapping.json")


class CTIClassifier:
    """CTI 공격 분류기"""
    
    def __init__(
        self,
        model_path: str = MODEL_PATH,
        use_tactic_labels: bool = False,
        confidence_threshold: float = 0.7
    ):
        self.model = None
        self.label_encoder = None
        self.feature_names: List[str] = []
        self.id_to_name: Dict[int, str] = {}
        self.tactic_names: Dict[int, str] = {}
        self.use_tactic_labels = use_tactic_labels
        self.confidence_threshold = confidence_threshold
        
        self._load_model(model_path)
        self._load_mappings()
        
        logger.info(f"✅ CTI Classifier 초기화 완료 ({len(self.feature_names)} features)")

    def _load_model(self, model_path: str):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"모델 파일 없음: {model_path}")
        
        artifact = joblib.load(model_path)
        
        if isinstance(artifact, dict):
            self.model = artifact['model']
            self.label_encoder = artifact.get('encoder')
            if artifact.get('features'):
                self.feature_names = artifact['features']
            if artifact.get('mapping'):
                self.id_to_name.update(artifact['mapping'])
        else:
            self.model = artifact
        
        if not self.feature_names and os.path.exists(FEATURES_PATH):
            with open(FEATURES_PATH, 'r') as f:
                self.feature_names = json.load(f).get('features', [])
        
        if not self.feature_names and hasattr(self.model, 'feature_names_in_'):
            self.feature_names = list(self.model.feature_names_in_)

    def _load_mappings(self):
        try:
            if os.path.exists(EVENT_MAPPING_PATH):
                with open(EVENT_MAPPING_PATH, 'r', encoding='utf-8') as f:
                    name_to_id = json.load(f)
                    self.id_to_name = {v: k for k, v in name_to_id.items()}
        except Exception as e:
            logger.warning(f"Event mapping 로드 실패: {e}")

        try:
            if os.path.exists(TACTIC_MAPPING_PATH):
                with open(TACTIC_MAPPING_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tactic_names = {int(k): v for k, v in data.get('tactic_names', {}).items()}
        except Exception as e:
            logger.warning(f"Tactic mapping 로드 실패: {e}")

    def preprocess(self, log_entry: Dict[str, Any]) -> pd.DataFrame:
        """로그 엔트리 → 피처 벡터"""
        features = {feat: 0.0 for feat in self.feature_names}
        
        source = log_entry.get("_log_source") or log_entry.get("source", "unknown")
        data = log_entry.get("data", {}) or {}

        if source in ("network", "network_traffic_monitor"):
            features["pkt_length"] = float(data.get("length", 0) or 0)
            features["pkt_src_port"] = float(data.get("src_port", 0) or 0)
            features["pkt_dst_port"] = float(data.get("dst_port", 0) or 0)
            
            protocol = str(data.get("protocol", "")).upper()
            features["is_wifi_mgmt"] = 1.0 if protocol in ("802.11", "WIFI", "WLAN") else 0.0
            features["is_deauth"] = 1.0 if data.get("subtype") == "deauth" else 0.0
            
            dst_port = features["pkt_dst_port"]
            features["is_mavlink_port"] = 1.0 if dst_port in (5760, 14550, 14551) else 0.0
            features["is_web_port"] = 1.0 if dst_port in (80, 443, 3000, 8080) else 0.0
            features["is_ftp_port"] = 1.0 if dst_port in (20, 21) else 0.0
            features["is_ssh_port"] = 1.0 if dst_port == 22 else 0.0

        elif source in ("telemetry", "dvd_telemetry_monitor"):
            for key in ["lat", "lon", "alt_m", "relative_alt_m", "vx", "vy", "vz",
                       "pitch_deg", "roll_deg", "yaw_deg", "groundspeed_ms",
                       "battery_v", "battery_pct"]:
                if key in self.feature_names:
                    features[key] = float(data.get(key, 0) or 0)
            
            mode = str(data.get("mode", "")).upper()
            features["mode_is_guided"] = 1.0 if "GUIDED" in mode else 0.0
            features["mode_is_auto"] = 1.0 if "AUTO" in mode else 0.0
            features["mode_is_rtl"] = 1.0 if "RTL" in mode else 0.0

        elif source in ("container", "dvd_container_monitor"):
            features["cpu_load_pct"] = float(data.get("cpu_load_pct", 0) or 0)
            features["memory_pct"] = float(data.get("memory_pct", 0) or 0)
            features["net_rx_bytes"] = float(data.get("network_rx_bytes", 0) or 0)
            features["net_tx_bytes"] = float(data.get("network_tx_bytes", 0) or 0)
            features["container_running"] = 1.0 if data.get("running") else 0.0

        elif source in ("qos", "qos_monitor"):
            features["avg_rtt_ms"] = float(data.get("avg_rtt_ms", 0) or 0)
            features["packet_loss_pct"] = float(data.get("packet_loss_pct", 0) or 0)

        elif source in ("system", "docker_event_monitor"):
            status = str(data.get("status", "")).lower()
            features["is_exec_start"] = 1.0 if status == "exec_start" else 0.0
            features["is_copy"] = 1.0 if "copy" in status else 0.0
            features["is_die"] = 1.0 if status == "die" else 0.0

        df = pd.DataFrame([features])
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0.0
        
        return df[self.feature_names]

    def predict(self, log_entry: Dict[str, Any]) -> Tuple[int, float, str]:
        """
        로그 엔트리 분류
        
        Returns:
            (label_id, confidence, attack_name)
        """
        X = self.preprocess(log_entry)
        
        pred_prob = self.model.predict_proba(X)[0]
        pred_idx = int(np.argmax(pred_prob))
        confidence = float(pred_prob[pred_idx])
        
        if self.label_encoder:
            label_id = int(self.label_encoder.inverse_transform([pred_idx])[0])
        else:
            label_id = pred_idx
        
        if self.use_tactic_labels:
            attack_name = self.tactic_names.get(label_id, f"Tactic-{label_id}")
        else:
            attack_name = self.id_to_name.get(label_id, f"Unknown-{label_id}")
        
        return label_id, confidence, attack_name

    def is_attack(self, log_entry: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        공격 여부 판단
        
        Returns:
            (is_attack, details)
        """
        label_id, confidence, attack_name = self.predict(log_entry)
        
        is_attack = (label_id != 0) and (confidence >= self.confidence_threshold)
        
        details = {
            "label_id": label_id,
            "confidence": confidence,
            "attack_name": attack_name,
            "is_attack": is_attack,
            "threshold": self.confidence_threshold
        }
        
        return is_attack, details


def demo():
    """데모 실행"""
    print("=" * 60)
    print("CTI Classifier Demo")
    print("=" * 60)
    
    try:
        classifier = CTIClassifier()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("   먼저 train_classifier.py를 실행하세요.")
        return
    
    # 테스트 로그들
    test_logs = [
        {"_log_source": "network", "data": {"length": 100, "dst_port": 14550, "protocol": "UDP"}},
        {"_log_source": "network", "data": {"length": 50, "subtype": "deauth", "protocol": "802.11"}},
        {"_log_source": "telemetry", "data": {"lat": 37.5, "lon": 127.0, "alt_m": 50, "mode": "AUTO"}},
        {"_log_source": "container", "data": {"cpu_load_pct": 90, "memory_pct": 85, "running": True}},
    ]
    
    print("\n[테스트 결과]")
    for i, log in enumerate(test_logs):
        is_attack, details = classifier.is_attack(log)
        status = "🚨 ATTACK" if is_attack else "✅ Normal"
        print(f"\n  Log {i+1}: {log.get('_log_source')}")
        print(f"    {status} - {details['attack_name']} ({details['confidence']:.2%})")


if __name__ == "__main__":
    demo()
