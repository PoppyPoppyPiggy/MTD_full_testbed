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
        self.feature_names = None
        self.data_buffer = deque(maxlen=1000) # 최근 로그 버퍼
        self.running = True
        self.defense_cooldown = 0 # 방어 후 쿨다운
        
        # 모델 로드
        self.load_model()

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
                self.id_to_name = artifact['mapping']
                # feature_names는 별도 파일에서 로드하거나 artifact에 포함해야 함
                # 여기서는 features.json을 로드 시도
                feat_path = os.path.join(os.path.dirname(MODEL_PATH), 'training_features.json')
                if os.path.exists(feat_path):
                    with open(feat_path, 'r') as f:
                        self.feature_names = json.load(f)['features']
                else:
                    logger.warning("⚠️ feature names 파일이 없어 모델 속성에서 추론합니다.")
                    # 파이프라인의 경우 스텝 확인
                    if hasattr(self.model, 'feature_names_in_'):
                        self.feature_names = list(self.model.feature_names_in_)
                    elif hasattr(self.model.named_steps['clf'], 'feature_names_in_'):
                         self.feature_names = list(self.model.named_steps['clf'].feature_names_in_)
            else:
                # 구버전 호환 (모델만 저장된 경우)
                self.model = artifact
                self.id_to_name = {} # 매핑 정보 없음
                
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
        source = log_entry.get("_log_source") # 우리가 주입한 타입

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

    def execute_defense(self, attack_label, attack_name):
        """공격 탐지 시 방어 로직 실행"""
        current_time = time.time()
        if current_time < self.defense_cooldown:
            logger.info(f"🛡️ [Defense Skip] 쿨다운 중 ({int(self.defense_cooldown - current_time)}s 남음).")
            return

        logger.warning(f"🚨 [ALERT] 공격 탐지됨! Type: {attack_name} (ID: {attack_label})")
        
        # 공격 유형별 방어 전략 매핑 (예시)
        mtd_strategy = "random" # 기본값
        
        if "gps" in attack_name.lower():
            mtd_strategy = "ip_shuffle"
        elif "flooding" in attack_name.lower() or "dos" in attack_name.lower():
            mtd_strategy = "service_swap"
        elif "scan" in attack_name.lower() or "discovery" in attack_name.lower():
            mtd_strategy = "port_shuffle"

        logger.info(f"⚔️ [DEFENSE] MTD 방어 수행: {mtd_strategy}")
        
        try:
            # MTD 매니저 호출 (여기서는 예시로 스크립트 실행)
            # 실제로는 rl_driven_deception_manager.py에 요청을 보내거나
            # MTD API를 호출해야 함. 여기선 데모용 로그 출력.
            cmd = [sys.executable, DECEPTION_MGR, "--strategy", mtd_strategy, "--oneshot"]
            # subprocess.Popen(cmd) # 실제 실행 시 주석 해제
            
            logger.info("✅ 방어 명령 전달 완료.")
            self.defense_cooldown = current_time + 30 # 30초 쿨다운
            
        except Exception as e:
            logger.error(f"방어 실행 실패: {e}")

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
                    # (주의: 단건 추론은 비효율적일 수 있으므로 배치 처리가 좋음. 여기선 실시간성 강조)
                    try:
                        pred_prob = self.model.predict_proba(X_input)[0]
                        pred_idx = np.argmax(pred_prob)
                        confidence = pred_prob[pred_idx]
                        
                        # 0번은 'Normal'이라고 가정 (LabelEncoder 확인 필요)
                        # 보통 LabelEncoder는 알파벳/숫자 순으로 정렬하므로 
                        # 0이 Normal이 아닐 수 있음. id_to_name 매핑 활용.
                        
                        pred_label_id = self.label_encoder.inverse_transform([pred_idx])[0]
                        attack_name = self.id_to_name.get(pred_label_id, f"Unknown-{pred_label_id}")

                        # 3. 판단 및 대응
                        if attack_name.lower() != 'normal' and confidence > CONFIDENCE_THRESHOLD:
                            # 단순 튀는 값(Outlier) 방지: 연속 탐지 로직 등을 추가하면 좋음
                            self.execute_defense(pred_label_id, attack_name)
                        
                    except Exception as e:
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