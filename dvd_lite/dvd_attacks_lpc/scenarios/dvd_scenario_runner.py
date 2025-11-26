#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 경로: dvd_lite/dvd_attacks_lpc/scenarios/dvd_scenario_runner.py
# 설명: 시나리오 실행 및 ML 파이프라인 연동 (Complete Version)
#       - Multi-round, Variable Duration, Random Order 지원
#       - 종료 시(중단 포함) ML 파이프라인 자동 실행

import os
import sys
import time
import json
import logging
import argparse
import subprocess
import requests
import random
import yaml
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s")
log = logging.getLogger("DVDScenarioRunner_Final")

# --- 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)  # dvd_attacks_lpc
BUS_DIR = os.path.join(ROOT, "bus")
os.makedirs(BUS_DIR, exist_ok=True)
BUS_LOG = os.path.join(BUS_DIR, "bus.log")

# --- 상수 정의 ---
API_BASE = os.environ.get("DVD_API_BASE", "http://127.0.0.1:8000")
ATTACK_ORCH = os.path.join(ROOT, "attack_orchestrator.py")
SEEKER_AGENT = os.path.join(ROOT, "rl", "seeker.py")
DECEPTION_MGR = os.path.join(ROOT, "mtd", "rl_driven_deception_manager.py")

# CTI ML 파이프라인 경로
ML_DIR = os.path.join(ROOT, "ml")
DATA_BUILDER = os.path.join(ML_DIR, "data_builder.py")
DATASET_MANAGER = os.path.join(ML_DIR, "dataset_manager.py")
TRAIN_CLASSIFIER = os.path.join(ML_DIR, "train_classifier.py")
PROCESSED_DIR = os.path.join(ML_DIR, "processed_data")

# --- 동적 시나리오 빌더 등록용 딕셔너리 ---
SCENARIO_BUILDERS: Dict[str, Any] = {}

# --- Bus Logger ---
def bus_write(source: str, type_: str, data: Optional[Dict[str, Any]] = None):
    """중앙 버스 로그에 이벤트를 기록합니다."""
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
        r = requests.post(api_url, json=params or {}, timeout=60)
        if r.status_code // 100 == 2:
            log.info(f"  -> [HTTP OK] {endpoint} 성공")
            return True
        else:
            log.warning(f"  -> [HTTP {r.status_code}] {endpoint} 실패: {r.text[:200]}")
    except Exception as e:
        log.warning(f"  -> [HTTP FAIL] {endpoint} 오류: {e}")

    return False

def mavlink_fallback(action: str, params: Optional[Dict[str, Any]] = None):
    if params is None: params = {}
    
    cmd_map = {
        "stage/arm-and-takeoff": [
            "docker", "exec", "ground-control-station-lite", "bash", "-lc",
            f"printf 'arm throttle\\ntakeoff {int(params.get('alt', 10))}\\n' | mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"
        ],
        "stage/return-to-land": [
            "docker", "exec", "ground-control-station-lite", "bash", "-lc",
            "printf 'mode RTL\\n' | mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"
        ],
        "stage/autopilot-flight": [
            "docker", "exec", "ground-control-station-lite", "bash", "-lc",
            "printf 'mode AUTO\\nwp load /root/missions/waypoints_circle.txt\\nwp set 1\\n' | mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"
        ],
        "stage/boot": ["true"],
        "stage/post_analysis": ["true"]
    }

    cmd = cmd_map.get(action)
    if not cmd:
        log.error(f"[Fallback] 정의되지 않은 액션: {action}")
        return

    if cmd == ["true"]:
        return

    log.warning(f"[MAV Fallback] HTTP 실패. Fallback 실행: {action}")
    try:
        subprocess.run(cmd, timeout=15, check=True, capture_output=True, text=True)
        log.info(f"  -> [Fallback OK] {action} 실행 완료")
    except Exception as e:
        log.error(f"  -> [Fallback FAIL] {action} 오류: {e}")

# --- 2. 공격 및 MTD 제어 ---
def _run_process_for_duration(cmd: List[str], log_name: str, duration: int) -> bool:
    proc = None
    try:
        log.info(f"  -> Executing: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        log.info(f"  -> {log_name} 프로세스 시작 (PID: {proc.pid}). {duration}초 대기...")
        
        try:
            proc.wait(timeout=duration)
            log.warning(f"  -> {log_name} 조기 종료됨 (RC: {proc.returncode})")
        except subprocess.TimeoutExpired:
            log.info(f"  -> {log_name} {duration}초 실행 완료. 종료 신호 전송.")
            proc.terminate()
            
    except Exception as e:
        log.error(f"  -> [FAIL] {log_name} 실행 실패: {e}")
        if proc: proc.kill()
        return False
    finally:
        if proc:
            try:
                proc.wait(timeout=5)
            except:
                proc.kill()
        log.info(f"[*] {log_name} 프로세스 종료됨.")
    return True

def do_attack(name: str, duration_sec: int, params: Optional[Dict[str, Any]] = None):
    if params is None: params = {}
    use_seeker = bool(params.pop("use_seeker", False))
    
    base_log_data = {"attack_name": name, "duration_sec": duration_sec, "params": params}
    
    # --- Seeker (RL Agent) ---
    if use_seeker:
        policy_path = params.get("policy_path", "rl/models/seeker_policy.pth")
        policy_full_path = os.path.join(ROOT, policy_path)
        log.info(f"[ATTACK] RL Seeker 에이전트 시작 (Duration: {duration_sec}s)")

        if not os.path.exists(policy_full_path):
            log.error(f"  -> [FAIL] Seeker 정책 파일 없음: {policy_full_path}")
            return

        cmd = [
            sys.executable,
            SEEKER_AGENT,
            "--policy", policy_full_path,
            "--mtd_state_file", os.path.join(ROOT, "mtd/shared_state/mtd_state.json"),
        ]

        bus_write("scenario_runner", "attack_started", {**base_log_data, "use_seeker": True})
        _run_process_for_duration(cmd, f"RLSeeker({name})", duration_sec)
        bus_write("scenario_runner", "attack_stopped", {"attack_name": name})
        return
    
    # --- Script Attack ---
    log.info(f"[ATTACK] 스크립트 공격 시작: {name} (Duration: {duration_sec}s)")
    cmd = [sys.executable, ATTACK_ORCH, "start", name, "-d", str(duration_sec)]
    
    script_args = []
    for k, v in params.items():
        flag = f"--{k.replace('_', '-')}"
        script_args.extend([flag, "true" if v is True else "false" if v is False else str(v)])
    if script_args:
        cmd.extend(["-p", *script_args])

    try:
        bus_write("scenario_runner", "attack_started", base_log_data)
        # 공격 스크립트 실행 (Blocking)
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=duration_sec + 10 # 넉넉한 타임아웃
        )
        log.info(f"  -> 공격 실행 완료 ({name})")
        if result.stderr:
            log.debug(f"Orchestrator Stderr: {result.stderr.strip()}")

    except subprocess.CalledProcessError as e:
        log.error(f"  -> [FAIL] 공격 스크립트 오류 (RC: {e.returncode}): {e.stderr}")
        bus_write("scenario_runner", "attack_failed", {**base_log_data, "error": e.stderr})
    except subprocess.TimeoutExpired:
        log.error(f"  -> [FAIL] 공격 스크립트 타임아웃 (강제 종료)")
        bus_write("scenario_runner", "attack_failed", {**base_log_data, "error": "Timeout"})
    except Exception as e:
        log.error(f"  -> [FAIL] 공격 실행 중 예외: {e}")
        bus_write("scenario_runner", "attack_failed", {**base_log_data, "error": str(e)})
    finally:
        bus_write("scenario_runner", "attack_stopped", {"attack_name": name})
        log.info(f"[ATTACK] {name} 종료 처리 완료.")

def set_mtd_level(level: int):
    log.info(f"[MTD] Heuristic Level Set: {level}")
    # TODO: mtd manager 연동 구현

def enable_mtd_rl(policy_path: str):
    log.info(f"[MTD] RL Policy Enabled: {policy_path}")
    # TODO: rl deception manager 연동 구현

# ⭐️ CTI ML 파이프라인 실행 함수
def run_cti_ml_pipeline():
    log.info("="*60)
    log.info("🤖 [ML PIPELINE] CTI 분류기 학습 파이프라인 시작")
    log.info("="*60)
    
    # 1. Data Builder
    log.info("[ML] 1. Data Builder 실행...")
    try:
        subprocess.run([sys.executable, DATA_BUILDER, "--log-dir", BUS_DIR], check=True, timeout=300)
        log.info("✅ Data Builder 완료.")
    except Exception as e:
        log.error(f"❌ DataBuilder Failed: {e}")
        return

    # 2. Dataset Manager
    log.info("[ML] 2. Dataset Manager 실행 (Balancing)...")
    try:
        subprocess.run(
            [sys.executable, DATASET_MANAGER, "--test-size", "0.2", "--processed-dir", PROCESSED_DIR, "--smote"], 
            check=True, timeout=180
        )
        log.info("✅ Dataset Manager 완료.")
    except Exception as e:
        log.error(f"❌ DatasetManager Failed: {e}")
        return

    # 3. Trainer
    log.info("[ML] 3. Classifier Trainer 실행...")
    try:
        subprocess.run([sys.executable, TRAIN_CLASSIFIER], check=True, timeout=300)
        log.info("✅ Classifier Trainer 완료.")
    except Exception as e:
        log.error(f"❌ Trainer Failed: {e}")
        return
        
    log.info("✨ ML Pipeline 전체 완료.")

# -------------------------------------------------------------------
#  CTI 데이터 수집 시나리오 (Multi-round, Variable Duration)
# -------------------------------------------------------------------

FOCUS8_ATTACKS = [
    "wifi-deauth-attack",
    "gps-spoofing",
    "waypoint-injection",
    "wifi-client-data-leak",
    "flight-log-extraction",
    "mission-extraction",
    "communication-link-flooding",
    "satellite-spoofing",
]

def build_s_cti_data_collection_focus8() -> Dict[str, Any]:
    """
    CTI 데이터 수집 시나리오 (Focus-8) - 동적 생성
    """
    steps: List[Dict[str, Any]] = []
    
    # 1. Boot & Takeoff
    steps.append({"action": "http", "endpoint": "stage/boot", "params": {}})
    steps.append({"action": "sleep", "sec": 10})
    steps.append({"action": "http", "endpoint": "stage/arm-and-takeoff", "params": {"alt": 15}})
    steps.append({"action": "sleep", "sec": 20})
    
    # 2. Auto Flight
    steps.append({"action": "http", "endpoint": "stage/autopilot-flight", "params": {}})
    steps.append({"action": "sleep", "sec": 20})

    # 3. Multi-round Attacks (3 Rounds)
    ROUNDS = 3
    DURATIONS = [10, 15, 30] # 랜덤 선택될 지속 시간
    
    for r in range(ROUNDS):
        log.info(f"Generating Round {r+1}/{ROUNDS}...")
        
        # 라운드마다 순서 섞기
        current_attacks = list(FOCUS8_ATTACKS)
        random.shuffle(current_attacks)
        
        for attack_name in current_attacks:
            # 랜덤 지속 시간 선택
            dur = random.choice(DURATIONS)
            
            steps.append({
                "action": "attack", 
                "name": attack_name, 
                "duration_sec": dur, 
                "params": {"use_seeker": False}
            })
            
            # 공격 간 짧은 휴식 (5초)
            steps.append({"action": "sleep", "sec": 5})
        
        # 라운드 간 휴식 (10초)
        steps.append({"action": "sleep", "sec": 10})

    # 4. RTL & Landing
    steps.append({"action": "http", "endpoint": "stage/return-to-land", "params": {}})
    steps.append({"action": "sleep", "sec": 20})
    steps.append({"action": "http", "endpoint": "stage/post_analysis", "params": {}})

    return {
        "description": f"[CTI Optimized] {ROUNDS} Rounds x {len(FOCUS8_ATTACKS)} Attacks (Variable Duration 10/15/30s)",
        "steps": steps
    }

# 동적 시나리오 등록
SCENARIO_BUILDERS["s_cti_data_collection_focus8"] = build_s_cti_data_collection_focus8


# --- 3. 시나리오 실행기 ---
def run_step(step: Dict[str, Any]):
    action = step.get("action")
    log.debug(f"--- Step: {action} ---")

    try:
        if action == "http":
            endpoint = step["endpoint"]
            params = step.get("params", {})
            if not try_http(endpoint, params):
                mavlink_fallback(endpoint, params)

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

        elif action == "run_ml_pipeline":
            run_cti_ml_pipeline()

        else:
            log.warning(f"Unknown action: {action}")

    except Exception as e:
        log.error(f"Step failed: {e}")

def main():
    ap = argparse.ArgumentParser(description="DVD Scenario Runner (v9.1 - Robust)")
    ap.add_argument("--scenario", required=True, help="실행할 시나리오 이름")
    ap.add_argument("--playlist", default=os.path.join(SCRIPT_DIR, "playlist.yml"))
    args = ap.parse_args()

    # 1. Dynamic Builder 확인
    dynamic_builder = SCENARIO_BUILDERS.get(args.scenario)
    sc = None

    if dynamic_builder:
        log.info(f"[INFO] 동적 빌더 시나리오 실행: {args.scenario}")
        sc = dynamic_builder()
    else:
        # 2. Playlist File 확인
        try:
            with open(args.playlist, "r", encoding="utf-8") as f:
                pl = yaml.safe_load(f)
            sc = pl.get(args.scenario)
        except Exception as e:
            log.warning(f"플레이리스트 로드 실패: {e}")
            sc = None
            
    if not sc:
        log.critical(f"❌ 시나리오 '{args.scenario}'를 찾을 수 없습니다.")
        sys.exit(1)

    log.info("="*60)
    log.info(f"시나리오 실행 시작: {args.scenario}")
    log.info(f"설명: {sc.get('description', 'N/A')}")
    log.info("="*60)
    
    bus_write("scenario_runner", "scenario_started", {"name": args.scenario, "description": sc.get('description')})
    start_time = time.time()
    
    try:
        steps = sc.get("steps", [])
        for i, st in enumerate(steps):
            log.info(f"--- [Step {i+1}/{len(steps)}] ---")
            run_step(st)
            # 스텝 간 최소 대기 (너무 빠르면 로그 꼬임 방지)
            time.sleep(1) 

    except KeyboardInterrupt:
        log.warning("\n" + "="*60)
        log.warning("🛑 [KeyboardInterrupt] 사용자 중단.")
        log.warning("="*60)
        bus_write("scenario_runner", "scenario_interrupted", {"name": args.scenario})

    except Exception as e:
        log.error(f"❌ 치명적 오류 발생: {e}", exc_info=True)
        bus_write("scenario_runner", "scenario_error", {"error": str(e)})

    finally:
        end_time = time.time()
        duration = end_time - start_time
        log.info("="*60)
        log.info(f"시나리오 종료 (총 소요: {duration:.2f}초)")
        log.info("="*60)
        bus_write("scenario_runner", "scenario_finished", {"name": args.scenario, "duration_sec": duration})
        
        # CTI 관련 시나리오면 무조건(성공/중단 상관없이) ML 파이프라인 실행
        # (사용자가 중단해도 그동안 모은 데이터로 학습하고 싶어하는 경우가 많음)
        if "cti_data_collection" in args.scenario:
             run_cti_ml_pipeline()

if __name__ == "__main__":
    main()