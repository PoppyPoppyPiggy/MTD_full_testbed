#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import logging
import argparse
import subprocess
import requests
from datetime import datetime, timezone
import yaml
from typing import Optional, Dict, Any

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s")
log = logging.getLogger("DVDScenarioRunner_v3")

# --- 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR) # dvd_attacks_lpc
BUS_DIR = os.path.join(ROOT, "bus")
os.makedirs(BUS_DIR, exist_ok=True)
BUS_LOG = os.path.join(BUS_DIR, "bus.log") # 중앙 이벤트 버스 로그

# --- 상수 정의 ---
API_BASE = os.environ.get("DVD_API_BASE", "http://127.0.0.1:8000") # DVD WebUI (플랫폼 제어용)
ATTACK_ORCH = os.path.join(ROOT, "attack_orchestrator.py") # 공격 실행기
DECEPTION_MGR = os.path.join(ROOT, "mtd", "rl_driven_deception_manager.py") # MTD RL 에이전트
DEFAULT_SEEKER_POLICY = os.path.join(ROOT, "rl", "models", "seeker_policy.pth") # Seeker (공격) RL 정책

# --- Bus Logger ---
def bus_write(source: str, type_: str, data: Optional[Dict[str, Any]] = None):
    """중앙 버스 로그에 시나리오 진행 상황을 기록합니다."""
    rec = {
        "source": source,
        "type": type_,
        "ts": time.time(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data or {}
    }
    try:
        with open(BUS_LOG, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error(f"Failed to write to bus log: {e}")

# --- 플랫폼 제어 (HTTP / Fallback) ---
def try_http(endpoint: str, params: Optional[Dict[str, Any]] = None) -> bool:
    """DVD WebUI(시뮬레이터 관리) API를 호출합니다."""
    url = f"{API_BASE}/{endpoint}" 
    
    log.info(f"[HTTP] API 호출 시도: {url} (params: {params or {}})")
    try:
        r = requests.post(url, json=params or {}, timeout=10)
        if r.status_code // 100 == 2:
            log.info(f"  -> [HTTP OK] {endpoint} 성공")
            return True
        else:
            log.warning(f"  -> [HTTP {r.status_code}] {endpoint} 실패: {r.text[:200]}")
    except requests.exceptions.ConnectionError as e:
        log.error(f"  -> [HTTP FAIL] {endpoint} 연결 실패. WebUI (port 8000)가 실행 중인지 확인하세요. ({e})")
    except Exception as e:
        log.warning(f"  -> [HTTP FAIL] {endpoint} 예상치 못한 오류: {e}")
    return False

def mavlink_fallback(action: str, params: Optional[Dict[str, Any]] = None):
    """HTTP API 호출 실패 시, MAVLink(mavproxy)로 직접 제어를 시도합니다."""
    if params is None: params = {}
    
    # ⭐️ API 엔드포인트 이름과 일치하도록 키 수정
    cmd_map = {
        "stage/arm-and-takeoff": ["docker","exec","ground-control-station-lite","bash","-lc", f"printf 'arm throttle\\ntakeoff {int(params.get('alt',10))}\\n' | mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"],
        "stage/return-to-land":  ["docker","exec","ground-control-station-lite","bash","-lc", "printf 'mode RTL\\n' | mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"],
        "stage/autopilot-flight":  ["docker","exec","ground-control-station-lite","bash","-lc", "printf 'mode AUTO\\nwp load /root/missions/waypoints_circle.txt\\nwp set 1\\n' | mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"],
        "stage/boot": ["true"],
        "stage/post_analysis": ["true"]
    }
    cmd = cmd_map.get(action)
    if not cmd:
        log.error(f"[Fallback] 정의되지 않은 액션: {action}")
        return

    log.warning(f"[MAV Fallback] HTTP 실패. Fallback 실행: {action}")
    try:
        subprocess.run(cmd, timeout=15, check=True, capture_output=True, text=True)
        log.info(f"  -> [Fallback OK] {action} 실행 완료")
    except subprocess.CalledProcessError as e:
        log.error(f"  -> [Fallback FAIL] {action} 실패: {e.stderr}")
    except subprocess.TimeoutExpired:
        log.error(f"  -> [Fallback FAIL] {action} 시간 초과")
    except Exception as e:
        log.error(f"  -> [Fallback FAIL] {action} 오류: {e}")

# --- 공격 및 MTD 제어 ---
def do_attack(name: str, duration_sec: int, params: Optional[Dict[str, Any]] = None):
    """
    attack_orchestrator.py를 옵션과 함께 직접 호출하여 공격을 실행/중지합니다.
    params:
        use_seeker (bool): --seeker 플래그 활성화 여부
        intensity (str): --intensity 플래그 (low, medium, high)
        policy_path (str): --policy_path (Seeker RL 정책)
    """
    if params is None: params = {}
    
    use_seeker = params.get("use_seeker", False)
    intensity = params.get("intensity", "medium")
    policy_path = params.get("policy_path", DEFAULT_SEEKER_POLICY)

    log_data = {
        "attack_name": name, 
        "duration_sec": duration_sec,
        "use_seeker": use_seeker,
        "intensity": intensity
    }
    log.info(f"[ATTACK] 공격 시작: {name} (Seeker: {use_seeker}, Intensity: {intensity}, Duration: {duration_sec}s)")
    bus_write("scenario_runner", "attack_started", log_data)
    
    # ⭐️ attack_orchestrator.py에 전달할 명령어 생성
    cmd = [sys.executable, ATTACK_ORCH, "run", name, "--intensity", intensity]
    
    if use_seeker:
        cmd.append("--seeker")
        if os.path.exists(policy_path):
            cmd.extend(["--policy_path", policy_path])
        else:
            log.warning(f"  -> Seeker 정책 파일을 찾을 수 없음: {policy_path}. Orchestrator 기본값 사용.")

    attack_proc = None
    try:
        log.info(f"  -> Executing: {' '.join(cmd)}")
        # ⭐️ Popen으로 백그라운드 실행
        attack_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        log.info(f"  -> {name} 프로세스 시작 (PID: {attack_proc.pid}). {duration_sec}초 대기...")
        time.sleep(duration_sec)
        
    except Exception as e:
        log.error(f"  -> [ATTACK FAIL] {name} 실행 실패: {e}")
        
    finally:
        # 공격 종료
        log.info(f"[ATTACK] 공격 종료: {name} (PID: {attack_proc.pid if attack_proc else 'N/A'})")
        if attack_proc:
            try:
                attack_proc.terminate() # 1단계: Terminate
                attack_proc.wait(timeout=5) # 5초간 대기
            except subprocess.TimeoutExpired:
                log.warning(f"  -> {name} (PID: {attack_proc.pid})가 5초 내에 종료되지 않아 강제 종료(KILL) 시도.")
                attack_proc.kill() # 2단계: Kill
            except Exception as e:
                log.error(f"  -> {name} 종료 중 오류: {e}")
                
        # ⭐️ Fallback: attack_orchestrator.py의 'stop' 명령어로 잔여 프로세스 정리
        subprocess.run([sys.executable, ATTACK_ORCH, "stop", name])
        bus_write("scenario_runner", "attack_stopped", {"attack_name": name})

def set_mtd_level(level:int):
    """Heuristic MTD 레벨을 설정합니다."""
    log.info(f"[MTD] Heuristic MTD 레벨 설정: {level}")
    bus_write("scenario_runner", "mtd_heuristic_level_set", {"level": level})
    # TODO: deception_manager.py가 이 이벤트를 수신하거나
    #       파일/API를 통해 레벨을 읽도록 하는 로직 필요.
    #       (현재는 bus.log에 기록만 남김)

def enable_mtd_rl(policy_path: str):
    """RL 기반 MTD를 활성화합니다."""
    log.info(f"[MTD] RL MTD 정책 활성화: {policy_path}")
    bus_write("scenario_runner", "mtd_rl_enabled", {"policy_path": policy_path})
    
    policy_full_path = os.path.join(ROOT, policy_path)
    if not os.path.exists(policy_full_path):
        log.error(f"  -> [MTD FAIL] RL Defender 정책 파일을 찾을 수 없음: {policy_full_path}")
        return
        
    try:
        # RL 에이전트 프로세스 실행 (rl_driven_deception_manager.py)
        log.info(f"  -> RL Deception Manager 실행...")
        # (참고: 이미 실행 중인 경우 이 명령은 실패할 수 있음.
        #  실제 환경에서는 상태 확인/reload 로직이 필요)
        subprocess.Popen([sys.executable, DECEPTION_MGR, "--policy", policy_full_path])
    except Exception as e:
        log.error(f"  -> [MTD FAIL] RL Deception Manager 실행 실패: {e}")

# --- 시나리오 실행기 ---
def run_step(step: Dict[str, Any]):
    """플레이리스트의 단일 스텝을 실행합니다."""
    action = step.get("action")
    log.debug(f"--- Step: {action} ---")
    
    try:
        if action == "http":
            endpoint = step["endpoint"]
            params = step.get("params", {})
            if not try_http(endpoint, params):
                mavlink_fallback(endpoint, params) # HTTP 실패 시 Fallback
        
        elif action == "sleep":
            sec = step.get("sec", 1)
            log.info(f"[SLEEP] {sec}초 대기...")
            time.sleep(sec)
        
        elif action == "attack":
            # ⭐️ [수정] params를 do_attack으로 전달
            do_attack(
                step["name"], 
                int(step.get("duration_sec", 30)),
                step.get("params", {}) # Pass the whole params dict
            )
        
        elif action == "mtd_set":
            set_mtd_level(int(step.get("level", 1)))
        
        elif action == "mtd_rl_enable":
            enable_mtd_rl(step.get("policy_path"))
        
        else:
            log.warning(f"알 수 없는 액션입니다: {action}")
            
    except KeyError as e:
        log.error(f"  -> [STEP FAIL] '{action}' 스텝에 필수 키 누락: {e}")
    except Exception as e:
        log.error(f"  -> [STEP FAIL] '{action}' 스텝 실행 중 오류: {e}", exc_info=True)

def main():
    ap = argparse.ArgumentParser(description="DVD Scenario Runner (v3)")
    ap.add_argument("--scenario", required=True, help="실행할 시나리오 키 (playlist.yml 참조)")
    ap.add_argument("--playlist", default=os.path.join(SCRIPT_DIR, "playlist.yml"), help="시나리오 YML 파일 경로")
    args = ap.parse_args()

    # 플레이리스트 로드
    try:
        with open(args.playlist, "r", encoding="utf-8") as f:
            pl = yaml.safe_load(f)
    except FileNotFoundError:
        log.critical(f"플레이리스트 파일을 찾을 수 없습니다: {args.playlist}")
        sys.exit(1)
    except Exception as e:
        log.critical(f"플레이리스트 파일 로드 실패: {e}")
        sys.exit(1)

    sc = pl.get(args.scenario)
    if not sc:
        log.critical(f"시나리오 '{args.scenario}'를 플레이리스트에서 찾을 수 없습니다.")
        log.error(f"사용 가능한 시나리오: {list(pl.keys())}")
        sys.exit(1)

    log.info("="*60)
    log.info(f"시나리오 실행 시작: {args.scenario}")
    log.info(f"설명: {sc.get('description', 'N/A')}")
    log.info("="*60)
    bus_write("scenario_runner", "scenario_started", {"name": args.scenario, "description": sc.get('description')})

    start_time = time.time()
    
    # 시나리오 스텝 순차 실행
    for i, st in enumerate(sc.get("steps", [])):
        log.info(f"--- [Step {i+1}/{len(sc.get('steps', []))}] ---")
        run_step(st)
        time.sleep(1) # 스텝 간 1초 휴식

    end_time = time.time()
    duration = end_time - start_time
    
    log.info("="*60)
    log.info(f"시나리오 실행 완료: {args.scenario} (총 {duration:.2f}초 소요)")
    log.info("="*60)
    bus_write("scenario_runner", "scenario_finished", {"name": args.scenario, "duration_sec": duration})

if __name__ == "__main__":
    main()

