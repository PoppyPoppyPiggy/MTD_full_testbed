#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import subprocess
import time

DOCKER_COMPOSE_FILE = "docker-compose-lite.yaml"
AI_TRAINING_CONTAINER = "attacker"
SEEKER_CONTAINER = "seeker"
CTI_AGENT_CONTAINER = "attacker"
SIMULATION_DURATION_S = 300 # 5분

def run_command(command: str, container: str = None, detach: bool = False):
    """Docker 컨테이너 또는 로컬에서 명령어를 실행합니다."""
    full_command = command
    if container:
        mode = "-d" if detach else "-it"
        full_command = f"docker exec {mode} {container} {command}"
    
    print(f"\n[Orchestrator] Executing: {full_command}")
    subprocess.run(full_command, shell=True, check=True)

def main():
    try:
        print("--- PHASE 1: SETUP & AI TRAINING ---")
        run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} up --build -d")
        time.sleep(10)
        
        print("\n[Orchestrator] CTI 모델 훈련 시작...")
        run_command(f"bash -c 'python3 dvd_attacks_lpc/ml/data_builder.py && python3 dvd_attacks_lpc/ml/train_classifier.py'", container=AI_TRAINING_CONTAINER)
        
        print("\n[Orchestrator] MTD 및 Seeker RL 에이전트 훈련 시작...")
        run_command(f"bash -c 'pip install -q stable-baselines3[extra] tensorflow tensorboard && python3 dvd_attacks_lpc/rl/train_mtd_agent.py && python3 dvd_attacks_lpc/rl/train_seeker_agent.py'", container=AI_TRAINING_CONTAINER)

        print("\n--- PHASE 2: REAL-TIME SIMULATION ---")
        print("[Orchestrator] CTI 및 QoS 모니터 활성화...")
        run_command("python3 dvd_attacks_lpc/ml/cti_agent.py", container=CTI_AGENT_CONTAINER, detach=True)
        run_command("python3 dvd_attacks_lpc/monitors/qos_monitor.py", container="ground-control-station-lite", detach=True)

        print("[Orchestrator] Seeker 공격 에이전트 실행...")
        run_command("python3 dvd_attacks_lpc/rl/seeker.py", container=SEEKER_CONTAINER, detach=True)
        
        print(f"\n[Orchestrator] 시뮬레이션을 {SIMULATION_DURATION_S}초 동안 진행합니다...")
        print("Hint: open a new terminal and run 'docker logs -f deception_manager'")
        time.sleep(SIMULATION_DURATION_S)

        print("\n--- PHASE 3: ANALYSIS & CLEANUP ---")
        print("[Orchestrator] 종합 성능 평가 스코어 계산...")
        run_command(f"python3 dvd_attacks_lpc/tools/compute_mtd_metrics.py --out /mtd_full_testbed/dvd_lite/dvd_attacks_lpc/metrics_report.json")
        print("\n[Orchestrator] metrics_report.json 파일이 생성되었습니다.")

    except subprocess.CalledProcessError as e:
        print(f"\n[Orchestrator] 스크립트 실행 중 오류 발생: {e}")
    finally:
        print("\n[Orchestrator] 모든 실험 환경을 종료하고 정리합니다.")
        run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} down -v")

if __name__ == "__main__":
    main()