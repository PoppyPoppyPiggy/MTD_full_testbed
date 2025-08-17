#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/scripts/pipeline.sh
# Flow: (opt)attack -> timeline(with --rules) -> ns3 eval -> windowing -> unify -> train
set -euo pipefail

# ── 반드시 먼저: source 00_env.sh 로 MTD_ROOT/LPC_ROOT/LPC_LOG_DIR/NS3/NS3_BIN/NS3_SCRATCH 설정 ──
: "${LPC_ROOT:?source 00_env.sh 먼저 실행하세요}"
: "${LPC_LOG_DIR:?source 00_env.sh 먼저 실행하세요}"

cd "$LPC_ROOT"

# ===== User-tunable =====
RUN_ATTACK="${RUN_ATTACK:-0}"                 # 1이면 scripts/lpc_run.sh 실행
SCENARIO="${SCENARIO:-scenarios/S_lpc_v2.pipeline}"

EFFECTS_RULES="${EFFECTS_RULES:-tools/effects_rules.json}"

WIN="${WIN:-5}"                               # window length (sec)
STRIDE="${STRIDE:-1}"                         # window stride (sec)
BLIND="${BLIND:-2}"                           # event ±BLIND sec drop

SIM_TIME="${SIM_TIME:-60}"                    # ns-3 sim seconds
PKT_SIZE="${PKT_SIZE:-512}"                   # UDP payload bytes
ANIM_OUT="${ANIM_OUT:-}"                      # 비우면 미사용

PY="${PYTHON:-python3}"

ATT_OUT="$LPC_LOG_DIR"
TOOLS_DIR="$LPC_ROOT/tools"
ML_DIR="$LPC_ROOT/ml"

echo "==[0/6] sanity checks =="
mkdir -p "$ATT_OUT" "../../supervised_data"
command -v "$PY" >/dev/null || { echo "[ERR] python3 not found"; exit 2; }
[[ -f "$EFFECTS_RULES" ]] || { echo "[ERR] effects_rules.json not found: $EFFECTS_RULES"; exit 2; }

# ------------------------------------------------------------------------------------
# [1] (선택) 공격 실행 (주의: lpc_run.sh 내에서 타임라인 생성 금지!)
# ------------------------------------------------------------------------------------
if [[ "$RUN_ATTACK" == "1" ]]; then
  echo "==[1/6] run attack scenario =="
  if [[ -x "./scripts/lpc_run.sh" ]]; then
    bash ./scripts/lpc_run.sh "$SCENARIO" || true
  else
    echo "[WARN] scripts/lpc_run.sh 없음. 공격 실행 스킵." >&2
  fi
else
  echo "==[1/6] skip attack run (set RUN_ATTACK=1 to enable) =="
fi

# ------------------------------------------------------------------------------------
# [2] bus.log -> effect_timeline.csv (항상 --rules 전달, placeholder/구버전이면 재생성)
# ------------------------------------------------------------------------------------
echo "==[2/6] bus.log -> effect_timeline.csv =="
BUS="$ATT_OUT/bus.log"
TL="$ATT_OUT/effect_timeline.csv"

need_regen=false
if [[ ! -s "$TL" ]]; then
  need_regen=true
elif grep -q ',waiting,low$' "$TL" 2>/dev/null; then
  need_regen=true
elif [[ -s "$BUS" && "$BUS" -nt "$TL" ]]; then
  need_regen=true
fi

if $need_regen; then
  if [[ -s "$BUS" ]]; then
    echo "[*] generating effect_timeline with rules: $EFFECTS_RULES"
    "$PY" "$TOOLS_DIR/gen_effects_timeline.py" "$BUS" -o "$TL" --rules "$EFFECTS_RULES"
  else
    echo "[WARN] $BUS 없음/빈 파일. 타임라인 생략." >&2
  fi
else
  echo "[OK] effect_timeline.csv up-to-date ($TL)"
fi

# ------------------------------------------------------------------------------------
# [2.5] ns-3 평가 (./ns3 런처, waf 미사용)
# ------------------------------------------------------------------------------------
echo "==[2.5/6] ns-3 eval (effect_timeline -> ns3_metrics.csv) =="
NS3_OUT="$ATT_OUT/ns3_metrics.csv"
if [[ -s "$TL" ]]; then
  bash ./scripts/run_ns3_eval.sh "$TL" "$NS3_OUT" "$SIM_TIME" "$PKT_SIZE" "$ANIM_OUT" || {
    echo "[WARN] ns-3 평가 실패. 나중에 합성 fallback 사용." >&2
  }
else
  echo "[WARN] effect_timeline.csv 없음 → ns-3 평가 스킵"
fi

# ns-3 결과 품질검증: 너무 짧으면 타임라인 기반으로 합성
if [[ -s "$NS3_OUT" ]]; then
  NS3_LINES=$(wc -l < "$NS3_OUT" || echo 0)
  if [[ "$NS3_LINES" -lt 5 ]]; then
    echo "[WARN] ns3_metrics.csv too small ($NS3_LINES lines). Synthesizing from timeline."
    "$PY" - "$TL" "$NS3_OUT" <<'PYSYN'
import sys, pandas as pd, np as _np
tl_path, out_path = sys.argv[1], sys.argv[2]
tl = pd.read_csv(tl_path).sort_values("t")
for c in ["rate_limit_mbps","loss_pct","delay_ms","jitter_ms","dup_pct"]:
    if c not in tl.columns: tl[c]=_np.nan
t0,t1 = float(tl["t"].min()), float(tl["t"].max())
grid = pd.DataFrame({"t": _np.arange(_np.floor(t0), _np.ceil(t1)+1, 1.0)})
tlff = pd.merge_asof(grid, tl[["t","rate_limit_mbps","loss_pct","delay_ms","jitter_ms","dup_pct"]].sort_values("t"),
                     on="t", direction="backward")
base=10.0
thr = tlff["rate_limit_mbps"].fillna(base) * (1.0 - tlff["loss_pct"].fillna(0.0)/100.0)
out = pd.DataFrame({
    "t": tlff["t"],
    "throughput_mbps": thr,
    "delay_ms": tlff["delay_ms"],
    "jitter_ms": tlff["jitter_ms"],
    "loss_pct": tlff["loss_pct"],
    "dup_pct": tlff["dup_pct"],
})
out.to_csv(out_path, index=False)
print(f"[OK] synthesized ns3_metrics -> {out_path} rows={len(out)}")
PYSYN
  fi
fi

# ------------------------------------------------------------------------------------
# [3] 윈도우링: 타임라인 기반(안정 CLI) → 구버전 CLI → ns3 fallback
# ------------------------------------------------------------------------------------
echo "==[3/6] effect_timeline.csv -> window_features.csv (or synthesize) =="
WF="$ATT_OUT/window_features.csv"
ABS_TL="$(realpath -m "$TL")"
ABS_WF="$(realpath -m "$WF")"
ABS_NS3="$(realpath -m "$NS3_OUT")"

if [[ -s "$WF" ]]; then
  echo "[OK] window_features.csv already exists ($WF)"
else
  # 3-1) 안정 CLI 우선
  if [[ -f "$TOOLS_DIR/lpc_metrics_cli.py" && -s "$TL" ]]; then
    set +e
    "$PY" "$TOOLS_DIR/lpc_metrics_cli.py" "$ABS_TL" -o "$ABS_WF" --win "$WIN" --stride "$STRIDE"
    RC=$?; set -e
    if [[ $RC -ne 0 || ! -s "$WF" ]]; then
      echo "[WARN] lpc_metrics_cli.py 실패/산출물 없음. 기존 lpc_metrics.py 시도." >&2
    fi
  fi

  # 3-2) 구버전 도구(절대경로 전달)
  if [[ ! -s "$WF" && -f "$TOOLS_DIR/lpc_metrics.py" && -s "$TL" ]]; then
    set +e
    "$PY" "$TOOLS_DIR/lpc_metrics.py" "$ABS_TL" -o "$ABS_WF" --win "$WIN" --stride "$STRIDE"
    RC=$?; set -e
    if [[ $RC -ne 0 || ! -s "$WF" ]]; then
      echo "[WARN] lpc_metrics.py 실패/산출물 없음. ns3_metrics 기반 합성으로 전환." >&2
    fi
  fi

  # 3-3) ns3_metrics 기반 합성
  if [[ ! -s "$WF" ]]; then
    if [[ -s "$NS3_OUT" ]]; then
      echo "[INFO] Synthesizing window_features.csv from ns3_metrics.csv (win=$WIN stride=$STRIDE)"
      "$PY" - "$ABS_NS3" "$ABS_WF" "$WIN" "$STRIDE" <<'PYGEN'
import sys, pandas as pd, numpy as np
ns3_path, out_path, WIN, STRIDE = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
df = pd.read_csv(ns3_path); df.columns=[c.strip().lower() for c in df.columns]
for c in ["t","time","ts","timestamp","start_t"]:
    if c in df.columns:
        df[c]=pd.to_numeric(df[c], errors="coerce"); df=df.dropna(subset=[c]).sort_values(c); tcol=c; break
else:
    df["t"]=np.arange(len(df), dtype=float); tcol="t"
t=df[tcol].to_numpy(float); t0,t1=float(np.min(t)),float(np.max(t))
rows=[]; cur=t0
def col(name, alts):
    for a in [name]+alts:
        if a in df.columns: return a
    return None
cols={"throughput":col("throughput_mbps",["rate","tx_rate","throughput"]),
      "delay":col("delay_ms",["delay","latency","rtt"]),
      "jitter":col("jitter_ms",["jitter"]),
      "loss":col("loss_pct",["loss","packet_loss","loss_rate"]),
      "dup":col("dup_pct",["dup","duplicates"])}
while cur<=t1:
    nxt=cur+WIN; w=df[(df[tcol]>=cur)&(df[tcol]<nxt)]
    if len(w)>0:
        rows.append({"start_t":cur,"end_t":nxt,
                     "rate_mean":float(np.nanmean(pd.to_numeric(w.get(cols["throughput"]),errors="coerce"))) if cols["throughput"] else np.nan,
                     "delay_mean":float(np.nanmean(pd.to_numeric(w.get(cols["delay"]),errors="coerce"))) if cols["delay"] else np.nan,
                     "jitter_mean":float(np.nanmean(pd.to_numeric(w.get(cols["jitter"]),errors="coerce"))) if cols["jitter"] else np.nan,
                     "loss_mean":float(np.nanmean(pd.to_numeric(w.get(cols["loss"]),errors="coerce"))) if cols["loss"] else np.nan,
                     "dup_mean":float(np.nanmean(pd.to_numeric(w.get(cols["dup"]),errors="coerce"))) if cols["dup"] else np.nan})
    cur+=STRIDE
pd.DataFrame(rows).to_csv(out_path, index=False)
print(f"[OK] synthesized window_features -> {out_path} rows={len(rows)}")
PYGEN
    else
      echo "[ERR] 윈도우 생성 불가(ns3_metrics 없음)." >&2; exit 2
    fi
  fi
fi

# ------------------------------------------------------------------------------------
# [4] unified_dataset 생성
# ------------------------------------------------------------------------------------
echo "==[4/6] build unified dataset =="
"$PY" "$ML_DIR/build_supervised.py" \
  --attack-output "$ATT_OUT" \
  --outdir "../../supervised_data" \
  --default-win "$WIN" \
  --blind "$BLIND"

DATA_PARQ="../../supervised_data/unified_dataset.parquet"
DATA_CSV="../../supervised_data/unified_dataset.csv"
DATA=""
[[ -s "$DATA_PARQ" ]] && DATA="$DATA_PARQ"
[[ -z "$DATA" && -s "$DATA_CSV" ]] && DATA="$DATA_CSV"
[[ -z "$DATA" ]] && { echo "[ERR] unified_dataset 생성 실패."; exit 2; }

# ------------------------------------------------------------------------------------
# [5] 학습 (행수 기반 folds 자동)
# ------------------------------------------------------------------------------------
echo "==[5/6] train baseline (auto folds) =="
N=$("$PY" - <<PYCNT
import pandas as pd, sys
p="$DATA"; df=pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p); print(len(df))
PYCNT
)
if [[ "$N" -lt 3 ]]; then
  echo "[WARN] too few rows (N=$N). Skipping training. Increase windows (SIM_TIME↑/WIN↓/STRIDE↓)." >&2
  exit 0
fi
FOLDS=$("$PY" - <<PYF
N=int("$N"); print(min(5, max(2, N-1)))
PYF
)
if [[ -x "$ML_DIR/train_baseline.py" ]]; then
  "$PY" "$ML_DIR/train_baseline.py" --data "$DATA" --folds "$FOLDS"
else
  "$PY" - "$DATA" "$FOLDS" <<'PYTRAIN'
import sys, numpy as np, pandas as pd
from pathlib import Path
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, average_precision_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
data_path, folds = Path(sys.argv[1]), int(sys.argv[2])
df = pd.read_parquet(data_path) if data_path.suffix==".parquet" else pd.read_csv(data_path)
assert "module" in df.columns, "dataset must include 'module'"
Xdf = df.select_dtypes(include=[float,int]).drop(columns=[c for c in df.columns if c.startswith("end_t")], errors="ignore")
X = Xdf.to_numpy()
col_means = np.nanmean(X, axis=0); inds = np.where(np.isnan(X))
if X.size>0 and len(inds[0])>0: X[inds] = np.take(col_means, inds[1])
y = df["module"].astype("category").cat.codes.to_numpy()
classes = df["module"].astype("category").cat.categories.tolist()
if "start_t" in df.columns:
    order = np.argsort(df["start_t"].to_numpy()); X, y = X[order], y[order]
models = {
    "logreg": Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=200, class_weight="balanced"))]),
    "rf": Pipeline([("clf", RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=42))])
}
tscv = TimeSeriesSplit(n_splits=folds)
for name, pipe in models.items():
    print(f"\n=== {name.upper()} (folds={folds}) ===")
    pr_aucs=[]
    for fold,(tr,te) in enumerate(tscv.split(X),1):
        pipe.fit(X[tr], y[tr]); yhat=pipe.predict(X[te])
        print(f"[Fold {fold}]"); print(classification_report(y[te], yhat, target_names=classes, digits=3))
        if hasattr(pipe, "predict_proba"):
            P = pipe.predict_proba(X[te])
            ap=[average_precision_score((y[te]==k).astype(int), P[:,k]) for k in range(len(classes))]
            pr_aucs.append(np.mean(ap))
    if pr_aucs: print(f"Mean macro PR AUC: {np.mean(pr_aucs):.3f}")
PYTRAIN
fi

echo "==[6/6] done =="
echo "Outputs:"
echo " - ../../supervised_data/unified_dataset.parquet (or .csv)"
echo " - ../../supervised_data/label_stats.json (if exists)"
