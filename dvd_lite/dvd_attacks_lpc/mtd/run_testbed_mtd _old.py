#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real Testbed MTD Execution Script
=================================

학습된 RL-CTI MTD 모델을 실제 테스트베드에 적용

Usage:
    # Step 1: Dry-run 테스트 (iptables 명령어만 출력)
    python run_testbed_mtd.py --model best_model.pt --dry-run --episodes 5

    # Step 2: 실제 iptables 적용 (root 필요)
    sudo python run_testbed_mtd.py --model best_model.pt --episodes 10

    # Step 3: 실시간 방어 모드
    sudo python run_testbed_mtd.py --model best_model.pt --realtime --duration 300

Author: MTD-RL Research Team
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# PyTorch
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not available. Install with: pip install torch")


# =============================================================================
# Constants
# =============================================================================
STATE_DIM = 17
ACTION_DIM = 7

MTD_DEFENSE_WEIGHTS = {
    'shuffle': 0.35,
    'port_hop': 0.20,
    'decoy': 0.15,
    'blacklist': 0.10,
    'swap': 0.45,
}

ACTION_THRESHOLDS = {
    'shuffle': 0.25,
    'port_hop': 0.35,
    'decoy': 0.40,
    'swap': 0.30,
}

ACTION_COSTS = {
    'shuffle': 0.05,
    'port_hop': 0.03,
    'decoy': 0.02,
    'swap': 0.06,
}

# 테스트베드 서비스 설정 (Table 8)
SERVICES_CONFIG = {
    "fc_mavlink": {
        "name": "Flight Controller MAVLink",
        "real_ip": "10.13.0.10",
        "real_port": 14550,
        "protocol": "udp",
        "is_critical": True,
    },
    "cc_sitl": {
        "name": "Companion Computer SITL",
        "real_ip": "10.13.0.11",
        "real_port": 5760,
        "protocol": "tcp",
        "is_critical": True,
    },
    "cc_mavlink": {
        "name": "Companion Computer MAVLink",
        "real_ip": "10.13.0.11",
        "real_port": 14550,
        "protocol": "udp",
        "is_critical": False,
    },
    "gcs_web": {
        "name": "Ground Control Station Web",
        "real_ip": "10.13.0.20",
        "real_port": 3000,
        "protocol": "tcp",
        "is_critical": True,
    },
    "video_stream": {
        "name": "Video Stream",
        "real_ip": "10.13.0.12",
        "real_port": 554,
        "protocol": "tcp",
        "is_critical": False,
    },
    "telemetry_db": {
        "name": "Telemetry Database",
        "real_ip": "10.13.0.14",
        "real_port": 5432,
        "protocol": "tcp",
        "is_critical": False,
    },
}

DECOYS_CONFIG = {
    "honeydrone_1": {"real_ip": "10.13.0.100", "real_port": 14550, "protocol": "udp"},
    "honeydrone_2": {"real_ip": "10.13.0.101", "real_port": 14550, "protocol": "udp"},
    "decoy_gcs": {"real_ip": "10.13.0.102", "real_port": 3000, "protocol": "tcp"},
    "tarpit": {"real_ip": "10.13.0.103", "real_port": 9999, "protocol": "tcp"},
}

MTD_CHAINS = {
    "prerouting": "MTD_PREROUTING",
    "postrouting": "MTD_POSTROUTING",
    "forward": "MTD_FORWARD",
}


# =============================================================================
# Actor-Critic Network
# =============================================================================
if TORCH_AVAILABLE:
    class ActorCritic(nn.Module):
        def __init__(self, state_dim: int = STATE_DIM, action_dim: int = ACTION_DIM, hidden_size: int = 256):
            super().__init__()
            self.shared = nn.Sequential(
                nn.Linear(state_dim, hidden_size), nn.LayerNorm(hidden_size), nn.ReLU(),
                nn.Linear(hidden_size, hidden_size), nn.LayerNorm(hidden_size), nn.ReLU(),
            )
            self.actor = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2), nn.ReLU(),
                nn.Linear(hidden_size // 2, action_dim), nn.Tanh(),
            )
            self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)
            self.critic = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2), nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
            )

        def forward(self, state):
            features = self.shared(state)
            return self.actor(features), self.critic(features)

        def act(self, state, deterministic=True):
            action_mean, value = self.forward(state)
            if deterministic:
                return action_mean, torch.zeros(1), value
            std = torch.exp(self.log_std)
            dist = torch.distributions.Normal(action_mean, std)
            action = dist.sample().clamp(-1, 1)
            return action, dist.log_prob(action).sum(-1, keepdim=True), value


# =============================================================================
# Service Target
# =============================================================================
@dataclass
class ServiceTarget:
    name: str
    real_ip: str
    real_port: int
    virtual_ip: str
    virtual_port: int
    protocol: str = "tcp"
    is_critical: bool = False
    is_decoy: bool = False


# =============================================================================
# iptables Executor (Real)
# =============================================================================
class IptablesExecutor:
    """실제 iptables 명령어 실행기"""
    
    def __init__(self, dry_run: bool = True, log_file: str = None):
        self.dry_run = dry_run
        self.command_history: List[Dict] = []
        self.rule_counter = 0
        self.log_file = Path(log_file) if log_file else None
        
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _gen_comment(self, action: str) -> str:
        self.rule_counter += 1
        ts = datetime.now().strftime("%H%M%S")
        return f"MTD_{action}_{ts}_{self.rule_counter}"
    
    def execute(self, cmd: str, description: str = "") -> bool:
        """명령어 실행"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "command": cmd,
            "description": description,
            "dry_run": self.dry_run,
            "success": True,
            "error": None,
        }
        
        if self.dry_run:
            print(f"  [DRY-RUN] {cmd}")
            self.command_history.append(entry)
            return True
        
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                entry["success"] = False
                entry["error"] = result.stderr.strip()
                print(f"  [ERROR] {cmd}")
                print(f"          {result.stderr.strip()}")
            else:
                print(f"  [OK] {cmd}")
        except subprocess.TimeoutExpired:
            entry["success"] = False
            entry["error"] = "Timeout"
            print(f"  [TIMEOUT] {cmd}")
        except Exception as e:
            entry["success"] = False
            entry["error"] = str(e)
            print(f"  [EXCEPTION] {cmd}: {e}")
        
        self.command_history.append(entry)
        
        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + "\n")
        
        return entry["success"]
    
    def execute_batch(self, commands: List[str], description: str = "") -> int:
        success_count = 0
        for cmd in commands:
            if self.execute(cmd, description):
                success_count += 1
        return success_count


# =============================================================================
# MTD Controller (Real Testbed)
# =============================================================================
class RealMTDController:
    """실제 테스트베드용 MTD 컨트롤러"""
    
    def __init__(self, dry_run: bool = True, log_dir: str = "logs"):
        self.dry_run = dry_run
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = self.log_dir / f"iptables_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.executor = IptablesExecutor(dry_run=dry_run, log_file=str(log_file))
        
        self.services: Dict[str, ServiceTarget] = {}
        self.decoys: Dict[str, ServiceTarget] = {}
        self.config_history: List[str] = []
        
        self.stats = {
            'total_shuffles': 0,
            'total_port_hops': 0,
            'total_swaps': 0,
            'total_decoy_activations': 0,
            'total_cost': 0.0,
            'iptables_commands': 0,
        }
        
        self._init_services()
    
    def _init_services(self):
        for name, cfg in SERVICES_CONFIG.items():
            self.services[name] = ServiceTarget(
                name=name, real_ip=cfg["real_ip"], real_port=cfg["real_port"],
                virtual_ip=cfg["real_ip"], virtual_port=cfg["real_port"],
                protocol=cfg["protocol"], is_critical=cfg.get("is_critical", False),
            )
        for name, cfg in DECOYS_CONFIG.items():
            self.decoys[name] = ServiceTarget(
                name=name, real_ip=cfg["real_ip"], real_port=cfg["real_port"],
                virtual_ip=cfg["real_ip"], virtual_port=cfg["real_port"],
                protocol=cfg["protocol"], is_decoy=True,
            )
        self._record_config()
    
    def _get_config_snapshot(self) -> str:
        return "|".join(sorted([f"{s.virtual_ip}:{s.virtual_port}" for s in self.services.values()]))
    
    def _record_config(self):
        self.config_history.append(self._get_config_snapshot())
    
    def init_chains(self):
        """MTD iptables 체인 초기화"""
        print("\n[iptables] Initializing MTD chains...")
        commands = [
            f"iptables -t nat -N {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -N {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -N {MTD_CHAINS['forward']} 2>/dev/null || true",
            f"iptables -t nat -C PREROUTING -j {MTD_CHAINS['prerouting']} 2>/dev/null || "
            f"iptables -t nat -I PREROUTING -j {MTD_CHAINS['prerouting']}",
            f"iptables -t nat -C POSTROUTING -j {MTD_CHAINS['postrouting']} 2>/dev/null || "
            f"iptables -t nat -I POSTROUTING -j {MTD_CHAINS['postrouting']}",
            f"iptables -C FORWARD -j {MTD_CHAINS['forward']} 2>/dev/null || "
            f"iptables -I FORWARD -j {MTD_CHAINS['forward']}",
        ]
        self.executor.execute_batch(commands, "Initialize MTD chains")
    
    def cleanup(self):
        """MTD 규칙 정리"""
        print("\n[iptables] Cleaning up MTD rules...")
        commands = [
            f"iptables -t nat -F {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -F {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -F {MTD_CHAINS['forward']} 2>/dev/null || true",
            f"iptables -t nat -D PREROUTING -j {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -D POSTROUTING -j {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -D FORWARD -j {MTD_CHAINS['forward']} 2>/dev/null || true",
            f"iptables -t nat -X {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -X {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -X {MTD_CHAINS['forward']} 2>/dev/null || true",
        ]
        self.executor.execute_batch(commands, "Cleanup MTD chains")
    
    def reset(self):
        self._init_services()
        self.config_history.clear()
        self.stats = {k: 0 if isinstance(v, int) else 0.0 for k, v in self.stats.items()}
        self._record_config()
    
    def shuffle(self, intensity: float) -> float:
        """네트워크 셔플"""
        n = max(1, int(len(self.services) * intensity))
        keys = list(self.services.keys())
        shuffled = np.random.choice(keys, min(n, len(keys)), replace=False)
        commands = []
        
        for svc_name in shuffled:
            svc = self.services[svc_name]
            old_vip, old_vport = svc.virtual_ip, svc.virtual_port
            new_vip = f"10.13.0.{np.random.randint(200, 250)}"
            new_vport = np.random.randint(10000, 60000)
            
            comment = self.executor._gen_comment("SHUFFLE")
            
            # 기존 규칙 삭제
            if old_vip != svc.real_ip or old_vport != svc.real_port:
                commands.append(
                    f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
                    f"-d {old_vip} -p {svc.protocol} --dport {old_vport} "
                    f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} 2>/dev/null || true"
                )
            
            # 새 DNAT 규칙
            commands.append(
                f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                f"-d {new_vip} -p {svc.protocol} --dport {new_vport} "
                f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} "
                f"-m comment --comment \"{comment}\""
            )
            
            # SNAT 규칙
            commands.append(
                f"iptables -t nat -A {MTD_CHAINS['postrouting']} "
                f"-s {svc.real_ip} -p {svc.protocol} --sport {svc.real_port} "
                f"-j SNAT --to-source {new_vip}:{new_vport} "
                f"-m comment --comment \"{comment}\""
            )
            
            svc.virtual_ip = new_vip
            svc.virtual_port = new_vport
        
        if commands:
            print(f"\n[MTD] Shuffle: {len(shuffled)} services (intensity={intensity:.2f})")
            self.executor.execute_batch(commands, f"Shuffle {len(shuffled)} services")
        
        self.stats['total_shuffles'] += 1
        self.stats['iptables_commands'] += len(commands)
        cost = intensity * ACTION_COSTS['shuffle']
        self.stats['total_cost'] += cost
        self._record_config()
        return cost
    
    def port_hop(self, intensity: float) -> float:
        """포트 호핑"""
        commands = []
        for svc in self.services.values():
            if svc.is_critical and np.random.random() < intensity:
                old_vport = svc.virtual_port
                new_vport = np.random.randint(10000, 60000)
                comment = self.executor._gen_comment("PORTHOP")
                
                if old_vport != svc.real_port:
                    commands.append(
                        f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
                        f"-d {svc.virtual_ip} -p {svc.protocol} --dport {old_vport} "
                        f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} 2>/dev/null || true"
                    )
                
                commands.append(
                    f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                    f"-d {svc.virtual_ip} -p {svc.protocol} --dport {new_vport} "
                    f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} "
                    f"-m comment --comment \"{comment}\""
                )
                svc.virtual_port = new_vport
        
        if commands:
            print(f"\n[MTD] Port Hop (intensity={intensity:.2f})")
            self.executor.execute_batch(commands, "Port hopping")
        
        self.stats['total_port_hops'] += 1
        self.stats['iptables_commands'] += len(commands)
        cost = intensity * ACTION_COSTS['port_hop']
        self.stats['total_cost'] += cost
        return cost
    
    def swap(self, intensity: float) -> float:
        """서비스 스왑"""
        keys = list(self.services.keys())
        if len(keys) < 2:
            return 0.0
        
        critical = [k for k in keys if self.services[k].is_critical]
        non_critical = [k for k in keys if not self.services[k].is_critical]
        
        if critical and non_critical:
            a, b = np.random.choice(critical), np.random.choice(non_critical)
        else:
            a, b = np.random.choice(keys, 2, replace=False)
        
        svc_a, svc_b = self.services[a], self.services[b]
        a_vip, a_vport = svc_a.virtual_ip, svc_a.virtual_port
        b_vip, b_vport = svc_b.virtual_ip, svc_b.virtual_port
        
        comment = self.executor._gen_comment("SWAP")
        commands = [
            # 기존 규칙 삭제
            f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
            f"-d {a_vip} -p {svc_a.protocol} --dport {a_vport} "
            f"-j DNAT --to-destination {svc_a.real_ip}:{svc_a.real_port} 2>/dev/null || true",
            f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
            f"-d {b_vip} -p {svc_b.protocol} --dport {b_vport} "
            f"-j DNAT --to-destination {svc_b.real_ip}:{svc_b.real_port} 2>/dev/null || true",
            # 스왑된 규칙 추가
            f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
            f"-d {a_vip} -p {svc_b.protocol} --dport {a_vport} "
            f"-j DNAT --to-destination {svc_b.real_ip}:{svc_b.real_port} "
            f"-m comment --comment \"{comment}_A2B\"",
            f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
            f"-d {b_vip} -p {svc_a.protocol} --dport {b_vport} "
            f"-j DNAT --to-destination {svc_a.real_ip}:{svc_a.real_port} "
            f"-m comment --comment \"{comment}_B2A\"",
        ]
        
        print(f"\n[MTD] Swap: {a} <-> {b} (intensity={intensity:.2f})")
        self.executor.execute_batch(commands, f"Swap {a} <-> {b}")
        
        svc_a.virtual_ip, svc_b.virtual_ip = b_vip, a_vip
        svc_a.virtual_port, svc_b.virtual_port = b_vport, a_vport
        
        self.stats['total_swaps'] += 1
        self.stats['iptables_commands'] += len(commands)
        cost = intensity * ACTION_COSTS['swap']
        self.stats['total_cost'] += cost
        self._record_config()
        return cost
    
    def activate_decoys(self, ratio: float) -> float:
        """디코이 활성화"""
        n = max(1, int(len(self.decoys) * ratio))
        decoy_keys = list(self.decoys.keys())[:n]
        commands = []
        
        for name in decoy_keys:
            decoy = self.decoys[name]
            comment = self.executor._gen_comment("DECOY")
            commands.append(
                f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                f"-d {decoy.virtual_ip} -p {decoy.protocol} --dport {decoy.virtual_port} "
                f"-j DNAT --to-destination {decoy.real_ip}:{decoy.real_port} "
                f"-m comment --comment \"{comment}\""
            )
            commands.append(
                f"iptables -A {MTD_CHAINS['forward']} "
                f"-d {decoy.real_ip} -p {decoy.protocol} --dport {decoy.real_port} "
                f"-j LOG --log-prefix \"[MTD-DECOY-HIT] \" --log-level 4 "
                f"-m comment --comment \"{comment}\""
            )
        
        if commands:
            print(f"\n[MTD] Activate Decoys: {n}")
            self.executor.execute_batch(commands, f"Activate {n} decoys")
        
        self.stats['total_decoy_activations'] += n
        self.stats['iptables_commands'] += len(commands)
        cost = ratio * ACTION_COSTS['decoy'] * n
        self.stats['total_cost'] += cost
        return cost
    
    def get_cdi(self) -> float:
        if len(self.config_history) <= 1:
            return 0.1
        unique = len(set(self.config_history))
        total = len(self.config_history)
        base = unique / total
        action_bonus = min(0.3, (self.stats['total_shuffles'] + self.stats['total_swaps']) * 0.02)
        return float(np.clip(base * 0.4 + action_bonus + 0.1, 0.1, 1.0))
    
    def get_targets(self) -> List[ServiceTarget]:
        return list(self.services.values()) + list(self.decoys.values())
    
    def print_status(self):
        """현재 MTD 상태 출력"""
        print(f"\n{'='*60}")
        print("Current MTD Status")
        print(f"{'='*60}")
        print(f"Shuffles: {self.stats['total_shuffles']}")
        print(f"Port Hops: {self.stats['total_port_hops']}")
        print(f"Swaps: {self.stats['total_swaps']}")
        print(f"Decoy Activations: {self.stats['total_decoy_activations']}")
        print(f"Total Cost: {self.stats['total_cost']:.3f}")
        print(f"iptables Commands: {self.stats['iptables_commands']}")
        print(f"CDI: {self.get_cdi():.3f}")
        print(f"\nService Mappings:")
        for name, svc in self.services.items():
            print(f"  {name}: {svc.virtual_ip}:{svc.virtual_port} -> {svc.real_ip}:{svc.real_port}")
        print(f"{'='*60}")


# =============================================================================
# CTI Detection Model
# =============================================================================
class CTIDetectionModel:
    def __init__(self):
        self.precision = 0.66
        self.recall = 0.85
        self.f1_score = 0.71
    
    def detect_attack(self, indicators: Dict) -> Tuple[bool, float]:
        threat_level = indicators.get('scan_intensity', 0) * 0.4 + indicators.get('exploit_attempts', 0) * 0.5
        detected = np.random.random() < self.recall if threat_level > 0.1 else False
        confidence = self.precision * np.random.uniform(0.8, 1.0) if detected else 0.0
        return detected, confidence


# =============================================================================
# Defense Probability Calculator
# =============================================================================
class DefenseProbabilityCalculator:
    P_BASE = 0.25
    BETA_CDI = 0.15
    
    def __init__(self):
        self.recent_effects = []
    
    def compute(self, intensities: Dict, cdi: float, step: int, cti_detected: bool = False) -> float:
        current_effect = sum(MTD_DEFENSE_WEIGHTS.get(a, 0) * i for a, i in intensities.items())
        self.recent_effects.append((step, current_effect))
        if len(self.recent_effects) > 10:
            self.recent_effects = self.recent_effects[-10:]
        residual = sum(e * 0.3 * (0.9 ** (step - s)) for s, e in self.recent_effects[:-1] if step > s)
        cti_bonus = 0.15 if cti_detected else 0.0
        p_def = self.P_BASE + current_effect + residual + self.BETA_CDI * cdi + cti_bonus
        return float(np.clip(p_def, 0.10, 0.95))
    
    def reset(self):
        self.recent_effects.clear()


# =============================================================================
# Main Execution
# =============================================================================
class TestbedMTDRunner:
    def __init__(self, model_path: str, dry_run: bool = True, device: str = "cpu"):
        self.dry_run = dry_run
        self.device = device
        self.running = True
        
        # Load RL model
        self.policy = None
        if TORCH_AVAILABLE and model_path and os.path.exists(model_path):
            print(f"✅ Loading RL model: {model_path}")
            self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
            ckpt = torch.load(model_path, map_location=device, weights_only=False)
            self.policy.load_state_dict(ckpt.get("policy", ckpt))
            self.policy.eval()
        else:
            print(f"⚠️ Model not found: {model_path}")
            print("   Using heuristic fallback...")
        
        self.mtd = RealMTDController(dry_run=dry_run)
        self.defense_calc = DefenseProbabilityCalculator()
        self.cti = CTIDetectionModel()
        
        # Signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print("\n\n⚠️ Received shutdown signal...")
        self.running = False
    
    def _scale_action(self, action: np.ndarray) -> np.ndarray:
        return (np.array(action) + 1.0) / 2.0
    
    def _build_state(self, step: int, threat_level: float = 0.0, last_action: np.ndarray = None) -> np.ndarray:
        if last_action is None:
            last_action = np.zeros(ACTION_DIM)
        scaled = self._scale_action(last_action)
        
        return np.array([
            threat_level * 0.5,      # scan_progress
            threat_level * 0.3,      # discovered_ratio
            float(threat_level > 0.5),  # critical_exposed
            threat_level * 0.2,      # exploited_ratio
            min(1.0, threat_level),  # attack_phase
            self.mtd.get_cdi(),      # cdi
            0.5,                     # redundancy
            0.1,                     # decoy_hit_ratio
            0.8,                     # attacker_energy
            min(1.0, self.mtd.stats['total_swaps'] / 10),
            min(1.0, step / 50),
            0.1,                     # confusion
            threat_level * 0.4,
            scaled[0], scaled[1], scaled[2],
            scaled[5] if len(scaled) > 5 else 0,
        ], dtype=np.float32)
    
    def get_action(self, state: np.ndarray, step: int) -> np.ndarray:
        """RL 모델에서 행동 결정"""
        if self.policy is not None:
            with torch.no_grad():
                t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                action, _, _ = self.policy.act(t, deterministic=True)
            return action.cpu().numpy().squeeze()
        else:
            # Heuristic fallback
            action = np.ones(ACTION_DIM) * -1.0
            threat = state[4]
            if threat > 0.5:
                action[0] = 0.7   # shuffle
                action[5] = 0.6   # swap
            elif threat > 0.3:
                action[0] = 0.5
                action[2] = 0.4
            elif threat > 0.1:
                action[1] = 0.4
            return action
    
    def execute_action(self, action: np.ndarray) -> Dict[str, float]:
        """MTD 행동 실행"""
        scaled = self._scale_action(action)
        intensities = {}
        
        if scaled[0] > ACTION_THRESHOLDS['shuffle']:
            self.mtd.shuffle(scaled[0])
            intensities['shuffle'] = float(scaled[0])
        
        if scaled[1] > ACTION_THRESHOLDS['port_hop']:
            self.mtd.port_hop(scaled[1])
            intensities['port_hop'] = float(scaled[1])
        
        if scaled[2] > ACTION_THRESHOLDS['decoy']:
            self.mtd.activate_decoys(scaled[2])
            intensities['decoy'] = float(scaled[2])
        
        if scaled[5] > ACTION_THRESHOLDS['swap']:
            self.mtd.swap(scaled[5])
            intensities['swap'] = float(scaled[5])
        
        return intensities
    
    def run_episode(self, max_steps: int = 200, threat_scenario: str = "normal"):
        """단일 에피소드 실행"""
        print(f"\n{'='*70}")
        print(f"Running Episode (max_steps={max_steps}, scenario={threat_scenario})")
        print(f"{'='*70}")
        
        self.mtd.reset()
        self.defense_calc.reset()
        
        last_action = np.zeros(ACTION_DIM)
        
        for step in range(max_steps):
            if not self.running:
                print("\n⚠️ Interrupted by user")
                break
            
            # Simulate threat level based on scenario
            if threat_scenario == "escalating":
                threat_level = min(1.0, step / max_steps)
            elif threat_scenario == "burst":
                threat_level = 0.8 if 50 <= step <= 100 else 0.2
            else:  # normal
                threat_level = 0.3 + np.random.random() * 0.3
            
            # Build state and get action
            state = self._build_state(step, threat_level, last_action)
            action = self.get_action(state, step)
            last_action = action.copy()
            
            # Execute MTD actions
            intensities = self.execute_action(action)
            
            # Calculate defense probability
            cti_detected, conf = self.cti.detect_attack({'scan_intensity': threat_level})
            p_def = self.defense_calc.compute(intensities, self.mtd.get_cdi(), step, cti_detected)
            
            # Progress output
            if (step + 1) % 20 == 0:
                print(f"\n  Step {step+1}/{max_steps}: threat={threat_level:.2f}, p_def={p_def:.2f}, "
                      f"cost={self.mtd.stats['total_cost']:.3f}")
            
            time.sleep(0.1)  # Small delay for real system
        
        self.mtd.print_status()
    
    def run_realtime(self, duration_sec: int = 300, interval_sec: float = 5.0):
        """실시간 방어 모드"""
        print(f"\n{'='*70}")
        print(f"Real-time Defense Mode (duration={duration_sec}s, interval={interval_sec}s)")
        print(f"{'='*70}")
        print("Press Ctrl+C to stop\n")
        
        self.mtd.init_chains()
        self.mtd.reset()
        self.defense_calc.reset()
        
        start_time = time.time()
        step = 0
        last_action = np.zeros(ACTION_DIM)
        
        try:
            while self.running and (time.time() - start_time) < duration_sec:
                elapsed = time.time() - start_time
                remaining = duration_sec - elapsed
                
                # Simulated threat detection (실제로는 네트워크 모니터링 연동)
                threat_level = 0.2 + np.random.random() * 0.4
                
                state = self._build_state(step, threat_level, last_action)
                action = self.get_action(state, step)
                last_action = action.copy()
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Step {step} | "
                      f"Remaining: {remaining:.0f}s | Threat: {threat_level:.2f}")
                
                intensities = self.execute_action(action)
                
                cti_detected, conf = self.cti.detect_attack({'scan_intensity': threat_level})
                if cti_detected:
                    print(f"  ⚠️ CTI Alert: confidence={conf:.2f}")
                
                step += 1
                time.sleep(interval_sec)
        
        finally:
            print("\n\nFinal Status:")
            self.mtd.print_status()
            
            if not self.dry_run:
                self.mtd.cleanup()
    
    def cleanup(self):
        if not self.dry_run:
            self.mtd.cleanup()


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Real Testbed MTD Execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run test (iptables 명령어만 출력)
  python run_testbed_mtd.py --model best_model.pt --dry-run --episodes 5

  # 실제 iptables 적용 (root 필요)
  sudo python run_testbed_mtd.py --model best_model.pt --episodes 10

  # 실시간 방어 모드 (5분간)
  sudo python run_testbed_mtd.py --model best_model.pt --realtime --duration 300

  # 특정 시나리오 테스트
  python run_testbed_mtd.py --model best_model.pt --dry-run --scenario escalating
        """
    )
    parser.add_argument("--model", type=str, required=True, help="학습된 모델 경로 (.pt)")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run 모드 (명령어만 출력)")
    parser.add_argument("--device", type=str, default="cpu", help="PyTorch device")
    parser.add_argument("--episodes", type=int, default=1, help="실행할 에피소드 수")
    parser.add_argument("--max-steps", type=int, default=200, help="에피소드당 최대 스텝")
    parser.add_argument("--scenario", type=str, default="normal", 
                       choices=["normal", "escalating", "burst"], help="위협 시나리오")
    parser.add_argument("--realtime", action="store_true", help="실시간 방어 모드")
    parser.add_argument("--duration", type=int, default=300, help="실시간 모드 지속 시간(초)")
    parser.add_argument("--interval", type=float, default=5.0, help="실시간 모드 간격(초)")
    
    args = parser.parse_args()
    
    mode_str = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\n{'='*70}")
    print(f"MTD-RL Testbed Runner [{mode_str}]")
    print(f"{'='*70}")
    print(f"Model: {args.model}")
    print(f"Mode: {'Realtime' if args.realtime else 'Episode'}")
    
    if not args.dry_run:
        if os.geteuid() != 0:
            print("\n❌ Error: Root privileges required for live mode!")
            print("   Run with: sudo python run_testbed_mtd.py ...")
            sys.exit(1)
        print("\n⚠️ WARNING: Live mode will modify iptables rules!")
        confirm = input("Continue? [y/N]: ")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
    
    runner = TestbedMTDRunner(
        model_path=args.model,
        dry_run=args.dry_run,
        device=args.device,
    )
    
    try:
        if args.realtime:
            runner.run_realtime(
                duration_sec=args.duration,
                interval_sec=args.interval,
            )
        else:
            for ep in range(args.episodes):
                print(f"\n\n{'#'*70}")
                print(f"Episode {ep+1}/{args.episodes}")
                print(f"{'#'*70}")
                runner.run_episode(
                    max_steps=args.max_steps,
                    threat_scenario=args.scenario,
                )
    finally:
        runner.cleanup()


if __name__ == "__main__":
    main()