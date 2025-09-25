import os
import sys
import json
import time
import joblib
import pandas as pd
from collections import deque
import threading

# --- 경로 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from bus.logger import log_bus_event

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'output', 'cti_classifier_model.joblib')
LOG_SOURCES = {
    "events": os.path.join(PROJECT_ROOT, 'bus', 'bus.log'),
    "telemetry": os.path.join(PROJECT_ROOT, 'bus', 'bus_dvd.log'),
}
TIME_WINDOW_SEC = 3.0  # 판단 시간 창을 약간 늘려 시계열 피처의 효과를 극대화
PREDICTION_INTERVAL_SEC = 0.5

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
    print("[*] CTI 분류 AI 에이전트 (v3.0, Ensemble) 시작.")
    
    print(f"[*] AI 모델 로딩 대기 중: '{MODEL_PATH}'")
    while not os.path.exists(MODEL_PATH):
        time.sleep(2)
        
    try:
        model = joblib.load(MODEL_PATH)
        print("[*] AI 모델 로드 완료.")
    except Exception as e:
        print(f"[!] 오류: AI 모델 파일 '{MODEL_PATH}' 로드 실패: {e}")
        return

    # 메모리 최적화를 위해 고정 크기 deque 사용
    log_queues = {name: deque(maxlen=2000) for name in LOG_SOURCES.keys()}

    for name, path in LOG_SOURCES.items():
        while not os.path.exists(path): 
            print(f"[*] 로그 파일 대기 중: {path}")
            time.sleep(1)
        try:
            f = open(path, 'r', errors='ignore')
            threading.Thread(target=follow, args=(f, log_queues[name]), daemon=True).start()
        except FileNotFoundError:
            print(f"[!] 로그 파일 없음: {path}")
            return

    print("[*] 모든 로그 소스 감시 시작...")
    
    # 현재 데이터 창을 관리하기 위한 deque
    time_window_data = deque()
    last_prediction_time = 0
    
    while True:
        new_data_found = False
        for name, queue in log_queues.items():
            while queue:
                log = queue.popleft()
                log['log_source'] = name
                log['log_type'] = log.get('type', 'unknown')
                time_window_data.append(log)
                new_data_found = True
        
        now = time.time()
        
        # 오래된 데이터 제거
        while time_window_data and (now - time_window_data[0].get('ts', 0)) > TIME_WINDOW_SEC:
            time_window_data.popleft()

        if not time_window_data:
            time.sleep(0.2)
            continue
            
        if (now - last_prediction_time) > PREDICTION_INTERVAL_SEC:
            last_prediction_time = now
            
            df_window = pd.json_normalize(list(time_window_data), sep='_')
            
            try:
                training_cols = model.steps[0].get_feature_names_out()
            except AttributeError:
                # 파이프라인의 ColumnTransformer 내부의 피처 이름을 가져오는 로직
                transformers = model.steps[0][1].transformers_
                training_cols = []
                for name, _, features in transformers:
                    if name == 'num':
                        training_cols.extend(features)
                    elif name == 'cat':
                        # OneHotEncoder의 출력 피처 이름을 가져옴
                        ohe_feature_names = model.steps[0][1].named_transformers_['cat']['onehot'].get_feature_names_out(features)
                        training_cols.extend(ohe_feature_names)

            # 학습에 사용된 피처가 실시간 데이터에 없으면 0으로 채움
            for col in training_cols:
                if col not in df_window.columns:
                    df_window[col] = 0
            
            # 피처 순서 맞추기 및 NaN 처리
            X_live = df_window[training_cols].fillna(0)
            
            if X_live.empty:
                continue

            latest_point = X_live.iloc[[-1]]
            prediction = model.predict(latest_point)[0]
            confidence = max(model.predict_proba(latest_point)[0])
            
            if prediction == 'Attack' and confidence > 0.75: # 신뢰도 임계값 설정
                latest_log = time_window_data[-1]
                context = {
                    "confidence": f"{confidence:.2%}",
                    "source_event_type": latest_log.get('log_type'),
                    "drone_mode": latest_log.get('data_mode', 'N/A'),
                    "triggering_log": latest_log,
                }
                
                log_bus_event("ai_cti_classification", context)

                print(f"  \033[91m[AI-CTI] 위협 탐지! (신뢰도: {context['confidence']}, 모드: {context['drone_mode']})\033[0m <= {context['source_event_type']}")
        
        time.sleep(0.1)

if __name__ == "__main__":
    main()