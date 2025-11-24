#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: dvd_lite/dvd_attacks_lpc/ml/data_builder.py
설 명: bus 로그(들)를 읽어 피처를 생성하고 CSV로 저장 (Full Logic Version)
      - 단일 파일 또는 디렉토리 내 모든 bus 로그 처리 지원
      - 타임스탬프 기준 자동 정렬 기능 포함
"""

import os
import sys
import json
import time
import logging
import argparse
import glob
from datetime import datetime
from typing import Any, Dict, List, Optional, Generator

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
DEFAULT_BUS_DIR = os.path.abspath(os.path.join(BASE_DIR, "../bus"))
DEFAULT_BUS_LOG_PATH = os.path.join(DEFAULT_BUS_DIR, "bus.log")
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, "./processed_data"))
DEFAULT_MAPPING_FILE = os.path.abspath(os.path.join(BASE_DIR, "event_mapping.json"))

class DataBuilder:
    def __init__(
        self,
        bus_log_path: Optional[str] = None,
        bus_log_dir: Optional[str] = None,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        mapping_file: str = DEFAULT_MAPPING_FILE
    ):
        self.bus_log_path = bus_log_path
        self.bus_log_dir = bus_log_dir
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

    def _collect_log_files(self) -> List[str]:
        """처리할 로그 파일 목록을 수집합니다."""
        files = []
        
        # 1. 단일 파일 지정 시
        if self.bus_log_path and os.path.isfile(self.bus_log_path):
            files.append(self.bus_log_path)
        
        # 2. 디렉토리 지정 시 (bus_*.log 패턴 검색)
        if self.bus_log_dir and os.path.isdir(self.bus_log_dir):
            patterns = [
                os.path.join(self.bus_log_dir, "bus.log"),
                os.path.join(self.bus_log_dir, "bus_*.log")
            ]
            for pattern in patterns:
                for fpath in glob.glob(pattern):
                    if fpath not in files:
                        files.append(fpath)
        
        if not files:
            logger.warning("No log files found to process.")
            
        return files

    def _read_and_sort_logs(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """여러 로그 파일을 읽어서 타임스탬프 순으로 정렬하여 반환합니다."""
        all_logs = []
        logger.info(f"Reading logs from {len(file_paths)} files...")
        
        for fpath in file_paths:
            try:
                logger.debug(f"Reading file: {fpath}")
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            entry = json.loads(line)
                            # ts 필드 확보 (없으면 0.0)
                            if 'ts' not in entry:
                                # timestamp 문자열 파싱 시도 (ISO format)
                                ts_str = entry.get('timestamp')
                                if ts_str:
                                    try:
                                        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                                        entry['ts'] = dt.timestamp()
                                    except:
                                        entry['ts'] = 0.0
                                else:
                                    entry['ts'] = 0.0
                            all_logs.append(entry)
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.error(f"Error reading file {fpath}: {e}")

        # 타임스탬프 기준 정렬
        logger.info(f"Sorting {len(all_logs)} log entries...")
        all_logs.sort(key=lambda x: x.get('ts', 0.0))
        return all_logs

    def iter_bus_logs(self) -> Generator[Dict[str, Any], None, None]:
        """수집된 모든 로그를 시간 순서대로 yield합니다."""
        files = self._collect_log_files()
        if not files:
            return

        # 메모리에 모두 올려서 정렬하는 방식 (데이터가 아주 크지 않다면 가장 정확함)
        # 대용량 데이터의 경우 외부 정렬이나 merge sort 방식이 필요할 수 있음
        sorted_logs = self._read_and_sort_logs(files)
        
        for entry in sorted_logs:
            yield entry

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
        수집된 로그 전체를 읽어서 feature + label 이 들어간 DataFrame을 만든다.
        상태머신을 통해 공격 구간에 라벨을 부여한다.
        """
        records = []
        current_attack_name: Optional[str] = None
        current_label: int = 0  # 0 = normal

        logger.info("Starting batch processing...")

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
                    # logger.debug(f"Attack started: {attack_name} (Label: {current_label})")
                elif log_type == "attack_stopped":
                    current_label = 0
                    current_attack_name = None
                    # logger.debug("Attack stopped.")

            # --- 2) feature 추출 ---
            features = self.extract_features(log_entry)
            features["label"] = current_label
            features["current_attack_name"] = current_attack_name
            
            # timestamp 유지
            features["ts"] = log_entry.get("ts")
            features["timestamp"] = log_entry.get("timestamp")

            records.append(features)

        if not records:
            logger.warning("No records found in log files.")
            return None

        df = pd.DataFrame.from_records(records)

        # NaN / inf 정리
        df.replace([float("inf"), float("-inf")], float("nan"), inplace=True)
        
        # FutureWarning 방지: fillna 호출 시 downcasting 동작 명시
        df.fillna(0, inplace=True)

        # 출력 경로 저장
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"features_batch_{ts_str}.csv")
        
        try:
            df.to_csv(output_path, index=False)
            logger.info(f"Batch feature data saved: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save CSV: {e}")

        # Label 분포 로깅
        if "label" in df.columns:
            logger.info("--- Label Distribution ---")
            logger.info(df["label"].value_counts(normalize=False).sort_index()) # 개수로 표시
            logger.info("--------------------------")

        return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build features from bus logs")
    parser.add_argument("--mode", choices=["batch"], default="batch")
    parser.add_argument("--log-file", help="Path to a single log file")
    parser.add_argument("--log-dir", help="Path to directory containing log files")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mapping-file", default=DEFAULT_MAPPING_FILE)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 인자 처리 우선순위: log-file > log-dir > default (DEFAULT_BUS_LOG_PATH)
    log_file = args.log_file
    log_dir = args.log_dir
    
    # 아무것도 지정 안되면 기본 경로 사용 (단일 파일 모드)
    if not log_file and not log_dir:
        log_file = DEFAULT_BUS_LOG_PATH

    builder = DataBuilder(
        bus_log_path=log_file,
        bus_log_dir=log_dir,
        output_dir=args.output_dir,
        mapping_file=args.mapping_file
    )

    if args.mode == "batch":
        builder.process_logs_batch()