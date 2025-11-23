#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: dvd_lite/dvd_attacks_lpc/ml/data_builder.py
설  명: bus.log를 배치로 읽어 피처를 생성하고 CSV로 저장
       - docker 재시작/placeholder 통계(None) 안전 처리
       - 공격 시작/종료 이벤트 기반 레이블 상태머신
       - 경로/인코딩/형변환/결측 처리 강화
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

# 스트리밍 예시용(현재 비활성) 의존성
try:
    from watchdog.observers import Observer  # noqa: F401
    from watchdog.events import FileSystemEventHandler  # noqa: F401
except Exception:
    # watchdog 미설치 환경 고려
    class FileSystemEventHandler:  # type: ignore
        pass

# ----------------------------
# 로깅 설정
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DataBuilder")


# ----------------------------
# 안전 변환 헬퍼
# ----------------------------
def _safe_float(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _bytes_to_mb(x):
    try:
        return (float(x) / (1024.0 * 1024.0)) if x is not None else None
    except (TypeError, ValueError):
        return None


# ----------------------------
# 경로 기본값(절대경로)
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUS_LOG_PATH = os.path.abspath(os.path.join(BASE_DIR, "../bus/bus.log"))
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, "./processed_data"))
DEFAULT_MAPPING_FILE = os.path.abspath(os.path.join(BASE_DIR, "event_mapping.json"))


# ----------------------------
# DatasetManager (별도 파일 권장)
# ----------------------------
try:
    # 같은 디렉토리에 dataset_manager.py가 있는 경우 이를 사용
    from dataset_manager import DatasetManager  # type: ignore
except Exception:
    class DatasetManager:
        """간단한 CSV 저장기(임시). 실제 프로젝트에선 별도 파일로 두는 것을 권장합니다."""
        def __init__(self, output_dir: str):
            self.output_dir = output_dir
            os.makedirs(self.output_dir, exist_ok=True)

        def save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
            if not isinstance(df, pd.DataFrame):
                print("[DatasetManager Error] df is not a DataFrame.", file=sys.stderr)
                return
            try:
                output_path = os.path.join(self.output_dir, filename)
                df.to_csv(output_path, index=False)
            except Exception as e:
                print(f"[DatasetManager Error] Failed to save {filename}: {e}", file=sys.stderr)


class DataBuilder:
    def __init__(
        self,
        bus_log_path: str = DEFAULT_BUS_LOG_PATH,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        mapping_file: str = DEFAULT_MAPPING_FILE
    ):
        self.bus_log_path = bus_log_path
        self.output_dir = output_dir
        self.dataset_manager = DatasetManager(output_dir)
        self.event_mapping: Dict[str, int] = {}

        os.makedirs(self.output_dir, exist_ok=True)

        # 공격명 -> 정수 라벨 매핑 로드
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                self.event_mapping = json.load(f)
            logger.info(f"Loaded event mapping from {mapping_file}")
        except FileNotFoundError:
            logger.error(
                f"Event mapping file not found at {mapping_file}. "
                f"Cannot automatically label attack data. Using empty mapping."
            )
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {mapping_file}: {e}. Using empty mapping.")
        except Exception as e:
            logger.error(f"Unexpected error loading event mapping: {e}. Using empty mapping.")

        # streaming 모드 관련 내부 상태(현재 비활성)
        self._last_file_position = 0
        self._last_log_timestamp: Optional[datetime] = None

    # ----------------------------
    # (예전) 로그 파서 – 현재는 iter_bus_logs가 직접 JSON 파싱
    # ----------------------------
    def parse_log_entry(self, line: str) -> Optional[Dict[str, Any]]:
        """이전 버전 호환용. (지금은 iter_bus_logs 에서 바로 json.loads 사용 권장)"""
        try:
            log_entry = json.loads(line)
            ts_str = log_entry.get("timestamp")
            ts_posix = log_entry.get("ts")

            if ts_posix:
                log_entry["timestamp_dt"] = datetime.fromtimestamp(float(ts_posix))
            elif ts_str:
                try:
                    log_entry["timestamp_dt"] = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        log_entry["timestamp_dt"] = datetime.fromisoformat(ts_str)
                        logger.warning(f"Timestamp '{ts_str}' parsed as local time.")
                    except ValueError:
                        logger.error(f"Could not parse timestamp format: {ts_str}. Using current time.")
                        log_entry["timestamp_dt"] = datetime.now()
            else:
                logger.warning("Log entry missing 'timestamp' and 'ts'. Using current time.")
                log_entry["timestamp_dt"] = datetime.now()

            log_entry["timestamp_str"] = ts_str if ts_str else log_entry["timestamp_dt"].isoformat()
            return log_entry

        except json.JSONDecodeError:
            logger.debug(f"Skipping malformed JSON: {line.strip()}")
            return None
        except Exception as e:
            logger.error(f"Error parsing log entry: {e}")
            return None

    # ----------------------------
    # bus.log 이터레이터 (새로운 공통 진입점)
    # ----------------------------
    def iter_bus_logs(self):
        """
        bus.log 파일을 순차적으로 읽어 JSON dict 를 yield.
        - 잘못된 JSON 라인은 건너뜀.
        """
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
                    logger.debug(f"Skipping malformed JSON: {line}")
                except Exception as e:
                    logger.error(f"Error parsing bus.log line: {e}")

    # ----------------------------
    # 피처 추출 (새 버전)
    # ----------------------------
    def extract_features(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        하나의 bus 로그 엔트리(JSON dict)에서 ML용 feature를 추출한다.
        - source / type / event_type 등을 공통적으로 처리해서,
          attack_orchestrator, network_traffic_monitor, qos_monitor 등에서 오는
          데이터를 일관된 형태로 만든다.
        """
        source = log_entry.get("source", "unknown")
        # ✅ type -> event_type 순으로 fallback
        log_type = log_entry.get("type") or log_entry.get("event_type") or "unknown"
        data = log_entry.get("data", {}) or {}

        features: Dict[str, Any] = {
            "source": source,
            "log_type": log_type,
        }

        # ---- attack_orchestrator 이벤트 (레이블링에 중요) ----
        if source == "attack_orchestrator":
            # 예: {"attack_name": "...", "scenario": "...", ...}
            attack_name = data.get("attack_name")
            scenario = data.get("scenario")
            features["attack_name"] = attack_name
            features["scenario"] = scenario

        # ---- scenario_runner 메타 이벤트 (선택) ----
        elif source == "scenario_runner":
            features["attack_name"] = data.get("attack_name")
            features["scenario"] = data.get("scenario")
            features["runner_event"] = log_type

        # ---- network_traffic_monitor ----
        elif source == "network_traffic_monitor":
            # network_packet / network_traffic_batch 둘 다 올 수 있음
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
                # 기타 타입은 최소한 길이/프로토콜만
                features["pkt_length"] = data.get("length")
                features["pkt_proto"] = data.get("protocol")

        # ---- dvd_telemetry_monitor ----
        elif source == "dvd_telemetry_monitor":
            # 예: mavlink_global_position_int, mavlink_attitude 등
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
            # container_telemetry
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

        # 기타/unknown source 는 최소 정보만 남겨둠
        return features

    # ----------------------------
    # (구버전) 후처리 – 지금은 사용 안 하지만 남겨둠
    # ----------------------------
    def _post_process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        logger.info(f"Shape before post-processing: {df.shape}")

        if "label" in df.columns:
            df["label"] = df["label"].fillna(0)
        else:
            df["label"] = 0
        if "attack_name" in df.columns:
            df["attack_name"] = df["attack_name"].fillna("normal")
        else:
            df["attack_name"] = "normal"

        fill_zeros = [
            c for c in df.columns
            if ("count" in c or "bytes" in c or c.endswith("_id") or c.endswith("_status")
                or c.endswith("_type") or "progress" in c or "detected" in c or "opcode" in c or c.endswith("pids"))
        ]
        fill_neg_one = [c for c in df.columns if c.endswith("port")]

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        remaining_numeric = list(
            set(numeric_cols).difference(set(["ts", "label"] + fill_zeros + fill_neg_one))
        )

        for c in fill_zeros:
            if c in df.columns:
                df[c] = df[c].fillna(0)
        for c in fill_neg_one:
            if c in df.columns:
                df[c] = df[c].fillna(-1)
        for c in remaining_numeric:
            if c in df.columns:
                df[c] = df[c].fillna(0)

        categorical_cols = [
            "net_protocol", "mav_msg_name", "cont_name", "cont_status",
            "docker_cont_name", "docker_event_status", "docker_health_status", "net_tcp_flags"
        ]
        for col in categorical_cols:
            if col in df.columns:
                df[col] = df[col].fillna("UNKNOWN")
                try:
                    top_categories = df[col].value_counts().nlargest(50).index
                    df[col] = df[col].where(df[col].isin(top_categories), "OTHER")
                    df = pd.get_dummies(df, columns=[col], prefix=col, dummy_na=False)
                except Exception as e:
                    logger.error(f"One-hot encoding failed for '{col}': {e}")

        ip_cols = [c for c in df.columns if c.endswith("_ip")]
        if ip_cols:
            logger.warning(f"IP address columns {ip_cols} found. They may be dropped in later stages.")
            for c in ip_cols:
                df[c] = df[c].fillna("UNKNOWN")

        logger.info(f"Shape after post-processing: {df.shape}")
        return df

    # ----------------------------
    # 배치 처리 (새 버전)
    # ----------------------------
    def process_logs_batch(self) -> Optional[pd.DataFrame]:
        """
        bus.log 전체를 읽어서 feature + label 이 들어간 DataFrame을 만든다.
        - attack_orchestrator 의 attack_started / attack_stopped 를 상태머신으로 읽어,
          각 구간에 label (정수)을 붙인다.
        """
        records: list[Dict[str, Any]] = []

        current_attack_name: Optional[str] = None
        current_label: int = 0  # 0 = normal

        logger.info(f"Starting batch processing of: {self.bus_log_path}")

        for log_entry in self.iter_bus_logs():
            source = log_entry.get("source")
            # ✅ type -> event_type 순으로 읽기
            log_type = log_entry.get("type") or log_entry.get("event_type")
            data = log_entry.get("data", {}) or {}

            # --- 1) 상태머신: 공격 시작/종료 이벤트 처리 ---
            if source == "attack_orchestrator":
                attack_name = data.get("attack_name")
                if log_type == "attack_started" and attack_name:
                    current_label = self.event_mapping.get(attack_name, 0)
                    current_attack_name = attack_name
                elif log_type == "attack_stopped" and attack_name:
                    current_label = 0
                    current_attack_name = None

            # --- 2) feature 추출 ---
            features = self.extract_features(log_entry)
            features["label"] = current_label
            features["current_attack_name"] = current_attack_name

            # timestamp/ts 유지 (없으면 None)
            features["ts"] = log_entry.get("ts")
            features["timestamp"] = log_entry.get("timestamp")

            records.append(features)

        if not records:
            logger.warning("bus.log 에서 레코드를 하나도 읽지 못했습니다.")
            return None

        df = pd.DataFrame.from_records(records)

        # NaN / inf 정리
        df.replace([float("inf"), float("-inf")], float("nan"), inplace=True)
        df.fillna(0, inplace=True)

        # 출력 경로 저장 (dataset_manager와 호환되도록 타임스탬프 붙임)
        os.makedirs(self.output_dir, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"features_batch_{ts_str}.csv")
        df.to_csv(output_path, index=False)
        logger.info(f"배치 feature 데이터 저장 완료: {output_path}")

        return df

    # ----------------------------
    # 스트리밍(비활성)
    # ----------------------------
    def _process_new_log_lines(self) -> pd.DataFrame:
        logger.warning("Streaming is handled by cti_agent.py, not DataBuilder.")
        return pd.DataFrame()

    def process_logs_streaming(self) -> None:
        logger.error("Streaming mode is not supported here. Use 'batch' mode.")


# (옵션) 파일 변경 이벤트 핸들러(현재 비활성)
class LogFileHandler(FileSystemEventHandler):  # type: ignore
    def __init__(self, data_builder_instance: DataBuilder):
        self.builder = data_builder_instance
        self.log_filename = os.path.basename(data_builder_instance.bus_log_path)

    def on_modified(self, event):
        pass


# ----------------------------
# 실행부
# ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build features from bus.log")
    parser.add_argument("--mode", choices=["batch", "stream"], default="batch")
    parser.add_argument("--log-file", default=DEFAULT_BUS_LOG_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mapping-file", default=DEFAULT_MAPPING_FILE)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    os.makedirs(args.output_dir, exist_ok=True)

    # event_mapping.json이 없으면 샘플 작성
    if not os.path.exists(args.mapping_file):
        dummy_mapping = {
            "example_attack_1": 1,
            "example_attack_2": 2,
            "gps-spoofing": 3,
            "communication-link-flooding": 4,
            "mavlink-injection-attack": 5
        }
        try:
            with open(args.mapping_file, "w", encoding="utf-8") as f:
                json.dump(dummy_mapping, f, indent=4, ensure_ascii=False)
            logger.info(f"Created dummy mapping: {args.mapping_file}")
        except IOError as e:
            logger.error(f"Could not create mapping file: {e}")

    # bus.log이 없으면 빈 파일 생성(테스트 편의)
    if not os.path.exists(args.log_file):
        logger.warning(f"Log file {args.log_file} not found. Creating empty file.")
        try:
            os.makedirs(os.path.dirname(args.log_file), exist_ok=True)
            open(args.log_file, "a").close()
        except IOError as e:
            logger.error(f"Could not create log file {args.log_file}: {e}")
            sys.exit(1)

    builder = DataBuilder(
        bus_log_path=args.log_file,
        output_dir=args.output_dir,
        mapping_file=args.mapping_file
    )

    if args.mode == "batch":
        logger.info("Running in BATCH mode.")
        df_out = builder.process_logs_batch()
        if df_out is not None:
            logger.info("Batch processing complete.")
            if "label" in df_out.columns:
                logger.info("--- Label Distribution ---")
                logger.info(df_out["label"].value_counts(normalize=True).sort_index())
                logger.info("--------------------------")
            else:
                logger.error("'label' column not found in DataFrame.")
        else:
            logger.error("Batch processing failed.")
    else:
        logger.error("Streaming mode is handled by cti_agent.py; use batch mode here.")
