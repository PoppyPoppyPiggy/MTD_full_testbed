import numpy as np
import random

class Endpoint:
    def __init__(self, ip, name="Unknown", is_decoy=False):
        self.ip = ip
        self.name = name
        self.is_decoy = is_decoy
        self.scan_progress = 0.0
        self.exploit_progress = 0.0
        self.breach_progress = 0.0
        self.state = 0 # 0: Safe, 1: Scanned, 2: Exploited, 3: Breached

    def reset_progress(self):
        self.scan_progress = 0.0
        self.exploit_progress = 0.0
        self.breach_progress = 0.0
        self.state = 0

class SimulatedHeuristicSeeker:
    def __init__(self, rng, level, endpoints):
        self.rng = rng
        self.endpoints = endpoints
        self.current_target = self.rng.choice(endpoints)
        
        # Seeker Level Parameters
        params = {
            0: (0.1, 0.1, 0.05, 0.2),
            1: (0.3, 0.2, 0.1, 0.4),
            2: (0.5, 0.4, 0.3, 0.6),
            3: (0.7, 0.6, 0.5, 0.8),
            4: (0.9, 0.9, 0.8, 1.0)
        }
        p = params.get(level, params[2])
        self.scan_effort = p[0]
        self.attack_speed = p[1]
        self.ip_change_prob = p[2]
        self.patience = p[3]
        
        self.seeker_ip_base = "192.168.1"
        self.seeker_id = 100
        self.seeker_ip = f"{self.seeker_ip_base}.{self.seeker_id}"
        self.seeker_params = (self.scan_effort, 0.5) 

    def _change_ip(self):
        self.seeker_id = self.rng.integers(101, 250)
        self.seeker_ip = f"{self.seeker_ip_base}.{self.seeker_id}"

    def step(self, defense_status):
        """
        defense_status: { "is_shuffle", "is_decoy_active", "decoy_ratio" }
        """
        # 1. 셔플 발생 시 반응 (모든 진행도 리셋)
        if defense_status.get("is_shuffle", False):
            for ep in self.endpoints:
                ep.reset_progress()
            # 강제로 타겟 변경 (재탐색 시간 소요)
            self.current_target = self.rng.choice(self.endpoints)
            
            return {
                "seeker_ip": self.seeker_ip,
                "is_scan": True,
                "intent": "reorient",
                "target_ep": None,
                "is_exploit_attempt": False, 
                "is_breach_attempt": False
            }

        t = self.current_target
        intent = "scan"
        
        # 2. 디코이 활성화 시 유인 (속임수)
        # 디코이 정책이 켜져 있고, 현재 타겟이 진짜라면 -> 확률적으로 디코이로 바꿈
        if defense_status.get("is_decoy_active", False):
            if not t.is_decoy and self.rng.random() < defense_status.get("decoy_ratio", 0.0):
                decoys = [ep for ep in self.endpoints if ep.is_decoy]
                if decoys:
                    self.current_target = self.rng.choice(decoys)
                    t = self.current_target

        # 3. 공격 진행
        t.exploit_progress += self.attack_speed
        
        is_exploit_attempt = False
        is_breach_attempt = False
        
        if t.exploit_progress >= 1.0:
            intent = "exploit"
            is_exploit_attempt = True
            
        if t.breach_progress >= 1.0:
            intent = "breach"
            is_breach_attempt = True
        
        return {
            "seeker_ip": self.seeker_ip,
            "is_scan": True,
            "intent": intent,
            "target_ep": t,
            "is_exploit_attempt": is_exploit_attempt,
            "is_breach_attempt": is_breach_attempt
        }

    def handle_outcome(self, outcome):
        t = self.current_target
        
        if outcome == "blocked":
            # 차단 시: 진행도를 크게 잃음 (처음부터 다시 해야 함)
            t.exploit_progress = 0.0
            t.breach_progress = 0.0
            
            # IP 변경 시도 (회피)
            if self.rng.random() < self.ip_change_prob:
                self._change_ip()
            else:
                # 인내심 테스트 후 타겟 변경
                if self.rng.random() > self.patience:
                    self.current_target = self.rng.choice(self.endpoints)

        elif outcome == "exploit_success":
            t.breach_progress += self.attack_speed 
            
        elif outcome == "breach_success":
            t.state = 3 
            
        elif outcome == "decoy_hit":
            # 디코이 공격: 진행도는 초기화되지만, 계속 속아 넘어갈 수도 있음
            t.exploit_progress = 0.0
            t.breach_progress = 0.0
            # 20% 확률로만 디코이임을 눈치채고 타겟 변경
            if self.rng.random() > 0.8:
                self.current_target = self.rng.choice(self.endpoints)