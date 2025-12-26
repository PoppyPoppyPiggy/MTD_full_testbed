#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Builder v2.0 (Paper-Ready)
================================
DVD bus 로그 → ML 피처 CSV 변환

Features:
- 실제 공격 스크립트 파일명 기반 라벨링
- 전술(Tactic) 레벨 라벨 지원
- 공격 특화 피처 추출
"""

import os
import sys
import json
import logging
import argparse
import glob
from datetime import datetime
from typing import Any, Dict, List, Optional, Generator

import pandas as pd
import numpy as np

pd.set_option('future.no_silent_downcasting', True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DataBuilder")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUS_DIR = os.path.abspath(os.path.join(BASE_DIR, "../bus"))
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, "./processed_data"))
DEFAULT_MAPPING_FILE = os.path.abspath(os.path.join(BASE_DIR, "event_mapping.json"))
DEFAULT_TACTIC_FILE = os.path.abspath(os.path.join(BASE_DIR, "tactic_mapping.json"))


def normalize_attack_name(name: str) -> str:
    if not name:
        return name
    name = name.strip()
    if name.endswith('.sh'):
        name = name[:-3]
    return name


class DataBuilder:
    def __init__(
        self,
        bus_log_path: Optional[str] = None,
        bus_log_dir: Optional[str] = None,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        mapping_file: str = DEFAULT_MAPPING_FILE,
        tactic_file: str = DEFAULT_TACTIC_FILE,
        use_tactic_labels: bool = False
    ):
        self.bus_log_path = bus_log_path
        self.bus_log_dir = bus_log_dir
        self.output_dir = output_dir
        self.use_tactic_labels = use_tactic_labels
        
        self.event_mapping: Dict[str, int] = {}
        self.reverse_mapping: Dict[int, str] = {}
        self.tactic_mapping: Dict[int, int] = {}
        self.tactic_names: Dict[int, str] = {}

        os.makedirs(self.output_dir, exist_ok=True)

        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                self.event_mapping = json.load(f)
                self.reverse_mapping = {v: k for k, v in self.event_mapping.items()}
            logger.info(f"✓ Event mapping: {len(self.event_mapping)} 항목")
        except Exception as e:
            logger.error(f"❌ Event mapping 로드 실패: {e}")

        if use_tactic_labels and os.path.exists(tactic_file):
            try:
                with open(tactic_file, "r", encoding="utf-8") as f:
                    tactic_data = json.load(f)
                    self.tactic_mapping = {int(k): int(v) for k, v in tactic_data.get("attack_to_tactic", {}).items()}
                    self.tactic_names = {int(k): v for k, v in tactic_data.get("tactic_names", {}).items()}
                logger.info(f"✓ Tactic mapping: {len(self.tactic_names)} 전술")
            except Exception as e:
                logger.error(f"❌ Tactic mapping 로드 실패: {e}")

    def _get_label_for_attack(self, attack_name: str) -> int:
        if not attack_name:
            return 0
        normalized = normalize_attack_name(attack_name)
        if normalized in self.event_mapping:
            return self.event_mapping[normalized]
        for key, val in self.event_mapping.items():
            if key.lower() == normalized.lower():
                return val
        logger.warning(f"⚠ Unknown attack: {attack_name}")
        return 0

    def _get_tactic_label(self, attack_label: int) -> int:
        return self.tactic_mapping.get(attack_label, 0)

    def _collect_log_files(self) -> List[str]:
        files = set()
        if self.bus_log_path and os.path.isfile(self.bus_log_path):
            files.add(self.bus_log_path)
            if not self.bus_log_dir:
                self.bus_log_dir = os.path.dirname(self.bus_log_path)

        if self.bus_log_dir and os.path.isdir(self.bus_log_dir):
            for pattern in ["bus.log", "bus_*.log"]:
                for fpath in glob.glob(os.path.join(self.bus_log_dir, pattern)):
                    files.add(fpath)
                        
        file_list = list(files)
        if file_list:
            logger.info(f"✓ {len(file_list)} log files found")
        return file_list

    def _read_and_sort_logs(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        all_logs = []
        for fpath in file_paths:
            line_count = 0
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
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
                            line_count += 1
                        except json.JSONDecodeError:
                            pass
                logger.info(f"  {os.path.basename(fpath)}: {line_count:,} entries")
            except Exception as e:
                logger.error(f"Error reading {fpath}: {e}")

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
        source = log_entry.get("source", "unknown")
        log_type = log_entry.get("type") or log_entry.get("event_type") or "unknown"
        data = log_entry.get("data", {}) or {}

        features: Dict[str, Any] = {"source": source, "log_type": log_type}

        if source in ("attack_orchestrator", "scenario_runner"):
            features["attack_name"] = normalize_attack_name(data.get("attack_name"))
            features["scenario"] = data.get("scenario")

        elif source == "network_traffic_monitor":
            features["pkt_length"] = float(data.get("length", 0) or 0)
            features["pkt_src_port"] = float(data.get("src_port", 0) or 0)
            features["pkt_dst_port"] = float(data.get("dst_port", 0) or 0)
            
            protocol = str(data.get("protocol", "")).upper()
            features["is_wifi_mgmt"] = 1 if protocol in ("802.11", "WIFI", "WLAN") else 0
            features["is_deauth"] = 1 if data.get("subtype") == "deauth" else 0
            features["is_disassoc"] = 1 if data.get("subtype") == "disassoc" else 0
            features["is_beacon"] = 1 if data.get("subtype") == "beacon" else 0
            features["is_probe"] = 1 if data.get("subtype") in ("probe-req", "probe-resp") else 0
            
            dst_port = features["pkt_dst_port"]
            src_port = features["pkt_src_port"]
            features["is_mavlink_port"] = 1 if dst_port in (5760, 14550, 14551) or src_port in (5760, 14550, 14551) else 0
            features["is_web_port"] = 1 if dst_port in (80, 443, 3000, 8080) else 0
            features["is_ftp_port"] = 1 if dst_port in (20, 21) or src_port in (20, 21) else 0
            features["is_ssh_port"] = 1 if dst_port == 22 or src_port == 22 else 0
            features["is_ros_port"] = 1 if dst_port in (11311, 11312) or src_port in (11311, 11312) else 0
            features["pkt_size_small"] = 1 if features["pkt_length"] < 100 else 0
            features["pkt_size_large"] = 1 if features["pkt_length"] > 1400 else 0

        elif source == "dvd_telemetry_monitor":
            features.update({
                "lat": float(data.get("lat", 0) or 0),
                "lon": float(data.get("lon", 0) or 0),
                "alt_m": float(data.get("alt_m", 0) or 0),
                "relative_alt_m": float(data.get("relative_alt_m", 0) or 0),
                "vx": float(data.get("vx", 0) or 0),
                "vy": float(data.get("vy", 0) or 0),
                "vz": float(data.get("vz", 0) or 0),
                "pitch_deg": float(data.get("pitch_deg", 0) or 0),
                "roll_deg": float(data.get("roll_deg", 0) or 0),
                "yaw_deg": float(data.get("yaw_deg", 0) or 0),
                "groundspeed_ms": float(data.get("groundspeed_ms", 0) or 0),
                "battery_v": float(data.get("battery_v", 0) or 0),
                "battery_pct": float(data.get("battery_pct", 0) or 0),
                "heading_deg": float(data.get("heading_deg", 0) or 0),
            })
            
            mode = str(data.get("mode", "")).upper()
            features["mode_is_guided"] = 1 if "GUIDED" in mode else 0
            features["mode_is_auto"] = 1 if "AUTO" in mode else 0
            features["mode_is_rtl"] = 1 if "RTL" in mode else 0
            features["mode_is_stabilize"] = 1 if "STABILIZE" in mode else 0
            features["mode_is_land"] = 1 if "LAND" in mode else 0
            features["mode_is_loiter"] = 1 if "LOITER" in mode else 0
            
            features["gps_fix_type"] = int(data.get("gps_fix_type", 0) or 0)
            features["gps_satellites"] = int(data.get("satellites_visible", 0) or 0)
            features["battery_critical"] = 1 if features["battery_pct"] < 20 else 0
            features["altitude_anomaly"] = 1 if features["alt_m"] < 0 or features["alt_m"] > 500 else 0

        elif source == "dvd_container_monitor":
            features.update({
                "cpu_load_pct": float(data.get("cpu_load_pct", 0) or 0),
                "memory_pct": float(data.get("memory_pct", 0) or 0),
                "net_rx_bytes": float(data.get("network_rx_bytes", 0) or 0),
                "net_tx_bytes": float(data.get("network_tx_bytes", 0) or 0),
                "disk_read_bytes": float(data.get("disk_read_bytes", 0) or 0),
                "disk_write_bytes": float(data.get("disk_write_bytes", 0) or 0),
                "container_running": 1 if data.get("running") else 0,
            })
            
            c_name = str(data.get("container_name", "")).lower()
            features["is_gcs_container"] = 1 if "ground-control" in c_name else 0
            features["is_fc_container"] = 1 if "flight-controller" in c_name else 0
            features["is_cc_container"] = 1 if "companion" in c_name else 0
            features["cpu_high"] = 1 if features["cpu_load_pct"] > 80 else 0
            features["memory_high"] = 1 if features["memory_pct"] > 80 else 0

        elif source == "qos_monitor":
            features.update({
                "avg_rtt_ms": float(data.get("avg_rtt_ms", 0) or 0),
                "packet_loss_pct": float(data.get("packet_loss_pct", 0) or 0),
                "jitter_ms": float(data.get("jitter_ms", 0) or 0),
            })
            
            cumulative = data.get("system_resources_cumulative") or {}
            features["mem_percent"] = float(cumulative.get("memory_percent", 0) or 0)
            
            rates = data.get("system_resources_rates") or {}
            features["disk_read_bps"] = float(rates.get("disk_read_bps", 0) or 0)
            features["disk_write_bps"] = float(rates.get("disk_write_bps", 0) or 0)
            features["net_sent_bps"] = float(rates.get("net_sent_bps", 0) or 0)
            features["net_recv_bps"] = float(rates.get("net_recv_bps", 0) or 0)
            
            features["high_latency"] = 1 if features["avg_rtt_ms"] > 100 else 0
            features["high_packet_loss"] = 1 if features["packet_loss_pct"] > 5 else 0

        elif source == "docker_event_monitor":
            status = str(data.get("status", "")).lower()
            features["is_exec_start"] = 1 if status == "exec_start" else 0
            features["is_exec_create"] = 1 if status == "exec_create" else 0
            features["is_copy"] = 1 if "copy" in status or "archive" in status else 0
            features["is_die"] = 1 if status == "die" else 0
            features["is_start"] = 1 if status == "start" else 0
            features["is_stop"] = 1 if status == "stop" else 0

        elif source == "mavlink_monitor":
            msg_type = str(data.get("mavpackettype", "")).upper()
            features["is_heartbeat"] = 1 if msg_type == "HEARTBEAT" else 0
            features["is_command_long"] = 1 if msg_type == "COMMAND_LONG" else 0
            features["is_mission_item"] = 1 if "MISSION" in msg_type else 0
            features["is_param"] = 1 if "PARAM" in msg_type else 0
            features["is_gps_raw"] = 1 if msg_type == "GPS_RAW_INT" else 0
            features["mav_sys_id"] = int(data.get("get_srcSystem", 0) or 0)
            features["mav_comp_id"] = int(data.get("get_srcComponent", 0) or 0)

        return features

    def process_logs_batch(self) -> Optional[pd.DataFrame]:
        records = []
        current_attack_name: Optional[str] = None
        current_label: int = 0
        attack_count = 0

        logger.info("🚀 배치 처리 시작...")

        for log_entry in self.iter_bus_logs():
            source = log_entry.get("source")
            log_type = log_entry.get("type") or log_entry.get("event_type")
            data = log_entry.get("data", {}) or {}

            if source in ("attack_orchestrator", "scenario_runner"):
                attack_name = data.get("attack_name")
                
                if log_type == "attack_started" and attack_name:
                    normalized_name = normalize_attack_name(attack_name)
                    current_label = self._get_label_for_attack(normalized_name)
                    current_attack_name = normalized_name
                    attack_count += 1
                    
                elif log_type == "attack_stopped":
                    current_label = 0
                    current_attack_name = None

            features = self.extract_features(log_entry)
            features["label"] = current_label
            
            if self.use_tactic_labels:
                features["tactic_label"] = self._get_tactic_label(current_label)
            
            features["current_attack_name"] = current_attack_name
            features["ts"] = log_entry.get("ts")
            features["timestamp"] = log_entry.get("timestamp")

            records.append(features)

        if not records:
            logger.warning("⚠ No records found.")
            return None

        logger.info(f"✓ {len(records):,} 레코드, {attack_count} 공격 이벤트")

        df = pd.DataFrame.from_records(records)

        exclude_cols = ["source", "log_type", "attack_name", "scenario", 
                       "runner_event", "timestamp", "current_attack_name"]
        
        numeric_cols = [c for c in df.columns if c not in exclude_cols]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.fillna(0, inplace=True)

        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"features_batch_{ts_str}.csv")
        df.to_csv(output_path, index=False)
        logger.info(f"✅ 저장: {output_path}")

        self._print_label_distribution(df)
        return df

    def _print_label_distribution(self, df: pd.DataFrame):
        logger.info("\n" + "=" * 60)
        logger.info("📊 라벨 분포:")
        logger.info("=" * 60)
        
        label_col = "tactic_label" if self.use_tactic_labels and "tactic_label" in df.columns else "label"
        name_map = self.tactic_names if self.use_tactic_labels else self.reverse_mapping
        
        label_counts = df[label_col].value_counts().sort_index()
        for label_id, count in label_counts.items():
            name = name_map.get(int(label_id), "unknown")
            pct = count / len(df) * 100
            logger.info(f"  [{label_id:2d}] {name:40s}: {count:8,} ({pct:5.1f}%)")
        logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Builder v2.0")
    parser.add_argument("--log-file", help="Single log file path")
    parser.add_argument("--log-dir", help="Log directory path")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mapping-file", default=DEFAULT_MAPPING_FILE)
    parser.add_argument("--tactic-level", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    log_dir = args.log_dir if args.log_dir else DEFAULT_BUS_DIR

    builder = DataBuilder(
        bus_log_path=args.log_file,
        bus_log_dir=log_dir,
        output_dir=args.output_dir,
        mapping_file=args.mapping_file,
        use_tactic_labels=args.tactic_level
    )

    builder.process_logs_batch()
