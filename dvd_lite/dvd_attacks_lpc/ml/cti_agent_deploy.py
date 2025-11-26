#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 디렉토리: dvd_lite/dvd_attacks_lpc/ml
# 파일명: cti_agent_deploy.py
# 설명: [Deployment] 학습된 모델을 로드하여 실시간 로그를 분석하고 공격 탐지 시 방어(MTD)를 수행하는 에이전트
#       - bus.log(메타 데이터)는 참조하지 않음
#       - bus_network.log, bus_telemetry.log 등을 실시간 모니터링

import os
import sys
import time
import json
import joblib
import logging
import subprocess
import threading
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime

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
MODEL_PATH = os.path.join(BASE_DIR, "output", "cti_classifier_model.joblib")
DECEPTION_MGR = os.path.join(PROJECT_ROOT, "mtd", "rl_driven_deception_manager.py")

# --- 방어 모드 설정 ---
#   CTI_DEFENSE_MODE 환경변수로 제어
#   - "none"     : 탐지만 수행 (No-MTD / Static-MTD 실험에서 사용)
#   - "cti_rule" : 규칙 기반 MTD (이 파일에서 iptables_mtd_controller 직접 제어)
#   - "rl"       : RL 기반 MTD 매니저 호출 (rl_driven_deception_manager.py)
DEFENSE_MODE = os.environ.get("CTI_DEFENSE_MODE", "none").lower()

# --- iptables 기반 MTD 컨트롤러 (cti_rule 모드에서만 사용) ---
try:
    from mtd.iptables_mtd_controller import IptablesMTDController
except Exception:
    IptablesMTDController = None

# --- 모니터링할 로그 파일 목록 (bus.log 제외) ---
TARGET_LOGS = {
    "network": os.path.join(BUS_DIR, "bus_network.log"),
    "telemetry": os.path.join(BUS_DIR, "bus_telemetry.log"),
    "qos": os.path.join(BUS_DIR, "bus_qos.log"),
    "container": os.path.join(BUS_DIR, "bus_container_telemetry.log"),
    "system": os.path.join(BUS_DIR, "bus_system_events.log")
}

# --- 설정 ---
DETECTION_INTERVAL = 1.0  # 초 단위 탐지 주기
FEATURE_WINDOW_SIZE = 10  # 최근 N개 로그를 기반으로 피처 생성 (간이)
CONFIDENCE_THRESHOLD = 0.7 # 공격 판단 임계값 (확률)


class RealTimeLogReader(threading.Thread):
    """로그 파일을 실시간으로 읽어 큐에 넣는 스레드 (tail -f 유사 기능)"""
    def __init__(self, filepath, log_type, data_queue):
        super().__init__()
        self.filepath = filepath
        self.log_type = log_type
        self.data_queue = data_queue
        self.running = True
        self.daemon = True

    def run(self):
        # 파일이 생성될 때까지 대기
        while self.running and not os.path.exists(self.filepath):
            time.sleep(1)

        logger.info(f"[*] Monitoring started: {os.path.basename(self.filepath)}")

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                # 파일 끝으로 이동 (과거 로그 무시하고 현재부터 탐지하려면)
                f.seek(0, os.SEEK_END)

                while self.running:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue

                    try:
                        data = json.loads(line)
                        # 타입 정보 추가하여 큐에 삽입
                        data['_log_source'] = self.log_type
                        self.data_queue.append(data)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.error(f"Reader error ({self.log_type}): {e}")


class CTIAgent:
    def __init__(self):
        self.model = None
        self.label_encoder = None
        self.id_to_name = {}
        self.feature_names = None
        self.data_buffer = deque(maxlen=1000)  # 최근 로그 버퍼
        self.running = True
        self.defense_cooldown = 0.0  # 방어 후 쿨다운

        # --- 멀티 서비스 정의 (서비스 이름 -> (target_key, port_idx)) ---
        # iptables_mtd_controller.DEFAULT_TARGETS와 맞춰서 사용
        self.mtd_services = {
            "fc_mavlink": ("FC", 0),     # FC MAVLink (10.13.0.2:14550)
            "cc_web": ("CC", 0),         # Companion Web (10.13.0.3:3000)
            "cc_mavlink": ("CC", 1),     # Companion MAVLink (10.13.0.3:14550)
            "gcs_mavlink": ("GCS", 0),   # GCS MAVLink (10.13.0.4:14550)
            # 필요 시 SIM/ROS 등도 추가 가능:
            # "sim_sitl": ("SIM", 0),
            # "sim_ros": ("SIM", 1),
        }

        # 규칙 기반 MTD에서 사용할 iptables 컨트롤러
        self.mtd_controller = None
        self._init_mtd_if_needed()

        # 모델 로드
        self.load_model()

        logger.info(f"CTI-Agent Defense Mode = {DEFENSE_MODE}")

    # ------------------------------------------------------------------
    # MTD 컨트롤러 초기화 (cti_rule 모드에서만)
    # ------------------------------------------------------------------
    def _init_mtd_if_needed(self):
        if DEFENSE_MODE != "cti_rule":
            return
        if IptablesMTDController is None:
            logger.error("cti_rule 모드인데 IptablesMTDController를 import하지 못했습니다.")
            return

        try:
            # NOTE: 필요에 따라 dry_run=False로 실제 iptables 적용 가능
            self.mtd_controller = IptablesMTDController(dry_run=True)

            # 멀티 서비스 한 번에 등록
            for svc_name, (target_key, port_idx) in self.mtd_services.items():
                self.mtd_controller.register_service(svc_name, target_key, port_idx)
                logger.info(f"MTD 서비스 등록: {svc_name} -> {target_key}[{port_idx}]")
        except Exception as e:
            logger.error(f"MTD Controller 초기화 실패: {e}")
            self.mtd_controller = None

    # ------------------------------------------------------------------
    # 모델 로드 / 피처 처리
    # ------------------------------------------------------------------
    def load_model(self):
        if not os.path.exists(MODEL_PATH):
            logger.critical(f"❌ 모델 파일을 찾을 수 없습니다: {MODEL_PATH}")
            sys.exit(1)

        try:
            logger.info(f"Loading model artifact from {MODEL_PATH}...")
            artifact = joblib.load(MODEL_PATH)

            # 저장된 형식이 딕셔너리인지 직접 모델인지 확인
            if isinstance(artifact, dict):
                self.model = artifact['model']
                self.label_encoder = artifact['encoder']
                self.id_to_name = artifact.get('mapping', {})
                # feature_names는 별도 파일에서 로드하거나 artifact에 포함해야 함
                # 여기서는 training_features.json을 로드 시도
                feat_path = os.path.join(os.path.dirname(MODEL_PATH), 'training_features.json')
                if os.path.exists(feat_path):
                    with open(feat_path, 'r') as f:
                        self.feature_names = json.load(f)['features']
                else:
                    logger.warning("⚠️ feature names 파일이 없어 모델 속성에서 추론합니다.")
                    if hasattr(self.model, 'feature_names_in_'):
                        self.feature_names = list(self.model.feature_names_in_)
                    elif hasattr(self.model, "named_steps") and "clf" in self.model.named_steps:
                        clf = self.model.named_steps["clf"]
                        if hasattr(clf, "feature_names_in_"):
                            self.feature_names = list(clf.feature_names_in_)
            else:
                # 구버전 호환 (모델만 저장된 경우)
                self.model = artifact
                self.id_to_name = {}  # 매핑 정보 없음

            if not self.feature_names:
                logger.error("feature_names를 결정할 수 없습니다. 학습 파이프라인과 일치하는 구성이 필요합니다.")
                sys.exit(1)

            logger.info("✅ Model loaded successfully.")

        except Exception as e:
            logger.critical(f"❌ 모델 로드 실패: {e}")
            sys.exit(1)

    def preprocess_log_to_features(self, log_entry):
        """
        단일 로그 엔트리를 모델 입력 피처 벡터로 변환
        (data_builder.py의 extract_features 로직 간소화 버전)
        """
        # 기본값 0으로 초기화된 딕셔너리 생성 (모든 피처 포함)
        features = {feat: 0.0 for feat in self.feature_names}

        data = log_entry.get("data", {})
        source = log_entry.get("_log_source")  # 우리가 주입한 타입

        # 각 로그 타입별 피처 매핑
        if source == "network":
            features['pkt_length'] = float(data.get('length', 0))
            features['pkt_src_port'] = float(data.get('src_port', 0))
            features['pkt_dst_port'] = float(data.get('dst_port', 0))
            # 프로토콜 등은 원-핫 인코딩이 필요하나 여기선 간략히 수치형만 처리

        elif source == "telemetry":
            features['alt_m'] = float(data.get('alt_m', 0))
            features['groundspeed_ms'] = float(data.get('groundspeed_ms', 0))
            features['battery_v'] = float(data.get('battery_v', 0))
            features['pitch_deg'] = float(data.get('pitch_deg', 0))
            features['roll_deg'] = float(data.get('roll_deg', 0))

        elif source == "qos":
            features['cpu_load_pct'] = float(data.get('cpu_load_pct', 0))
            features['packet_loss_pct'] = float(data.get('packet_loss_pct', 0))
            features['avg_rtt_ms'] = float(data.get('avg_rtt_ms', 0))
            features['net_recv_bps'] = float((data.get('system_resources_rates') or {}).get('net_recv_bps', 0))

        # DataFrame으로 변환 (1개 행)
        df = pd.DataFrame([features])

        # 모델 학습 시 사용된 컬럼 순서와 정확히 일치시켜야 함
        df = df[self.feature_names]

        return df

    # ------------------------------------------------------------------
    # 규칙 기반 MTD (cti_rule 모드)
    # ------------------------------------------------------------------
    def _execute_cti_rule_mtd(self, mtd_strategy: str, attack_name: str):
        """
        규칙 기반 MTD: 공격 유형에 따라 어떤 서비스들에 어떤 MTD를 적용할지 결정.
        """
        if self.mtd_controller is None:
            logger.error("MTD Controller가 초기화되지 않아 cti_rule 방어를 수행할 수 없습니다.")
            return

        lower_name = attack_name.lower()
        target_services = []

        # 예시 정책:
        # - gps spoofing 계열: FC/GCS MAVLink 중심
        if "gps" in lower_name or "position" in lower_name:
            target_services = ["fc_mavlink", "gcs_mavlink"]

        # - flooding/dos: 모든 MAVLink + web
        elif "flood" in lower_name or "dos" in lower_name:
            target_services = ["fc_mavlink", "cc_mavlink", "gcs_mavlink", "cc_web"]

        # - scan/discovery: 전체 서비스 대상으로 port shuffle
        elif "scan" in lower_name or "discovery" in lower_name:
            target_services = list(self.mtd_services.keys())

        else:
            # 기본값: FC MAVLink만 (high value channel)
            target_services = ["fc_mavlink"]

        logger.info(
            f"⚔️ [DEFENSE-CTI_RULE] strategy={mtd_strategy}, "
            f"attack={attack_name}, targets={target_services}"
        )

        try:
            for svc in target_services:
                if mtd_strategy in ("ip_shuffle", "port_shuffle", "random"):
                    self.mtd_controller.shuffle_network(svc, intensity=0.7)
                if mtd_strategy == "service_swap":
                    self.mtd_controller.enable_decoy(svc)

            logger.info("✅ [CTI_RULE] iptables MTD 명령 수행 완료.")
        except Exception as e:
            logger.error(f"[CTI_RULE] MTD 실행 실패: {e}")

    # ------------------------------------------------------------------
    # 방어 실행
    # ------------------------------------------------------------------
    def execute_defense(self, attack_label, attack_name):
        """공격 탐지 시 방어 로직 실행 (DEFENSE_MODE에 따라 동작)"""
        current_time = time.time()
        if current_time < self.defense_cooldown:
            logger.info(f"🛡️ [Defense Skip] 쿨다운 중 ({int(self.defense_cooldown - current_time)}s 남음).")
            return

        logger.warning(f"🚨 [ALERT] 공격 탐지됨! Type: {attack_name} (ID: {attack_label}), mode={DEFENSE_MODE}")

        # 공격 유형별 방어 전략 매핑 (공통)
        mtd_strategy = "random"  # 기본값

        if "gps" in attack_name.lower():
            mtd_strategy = "ip_shuffle"
        elif "flooding" in attack_name.lower() or "dos" in attack_name.lower():
            mtd_strategy = "service_swap"
        elif "scan" in attack_name.lower() or "discovery" in attack_name.lower():
            mtd_strategy = "port_shuffle"

        # --- 방어 모드별 처리 ---
        if DEFENSE_MODE == "none":
            # No-MTD: 탐지만 수행 (비교 실험 참고용)
            logger.info("🔍 [MODE=none] MTD 방어는 수행하지 않습니다 (탐지만).")
            return

        elif DEFENSE_MODE == "cti_rule":
            # 규칙 기반 MTD: iptables_mtd_controller 직접 제어
            self._execute_cti_rule_mtd(mtd_strategy, attack_name)
            self.defense_cooldown = current_time + 30  # 30초 쿨다운
            return

        elif DEFENSE_MODE == "rl":
            # RL 기반 MTD 매니저 호출 (rl_driven_deception_manager.py)
            logger.info(f"⚔️ [DEFENSE-RL] MTD 방어 수행: {mtd_strategy}")
            try:
                # NOTE: 실제 구현에서는 전략 이름을 RLDM에 전달하거나
                #       CTI 이벤트를 shared_state로 넘기는 방식 등으로 확장 가능.
                cmd = [sys.executable, DECEPTION_MGR, "--strategy", mtd_strategy, "--oneshot"]
                # subprocess.Popen(cmd)  # 실제 실행 시 주석 해제
                logger.info("✅ RL MTD 매니저 호출 (데모용, 실제 실행은 주석 해제 필요).")
                self.defense_cooldown = current_time + 30  # 30초 쿨다운
            except Exception as e:
                logger.error(f"[DEFENSE-RL] 방어 실행 실패: {e}")
            return

        else:
            logger.warning(f"알 수 없는 DEFENSE_MODE='{DEFENSE_MODE}' - 방어를 수행하지 않습니다.")
            return

    # ------------------------------------------------------------------
    # 메인 루프
    # ------------------------------------------------------------------
    def run(self):
        logger.info("🚀 CTI Agent Started. Monitoring logs...")

        # 로그 리더 스레드 시작
        readers = []
        for name, path in TARGET_LOGS.items():
            reader = RealTimeLogReader(path, name, self.data_buffer)
            reader.start()
            readers.append(reader)

        try:
            while self.running:
                if not self.data_buffer:
                    time.sleep(0.5)
                    continue

                # 큐에서 데이터 가져오기 (최근 데이터 처리)
                while self.data_buffer:
                    log_entry = self.data_buffer.popleft()

                    # 1. 전처리
                    X_input = self.preprocess_log_to_features(log_entry)

                    # 2. 추론
                    try:
                        pred_prob = self.model.predict_proba(X_input)[0]
                        pred_idx = int(np.argmax(pred_prob))
                        confidence = float(pred_prob[pred_idx])

                        # LabelEncoder 역변환
                        if self.label_encoder is not None:
                            pred_label_id = self.label_encoder.inverse_transform([pred_idx])[0]
                        else:
                            pred_label_id = pred_idx

                        attack_name = self.id_to_name.get(pred_label_id, f"Unknown-{pred_label_id}")

                        # 3. 판단 및 대응
                        if attack_name.lower() != 'normal' and confidence > CONFIDENCE_THRESHOLD:
                            logger.info(
                                f"[PREDICT] label_id={pred_label_id}, "
                                f"name={attack_name}, conf={confidence:.3f}"
                            )
                            self.execute_defense(pred_label_id, attack_name)

                    except Exception as e:
                        # 추론 오류는 디버깅 시에만 확인
                        # logger.debug(f"Inference error: {e}")
                        pass

                time.sleep(DETECTION_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Stopping agent...")
            self.running = False
            for r in readers:
                r.running = False
                r.join()


if __name__ == "__main__":
    agent = CTIAgent()
    agent.run()
