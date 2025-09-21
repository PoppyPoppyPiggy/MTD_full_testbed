#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time

def get_shared_path(filename: str) -> str:
    container_path = os.path.join("/shared", filename)
    if os.path.exists(container_path): return container_path
    # 로컬 테스트를 위한 경로 (실제 컨테이너 환경에서는 /shared 사용)
    mtd_dir = os.path.join(os.path.dirname(__file__), '..', 'mtd')
    return os.path.join(mtd_dir, "shared_state", filename)

STATE_FILE_PATH = get_shared_path("mtd_state.json")

class SeekerAgent:
    """RL 기반 공격 에이전트 (v1.0 - 정찰)"""
    def __init__(self):
        self.run_flag = True
        self.mtd_state = {}

    def read_mtd_state(self):
        """MTD 상태 파일을 읽어옴"""
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                self.mtd_state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("[Seeker] MTD 상태 파일을 찾을 수 없거나 형식이 잘못되었습니다.", file=sys.stderr)
            self.mtd_state = {}

    def run(self):
        print("[Seeker] 공격 에이전트 시작...")
        while self.run_flag:
            self.read_mtd_state()
            current_target = self.mtd_state.get('current_target', 'N/A')
            is_dummy_active = self.mtd_state.get('dummy_active', 'Unknown')
            
            print(f"\r[Seeker] 현재 MTD 타겟: {current_target}, 실제 드론 활성 상태: {is_dummy_active}", end="")
            
            # TODO: 여기에 RL 모델을 이용한 정찰 및 공격 로직 추가
            # 1. 상태 관측 (self.mtd_state)
            # 2. RL 모델로 행동 결정 (예: PROBE_CANDIDATE_1)
            # 3. 행동 실행 (네트워크 프로빙)
            # 4. 결과에 따른 보상 계산 및 모델 업데이트
            
            time.sleep(5)

if __name__ == "__main__":
    agent = SeekerAgent()
    agent.run()