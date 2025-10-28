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
    # 로그 파서
    # ----------------------------
    def parse_log_entry(self, line: str) -> Optional[Dict[str, Any]]:
        """bus.log의 한 줄(JSON)을 dict로 파싱 + timestamp 표준화."""
        try:
            log_entry = json.loads(line)
            ts_str = log_entry.get("timestamp")
            ts_posix = log_entry.get("ts")

            if ts_posix:
                log_entry["timestamp_dt"] = datetime.fromtimestamp(float(ts_posix))
            elif ts_str:
                try:
                    # ISO8601(Z 표기 지원)
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

            # 원본 문자열 보존
            log_entry["timestamp_str"] = ts_str if ts_str else log_entry["timestamp_dt"].isoformat()
            return log_entry

        except json.JSONDecodeError:
            logger.debug(f"Skipping malformed JSON: {line.strip()}")
            return None
        except Exception as e:
            logger.error(f"Error parsing log entry: {e}")
            return None

    # ----------------------------
    # 피처 추출
    # ----------------------------
    def extract_features(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        모니터링/이벤트 레코드로부터 피처를 생성.
        레이블 할당은 process_logs_batch()의 상태머신에서 수행.
        """
        features: Dict[str, Any] = {
            "timestamp": log_entry["timestamp_str"],
            "ts": log_entry.get("ts", log_entry["timestamp_dt"].timestamp()),
        }

        source = log_entry.get("source", "unknown")
        log_type = log_entry.get("type", "unknown")
        data = log_entry.get("data", {}) or {}

        # 1) 네트워크 모니터
        if source == "network_traffic_monitor" and log_type == "network_packet":
            features["net_protocol"] = data.get("transport_protocol", data.get("protocol", "unknown")).lower()
            features["net_src_ip"] = data.get("ip_src", data.get("ipv6_src"))
            features["net_dst_ip"] = data.get("ip_dst", data.get("ipv6_dst"))
            features["net_src_port"] = data.get("tcp_srcport", data.get("udp_srcport"))
            features["net_dst_port"] = data.get("tcp_dstport", data.get("udp_dstport"))
            features["net_pkt_len"] = data.get("length")
            # TCP/ARP 세부
            if features["net_protocol"] == "tcp":
                features["net_tcp_flags"] = data.get("tcp_flags")
            elif features["net_protocol"] == "arp":
                features["net_arp_opcode"] = data.get("arp_opcode")

        # 2) 텔레메트리(MAVLink)
        elif source == "dvd_telemetry_monitor" and log_type.startswith("mavlink_"):
            msg_name = log_type.replace("mavlink_", "").upper()
            features["mav_msg_name"] = msg_name
            payload = data

            if msg_name == "HEARTBEAT":
                features["mav_hb_type"] = payload.get("type")
                features["mav_hb_autopilot"] = payload.get("autopilot")
                features["mav_hb_status"] = payload.get("system_status")

            elif msg_name == "GLOBAL_POSITION_INT":
                features["mav_gps_lat"] = payload.get("lat")
                features["mav_gps_lon"] = payload.get("lon")
                features["mav_gps_alt"] = payload.get("alt")
                features["mav_gps_rel_alt"] = payload.get("relative_alt")
                features["mav_gps_vx"] = payload.get("vx")
                features["mav_gps_vy"] = payload.get("vy")
                features["mav_gps_vz"] = payload.get("vz")
                features["mav_gps_hdg"] = payload.get("hdg")

            elif msg_name == "ATTITUDE":
                features["mav_att_roll"] = payload.get("roll")
                features["mav_att_pitch"] = payload.get("pitch")
                features["mav_att_yaw"] = payload.get("yaw")
                features["mav_att_rollspeed"] = payload.get("rollspeed")

            elif msg_name == "SYS_STATUS":
                features["mav_sys_voltage"] = payload.get("voltage_battery")
                features["mav_sys_current"] = payload.get("current_battery")
                features["mav_sys_load"] = payload.get("load")
                features["mav_sys_errors"] = payload.get("errors_count1")

        # 3) 컨테이너 모니터
        elif source == "dvd_container_monitor" and log_type == "container_stats_details":
            features["cont_name"] = data.get("name")
            features["cont_status"] = data.get("status")
            features["cont_restarting"] = bool(data.get("restarting", False))
            features["cont_exit_code"] = data.get("exit_code")

            stats = data.get("stats") or {}
            # 도커 placeholder(읽을 수 없는 통계) 감지
            is_placeholder = stats.get("read_time") in (None, "", "0001-01-01T00:00:00Z")

            if not is_placeholder:
                features["cont_cpu_usage_pct"] = _safe_float(stats.get("cpu_percent"))
                features["cont_mem_usage_mb"] = _bytes_to_mb(stats.get("memory_usage_bytes"))
                features["cont_mem_limit_mb"] = _bytes_to_mb(stats.get("memory_limit_bytes"))
                features["cont_mem_pct"] = _safe_float(stats.get("memory_percent"))
                # 누적 카운터류는 None이면 0
                features["cont_net_rx_bytes"] = stats.get("network_rx_bytes") or 0
                features["cont_net_tx_bytes"] = stats.get("network_tx_bytes") or 0
                features["cont_disk_read_bytes"] = stats.get("disk_read_bytes") or 0
                features["cont_disk_write_bytes"] = stats.get("disk_write_bytes") or 0
                features["cont_pids"] = stats.get("pids") if stats.get("pids") is not None else 0
            else:
                # 재시작/중지 직후 등 유효 통계 없음
                features["cont_cpu_usage_pct"] = None
                features["cont_mem_usage_mb"] = None
                features["cont_mem_limit_mb"] = None
                features["cont_mem_pct"] = None
                features["cont_net_rx_bytes"] = 0
                features["cont_net_tx_bytes"] = 0
                features["cont_disk_read_bytes"] = 0
                features["cont_disk_write_bytes"] = 0
                features["cont_pids"] = 0

        # 4) QoS 모니터
        elif source == "qos_monitor" and log_type == "system_qos":
            rates = data.get("system_resources_rates", {}) or {}
            quality = data.get("network_quality", {}) or {}
            cumulative = data.get("system_resources_cumulative", {}) or {}

            features["qos_cpu_overall_pct"] = cumulative.get("cpu_percent_overall")
            features["qos_mem_pct"] = cumulative.get("memory_percent")
            features["qos_disk_read_bps"] = rates.get("disk_read_bps")
            features["qos_disk_write_bps"] = rates.get("disk_write_bps")
            features["qos_net_sent_bps"] = rates.get("net_sent_bps")
            features["qos_net_recv_bps"] = rates.get("net_recv_bps")
            features["qos_ping_rtt_ms"] = quality.get("avg_rtt_ms")
            features["qos_ping_loss_pct"] = quality.get("packet_loss_percent")

        # 5) Docker 이벤트
        elif source == "docker_event_monitor" and log_type == "docker_event":
            features["docker_cont_name"] = data.get("name")
            features["docker_event_status"] = data.get("status")
            if data.get("status") == "health_status":
                features["docker_health_status"] = data.get("health_status")

        # 숫자형 통일 캐스팅(가능한 항목만)
        numeric_cols = [
            "ts", "net_src_port", "net_dst_port", "net_pkt_len", "net_arp_opcode",
            "mav_hb_type", "mav_hb_autopilot", "mav_hb_status",
            "mav_gps_lat", "mav_gps_lon", "mav_gps_alt", "mav_gps_rel_alt",
            "mav_gps_vx", "mav_gps_vy", "mav_gps_vz", "mav_gps_hdg",
            "mav_att_roll", "mav_att_pitch", "mav_att_yaw", "mav_att_rollspeed",
            "mav_sys_voltage", "mav_sys_current", "mav_sys_load", "mav_sys_errors",
            "cont_cpu_usage_pct", "cont_mem_usage_mb", "cont_mem_limit_mb", "cont_mem_pct",
            "cont_net_rx_bytes", "cont_net_tx_bytes", "cont_disk_read_bytes", "cont_disk_write_bytes", "cont_pids",
            "qos_cpu_overall_pct", "qos_mem_pct", "qos_disk_read_bps", "qos_disk_write_bps",
            "qos_net_sent_bps", "qos_net_recv_bps", "qos_ping_rtt_ms", "qos_ping_loss_pct"
        ]
        for col in numeric_cols:
            if col in features:
                try:
                    features[col] = float(features[col]) if features[col] is not None else None
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert '{col}' value '{features[col]}' to float. Set to None.")
                    features[col] = None

        return features

    # ----------------------------
    # 후처리 (결측/범주 등)
    # ----------------------------
    def _post_process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        logger.info(f"Shape before post-processing: {df.shape}")

        # 레이블/공격명 기본값
        if "label" in df.columns:
            df["label"] = df["label"].fillna(0)
        else:
            df["label"] = 0
        if "attack_name" in df.columns:
            df["attack_name"] = df["attack_name"].fillna("normal")
        else:
            df["attack_name"] = "normal"

        # 채움 전략
        fill_zeros = [
            c for c in df.columns
            if ("count" in c or "bytes" in c or c.endswith("_id") or c.endswith("_status")
                or c.endswith("_type") or "progress" in c or "detected" in c or "opcode" in c or c.endswith("pids"))
        ]
        fill_neg_one = [c for c in df.columns if c.endswith("port")]

        # 나머지 숫자형(통계/QoS/GPS 등)은 0으로
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

        # 범주형 처리(원-핫, 과도한 cardinality 억제)
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

        # IP 주소 열은 분석/학습 전에 제거 예정(경고만)
        ip_cols = [c for c in df.columns if c.endswith("_ip")]
        if ip_cols:
            logger.warning(f"IP address columns {ip_cols} found. They may be dropped in later stages.")
            for c in ip_cols:
                df[c] = df[c].fillna("UNKNOWN")

        logger.info(f"Shape after post-processing: {df.shape}")
        return df

    # ----------------------------
    # 배치 처리
    # ----------------------------
    def process_logs_batch(self) -> Optional[pd.DataFrame]:
        """
        bus.log 전체를 일괄 처리하여 피처 CSV 생성.
        attack_orchestrator의 attack_started/attack_stopped로 상태를 추적하여 레이블링.
        """
        extracted: list[Dict[str, Any]] = []
        logger.info(f"Starting batch processing of: {self.bus_log_path}")

        current_attack_label = 0
        current_attack_name = "normal"

        try:
            with open(self.bus_log_path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    log_entry = self.parse_log_entry(line)
                    if not log_entry:
                        continue

                    source = log_entry.get("source")
                    log_type = log_entry.get("type")
                    if source == "attack_orchestrator":
                        data = log_entry.get("data", {}) or {}
                        attack_name = data.get("attack_name")

                        if log_type == "attack_started" and attack_name:
                            current_attack_label = self.event_mapping.get(attack_name, 0)
                            current_attack_name = attack_name
                            if current_attack_label == 0:
                                logger.warning(f"Attack '{attack_name}' not in mapping. Label=0.")
                            logger.info(
                                f"Attack STATE CHANGE: '{attack_name}'(Label:{current_attack_label}) START @ {log_entry['timestamp_str']}"
                            )
                        elif log_type == "attack_stopped":
                            stopped_name = attack_name or "unknown"
                            logger.info(
                                f"Attack STATE CHANGE: '{stopped_name}' STOP @ {log_entry['timestamp_str']}"
                            )
                            current_attack_label = 0
                            current_attack_name = "normal"
                        # 오케스트레이터 로그는 피처화하지 않음
                        continue

                    try:
                        feats = self.extract_features(log_entry)
                        if feats:
                            feats["label"] = current_attack_label
                            feats["attack_name"] = current_attack_name
                            extracted.append(feats)
                        # 진행 로그
                        if (i + 1) % 50000 == 0:
                            logger.info(f"Processed {i+1} lines... (state: {current_attack_name})")
                    except Exception as e_feat:
                        logger.error(
                            f"Error extracting features at line {i+1}: {e_feat}",
                            exc_info=True
                        )

        except FileNotFoundError:
            logger.error(f"Log file not found: {self.bus_log_path}")
            return None
        except Exception as e:
            logger.error(f"Error during log reading: {e}", exc_info=True)
            return None

        if not extracted:
            logger.warning("No data extracted from log file.")
            return None

        logger.info(f"Creating DataFrame from {len(extracted)} records.")
        df = pd.DataFrame(extracted)
        df = self._post_process_dataframe(df)

        if df.empty:
            logger.warning("DataFrame is empty after post-processing.")
            return None

        # 저장
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"features_batch_{timestamp_str}.csv"
        try:
            self.dataset_manager.save_dataframe(df, out_name)
            logger.info(f"Saved processed batch data to {os.path.join(self.output_dir, out_name)}")
        except Exception as e:
            logger.error(f"Failed to save processed data: {e}", exc_info=True)

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
