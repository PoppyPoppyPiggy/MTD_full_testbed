#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import random
import signal
import yaml
import docker
import threading
import datetime
from collections import deque
from typing import Dict, Optional, Any

# --- 경로 설정 및 로거 import ---
MTD_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_ROOT = os.path.abspath(os.path.join(MTD_DIR, '..'))
if LPC_ROOT not in sys.path:
    sys.path.insert(0, LPC_ROOT)
from bus.logger import log_bus_event

# --- 상수 및 경로 탐색 로직 ---
def get_shared_path(filename: str) -> str:
    container_path = os.path.join("/shared", filename)
    if os.path.exists(container_path): 
        return container_path
    return os.path.join(MTD_DIR, "shared_state", filename)

STATE_FILE_PATH = get_shared_path("mtd_state.json")
POLICY_FILE_PATH = get_shared_path("mtd_policy.yaml")
BUS_LOG_PATH = os.path.join(LPC_ROOT, "bus", "bus.log")
DOCKER_NETWORK = "simulator"

class AdaptiveMtdEngine:
    """CTI 및 LPC 기반 지능형 적응 MTD 엔진 (v12.1, 안정성 보강)"""
    def __init__(self, client: docker.DockerClient):
        self.client = client
        self.run_flag = True
        self.lock = threading.Lock()
        
        self.policy: Dict[str, Any] = {}
        self.state: Dict[str, Any] = {}
        self.network: Optional[docker.models.networks.Network] = None
        
        self.current_strategy = 'adaptive_defense'
        self.ip_blacklist: Dict[str, float] = {}
        self.port_blacklist: Dict[int, float] = {}
        self.attacker_ip_blacklist: Dict[str, float] = {}
        self.prober_hits: Dict[str, int] = {}

        self.attack_timestamps = deque()
        self.last_shuffle_ts = 0
        self.current_shuffle_interval = 30

    def _signal_handler(self, *_):
        self.run_flag = False
        print("\n[알림] 종료 신호 수신. MTD 엔진을 안전하게 종료합니다.")
        log_bus_event("mtd_engine_stop", {"reason": "signal_received"})
        self._write_state()

    def load_policy_and_state(self):
        print(f"[정보] 정책 파일 로드 시도: {POLICY_FILE_PATH}")
        try:
            with open(POLICY_FILE_PATH, 'r') as f:
                self.policy = yaml.safe_load(f) or {}
            self.current_strategy = self.policy.get('default_strategy', 'adaptive_defense')
        except Exception as e:
            print(f"[오류] 정책 파일 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)
            
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                self.state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("[정보] 기존 상태 파일 없음. 정책에 따라 초기 상태를 생성합니다.")
            initial_ip = self.policy.get('real_target_ip', "10.13.0.3")
            initial_port = random.choice(self.policy.get('port_pool', [14550]))
            self.state = {"current_target": f"{initial_ip}:{initial_port}"}
        
        try:
            self.network = self.client.networks.get(DOCKER_NETWORK)
        except docker.errors.NotFound:
            print(f"[오류] Docker 네트워크 '{DOCKER_NETWORK}'를 찾을 수 없습니다.", file=sys.stderr)
            sys.exit(1)
        
        self.apply_mtd_swap(is_initial=True)

    def _write_state(self):
        with self.lock:
            self.state['strategy'] = self.current_strategy
            self.state['last_updated'] = time.time()
            self.state['heartbeat'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
                with open(STATE_FILE_PATH, 'w') as f:
                    json.dump(self.state, f, indent=2)
            except IOError as e:
                print(f"\n[경고] mtd_state.json 파일 쓰기 실패: {e}", file=sys.stderr)

    def watch_bus_log(self):
        print("[감시] bus.log 감시 스레드 시작...")
        while not os.path.exists(BUS_LOG_PATH) and self.run_flag:
            time.sleep(1)

        with open(BUS_LOG_PATH, 'r', errors='ignore') as f:
            f.seek(0, os.SEEK_END)
            while self.run_flag:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                try:
                    event = json.loads(line)
                    self._handle_bus_event(event)
                except json.JSONDecodeError:
                    pass

    def _handle_bus_event(self, event: Dict[str, Any]):
        event_type = event.get("type")
        data = event.get("data", {})
        
        with self.lock:
            if event_type == "attack_started":
                if self.current_strategy != 'attack_adaptive':
                    self.current_strategy = 'attack_adaptive'
                    log_bus_event("mtd_strategy_change", {"to": "attack_adaptive", "reason": "attack_started"})
                self.attack_timestamps.append(time.time())
                attacker_ip = data.get("source_ip")
                if attacker_ip and self.policy.get('enable_attacker_blacklist', False):
                    duration = self.policy.get('strategies', {}).get('adaptive_defense', {}).get('blacklist_duration_s', 300)
                    self.attacker_ip_blacklist[attacker_ip] = time.time() + duration
                    log_bus_event("mtd_blacklist_add", {"type": "attacker_ip", "value": attacker_ip, "duration_s": duration})
                self.apply_mtd_swap(reason="attack_reaction")

            elif event_type == "threat_detected":
                reason = data.get('reason', 'unknown')
                print(f"\n[위협 감지!] 사유: {reason}")
                duration = self.policy.get('strategies', {}).get('adaptive_defense', {}).get('blacklist_duration_s', 300)
                if 'target_ip' in data:
                    self.ip_blacklist[data['target_ip']] = time.time() + duration
                if 'target_port' in data:
                    self.port_blacklist[data['target_port']] = time.time() + duration
                self.apply_mtd_swap(reason="threat_evasion")

            elif event_type == "prober_activity":
                prober_ip = data.get("source_ip")
                if not prober_ip:
                    return
                self.prober_hits[prober_ip] = self.prober_hits.get(prober_ip, 0) + 1
                prober_policy = self.policy.get('strategies', {}).get('prober_response', {})
                threshold = prober_policy.get('blacklist_threshold', 5)
                if self.prober_hits[prober_ip] >= threshold:
                    duration = prober_policy.get('blacklist_duration_s', 600)
                    self.attacker_ip_blacklist[prober_ip] = time.time() + duration
                    log_bus_event("mtd_blacklist_add", {"type": "prober_ip", "value": prober_ip, "reason": "threshold_exceeded"})
                    self.prober_hits[prober_ip] = 0
            
            elif event_type == "lpc_recon_success":
                prober_ip = data.get("prober_ip", "unknown")
                print(f"\n[심각] Prober({prober_ip})가 MTD를 우회하고 타겟을 확정했습니다! 즉시 최대 대응합니다.")
                log_bus_event("mtd_emergency_response", {"reason": "lpc_recon_success", "prober_ip": prober_ip})
                self.attacker_ip_blacklist[prober_ip] = time.time() + 3600  # 1시간 차단
                self.apply_mtd_swap(reason="emergency_evasion")

    def _cleanup_blacklists(self):
        now = time.time()
        self.ip_blacklist = {ip: exp for ip, exp in self.ip_blacklist.items() if exp > now}
        self.port_blacklist = {port: exp for port, exp in self.port_blacklist.items() if exp > now}
        self.attacker_ip_blacklist = {ip: exp for ip, exp in self.attacker_ip_blacklist.items() if exp > now}

    def _update_attack_adaptive_interval(self):
        if self.current_strategy != 'attack_adaptive':
            return
        conf = self.policy.get('strategies', {}).get('attack_adaptive', {})
        window = conf.get('attack_window_s', 60)
        now = time.time()
        while self.attack_timestamps and self.attack_timestamps[0] < now - window:
            self.attack_timestamps.popleft()
        
        apm = len(self.attack_timestamps) * (60 / window) if window > 0 else 0
        new_interval = conf.get('base_interval_s', 30)
        for rule in sorted(conf.get('cycle_map', []), key=lambda x: x['frequency_apm'], reverse=True):
            if apm >= rule.get('frequency_apm', 0):
                new_interval = rule.get('shuffle_interval_s', new_interval)
                break
        self.current_shuffle_interval = new_interval

    def apply_mtd_swap(self, is_initial=False, reason="periodic_shuffle"):
        with self.lock:
            old_full = self.state.get("current_target", "N/A")
            self._cleanup_blacklists()
            decoy_pool = self.policy.get('decoy_pool', [])
            port_pool = self.policy.get('port_pool', [])
            if not decoy_pool or not port_pool:
                print("[경고] decoy_pool/port_pool이 비어 셔플 불가. 정책 확인 필요.", file=sys.stderr)
                return

            valid_ips = [ip for ip in decoy_pool if ip not in self.ip_blacklist] or decoy_pool
            valid_ports = [p for p in port_pool if p not in self.port_blacklist] or port_pool

            new_ip = random.choice(valid_ips)
            new_port = random.choice(valid_ports)
            new_full = f"{new_ip}:{new_port}"
            
            if old_full == new_full and not is_initial:
                return

            print(f"\n[MTD] 셔플링 수행 ({reason}): {old_full} -> {new_full}")

            real_target_ip = self.policy.get('real_target_ip')
            if real_target_ip:
                old_ip = old_full.split(':')[0] if ':' in old_full else old_full
                container_name = self.policy.get('ip_to_container_map', {}).get(real_target_ip)
                if container_name:
                    if not is_initial and old_ip == real_target_ip and new_ip != real_target_ip:
                        self._remap_container_ip(container_name, False)
                    if new_ip == real_target_ip and old_ip != real_target_ip:
                        self._remap_container_ip(container_name, True, new_ip)

            self.state["current_target"] = new_full
            self.state["decoy_target"] = old_full
            self._write_state()
            self.last_shuffle_ts = time.time()
            log_bus_event("mtd_target_swap", {"from": old_full, "to": new_full, "reason": reason})

    def _remap_container_ip(self, container_name: str, connect: bool, ip_addr: str = ""):
        try:
            container = self.client.containers.get(container_name)
            if connect:
                try:
                    self.network.disconnect(container)
                except docker.errors.APIError:
                    pass
                self.network.connect(container, ipv4_address=ip_addr)
                print(f"[Docker] {container_name} connected with IP {ip_addr}")
            else:
                self.network.disconnect(container)
                print(f"[Docker] {container_name} disconnected")
        except docker.errors.APIError as e:
            if 'is already connected' not in str(e) and 'is not connected' not in str(e):
                 print(f"[경고] Docker IP 변경 실패 ({container_name}): {e}", file=sys.stderr)
        except Exception as e:
            print(f"[경고] Docker 예외 ({container_name}): {e}", file=sys.stderr)

    def run(self):
        self.load_policy_and_state()
        log_bus_event("mtd_engine_start", {"version": "v12.1-lpc-aware", "policy": self.policy})
        threading.Thread(target=self.watch_bus_log, daemon=True).start()

        while self.run_flag:
            with self.lock:
                now = time.time()
                self._update_attack_adaptive_interval()

                if self.current_strategy == 'attack_adaptive' and (now - self.last_shuffle_ts) > self.current_shuffle_interval:
                    self.apply_mtd_swap()
                
                conf = self.policy.get('strategies', {}).get('attack_adaptive', {})
                win = conf.get('attack_window_s', 60)
                apm = len(self.attack_timestamps) * (60 / win) if win > 0 else 0.0
                status = (f"\r[MTD Engine] Strategy: {self.current_strategy.upper():<18} | "
                          f"Target: {self.state.get('current_target'):<18} | "
                          f"Blacklist (Tgt/Atk): {len(self.ip_blacklist)}/{len(self.attacker_ip_blacklist)} | "
                          f"APM: {apm:<4.1f} | "
                          f"Interval: {self.current_shuffle_interval:<4.1f}s")
                sys.stdout.write(status + ' ' * 5)
                sys.stdout.flush()
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        import docker, yaml
    except ImportError:
        print("[오류] 필수 패키지가 없습니다. 'pip install docker pyyaml'을 실행해주세요.", file=sys.stderr)
        sys.exit(1)
    
    client = docker.from_env()
    engine = AdaptiveMtdEngine(client)
    signal.signal(signal.SIGINT, engine._signal_handler)
    signal.signal(signal.SIGTERM, engine._signal_handler)
    engine.run()
