#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import random
from collections import defaultdict

# --- 경로 설정 및 로거 import ---
MTD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LPC_ROOT = os.path.abspath(os.path.join(MTD_DIR, '..'))
if LPC_ROOT not in sys.path:
    sys.path.insert(0, LPC_ROOT)
from bus.logger import log_bus_event

STATE_FILE_PATH = os.path.join(LPC_ROOT, "mtd", "shared_state", "mtd_state.json")

class AdvancedSeeker:
    def __init__(self, recon_duration=120, attack_interval=15):
        self.recon_duration = recon_duration
        self.attack_interval = attack_interval
        self.knowledge_base = {
            "ip_pool": set(),
            "port_pool": set(),
            "shuffle_history":,
            "transition_matrix": defaultdict(lambda: defaultdict(int))
        }
        self.last_known_target = None

    def read_current_target(self):
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                state = json.load(f)
                return state.get("current_target")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def analyze_patterns(self):
        """셔플링 기록을 분석하여 IP와 Port 풀, 그리고 전환 확률을 학습"""
        if not self.knowledge_base["shuffle_history"]:
            return

        # IP 및 Port 풀 업데이트
        for target, _ in self.knowledge_base["shuffle_history"]:
            ip, port_str = target.split(':')
            self.knowledge_base["ip_pool"].add(ip)
            self.knowledge_base["port_pool"].add(int(port_str))

        # 전환 행렬(Transition Matrix) 생성
        history = self.knowledge_base["shuffle_history"]
        for i in range(len(history) - 1):
            current_target, _ = history[i]
            next_target, _ = history[i+1]
            self.knowledge_base["transition_matrix"][current_target][next_target] += 1

    def predict_next_target(self):
        """학습된 패턴을 기반으로 다음 타겟 예측"""
        if not self.last_known_target or not self.knowledge_base["transition_matrix"]:
            # 정보가 부족하면 풀에서 무작위로 선택
            if not self.knowledge_base["ip_pool"] or not self.knowledge_base["port_pool"]:
                return "10.13.0.3:14550" # 최악의 경우 기본값
            
            pred_ip = random.choice(list(self.knowledge_base["ip_pool"]))
            pred_port = random.choice(list(self.knowledge_base["port_pool"]))
            return f"{pred_ip}:{pred_port}"

        transitions = self.knowledge_base["transition_matrix"].get(self.last_known_target)
        if not transitions:
            return self.last_known_target # 변경 없을 것으로 예측

        # 가장 빈번하게 전환된 타겟을 다음 타겟으로 예측
        next_target = max(transitions, key=transitions.get)
        return next_target

    def run(self):
        print(" 정찰 단계 시작...")
        start_time = time.time()
        while time.time() - start_time < self.recon_duration:
            current_target = self.read_current_target()
            if current_target and current_target!= self.last_known_target:
                print(f" 타겟 변경 감지: {current_target}")
                self.knowledge_base["shuffle_history"].append((current_target, time.time()))
                self.last_known_target = current_target
            time.sleep(1)
        
        print(" 정찰 완료. 패턴 분석 및 공격 단계 시작...")
        self.analyze_patterns()
        print(f" 학습된 IP 풀: {self.knowledge_base['ip_pool']}")
        print(f" 학습된 Port 풀: {self.knowledge_base['port_pool']}")

        while True:
            predicted_target = self.predict_next_target()
            print(f" 다음 타겟 예측: {predicted_target}. {self.attack_interval}초 후 공격 실행.")
            
            time.sleep(self.attack_interval)
            
            # 실제 타겟과 예측 비교
            actual_target = self.read_current_target()
            is_success = (predicted_target == actual_target)
            
            print(f" 공격 실행! 예측: {predicted_target}, 실제: {actual_target} -> {'성공' if is_success else '실패'}")
            
            # 공격 이벤트 로깅
            log_bus_event("attack_detected", {
                "source_ip": "10.13.0.204", # Seeker's IP
                "target": predicted_target,
                "is_success": is_success,
                "is_real_asset": actual_target.startswith("10.13.0.3") if actual_target else False
            })
            
            # 최신 정보로 업데이트
            if actual_target and actual_target!= self.last_known_target:
                 self.knowledge_base["shuffle_history"].append((actual_target, time.time()))
                 self.last_known_target = actual_target
                 self.analyze_patterns() # 재학습

if __name__ == "__main__":
    seeker = AdvancedSeeker()
    seeker.run()