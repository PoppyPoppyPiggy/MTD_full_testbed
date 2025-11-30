
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
CTI_POLICY_PATH = os.path.join(PROJECT_ROOT, "mtd", "shared_state", "cti_policy.json")
CTI_STATUS_PATH = os.path.join(PROJECT_ROOT, "mtd", "shared_state", "cti_status.json")

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
@@ -87,94 +89,126 @@ class RealTimeLogReader(threading.Thread):
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
        self.detection_threshold = CONFIDENCE_THRESHOLD
        self.ban_duration_sec = 300
        self._policy_mtime = None

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

        # CTI 정책 초기 로드 (RL이 cti_policy.json을 덮어쓰면 탐지/밴 파라미터를 즉시 반영)
        self._refresh_cti_policy(force=True)

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
    # CTI 정책 파일 로딩
    # ------------------------------------------------------------------
    def _refresh_cti_policy(self, force: bool = False):
        """cti_policy.json 변경사항을 반영해 탐지/밴 파라미터를 업데이트한다."""
        try:
            if not os.path.exists(CTI_POLICY_PATH):
                return

            mtime = os.path.getmtime(CTI_POLICY_PATH)
            if self._policy_mtime is not None and mtime == self._policy_mtime and not force:
                return

            with open(CTI_POLICY_PATH, "r", encoding="utf-8") as f:
                policy = json.load(f)

            self.detection_threshold = float(policy.get("detection_threshold", self.detection_threshold))
            self.ban_duration_sec = float(policy.get("ban_duration_sec", self.ban_duration_sec))
            self._policy_mtime = mtime
            logger.info(
                f"CTI 정책 적용: detection_threshold={self.detection_threshold:.3f}, "
                f"ban_duration_sec={self.ban_duration_sec}"
            )
        except Exception as e:
            logger.error(f"CTI 정책 로드 실패: {e}")

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
@@ -253,153 +287,190 @@ class CTIAgent:
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
            # RL이 설정한 블랙리스트 지속 시간을 규칙 기반 MTD에도 반영
            self.mtd_controller.apply_blacklist_policy(aggression=0.8, duration_sec=self.ban_duration_sec)
            for svc in target_services:
                if mtd_strategy in ("ip_shuffle", "port_shuffle", "random"):
                    self.mtd_controller.shuffle_network(svc, intensity=0.7)
                if mtd_strategy == "service_swap":
                    self.mtd_controller.enable_decoy(svc)

            logger.info("✅ [CTI_RULE] iptables MTD 명령 수행 완료.")
        except Exception as e:
            logger.error(f"[CTI_RULE] MTD 실행 실패: {e}")

    # ------------------------------------------------------------------
    # CTI 상태 파일 기록
    # ------------------------------------------------------------------
    def _write_cti_status(
        self,
        attack_type: str,
        attack_confidence: float,
        detection_threshold: float,
        ban_duration_sec: float,
    ) -> None:
        """CTI 상태를 shared_state/cti_status.json에 기록한다."""
        try:
            os.makedirs(os.path.dirname(CTI_STATUS_PATH), exist_ok=True)
            status = {
                "is_attack_detected": True,
                "attack_type": attack_type,
                "attack_confidence": attack_confidence,
                "detection_threshold": detection_threshold,
                "ban_duration_sec": ban_duration_sec,
                "last_alert_time": datetime.utcnow().isoformat() + "Z",
            }
            with open(CTI_STATUS_PATH, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"cti_status.json 기록 실패: {e}")

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
                subprocess.Popen(cmd)
                logger.info("✅ RL MTD 매니저 호출 완료.")
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
                # RL이 조정한 cti_policy.json 변경분을 주기적으로 반영
                self._refresh_cti_policy()

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
                        if attack_name.lower() != 'normal' and confidence > self.detection_threshold:
                            logger.info(
                                f"[PREDICT] label_id={pred_label_id}, "
                                f"name={attack_name}, conf={confidence:.3f}"
                            )
                            self._write_cti_status(
                                attack_type=attack_name,
                                attack_confidence=confidence,
                                detection_threshold=self.detection_threshold,
                                ban_duration_sec=self.ban_duration_sec,
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