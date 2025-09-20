import os
import sys
import json
import time
import joblib

# 프로젝트 루트 경로 설정 (bus.logger를 import하기 위함)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from bus.logger import log_bus_event

MODEL_PATH = "cti_classifier_model.joblib"
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "bus", "bus.log")

def follow(file):
    file.seek(0, os.SEEK_END)
    while True:
        line = file.readline()
        if not line:
            time.sleep(0.1)
            continue
        yield line

def main():
    print("[*] CTI 분류 AI 에이전트 시작.")
    try:
        model = joblib.load(MODEL_PATH)
        print(f"[*] AI 모델 로드 완료: '{MODEL_PATH}'")
    except FileNotFoundError:
        print(f"[!] 오류: AI 모델 파일 '{MODEL_PATH}' 없음. train_classifier.py를 먼저 실행하세요.")
        return

    print(f"[*] 이벤트 버스 감시 시작: '{LOG_FILE_PATH}'")
    
    while not os.path.exists(LOG_FILE_PATH):
        time.sleep(1)

    with open(LOG_FILE_PATH, 'r') as logfile:
        for line in follow(logfile):
            try:
                log = json.loads(line)
                if log.get('type') == 'ai_cti_classification': continue # AI가 쓴 로그는 무시
                    
                log_text = f"{log.get('type', '')} {' '.join([f'{k}_{v}' for k, v in log.get('data', {}).items()])}"
                
                prediction = model.predict([log_text])[0]
                confidence = max(model.predict_proba([log_text])[0])
                
                classification_data = {
                    "predicted_category": prediction,
                    "confidence": f"{confidence:.2%}",
                    "source_event": log.get('type')
                }
                log_bus_event("ai_cti_classification", classification_data)
                
                color_map = {"기동부": "\033[94m", "통신부": "\032[92m", "제어부": "\033[91m"}
                color = color_map.get(prediction, "\033[0m")
                print(f"  {color}[AI 분류] {prediction} (신뢰도: {confidence:.2%})\033[0m <= {log.get('type')}")
            except: pass

if __name__ == "__main__":
    main()