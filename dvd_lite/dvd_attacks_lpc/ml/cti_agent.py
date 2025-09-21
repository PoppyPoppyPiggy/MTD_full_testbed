import os
import sys
import json
import time
import joblib
import pandas as pd
from collections import deque
import threading

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from bus.logger import log_bus_event

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'output', 'cti_classifier_model.joblib')
LOG_SOURCES = {
    "events": os.path.join(PROJECT_ROOT, 'bus', 'bus.log'),
    "telemetry": os.path.join(PROJECT_ROOT, 'bus', 'bus_dvd.log'),
}
TIME_WINDOW_SEC = 2.0

def follow(file, queue):
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
    print("[*] CTI 분류 AI 에이전트 (v2.0) 시작.")
    try:
        model = joblib.load(MODEL_PATH)
        print(f"[*] AI 모델 로드 완료: '{MODEL_PATH}'")
    except FileNotFoundError:
        print(f"[!] 오류: AI 모델 파일 '{MODEL_PATH}' 없음. train_classifier.py를 먼저 실행하세요.")
        return

    log_queues = {name: deque() for name in LOG_SOURCES.keys()}

    for name, path in LOG_SOURCES.items():
        while not os.path.exists(path): time.sleep(1)
        f = open(path, 'r', errors='ignore')
        threading.Thread(target=follow, args=(f, log_queues[name]), daemon=True).start()

    print("[*] 모든 로그 소스 감시 시작...")
    
    current_data = []
    last_prediction_time = 0
    while True:
        new_data_found = False
        for name, queue in log_queues.items():
            while queue:
                log = queue.popleft()
                log['log_source'] = name
                log['log_type'] = log.get('type', 'unknown')
                current_data.append(log)
                new_data_found = True
        
        if not new_data_found and not current_data:
            time.sleep(0.2)
            continue
            
        now = time.time()
        current_data = [d for d in current_data if now - d.get('ts', 0) < TIME_WINDOW_SEC]
        
        # 0.5초마다 한번씩만 예측 수행
        if current_data and (now - last_prediction_time > 0.5):
            df_window = pd.json_normalize(current_data, sep='_')
            
            # 학습 시 사용한 컬럼 정보가 모델에 저장되어 있음
            training_cols = model.steps[0][1].feature_names_in_
            for col in training_cols:
                if col not in df_window.columns:
                    df_window[col] = pd.NA
            
            X_live = df_window[training_cols]
            
            prediction = model.predict(X_live)[-1] # 마지막 데이터 포인트로 예측
            confidence = max(model.predict_proba(X_live)[-1])
            
            if prediction == 'Attack':
                classification_data = {
                    "predicted_label": prediction,
                    "confidence": f"{confidence:.2%}",
                    "source_event": X_live['log_type'].iloc[-1]
                }
                log_bus_event("ai_cti_classification", classification_data)

                print(f"  \033[91m[AI-CTI] 위협 탐지 (신뢰도: {confidence:.2%})\033[0m <= {X_live['log_type'].iloc[-1]}")
            
            last_prediction_time = now
        
        time.sleep(0.1)

if __name__ == "__main__":
    main()