#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# v9: CTI/ML 자동화 로직 제거 (권한 문제), HTTP/Orchestrator 타임아웃 수정
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
from typing import Optional, Dict, Any, List

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s")
log = logging.getLogger("DVDScenarioRunner_v9")

# --- 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR) # dvd_attacks_lpc
BUS_DIR = os.path.join(ROOT, "bus")
os.makedirs(BUS_DIR, exist_ok=True)
BUS_LOG = os.path.join(BUS_DIR, "bus.log") # 중앙 이벤트 버스 로그

# --- 상수 정의 ---
API_BASE = os.environ.get("DVD_API_BASE", "http://127.0.0.1:8000") # DVD WebUI
ATTACK_ORCH = os.path.join(ROOT, "attack_orchestrator.py")
SEEKER_AGENT = os.path.join(ROOT, "rl", "seeker.py") 
DECEPTION_MGR = os.path.join(ROOT, "mtd", "rl_driven_deception_manager.py") 

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

# --- 1. 플랫폼 제어 (HTTP / Fallback) ---
def try_http(endpoint: str, params: Optional[Dict[str, Any]] = None) -> bool:
    """DVD WebUI(시뮬레이터 관리) API를 호출합니다."""
    
    endpoint_map = {
        "stage/boot": "/stage1",
        "stage/arm-and-takeoff": "/stage2",
        "stage/autopilot-flight": "/stage3",
        "stage/return-to-land": "/stage4",
        "stage/post_analysis": "/stage5"
    }
    
    api_path = endpoint_map.get(endpoint)
    
    if not api_path:
        log.error(f"[HTTP] 매핑에 없는 엔드포인트: {endpoint}")
        return False

    api_url = f"{API_BASE}{api_path}"
    log.info(f"[HTTP] API 호출 시도: {api_url} (params: {params or {}})")
    
    try:
        # ⭐️ [수정 v9] API 타임아웃을 60초로 늘려 stage1/2/3의 긴 실행 시간 허용
        r = requests.post(api_url, json=params or {}, timeout=60) 
        
        if r.status_code // 100 == 2:
            log.info(f"  -> [HTTP OK] {endpoint} ({api_url}) 성공")
            return True
        else:
            log.warning(f"  -> [HTTP {r.status_code}] {endpoint} ({api_url}) 실패: {r.text[:200]}")
            
    except requests.exceptions.ReadTimeout as e:
        # ⭐️ [수정 v9] 타임아웃은 API 호출 실패로 간주하고 Fallback을 유도
        log.warning(f"  -> [HTTP Timeout] {endpoint} ({api_url}) 응답 시간 초과 (60s). Fallback 시도.")
    except requests.exceptions.ConnectionError as e:
        log.error(f"  -> [HTTP FAIL] {endpoint} 연결 실패. WebUI (port 8000)가 실행 중인지 확인하세요. ({e})")
    except Exception as e:
        log.warning(f"  -> [HTTP FAIL] {endpoint} 예상치 못한 오류: {e}")
        
    return False # 실패 시 False 반환하여 Fallback 실행

def mavlink_fallback(action: str, params: Optional[Dict[str, Any]] = None):
    """HTTP API 호출 실패 시, MAVLink(mavproxy)로 직접 제어를 시도합니다."""
    if params is None: params = {}
    
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

    if cmd == ["true"]:
        log.info(f"  -> (Fallback 무시: {action}은(는) 논리 스텝)")
        return

    log.warning(f"[MAV Fallback] HTTP 실패. Fallback 실행: {action}")
    try:
        result = subprocess.run(cmd, timeout=15, check=True, capture_output=True, text=True)
        log.info(f"  -> [Fallback OK] {action} 실행 완료")
        log.debug(f"Fallback stdout: {result.stdout}")
    except subprocess.CalledProcessError as e:
        log.error(f"  -> [Fallback FAIL] {action} 오류 (Exit Code {e.returncode}): {e.stderr}")
    except Exception as e:
        log.error(f"  -> [Fallback FAIL] {action} 알 수 없는 오류: {e}")


# --- 2. 공격 및 MTD 제어 ---
def _run_process_for_duration(cmd: List[str], log_name: str, duration: int) -> bool:
    proc = None
    try:
        log.info(f"  -> Executing: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        log.info(f"  -> {log_name} 프로세스 시작 (PID: {proc.pid}). {duration}초 대기...")
        proc.wait(timeout=duration)
        log.warning(f"  -> {log_name} (PID: {proc.pid})가 지정된 시간({duration}s)보다 일찍 종료되었습니다. (RC: {proc.returncode})")
    except subprocess.TimeoutExpired:
        log.info(f"  -> {log_name} (PID: {proc.pid})가 {duration}초 동안 실행되었습니다. 종료 신호(SIGTERM) 전송.")
        proc.terminate() 
    except Exception as e:
        log.error(f"  -> [FAIL] {log_name} 실행 실패: {e}")
        if proc: proc.kill()
        return False 
    finally:
        if proc:
            try:
                proc.wait(timeout=5) 
                log.info(f"  -> {log_name} (PID: {proc.pid}) 정상 종료 확인 (RC: {proc.returncode}).")
            except subprocess.TimeoutExpired:
                log.error(f"  -> [FAIL] {log_name} (PID: {proc.pid})가 강제 종료(Terminate)에 응답하지 않습니다. Kill 실행.")
                proc.kill()
        log.info(f"[*] {log_name} 프로세스 종료됨.")
    return True

def do_attack(name: str, duration_sec: int, params: Optional[Dict[str, Any]] = None):
    if params is None: params = {}
    use_seeker = params.get("use_seeker", False)
    intensity = params.get("intensity", "medium") 
    log_data = {"attack_name": name, "duration_sec": duration_sec, "use_seeker": use_seeker, "intensity": intensity}
    
    if use_seeker:
        policy_path = params.get("policy_path", "rl/models/seeker_policy.pth")
        policy_full_path = os.path.join(ROOT, policy_path)
        log.info(f"[ATTACK] RL Seeker 에이전트 시작 (Policy: {policy_path}, Duration: {duration_sec}s)")
        if not os.path.exists(policy_full_path):
             log.error(f"  -> [FAIL] Seeker 정책 파일을 찾을 수 없음: {policy_full_path}")
             bus_write("scenario_runner", "attack_failed", {**log_data, "error": "Seeker policy not found"})
             return
        cmd = [sys.executable, SEEKER_AGENT, "--policy", policy_full_path, "--mtd_state_file", os.path.join(ROOT, "mtd/shared_state/mtd_state.json")]
        bus_write("scenario_runner", "attack_started", log_data)
        _run_process_for_duration(cmd, f"RLSeeker({name})", duration_sec)
        bus_write("scenario_runner", "attack_stopped", {"attack_name": name})
    else:
        log.info(f"[ATTACK] 스크립트 공격 시작: {name} (Duration: {duration_sec}s)")
        cmd = [sys.executable, ATTACK_ORCH, "start", name, "-d", str(duration_sec)]
        try:
            # ⭐️ [수정 v9] 타임아웃을 10초 -> 30초로 늘려 MTD 타겟 리졸브 시간 확보
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            log.info(f"  -> Orchestrator 'start' 명령 전달 성공.")
            log.debug(f"Orchestrator stdout: {result.stdout}")
            bus_write("scenario_runner", "attack_started", log_data)
            log.info(f"  -> {name} 공격이 {duration_sec}초 동안 실행되도록 대기...")
            time.sleep(duration_sec)
        except subprocess.CalledProcessError as e:
             log.error(f"  -> [FAIL] Orchestrator 'start' 명령 실패: {e.stderr}")
             bus_write("scenario_runner", "attack_failed", {**log_data, "error": e.stderr})
        except subprocess.TimeoutExpired as e:
             log.error(f"  -> [FAIL] Orchestrator 'start' 명령이 30초 내에 응답하지 않았습니다 (타임아웃).")
             bus_write("scenario_runner", "attack_failed", {**log_data, "error": "Orchestrator start timed out (30s)"})
        except Exception as e:
             log.error(f"  -> [FAIL] Orchestrator 'start' 실행 중 오류: {e}")
             bus_write("scenario_runner", "attack_failed", {**log_data, "error": str(e)})
        finally:
            log.info(f"[ATTACK] {name} 공격 중지 명령 전송...")
            subprocess.run([sys.executable, ATTACK_ORCH, "stop", name], capture_output=True)
            bus_write("scenario_runner", "attack_stopped", {"attack_name": name})

def set_mtd_level(level:int):
    log.info(f"[MTD] Heuristic MTD 레벨 설정: {level}")
    bus_write("scenario_runner", "mtd_heuristic_level_set", {"level": level})

def enable_mtd_rl(policy_path: str):
    log.info(f"[MTD] RL MTD 정책 활성화: {policy_path}")
    policy_full_path = os.path.join(ROOT, policy_path)
    if not os.path.exists(policy_full_path):
        log.error(f"  -> [MTD FAIL] RL Defender 정책 파일을 찾을 수 없음: {policy_full_path}")
        bus_write("scenario_runner", "mtd_rl_failed", {"error": "Defender policy not found"})
        return
    try:
        log.info(f"  -> RL Deception Manager 실행...")
        proc = subprocess.Popen([sys.executable, DECEPTION_MGR, "--policy", policy_full_path])
        bus_write("scenario_runner", "mtd_rl_enabled", {"policy_path": policy_path, "pid": proc.pid})
        log.info(f"  -> RL Deception Manager 시작됨 (PID: {proc.pid}).")
    except Exception as e:
        log.error(f"  -> [MTD FAIL] RL Deception Manager 실행 실패: {e}")
        bus_write("scenario_runner", "mtd_rl_failed", {"error": str(e)})


# --- 3. 시나리오 실행기 ---
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
            do_attack(
                step["name"], 
                int(step.get("duration_sec", 30)),
                step.get("params", {})
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
    ap = argparse.ArgumentParser(description="DVD Scenario Runner (v9 - Standalone Runner)")
    ap.add_argument("--scenario", required=True, help="실행할 시나리오 키 (playlist.yml 참조)")
    ap.add_argument("--playlist", default=os.path.join(SCRIPT_DIR, "playlist.yml"), help="시나리오 YML 파일 경로")
    # ⭐️ [제거 v9] --train 플래그 제거
    args = ap.parse_args()

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

    # ⭐️ [제거 v9] CTI 모니터 시작 로직 제거

    log.info("="*60)
    log.info(f"시나리오 실행 시작: {args.scenario}")
    log.info(f"설명: {sc.get('description', 'N/A')}")
    log.info("="*60)
    bus_write("scenario_runner", "scenario_started", {"name": args.scenario, "description": sc.get('description')})
    start_time = time.time()
    
    try:
        for i, st in enumerate(sc.get("steps", [])):
            log.info(f"--- [Step {i+1}/{len(sc.get('steps', []))}] ---")
            run_step(st)
            time.sleep(1) # 스텝 간 1초 휴식

    except KeyboardInterrupt:
        log.warning("\n" + "="*60)
        log.warning("🛑 [KeyboardInterrupt] 시나리오 실행이 중단되었습니다.")
        log.warning("="*60)
        bus_write("scenario_runner", "scenario_interrupted", {"name": args.scenario})

    finally:
        end_time = time.time()
        duration = end_time - start_time
        
        log.info("="*60)
        log.info(f"시나리오 실행 완료: {args.scenario} (총 {duration:.2f}초 소요)")
        log.info("="*60)
        bus_write("scenario_runner", "scenario_finished", {"name": args.scenario, "duration_sec": duration})

        # ⭐️ [제거 v9] CTI 모니터 중지 및 학습 로직 제거

if __name__ == "__main__":
    main()