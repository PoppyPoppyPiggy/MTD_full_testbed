#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Builder (Fixed Version)
=============================
bus 로그를 읽어 ML 학습용 피처를 생성하고 CSV로 저장

수정 사항:
1. 공격명 정규화 함수 추가 (파일명 ↔ event_mapping 변환)
2. 피처 추출 로직 강화 (공격 특화 피처)
3. 로그 파싱 안정성 개선
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


# ----------------------------
# 공격명 정규화 함수
# ----------------------------
def normalize_attack_name(name: str) -> str:
    """
    공격명을 정규화하여 event_mapping.json과 일치시킴
    
    파일명 패턴:
    - wifi-analysis-_-cracking.sh → wifi-analysis-_-cracking
    - drone-gps-_-telemetry-detection.sh → drone-gps-_-telemetry-detection
    
    주의: 언더스코어가 포함된 파일명을 그대로 사용
    """
    if not name:
        return name
    
    # .sh 확장자 제거
    if name.endswith('.sh'):
        name = name[:-3]
    
    return name.strip()


def get_attack_name_variants(name: str) -> List[str]:
    """
    공격명의 가능한 변형들을 반환 (검색용)
    """
    variants = [name]
    
    # 언더스코어 변형
    # wifi-analysis-cracking ↔ wifi-analysis-_-cracking
    if '-_-' in name:
        variants.append(name.replace('-_-', '-'))
    else:
        # 가능한 위치에 -_- 삽입 시도
        parts = name.split('-')
        for i in range(1, len(parts)):
            variant = '-'.join(parts[:i]) + '-_-' + '-'.join(parts[i:])
            variants.append(variant)
    
    return variants


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
        self.reverse_mapping: Dict[int, str] = {}  # ID → Name

        os.makedirs(self.output_dir, exist_ok=True)

        # 공격명 → 정수 라벨 매핑 로드
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                self.event_mapping = json.load(f)
                self.reverse_mapping = {v: k for k, v in self.event_mapping.items()}
            logger.info(f"✓ Event mapping 로드: {len(self.event_mapping)} 항목")
        except FileNotFoundError:
            logger.error(f"❌ Event mapping 파일 없음: {mapping_file}")
        except Exception as e:
            logger.error(f"❌ Event mapping 로드 실패: {e}")

    def _get_label_for_attack(self, attack_name: str) -> int:
        """
        공격명에 해당하는 라벨 반환 (변형 검색 포함)
        """
        if not attack_name:
            return 0
        
        normalized = normalize_attack_name(attack_name)
        
        # 직접 매칭
        if normalized in self.event_mapping:
            return self.event_mapping[normalized]
        
        # 변형 검색
        for variant in get_attack_name_variants(normalized):
            if variant in self.event_mapping:
                logger.debug(f"Attack name variant matched: {attack_name} → {variant}")
                return self.event_mapping[variant]
        
        # 매칭 실패 시 경고
        logger.warning(f"⚠ Unknown attack name: {attack_name} (normalized: {normalized})")
        return 0

    def _collect_log_files(self) -> List[str]:
        """처리할 로그 파일 목록을 수집"""
        files = set()
        
        # 1. 단일 파일 지정 시
        if self.bus_log_path and os.path.isfile(self.bus_log_path):
            files.add(self.bus_log_path)
            if not self.bus_log_dir:
                derived_dir = os.path.dirname(self.bus_log_path)
                if os.path.isdir(derived_dir):
                    logger.info(f"Auto-detecting sibling logs in: {derived_dir}")
                    self.bus_log_dir = derived_dir

        # 2. 디렉토리 지정 시
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
            logger.warning(f"⚠ No log files found")
        else:
            logger.info(f"✓ Collected {len(file_list)} log files:")
            for f in sorted(file_list):
                logger.info(f"  - {os.path.basename(f)}")
            
        return file_list

    def _read_and_sort_logs(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """여러 로그 파일을 읽어 타임스탬프 순으로 정렬"""
        all_logs = []
        logger.info(f"Reading logs from {len(file_paths)} files...")
        
        for fpath in file_paths:
            line_count = 0
            error_count = 0
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
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
                            line_count += 1
                        except json.JSONDecodeError:
                            error_count += 1
                            
                logger.info(f"  {os.path.basename(fpath)}: {line_count} entries, {error_count} errors")
            except Exception as e:
                logger.error(f"Error reading {fpath}: {e}")

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
        하나의 bus 로그 엔트리에서 ML용 feature를 추출
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
            features["attack_name"] = normalize_attack_name(data.get("attack_name"))
            features["scenario"] = data.get("scenario")

        # ---- scenario_runner ----
        elif source == "scenario_runner":
            features["attack_name"] = normalize_attack_name(data.get("attack_name"))
            features["scenario"] = data.get("scenario")
            features["runner_event"] = log_type

        # ---- network_traffic_monitor ----
        elif source == "network_traffic_monitor":
            # 기본 네트워크 피처
            features["pkt_length"] = float(data.get("length", 0) or 0)
            features["pkt_src_port"] = float(data.get("src_port", 0) or 0)
            features["pkt_dst_port"] = float(data.get("dst_port", 0) or 0)
            
            # 공격 특화 피처
            protocol = str(data.get("protocol", "")).upper()
            features["is_wifi_mgmt"] = 1 if protocol in ("802.11", "WIFI", "WLAN") else 0
            features["is_deauth"] = 1 if data.get("subtype") == "deauth" else 0
            features["is_disassoc"] = 1 if data.get("subtype") == "disassoc" else 0
            
            # 주요 서비스 포트
            dst_port = features["pkt_dst_port"]
            features["is_mavlink_port"] = 1 if dst_port in (5760, 14550, 14551) else 0
            features["is_web_port"] = 1 if dst_port in (80, 443, 3000, 8080) else 0
            features["is_ftp_port"] = 1 if dst_port in (20, 21) else 0
            features["is_ssh_port"] = 1 if dst_port == 22 else 0

        # ---- dvd_telemetry_monitor ----
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
            })
            
            # 모드 감지
            mode = str(data.get("mode", "")).upper()
            features["mode_is_guided"] = 1 if "GUIDED" in mode else 0
            features["mode_is_auto"] = 1 if "AUTO" in mode else 0
            features["mode_is_rtl"] = 1 if "RTL" in mode else 0
            features["mode_is_stabilize"] = 1 if "STABILIZE" in mode else 0

        # ---- dvd_container_monitor ----
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

        # ---- qos_monitor ----
        elif source == "qos_monitor":
            features.update({
                "avg_rtt_ms": float(data.get("avg_rtt_ms", 0) or 0),
                "packet_loss_pct": float(data.get("packet_loss_pct", 0) or 0),
                "cpu_load_pct": float(data.get("cpu_load_pct", 0) or 0),
                "mem_percent": float((data.get("system_resources_cumulative") or {}).get("memory_percent", 0) or 0),
                "disk_read_bps": float((data.get("system_resources_rates") or {}).get("disk_read_bps", 0) or 0),
                "disk_write_bps": float((data.get("system_resources_rates") or {}).get("disk_write_bps", 0) or 0),
                "net_sent_bps": float((data.get("system_resources_rates") or {}).get("net_sent_bps", 0) or 0),
                "net_recv_bps": float((data.get("system_resources_rates") or {}).get("net_recv_bps", 0) or 0),
            })

        # ---- docker_event_monitor ----
        elif source == "docker_event_monitor":
            status = str(data.get("status", "")).lower()
            features["docker_health"] = data.get("health_status")
            
            # Exfiltration 탐지용
            features["is_exec_start"] = 1 if status == "exec_start" else 0
            features["is_copy"] = 1 if "copy" in status or "archive" in status else 0
            features["is_die"] = 1 if status == "die" else 0

        return features

    def process_logs_batch(self) -> Optional[pd.DataFrame]:
        """배치 모드로 모든 로그 처리"""
        records = []
        current_attack_name: Optional[str] = None
        current_label: int = 0
        attack_count = 0

        logger.info("🚀 배치 처리 시작...")

        for log_entry in self.iter_bus_logs():
            source = log_entry.get("source")
            log_type = log_entry.get("type") or log_entry.get("event_type")
            data = log_entry.get("data", {}) or {}

            # --- 1) 상태머신: 공격 시작/종료 ---
            if source in ("attack_orchestrator", "scenario_runner"):
                attack_name = data.get("attack_name")
                
                if log_type == "attack_started" and attack_name:
                    normalized_name = normalize_attack_name(attack_name)
                    current_label = self._get_label_for_attack(normalized_name)
                    current_attack_name = normalized_name
                    attack_count += 1
                    logger.debug(f"Attack started: {current_attack_name} → label {current_label}")
                    
                elif log_type == "attack_stopped":
                    logger.debug(f"Attack stopped: {current_attack_name}")
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
            logger.warning("⚠ No records found in log files.")
            return None

        logger.info(f"✓ 총 {len(records):,} 레코드, {attack_count} 공격 이벤트 처리")

        df = pd.DataFrame.from_records(records)

        # --- 데이터 정제 ---
        logger.info("데이터 정제 중...")
        
        # 제외할 컬럼 (문자열)
        exclude_cols = ["source", "log_type", "attack_name", "scenario", 
                       "runner_event", "timestamp", "current_attack_name", 
                       "container_name", "docker_name", "docker_health"]
        
        # 수치형 변환
        numeric_cols = [c for c in df.columns if c not in exclude_cols]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # NaN/Inf 처리
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.fillna(0, inplace=True)

        # 저장
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"features_batch_{ts_str}.csv")
        
        try:
            df.to_csv(output_path, index=False)
            logger.info(f"✅ 저장 완료: {output_path}")
        except Exception as e:
            logger.error(f"❌ CSV 저장 실패: {e}")

        # 라벨 분포 출력
        if "label" in df.columns:
            logger.info("\n" + "=" * 50)
            logger.info("📊 라벨 분포:")
            logger.info("=" * 50)
            label_counts = df["label"].value_counts().sort_index()
            for label_id, count in label_counts.items():
                attack_name = self.reverse_mapping.get(int(label_id), "unknown")
                pct = count / len(df) * 100
                logger.info(f"  [{label_id:2d}] {attack_name:40s}: {count:6,} ({pct:5.1f}%)")
            logger.info("=" * 50)

        return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build features from bus logs (Fixed)")
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