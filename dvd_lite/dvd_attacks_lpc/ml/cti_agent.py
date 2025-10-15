#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import joblib
import pandas as pd
import numpy as np
from collections import deque
import threading
from typing import Dict, Any, Optional

# --- 경로 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# bus 디렉토리에 로그 기록을 위한 간단한 함수가 있다고 가정
BUS_LOG_PATH = os.path.join(PROJECT_ROOT, 'bus', 'bus.log')

# datetime 모듈 임포트 추가 (로그 기록 시 사용)
import datetime 

def log_bus_event(type: str, data: Dict[str, Any], source_override: str = "ai_cti_agent"):
    """간단한 버스 이벤트 로깅 함수 (ML alert용)"""
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": time.time(),
        "source": source_override,
        "type": type,
        "data": data,
    }
    try:
        with open(BUS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError:
        print("Warning: Failed to write to bus.log")
        

# --- 상수 정의 ---
MODEL_PATH = os.path.join(PROJECT_ROOT, 'ml', 'output', 'cti_classifier_model.joblib')
FEATURES_PATH = os.path.join(PROJECT_ROOT, 'ml', 'output', 'training_features.json') # 학습에 사용된 피처 목록
# ⭐️ 로그 파일 경로를 모니터 파일에 맞춰 정확하게 수정
LOG_SOURCES = {
    "system_events": os.path.join(PROJECT_ROOT, 'bus', 'bus.log'),
    "telemetry": os.path.join(PROJECT_ROOT, 'bus', 'bus_telemetry.log'),
    "network": os.path.join(PROJECT_ROOT, 'bus', 'bus_network.log'),
    "qos": os.path.join(PROJECT_ROOT, 'bus', 'bus_qos.log'),
}
TIME_WINDOW_SEC = 5.0  # 특징 추출을 위한 시간 창
PREDICTION_INTERVAL_SEC = 1.0 # 1초마다 예측 수행
CONFIDENCE_THRESHOLD = 0.70 # 탐지 신뢰도 임계값

# ==============================================================================
# 실시간 특징 공학 (Feature Engineering)
# ==============================================================================
def create_features_from_window(df_window: pd.DataFrame) -> Optional[pd.DataFrame]:
    """시간 창 데이터프레임으로부터 통계적 특징 벡터를 생성합니다."""
    if df_window.empty:
        return None

    features = {}
    
    # 1. 이벤트 타입별 발생 빈도 계산
    event_counts = df_window['type'].value_counts()
    for event_type, count in event_counts.items():
        features[f'event_count_{event_type}'] = count

    # 2. 주요 수치 데이터에 대한 통계량 계산
    numeric_cols = {
        'data.alt_m': 'alt', 'data.relative_alt_m': 'rel_alt',
        'data.groundspeed_ms': 'gs', 'data.vx': 'vx', 'data.vy': 'vy', 'data.vz': 'vz',
        'data.xacc': 'xacc', 'data.yacc': 'yacc', 'data.zacc': 'zacc',
        'data.pitch_deg': 'pitch', 'data.roll_deg': 'roll', 
        'data.avg_rtt_ms': 'rtt',
        'data.jitter_ms': 'jitter',
        'data.packet_loss_pct': 'loss',
        'data.length': 'pkt_len',
        'data.inter_arrival_time_ms': 'pkt_iat',
        'data.cpu_percent': 'cpu',
        'data.memory_mb': 'mem',
    }
    
    for col, prefix in numeric_cols.items():
        if col in df_window.columns:
            # 숫자로 변환하고 NaN 제거
            series = pd.to_numeric(df_window[col], errors='coerce').dropna()
            if not series.empty:
                features[f'{prefix}_mean'] = series.mean()
                features[f'{prefix}_std'] = series.std()
                features[f'{prefix}_max'] = series.max()
                features[f'{prefix}_min'] = series.min()

    # 3. 카테고리 데이터 처리 (드론 모드 비율)
    if 'data.mode' in df_window.columns:
        # ⭐️ 모드가 시간 창 내에서 차지하는 비율을 계산 (data_builder와 동일)
        mode_counts = df_window['data.mode'].value_counts(normalize=True)
        for mode, ratio in mode_counts.items():
            features[f'mode_ratio_{mode}'] = ratio
            
    if not features: return None
    
    return pd.DataFrame([features]).fillna(0)


# ==============================================================================
# CTI 에이전트 메인 로직
# ==============================================================================
def follow(file, queue: deque):
    """파일의 새로운 라인을 지속적으로 읽어 deque에 추가합니다."""
    file.seek(0, os.SEEK_END)
    while True:
        line = file.readline()
        if not line:
            time.sleep(0.05)
            continue
        try:
            queue.append(json.loads(line))
        except json.JSONDecodeError:
            pass

def main():
    print("🚀 [AI-CTI Agent v4.0] 지능형 위협 분류 에이전트 시작")

    # 1. 모델 및 피처 목록 로드
    print(f"[*] AI 모델 로딩 대기 중: '{MODEL_PATH}'")
    while not (os.path.exists(MODEL_PATH) and os.path.exists(FEATURES_PATH)):
        time.sleep(2)
        
    try:
        model = joblib.load(MODEL_PATH)
        with open(FEATURES_PATH, 'r') as f:
            training_features = json.load(f)['features']
        print(f"✅ AI 모델 및 {len(training_features)}개 피처 목록 로드 완료.")
    except Exception as e:
        print(f"❌ 오류: AI 모델/피처 파일 로드 실패: {e}", file=sys.stderr)
        return

    # 2. 실시간 로그 수집 시작
    log_queues = {name: deque(maxlen=5000) for name in LOG_SOURCES.keys()}
    for name, path in LOG_SOURCES.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            # 파일이 없으면 생성, 있으면 끝까지 이동하여 새로운 라인만 읽음
            f = open(path, 'a+') 
            f.seek(0, os.SEEK_END)
            threading.Thread(target=follow, args=(f, log_queues[name]), daemon=True).start()
        except Exception as e:
            print(f"❌ 로그 파일 '{path}' 열기 실패: {e}", file=sys.stderr)
            return

    print("[*] 모든 로그 소스 감시 시작...")
    
    time_window_data = deque()
    last_prediction_time = 0
    
    while True:
        # 3. 최신 로그를 시간 창에 추가
        now = time.time()
        for queue in log_queues.values():
            while queue:
                log = queue.popleft()
                if 'ts' not in log: log['ts'] = now
                time_window_data.append(log)
        
        # 4. 오래된 데이터 제거
        while time_window_data and (now - time_window_data[0].get('ts', 0)) > TIME_WINDOW_SEC:
            time_window_data.popleft()

        if not time_window_data:
            time.sleep(0.2)
            continue
            
        # 5. 예측 주기마다 위협 분석 수행
        if (now - last_prediction_time) > PREDICTION_INTERVAL_SEC:
            last_prediction_time = now
            
            # 원시 로그를 정형화된 데이터프레임으로 변환
            df_raw = pd.json_normalize(list(time_window_data), sep='.')
            
            # 실시간 특징 벡터 생성
            live_features_df = create_features_from_window(df_raw)
            if live_features_df is None:
                continue

            # ⭐️ 안정화된 피처 준비 (FutureWarning 해결)
            # 학습에 사용된 피처 목록으로 빈 DataFrame을 생성하고, live_features_df의 값으로 업데이트
            X_live = pd.DataFrame(0.0, index=[0], columns=training_features)
            
            # live_features_df의 값을 X_live에 복사
            for col in live_features_df.columns:
                if col in X_live.columns:
                    X_live.loc[0, col] = live_features_df.loc[0, col]

            # 6. 예측 및 결과 분석
            prediction = model.predict(X_live)[0]
            probabilities = model.predict_proba(X_live)[0]
            confidence = probabilities.max()
            
            # 'normal'이 아닌 다른 클래스가 특정 신뢰도 이상으로 예측될 경우
            if prediction != 'normal' and confidence >= CONFIDENCE_THRESHOLD:
                
                # 판단의 근거가 된 상위 특징 찾기
                try:
                    # model이 Pipeline이 아닌 RandomForestClassifier 객체라고 가정 (train_classifier.py에 따름)
                    importances = model.feature_importances_ 
                    
                    # 현재 윈도우의 특징 값 * 중요도를 기반으로 증거 추출
                    feature_importance = sorted(zip(training_features, importances * X_live.iloc[0].values), 
                                                key=lambda x: x[1], reverse=True)
                    # 값이 0보다 큰 상위 3개 특징만 증거로 사용
                    top_evidence = {f: round(v, 4) for f, v in feature_importance[:3] if v > 0}
                except Exception:
                    top_evidence = {"error": "Failed to calculate feature importance."}

                context = {
                    "detected_attack_category": prediction,
                    "confidence": f"{confidence:.2%}",
                    "evidence_features": top_evidence,
                    "model_path": os.path.basename(MODEL_PATH),
                    "window_size_sec": TIME_WINDOW_SEC,
                    "log_count_in_window": len(time_window_data)
                }
                
                log_bus_event("ai_cti_alert", context)
                print(f"  🚨 \033[91m[AI-CTI] 위협 탐지! -> '{prediction.upper()}' (신뢰도: {context['confidence']})\033[0m")
                print(f"      - 근거: {json.dumps(top_evidence, indent=2)}")

        time.sleep(0.1)

if __name__ == "__main__":
    main()
