#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 디렉토리: dvd_lite/dvd_attacks_lpc/ml
# 파일명: data_builder.py
# 설명: bus 로그(들)를 읽어 피처를 생성하고 CSV로 저장 (Full Logic + Feature Engineering)
#       - [NEW] 공격 특화 피처 엔지니어링 추가 (WiFi, Injection, Exfil 탐지용)

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
import numpy as np 

# 경고 메시지 제어
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
        files = set()
        
        # 1. 단일 파일 지정 시
        if self.bus_log_path and os.path.isfile(self.bus_log_path):
            files.add(self.bus_log_path)
            if not self.bus_log_dir:
                derived_dir = os.path.dirname(self.bus_log_path)
                if os.path.isdir(derived_dir):
                    logger.info(f"Auto-detecting sibling logs in directory: {derived_dir}")
                    self.bus_log_dir = derived_dir

        # 2. 디렉토리 지정 검색
        if self.bus_log_dir and os.path.isdir(self.bus_log_dir):
            patterns = [
                os.path.join(self.bus_log_dir, "bus.log"),
                os.path.join(self.bus_log_dir, "bus_*.log")
            ]
            for pattern in patterns:
                found = glob.glob(pattern)
                for fpath in found:
                    files.add(fpath)
                        
        file_list = list(files)
        if not file_list:
            logger.warning(f"No log files found in path: {self.bus_log_path} or dir: {self.bus_log_dir}")
        else:
            logger.info(f"Collected {len(file_list)} log files:")
            for f in sorted(file_list):
                logger.info(f"  - {os.path.basename(f)}")
            
        return file_list

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
                            # 타임스탬프 표준화
                            if 'ts' not in entry:
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

        logger.info(f"Sorting {len(all_logs)} log entries...")
        all_logs.sort(key=lambda x: x.get('ts', 0.0))
        return all_logs

    def iter_bus_logs(self) -> Generator[Dict[str, Any], None, None]:
        files = self._collect_log_files()
        if not files:
            return
        sorted_logs = self._read_and_sort_logs(files)
        for entry in sorted_logs:
            yield entry

    def extract_features(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        하나의 bus 로그 엔트리에서 상세 ML용 feature를 추출한다.
        [NEW] 공격 특화 피처 추가
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
            # 기본 네트워크 피처
            features["pkt_length"] = float(data.get("length", 0))
            features["pkt_src_port"] = float(data.get("src_port", 0))
            features["pkt_dst_port"] = float(data.get("dst_port", 0))
            
            # [NEW] 공격 특화 피처
            # 1. WiFi Deauth 탐지 (802.11, deauth subtype)
            features["is_wifi_mgmt"] = 1 if data.get("protocol") in ("802.11", "WiFi", "WLAN") else 0
            features["is_deauth"] = 1 if data.get("subtype") == "deauth" else 0
            features["is_disassoc"] = 1 if data.get("subtype") == "disassoc" else 0
            
            # 2. 주요 서비스 포트 접근 여부 (Scan/Dos 탐지)
            dst_port = features["pkt_dst_port"]
            features["is_mavlink_port"] = 1 if dst_port in (5760, 14550, 14551) else 0
            features["is_web_port"] = 1 if dst_port in (80, 443, 3000, 8080) else 0
            features["is_ftp_port"] = 1 if dst_port in (20, 21) else 0
            features["is_ssh_port"] = 1 if dst_port == 22 else 0

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
            })
            
            # [NEW] Waypoint Injection / Mode Change 탐지
            mode = str(data.get("mode", "")).upper()
            features["mode_is_guided"] = 1 if "GUIDED" in mode else 0
            features["mode_is_auto"] = 1 if "AUTO" in mode else 0
            features["mode_is_rtl"] = 1 if "RTL" in mode else 0
            features["mode_is_stabilize"] = 1 if "STABILIZE" in mode else 0

        # ---- dvd_container_monitor ----
        elif source == "dvd_container_monitor":
            features.update({
                "cpu_load_pct": data.get("cpu_load_pct"),
                "memory_pct": data.get("memory_pct"),
                "net_rx_bytes": data.get("network_rx_bytes"),
                "net_tx_bytes": data.get("network_tx_bytes"),
                "disk_read_bytes": data.get("disk_read_bytes"),
                "disk_write_bytes": data.get("disk_write_bytes"),
                "container_running": data.get("running"),
            })
            # 컨테이너 이름 식별 (One-hot 대용)
            c_name = str(data.get("container_name", "")).lower()
            features["is_gcs_container"] = 1 if "ground-control" in c_name else 0
            features["is_fc_container"] = 1 if "flight-controller" in c_name else 0

        # ---- qos_monitor ----
        elif source == "qos_monitor":
            features.update({
                "avg_rtt_ms": data.get("avg_rtt_ms"),
                "packet_loss_pct": data.get("packet_loss_pct"),
                "cpu_load_pct": data.get("cpu_load_pct"),
                "mem_percent": (data.get("system_resources_cumulative") or {}).get("memory_percent"),
                "disk_read_bps": (data.get("system_resources_rates") or {}).get("disk_read_bps"),
                "disk_write_bps": (data.get("system_resources_rates") or {}).get("disk_write_bps"),
                "net_sent_bps": (data.get("system_resources_rates") or {}).get("net_sent_bps"),
                "net_recv_bps": (data.get("system_resources_rates") or {}).get("net_recv_bps"),
            })

        # ---- docker_event_monitor ----
        elif source == "docker_event_monitor":
            status = str(data.get("status", "")).lower()
            features["docker_health"] = data.get("health_status")
            
            # [NEW] Exfiltration 탐지 (파일 접근/복사/실행)
            features["is_exec_start"] = 1 if status == "exec_start" else 0
            features["is_copy"] = 1 if "copy" in status or "archive" in status else 0
            features["is_die"] = 1 if status == "die" else 0

        return features

    def process_logs_batch(self) -> Optional[pd.DataFrame]:
        records = []
        current_attack_name: Optional[str] = None
        current_label: int = 0

        logger.info("Starting batch processing...")

        for log_entry in self.iter_bus_logs():
            source = log_entry.get("source")
            log_type = log_entry.get("type") or log_entry.get("event_type")
            data = log_entry.get("data", {}) or {}

            # --- 1) 상태머신: 공격 시작/종료 ---
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
            
            features["ts"] = log_entry.get("ts")
            features["timestamp"] = log_entry.get("timestamp")

            records.append(features)

        if not records:
            logger.warning("No records found in log files.")
            return None

        df = pd.DataFrame.from_records(records)

        # -------------------------------------------------------------
        # [CRITICAL FIX] 데이터 Sanitizing (DtypeWarning 해결)
        # -------------------------------------------------------------
        logger.info("Sanitizing dataframe (converting non-numeric to NaN/0)...")
        
        # 1. 제외할 컬럼 (문자열로 유지해야 하는 메타 데이터)
        exclude_cols = ["source", "log_type", "attack_name", "scenario", "runner_event", 
                        "timestamp", "current_attack_name", "container_name", 
                        "pkt_proto", "pkt_tcp_flags", "pkt_arp_op", "mode", 
                        "docker_status", "docker_name", "docker_health", "ping_target"]
        
        # 2. 수치형 후보 컬럼 식별
        numeric_cols = [c for c in df.columns if c not in exclude_cols]
        
        # 3. 강제 형변환
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # 4. NaN 및 Inf 처리 -> 0으로 채움
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.fillna(0, inplace=True)
        # -------------------------------------------------------------

        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"features_batch_{ts_str}.csv")
        
        try:
            df.to_csv(output_path, index=False)
            logger.info(f"Batch feature data saved: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save CSV: {e}")

        if "label" in df.columns:
            logger.info("--- Label Distribution ---")
            logger.info(df["label"].value_counts(normalize=False).sort_index())
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

    log_file = args.log_file
    log_dir = args.log_dir
    
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