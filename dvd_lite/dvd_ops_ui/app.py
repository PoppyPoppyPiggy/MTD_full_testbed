#!/usr/bin/env python3
import os, subprocess, threading, time, json, shlex
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent  # dvd_lite
ATTACKS_DIR = ROOT / "dvd_attacks_lpc"

# DVD 컨테이너 롤 추론용 (이름에 포함되면 매칭)
ROLE_HINTS = {
    "ground-control-station": "GCS",
    "companion-computer": "Companion",
    "flight-controller": "FC",
    "simulator": "Simulator",
    "qgc": "GCS",
    "mavproxy": "GCS",
}

# 모니터링 대상 자동 감지 필터(환경변수로 오버라이드 가능)
DEFAULT_FILTER_SUBSTR = os.environ.get("DVD_NAME_FILTER", "damn-vulnerable-drone")
# 예: docker ps --format '{{json .}}' 사용
PS_FORMAT = "{{json .}}"
STATS_FORMAT = "{{json .}}"

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# ---- docker events 백그라운드 수집 ----
_events_lock = threading.Lock()
_events_buf = []  # 최근 이벤트 1000개
_events_proc = None

def _events_loop():
    global _events_proc
    cmd = "docker events --format '{{json .}}'"
    _events_proc = subprocess.Popen(["bash","-lc",cmd], stdout=subprocess.PIPE, text=True, bufsize=1)
    for line in _events_proc.stdout:
        line = line.strip()
        if not line: continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        with _events_lock:
            _events_buf.append(evt)
            if len(_events_buf) > 1000:
                _events_buf[:] = _events_buf[-1000:]

def start_events_thread():
    t = threading.Thread(target=_events_loop, daemon=True)
    t.start()

# ---- 유틸 ----
def _run(cmd, timeout=5, cwd=None):
    return subprocess.check_output(["bash","-lc",cmd], text=True, timeout=timeout, cwd=cwd)

def _list_containers(all_=True):
    flag = "-a" if all_ else ""
    out = _run(f"docker ps {flag} --format '{PS_FORMAT}' || true", timeout=3)
    items = []
    for ln in out.splitlines():
        try:
            obj = json.loads(ln)
            # 필터: 이름/이미지에 키워드 포함 시
            name = obj.get("Names","")
            image = obj.get("Image","")
            if (DEFAULT_FILTER_SUBSTR and (DEFAULT_FILTER_SUBSTR in name or DEFAULT_FILTER_SUBSTR in image)) or \
               any(hint in name for hint in ROLE_HINTS):
                # 롤 매핑
                role = None
                for k,v in ROLE_HINTS.items():
                    if k in name:
                        role = v; break
                obj["Role"] = role or ""
                items.append(obj)
        except Exception:
            continue
    return items

def _stats_one(name):
    # docker stats --no-stream --format '{{json .}}' <name>
    out = _run(f"docker stats --no-stream --format '{STATS_FORMAT}' {shlex.quote(name)} || true", timeout=4)
    for ln in out.splitlines():
        try:
            obj = json.loads(ln); return obj
        except: pass
    return {}

def _inspect(name):
    out = _run(f"docker inspect {shlex.quote(name)} || true", timeout=5)
    try:
        return json.loads(out)[0]
    except Exception:
        return {}

def _logs(name, n=200):
    return _run(f"docker logs --tail {int(n)} {shlex.quote(name)} 2>&1 || true", timeout=5)

# ---- 라우트 ----
@app.route("/")
def index():
    # DVD 운영 가정 설명(네트/포트 등): README 기반
    dvd_notes = {
        "infra_cidr": "10.13.0.0/24",
        "sim_ip": "10.13.0.5",
        "wifi_cidr": "192.168.13.0/24",
        "sim_ui": "http://localhost:8000",
    }
    return render_template("index.html", dvd_notes=dvd_notes, filter_keyword=DEFAULT_FILTER_SUBSTR)

@app.route("/api/containers")
def api_containers():
    return jsonify(_list_containers(all_=True))

@app.route("/api/container/<name>/stats")
def api_stats(name):
    return jsonify(_stats_one(name))

@app.route("/api/container/<name>/inspect")
def api_inspect(name):
    return jsonify(_inspect(name))

@app.route("/api/container/<name>/logs")
def api_logs(name):
    n = int(request.args.get("n","200"))
    return jsonify({"name": name, "lines": _logs(name, n).splitlines()})

@app.route("/api/events")
def api_events():
    limit = int(request.args.get("limit","200"))
    with _events_lock:
        ev = list(_events_buf[-limit:])
    return jsonify(ev)

@app.route("/api/kill/<name>", methods=["POST"])
def api_kill(name):
    try:
        _run(f"docker kill {shlex.quote(name)}", timeout=5)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    start_events_thread()
    app.run(host="0.0.0.0", port=5002, debug=False)
