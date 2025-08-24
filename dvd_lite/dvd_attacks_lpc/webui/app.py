#!/usr/bin/env python3
import os, json, subprocess, time
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, render_template, request
from flask_cors import CORS
import pandas as pd

BASE = Path(__file__).resolve().parents[1]  # .../dvd_lite/dvd_attacks_lpc
OUT = BASE / "attack_output"
TOOLS = BASE / "tools"
SCRIPTS = BASE / "scripts"

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# --------- 유틸 ---------
def safe_csv(path, **kwargs):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(p, **kwargs)
    except Exception:
        return pd.DataFrame()

def safe_json(path):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def ensure_outputs():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ["bus.log", "effect_timeline.csv", "ns3_metrics.csv", "score.json", "dataset.csv", "cti_targets.env"]:
        (OUT / f).touch(exist_ok=True)

ensure_outputs()

# --------- 정적/뷰 ---------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename, as_attachment=False)

# --------- API: 간단 메트릭 ---------
@app.route("/api/metrics")
def api_metrics():
    # 파일 유무/크기/갱신시간
    def info(name):
        p = OUT / name
        return {
            "name": name,
            "exists": p.exists(),
            "size": p.stat().st_size if p.exists() else 0,
            "mtime": int(p.stat().st_mtime) if p.exists() else 0
        }
    files = ["bus.log","effect_timeline.csv","ns3_metrics.csv","score.json","dataset.csv","cti_targets.env"]
    return jsonify({"ok": True, "files": [info(f) for f in files]})

# --------- API: CTI ---------
@app.route("/api/cti")
def api_cti():
    env_path = OUT / "cti_targets.env"
    data = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line:
                k,v = line.split("=",1)
                data[k.strip()] = v.strip()
    return jsonify({"ok": True, "cti": data})

# --------- API: bus ---------
@app.route("/api/bus")
def api_bus():
    limit = int(request.args.get("limit", "500"))
    logp = OUT / "bus.log"
    rows = []
    if logp.exists():
        with logp.open("r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]
            for ln in lines:
                ln = ln.strip()
                if not ln: continue
                # epoch_ms \t TAG \t k=v ...
                parts = ln.split("\t")
                epoch = parts[0] if len(parts)>0 else ""
                tag = parts[1] if len(parts)>1 else ""
                meta = parts[2] if len(parts)>2 else ""
                rows.append({"t": epoch, "tag": tag, "meta": meta})
    return jsonify({"ok": True, "rows": rows})

# --------- API: effects ---------
@app.route("/api/effects")
def api_effects():
    df = safe_csv(OUT / "effect_timeline.csv")
    if df.empty:
        return jsonify({"ok": True, "rows": []})
    # 기대 스키마: t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps
    cols = [c for c in df.columns]
    rows = [dict(zip(cols, list(df.iloc[i]))) for i in range(len(df))]
    return jsonify({"ok": True, "rows": rows})

# --------- API: ns3 ---------
@app.route("/api/ns3")
def api_ns3():
    df = safe_csv(OUT / "ns3_metrics.csv")
    if df.empty:
        return jsonify({"ok": True, "rows": []})
    # metric,value,unit 스키마
    rows = []
    for _, r in df.iterrows():
        rows.append({"metric": str(r.get("metric","")), "value": r.get("value", None), "unit": str(r.get("unit",""))})
    return jsonify({"ok": True, "rows": rows})

# --------- API: score ---------
@app.route("/api/score")
def api_score():
    data = safe_json(OUT / "score.json")
    return jsonify({"ok": True, "score": data})

# --------- API: dataset ---------
@app.route("/api/dataset")
def api_dataset():
    limit = int(request.args.get("limit", "50"))
    df = safe_csv(OUT / "dataset.csv")
    if df.empty:
        return jsonify({"ok": True, "cols": [], "rows": []})
    cols = list(df.columns)
    # 끝에서 limit개
    df2 = df.tail(limit)
    rows = [dict(zip(cols, list(df2.iloc[i]))) for i in range(len(df2))]
    return jsonify({"ok": True, "cols": cols, "rows": rows})

# --------- API: 타임라인 리빌드 ---------
@app.route("/api/timeline/rebuild")
def api_rebuild_timeline():
    # bus.log -> effect_timeline.csv
    cmd = [
        "python3", str(TOOLS / "gen_effects_timeline.py"),
        str(OUT / "bus.log"),
        "-o", str(OUT / "effect_timeline.csv"),
        "--rules", str(TOOLS / "effects_rules.json"),
        "--mode", "hold"
    ]
    try:
        subprocess.run(cmd, cwd=str(BASE), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ok = True
        msg = "timeline rebuilt"
    except subprocess.CalledProcessError as e:
        ok = False
        msg = e.stderr.decode(errors="ignore")
    return jsonify({"ok": ok, "msg": msg})

# --------- API: 실행 (stream/collect) ---------
def _spawn_detached(cmd, cwd):
    # 백그라운드로 계속 돌도록 detatch
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=open(OUT / "run.log", "ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )

@app.route("/api/run/stream", methods=["POST"])
def api_run_stream():
    # 무한 라운드: scripts/auto_stream.sh
    cmd = ["bash", str(SCRIPTS / "auto_stream.sh")]
    _spawn_detached(cmd, str(BASE))
    return jsonify({"ok": True, "msg": "auto_stream started"})

@app.route("/api/run/collect", methods=["POST"])
def api_run_collect():
    # 일괄 수집: N, RUN_NS3, ATK_RATE_MBPS, SIM_TIME 등 옵션을 body에서 받음
    body = request.get_json(silent=True) or {}
    env = os.environ.copy()
    for k in ["N","RUN_NS3","ATK_RATE_MBPS","SIM_TIME","PORT_HOP_PROB","FOLLOW_FLOOD_PROB","CTI_WAIT_S"]:
        if k in body:
            env[k] = str(body[k])
    # run.log 초기화
    (OUT / "run.log").write_text("", encoding="utf-8")
    cmd = ["bash", str(SCRIPTS / "auto_collect.sh")]
    _spawn_detached(cmd, str(BASE))
    return jsonify({"ok": True, "msg": "auto_collect started", "env": {k: env.get(k) for k in ["N","RUN_NS3","ATK_RATE_MBPS","SIM_TIME"]}})

# --------- API: run.log tail ---------
@app.route("/api/runlog")
def api_runlog():
    p = OUT / "run.log"
    text = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    # 뒤에서 400줄만
    lines = text.splitlines()[-400:]
    return jsonify({"ok": True, "lines": lines})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
