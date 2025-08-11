#!/usr/bin/env python3
import os, subprocess, threading, time, uuid, shlex
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory

APP_DIR = Path(__file__).resolve().parent
ATTACKS_DIR = APP_DIR.parent / "dvd_attacks_lpc"
BUS_LOG = ATTACKS_DIR / "attack_output" / "bus.log"
TOOLS_METRICS = ATTACKS_DIR / "attack_output" / "metrics.csv"

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# ---- background job registry ----
JOBS = {}  # job_id -> Popen

def list_files(dirpath: Path, exts: tuple):
    if not dirpath.exists(): return []
    return sorted([p for p in dirpath.iterdir() if p.is_file() and p.suffix in exts])

def list_modules():
    return sorted((ATTACKS_DIR / "modules").glob("*.sh"))

def list_scenarios():
    return sorted((ATTACKS_DIR / "scenarios").glob("*.pipeline"))

def list_profiles():
    return sorted((ATTACKS_DIR / "scenarios" / "options.d").glob("profile_*.env"))

def list_phases():
    return sorted((ATTACKS_DIR / "scenarios" / "options.d").glob("*.csv"))

def docker_ps_names():
    try:
        out = subprocess.check_output(["bash","-lc","docker ps --format '{{.Names}}'"], text=True, timeout=3)
        return [x.strip() for x in out.splitlines() if x.strip()]
    except Exception:
        return []

def ensure_buslog():
    (ATTACKS_DIR / "attack_output").mkdir(parents=True, exist_ok=True)
    BUS_LOG.touch(exist_ok=True)

def build_env_assign(form):
    # 안전하게 필요한 변수만 픽해서 env로 전달
    keys = [
        "LPC_DUTY","LPC_INTERVAL_MS","LPC_JITTER_PCT","LPC_BACKOFF","LPC_MAX_BUDGET",
        "LPC_STEP","LPC_WINDOW","LPC_SEED","LPC_PROFILE","LPC_PHASE_FILE",
        "DVD_C_GCS","DVD_C_CC","DVD_C_FC"
    ]
    parts = []
    for k in keys:
        v = (form.get(k) or "").strip()
        if v:
            # 인젝션 방지: 공백/quote 최소화, 숫자/문자/_-.:=%만 허용
            safe = "".join([c for c in v if c.isalnum() or c in "._-:=%/"])
            parts.append(f'{k}={shlex.quote(safe)}')
    # 항상 창 비우기 옵션 체크박스 지원
    if form.get("force_now"):
        parts.append('LPC_WINDOW=""')
    return " ".join(parts)

def run_bg(cmd, cwd):
    job_id = str(uuid.uuid4())[:8]
    p = subprocess.Popen(["bash","-lc", cmd], cwd=str(cwd))
    JOBS[job_id] = p
    return job_id

@app.route("/")
def index():
    ensure_buslog()
    return render_template(
        "index.html",
        modules=list_modules(),
        scenarios=list_scenarios(),
        profiles=list_profiles(),
        phases=list_phases(),
        docker_names=docker_ps_names(),
        attacks_dir=str(ATTACKS_DIR),
    )

@app.route("/api/run/module", methods=["POST"])
def api_run_module():
    ensure_buslog()
    mod = request.form.get("module")
    if not mod: return jsonify({"ok":False,"msg":"모듈을 선택하세요"}), 400
    envs = build_env_assign(request.form)
    cmd = f'cd "{ATTACKS_DIR}" && {envs} "{mod}"'
    job_id = run_bg(cmd, ATTACKS_DIR)
    return jsonify({"ok":True, "job_id":job_id, "cmd":cmd})

@app.route("/api/run/scenario", methods=["POST"])
def api_run_scenario():
    ensure_buslog()
    sc = request.form.get("scenario")
    if not sc: return jsonify({"ok":False,"msg":"시나리오를 선택하세요"}), 400
    envs = build_env_assign(request.form)
    cmd = f'cd "{ATTACKS_DIR}" && {envs} ./run_scenario.sh "{sc}"'
    job_id = run_bg(cmd, ATTACKS_DIR)
    return jsonify({"ok":True, "job_id":job_id, "cmd":cmd})

@app.route("/api/run/eval", methods=["POST"])
def api_run_eval():
    ensure_buslog()
    sc = request.form.get("scenario")
    if not sc: return jsonify({"ok":False,"msg":"시나리오를 선택하세요"}), 400
    envs = build_env_assign(request.form)
    cmd = f'cd "{ATTACKS_DIR}" && {envs} ./eval/run_eval.sh "{sc}"'
    job_id = run_bg(cmd, ATTACKS_DIR)
    return jsonify({"ok":True, "job_id":job_id, "cmd":cmd})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    job_id = request.form.get("job_id","").strip()
    p = JOBS.get(job_id)
    if not p: return jsonify({"ok":False,"msg":"존재하지 않는 작업"}), 404
    try:
        p.terminate()
        time.sleep(0.5)
        if p.poll() is None:
            p.kill()
        return jsonify({"ok":True})
    finally:
        JOBS.pop(job_id, None)

@app.route("/api/jobs")
def api_jobs():
    alive = {jid: (p.poll() is None) for jid,p in JOBS.items()}
    return jsonify(alive)

@app.route("/api/logs")
def api_logs():
    ensure_buslog()
    n = int(request.args.get("n","200"))
    try:
        with BUS_LOG.open("r") as f:
            lines = f.readlines()[-n:]
        return jsonify({"ok":True, "lines":[x.rstrip("\n") for x in lines]})
    except Exception as e:
        return jsonify({"ok":False, "msg":str(e)}), 500

@app.route("/api/metrics")
def api_metrics():
    if not TOOLS_METRICS.exists():
        return jsonify({"ok":False, "msg":"metrics.csv 없음 — eval 실행 후 확인"}), 404
    with TOOLS_METRICS.open() as f:
        rows = [line.strip().split(",") for line in f if line.strip()]
    header, data = rows[0], rows[1:]
    return jsonify({"ok":True,"header":header,"data":data})

if __name__ == "__main__":
    # 호스트에서 접근 쉽게 0.0.0.0, 포트 5001
    app.run(host="0.0.0.0", port=5001, debug=False)
