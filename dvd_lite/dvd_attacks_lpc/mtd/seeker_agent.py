# Directory: dvd_lite/dvd_attacks_lpc/mtd/
# Filename: seeker_agent.py

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
    """
    Advanced Seeker Agent that interacts with MTD defenses.
    """
    def __init__(self, rng, level, endpoints):
        self.rng = rng
        self.endpoints = endpoints
        self.current_target = self.rng.choice(endpoints)
        
        # Seeker Level Parameters
        # (Scan Effort, Attack Speed, IP Change Probability, Patience)
        params = {
            0: (0.1, 0.1, 0.05, 0.2),
            1: (0.3, 0.2, 0.1, 0.4),
            2: (0.5, 0.4, 0.3, 0.6),
            3: (0.7, 0.6, 0.5, 0.8),
            4: (0.9, 0.8, 0.8, 1.0)
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
        Determine Seeker's intent based on defense status.
        defense_status: {
            "is_shuffle": bool,
            "is_decoy_active": bool,
            "decoy_ratio": float
        }
        """
        # 1. Reaction to Shuffle (Connection Reset)
        if defense_status.get("is_shuffle", False):
            for ep in self.endpoints:
                ep.reset_progress()
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
        
        # 2. Apply Decoy Effect (If active, chance to switch to a decoy target)
        if defense_status.get("is_decoy_active", False):
            # Higher decoy_ratio -> Higher chance to get lured
            if not t.is_decoy and self.rng.random() < defense_status.get("decoy_ratio", 0.0):
                # Switch target to a decoy
                decoys = [ep for ep in self.endpoints if ep.is_decoy]
                if decoys:
                    self.current_target = self.rng.choice(decoys)
                    t = self.current_target

        # 3. Progress Attack
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
        """
        React to environment feedback (Blocked, Success, Decoy Hit)
        """
        t = self.current_target
        
        if outcome == "blocked":
            # If blocked, lose progress
            t.exploit_progress = max(0.0, t.exploit_progress - 0.8)
            t.breach_progress = max(0.0, t.breach_progress - 0.8)
            
            # Decide whether to change IP (Evasion)
            if self.rng.random() < self.ip_change_prob:
                self._change_ip()
            else:
                # If low patience, might switch target
                if self.rng.random() > self.patience:
                    self.current_target = self.rng.choice(self.endpoints)

        elif outcome == "exploit_success":
            t.breach_progress += self.attack_speed # Move to breach phase
            
        elif outcome == "breach_success":
            t.state = 3 # Pwned
            
        elif outcome == "decoy_hit":
            # Wasted time on decoy
            t.exploit_progress = 0.0
            t.breach_progress = 0.0
            # Realize it's a decoy? Maybe switch target
            if self.rng.random() > 0.2:
                self.current_target = self.rng.choice(self.endpoints)