#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD/FANET HoneyDrone Testbed Web Console (Flask)
- 공격 모듈 실행(DUR/INTENSITY 등 파라미터)
- 시나리오 실행
- auto_eval(ns-3 포함) 실행
- bus.log / window_features.csv / ns3_metrics.csv 조회 & 다운로드
- 안전한 화이트리스트 기반 실행 (임의 명령 차단)
"""

import os
import csv
import json
import time
import threading
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash

# ====== 기본 경로 설정 ======
ROOT = os.environ.get("MTD_ROOT", "/home/kali/MTD/MTD_full_testbed")
BASE = os.environ.get("BASE", f"{ROOT}/dvd_lite/dvd_attacks_lpc")

ATTACK_OUT = f"{BASE}/attack_output"
TOOLS = f"{BASE}/tools"
MODULES_DIR = f"{BASE}/modules"
SCENARIOS_DIR = f"{BASE}/scenarios"
EVAL = f"{BASE}/eval"
ENV_SH = f"{BASE}/00_env.sh"

BUS_LOG = f"{ATTACK_OUT}/bus.log"
TIMELINE = f"{ATTACK_OUT}/effect_timeline.csv"
FEATURES = f"{ATTACK_OUT}/window_features.csv"
NS3_METRICS = f"{ATTACK_OUT}/ns3_metrics.csv"
PLOT_PNG = f"{ATTACK_OUT}/eval.png"  # tools/plot_eval.py 기본 산출물 가정(있으면 표시)

Path(ATTACK_OUT).mkdir(parents=True, exist_ok=True)

# ====== 화이트리스트 ======
ALLOWED_MODULES = [
    "wifi_slow_scan",
    "telemetry_trickle_jam",
    "mavlink_param_drift",
    "gps_slow_spoof",
    "power_route_bias",
    "service_enum_probe",
    # 필요 시 여기 추가
]
ALLOWED_INTENSITY = ["low", "medium", "high"]

ALLOWED_SCENARIOS = [
    "S_lpc_multi.pipeline",
    # 필요 시 여기 추가(파일명이 실제로 존재해야 실행)
]

# ====== Flask ======
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "mtd_ui_dev_secret"  # 데모용

# ====== 유틸 ======
def run_bash(cmd: str) -> subprocess.CompletedProcess:
    """
    bash -lc 로 실행하여 00_env.sh 를 source 한 뒤 커맨드 수행
    stdout/stderr 를 모두 캡처해서 반환
    """
    full = f'set -euo pipefail; source "{ENV_SH}" 2>/dev/null || true; {cmd}'
    return subprocess.run(["bash", "-lc", full],
                          capture_output=True, text=True)

def run_bash_bg(cmd: str, log_path: str = None):
    """
    백그라운드(스레드)로 실행. 긴 작업(auto_eval, scenario 등)에 사용.
    """
    def _target():
        res = run_bash(cmd)
        msg = f"[CMD]\n{cmd}\n[STDOUT]\n{res.stdout}\n[STDERR]\n{res.stderr}\n[RC]={res.returncode}\n"
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg)
        else:
            print(msg)
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t

def parse_csv_head(path: str, n=50):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return {"headers": [], "rows": []}
    headers, rows = [], []
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        try:
            headers = next(r)
        except StopIteration:
            return {"headers": [], "rows": []}
        for i, row in enumerate(r):
            if i >= n:
                break
            rows.append(row)
    return {"headers": headers, "rows": rows}

def tail_text(path: str, n=1200) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        # 간단 구현(작은 파일 가정) — 큰 로그면 개선 필요
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
        return "\n".join(data.splitlines()[-n:])
    except Exception:
        return ""

# ====== 라우팅 ======
@app.route("/")
def index():
    bus_tail = tail_text(BUS_LOG, 300)
    ns3 = parse_csv_head(NS3_METRICS, n=50)
    features = parse_csv_head(FEATURES, n=30)
    timeline = parse_csv_head(TIMELINE, n=30)
    plot_exists = os.path.isfile(PLOT_PNG)

    return render_template(
        "index.html",
        allowed_modules=ALLOWED_MODULES,
        allowed_intensity=ALLOWED_INTENSITY,
        allowed_scenarios=[s for s in ALLOWED_SCENARIOS if os.path.isfile(f"{SCENARIOS_DIR}/{s}")],
        bus_tail=bus_tail,
        ns3=ns3,
        features=features,
        timeline=timeline,
        plot_exists=plot_exists,
        base_path=BASE,   # ← 추가
    )

@app.post("/start-attack")
def start_attack():
    module = request.form.get("module", "").strip()
    intensity = request.form.get("intensity", "low").strip().lower()
    dur = request.form.get("duration", "20").strip()

    if module not in ALLOWED_MODULES:
        flash("허용되지 않은 모듈입니다.", "error")
        return redirect(url_for("index"))
    if intensity not in ALLOWED_INTENSITY:
        flash("허용되지 않은 강도입니다.", "error")
        return redirect(url_for("index"))
    try:
        int(dur)
    except ValueError:
        flash("Duration은 정수(초)여야 합니다.", "error")
        return redirect(url_for("index"))

    # 실행
    cmd = f'cd "{BASE}" && DUR={dur} INTENSITY={intensity} modules/{module}.sh'
    log_path = f"{ATTACK_OUT}/web_actions.log"
    run_bash_bg(cmd, log_path=log_path)

    flash(f"모듈 실행 요청: {module} (dur={dur}s, intensity={intensity})", "ok")
    return redirect(url_for("index"))

@app.post("/run-scenario")
def run_scenario():
    scen = request.form.get("scenario", "").strip()
    if scen not in ALLOWED_SCENARIOS:
        flash("허용되지 않은 시나리오입니다.", "error")
        return redirect(url_for("index"))

    cmd = f'cd "{BASE}" && timeout 300s scenarios/{scen} || true'
    log_path = f"{ATTACK_OUT}/web_actions.log"
    run_bash_bg(cmd, log_path=log_path)

    flash(f"시나리오 실행: {scen}", "ok")
    return redirect(url_for("index"))

@app.post("/auto-eval")
def auto_eval():
    # timeline 생성 → features → ns-3 → (선택)plot
    cmd = f'cd "{BASE}" && tools/auto_eval.sh; python3 tools/plot_eval.py || true'
    log_path = f"{ATTACK_OUT}/web_actions.log"
    run_bash_bg(cmd, log_path=log_path)

    flash("Auto Eval 수행 요청됨.", "ok")
    return redirect(url_for("index"))

@app.get("/download/<what>")
def download(what):
    m = {
        "bus": BUS_LOG,
        "timeline": TIMELINE,
        "features": FEATURES,
        "ns3": NS3_METRICS,
        "plot": PLOT_PNG,
        "web_log": f"{ATTACK_OUT}/web_actions.log"
    }
    path = m.get(what)
    if not path or not os.path.isfile(path):
        flash("파일이 없습니다.", "error")
        return redirect(url_for("index"))
    return send_file(path, as_attachment=True)

@app.get("/metrics.json")
def metrics_json():
    """
    간단한 차트 용 JSON: ns3_metrics.csv를 반환
    """
    if not os.path.isfile(NS3_METRICS):
        return jsonify({"ok": True, "headers": [], "rows": []})
    with open(NS3_METRICS, newline="", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        try:
            headers = next(r)
        except StopIteration:
            headers = []
        rows = [row for row in r]
    return jsonify({"ok": True, "headers": headers, "rows": rows})

# ====== 엔트리 ======
if __name__ == "__main__":
    # 개발용 서버 (운영시: waitress/gunicorn 권장)
    app.run(host="0.0.0.0", port=5055, debug=True)
