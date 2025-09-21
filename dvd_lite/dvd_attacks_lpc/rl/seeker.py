#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time

def get_shared_path(filename: str) -> str:
    container_path = os.path.join("/shared", filename)
    if os.path.exists(container_path): 
        return container_path
    # 로컬 테스트 경로 (/shared 미존재 시)
    mtd_dir = os.path.join(os.path.dirname(__file__), '..', 'mtd')
    return os.path.join(os.path.abspath(mtd_dir), "shared_state", filename)

STATE_FILE_PATH = get_shared_path("mtd_state.json")

class SeekerAgent:
    """RL 기반 공격 에이전트 (v1.0 - 정찰 루프)"""
    def __init__(self):
        self.run_flag = True
        self.mtd_state = {}

    def read_mtd_state(self):
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                self.mtd_state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.mtd_state = {}

    def run(self):
        print("[Seeker] 공격 에이전트 시작...")
        while self.run_flag:
            self.read_mtd_state()
            current_target = self.mtd_state.get('current_target', 'N/A')
            is_dummy_active = self.mtd_state.get('dummy_active', 'Unknown')
            msg = f"\r[Seeker] 현재 MTD 타겟: {current_target:<18} | 실제 드론 활성 상태: {is_dummy_active}"
            sys.stdout.write(msg)
            sys.stdout.flush()

            # TODO: (향후) RL 모델 기반 정찰/공격 의사결정 추가
            # 1) 관측 수집(self.mtd_state)
            # 2) PPO/DQN 등으로 행동 결정
            # 3) 행동 실행(네트워크 프로브)
            # 4) 결과 보상 및 업데이트

            time.sleep(5)

if __name__ == "__main__":
    agent = SeekerAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        print("\n[Seeker] 종료합니다.")
