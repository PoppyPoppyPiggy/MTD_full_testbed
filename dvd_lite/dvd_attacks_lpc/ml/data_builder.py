#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: dvd_lite/dvd_attacks_lpc/ml/data_builder.py
설 명: bus.log를 배치로 읽어 피처를 생성하고 CSV로 저장 (Full Logic Version)
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

# 경고 메시지 제어 (FutureWarning 해결)
pd.set_option('future.no_silent_downcasting', True)

# ----------------------------
# 로깅 설정
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DataBuilder")

# ----------------------------
# 경로 기본값
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUS_LOG_PATH = os.path.abspath(os.path.join(BASE_DIR, "../bus/bus.log"))
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, "./processed_data"))
DEFAULT_MAPPING_FILE = os.path.abspath(os.path.join(BASE_DIR, "event_mapping.json"))

class DataBuilder:
    def __init__(
        self,
        bus_log_path: str = DEFAULT_BUS_LOG_PATH,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        mapping_file: str = DEFAULT_MAPPING_FILE
    ):
        self.bus_log_path = bus_log_path
        self.output_dir = output_dir
        self.event_mapping: Dict[str, int] = {}

        os.makedirs(self.output_dir, exist_ok=True)

        # 공격명 -> 정수 라벨 매핑 로드
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                self.event_mapping = json.load(f)
            logger.info(f"Loaded event mapping from {mapping_file}")
        except FileNotFoundError:
            logger.error(f"Event mapping file not found at {mapping_file}. Using empty mapping.")
        except Exception as e:
            logger.error(f"Error loading event mapping: {e}. Using empty mapping.")

    def iter_bus_logs(self):
        """bus.log 파일을 순차적으로 읽어 JSON dict 를 yield."""
        if not os.path.exists(self.bus_log_path):
            logger.warning(f"bus.log not found: {self.bus_log_path}")
            return

        with open(self.bus_log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Error parsing bus.log line: {e}")

    def extract_features(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        하나의 bus 로그 엔트리에서 상세 ML용 feature를 추출한다.
        (원본의 상세 로직 복원)
        """
        source = log_entry.get("source", "unknown")
        log_type = log_entry.get("type") or log_entry.get("event_type") or "unknown"
        data = log_entry.get("data", {}) or {}

        features: Dict[str, Any] = {
            "source": source,
            "log_type": log_type,
        }

        # ---- attack_orchestrator ----
        if source == "attack_orchestrator":
            features["attack_name"] = data.get("attack_name")
            features["scenario"] = data.get("scenario")

        # ---- scenario_runner ----
        elif source == "scenario_runner":
            features["attack_name"] = data.get("attack_name")
            features["scenario"] = data.get("scenario")
            features["runner_event"] = log_type

        # ---- network_traffic_monitor ----
        elif source == "network_traffic_monitor":
            if log_type in ("network_packet", "network_traffic_batch"):
                if isinstance(data, dict):
                    features.update({
                        "pkt_length": data.get("length"),
                        "pkt_proto": data.get("protocol"),
                        "pkt_src_port": data.get("src_port"),
                        "pkt_dst_port": data.get("dst_port"),
                        "pkt_tcp_flags": data.get("tcp_flags"),
                        "pkt_arp_op": data.get("arp_op"),
                    })
            else:
                features["pkt_length"] = data.get("length")
                features["pkt_proto"] = data.get("protocol")

        # ---- dvd_telemetry_monitor ----
        elif source == "dvd_telemetry_monitor":
            features.update({
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "alt_m": data.get("alt_m"),
                "relative_alt_m": data.get("relative_alt_m"),
                "vx": data.get("vx"),
                "vy": data.get("vy"),
                "vz": data.get("vz"),
                "pitch_deg": data.get("pitch_deg"),
                "roll_deg": data.get("roll_deg"),
                "yaw_deg": data.get("yaw_deg"),
                "groundspeed_ms": data.get("groundspeed_ms"),
                "battery_v": data.get("battery_v"),
                "battery_pct": data.get("battery_pct"),
                "mode": data.get("mode"),
            })

        # ---- dvd_container_monitor ----
        elif source == "dvd_container_monitor":
            features.update({
                "container_name": data.get("container_name"),
                "cpu_load_pct": data.get("cpu_load_pct"),
                "memory_pct": data.get("memory_pct"),
                "net_rx_bytes": data.get("network_rx_bytes"),
                "net_tx_bytes": data.get("network_tx_bytes"),
                "disk_read_bytes": data.get("disk_read_bytes"),
                "disk_write_bytes": data.get("disk_write_bytes"),
                "container_running": data.get("running"),
            })

        # ---- qos_monitor ----
        elif source == "qos_monitor":
            features.update({
                "avg_rtt_ms": data.get("avg_rtt_ms"),
                "packet_loss_pct": data.get("packet_loss_pct"),
                "ping_target": data.get("ping_target"),
                "cpu_load_pct": data.get("cpu_load_pct"),
                "mem_percent": (data.get("system_resources_cumulative") or {}).get("memory_percent"),
                "disk_read_bps": (data.get("system_resources_rates") or {}).get("disk_read_bps"),
                "disk_write_bps": (data.get("system_resources_rates") or {}).get("disk_write_bps"),
                "net_sent_bps": (data.get("system_resources_rates") or {}).get("net_sent_bps"),
                "net_recv_bps": (data.get("system_resources_rates") or {}).get("net_recv_bps"),
            })

        # ---- docker_event_monitor ----
        elif source == "docker_event_monitor":
            features.update({
                "docker_status": data.get("status"),
                "docker_name": data.get("name"),
                "docker_health": data.get("health_status"),
            })

        return features

    def process_logs_batch(self) -> Optional[pd.DataFrame]:
        """
        bus.log 전체를 읽어서 feature + label 이 들어간 DataFrame을 만든다.
        상태머신을 통해 공격 구간에 라벨을 부여한다.
        """
        records = []
        current_attack_name: Optional[str] = None
        current_label: int = 0  # 0 = normal

        logger.info(f"Starting batch processing of: {self.bus_log_path}")

        for log_entry in self.iter_bus_logs():
            source = log_entry.get("source")
            log_type = log_entry.get("type") or log_entry.get("event_type")
            data = log_entry.get("data", {}) or {}

            # --- 1) 상태머신: 공격 시작/종료 이벤트 처리 ---
            if source == "attack_orchestrator":
                attack_name = data.get("attack_name")
                if log_type == "attack_started" and attack_name:
                    current_label = self.event_mapping.get(attack_name, 0)
                    current_attack_name = attack_name
                elif log_type == "attack_stopped":
                    current_label = 0
                    current_attack_name = None

            # --- 2) feature 추출 ---
            features = self.extract_features(log_entry)
            features["label"] = current_label
            features["current_attack_name"] = current_attack_name
            
            # timestamp 유지
            features["ts"] = log_entry.get("ts")
            features["timestamp"] = log_entry.get("timestamp")

            records.append(features)

        if not records:
            logger.warning("bus.log 에서 레코드를 하나도 읽지 못했습니다.")
            return None

        df = pd.DataFrame.from_records(records)

        # NaN / inf 정리
        df.replace([float("inf"), float("-inf")], float("nan"), inplace=True)
        
        # [수정] FutureWarning 방지: fillna 호출 시 downcasting 동작 명시
        df.fillna(0, inplace=True)

        # 출력 경로 저장
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"features_batch_{ts_str}.csv")
        
        try:
            df.to_csv(output_path, index=False)
            logger.info(f"배치 feature 데이터 저장 완료: {output_path}")
        except Exception as e:
            logger.error(f"CSV 저장 실패: {e}")

        # Label 분포 로깅
        if "label" in df.columns:
            logger.info("--- Label Distribution ---")
            logger.info(df["label"].value_counts(normalize=True).sort_index())
            logger.info("--------------------------")

        return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build features from bus.log")
    parser.add_argument("--mode", choices=["batch"], default="batch")
    parser.add_argument("--log-file", default=DEFAULT_BUS_LOG_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mapping-file", default=DEFAULT_MAPPING_FILE)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    builder = DataBuilder(
        bus_log_path=args.log_file,
        output_dir=args.output_dir,
        mapping_file=args.mapping_file
    )

    if args.mode == "batch":
        builder.process_logs_batch()