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
    """CTI, RL, LPC 기반 지능형 적응 MTD 엔진"""
    def __init__(self, client: docker.DockerClient):
        self.client = client
        self.run_flag = True
        self.lock = threading.Lock()

        self.policy: Dict[str, Any] = {}
        self.state: Dict[str, Any] = {}
        self.network: Optional[docker.models.networks.Network] = None

        self.current_strategy = 'adaptive_defense'
        self.current_posture = 'LOW_PROFILE'
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
            self.current_shuffle_interval = self.policy.get('strategies', {}).get('attack_adaptive', {}).get('base_interval_s', 30)
        except Exception as e:
            print(f"[오류] 정책 파일 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            with open(STATE_FILE_PATH, 'r') as f:
                self.state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("[정보] 기존 상태 파일 없음. 정책에 따라 초기 상태를 생성합니다.")
            initial_ip = self.policy.get('real_target_ip', "10.13.0.3")
            initial_port = random.choice(self.policy.get('port_pool', ))
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
            self.state['posture'] = self.current_posture
            self.state['shuffle_interval_s'] = self.current_shuffle_interval
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
        if not os.path.exists(BUS_LOG_PATH):
            open(BUS_LOG_PATH, 'a').close() # 파일 생성

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
            if event_type == "attack_detected":
                self.attack_timestamps.append(time.time())
                attacker_ip = data.get("source_ip")
                if attacker_ip and self.policy.get('enable_attacker_blacklist', False):
                    duration = self.policy.get('prober_response', {}).get('blacklist_duration_s', 600)
                    self.attacker_ip_blacklist[attacker_ip] = time.time() + duration
                    log_bus_event("mtd_blacklist_add", {"type": "attacker_ip", "value": attacker_ip, "duration_s": duration})
                # 공격 감지 시 즉각적인 셔플링 트리거
                self.apply_mtd_swap(reason="attack_reaction")

            elif event_type == "rl_agent_decision":
                new_posture = data.get("posture")
                if new_posture and new_posture in self.policy.get('defense_postures', {}):
                    if self.current_posture!= new_posture:
                        print(f"\n 방어 태세 변경: {self.current_posture} -> {new_posture}")
                        self.current_posture = new_posture
                        posture_config = self.policy['defense_postures'][new_posture]
                        self.current_shuffle_interval = posture_config.get('shuffle_interval_s', 30)
                        log_bus_event("mtd_posture_change", {"to": new_posture, "shuffle_interval_s": self.current_shuffle_interval})
                        # 태세 변경 시 즉시 셔플링 적용
                        self.apply_mtd_swap(reason=f"posture_change_to_{new_posture}")

    def _cleanup_blacklists(self):
        now = time.time()
        self.attacker_ip_blacklist = {ip: exp for ip, exp in self.attacker_ip_blacklist.items() if exp > now}

    def _update_adaptive_interval(self):
        # RL 에이전트가 활성화되면 이 로직은 RL의 결정에 의해 오버라이드됨
        if self.current_strategy == 'attack_adaptive' and self.current_posture == 'LOW_PROFILE': # RL이 없을 때의 Fallback
            conf = self.policy.get('strategies', {}).get('attack_adaptive', {})
            window = conf.get('attack_window_s', 60)
            now = time.time()
            while self.attack_timestamps and self.attack_timestamps < now - window:
                self.attack_timestamps.popleft()

            apm = len(self.attack_timestamps)
            new_interval = conf.get('base_interval_s', 30)
            for rule in sorted(conf.get('cycle_map',), key=lambda x: x['frequency_apm'], reverse=True):
                if apm >= rule.get('frequency_apm', 0):
                    new_interval = rule.get('shuffle_interval_s', new_interval)
                    break
            self.current_shuffle_interval = new_interval

    def apply_mtd_swap(self, is_initial=False, reason="periodic_shuffle"):
        with self.lock:
            old_full = self.state.get("current_target", "N/A")
            self._cleanup_blacklists()

            decoy_pool = self.policy.get('decoy_pool',)
            port_pool = self.policy.get('port_pool',)
            if not decoy_pool or not port_pool:
                print("[경고] decoy_pool/port_pool이 비어 셔플 불가.", file=sys.stderr)
                return

            # 현재 타겟과 블랙리스트를 제외하고 새로운 IP/Port 선택
            old_ip, old_port_str = old_full.split(':') if ':' in old_full else (None, None)
            old_port = int(old_port_str) if old_port_str else None

            valid_ips = [ip for ip in decoy_pool if ip!= old_ip] or decoy_pool
            valid_ports = [p for p in port_pool if p!= old_port] or port_pool

            new_ip = random.choice(valid_ips)
            new_port = random.choice(valid_ports)
            new_full = f"{new_ip}:{new_port}"

            if old_full == new_full and not is_initial:
                return # 변경점이 없으면 스킵

            print(f"\n 셔플링 수행 ({reason}): {old_full} -> {new_full}")

            self.state["current_target"] = new_full
            self.state["decoy_target"] = old_full # 이전 타겟은 이제 디코이 역할을 함
            self._write_state()
            self.last_shuffle_ts = time.time()
            log_bus_event("mtd_target_swap", {"from": old_full, "to": new_full, "reason": reason, "is_real_asset": new_ip == self.policy.get('real_target_ip')})

    def run(self):
        self.load_policy_and_state()
        log_bus_event("mtd_engine_start", {"version": "v17.0-rl-aware", "policy_name": POLICY_FILE_PATH})
        threading.Thread(target=self.watch_bus_log, daemon=True).start()

        while self.run_flag:
            now = time.time()
            if (now - self.last_shuffle_ts) > self.current_shuffle_interval:
                self.apply_mtd_swap()

            with self.lock:
                self._update_adaptive_interval()
                apm = len([ts for ts in self.attack_timestamps if ts > time.time() - 60])
                status = (f"\r Posture: {self.current_posture:<18} | "
                          f"Target: {self.state.get('current_target'):<18} | "
                          f"Blacklisted: {len(self.attacker_ip_blacklist)} | "
                          f"APM: {apm:<3} | "
                          f"Interval: {self.current_shuffle_interval:<4.1f}s")
                sys.stdout.write(status + ' ' * 5)
                sys.stdout.flush()

            time.sleep(1)

if __name__ == "__main__":
    try:
        client = docker.from_env()
    except ImportError:
        print("[오류] 필수 패키지가 없습니다. 'pip install docker pyyaml'을 실행해주세요.", file=sys.stderr)
        sys.exit(1)

    engine = AdaptiveMtdEngine(client)
    signal.signal(signal.SIGINT, engine._signal_handler)
    signal.signal(signal.SIGTERM, engine._signal_handler)
    engine.run()