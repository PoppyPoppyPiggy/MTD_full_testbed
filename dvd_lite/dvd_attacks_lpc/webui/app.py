#!/usr/bin/env python3
import os, json, csv, subprocess, shlex, time
from pathlib import Path
from flask import Flask, render_template, jsonify, request

APP_DIR = Path(__file__).resolve().parent
ROOT    = APP_DIR.parent  # dvd_lite/dvd_attacks_lpc
OUT     = ROOT / "attack_output"
TOOLS   = ROOT / "tools"
SCRIPTS = ROOT / "scripts"

BUS_PATH   = OUT / "bus.log"
TL_PATH    = OUT / "effect_timeline.csv"
NS3_PATH   = OUT / "ns3_metrics.csv"
SCORE_PATH = OUT / "score.json"
DS_PATH    = OUT / "dataset.csv"

app = Flask(__name__, template_folder=str(APP_DIR/"templates"), static_folder=str(APP_DIR/"static"))

def _file_mtime(p: Path):
    return time.strftime("%F %T", time.localtime(p.stat().st_mtime)) if p.exists() else "-"

def read_bus(limit=1000):
    if not BUS_PATH.exists(): return {"rows":[], "mtime":"-"}
    rows=[]
    with BUS_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line=line.rstrip("\n")
            if not line: continue
            parts=line.split("\t", 2)
            if len(parts)<3: continue
            ts, tag, rest = parts
            rows.append({"ts": float(ts), "tag": tag, "kv": rest})
    rows = rows[-limit:]
    return {"rows": rows, "mtime": _file_mtime(BUS_PATH)}

def read_timeline():
    if not TL_PATH.exists():
        return {"t":[], "loss_pct":[], "delay_ms":[], "jitter_ms":[], "dup_pct":[], "rate_limit_mbps":[], "mtime":"-"}
    t=[]; loss=[]; delay=[]; jitter=[]; dup=[]; rlm=[]
    with TL_PATH.open(newline="") as f:
        r=csv.DictReader(f)
        for i,row in enumerate(r):
            try:
                t.append(float(row.get("t","0") or 0))
                loss.append(float(row.get("loss_pct","0") or 0))
                delay.append(float(row.get("delay_ms","0") or 0))
                jitter.append(float(row.get("jitter_ms","0") or 0))
                dup.append(float(row.get("dup_pct","0") or 0))
                rlm.append(float(row.get("rate_limit_mbps","0") or 0))
            except: 
                continue
    # downsample(너무 길면 1,000 포인트로 축소)
    n=len(t)
    if n>1000:
        step = max(1, n//1000)
        t=t[::step]; loss=loss[::step]; delay=delay[::step]; jitter=jitter[::step]; dup=dup[::step]; rlm=rlm[::step]
    return {"t":t,"loss_pct":loss,"delay_ms":delay,"jitter_ms":jitter,"dup_pct":dup,"rate_limit_mbps":rlm,"mtime":_file_mtime(TL_PATH)}

def read_ns3():
    if not NS3_PATH.exists():
        return {"metrics":{}, "mtime":"-"}
    metrics={}
    with NS3_PATH.open(newline="") as f:
        r=csv.reader(f); header=next(r, None)
        for row in r:
            if not row: continue
            k=row[0].strip()
            v=row[1].strip() if len(row)>1 else ""
            try: metrics[k]=float(v)
            except: metrics[k]=v
    return {"metrics":metrics, "mtime":_file_mtime(NS3_PATH)}

def read_score():
    if not SCORE_PATH.exists():
        return {"score":{}, "mtime":"-"}
    try:
        score=json.loads(SCORE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        score={"error":str(e)}
    return {"score":score, "mtime":_file_mtime(SCORE_PATH)}

def read_dataset(limit=50):
    if not DS_PATH.exists():
        return {"header":[], "rows":[], "mtime":"-"}
    out=[]
    with DS_PATH.open(newline="") as f:
        r=csv.reader(f)
        header=next(r, [])
        for i,row in enumerate(r):
            out.append(row)
    return {"header":header, "rows":out[:limit], "mtime":_file_mtime(DS_PATH), "count":len(out)}

@app.route("/")
def index():
    return render_template("index.html",
                           bus_mtime=_file_mtime(BUS_PATH),
                           tl_mtime=_file_mtime(TL_PATH),
                           ns3_mtime=_file_mtime(NS3_PATH),
                           score_mtime=_file_mtime(SCORE_PATH),
                           ds_mtime=_file_mtime(DS_PATH))

@app.get("/api/bus")
def api_bus():
    limit=int(request.args.get("limit", 500))
    return jsonify(read_bus(limit))

@app.get("/api/effects")
def api_effects():
    return jsonify(read_timeline())

@app.get("/api/ns3")
def api_ns3():
    return jsonify(read_ns3())

@app.get("/api/score")
def api_score():
    return jsonify(read_score())

@app.get("/api/dataset")
def api_dataset():
    limit=int(request.args.get("limit", 50))
    return jsonify(read_dataset(limit))

@app.post("/api/run")
def api_run():
    """
    배치 수집/학습 원클릭 (비동기 실행)
    body 예: {"N": 50, "RUN_NS3": 1, "ATK_RATE_MBPS": 30}
    """
    data = request.get_json(force=True, silent=True) or {}
    env = os.environ.copy()
    # 기본값
    env["N"] = str(data.get("N", 30))
    env["RUN_NS3"] = "1" if str(data.get("RUN_NS3", 1)) in ("1","true","True") else "0"
    if "ATK_RATE_MBPS" in data: env["ATK_RATE_MBPS"]=str(data["ATK_RATE_MBPS"])
    if "PORT_HOP_PROB" in data: env["PORT_HOP_PROB"]=str(data["PORT_HOP_PROB"])
    if "FOLLOW_FLOOD_PROB" in data: env["FOLLOW_FLOOD_PROB"]=str(data["FOLLOW_FLOOD_PROB"])
    if "CTI_WAIT_S" in data: env["CTI_WAIT_S"]=str(data["CTI_WAIT_S"])

    script = str(SCRIPTS/"auto_collect.sh")
    if not Path(script).exists():
        return jsonify({"ok":False,"error":"scripts/auto_collect.sh not found"}), 404

    # 비동기 시작
    logf = OUT / "webui_task.log"
    with logf.open("ab") as lf:
        proc = subprocess.Popen(["bash", script], cwd=str(ROOT), env=env, stdout=lf, stderr=lf)
    (OUT/"webui_task.pid").write_text(str(proc.pid))
    return jsonify({"ok":True, "pid":proc.pid, "log":str(logf)})

@app.post("/api/kill")
def api_kill():
    pid_file = OUT/"webui_task.pid"
    if not pid_file.exists():
        return jsonify({"ok":False,"error":"no running pid file"}), 404
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 15)  # SIGTERM
        return jsonify({"ok":True,"killed":pid})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
