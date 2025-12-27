#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RL-Driven Deception Manager v09.8 - Real iptables Integration
==============================================================

실제 iptables 명령어를 생성하고 실행하는 MTD 컨트롤러

Usage:
    # 시뮬레이션 실험 (iptables 없이)
    python rl_driven_deception_manager_v09.py --experiment --episodes 50

    # 실제 테스트베드 (명령어만 출력)
    python rl_driven_deception_manager_v09.py --model best.pt --testbed --dry-run

    # 실제 테스트베드 (iptables 실행, root 필요)
    sudo python rl_driven_deception_manager_v09.py --model best.pt --testbed

    # 특정 레벨만 테스트
    python rl_driven_deception_manager_v09.py --testbed --dry-run --level 4 --episodes 10

Author: MTD-RL Research Team
Version: 0.9.8
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# PyTorch (optional)
TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Constants
# =============================================================================
STATE_DIM = 17
ACTION_DIM = 7

ACTION_THRESHOLDS = {
    'shuffle': 0.25,
    'port_hop': 0.35,
    'decoy': 0.40,
    'blacklist': 0.60,
    'swap': 0.30,
}

ACTION_COSTS = {
    'shuffle': 0.05,
    'port_hop': 0.03,
    'decoy': 0.02,
    'blacklist': 0.02,
    'swap': 0.05,
}

MTD_DEFENSE_WEIGHTS = {
    'shuffle': 0.35,
    'port_hop': 0.20,
    'decoy': 0.15,
    'blacklist': 0.10,
    'swap': 0.45,
}

ATTACKER_PROFILES = {
    0: {"name": "Script Kiddie", "scan_rate": 0.03, "p_disc": 0.15, 
        "p_exp": 0.08, "decoy_detection": 0.1, "energy_decay": 0.008, "kappa": 1.00},
    1: {"name": "Hobbyist", "scan_rate": 0.05, "p_disc": 0.25,
        "p_exp": 0.12, "decoy_detection": 0.2, "energy_decay": 0.006, "kappa": 0.92},
    2: {"name": "Professional", "scan_rate": 0.08, "p_disc": 0.35,
        "p_exp": 0.20, "decoy_detection": 0.35, "energy_decay": 0.004, "kappa": 0.84},
    3: {"name": "Expert", "scan_rate": 0.12, "p_disc": 0.50,
        "p_exp": 0.30, "decoy_detection": 0.5, "energy_decay": 0.003, "kappa": 0.76},
    4: {"name": "APT", "scan_rate": 0.15, "p_disc": 0.65,
        "p_exp": 0.40, "decoy_detection": 0.65, "energy_decay": 0.002, "kappa": 0.68},
}

# Table 8: Testbed Services
SERVICES_CONFIG = {
    "fc_mavlink": {"real_ip": "10.13.0.10", "real_port": 14550, "protocol": "udp", "is_critical": True},
    "cc_sitl": {"real_ip": "10.13.0.11", "real_port": 5760, "protocol": "tcp", "is_critical": True},
    "cc_mavlink": {"real_ip": "10.13.0.11", "real_port": 14550, "protocol": "udp", "is_critical": False},
    "gcs_web": {"real_ip": "10.13.0.20", "real_port": 3000, "protocol": "tcp", "is_critical": True},
    "video_stream": {"real_ip": "10.13.0.12", "real_port": 554, "protocol": "tcp", "is_critical": False},
    "telemetry_db": {"real_ip": "10.13.0.14", "real_port": 5432, "protocol": "tcp", "is_critical": False},
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


def to_python(obj):
    """numpy 타입을 Python 기본 타입으로 변환"""
    if obj is None:
        return None
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (list, tuple)):
        return [to_python(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_python(v) for k, v in obj.items()}
    return obj


def scale_action(action: np.ndarray) -> np.ndarray:
    """[-1,1] -> [0,1] 스케일링"""
    return (np.array(action) + 1.0) / 2.0


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
    vulnerability_score: float = 0.5
    scan_progress: float = 0.0
    discovery_progress: float = 0.0
    exploit_progress: float = 0.0


# =============================================================================
# iptables Command Executor
# =============================================================================
class IptablesExecutor:
    """iptables 명령어 실행기"""
    
    def __init__(self, dry_run: bool = True, log_file: str = None):
        self.dry_run = dry_run
        self.command_history: List[Dict] = []
        self.rule_counter = 0
        self.log_file = log_file
        
        if log_file:
            self.log_path = Path(log_file)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _gen_comment(self, action: str) -> str:
        """규칙 주석 생성"""
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
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
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
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + "\n")
        
        return entry["success"]
    
    def execute_batch(self, commands: List[str], description: str = "") -> int:
        """여러 명령어 배치 실행"""
        success_count = 0
        for cmd in commands:
            if self.execute(cmd, description):
                success_count += 1
        return success_count


# =============================================================================
# MTD Controller with iptables
# =============================================================================
class MTDController:
    """MTD 컨트롤러 - iptables 연동"""
    
    def __init__(self, testbed_mode: bool = False, dry_run: bool = True, log_file: str = None):
        self.testbed_mode = testbed_mode
        self.dry_run = dry_run
        
        self.services: Dict[str, ServiceTarget] = {}
        self.decoys: Dict[str, ServiceTarget] = {}
        self.blacklist: set = set()
        
        self.stats = {
            'total_shuffles': 0,
            'total_port_hops': 0,
            'total_swaps': 0,
            'total_decoy_activations': 0,
            'total_blacklists': 0,
            'total_cost': 0.0,
        }
        
        self.config_history: deque = deque(maxlen=50)
        self.last_config: Optional[str] = None
        
        if testbed_mode:
            self.executor = IptablesExecutor(dry_run=dry_run, log_file=log_file)
        else:
            self.executor = None
        
        self._init_services()
    
    def _init_services(self):
        """서비스 초기화"""
        for name, cfg in SERVICES_CONFIG.items():
            self.services[name] = ServiceTarget(
                name=name,
                real_ip=cfg["real_ip"],
                real_port=cfg["real_port"],
                virtual_ip=cfg["real_ip"],
                virtual_port=cfg["real_port"],
                protocol=cfg["protocol"],
                is_critical=cfg.get("is_critical", False),
                vulnerability_score=np.random.uniform(0.3, 0.7),
            )
        
        for name, cfg in DECOYS_CONFIG.items():
            self.decoys[name] = ServiceTarget(
                name=name,
                real_ip=cfg["real_ip"],
                real_port=cfg["real_port"],
                virtual_ip=cfg["real_ip"],
                virtual_port=cfg["real_port"],
                protocol=cfg["protocol"],
                is_decoy=True,
            )
        
        self._record_config()
    
    def _get_config_snapshot(self) -> str:
        """현재 구성 스냅샷"""
        configs = sorted([f"{s.virtual_ip}:{s.virtual_port}" for s in self.services.values()])
        return "|".join(configs)
    
    def _record_config(self):
        """구성 변경 기록"""
        current = self._get_config_snapshot()
        if current != self.last_config:
            self.config_history.append(current)
            self.last_config = current
    
    def reset(self):
        """상태 초기화"""
        self._init_services()
        self.blacklist.clear()
        self.stats = {k: 0 if isinstance(v, int) else 0.0 for k, v in self.stats.items()}
        self.config_history.clear()
        self.last_config = None
        self._record_config()
        
        if self.testbed_mode:
            self._flush_mtd_rules()
    
    # =========================================================================
    # iptables Chain Management
    # =========================================================================
    def init_iptables_chains(self):
        """MTD 체인 초기화"""
        if not self.testbed_mode:
            return
        
        print("\n[iptables] Initializing MTD chains...")
        
        commands = [
            # nat 테이블 체인 생성
            f"iptables -t nat -N {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -N {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            # filter 테이블 체인 생성
            f"iptables -N {MTD_CHAINS['forward']} 2>/dev/null || true",
            # 메인 체인에 점프 규칙 추가
            f"iptables -t nat -C PREROUTING -j {MTD_CHAINS['prerouting']} 2>/dev/null || "
            f"iptables -t nat -I PREROUTING -j {MTD_CHAINS['prerouting']}",
            f"iptables -t nat -C POSTROUTING -j {MTD_CHAINS['postrouting']} 2>/dev/null || "
            f"iptables -t nat -I POSTROUTING -j {MTD_CHAINS['postrouting']}",
            f"iptables -C FORWARD -j {MTD_CHAINS['forward']} 2>/dev/null || "
            f"iptables -I FORWARD -j {MTD_CHAINS['forward']}",
        ]
        
        self.executor.execute_batch(commands, "Initialize MTD chains")
    
    def _flush_mtd_rules(self):
        """MTD 규칙 초기화"""
        if not self.testbed_mode:
            return
        
        print("\n[iptables] Flushing MTD rules...")
        
        commands = [
            f"iptables -t nat -F {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -F {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -F {MTD_CHAINS['forward']} 2>/dev/null || true",
        ]
        
        self.executor.execute_batch(commands, "Flush MTD rules")
    
    def cleanup_iptables(self):
        """iptables 정리"""
        if not self.testbed_mode:
            return
        
        print("\n[iptables] Cleaning up...")
        
        commands = [
            # 규칙 삭제
            f"iptables -t nat -F {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -F {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -F {MTD_CHAINS['forward']} 2>/dev/null || true",
            # 점프 규칙 삭제
            f"iptables -t nat -D PREROUTING -j {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -D POSTROUTING -j {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -D FORWARD -j {MTD_CHAINS['forward']} 2>/dev/null || true",
            # 체인 삭제
            f"iptables -t nat -X {MTD_CHAINS['prerouting']} 2>/dev/null || true",
            f"iptables -t nat -X {MTD_CHAINS['postrouting']} 2>/dev/null || true",
            f"iptables -X {MTD_CHAINS['forward']} 2>/dev/null || true",
        ]
        
        self.executor.execute_batch(commands, "Cleanup MTD chains")
    
    # =========================================================================
    # MTD Actions with iptables
    # =========================================================================
    def shuffle(self, intensity: float) -> Tuple[float, List[str]]:
        """
        네트워크 셔플 - IP/Port 변경
        
        iptables 명령어:
        - DNAT: 가상 IP -> 실제 IP
        - SNAT: 응답 패킷 소스 변경
        """
        commands = []
        n = max(1, int(len(self.services) * intensity))
        keys = list(self.services.keys())
        shuffled = np.random.choice(keys, min(n, len(keys)), replace=False)
        
        for svc_name in shuffled:
            svc = self.services[svc_name]
            old_vip = svc.virtual_ip
            old_vport = svc.virtual_port
            
            # 새 가상 주소 생성
            new_vip = f"10.13.0.{np.random.randint(200, 250)}"
            new_vport = np.random.randint(10000, 60000)
            
            if self.testbed_mode:
                comment = self.executor._gen_comment("SHUFFLE")
                
                # 기존 DNAT 규칙 삭제
                if old_vip != svc.real_ip or old_vport != svc.real_port:
                    commands.append(
                        f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
                        f"-d {old_vip} -p {svc.protocol} --dport {old_vport} "
                        f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} 2>/dev/null || true"
                    )
                
                # 새 DNAT 규칙 (가상 -> 실제)
                commands.append(
                    f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                    f"-d {new_vip} -p {svc.protocol} --dport {new_vport} "
                    f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} "
                    f"-m comment --comment \"{comment}\""
                )
                
                # SNAT 규칙 (응답 패킷)
                commands.append(
                    f"iptables -t nat -A {MTD_CHAINS['postrouting']} "
                    f"-s {svc.real_ip} -p {svc.protocol} --sport {svc.real_port} "
                    f"-j SNAT --to-source {new_vip}:{new_vport} "
                    f"-m comment --comment \"{comment}\""
                )
                
                # FORWARD 허용
                commands.append(
                    f"iptables -A {MTD_CHAINS['forward']} "
                    f"-d {svc.real_ip} -p {svc.protocol} --dport {svc.real_port} "
                    f"-j ACCEPT -m comment --comment \"{comment}\""
                )
            
            # 상태 업데이트
            svc.virtual_ip = new_vip
            svc.virtual_port = new_vport
        
        if self.testbed_mode and commands:
            print(f"\n[MTD] Shuffle: {len(shuffled)} services")
            self.executor.execute_batch(commands, f"Shuffle {len(shuffled)} services")
        
        self.stats['total_shuffles'] += 1
        cost = intensity * ACTION_COSTS['shuffle']
        self.stats['total_cost'] += cost
        self._record_config()
        
        return cost, commands
    
    def port_hop(self, intensity: float) -> Tuple[float, List[str]]:
        """
        포트 호핑 - Critical 서비스 포트 변경
        """
        commands = []
        changed = False
        
        for svc in self.services.values():
            if svc.is_critical and np.random.random() < intensity:
                old_vport = svc.virtual_port
                new_vport = np.random.randint(10000, 60000)
                
                if self.testbed_mode:
                    comment = self.executor._gen_comment("PORTHOP")
                    
                    # 기존 규칙 삭제
                    if old_vport != svc.real_port:
                        commands.append(
                            f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
                            f"-d {svc.virtual_ip} -p {svc.protocol} --dport {old_vport} "
                            f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} 2>/dev/null || true"
                        )
                    
                    # 새 포트 DNAT
                    commands.append(
                        f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                        f"-d {svc.virtual_ip} -p {svc.protocol} --dport {new_vport} "
                        f"-j DNAT --to-destination {svc.real_ip}:{svc.real_port} "
                        f"-m comment --comment \"{comment}\""
                    )
                
                svc.virtual_port = new_vport
                changed = True
        
        if self.testbed_mode and commands:
            print(f"\n[MTD] Port Hop")
            self.executor.execute_batch(commands, "Port hopping")
        
        self.stats['total_port_hops'] += 1
        cost = intensity * ACTION_COSTS['port_hop']
        self.stats['total_cost'] += cost
        
        if changed:
            self._record_config()
        
        return cost, commands
    
    def swap(self, intensity: float, target_critical: bool = True) -> Tuple[float, List[str]]:
        """
        서비스 스왑 - 두 서비스의 가상 주소 교환
        """
        commands = []
        keys = list(self.services.keys())
        
        if len(keys) < 2:
            return 0.0, []
        
        # 스왑 대상 선택
        if target_critical:
            critical = [k for k in keys if self.services[k].is_critical]
            non_critical = [k for k in keys if not self.services[k].is_critical]
            if critical and non_critical:
                a, b = np.random.choice(critical), np.random.choice(non_critical)
            else:
                a, b = np.random.choice(keys, 2, replace=False)
        else:
            a, b = np.random.choice(keys, 2, replace=False)
        
        svc_a, svc_b = self.services[a], self.services[b]
        
        # 현재 가상 주소 저장
        a_vip, a_vport = svc_a.virtual_ip, svc_a.virtual_port
        b_vip, b_vport = svc_b.virtual_ip, svc_b.virtual_port
        
        if self.testbed_mode:
            comment = self.executor._gen_comment("SWAP")
            
            # 기존 규칙 삭제
            commands.append(
                f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
                f"-d {a_vip} -p {svc_a.protocol} --dport {a_vport} "
                f"-j DNAT --to-destination {svc_a.real_ip}:{svc_a.real_port} 2>/dev/null || true"
            )
            commands.append(
                f"iptables -t nat -D {MTD_CHAINS['prerouting']} "
                f"-d {b_vip} -p {svc_b.protocol} --dport {b_vport} "
                f"-j DNAT --to-destination {svc_b.real_ip}:{svc_b.real_port} 2>/dev/null || true"
            )
            
            # 스왑된 규칙 추가: A의 가상주소 -> B의 실제주소
            commands.append(
                f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                f"-d {a_vip} -p {svc_b.protocol} --dport {a_vport} "
                f"-j DNAT --to-destination {svc_b.real_ip}:{svc_b.real_port} "
                f"-m comment --comment \"{comment}_A2B\""
            )
            
            # B의 가상주소 -> A의 실제주소
            commands.append(
                f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                f"-d {b_vip} -p {svc_a.protocol} --dport {b_vport} "
                f"-j DNAT --to-destination {svc_a.real_ip}:{svc_a.real_port} "
                f"-m comment --comment \"{comment}_B2A\""
            )
            
            print(f"\n[MTD] Swap: {a} <-> {b}")
            self.executor.execute_batch(commands, f"Swap {a} <-> {b}")
        
        # 가상 주소 교환
        svc_a.virtual_ip, svc_b.virtual_ip = b_vip, a_vip
        svc_a.virtual_port, svc_b.virtual_port = b_vport, a_vport
        
        self.stats['total_swaps'] += 1
        cost = intensity * ACTION_COSTS['swap']
        self.stats['total_cost'] += cost
        self._record_config()
        
        return cost, commands
    
    def activate_decoys(self, ratio: float) -> Tuple[float, List[str]]:
        """
        디코이 활성화 - Honeypot DNAT 규칙
        """
        commands = []
        n = max(1, int(len(self.decoys) * ratio))
        decoy_keys = list(self.decoys.keys())[:n]
        
        if self.testbed_mode:
            comment = self.executor._gen_comment("DECOY")
            
            for name in decoy_keys:
                decoy = self.decoys[name]
                
                # 허니팟으로 리다이렉트
                commands.append(
                    f"iptables -t nat -A {MTD_CHAINS['prerouting']} "
                    f"-d {decoy.virtual_ip} -p {decoy.protocol} --dport {decoy.virtual_port} "
                    f"-j DNAT --to-destination {decoy.real_ip}:{decoy.real_port} "
                    f"-m comment --comment \"{comment}\""
                )
                
                # 로깅 (허니팟 접근 감지)
                commands.append(
                    f"iptables -A {MTD_CHAINS['forward']} "
                    f"-d {decoy.real_ip} -p {decoy.protocol} --dport {decoy.real_port} "
                    f"-j LOG --log-prefix \"[MTD-DECOY-HIT] \" --log-level 4 "
                    f"-m comment --comment \"{comment}\""
                )
            
            print(f"\n[MTD] Activate Decoys: {n}")
            self.executor.execute_batch(commands, f"Activate {n} decoys")
        
        self.stats['total_decoy_activations'] += n
        cost = ratio * ACTION_COSTS['decoy'] * n
        self.stats['total_cost'] += cost
        
        return cost, commands
    
    def blacklist_ip(self, ip: str, duration: int = 300) -> Tuple[float, List[str]]:
        """
        IP 블랙리스트 - 특정 IP 차단
        """
        commands = []
        
        if ip in self.blacklist:
            return 0.0, []
        
        if self.testbed_mode:
            comment = self.executor._gen_comment("BLACKLIST")
            
            # INPUT/FORWARD 차단
            commands.append(
                f"iptables -I INPUT -s {ip} -j DROP "
                f"-m comment --comment \"{comment}\""
            )
            commands.append(
                f"iptables -I FORWARD -s {ip} -j DROP "
                f"-m comment --comment \"{comment}\""
            )
            
            # 로깅
            commands.append(
                f"iptables -I INPUT -s {ip} "
                f"-j LOG --log-prefix \"[MTD-BLOCKED] \" --log-level 4 "
                f"-m comment --comment \"{comment}\""
            )
            
            print(f"\n[MTD] Blacklist IP: {ip}")
            self.executor.execute_batch(commands, f"Blacklist {ip}")
        
        self.blacklist.add(ip)
        self.stats['total_blacklists'] += 1
        cost = ACTION_COSTS['blacklist']
        self.stats['total_cost'] += cost
        
        return cost, commands
    
    # =========================================================================
    # Metrics
    # =========================================================================
    def get_cdi(self) -> float:
        """CDI 계산 - 시간에 따른 구성 변화 다양성"""
        if len(self.config_history) <= 1:
            return 0.1
        
        unique_configs = len(set(self.config_history))
        total_configs = len(self.config_history)
        base_diversity = unique_configs / total_configs
        
        recent_changes = 0
        history_list = list(self.config_history)
        for i in range(1, min(10, len(history_list))):
            if i < len(history_list) and history_list[-i] != history_list[-i-1]:
                recent_changes += 1
        
        recency_bonus = recent_changes / 10 * 0.3
        total_actions = (self.stats['total_shuffles'] + 
                        self.stats['total_port_hops'] + 
                        self.stats['total_swaps'])
        action_bonus = min(0.3, total_actions * 0.02)
        
        cdi = base_diversity * 0.4 + recency_bonus + action_bonus + 0.1
        return float(np.clip(cdi, 0.1, 1.0))
    
    def get_redundancy(self) -> float:
        """Redundancy 계산"""
        active = self.stats['total_decoy_activations'] / max(1, len(self.decoys) * 10)
        swap_bonus = min(0.3, self.stats['total_swaps'] * 0.05)
        return min(1.0, active * 0.6 + swap_bonus + 0.1)
    
    def get_targets(self) -> List[ServiceTarget]:
        return list(self.services.values()) + list(self.decoys.values())
    
    def get_iptables_summary(self) -> Dict:
        """iptables 명령어 요약"""
        if not self.testbed_mode or not self.executor:
            return {}
        
        return {
            "total_commands": len(self.executor.command_history),
            "successful": sum(1 for c in self.executor.command_history if c["success"]),
            "failed": sum(1 for c in self.executor.command_history if not c["success"]),
            "dry_run": self.dry_run,
        }


# =============================================================================
# CTI Detection Model
# =============================================================================
@dataclass
class CTIDetectionModel:
    precision: float = 0.66
    recall: float = 0.85
    f1_score: float = 0.71
    
    class_performance: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "Normal": {"precision": 0.87, "recall": 0.73, "f1": 0.79},
        "Brute-force": {"precision": 0.67, "recall": 0.94, "f1": 0.78},
        "Battery-spoofing": {"precision": 0.60, "recall": 0.90, "f1": 0.72},
        "Flight-term": {"precision": 0.68, "recall": 0.85, "f1": 0.75},
        "GPS-inject": {"precision": 0.39, "recall": 0.92, "f1": 0.54},
    })
    
    def detect_attack(self, attack_type: str = "scan") -> Tuple[bool, float, str]:
        attack_mapping = {
            "scan": "Brute-force",
            "exploit": "Flight-term",
            "gps_spoof": "GPS-inject",
            "battery": "Battery-spoofing",
        }
        mapped_class = attack_mapping.get(attack_type, "Normal")
        perf = self.class_performance.get(mapped_class, self.class_performance["Normal"])
        detected = np.random.random() < perf["recall"]
        confidence = perf["precision"] * np.random.uniform(0.8, 1.0) if detected else np.random.uniform(0.1, 0.4)
        return detected, float(confidence), mapped_class
    
    def get_threat_level(self, indicators: Dict[str, float]) -> float:
        base_threat = 0.0
        if indicators.get('scan_intensity', 0) > 0.1:
            detected, conf, _ = self.detect_attack("scan")
            if detected:
                base_threat += indicators['scan_intensity'] * conf * 0.4
        if indicators.get('exploit_attempts', 0) > 0:
            detected, conf, _ = self.detect_attack("exploit")
            if detected:
                base_threat += indicators['exploit_attempts'] * conf * 0.5
        return min(1.0, base_threat * self.f1_score)


# =============================================================================
# Attack Phase & Attacker Agent
# =============================================================================
class AttackPhase:
    INITIAL = "initial"
    RECONNAISSANCE = "reconnaissance"
    DISCOVERY = "discovery"
    EXPLOITATION = "exploitation"
    PERSISTENCE = "persistence"
    BREACH = "breach"
    DEFENDED = "defended"


class AttackerAgent:
    def __init__(self, level: int = 2, seed: int = 42, targets: List[ServiceTarget] = None):
        self.level = level
        self.profile = ATTACKER_PROFILES.get(level, ATTACKER_PROFILES[2])
        np.random.seed(seed)
        
        self.phase = AttackPhase.INITIAL
        self.energy = 1.0
        self.confusion_level = 0.0
        self.step_count = 0
        
        self.scanned_ips: set = set()
        self.discovered_services: set = set()
        self.exploited_services: set = set()
        self.decoy_hits = 0
        
        self.targets = targets or []
        self.cti = CTIDetectionModel()
    
    def reset(self, seed: int = None):
        if seed:
            np.random.seed(seed)
        self.phase = AttackPhase.INITIAL
        self.energy = 1.0
        self.confusion_level = 0.0
        self.step_count = 0
        self.scanned_ips.clear()
        self.discovered_services.clear()
        self.exploited_services.clear()
        self.decoy_hits = 0
    
    def set_targets(self, targets: List[ServiceTarget]):
        self.targets = targets
    
    def step(self, mtd_status: Dict[str, Any]) -> Dict[str, Any]:
        self.step_count += 1
        result = {
            "phase": self.phase, "scanned": False, "discovered": False,
            "exploited": False, "breach": False, "decoy_hit": False,
            "defended": False, "cti_detected": False, "energy": self.energy,
        }
        
        shuffle_intensity = mtd_status.get('shuffle_intensity', 0)
        swap_intensity = mtd_status.get('swap_intensity', 0)
        defense_prob = mtd_status.get('defense_probability', 0.25)
        
        if mtd_status.get('is_shuffle', False):
            self.confusion_level += shuffle_intensity * 0.3
        if mtd_status.get('is_swap', False):
            self.confusion_level += swap_intensity * 0.4
        self.confusion_level *= 0.92
        
        self.energy -= self.profile["energy_decay"]
        if self.energy <= 0:
            self.phase = AttackPhase.DEFENDED
            result["defended"] = True
            return result
        
        confusion_penalty = min(0.6, self.confusion_level * 0.5)
        effective_rate = max(0.05, 1.0 - confusion_penalty)
        
        cti_indicators = {
            'scan_intensity': len(self.scanned_ips) / 254,
            'exploit_attempts': len(self.exploited_services) / max(1, len(self.targets)),
        }
        cti_threat = self.cti.get_threat_level(cti_indicators)
        if cti_threat > 0.3:
            result["cti_detected"] = True
            defense_prob = min(0.9, defense_prob + cti_threat * 0.3)
        
        if self.phase == AttackPhase.INITIAL:
            self.phase = AttackPhase.RECONNAISSANCE
        elif self.phase == AttackPhase.RECONNAISSANCE:
            n_scan = int(254 * self.profile["scan_rate"] * effective_rate)
            for _ in range(n_scan):
                ip = f"10.13.0.{np.random.randint(1, 255)}"
                if np.random.random() >= defense_prob * 0.3:
                    self.scanned_ips.add(ip)
                    result["scanned"] = True
            if len(self.scanned_ips) > 5 and np.random.random() < 0.3 * (1 - defense_prob * 0.3):
                self.phase = AttackPhase.DISCOVERY
        elif self.phase == AttackPhase.DISCOVERY:
            for target in self.targets:
                if target.name in self.discovered_services or target.virtual_ip not in self.scanned_ips:
                    continue
                if np.random.random() < defense_prob * 0.5:
                    result["defended"] = True
                    continue
                if target.is_decoy and np.random.random() >= self.profile["decoy_detection"]:
                    self.decoy_hits += 1
                    result["decoy_hit"] = True
                    self.energy -= 0.1
                    continue
                if np.random.random() < self.profile["p_disc"] * effective_rate:
                    target.discovery_progress += 0.4
                    if target.discovery_progress >= 0.8:
                        self.discovered_services.add(target.name)
                        result["discovered"] = True
            if len(self.discovered_services) >= 1 and np.random.random() < 0.4 * (1 - defense_prob * 0.4):
                self.phase = AttackPhase.EXPLOITATION
        elif self.phase == AttackPhase.EXPLOITATION:
            for target in self.targets:
                if target.name not in self.discovered_services or target.name in self.exploited_services:
                    continue
                if np.random.random() < defense_prob * 0.7:
                    result["defended"] = True
                    continue
                exploit_prob = self.profile["p_exp"] * target.vulnerability_score * effective_rate
                if np.random.random() < exploit_prob:
                    target.exploit_progress += 0.5
                    if target.exploit_progress >= 0.9:
                        self.exploited_services.add(target.name)
                        result["exploited"] = True
                        if target.is_critical:
                            self.phase = AttackPhase.PERSISTENCE
        elif self.phase == AttackPhase.PERSISTENCE:
            if np.random.random() < defense_prob * 0.8:
                result["defended"] = True
            else:
                critical_exploited = any(t.is_critical and t.name in self.exploited_services for t in self.targets)
                if critical_exploited and np.random.random() < 0.3 * (1 - defense_prob):
                    self.phase = AttackPhase.BREACH
                    result["breach"] = True
        
        result["phase"] = self.phase
        result["energy"] = self.energy
        return result


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
# Defense Probability Calculator
# =============================================================================
class DefenseProbabilityCalculator:
    P_BASE = 0.25
    BETA_CDI = 0.15
    
    def __init__(self):
        self.recent_effects: List[Tuple[int, float]] = []
    
    def compute(self, action_intensities: Dict, cdi: float, attacker_level: int, 
                step: int, cti_detected: bool = False) -> float:
        current_effect = sum(MTD_DEFENSE_WEIGHTS.get(a, 0) * i for a, i in action_intensities.items())
        self.recent_effects.append((step, current_effect))
        if len(self.recent_effects) > 10:
            self.recent_effects = self.recent_effects[-10:]
        residual = sum(e * 0.3 * (0.9 ** (step - s)) for s, e in self.recent_effects[:-1] if step > s)
        kappa = ATTACKER_PROFILES[attacker_level]["kappa"]
        cti_bonus = 0.15 if cti_detected else 0.0
        p_def = (self.P_BASE + current_effect + residual + self.BETA_CDI * cdi + cti_bonus) * kappa
        return float(np.clip(p_def, 0.10, 0.95))
    
    def reset(self):
        self.recent_effects.clear()


# =============================================================================
# Episode Result
# =============================================================================
@dataclass
class EpisodeResult:
    episode_id: int = 0
    strategy_name: str = ""
    attacker_level: int = 0
    steps: int = 0
    breach_occurred: bool = False
    total_cost: float = 0.0
    mttc: int = 200
    asr: float = 0.0
    cdi: float = 0.0
    redundancy: float = 0.0
    des: float = 0.0
    cer: float = 0.0
    shuffle_count: int = 0
    swap_count: int = 0
    decoy_hits: int = 0
    services_discovered: int = 0
    services_exploited: int = 0
    final_phase: str = "initial"
    cti_detections: int = 0
    iptables_commands: int = 0


# =============================================================================
# Strategies
# =============================================================================
class BaselineStrategy:
    def __init__(self, name: str):
        self.name = name
    def get_action(self, state, step) -> np.ndarray:
        raise NotImplementedError
    def reset(self):
        pass


class NoMTDStrategy(BaselineStrategy):
    def __init__(self):
        super().__init__("Baseline")
    def get_action(self, state, step):
        return np.ones(ACTION_DIM) * -1.0


class StaticMTDStrategy(BaselineStrategy):
    def __init__(self, period: int = 30):
        super().__init__("Static MTD")
        self.period = period
    def get_action(self, state, step):
        action = np.ones(ACTION_DIM) * -1.0
        if step % self.period == 0:
            action[0] = 0.8
            action[1] = 0.5
        return action


class HeuristicCTIStrategy(BaselineStrategy):
    def __init__(self, threshold: float = 0.7):
        super().__init__("Heuristic+CTI")
        self.threshold = threshold
        self.cti = CTIDetectionModel()
    
    def get_action(self, state, step):
        action = np.ones(ACTION_DIM) * -1.0
        threat = state[1] * 0.3 + state[3] * 0.5 + state[4] * 0.2 if len(state) > 4 else 0.2
        detected, conf, _ = self.cti.detect_attack("scan")
        if detected and conf > self.threshold:
            action[0] = 0.8
            action[5] = 0.7
        elif threat > 0.5:
            action[0] = 0.6
            action[2] = 0.5
        elif threat > 0.3:
            action[1] = 0.5
            action[2] = 0.4
        elif threat > 0.1:
            action[2] = 0.3
        return action


if TORCH_AVAILABLE:
    class RLCTIMTDStrategy(BaselineStrategy):
        def __init__(self, model_path: str, device: str = "cpu"):
            super().__init__("RL-CTI MTD")
            self.device = device
            self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
            if os.path.exists(model_path):
                ckpt = torch.load(model_path, map_location=device, weights_only=False)
                self.policy.load_state_dict(ckpt.get("policy", ckpt))
                self.policy.eval()
                print(f"✅ RL-CTI MTD Policy loaded: {model_path}")
            else:
                print(f"⚠️ Model not found: {model_path}")
        
        def get_action(self, state, step):
            with torch.no_grad():
                t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                a, _, _ = self.policy.act(t, deterministic=True)
            return a.cpu().numpy().squeeze()


# =============================================================================
# Main Manager
# =============================================================================
class RLDeceptionManager:
    def __init__(
        self,
        model_path: Optional[str] = None,
        output_dir: str = "results",
        max_steps: int = 200,
        device: str = "cpu",
        testbed_mode: bool = False,
        dry_run: bool = True,
    ):
        self.model_path = model_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_steps = max_steps
        self.device = device
        self.testbed_mode = testbed_mode
        self.dry_run = dry_run
        
        log_file = str(self.output_dir / "iptables_commands.log") if testbed_mode else None
        self.mtd = MTDController(testbed_mode=testbed_mode, dry_run=dry_run, log_file=log_file)
        self.defense_calc = DefenseProbabilityCalculator()
        self.cti = CTIDetectionModel()
        
        self.strategies = {
            "Baseline": NoMTDStrategy(),
            "Static MTD": StaticMTDStrategy(period=30),
            "Heuristic+CTI": HeuristicCTIStrategy(threshold=0.7),
        }
        
        if TORCH_AVAILABLE and model_path and os.path.exists(model_path):
            self.strategies["RL-CTI MTD"] = RLCTIMTDStrategy(model_path, device)
        
        self.results: Dict[str, Dict[int, List[EpisodeResult]]] = defaultdict(lambda: defaultdict(list))
    
    def _build_state(self, attacker: AttackerAgent, step: int, last_action: np.ndarray) -> np.ndarray:
        n_svc = len(self.mtd.services)
        scaled = scale_action(last_action)
        critical_exposed = any(
            self.mtd.services[s].is_critical for s in attacker.discovered_services if s in self.mtd.services
        )
        phase_map = {
            AttackPhase.INITIAL: 0.0, AttackPhase.RECONNAISSANCE: 0.2,
            AttackPhase.DISCOVERY: 0.4, AttackPhase.EXPLOITATION: 0.6,
            AttackPhase.PERSISTENCE: 0.8, AttackPhase.BREACH: 1.0, AttackPhase.DEFENDED: 0.0,
        }
        return np.array([
            min(1.0, len(attacker.scanned_ips) / 254),
            len(attacker.discovered_services) / n_svc,
            float(critical_exposed),
            len(attacker.exploited_services) / n_svc,
            phase_map.get(attacker.phase, 0.0),
            self.mtd.get_cdi(),
            self.mtd.get_redundancy(),
            min(1.0, attacker.decoy_hits / 10),
            attacker.energy,
            min(1.0, self.mtd.stats['total_swaps'] / 10),
            min(1.0, step / 50),
            attacker.confusion_level,
            min(1.0, len(attacker.scanned_ips) / 50),
            scaled[0], scaled[1], scaled[2],
            scaled[5] if len(scaled) > 5 else 0,
        ], dtype=np.float32)
    
    def _execute_action(self, action: np.ndarray) -> Tuple[Dict[str, float], float]:
        scaled = scale_action(action)
        total_cost = 0.0
        intensities = {}
        
        if scaled[0] > ACTION_THRESHOLDS['shuffle']:
            cost, _ = self.mtd.shuffle(scaled[0])
            total_cost += cost
            intensities['shuffle'] = float(scaled[0])
        
        if scaled[1] > ACTION_THRESHOLDS['port_hop']:
            cost, _ = self.mtd.port_hop(scaled[1])
            total_cost += cost
            intensities['port_hop'] = float(scaled[1])
        
        if scaled[2] > ACTION_THRESHOLDS['decoy']:
            cost, _ = self.mtd.activate_decoys(scaled[2])
            total_cost += cost
            intensities['decoy'] = float(scaled[2])
        
        if scaled[3] > ACTION_THRESHOLDS['blacklist']:
            total_cost += scaled[3] * scaled[4] * ACTION_COSTS['blacklist']
            intensities['blacklist'] = float(scaled[3])
        
        if scaled[5] > ACTION_THRESHOLDS['swap']:
            cost, _ = self.mtd.swap(scaled[5], scaled[6] > 0.5)
            total_cost += cost
            intensities['swap'] = float(scaled[5])
        
        return intensities, total_cost
    
    def run_episode(self, strategy: BaselineStrategy, level: int, ep_id: int, seed: int) -> EpisodeResult:
        np.random.seed(seed)
        self.mtd.reset()
        self.defense_calc.reset()
        strategy.reset()
        
        attacker = AttackerAgent(level=level, seed=seed, targets=self.mtd.get_targets())
        result = EpisodeResult(episode_id=ep_id, strategy_name=strategy.name, attacker_level=level)
        
        last_action = np.zeros(ACTION_DIM)
        cti_detections = 0
        
        for step in range(self.max_steps):
            state = self._build_state(attacker, step, last_action)
            action = strategy.get_action(state, step)
            last_action = action.copy()
            
            intensities, _ = self._execute_action(action)
            cdi = self.mtd.get_cdi()
            
            cti_detected = False
            if len(attacker.scanned_ips) > 10 or len(attacker.exploited_services) > 0:
                detected, conf, _ = self.cti.detect_attack("scan")
                cti_detected = detected
                if detected:
                    cti_detections += 1
            
            defense_prob = self.defense_calc.compute(intensities, cdi, level, step, cti_detected)
            
            attack_result = attacker.step({
                'is_shuffle': 'shuffle' in intensities,
                'shuffle_intensity': intensities.get('shuffle', 0),
                'is_swap': 'swap' in intensities,
                'swap_intensity': intensities.get('swap', 0),
                'defense_probability': defense_prob,
            })
            
            if attack_result['breach']:
                result.breach_occurred = True
                result.mttc = step + 1
                break
            
            if attacker.phase == AttackPhase.DEFENDED:
                break
        
        result.steps = step + 1
        result.total_cost = float(self.mtd.stats['total_cost'])
        result.shuffle_count = int(self.mtd.stats['total_shuffles'])
        result.swap_count = int(self.mtd.stats['total_swaps'])
        result.decoy_hits = int(attacker.decoy_hits)
        result.services_discovered = int(len(attacker.discovered_services))
        result.services_exploited = int(len(attacker.exploited_services))
        result.final_phase = str(attacker.phase)
        result.cti_detections = cti_detections
        
        if self.testbed_mode and self.mtd.executor:
            result.iptables_commands = len(self.mtd.executor.command_history)
        
        n_svc = len(self.mtd.services)
        mttc = result.mttc if result.breach_occurred else self.max_steps
        result.mttc = int(mttc)
        result.cdi = float(cdi)
        result.redundancy = float(self.mtd.get_redundancy())
        
        discovered = result.services_discovered
        exploited = result.services_exploited
        exposed = discovered + exploited * 2
        max_exposure = n_svc * 3
        result.asr = float(1.0 - min(1.0, exposed / max_exposure))
        
        mttc_norm = mttc / self.max_steps
        asp = exploited / max(1, discovered) if discovered > 0 else 0
        ned = np.random.uniform(0.3, 0.7)
        result.des = float(
            0.25 * mttc_norm + 0.20 * result.asr + 0.20 * result.cdi + 
            0.15 * ned + 0.10 * (1.0 - asp) + 0.10 * result.redundancy
        )
        result.cer = float(result.des / (result.total_cost + 0.1))
        
        return result
    
    def run_experiment(self, episodes: int = 50, levels: List[int] = None, strategies: List[str] = None):
        levels = levels or [0, 1, 2, 3, 4]
        strategies = strategies or list(self.strategies.keys())
        
        mode_str = "TESTBED" if self.testbed_mode else "SIMULATION"
        dry_str = " (DRY-RUN)" if self.testbed_mode and self.dry_run else ""
        
        print(f"\n{'='*70}")
        print(f"MTD-RL Experiment v09.8 - {mode_str}{dry_str}")
        print(f"{'='*70}")
        print(f"Strategies: {strategies}")
        print(f"Levels: {levels}")
        print(f"Episodes/level: {episodes}")
        print(f"{'='*70}\n")
        
        if self.testbed_mode:
            self.mtd.init_iptables_chains()
        
        start_time = time.time()
        
        for strat_name in strategies:
            if strat_name not in self.strategies:
                print(f"⚠️ Strategy not found: {strat_name}")
                continue
            
            strat = self.strategies[strat_name]
            print(f"\n📊 Strategy: {strat_name}")
            
            for level in levels:
                print(f"  Level {level} ({ATTACKER_PROFILES[level]['name']}): ", end="", flush=True)
                
                for ep in range(episodes):
                    r = self.run_episode(strat, level, ep, 42 + level * 1000 + ep)
                    self.results[strat_name][level].append(r)
                    if (ep + 1) % 10 == 0:
                        print(".", end="", flush=True)
                
                eps = self.results[strat_name][level]
                br = sum(1 for e in eps if e.breach_occurred) / len(eps) * 100
                des = np.mean([e.des for e in eps])
                cdi = np.mean([e.cdi for e in eps])
                print(f" BR={br:.1f}%, DES={des:.3f}, CDI={cdi:.2f}")
        
        elapsed = (time.time() - start_time) / 60
        print(f"\n✅ Completed in {elapsed:.1f} minutes")
        
        if self.testbed_mode:
            summary = self.mtd.get_iptables_summary()
            print(f"\n📋 iptables Summary:")
            print(f"   Total commands: {summary.get('total_commands', 0)}")
            print(f"   Successful: {summary.get('successful', 0)}")
            print(f"   Failed: {summary.get('failed', 0)}")
        
        self._save_results()
        self._print_summary()
    
    def _save_results(self):
        output = {}
        for strat, level_results in self.results.items():
            output[strat] = {}
            for level, eps in level_results.items():
                output[strat][str(level)] = [
                    to_python({
                        "episode_id": r.episode_id, "steps": r.steps, "breach": r.breach_occurred,
                        "cost": r.total_cost, "mttc": r.mttc, "asr": r.asr, "cdi": r.cdi,
                        "redundancy": r.redundancy, "des": r.des, "cer": r.cer,
                        "shuffle_count": r.shuffle_count, "swap_count": r.swap_count,
                        "decoy_hits": r.decoy_hits, "services_discovered": r.services_discovered,
                        "services_exploited": r.services_exploited, "final_phase": r.final_phase,
                        "cti_detections": r.cti_detections, "iptables_commands": r.iptables_commands,
                    }) for r in eps
                ]
        
        path = self.output_dir / "experiment_results.json"
        with open(path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n✅ Results saved: {path}")
    
    def _print_summary(self):
        print(f"\n{'='*110}")
        print("EXPERIMENT SUMMARY")
        print(f"{'='*110}")
        
        levels = sorted(self.results[list(self.results.keys())[0]].keys())
        header = f"{'Strategy':<20}"
        for l in levels:
            header += f" | L{l} BR%"
        header += " | Avg DES | Avg CDI | Avg CER"
        print(header)
        print("-" * 110)
        
        for strat in self.results:
            row = f"{strat:<20}"
            all_des, all_cdi, all_cer = [], [], []
            for level in levels:
                eps = self.results[strat][level]
                br = sum(1 for e in eps if e.breach_occurred) / len(eps) * 100
                row += f" | {br:6.1f}"
                all_des.extend([e.des for e in eps])
                all_cdi.extend([e.cdi for e in eps])
                all_cer.extend([e.cer for e in eps])
            row += f" | {np.mean(all_des):7.3f} | {np.mean(all_cdi):7.2f} | {np.mean(all_cer):7.2f}"
            print(row)
        print(f"{'='*110}")
    
    def cleanup(self):
        """정리"""
        if self.testbed_mode:
            self.mtd.cleanup_iptables()


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="MTD-RL Deception Manager v09.8",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simulation experiment
  python %(prog)s --experiment --episodes 50

  # Testbed with dry-run (print commands only)
  python %(prog)s --model best.pt --testbed --dry-run

  # Testbed with real iptables execution (requires root)
  sudo python %(prog)s --model best.pt --testbed

  # Single level test
  python %(prog)s --testbed --dry-run --level 4 --episodes 10
        """
    )
    parser.add_argument("--model", type=str, default=None, help="RL model path")
    parser.add_argument("--output-dir", type=str, default="results", help="Output directory")
    parser.add_argument("--max-steps", type=int, default=200, help="Max steps per episode")
    parser.add_argument("--device", type=str, default="cpu", help="PyTorch device")
    parser.add_argument("--level", type=int, default=None, help="Single attacker level")
    parser.add_argument("--episodes", type=int, default=50, help="Episodes per level")
    parser.add_argument("--experiment", action="store_true", help="Run full experiment (all levels)")
    parser.add_argument("--strategies", nargs="+", default=None, help="Strategies to test")
    parser.add_argument("--testbed", action="store_true", help="Enable testbed mode (iptables)")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (print commands only)")
    args = parser.parse_args()
    
    manager = RLDeceptionManager(
        model_path=args.model,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        device=args.device,
        testbed_mode=args.testbed,
        dry_run=args.dry_run,
    )
    
    if args.experiment:
        levels = [0, 1, 2, 3, 4]
    else:
        levels = [args.level] if args.level is not None else [2]
    
    try:
        manager.run_experiment(
            episodes=args.episodes,
            levels=levels,
            strategies=args.strategies,
        )
    finally:
        if args.testbed and not args.dry_run:
            manager.cleanup()


if __name__ == "__main__":
    main()