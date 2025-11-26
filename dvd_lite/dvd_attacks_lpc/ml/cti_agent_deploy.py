#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 디렉토리: dvd_lite/dvd_attacks_lpc/ml
# 파일명: cti_agent_deploy.py
# 설명: [Deployment] 학습된 모델을 로드하여 실시간 로그를 분석하고
#       방어 모드(DEFENSE_MODE)에 따라 MTD를 수행하거나, 탐지만 수행하는 CTI Agent.
#
# 방어 모드:
#   - "none"      : MTD 아무 것도 하지 않고, 공격 탐지만 수행 (Case 0 / Case 1에서 사용)
#   - "cti_rule"  : 규칙 기반 MTD (공격 유형에 따라 iptables_mtd_controller로 즉시 방어)
#   - "rl"        : RL 기반 MTD (실제 MTD는 rl_driven_deception_manager가 수행한다고 가정, 여기선 신호만/로그만)
#
# 주의:
#   - Static MTD (정적/시간 기반)는 보통 별도 스크립트/크론으로 돌리는 게 깔끔함.
#     그 경우 CTI Agent는 DEFENSE_MODE="none"으로 두고, 공격 탐지만 해서 데이터셋/지표에 쓰면 됨.

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
from typing import Optional, Dict, Any

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

# mtd 모듈 import (iptables_mtd_controller)
MTD_DIR = os.path.join(PROJECT_ROOT, "mtd")
if MTD_DIR not in sys.path:
    sys.path.append(MTD_DIR)
try:
    from mtd.iptables_mtd_controller import IptablesMTDController  # type: ignore
except Exception as e:
    IptablesMTDController = None
    logger.warning(f"iptables_mtd_controller import 실패: {e}")

# --- 모니터링할 로그 파일 목록 (bus.log 제외) ---
TARGET_LOGS = {
    "network": os.path.join(BUS_DIR, "bus_network.log"),
    "telemetry": os.path.join(BUS_DIR, "bus_telemetry.log"),
    "qos": os.path.join(BUS_DIR, "bus_qos.log"),
    "container": os.path.join(BUS_DIR, "bus_container_telemetry.log"),
    "system": os.path.join(BUS_DIR, "bus_system_events.log")
}

# --- 설정 ---
DETECTION_INTERVAL = 1.0   # 초 단위 탐지 주기
FEATURE_WINDOW_SIZE = 10   # (여기서는 단일 로그 기준이지만 확장 가능)
CONFIDENCE_THRESHOLD = 0.7 # 공격 판단 임계값 (확률)

# --- 방어 모드 설정 ---
#   환경변수 CTI_DEFENSE_MODE 로 override 가능:
#   - "none"     : 방어 없음 (탐지만)  -> Case 0, Case 1
#   - "cti_rule" : CTI 규칙 기반 MTD  -> Case 2
#   - "rl"       : RL + CTI MTD       -> Case 3 (실제 MTD는 rl_driven_deception_manager가 담당)
DEFENSE_MODE = os.environ.get("CTI_DEFENSE_MODE", "cti_rule").lower()
if DEFENSE_MODE not in ("none", "cti_rule", "rl"):
    logger.warning(f"알 수 없는 DEFENSE_MODE={DEFENSE_MODE}, 'cti_rule'로 fallback.")
    DEFENSE_MODE = "cti_rule"

# 정적 MTD는 여기서 다루지 않고, 별도 스크립트 + DEFENSE_MODE='none' 조합으로 운영하는 것을 권장.

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
        self.id_to_name: Dict[Any, str] = {}
        self.feature_names = None
        self.data_buffer = deque(maxlen=1000) # 최근 로그 버퍼
        self.running = True
        self.defense_cooldown = 0.0  # 방어 후 쿨다운 (epoch time)

        # MTD 컨트롤러 (cti_rule 모드에서 사용)
        self.mtd_controller: Optional[IptablesMTDController] = None
        self.mtd_service_name = "mavlink_fc"  # iptables_mtd_controller의 service name과 일치 필요
        self._init_mtd_if_needed()

        # 모델 로드
        self.load_model()

        logger.info(f"CTI-Agent Defense Mode = {DEFENSE_MODE}")

    # ------------------------------------------------------------------
    # MTD 초기화 (cti_rule 모드에서만 실제 사용)
    # ------------------------------------------------------------------
    def _init_mtd_if_needed(self):
        if DEFENSE_MODE != "cti_rule":
            return
        if IptablesMTDController is None:
            logger.error("cti_rule 모드인데 IptablesMTDController를 import하지 못했습니다.")
            return

        try:
            self.mtd_controller = IptablesMTDController(dry_run=True)
            # 기본 FC MAVLink 서비스 등록 (iptables_mtd_controller의 DEFAULT_TARGETS["FC"] 기반)
            self.mtd_controller.register_service(self.mtd_service_name, "FC", 0)
            logger.info(f"MTD Controller 초기화 완료. 서비스 '{self.mtd_service_name}' 등록.")
        except Exception as e:
            logger.error(f"MTD Controller 초기화 실패: {e}")
            self.mtd_controller = None

    # ------------------------------------------------------------------
    # 모델 로드
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
                feat_path = os.path.join(os.path.dirname(MODEL_PATH), 'training_features.json')
                if os.path.exists(feat_path):
                    with open(feat_path, 'r', encoding='utf-8') as f:
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
                self.id_to_name = {}

            if self.feature_names is None:
                logger.critical("❌ feature_names를 결정할 수 없습니다. 학습 시 사용한 피처 이름 정보를 제공해야 합니다.")
                sys.exit(1)

            logger.info("✅ Model loaded successfully.")

        except Exception as e:
            logger.critical(f"❌ 모델 로드 실패: {e}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # 로그 → 피처 변환
    # ------------------------------------------------------------------
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
    # 방어 실행 (Defense Mode별로 분기)
    # ------------------------------------------------------------------
    def execute_defense(self, attack_label, attack_name):
        """공격 탐지 시 방어 로직 실행 (DEFENSE_MODE에 따라 동작 다름)"""
        current_time = time.time()
        if current_time < self.defense_cooldown:
            logger.info(
                f"🛡️ [Defense Skip] 쿨다운 중 ({int(self.defense_cooldown - current_time)}s 남음)."
            )
            return

        logger.warning(f"🚨 [ALERT] 공격 탐지됨! Type: {attack_name} (ID: {attack_label})")

        # Case 0 / Case 1: 방어 없음 (탐지 로그만 남김)
        if DEFENSE_MODE == "none":
            logger.info("[NO_MTD] 방어 로직은 수행하지 않습니다 (실험용 baseline).")
            return

        # 공격명 기반 간단 전략 태깅 (cti_rule / rl 모두에서 사용 가능)
        mtd_strategy = "random"  # 기본값
        lower_name = attack_name.lower()
        if "gps" in lower_name:
            mtd_strategy = "ip_shuffle"
        elif "flood" in lower_name or "dos" in lower_name:
            mtd_strategy = "service_swap"
        elif "scan" in lower_name or "discovery" in lower_name:
            mtd_strategy = "port_shuffle"

        # Case 2: CTI 규칙 기반 MTD (직접 iptables MTD를 건드림)
        if DEFENSE_MODE == "cti_rule":
            self._execute_cti_rule_mtd(mtd_strategy)
        # Case 3: RL + CTI (실제 MTD는 rl_driven_deception_manager가 PPO 정책으로 수행)
        elif DEFENSE_MODE == "rl":
            self._notify_rl_mtd(mtd_strategy)

        # 공통 쿨다운 (너무 자주 방어하지 않도록)
        self.defense_cooldown = current_time + 30.0  # 30초 쿨다운

    # ------------------------------------------------------------------
    # Case 2: CTI 규칙 기반 MTD
    # ------------------------------------------------------------------
    def _execute_cti_rule_mtd(self, mtd_strategy: str):
        """
        규칙 기반 MTD: 공격 유형에 따라 iptables_mtd_controller를 직접 제어.
        - ip_shuffle  : shuffle_network()
        - port_shuffle: shuffle_network() (포트도 바뀔 확률)
        - service_swap: enable_decoy()
        """
        if self.mtd_controller is None:
            logger.error("MTD Controller가 초기화되지 않아 cti_rule 방어를 수행할 수 없습니다.")
            return

        logger.info(f"⚔️ [DEFENSE-CTI_RULE] MTD 방어 수행: {mtd_strategy}")

        try:
            if mtd_strategy in ("ip_shuffle", "port_shuffle", "random"):
                # intensity는 대략 0.7 정도로 (IP/Port 모두 꽤 자주 바뀌도록)
                self.mtd_controller.shuffle_network(self.mtd_service_name, intensity=0.7)
            if mtd_strategy == "service_swap":
                self.mtd_controller.enable_decoy(self.mtd_service_name)
            # service_swap가 아니고, 이전에 decoy가 켜져 있었으면 끄고 싶으면:
            # else:
            #     self.mtd_controller.disable_decoy(self.mtd_service_name)

            logger.info("✅ [CTI_RULE] iptables MTD 명령 수행 완료.")
        except Exception as e:
            logger.error(f"[CTI_RULE] MTD 실행 실패: {e}")

    # ------------------------------------------------------------------
    # Case 3: RL + CTI
    # ------------------------------------------------------------------
    def _notify_rl_mtd(self, mtd_strategy: str):
        """
        RL 기반 MTD: 여기서는 RLDrivenDeceptionManager가 이미 실행 중이라고 가정.
        - CTI Agent는 '지금 공격이 있었다'라는 사실과, 대략적인 공격 카테고리(mtd_strategy)를
          로그로 남기거나, 나중에 연동할 IPC/파일/메시지 큐 등에 기록하는 역할만 담당.
        - 지금은 간단히 로그 + (옵션) oneshot 호출 예시만 남겨둠.
        """
        logger.info(f"⚔️ [DEFENSE-RL] RL 기반 MTD에 공격 이벤트 알림: strategy_hint={mtd_strategy}")

        # (선택 사항) rl_driven_deception_manager.py를 oneshot 모드로 한번 호출하는 예시
        # 실제로는 RLDM을 상시 데몬으로 띄우고, 이 함수는 파일/소켓 기반 신호만 남기는 게 더 적절함.
        try:
            # 간단 데모용 – 실제 실험에서는 주석 처리하고 RLDM을 별도 프로세스로 돌리는 구조 추천
            cmd = [
                sys.executable,
                DECEPTION_MGR,
                "--model-path", os.path.join(PROJECT_ROOT, "mtd", "runs", "latest", "final_policy.pth"),
                "--norm-meta-path", os.path.join(PROJECT_ROOT, "mtd", "runs", "latest", "norm_metadata.json"),
                "--attacker-config", os.path.join(PROJECT_ROOT, "mtd", "config", "attacker_config.json"),
                "--service-name", self.mtd_service_name,
                "--dry-run",
                "--max-steps", "1",
                "--interval-sec", "0.1",
                "--use-simple-runtime",
            ]
            # subprocess.Popen(cmd)  # 실제 호출하고 싶으면 주석 해제
            logger.info("[RL-MTD] (데모용) rl_driven_deception_manager oneshot 호출 명령 생성.")
        except Exception as e:
            logger.error(f"[RL-MTD] RL 매니저 연동 실패: {e}")

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
                            # 필요하다면 "연속 N번 이상" 조건 추가 가능
                            self.execute_defense(pred_label_id, attack_name)

                    except Exception:
                        # 너무 시끄러우면 debug로만
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
