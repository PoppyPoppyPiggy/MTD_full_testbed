#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DVD Scenario Runner v2.0 (Paper-Ready)
=======================================
시나리오 실행 및 ML 파이프라인 연동
"""

import os
import sys
import time
import json
import logging
import argparse
import subprocess
import random
import yaml
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s")
log = logging.getLogger("ScenarioRunner")

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
BUS_DIR = os.path.join(ROOT, "bus")
os.makedirs(BUS_DIR, exist_ok=True)
BUS_LOG = os.path.join(BUS_DIR, "bus.log")

API_BASE = os.environ.get("DVD_API_BASE", "http://127.0.0.1:8000")
ATTACK_ORCH = os.path.join(ROOT, "attack_orchestrator.py")

ML_DIR = os.path.join(ROOT, "ml")
DATA_BUILDER = os.path.join(ML_DIR, "data_builder.py")
DATASET_MANAGER = os.path.join(ML_DIR, "dataset_manager.py")
TRAIN_CLASSIFIER = os.path.join(ML_DIR, "train_classifier.py")

SCENARIO_BUILDERS: Dict[str, Any] = {}


def bus_write(source: str, type_: str, data: Optional[Dict[str, Any]] = None):
    rec = {
        "source": source, "type": type_, "ts": time.time(),
        "timestamp": datetime.now(timezone.utc).isoformat(), "data": data or {}
    }
    try:
        with open(BUS_LOG, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error(f"Bus log 실패: {e}")


def try_http(endpoint: str, params: Optional[Dict[str, Any]] = None) -> bool:
    if not HAS_REQUESTS:
        return False
    endpoint_map = {
        "stage/boot": "/stage1", "stage/arm-and-takeoff": "/stage2",
        "stage/autopilot-flight": "/stage3", "stage/return-to-land": "/stage4",
        "stage/post_analysis": "/stage5"
    }
    api_path = endpoint_map.get(endpoint)
    if not api_path:
        return False
    try:
        r = requests.post(f"{API_BASE}{api_path}", json=params or {}, timeout=60)
        if r.status_code // 100 == 2:
            log.info(f"[HTTP OK] {endpoint}")
            return True
        log.warning(f"[HTTP {r.status_code}] {endpoint}")
    except Exception as e:
        log.warning(f"[HTTP FAIL] {e}")
    return False


def mavlink_fallback(action: str, params: Optional[Dict[str, Any]] = None):
    if params is None:
        params = {}
    cmd_map = {
        "stage/arm-and-takeoff": ["docker", "exec", "ground-control-station-lite", "bash", "-lc",
            f"printf 'arm throttle\\ntakeoff {int(params.get('alt', 10))}\\n' | mavproxy.py --master=udp:host.docker.internal:14550"],
        "stage/return-to-land": ["docker", "exec", "ground-control-station-lite", "bash", "-lc",
            "printf 'mode RTL\\n' | mavproxy.py --master=udp:host.docker.internal:14550"],
        "stage/autopilot-flight": ["docker", "exec", "ground-control-station-lite", "bash", "-lc",
            "printf 'mode AUTO\\n' | mavproxy.py --master=udp:host.docker.internal:14550"],
    }
    cmd = cmd_map.get(action)
    if not cmd:
        return
    log.warning(f"[Fallback] {action}")
    try:
        subprocess.run(cmd, timeout=15, check=True, capture_output=True, text=True)
    except Exception as e:
        log.error(f"[Fallback FAIL] {e}")


def do_attack(name: str, duration_sec: int, params: Optional[Dict[str, Any]] = None):
    if params is None:
        params = {}
    log.info(f"[ATTACK] {name} ({duration_sec}s)")
    
    base_data = {"attack_name": name, "duration_sec": duration_sec, "params": params}
    cmd = [sys.executable, ATTACK_ORCH, "start", name, "-d", str(duration_sec)]
    
    script_args = []
    for k, v in params.items():
        if k == "use_seeker":
            continue
        script_args.extend([f"--{k.replace('_', '-')}", str(v)])
    if script_args:
        cmd.extend(["-p"] + script_args)

    try:
        bus_write("scenario_runner", "attack_started", base_data)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_sec + 30)
        if result.returncode != 0:
            log.warning(f"  -> RC: {result.returncode}")
        else:
            log.info(f"  -> OK")
    except subprocess.TimeoutExpired:
        log.error(f"  -> Timeout")
        bus_write("scenario_runner", "attack_failed", {**base_data, "error": "Timeout"})
    except Exception as e:
        log.error(f"  -> Error: {e}")
        bus_write("scenario_runner", "attack_failed", {**base_data, "error": str(e)})
    finally:
        bus_write("scenario_runner", "attack_stopped", {"attack_name": name})


def run_ml_pipeline(use_tactic: bool = False):
    log.info("=" * 60)
    log.info("🤖 [ML PIPELINE] 시작")
    log.info("=" * 60)
    
    # Data Builder
    log.info("[ML] 1. Data Builder...")
    cmd = [sys.executable, DATA_BUILDER, "--log-dir", BUS_DIR]
    if use_tactic:
        cmd.append("--tactic-level")
    try:
        subprocess.run(cmd, check=True, timeout=300)
        log.info("✅ Data Builder")
    except Exception as e:
        log.error(f"❌ Data Builder: {e}")
        return

    # Dataset Manager
    log.info("[ML] 2. Dataset Manager...")
    cmd = [sys.executable, DATASET_MANAGER, "--test-size", "0.2"]
    if use_tactic:
        cmd.append("--tactic-level")
    try:
        subprocess.run(cmd, check=True, timeout=180)
        log.info("✅ Dataset Manager")
    except Exception as e:
        log.error(f"❌ Dataset Manager: {e}")
        return

    # Trainer
    log.info("[ML] 3. Trainer...")
    cmd = [sys.executable, TRAIN_CLASSIFIER]
    if use_tactic:
        cmd.append("--tactic-level")
    try:
        subprocess.run(cmd, check=True, timeout=600)
        log.info("✅ Trainer")
    except Exception as e:
        log.error(f"❌ Trainer: {e}")
        return
        
    log.info("✨ ML Pipeline 완료")


# 동적 시나리오 빌더
CORE_ATTACKS = [
    "drone-discovery", "gps-spoofing", "wifi-deauth-attack", "communication-link-flooding",
    "waypoint-injection", "satellite-spoofing", "flight-log-extraction", "mission-extraction",
]

def build_cti_dynamic() -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    steps.append({"action": "http", "endpoint": "stage/boot"})
    steps.append({"action": "sleep", "sec": 10})
    steps.append({"action": "http", "endpoint": "stage/arm-and-takeoff", "params": {"alt": 15}})
    steps.append({"action": "sleep", "sec": 20})
    steps.append({"action": "http", "endpoint": "stage/autopilot-flight"})
    steps.append({"action": "sleep", "sec": 20})

    ROUNDS = 3
    DURATIONS = [15, 25, 35]
    
    for r in range(ROUNDS):
        attacks = list(CORE_ATTACKS)
        random.shuffle(attacks)
        for attack in attacks:
            dur = random.choice(DURATIONS)
            steps.append({"action": "attack", "name": attack, "duration_sec": dur})
            steps.append({"action": "sleep", "sec": 5})
        steps.append({"action": "sleep", "sec": 10})

    steps.append({"action": "http", "endpoint": "stage/return-to-land"})
    steps.append({"action": "sleep", "sec": 20})
    steps.append({"action": "http", "endpoint": "stage/post_analysis"})

    return {"description": f"[Dynamic] {ROUNDS} Rounds x {len(CORE_ATTACKS)} Attacks", "steps": steps}

SCENARIO_BUILDERS["cti_dynamic"] = build_cti_dynamic


def run_step(step: Dict[str, Any]):
    action = step.get("action")
    try:
        if action == "http":
            endpoint = step["endpoint"]
            params = step.get("params", {})
            if not try_http(endpoint, params):
                mavlink_fallback(endpoint, params)
        elif action == "sleep":
            sec = step.get("sec", 1)
            log.info(f"[SLEEP] {sec}s")
            time.sleep(sec)
        elif action == "attack":
            do_attack(step["name"], int(step.get("duration_sec", 30)), step.get("params", {}))
        elif action == "run_ml_pipeline":
            run_ml_pipeline(use_tactic=step.get("tactic_level", False))
        else:
            log.warning(f"Unknown: {action}")
    except Exception as e:
        log.error(f"Step failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="DVD Scenario Runner v2.0")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--playlist", default=os.path.join(SCRIPT_DIR, "playlist.yml"))
    parser.add_argument("--tactic-level", action="store_true")
    parser.add_argument("--no-ml", action="store_true")
    args = parser.parse_args()

    # 동적 빌더 확인
    dynamic_builder = SCENARIO_BUILDERS.get(args.scenario)
    sc = None

    if dynamic_builder:
        log.info(f"[Dynamic] {args.scenario}")
        sc = dynamic_builder()
    else:
        try:
            with open(args.playlist, "r", encoding="utf-8") as f:
                pl = yaml.safe_load(f)
            sc = pl.get(args.scenario)
        except Exception as e:
            log.warning(f"Playlist 로드 실패: {e}")
            
    if not sc:
        log.critical(f"❌ 시나리오 없음: '{args.scenario}'")
        sys.exit(1)

    log.info("=" * 60)
    log.info(f"🚀 {args.scenario}")
    log.info(f"   {sc.get('description', 'N/A')}")
    log.info("=" * 60)
    
    bus_write("scenario_runner", "scenario_started", {"name": args.scenario, "description": sc.get('description')})
    start_time = time.time()
    
    try:
        steps = sc.get("steps", [])
        for i, st in enumerate(steps):
            log.info(f"--- [Step {i+1}/{len(steps)}] ---")
            run_step(st)
            time.sleep(1)

    except KeyboardInterrupt:
        log.warning("\n🛑 중단됨")
        bus_write("scenario_runner", "scenario_interrupted", {"name": args.scenario})

    except Exception as e:
        log.error(f"❌ 오류: {e}", exc_info=True)
        bus_write("scenario_runner", "scenario_error", {"error": str(e)})

    finally:
        duration = time.time() - start_time
        log.info("=" * 60)
        log.info(f"종료 ({duration:.1f}초)")
        log.info("=" * 60)
        bus_write("scenario_runner", "scenario_finished", {"name": args.scenario, "duration_sec": duration})
        
        if not args.no_ml and ("cti" in args.scenario.lower() or "tactic" in args.scenario.lower()):
            run_ml_pipeline(use_tactic=args.tactic_level)


if __name__ == "__main__":
    main()
