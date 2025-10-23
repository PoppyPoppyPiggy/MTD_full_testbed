#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import subprocess
import time
import json
import signal
import threading
from typing import List, Dict, Any, Optional, Tuple
import sys
import socket
import re
import random # RL 모드에서 확률적 실행 위해 추가
import numpy as np # RL 상태 벡터 위해 추가

# --- RL 관련 임포트 (Seeker 모드용) ---
try:
    import torch
    import torch.nn as nn
    from torch.distributions import Categorical
    # train.py 또는 rl_driven_deception_manager.py 와 동일한 ActorCritic 클래스 정의
    class ActorCritic(nn.Module):
        def __init__(self, state_dim: int, action_dim: int):
            super(ActorCritic, self).__init__()
            self.shared = nn.Sequential(nn.Linear(state_dim, 128), nn.Tanh(), nn.Linear(128, 128), nn.Tanh())
            self.actor = nn.Linear(128, action_dim)
            self.critic = nn.Linear(128, 1) # Critic은 여기서 사용 안 함

        def forward(self, state):
            x = self.shared(state)
            # Critic은 필요 없으므로 액터 로짓만 반환하도록 수정 가능하나, 호환성 위해 유지
            return Categorical(logits=self.actor(x)), self.critic(x).squeeze(-1)

        def act(self, state):
            dist, value = self.forward(state)
            action = dist.sample() # 확률적으로 행동 선택
            # 평가 시에는 dist.probs.argmax() 사용 가능
            return action, dist.log_prob(action), value # log_prob, value는 Seeker 모드에서 직접 사용 안 함
    RL_AVAILABLE = True
except ImportError:
    print("WARNING: PyTorch가 설치되지 않았습니다. --seeker 모드를 사용할 수 없습니다.", file=sys.stderr)
    ActorCritic = None # 클래스 정의 없애기
    RL_AVAILABLE = False


# --- 경로 설정 ---
LPC_DIR = os.path.dirname(os.path.realpath(__file__))
ATTACKS_DIR = os.path.join(LPC_DIR, 'modules', 'attacks_wiki')
ATTACK_META_DIR = os.path.join(ATTACKS_DIR, 'json')
SHARED_STATE_CONTAINER_PATH = "/shared/mtd_state.json"
SHARED_STATE_HOST_FALLBACK = os.path.join(LPC_DIR, 'mtd', 'shared_state', 'mtd_state.json')
# ⭐️ Seeker 모델 경로 추가
SEEKER_MODEL_PATH = os.path.join(LPC_DIR, 'rl', 'models', 'seeker_policy.pth')

# --- PYTHONPATH 자동 설정 ---
if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

# --- 로거 설정 ---
try:
    from bus.logger import log_bus_event
    print("[Attack Orchestrator] bus.logger 로드 성공. 이벤트는 bus.log에 기록됩니다.")
except ImportError:
    print("WARNING: bus.logger를 임포트할 수 없습니다. 이벤트는 stdout으로 출력됩니다.", file=sys.stderr)
    def log_bus_event(type: str, data: Dict[str, Any], source_override: str = "orchestrator"):
        record = {"ts": time.time(), "source": source_override, "type": type, "data": data}
        print(json.dumps(record))

# --- 전역 변수 ---
attack_process: Optional[subprocess.Popen] = None
attack_lock = threading.RLock()
stop_event = threading.Event()
try:
    MY_IP_ADDRESS = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip().split()[0]
except Exception:
    MY_IP_ADDRESS = '10.13.0.200'

# --- Seeker RL 모드용 전역 변수 ---
seeker_policy: Optional[ActorCritic] = None
seeker_state_dim = 5 # train.py _obs_seek() 차원
seeker_action_dim = 5 # train.py SEEKER_META_ACTIONS 개수
# Seeker 동적 파라미터 (train.py Config 와 유사)
seeker_dyn_params = {
    "attack_bias": {"val": 1.0, "min": 0.5, "max": 2.0},
    "scan_effort": {"val": 1.0, "min": 0.5, "max": 2.0}
}
seeker_meta_actions = { # train.py SEEKER_META_ACTIONS
    0: ("attack_bias", 1.2), 1: ("attack_bias", 0.8),
    2: ("scan_effort", 1.2), 3: ("scan_effort", 0.8),
    4: ("none", 1.0)
}
# Seeker 환경 관찰 변수
seeker_known_target = False # 현재 타겟 IP/Port를 아는가?
seeker_last_target_ip: Optional[str] = None
seeker_last_mtd_state_mtime: float = 0.0 # 상태 파일 최종 수정 시간
seeker_observed_shuffle_ema = 0.0 # MTD 셔플 관찰 빈도 (EMA)

# ==============================================================================
# 유틸리티 함수 (기존과 동일)
# ==============================================================================
def get_mtd_state_file_path() -> str:
    """MTD 상태 파일의 실제 경로를 결정합니다."""
    if os.path.exists(SHARED_STATE_CONTAINER_PATH):
        return SHARED_STATE_CONTAINER_PATH
    elif os.path.exists(SHARED_STATE_HOST_FALLBACK):
        # print(f"[정보] 컨테이너 경로({SHARED_STATE_CONTAINER_PATH}) 없음. 호스트 경로({SHARED_STATE_HOST_FALLBACK}) 사용.")
        return SHARED_STATE_HOST_FALLBACK
    else:
        print(f"[경고] MTD 상태 파일을 찾을 수 없음: {SHARED_STATE_CONTAINER_PATH} 또는 {SHARED_STATE_HOST_FALLBACK}", file=sys.stderr)
        return SHARED_STATE_HOST_FALLBACK

def read_mtd_target(state_file: str) -> Tuple[Optional[str], Optional[int]]:
    """MTD 상태 파일에서 현재 타겟 IP와 Port를 읽습니다."""
    try:
        current_mtime = os.path.getmtime(state_file) # 파일 수정 시간 확인
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        target_str = state.get("current_target")
        if not target_str or ":" not in target_str:
            return None, None, current_mtime # 수정 시간 반환 추가
        ip, port_str = target_str.split(":", 1)
        return ip, int(port_str), current_mtime # 수정 시간 반환 추가
    except FileNotFoundError:
        return None, None, 0.0 # 수정 시간 0 반환
    except (json.JSONDecodeError, ValueError, Exception) as e:
        print(f"[경고] MTD 상태 파일({state_file}) 읽기/파싱 오류: {e}", file=sys.stderr)
        return None, None, seeker_last_mtd_state_mtime # 이전 수정 시간 반환

def get_available_attacks() -> List[str]:
    """사용 가능한 공격 스크립트(.sh) 목록을 가져옵니다."""
    if not os.path.isdir(ATTACKS_DIR):
        print(f"⛔ 오류: 공격 스크립트 디렉토리 '{ATTACKS_DIR}'를 찾을 수 없습니다.", file=sys.stderr)
        return []
    try:
        attacks = sorted([f for f in os.listdir(ATTACKS_DIR) if f.endswith('.sh') and os.path.isfile(os.path.join(ATTACKS_DIR, f))])
        if not attacks:
             print(f"⛔ 오류: '{ATTACKS_DIR}' 디렉토리에 실행 가능한 .sh 공격 스크립트가 없습니다.", file=sys.stderr)
        return attacks
    except OSError as e:
        print(f"⛔ 오류: 공격 스크립트 디렉토리 '{ATTACKS_DIR}' 접근 중 오류 발생: {e}", file=sys.stderr)
        return []

def get_attack_metadata(attack_name: str) -> Dict[str, Any]:
    """공격 스크립트 이름에서 메타데이터(카테고리=스크립트명, MITRE)를 추론합니다."""
    base_name = attack_name.replace('.sh', '')
    meta = {"mitre_tactics": [], "attack_category": base_name}
    json_path = os.path.join(ATTACK_META_DIR, f"{base_name}_attack_tree.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f: attack_tree = json.load(f)
            tactics = re.findall(r'TA\d{4}', json.dumps(attack_tree))
            meta['mitre_tactics'] = sorted(list(set(tactics)))
        except Exception: pass
    return meta

# ==============================================================================
# 공격 프로세스 관리 (기존과 동일)
# ==============================================================================
def _kill_process_group(proc: subprocess.Popen):
    if proc and proc.poll() is None:
        pgid = 0
        try:
            pgid = os.getpgid(proc.pid)
            # print(f"[프로세스 관리] SIGTERM 전송 (PGID:{pgid}, PID:{proc.pid})...")
            os.killpg(pgid, signal.SIGTERM)
            proc.wait(timeout=3)
            # print(f"[프로세스 관리] 정상 종료됨 (PGID:{pgid}, RC: {proc.returncode}).")
        except ProcessLookupError: pass # 이미 종료됨
        except subprocess.TimeoutExpired:
            print(f"[프로세스 관리] SIGTERM 타임아웃. SIGKILL 전송 (PGID:{pgid})...")
            try:
                os.killpg(pgid, signal.SIGKILL)
                proc.wait(timeout=1)
            except Exception: pass # 최후의 수단
        except Exception: pass

def cleanup_attack_process(reason: str):
    global attack_process
    with attack_lock:
        proc_to_clean = attack_process
        if proc_to_clean:
            attack_process = None
            print(f"[정리] 공격 프로세스 정리 (사유: {reason}, PID: {proc_to_clean.pid})")
            log_bus_event("attack_cleanup", {"reason": reason, "pid": proc_to_clean.pid}, source_override="attack_orchestrator")
            _kill_process_group(proc_to_clean)

def terminate_orchestrator(reason: str):
    print(f"\n[종료] 오케스트레이터 종료 시작 (사유: {reason})")
    if not stop_event.is_set():
        stop_event.set()
        cleanup_attack_process(f"orchestrator_shutdown_{reason}")
        print("[종료] 오케스트레이터 종료 완료.")

def stream_reader(pipe, stream_name: str, attack_name: str):
    if not pipe: return
    try:
        for line in iter(pipe.readline, ''):
            if stop_event.is_set(): break
            line_stripped = line.strip()
            if line_stripped:
                 log_bus_event(f"attack_{stream_name}", {"attack": attack_name, "output": line_stripped}, source_override="attack_script")
    except ValueError: pass
    except Exception: pass
    finally:
        if pipe:
            try: pipe.close()
            except Exception: pass

# ==============================================================================
# Seeker RL 모드 함수
# ==============================================================================
def load_seeker_policy(path: str) -> Optional[ActorCritic]:
    """Seeker RL 정책 모델을 로드합니다."""
    if not RL_AVAILABLE: return None
    if not os.path.exists(path):
        print(f"❌ RL Seeker 정책 모델을 찾을 수 없습니다: {path}", file=sys.stderr)
        print("   먼저 train.py를 실행하여 모델을 학습시키고, 올바른 경로에 배치해야 합니다.")
        return None

    print(f"🤖 RL Seeker 정책 모델 로드 중: {path}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy = ActorCritic(seeker_state_dim, seeker_action_dim).to(device)
    try:
        policy.load_state_dict(torch.load(path, map_location=device))
        policy.eval()
        print("✅ RL Seeker 정책 모델 로드 완료.")
        return policy
    except Exception as e:
        print(f"❌ RL Seeker 정책 모델 로드 실패: {e}", file=sys.stderr)
        return None

def observe_environment_seeker(state_file: str) -> Tuple[torch.Tensor, bool]:
    """Seeker 관점에서 환경을 관찰하고 상태 벡터를 생성합니다."""
    global seeker_known_target, seeker_last_target_ip, seeker_last_mtd_state_mtime, seeker_observed_shuffle_ema

    # MTD 상태 파일 읽기
    current_target_ip, _, current_mtime = read_mtd_target(state_file)
    observed_move = False # 이번 관찰에서 MTD 이동이 감지되었는가?

    if current_mtime > seeker_last_mtd_state_mtime: # 상태 파일 변경 감지
        if seeker_last_mtd_state_mtime != 0.0: # 첫 실행이 아니면
            print(f"[Seeker 관찰] MTD 상태 변경 감지됨 (이전: {seeker_last_target_ip}, 현재: {current_target_ip})")
            observed_move = True
            seeker_known_target = False # MTD 발생 시 일단 모른다고 가정
            # EMA 업데이트 (셔플 빈도 추정)
            seeker_observed_shuffle_ema = 0.8 * seeker_observed_shuffle_ema + 0.2 * 1.0 # 셔플 감지
        seeker_last_target_ip = current_target_ip
        seeker_last_mtd_state_mtime = current_mtime
    else:
        # EMA 업데이트 (셔플 없음)
        seeker_observed_shuffle_ema = 0.8 * seeker_observed_shuffle_ema + 0.2 * 0.0

    # TODO: 실제 스캔 결과 등을 통해 known_target 업데이트 로직 추가 필요
    # 예시: 최근 N초 내 스캔 성공 로그가 있으면 known_target = True
    # 현재는 MTD 발생 시 False, 그 외에는 True 유지 (단순화)
    if not observed_move and current_target_ip is not None:
        # 간단히, MTD가 없었고 타겟 IP가 있으면 안다고 가정
        # (실제로는 스캔 성공 여부 확인 필요)
        seeker_known_target = True


    # 상태 벡터 구성 (train.py _obs_seek() 와 동일)
    norm_atk_bias = np.clip((seeker_dyn_params["attack_bias"]["val"] - seeker_dyn_params["attack_bias"]["min"]) / \
                           (seeker_dyn_params["attack_bias"]["max"] - seeker_dyn_params["attack_bias"]["min"]), 0, 1)
    norm_scan_effort = np.clip((seeker_dyn_params["scan_effort"]["val"] - seeker_dyn_params["scan_effort"]["min"]) / \
                             (seeker_dyn_params["scan_effort"]["max"] - seeker_dyn_params["scan_effort"]["min"]), 0, 1)

    state_values = [
        float(seeker_known_target), # 현재 타겟 아는지 여부 (0.0 또는 1.0)
        float(observed_move),      # 방금 MTD 이동 관찰 여부 (0.0 또는 1.0)
        np.clip(seeker_observed_shuffle_ema, 0, 1), # MTD 셔플 빈도 추정치
        norm_atk_bias,             # 현재 공격 편향
        norm_scan_effort           # 현재 스캔 노력
    ]
    # NaN 값 방지
    state_values = [0.0 if np.isnan(v) else v for v in state_values]

    state = torch.tensor(state_values, dtype=torch.float32)

    return state.unsqueeze(0), observed_move # 배치 차원 추가 및 이동 관찰 여부 반환

def apply_action_seeker(action_idx: int):
    """Seeker RL 에이전트가 선택한 행동을 내부 파라미터 변경으로 적용합니다."""
    action = seeker_meta_actions.get(action_idx)
    if not action or action[0] == "none":
        print("    - Seeker 행동: 유지 (None)")
        return

    param_name, value = action
    current_val = seeker_dyn_params[param_name]["val"]
    new_val = current_val * value # 곱셈 방식으로 업데이트

    p_min = seeker_dyn_params[param_name]["min"]
    p_max = seeker_dyn_params[param_name]["max"]
    seeker_dyn_params[param_name]["val"] = float(np.clip(new_val, p_min, p_max))

    print(f"    - Seeker 행동: {param_name} -> {seeker_dyn_params[param_name]['val']:.2f}")

def select_attack_script_based_on_policy() -> Optional[str]:
    """Seeker 정책 파라미터에 따라 실행할 공격 스크립트를 확률적으로 선택합니다."""
    scan_prob = np.clip(0.4 * seeker_dyn_params["scan_effort"]["val"], 0.1, 0.8)
    attack_prob_base = seeker_dyn_params["attack_bias"]["val"] * (0.8 if seeker_known_target else 0.1)
    attack_prob = np.clip(attack_prob_base, 0.05, 0.9)

    available_attacks = get_available_attacks()
    discovery_attacks = [a for a in available_attacks if "discovery" in a or "scan" in a or "sniff" in a]
    exploit_attacks = [a for a in available_attacks if a not in discovery_attacks]

    rand_val = random.random()

    if rand_val < scan_prob and discovery_attacks:
        # 스캔 실행 (Discovery 스크립트 중 무작위 선택)
        selected_attack = random.choice(discovery_attacks)
        print(f"  [Seeker 결정] 스캔 실행 (확률: {scan_prob:.2f}). 선택된 스크립트: {selected_attack}")
        return selected_attack
    elif rand_val < scan_prob + attack_prob and exploit_attacks:
        # 공격 실행 (Exploit 스크립트 중 무작위 선택)
        selected_attack = random.choice(exploit_attacks)
        print(f"  [Seeker 결정] 공격 실행 (확률: {attack_prob:.2f}, Known: {seeker_known_target}). 선택된 스크립트: {selected_attack}")
        return selected_attack
    else:
        # 아무것도 안 함
        print(f"  [Seeker 결정] 행동 안 함 (스캔 확률: {scan_prob:.2f}, 공격 확률: {attack_prob:.2f})")
        return None


# ==============================================================================
# 메인 실행 로직 수정
# ==============================================================================
def run_single_attack(attack_to_run: str, state_file: str) -> Optional[subprocess.Popen]:
    """단일 공격 스크립트를 실행하고 로그 스트리밍 스레드를 시작합니다."""
    global attack_process

    # 이전 공격 정리 (기존 로직 유지)
    with attack_lock:
        if attack_process and attack_process.poll() is None:
            cleanup_attack_process("new_attack_request")

    attack_script_path = os.path.join(ATTACKS_DIR, attack_to_run)
    if not (os.path.exists(attack_script_path) and os.access(attack_script_path, os.X_OK)):
        print(f"⛔ 스크립트 오류: {attack_script_path}", file=sys.stderr)
        log_bus_event("attack_exception", {"attack": attack_to_run, "error": "Script not found or not executable"}, source_override="attack_orchestrator")
        return None

    target_ip, target_port, _ = read_mtd_target(state_file) # mtime은 여기서 사용 안 함
    if not target_ip or not target_port:
        target_ip, target_port = "10.13.0.3", 14550 # 기본값

    attack_base_name = attack_to_run.replace('.sh', '')
    attack_meta = get_attack_metadata(attack_to_run)

    process_env = os.environ.copy()
    process_env['TARGET_IP'] = target_ip
    process_env['TARGET_PORT'] = str(target_port)
    process_env['ATTACK_NAME'] = attack_base_name
    process_env['MY_IP'] = MY_IP_ADDRESS
    python_executable_dir = os.path.dirname(sys.executable)
    process_env['PATH'] = f"{python_executable_dir}:{os.environ.get('PATH', '')}"
    process_env['VIRTUAL_ENV'] = os.environ.get('VIRTUAL_ENV', os.path.dirname(python_executable_dir))

    proc = None
    try:
        print("\n" + "="*23 + " 공격 시작 " + "="*24)
        print(f"  - 스크립트         : {attack_to_run}")
        print(f"  - 타겟             : {target_ip}:{target_port}")
        print(f"  - 공격 카테고리    : {attack_meta['attack_category']}")
        print("="*58)

        log_bus_event("attack_started", {
            "attack": attack_to_run, "target": f"{target_ip}:{target_port}", "source_ip": MY_IP_ADDRESS,
            "attack_category": attack_meta['attack_category'], "mitre_tactics": attack_meta['mitre_tactics']
        }, source_override="attack_orchestrator")

        proc = subprocess.Popen(
            ['/bin/bash', attack_script_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding='utf-8', errors='replace', preexec_fn=os.setsid, env=process_env
        )
        with attack_lock: attack_process = proc

        threading.Thread(target=stream_reader, args=(proc.stdout, "stdout", attack_to_run), daemon=True).start()
        threading.Thread(target=stream_reader, args=(proc.stderr, "stderr", attack_to_run), daemon=True).start()

    except Exception as e:
        print(f"❌ 공격 실행 예외 ({attack_to_run}): {e}", file=sys.stderr)
        log_bus_event("attack_exception", {"attack": attack_to_run, "error": str(e)}, source_override="attack_orchestrator")
        with attack_lock: attack_process = None
        if proc and proc.poll() is None: _kill_process_group(proc)
        return None

    return proc

# ⭐️ Seeker RL 모드 메인 루프 함수
def run_seeker_mode(state_file: str, decision_interval: int):
    """Seeker RL 정책에 따라 주기적으로 행동을 결정하고 공격/스캔을 실행합니다."""
    global seeker_policy
    if not seeker_policy:
        print("❌ Seeker 모드 실행 불가: RL 정책 모델 로드 실패.")
        return

    print("\n--- 🤖 Seeker RL 모드 시작 ---")
    print(f"    결정 주기: {decision_interval}초")

    while not stop_event.is_set():
        start_time = time.time()
        print("\n" + "="*18 + " Seeker Decision Cycle " + "="*18)

        # 1. 환경 관찰
        current_state, observed_move = observe_environment_seeker(state_file)
        print(f"  [Seeker 관찰] 현재 상태: {np.round(current_state.numpy(), 3)}")
        print(f"                타겟 인지: {'Yes' if seeker_known_target else 'No'}, MTD 이동 감지: {'Yes' if observed_move else 'No'}")

        # 2. 행동 결정
        action_idx = 4 # 기본값 'none'
        try:
            with torch.no_grad():
                action_tensor, _, _ = seeker_policy.act(current_state)
                action_idx = action_tensor.item()
        except Exception as e:
            print(f"❌ Seeker 정책 모델 실행 오류: {e}", file=sys.stderr)

        print(f"  [Seeker 결정] 선택된 행동 인덱스: {action_idx}")

        # 3. 행동 적용 (내부 파라미터 업데이트)
        apply_action_seeker(action_idx)

        # 4. 공격/스캔 스크립트 선택 및 실행 (확률 기반)
        attack_script_to_run = select_attack_script_based_on_policy()

        if attack_script_to_run:
            proc = run_single_attack(attack_script_to_run, state_file)
            if proc:
                # Seeker 모드에서는 공격이 완료될 때까지 기다리지 않고 다음 결정 주기로 넘어감
                # (스크립트 자체의 duration은 내부에서 관리)
                # 필요 시, 공격 완료 후 결과(성공/실패)를 관찰하여 known_target 업데이트 가능
                print(f"    '{attack_script_to_run}' 실행 시작됨 (백그라운드).")
                # 공격 종료 로깅은 run_single_attack 내부 또는 별도 스레드에서 처리해야 함
                # (현재 구조에서는 wait() 없이는 return code 알 수 없음)
                # -> 간단화를 위해 attack_finished 로깅은 이 모드에서 생략하거나,
                #    별도의 프로세스 모니터링 스레드 필요
            else:
                print(f"    '{attack_script_to_run}' 실행 실패.")
        else:
             # 행동 안 함
             pass

        print("="*58)

        # 다음 결정까지 대기 (stop_event 감지하며 대기)
        elapsed_time = time.time() - start_time
        wait_time = max(0, decision_interval - elapsed_time)
        interrupted = stop_event.wait(timeout=wait_time)
        if interrupted:
             print("[Seeker 모드] 종료 신호 감지됨. 루프 종료.")
             break

    print("--- 🤖 Seeker RL 모드 종료 ---")


def main():
    def signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        print(f"\n[메인] 종료 신호 ({sig_name}) 수신...")
        terminate_orchestrator(f"signal_{sig_name}")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description="DVD 공격 오케스트레이터 v2.6 (Seeker RL Mode)")
    parser.add_argument('-a', '--attack', help="실행할 특정 공격 스크립트 (.sh 파일 이름)")
    parser.add_argument('--run-all', action='store_true', help="사용 가능한 모든 공격을 순차적으로 실행 (Seeker 모드와 동시 사용 불가)")
    parser.add_argument('--duration', type=int, default=60, help="--run-all 모드에서 각 공격 실행 최대 시간 (초)")
    parser.add_argument('--delay', type=int, default=5, help="--run-all 모드에서 공격 사이 대기 시간 (초)")
    # ⭐️ Seeker RL 모드 옵션 추가
    parser.add_argument('--seeker', action='store_true', help="Seeker RL 정책 모델을 사용하여 공격/스캔 수행")
    parser.add_argument('--seeker-interval', type=int, default=15, help="Seeker 모드 결정 주기 (초)")

    args = parser.parse_args()

    # 옵션 충돌 확인
    if args.seeker and (args.run_all or args.attack):
        print("⛔ 오류: --seeker 옵션은 --run-all 또는 -a 옵션과 함께 사용할 수 없습니다.")
        sys.exit(1)
    if not RL_AVAILABLE and args.seeker:
        print("⛔ 오류: --seeker 모드를 사용하려면 PyTorch를 설치해야 합니다.")
        sys.exit(1)


    state_file = get_mtd_state_file_path()
    all_attacks = get_available_attacks()

    # --- Seeker RL 모드 실행 ---
    if args.seeker:
        global seeker_policy
        seeker_policy = load_seeker_policy(SEEKER_MODEL_PATH)
        if seeker_policy:
            run_seeker_mode(state_file, args.seeker_interval)
        else:
             sys.exit(1) # 모델 로드 실패 시 종료

    # --- 기존 모드 실행 (run-all 또는 단일 공격) ---
    elif args.run_all:
        print(f"--- 전체 공격 순차 실행 모드 시작 ({len(all_attacks)}개 공격) ---")
        # ... (기존 run-all 로직과 동일) ...
        print(f"    각 공격 최대 실행 시간: {args.duration}초")
        print(f"    공격 간 대기 시간: {args.delay}초")
        for i, attack_name in enumerate(all_attacks, 1):
            if stop_event.is_set(): break
            attack_meta = get_attack_metadata(attack_name)
            print(f"\n--- [{i}/{len(all_attacks)}] '{attack_name}' 공격 실행 ---")
            proc = run_single_attack(attack_name, state_file)
            if proc:
                return_code = None
                try:
                    proc.wait(timeout=args.duration)
                    return_code = proc.returncode
                    print(f"    '{attack_name}' 정상 종료 (RC: {return_code}).")
                except subprocess.TimeoutExpired:
                    cleanup_attack_process(f"duration_limit ({args.duration}s)")
                    return_code = -1
                    print(f"    '{attack_name}' 시간 초과. 정리됨.")
                except Exception as wait_err:
                     cleanup_attack_process(f"wait_error_{type(wait_err).__name__}")
                     return_code = -2
                     print(f"❌ '{attack_name}' 대기 오류: {wait_err}", file=sys.stderr)

                log_bus_event("attack_finished", {"attack": attack_name, "return_code": return_code, "attack_category": attack_meta['attack_category']}, source_override="attack_orchestrator")
            else:
                log_bus_event("attack_exception", {"attack": attack_name, "error": "Failed to start"}, source_override="attack_orchestrator")

            if not stop_event.is_set() and i < len(all_attacks) and args.delay > 0:
                print(f"    다음 공격까지 {args.delay}초 대기...")
                interrupted = stop_event.wait(timeout=args.delay)
                if interrupted: break
        print("--- 전체 공격 순차 실행 완료 ---")


    elif args.attack:
        if args.attack not in all_attacks:
             print(f"⛔ 오류: 지정된 공격 '{args.attack}' 없음.", file=sys.stderr)
             sys.exit(1)
        attack_meta = get_attack_metadata(args.attack)
        print(f"--- 단일 공격 실행 모드: '{args.attack}' ---")
        proc = run_single_attack(args.attack, state_file)
        if proc:
            return_code = -99 # 초기값
            try:
                 proc.wait()
                 return_code = proc.returncode
                 print(f"    '{args.attack}' 종료됨 (RC: {return_code}).")
            except KeyboardInterrupt: return_code = -9 # signal_handler가 처리
            except Exception as wait_err: return_code = -2; print(f"❌ 대기 오류: {wait_err}", file=sys.stderr)
            # 종료 로그는 signal_handler 또는 finally 블록에서 처리되므로 중복 기록 방지
            # cleanup은 wait 후 필요 없음 (프로세스 이미 종료)
        else:
             print(f"    '{args.attack}' 실행 시작 실패.")
             # 실패 로그는 run_single_attack 내부에서 기록됨

    else:
        # 옵션 없이 실행 시 사용법 안내
        print("사용법: attack_orchestrator.py [--seeker | -a <attack.sh> | --run-all]")
        print("\n사용 가능한 공격 스크립트:")
        if all_attacks:
            for attack in all_attacks: print(f"  - {attack}")
        else:
             print("  (없음)")
        sys.exit(0)

    # 정상 종료 시 최종 정리 (signal_handler가 호출되지 않은 경우)
    if not stop_event.is_set():
        terminate_orchestrator("normal_completion")

if __name__ == "__main__":
    main()
# ```

# **주요 변경 및 추가 사항:**

# 1.  **`--seeker` 옵션 추가**: `argparse`를 사용하여 `--seeker` 플래그와 `--seeker-interval` 옵션을 추가했습니다. `--seeker`는 `--run-all` 또는 `-a`와 함께 사용할 수 없습니다.
# 2.  **RL 관련 임포트 및 클래스 정의**: 스크립트 상단에 `torch`, `ActorCritic` 등 필요한 모듈을 임포트하고 클래스를 정의했습니다. PyTorch가 설치되지 않은 경우 `--seeker` 옵션을 사용할 수 없도록 `RL_AVAILABLE` 플래그로 관리합니다.
# 3.  **Seeker 정책 로드 (`load_seeker_policy`)**: `--seeker` 모드 시 `seeker_policy.pth` 파일을 로드하는 함수를 추가했습니다.
# 4.  **Seeker 환경 관찰 (`observe_environment_seeker`)**:
#     * `read_mtd_target` 함수를 수정하여 MTD 상태 파일의 최종 수정 시간(`mtime`)을 반환하도록 했습니다.
#     * 이전 `mtime`과 비교하여 상태 파일 변경(MTD 셔플) 여부를 감지합니다 (`observed_move`).
#     * MTD 셔플 발생 시 `seeker_known_target`을 `False`로 초기화합니다. (실제로는 스캔 결과 등을 반영해야 더 정확해집니다.)
#     * 관찰된 셔플 빈도를 EMA(`seeker_observed_shuffle_ema`)로 추적합니다.
#     * `train.py`의 `_obs_seek`와 동일한 5차원 상태 벡터를 생성하여 반환합니다.
# 5.  **Seeker 행동 적용 (`apply_action_seeker`)**: Seeker 모델이 결정한 메타 행동에 따라 내부 `attack_bias`, `scan_effort` 파라미터를 업데이트하는 함수를 추가했습니다.
# 6.  **확률 기반 공격 선택 (`select_attack_script_based_on_policy`)**:
#     * 현재 `attack_bias`, `scan_effort`, `seeker_known_target` 값을 기반으로 스캔 또는 공격을 수행할 확률을 계산합니다.
#     * 사용 가능한 `.sh` 스크립트를 이름에 따라 Discovery/Exploit 그룹으로 나눕니다.
#     * 계산된 확률과 `random.random()` 값을 비교하여 실행할 행동(스캔/공격/안함)과 스크립트(해당 그룹 내 무작위 선택)를 결정합니다.
# 7.  **Seeker RL 모드 메인 루프 (`run_seeker_mode`)**:
#     * `--seeker-interval` 주기로 환경 관찰, 행동 결정, 파라미터 업데이트, 공격/스캔 선택 및 실행을 반복합니다.
#     * 공격 스크립트는 `run_single_attack`을 통해 실행하되, 완료될 때까지 기다리지 않고(`proc.wait()` 호출 안 함) 다음 주기로 넘어갑니다. (백그라운드 실행)
# 8.  **`main` 함수 수정**: `--seeker` 옵션 유무에 따라 `run_seeker_mode`를 호출하거나 기존의 `run-all`/단일 공격 로직을 수행하도록 분기합니다.

# **사용 방법:**

# ```bash
# # Seeker RL 모드로 실행 (결정 주기 15초)
# python3 attack_orchestrator.py --seeker --seeker-interval 15

# # 기존 방식: 모든 공격 30초씩 실행
# # python3 attack_orchestrator.py --run-all --duration 30

# # 기존 방식: 특정 공격 1회 실행
# # python3 attack_orchestrator.py -a network-scan.sh

