#!/usr/bin/env python3
import os, json, re, glob, subprocess, sys
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[0].parent
BUS  = BASE/"bus"
MODELS = BUS/"models"
LOGF = BUS/"detections.log"

WIN_S   = int(os.environ.get("WIN_S", "5"))
DRY     = int(os.environ.get("DRY_RUN", "1")) == 1
CONF_TH = float(os.environ.get("CONF_TH", "0.55"))

def latest(patterns):
    files=[]
    for pat in patterns:
        files += [Path(p) for p in glob.glob(str(pat))]
    if not files: return None
    return max(files, key=lambda p: p.stat().st_mtime)

def parse_xml_name(p:Path):
    # dvd_netanim_<atk>_<lv>_<mtd>_<scn>.xml  (mtd가 True/False인 구버전도 허용)
    m = re.match(r"^dvd_netanim_(.+)_(.+)_(.+)_(.+)\.xml$", p.name)
    if not m: return None
    atk, lv, mtd, scn = m.group(1), m.group(2), m.group(3), m.group(4)
    if mtd.lower() == "true":  mtd = "on"
    if mtd.lower() == "false": mtd = "off"
    return dict(atk=atk, lv=lv, mtd=mtd, scn=scn)

def pick_scn():
    x = latest([BUS/"dvd_netanim_*.xml"])
    if x:
        meta = parse_xml_name(x)
        if meta: return meta["scn"], meta
    # fallback: events_*.csv → scn
    ev = latest([BUS/"events_*.csv"])
    if ev:
        scn = ev.stem.replace("events_","")
        return scn, dict(atk="unknown", lv="unknown", mtd="off", scn=scn)
    return None, None

def load_policy():
    pol = MODELS/"mtd_policy.json"
    if pol.exists():
        with open(pol) as f: return json.load(f)
    # 기본값(없으면 아무 것도 적용 안 함)
    return {"policy":{}}

def find_model_file():
    # 가능한 이름들 중 먼저 발견되는 것 사용
    prefs = ["attack_clf.pkl","clf.pkl","model.pkl","pipeline.pkl"]
    for n in prefs:
        p = MODELS/n
        if p.exists(): return p
    # 그 외 pkl 하나라도
    anyp = list(MODELS.glob("*.pkl"))
    return anyp[0] if anyp else None

def load_model():
    mf = find_model_file()
    if not mf:
        print("[ERR] no model .pkl found in", MODELS, file=sys.stderr)
        sys.exit(2)
    import joblib
    mdl = joblib.load(mf)
    # label encoder/columns 스펙도 있으면 로드
    le = None
    for cand in ["label_encoder.pkl","le.pkl"]:
        cp = MODELS/cand
        if cp.exists():
            try:
                le = joblib.load(cp)
            except Exception:
                pass
    # 학습시 사용한 feature 컬럼 정의가 있으면 사용
    cols_json = MODELS/"feature_columns.json"
    cols = None
    if cols_json.exists():
        try:
            cols = json.loads(cols_json.read_text())
        except Exception:
            cols = None
    return mdl, le, cols

def make_now_features(scn):
    # window_features.csv에서 해당 scn의 윈도 행 뽑아 평균(또는 마지막 윈도) 사용
    wf = BUS/"window_features.csv"
    if not wf.exists():
        raise FileNotFoundError("window_features.csv not found")
    df = pd.read_csv(wf)
    df = df[df["scn"]==scn].copy()
    if df.empty:
        # 최근 1~N 윈도 fallback
        df = pd.read_csv(wf).tail(4).copy()
    # 가능한 공통 수치 컬럼
    candidate = ["pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"]
    use_cols = [c for c in candidate if c in df.columns]
    X = df[use_cols].astype(float)
    # 예측 안정화를 위해 평균 벡터 사용
    x1 = pd.DataFrame([X.mean(numeric_only=True).to_dict()])
    return x1, use_cols

def latest_pcap_for_scn(scn):
    root = BUS/"captures"/"pcap"
    if not root.exists(): return "n/a"
    # bus/captures/pcap/<scn>/*.pcap(.gz)
    d = root/scn
    pats = []
    if d.exists():
        pats += [d/"*.pcap", d/"*.pcap.gz"]
    # fallback: 모든 pcap 중 최신
    if not pats:
        pats = [root/"*/*.pcap", root/"*/*.pcap.gz"]
    p = latest(pats)
    return str(p) if p else "n/a"

def maybe_apply_mtd(action:str, args:dict):
    def run(cmd): subprocess.run(["bash","-lc",cmd], check=False)
    if DRY or action in (None,"none","noop"): return
    if action=="tc_filter":
        loss = args.get("loss_pct",1.0)
        delay= args.get("delay_ms",2)
        jitter=args.get("jitter_ms",1)
        dup   =args.get("dup_pct",0.0)
        run(f"bash modules/mtd/mtd_tc_filter.sh apply gcs mavlink --loss={loss} --delay={delay} --jitter={jitter} --dup={dup}")
    elif action=="port_shuffle":
        run("bash modules/mtd/mtd_port_shuffle.sh gcs mavlink")

def main():
    scn, meta = pick_scn()
    if not scn:
        print("[ERR] no scenario artifacts found (NetAnim XML or events_*.csv).")
        sys.exit(1)

    mdl, le, cols = load_model()
    X, use_cols = make_now_features(scn)

    # 필요 시 컬럼 정렬
    if cols:
        for c in cols:
            if c not in X.columns: X[c]=0.0
        X = X[cols]
    # 예측
    try:
        if hasattr(mdl,"predict_proba"):
            proba = mdl.predict_proba(X)[0]
            classes = getattr(mdl, "classes_", None)
            if classes is None and le is not None:
                classes = le.classes_
        else:
            yhat = mdl.predict(X)[0]
            classes, proba = [yhat], [1.0]
        # top-1
        import numpy as np
        top = int(np.argmax(proba))
        pred_label = classes[top] if isinstance(classes,(list,tuple)) else classes[top]
        conf = float(proba[top]) if len(proba)>top else 0.0
    except Exception as e:
        print("[ERR] prediction failed:", e, file=sys.stderr)
        sys.exit(3)

    if conf < CONF_TH:
        pred = "unknown"; conf = float(conf)
    else:
        pred = str(pred_label)

    # 정책 로딩
    policy = load_policy().get("policy",{})
    act_entry = policy.get(pred, {}) if isinstance(policy,dict) else {}
    action = act_entry.get("action","none")
    args   = act_entry.get("args",{})

    pcap = latest_pcap_for_scn(scn)
    ts = pd.Timestamp.utcnow().isoformat()

    BUS.mkdir(exist_ok=True)
    with open(LOGF, "a") as f:
        f.write(f"{ts},pred={pred},conf={conf:.3f},scn={scn},pcap={pcap},act={action},args={json.dumps(args)}\n")

    maybe_apply_mtd(action, args)

    print(f"[DETECT] pred={pred} conf={conf:.2f} act={action} DRY={DRY} (log:{LOGF})")

if __name__=="__main__":
    main()
