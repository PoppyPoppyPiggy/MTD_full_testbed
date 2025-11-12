#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI (Cyber Threat Intelligence) Agent

- (가상) 'monitors'가 생성한 로그/이벤트 데이터를 읽어옵니다.
- 'cti_classifier_model.joblib'를 사용해 위협을 분류합니다.
- [신규] 분석 결과를 'cti_threat_assessment.json' 파일에 주기적으로 씁니다.
"""

import os
import sys
import time
import json
import joblib
import random
import numpy as np

# --- 경로 설정 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# ML 모델 경로
MODEL_PATH = os.path.join(script_dir, 'cti_classifier_model.joblib')

# Scorer가 읽을 파일 경로
STATE_DIR = os.path.join(parent_dir, 'mtd', 'shared_state')
os.makedirs(STATE_DIR, exist_ok=True) # shared_state 디렉토리 생성
CTI_ASSESSMENT_FILE = os.path.join(STATE_DIR, 'cti_threat_assessment.json')

# 모니터가 생성하는 (가상의) 이벤트 로그 파일
EVENT_LOG_FILE = os.path.join(parent_dir, 'logs', 'system_events.log') # 예시 경로

class CTIAnalyzer:
    def __init__(self, model_path):
        print(f"[CTI] CTI 위협 분석 에이전트 초기화.")
        print(f"[CTI] CTI 평가 파일 경로: {CTI_ASSESSMENT_FILE}")
        try:
            self.model = joblib.load(model_path)
            print(f"[CTI] ML 모델 로드 성공: {model_path}")
        except FileNotFoundError:
            print(f"[CTI] Error: ML 모델({model_path})을 찾을 수 없습니다!", file=sys.stderr)
            print("[CTI] -> '랜덤 시뮬레이션 모드'로 대신 실행합니다.")
            self.model = None
        except Exception as e:
            print(f"[CTI] Error: ML 모델 로드 실패: {e}", file=sys.stderr)
            self.model = None
            
        self.attack_types = ["wifi_slow_scan", "gps_slow_spoof", "companion-computer-takeover"]
        self.attack_stages = ["Reconnaissance", "Exploitation", "Breach"]
        self.threat_levels = ["NONE", "LOW", "MEDIUM", "HIGH"]

    def read_monitor_events(self):
        """(가상) 모니터 로그 파일에서 이벤트를 읽어옵니다."""
        # TODO: 이 부분은 실제 'monitors'의 출력 방식에 맞춰 수정 필요
        # 지금은 랜덤 데이터 생성으로 대체
        event_count = random.randint(5, 200)
        # (가상) 100개 이상의 이벤트가 감지되면 위협으로 간주
        if event_count > 100:
            print(f"[CTI] {event_count}개 이벤트 감지. ML 모델용 13-feature 벡터 생성.")
            # [오류 수정] 10 -> 13. 모델이 13개 피처를 기대합니다.
            return event_count, np.random.rand(1, 13)
        
        print(f"[CTI] {event_count}개 이벤트 감지. 위협 없음 (0-벡터).")
        # [오류 수정] 10 -> 13. 모델이 13개 피처를 기대합니다.
        return event_count, np.zeros((1, 13))

    def analyze_events(self):
        """이벤트를 분석하고 JSON 파일에 씁니다."""
        
        event_count, feature_vector = self.read_monitor_events()
        
        # [!!! 핵심 수정 !!!]
        # model.predict()가 DataFrame을 요구하므로 (ValueError 발생),
        # 실제 모니터링 파이프라인이 DataFrame을 생성하도록 연동되기 전까지
        # 이 스크립트는 '시뮬레이션 모드'로만 작동해야 합니다.
        # 'if self.model...' 블록을 강제로 비활성화하고 시뮬레이션 로직만 사용합니다.

        # if self.model and np.any(feature_vector):
            # (가상) ML 모델이 [위협레벨, 공격단계, 공격타입]을 반환한다고 가정
            
            # [오류 수정] 모델이 3개의 값을 반환한다고 가정 (예: [레벨, 단계, 타입])
            # .predict()가 (1, 3) 형태의 2D 배열을 반환한다고 가정
            # prediction = self.model.predict(feature_vector) # <--- 이 부분이 오류를 유발
            
            # ... (오류가 발생하는 prediction 로직) ...

        # else:
            # (시뮬레이션) 모델이 없거나 위협이 없을 경우
            
            # [수정] 모델 로드 여부와 관계없이, 랜덤 시뮬레이션 로직을 강제 실행합니다.
            # (feature_vector가 0이 아닐 때, 즉 이벤트가 100개 이상일 때)
        if np.any(feature_vector):
            # (시뮬레이션) 모델이 없거나, 시뮬레이션 모드일 때
            print("[CTI] (시뮬레이션) 가상 위협 벡터 감지. 랜덤 평가 생성.")
            threat_level = random.choice(self.threat_levels[1:]) # LOW, MEDIUM, HIGH
            attack_stage = random.choice(self.attack_stages)
            active_attacks = [random.choice(self.attack_types)]
            confidence = random.uniform(0.6, 0.9)
            alert_detected = True
        else:
            # 위협 없음 (feature_vector가 0-벡터)
            print("[CTI] (시뮬레이션) 위협 없음. 'NONE' 평가 생성.")
            threat_level = "NONE"
            attack_stage = "None"
            active_attacks = []
            confidence = 1.0
            alert_detected = False

        # 분석 결과 생성
        assessment = {
            "last_analysis_timestamp": time.time(),
            "current_threat_level": threat_level,
            "confidence_score": confidence,
            "active_attack_types": active_attacks,
            "attack_stage_assessment": attack_stage,
            "source_ips_of_interest": [f"10.13.0.{random.randint(10, 20)}"],
            "raw_event_count_last_cycle": event_count,
            "alert_detected": alert_detected
        }
        
        return assessment

    def write_assessment_file(self, assessment):
        """분석 결과를 cti_threat_assessment.json 파일에 씁니다."""
        try:
            with open(CTI_ASSESSMENT_FILE, 'w') as f:
                json.dump(assessment, f, indent=4)
        except Exception as e:
            print(f"[CTI] Error: cti_threat_assessment.json 파일 쓰기 실패: {e}", sys.stderr)

    def run(self, interval=5):
        print(f"[CTI] CTI 에이전트 실행. ({interval}초마다 분석)")
        try:
            while True:
                assessment = self.analyze_events()
                self.write_assessment_file(assessment)
                
                if assessment["alert_detected"]:
                    print(f"[CTI] ❗ 위협 감지! (Level: {assessment['current_threat_level']}, Type: {assessment['active_attack_types']})")
                else:
                    print(f"[CTI] ✅ 시스템 정상. (Events: {assessment['raw_event_count_last_cycle']})")
                    
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[CTI] CTI 에이전트 중지됨.")
            # 종료 시 알림 없음 상태로 정리
            self.write_assessment_file({
                "last_analysis_timestamp": time.time(),
                "alert_detected": False,
                "current_threat_level": "NONE"
            })

if __name__ == "__main__":
    analyzer = CTIAnalyzer(MODEL_PATH)
    analyzer.run(interval=5) # 5초마다 위협 분석