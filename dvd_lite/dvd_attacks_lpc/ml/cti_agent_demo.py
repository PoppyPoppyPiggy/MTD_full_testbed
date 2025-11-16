#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI (Cyber Threat Intelligence) Agent - (v2 Attack-Linked)

- [MODIFIED] 'attack_orchestrator.py'가 생성하는 'attack_output' 파일을 직접 읽어옵니다.
- [REMOVED] ML 모델 및 랜덤 시뮬레이션 로직을 제거했습니다.
- 'attack_output' 파일 내용에 따라 실제 위협 경보를 'cti_threat_assessment.json'에 씁니다.
"""

import os
import sys
import time
import json
import random
import re # 정규표현식 임포트

# --- 경로 설정 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# Scorer가 읽을 파일 경로
STATE_DIR = os.path.join(parent_dir, 'mtd', 'shared_state')
os.makedirs(STATE_DIR, exist_ok=True) # shared_state 디렉토리 생성
CTI_ASSESSMENT_FILE = os.path.join(STATE_DIR, 'cti_threat_assessment.json')

# [MODIFIED] attack_orchestrator가 생성하는 공격 상태 파일
ATTACK_OUTPUT_FILE = os.path.join(parent_dir, 'attack_output') 

# [MODIFIED] Breach를 유발하는 공격 목록 (가정)
# 이 공격들이 탐지되면 'Breach'로 간주합니다.
BREACH_ATTACKS = [
    "companion-computer-takeover",
    "gps-spoofing", # 예시: GPS 스푸핑은 즉시 Breach로 간주
    "waypoint-injection"
]

class CTIAnalyzer:
    def __init__(self):
        print(f"[CTI] CTI 위협 분석 에이전트 초기화 (Attack-Linked v2).")
        print(f"[CTI] 감시 대상 파일: {ATTACK_OUTPUT_FILE}")
        print(f"[CTI] CTI 평가 파일: {CTI_ASSESSMENT_FILE}")
        
        self.last_attack_output = "" # 파일 변경 감지를 위함

    def read_attack_output(self):
        """'attack_output' 파일을 읽어 현재 실행 중인 공격을 반환합니다."""
        try:
            if not os.path.exists(ATTACK_OUTPUT_FILE):
                return "" # 파일이 없으면 공격 없음
                
            with open(ATTACK_OUTPUT_FILE, 'r') as f:
                content = f.read().strip()
            return content
            
        except Exception as e:
            print(f"[CTI] Error: 'attack_output' 파일 읽기 실패: {e}", file=sys.stderr)
            return "" # 오류 발생 시 공격 없음으로 간주

    def analyze_attack_content(self, content):
        """'attack_output' 파일 내용을 분석하여 CTI 평가서를 생성합니다."""
        
        assessment = {
            "last_analysis_timestamp": time.time(),
            "current_threat_level": "NONE",
            "confidence_score": 1.0,
            "active_attack_types": [],
            "attack_stage_assessment": "None",
            "source_ips_of_interest": [], # TODO: 공격 로그에서 IP 파싱
            "raw_event_count_last_cycle": 0, # attack_output 기반이므로 0
            "alert_detected": False
        }

        if not content or "Running attack" not in content:
            # 공격 없음
            return assessment

        # "Running attack: [attack_name]" 형식에서 attack_name 추출
        match = re.search(r"Running attack: (\S+)", content)
        if not match:
            return assessment # 형식에 맞지 않으면 무시

        attack_name = match.group(1).replace(".sh", "") # .sh 확장자 제거
        
        # 공격이 감지됨
        assessment["alert_detected"] = True
        assessment["active_attack_types"] = [attack_name]
        assessment["confidence_score"] = 0.95 # 파일 기반 탐지
        
        # 공격 유형에 따라 위협 수준 및 단계 결정
        if attack_name in BREACH_ATTACKS:
            assessment["current_threat_level"] = "HIGH"
            assessment["attack_stage_assessment"] = "Breach"
        elif "scan" in attack_name or "discovery" in attack_name:
            assessment["current_threat_level"] = "LOW"
            assessment["attack_stage_assessment"] = "Reconnaissance"
        else:
            assessment["current_threat_level"] = "MEDIUM"
            assessment["attack_stage_assessment"] = "Exploitation"

        return assessment

    def write_assessment_file(self, assessment):
        """분석 결과를 cti_threat_assessment.json 파일에 씁니다."""
        try:
            with open(CTI_ASSESSMENT_FILE, 'w') as f:
                json.dump(assessment, f, indent=4)
        except Exception as e:
            print(f"[CTI] Error: cti_threat_assessment.json 파일 쓰기 실패: {e}", sys.stderr)

    def run(self, interval=5):
        print(f"[CTI] CTI 에이전트 실행. ({interval}초마다 'attack_output' 파일 스캔)")
        try:
            while True:
                attack_content = self.read_attack_output()
                
                # [MODIFIED] 파일 내용이 변경되었을 때만 분석 및 로깅
                if attack_content != self.last_attack_output:
                    print(f"[CTI] 'attack_output' 변경 감지: '{attack_content}'")
                    self.last_attack_output = attack_content
                    
                    assessment = self.analyze_attack_content(attack_content)
                    self.write_assessment_file(assessment)
                    
                    if assessment["alert_detected"]:
                        print(f"[CTI] ❗ 위협 감지! (Level: {assessment['current_threat_level']}, Type: {assessment['active_attack_types']})")
                    else:
                        print(f"[CTI] ✅ 시스템 정상. (공격 없음)")
                
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
    analyzer = CTIAnalyzer()
    analyzer.run(interval=5) # 5초마다 'attack_output' 파일 확인
