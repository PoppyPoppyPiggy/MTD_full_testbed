import os
import sys
import time
import subprocess
import threading

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.getcwd())

from dvd_lite.dvd_attacks_lpc.mtd.effects_logger import EffectsLogger
from dvd_lite.dvd_attacks_lpc.mtd.evaluator import AttackSurfaceEvaluator
from dvd_lite.dvd_attacks_lpc.mtd.manager import MTDManager

# --- 시나리오 설정 ---
SCENARIO_DURATION_SEC = 120
MTD_INTERVAL_SEC = 20
DOCKER_COMPOSE_FILE = "docker-compose.yml"
NS3_DIR = os.path.expanduser("~/ns-3/ns-3.41") # home/ns-3 경로에 맞게 수정
BUS_DIR = "dvd_lite/dvd_attacks_lpc/bus"
# ---

class MTDawareAttacker:
    """MTD 환경에서 주기적으로 타겟을 공격하는 가상 공격자"""
    def __init__(self, mtd_manager):
        self.mtd_manager = mtd_manager
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run_attack_loop)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join()

    def _run_attack_loop(self):
        while not self.stop_event.is_set():
            ip, port = self.mtd_manager.get_current_surface_address()
            if ip and port:
                # Docker 내부의 attacker 컨테이너가 공격을 수행하도록 함
                cmd = f"""
                docker exec attacker python -c "
import socket;
ip, port = '{ip}', {port};
print(f'ATTACKER: Hitting {{ip}}:{{port}}');
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
    s.settimeout(0.5);
    s.connect_ex((ip, port));
    s.close();
except Exception:
    pass
"
                """
                subprocess.run(cmd, shell=True, capture_output=True)
            time.sleep(0.5)

def run_command(command, workdir=".", background=False):
    print(f"\n--- CMD: {command} (in {workdir}) ---\n")
    if background:
        return subprocess.Popen(command, shell=True, cwd=workdir)
    else:
        subprocess.run(command, shell=True, cwd=workdir)

def main():
    if not os.path.exists(NS3_DIR):
        print(f"Error: NS-3 directory not found at {NS3_DIR}")
        return

    effects_logger = EffectsLogger(BUS_DIR)
    evaluator = AttackSurfaceEvaluator(effects_logger, hit_threshold=5, time_window=10)
    mtd_manager = MTDManager(evaluator, effects_logger, interval=MTD_INTERVAL_SEC)
    attacker = MTDawareAttacker(mtd_manager)

    try:
        print("--- 1. Starting Docker Environment ---")
        run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} up --build -d")
        
        print("\n--- 2. Starting MTD Manager and Attacker ---")
        mtd_manager.start()
        attacker.start()
        
        print(f"\n--- 3. Running Scenario for {SCENARIO_DURATION_SEC} seconds ---")
        for i in range(SCENARIO_DURATION_SEC):
            print(f"Scenario running... {i+1}/{SCENARIO_DURATION_SEC}", end="\r")
            time.sleep(1)
        print("\nScenario finished.")

    finally:
        print("\n--- 4. Cleaning Up ---")
        attacker.stop()
        mtd_manager.stop()
        run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} down --volumes")

    print("\n--- 5. Generating NS-3 Timeline ---")
    run_command(f"python3 dvd_lite/dvd_attacks_lpc/tools/events_to_timeline.py --log_dir {BUS_DIR} --sim_duration {SCENARIO_DURATION_SEC}")
    
    print("\n--- 6. Running NS-3 Simulation ---")
    timeline_path = os.path.abspath(os.path.join(BUS_DIR, "effect_timeline.csv"))
    metrics_path = os.path.abspath(os.path.join(BUS_DIR, "ns3_metrics.csv"))
    
    ns3_command = f"./ns3 run 'scratch/drone_lpc_eval --timeline={timeline_path}'"
    run_command(ns3_command, workdir=NS3_DIR)
    run_command(f"mv {NS3_DIR}/ns3_metrics.csv {metrics_path}")

    print("\n--- SCENARIO COMPLETE ---")
    print(f"All artifacts are in the '{BUS_DIR}' directory.")
    print("Final network metrics are available in 'ns3_metrics.csv'")

if __name__ == "__main__":
    main()