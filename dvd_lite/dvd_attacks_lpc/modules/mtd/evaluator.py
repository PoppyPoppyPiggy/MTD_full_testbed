import os
import time
from collections import defaultdict

# 이 스크립트는 simulator-lite 내부에서 실행될 때와 외부에서 실행될 때 모두 경로를 맞추기 위함
HIT_LOG_FILE = "/shared/hit.log" if os.path.exists("/shared") else "dvd_lite/dvd_attacks_lpc/mtd/shared_state/hit.log"

class AttackSurfaceEvaluator:
    def __init__(self, effects_logger, hit_threshold=5, time_window=10, target_drone_ip="10.13.0.3"):
        self.effects_logger = effects_logger
        self.hit_threshold = hit_threshold
        self.time_window = time_window
        self.target_drone_ip = target_drone_ip
        self.hit_records = defaultdict(list)
        self.attack_authorized_for = set()
        self.last_log_size = 0
        if os.path.exists(HIT_LOG_FILE):
             os.remove(HIT_LOG_FILE)

    def check_hits(self):
        if not os.path.exists(HIT_LOG_FILE):
            return

        try:
            current_size = os.path.getsize(HIT_LOG_FILE)
            if current_size > self.last_log_size:
                with open(HIT_LOG_FILE, 'r') as f:
                    f.seek(self.last_log_size)
                    new_hits = f.readlines()
                    for attacker_ip in new_hits:
                        self._record_hit(attacker_ip.strip())
                self.last_log_size = current_size
        except FileNotFoundError:
            pass

    def _record_hit(self, attacker_ip):
        current_time = time.time()
        self.hit_records[attacker_ip] = [t for t in self.hit_records[attacker_ip] if current_time - t < self.time_window]
        self.hit_records[attacker_ip].append(current_time)
        
        hit_count = len(self.hit_records[attacker_ip])
        print(f"MTD EVALUATOR: Hit from {attacker_ip}. Count: {hit_count}/{self.hit_threshold}")

        if hit_count >= self.hit_threshold:
            if attacker_ip not in self.attack_authorized_for:
                print(f"MTD EVALUATOR: >>> ATTACK AUTHORIZED for {attacker_ip} <<<")
                self.attack_authorized_for.add(attacker_ip)
                self.effects_logger.record_effect("ATTACK_AUTHORIZED", packet_loss=0.3, delay=100)
        else:
            if attacker_ip in self.attack_authorized_for:
                print(f"MTD EVALUATOR: <<< Attack DE-AUTHORIZED for {attacker_ip} >>>")
                self.attack_authorized_for.remove(attacker_ip)
                self.effects_logger.record_effect("ATTACK_DEAUTHORIZED")

    def reset_due_to_mtd(self):
        print("MTD EVALUATOR: MTD action occurred. Resetting all authorizations.")
        if self.attack_authorized_for:
            self.effects_logger.record_effect("ATTACK_INTERRUPTED")
        self.attack_authorized_for.clear()