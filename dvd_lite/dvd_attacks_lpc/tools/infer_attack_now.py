#!/usr/bin/env python3
import os, json, glob
from pathlib import Path
import pandas as pd, joblib
from datetime import datetime, timezone

BASE=Path(__file__).resolve().parents[1]
BUS=BASE/"bus"
LOG=BUS/"detections.log"
WIN_S=int(os.environ.get("WIN_S","5"))
CONF=float(os.environ.get("CONF_TH","0.6"))
DRY=os.environ.get("DRY_RUN","1")!="0"

# 최신 pcap(압축/비압축 모두) 찾기
pcaps=sorted(BUS.glob("captures/pcap/*/*.pcap*"), key=lambda p:p.stat().st_mtime)
pcap=str(pcaps[-1]) if pcaps else ""

# 최신 SCN 추정
scns=[]
for e in BUS.glob("events_*.csv"): scns.append(e.stem.replace("events_",""))
for e in BUS.glob("dvd_netanim_*_*.xml"): 
    # *_<SCN>.xml
    scns.append(e.stem.split("_")[-1])
scn=sorted(set(scns))[-1] if scns else "unknown"

# 모델/정책
obj=joblib.load(BUS/"models/attack_clf.pkl")
clf=obj
policy=json.loads((BUS/"models/mtd_policy.json").read_text())["policy"]

# 특징은 window_features의 마지막 행 사용(실전이면 스트리밍 윈도 생성 필요)
wf=pd.read_csv(BUS/"window_features.csv")
wf_sc=wf[wf["scn"]==scn].tail(1)
if wf_sc.empty: wf_sc=wf.tail(1)
feat=[c for c in ["pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct",
                  "status_len_mean","param_id_nuniq","atk_pps_mean"] if c in wf_sc.columns]
X=wf_sc[feat].fillna(0.0)

# --- centroid(dict) 모델 가드 + softmax 확률 흉내 ---
proba=None
try:
    if isinstance(clf,dict) and clf.get("type")=="centroid_v1":
        import math
        feats=clf["feats"]; labs=clf["labels"]
        C=clf["centroids"]; S=clf["stdevs"]
        # NOTE: infer 코드에 이미 row(피처 dict)가 준비되어 있음
        x=[float(row.get(f,0.0)) for f in feats]
        scores=[]
        for lab in labs:
            mu=C[lab]; sd=S[lab]
            z=[ (xi-mui)/(sdi if sdi!=0 else 1.0) for xi,mui,sdi in zip(x,mu,sd) ]
            # 음의 L2 거리 = 점수(클수록 좋게)
            scores.append(-math.sqrt(sum(v*v for v in z)))
        # softmax
        m=max(scores) if scores else 0.0
        ex=[math.exp(v-m) for v in scores]
        ssum=sum(ex) or 1.0
        proba=[v/ssum for v in ex]
    else:
        proba=list(clf.predict_proba(X)[0])
except Exception:
    proba=None
# --- end guard ---
labels=clf.classes_.tolist()
idx=int(proba.argmax())
pred,conf=labels[idx],float(proba[idx])
act="none"; args={}
if conf>=CONF and pred in policy:
    act=policy[pred]["action"]; args=policy[pred]["args"]

ts=datetime.now(timezone.utc).isoformat()
with open(LOG,"a") as f:
    f.write(f"{ts},pred={pred},conf={conf:.3f},scn={scn},pcap={pcap},act={act},args={json.dumps(args)}\n")
print(f"[DETECT] pred={pred} conf={conf:.2f} act={act} DRY={DRY} (log:{LOG})")
# DRY 모드가 아니면 즉시 MTD 적용
def run(cmd): os.system(f"bash -lc '{cmd}' >/dev/null 2>&1")
if not DRY:
    if act=="tc_filter":
        run(f"bash modules/mtd/mtd_tc_filter.sh apply gcs mavlink --loss={args.get('loss_pct',1.0)} --delay={args.get('delay_ms',2)} --jitter={args.get('jitter_ms',1)} --dup={args.get('dup_pct',0.0)}")
    elif act=="port_shuffle":
        run("bash modules/mtd/mtd_port_shuffle.sh gcs mavlink")
