#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# dvd_lite/dvd_attacks_lpc/scenarios/dvd_scenario_runner.py

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
ROOT = os.path.dirname(SCRIPT_DIR)  # dvd_attacks_lpc
BUS_DIR = os.path.join(ROOT, "bus")
os.makedirs(BUS_DIR, exist_ok=True)
BUS_LOG = os.path.join(BUS_DIR, "bus.log")  # 중앙 이벤트 버스 로그

# --- 상수 정의 ---
API_BASE = os.environ.get("DVD_API_BASE", "http://127.0.0.1:8000")  # DVD WebUI
ATTACK_ORCH = os.path.join(ROOT, "attack_orchestrator.py")
SEEKER_AGENT = os.path.join(ROOT, "rl", "seeker.py")
DECEPTION_MGR = os.path.join(ROOT, "mtd", "rl_driven_deception_manager.py")
# ⭐️ CTI ML 파이프라인 경로
DATA_BUILDER = os.path.join(ROOT, "ml", "data_builder.py")
DATASET_MANAGER = os.path.join(ROOT, "ml", "dataset_manager.py")
TRAIN_CLASSIFIER = os.path.join(ROOT, "ml", "train_classifier.py")

# --- 동적 시나리오 빌더 등록용 딕셔너리 ---
SCENARIO_BUILDERS: Dict[str, Any] = {}

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
        r = requests.post(api_url, json=params or {}, timeout=60)

        if r.status_code // 100 == 2:
            log.info(f"  -> [HTTP OK] {endpoint} ({api_url}) 성공")
            return True
        else:
            log.warning(f"  -> [HTTP {r.status_code}] {endpoint} ({api_url}) 실패: {r.text[:200]}")

    except requests.exceptions.ReadTimeout as e:
        log.warning(f"  -> [HTTP Timeout] {endpoint} ({api_url}) 응답 시간 초과 (60s). Fallback 시도.")
    except requests.exceptions.ConnectionError as e:
        log.error(f"  -> [HTTP FAIL] {endpoint} 연결 실패. WebUI (port 8000)가 실행 중인지 확인하세요. ({e})")
    except Exception as e:
        log.warning(f"  -> [HTTP FAIL] {endpoint} 예상치 못한 오류: {e}")

    return False  # 실패 시 False 반환하여 Fallback 실행

def mavlink_fallback(action: str, params: Optional[Dict[str, Any]] = None):
    """HTTP API 호출 실패 시, MAVLink(mavproxy)로 직접 제어를 시도합니다."""
    if params is None:
        params = {}

    cmd_map = {
        "stage/arm-and-takeoff": [
            "docker", "exec", "ground-control-station-lite", "bash", "-lc",
            f"printf 'arm throttle\\ntakeoff {int(params.get('alt', 10))}\\n' | "
            "mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"
        ],
        "stage/return-to-land": [
            "docker", "exec", "ground-control-station-lite", "bash", "-lc",
            "printf 'mode RTL\\n' | "
            "mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"
        ],
        "stage/autopilot-flight": [
            "docker", "exec", "ground-control-station-lite", "bash", "-lc",
            "printf 'mode AUTO\\nwp load /root/missions/waypoints_circle.txt\\nwp set 1\\n' | "
            "mavproxy.py --master=udp:host.docker.internal:14550 --out=udp:127.0.0.1:14551"
        ],
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
        if proc:
            proc.kill()
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
    """
    하나의 공격(name)을 attack_orchestrator 에 위임해 실행한다.

    - use_seeker=true 인 경우:
        * RL Seeker 에이전트를 duration_sec 동안 실행 (기존 로직 유지)
    - use_seeker=false (기본, CTI 수집용):
        * attack_orchestrator.py start 를 한 번만 호출
        * timeout 을 duration_sec + 20초로 설정
        * stop 서브커맨드는 더 이상 호출하지 않고
          scenario_runner 쪽에서는 attack_started / attack_stopped 메타 로그만 남긴다.
    """
    if params is None:
        params = {}

    # RL Seeker 사용 여부만 별도로 분리 (나머지는 .sh 스크립트 인자로 넘길 수 있음)
    use_seeker = bool(params.pop("use_seeker", False))

    # 공통 로그 데이터
    base_log_data = {
        "attack_name": name,
        "duration_sec": duration_sec,
        "params": params,
    }

    # --- 1) RL Seeker 분기 (기존 로직 유지) ---
    if use_seeker:
        policy_path = params.get("policy_path", "rl/models/seeker_policy.pth")
        policy_full_path = os.path.join(ROOT, policy_path)
        log.info(f"[ATTACK] RL Seeker 에이전트 시작 (Policy: {policy_path}, Duration: {duration_sec}s)")

        if not os.path.exists(policy_full_path):
            log.error(f"  -> [FAIL] Seeker 정책 파일을 찾을 수 없음: {policy_full_path}")
            bus_write("scenario_runner", "attack_failed", {**base_log_data, "use_seeker": True, "error": "Seeker policy not found"})
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

    # --- 2) 스크립트 공격 분기 (Orchestrator start 한 번) ---
    log_data = dict(base_log_data)  # shallow copy
    log.info(f"[ATTACK] 스크립트 공격 시작: {name} (Duration: {duration_sec}s)")

    # Orchestrator CLI 구성
    cmd: List[str] = [sys.executable, ATTACK_ORCH, "start", name, "-d", str(duration_sec)]

    # params -> attack script 인자 (--foo bar ...) 로 변환해서 -p 로 전달
    script_args: List[str] = []
    for k, v in params.items():
        flag = f"--{k.replace('_', '-')}"
        if isinstance(v, bool):
            script_args.append(flag)
            script_args.append("true" if v else "false")
        else:
            script_args.append(flag)
            script_args.append(str(v))

    if script_args:
        cmd.extend(["-p", *script_args])

    try:
        # 메타 로그 – 어떤 시나리오에서 어떤 공격이 시작됐는지 기록
        bus_write("scenario_runner", "attack_started", log_data)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            # ✅ duration + 여유 (여기선 +20초)
            timeout=duration_sec + 20,
        )
        log.info(f"  -> Orchestrator 'start' + 공격 실행 완료 ({name}).")
        if result.stdout:
            log.debug(f"[orchestrator stdout] {result.stdout.strip()}")
        if result.stderr:
            log.debug(f"[orchestrator stderr] {result.stderr.strip()}")

    except subprocess.CalledProcessError as e:
        log.error(f"  -> [FAIL] Orchestrator 'start' 실패: {e.stderr}")
        bus_write(
            "scenario_runner",
            "attack_failed",
            {**log_data, "error": e.stderr},
        )
    except subprocess.TimeoutExpired:
        msg = "Orchestrator 'start' 명령이 타임아웃되었습니다."
        log.error(f"  -> [FAIL] {msg}")
        bus_write(
            "scenario_runner",
            "attack_failed",
            {**log_data, "error": msg},
        )
    except Exception as e:
        log.error(f"  -> [FAIL] Orchestrator 실행 중 오류: {e}", exc_info=True)
        bus_write(
            "scenario_runner",
            "attack_failed",
            {**log_data, "error": str(e)},
        )
    finally:
        # stop 서브커맨드는 더 이상 호출하지 않고,
        # “시나리오 상에서 공격 단계가 끝났다”는 메타 이벤트만 남긴다.
        bus_write("scenario_runner", "attack_stopped", {"attack_name": name})
        log.info(f"[ATTACK] {name} 공격 단계 종료(메타 로그 기록).")


def set_mtd_level(level: int):
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

# ⭐️ CTI ML 파이프라인 실행 함수
def run_cti_ml_pipeline():
    """데이터 빌더, 데이터셋 관리자, 분류기 훈련을 순차적으로 실행합니다."""
    log.info("="*60)
    log.info("🤖 [ML PIPELINE] CTI 분류기 학습 파이프라인 시작")
    log.info("="*60)
    bus_write("scenario_runner", "ml_pipeline_start", {"stage": "data_building"})

    # 1. Data Builder 실행 (특징 추출 및 CSV 저장)
    log.info("[ML] 1. Data Builder 실행 (로그 파일 병합 및 특징 추출)...")
    try:
        subprocess.run([sys.executable, DATA_BUILDER], check=True, timeout=300)  # 5분 타임아웃
        log.info("✅ Data Builder 완료.")
    except subprocess.CalledProcessError as e:
        log.critical(f"❌ [ML FAIL] Data Builder 실패 (RC: {e.returncode}). 스크립트 중단.")
        log.debug(f"Data Builder Stderr: {e.stderr}")
        bus_write("scenario_runner", "ml_pipeline_fail", {"stage": "data_building", "error": e.stderr})
        return
    except subprocess.TimeoutExpired:
        log.critical("❌ [ML FAIL] Data Builder 시간 초과 (5분). 스크립트 중단.")
        bus_write("scenario_runner", "ml_pipeline_fail", {"stage": "data_building", "error": "Timeout (300s)"})
        return

    # 2. Dataset Manager 실행 (훈련/테스트 분할)
    log.info("[ML] 2. Dataset Manager 실행 (훈련/테스트 데이터셋 분할)...")
    try:
        subprocess.run([sys.executable, DATASET_MANAGER, "--test-size", "0.2"], check=True, timeout=120)
        log.info("✅ Dataset Manager 완료.")
    except subprocess.CalledProcessError as e:
        log.critical(f"❌ [ML FAIL] Dataset Manager 실패 (RC: {e.returncode}). 스크립트 중단.")
        bus_write("scenario_runner", "ml_pipeline_fail", {"stage": "dataset_splitting", "error": e.stderr})
        return
    except subprocess.TimeoutExpired:
        log.critical("❌ [ML FAIL] Dataset Manager 시간 초과 (120s). 스크립트 중단.")
        bus_write("scenario_runner", "ml_pipeline_fail", {"stage": "dataset_splitting", "error": "Timeout (120s)"})
        return

    # 3. Classifier Trainer 실행 (훈련, 모델 저장 및 평가)
    log.info("[ML] 3. Classifier Trainer 실행 (모델 훈련 및 평가)...")
    try:
        subprocess.run([sys.executable, TRAIN_CLASSIFIER], check=True, timeout=180)
        log.info("✅ Classifier Trainer 완료. 모델 및 평가 보고서가 output/에 저장됨.")
        bus_write("scenario_runner", "ml_pipeline_success", {"stage": "training_complete"})
    except subprocess.CalledProcessError as e:
        log.critical(f"❌ [ML FAIL] Classifier Trainer 실패 (RC: {e.returncode}). 스크립트 중단.")
        bus_write("scenario_runner", "ml_pipeline_fail", {"stage": "training_evaluation", "error": e.stderr})
    except subprocess.TimeoutExpired:
        log.critical("❌ [ML FAIL] Classifier Trainer 시간 초과 (180s). 스크립트 중단.")
        bus_write("scenario_runner", "ml_pipeline_fail", {"stage": "training_evaluation", "error": "Timeout (180s)"})


# -------------------------------------------------------------------
#  새 CTI용 시나리오: s_cti_data_collection_focus8
#   - 8개 공격만 길게(각 120s) 반복
#   - 목적: CTI 분류기 학습용 "공격별 긴 구간" 데이터 확보
# -------------------------------------------------------------------

FOCUS8_ATTACKS = [
    ("wifi-deauth-attack",         120),
    ("gps-spoofing",               120),
    ("waypoint-injection",         120),
    ("wifi-client-data-leak",      120),
    ("flight-log-extraction",      120),
    ("mission-extraction",         120),
    ("communication-link-flooding",120),
    ("satellite-spoofing",         120),
]


def build_s_cti_data_collection_focus8() -> Dict[str, Any]:
    """
    CTI 데이터 수집 전용 시나리오 (Focus-8, dict 기반)
    - run_step()에서 사용하는 dict 포맷으로 steps를 구성한다.
    """
    steps: List[Dict[str, Any]] = []

    # (1) 부팅 + 이륙 + 자동 비행 시작
    steps.append({
        "action": "http",
        "endpoint": "stage/boot",
        "params": {}
    })
    steps.append({"action": "sleep", "sec": 10})

    steps.append({
        "action": "http",
        "endpoint": "stage/arm-and-takeoff",
        "params": {"alt": 10}
    })
    steps.append({"action": "sleep", "sec": 20})

    steps.append({
        "action": "http",
        "endpoint": "stage/autopilot-flight",
        "params": {}
    })
    steps.append({"action": "sleep", "sec": 20})

    # (2) 본격 공격 구간: 8개 공격 × 각 120초
    for attack_name, duration in FOCUS8_ATTACKS:
        steps.append({
            "action": "attack",
            "name": attack_name,
            "duration_sec": duration,
            "params": {}
        })
        steps.append({"action": "sleep", "sec": 15})

    # (3) 착륙 + post-analysis
    steps.append({
        "action": "http",
        "endpoint": "stage/return-to-land",
        "params": {}
    })
    steps.append({"action": "sleep", "sec": 15})

    steps.append({
        "action": "http",
        "endpoint": "stage/post_analysis",
        "params": {}
    })

    return {
        "description": "[CTI] Focus-8 (8 attacks x 120s, long CTI data collection)",
        "steps": steps
    }


# 동적 시나리오 등록
SCENARIO_BUILDERS["s_cti_data_collection_focus8"] = build_s_cti_data_collection_focus8


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

        elif action == "mtd_rl_enable":
            enable_mtd_rl(step.get("policy_path"))

        elif action == "run_ml_pipeline":
            run_cti_ml_pipeline()

        else:
            log.warning(f"알 수 없는 액션입니다: {action}")

    except KeyError as e:
        log.error(f"  -> [STEP FAIL] '{action}' 스텝에 필수 키 누락: {e}")
    except Exception as e:
        log.error(f"  -> [STEP FAIL] '{action}' 스텝 실행 중 오류: {e}", exc_info=True)


def main():
    ap = argparse.ArgumentParser(description="DVD Scenario Runner (v9 - Standalone Runner)")
    ap.add_argument("--scenario", required=True, help="실행할 시나리오 키 (playlist.yml 또는 SCENARIO_BUILDERS 참조)")
    ap.add_argument("--playlist", default=os.path.join(SCRIPT_DIR, "playlist.yml"), help="시나리오 YML 파일 경로")
    args = ap.parse_args()

    # 1) 먼저 동적 시나리오 빌더에서 찾기
    dynamic_builder = SCENARIO_BUILDERS.get(args.scenario)
    sc: Dict[str, Any]

    if dynamic_builder is not None:
        log.info(f"[INFO] 동적 빌더에서 시나리오 생성: {args.scenario}")
        sc = dynamic_builder()
    else:
        # 2) playlist.yml에서 검색
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

    try:
        steps_list: List[Dict[str, Any]] = sc.get("steps", [])
        for i, st in enumerate(steps_list):
            log.info(f"--- [Step {i+1}/{len(steps_list)}] ---")
            run_step(st)
            time.sleep(1)  # 스텝 간 1초 휴식

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

        # ⭐️ CTI 데이터 수집용 시나리오 끝나면 ML 파이프라인 자동 실행
        if args.scenario in ("s_cti_data_collection_full", "s_cti_data_collection_focus8","s_cti_data_collection_core6"):
            run_cti_ml_pipeline()


if __name__ == "__main__":
    main()
