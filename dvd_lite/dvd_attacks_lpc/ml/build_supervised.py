#!/usr/bin/env python3
"""
dvd_lite/dvd_attacks_lpc/ml/build_supervised.py  (robust time inference)

attack_output 아래 파일들을 윈도우 기준으로 합쳐서 지도학습 테이블을 만든다.
- REQUIRED: attack_output/window_features.csv
- RECOMMENDED: attack_output/effect_timeline.csv (라벨링)
- OPTIONAL: attack_output/ns3_metrics.csv, attack_output/bus.log

결과물:
- supervised_data/unified_dataset.parquet (or CSV)
- supervised_data/label_stats.json
"""

from pathlib import Path
import argparse, json, sys, time
import numpy as np, pandas as pd

# ---------- I/O helpers ----------
def read_required_csv(p: Path):
    if not p.exists():
        print(f"[ERR] missing required: {p}", file=sys.stderr)
        sys.exit(2)
    return pd.read_csv(p)

def read_optional_csv(p: Path):
    if not p.exists():
        print(f"[WARN] missing optional: {p}", file=sys.stderr)
        return None
    try:
        return pd.read_csv(p)
    except Exception as e:
        print(f"[WARN] failed to read {p}: {e}", file=sys.stderr)
        return None

def normalize_cols(df: pd.DataFrame):
    d = df.copy()
    d.columns = [c.strip().lower() for c in d.columns]
    return d

def to_epoch_seconds(series: pd.Series):
    """Accept numeric epoch or parse datetimes -> epoch seconds."""
    s = pd.to_datetime(series, errors="coerce", utc=True)
    if s.notna().any():
        return s.view("int64") / 1e9  # ns -> s
    # if already numeric
    return pd.to_numeric(series, errors="coerce")

def coerce_times(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ---------- window time inference ----------
START_CANDIDATES = [
    "start_t","window_start","win_start","start","t_start","ts","t","time","stime"
]
END_CANDIDATES = [
    "end_t","window_end","win_end","end","t_end","te","etime"
]
IDX_CANDIDATES = ["idx","win_idx","window_id","id","row","index"]

def pick_col(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def ensure_window_bounds(wf: pd.DataFrame, default_win: float):
    wf = wf.copy()

    # 1) try known start/end names
    s_col = pick_col(wf, START_CANDIDATES)
    e_col = pick_col(wf, END_CANDIDATES)

    # 2) parse to epoch if needed (handle ISO strings)
    if s_col is not None:
        try_as_time = to_epoch_seconds(wf[s_col])
        if try_as_time.notna().sum() >= max(1, int(0.5*len(wf))):
            wf["start_t"] = try_as_time
        else:
            wf["start_t"] = pd.to_numeric(wf[s_col], errors="coerce")
    if e_col is not None:
        try_as_time = to_epoch_seconds(wf[e_col])
        if try_as_time.notna().sum() >= max(1, int(0.5*len(wf))):
            wf["end_t"] = try_as_time
        else:
            wf["end_t"] = pd.to_numeric(wf[e_col], errors="coerce")

    # 3) if only center time 't' exists, treat as start_t
    if "start_t" not in wf.columns and "t" in wf.columns:
        wf["start_t"] = pd.to_numeric(wf["t"], errors="coerce")

    # 4) if still missing start_t, try index-based synthesis
    if "start_t" not in wf.columns or wf["start_t"].isna().all():
        idx_col = pick_col(wf, IDX_CANDIDATES)
        if idx_col and pd.to_numeric(wf[idx_col], errors="coerce").notna().any():
            base = pd.to_numeric(wf[idx_col], errors="coerce").fillna(0).astype(float)
            base = base - np.nanmin(base)
            wf["start_t"] = base * float(default_win)
            print(f"[INFO] synthesized start_t from {idx_col} * {default_win}s", file=sys.stderr)
        else:
            # last resort: use row index
            base = np.arange(len(wf), dtype=float)
            wf["start_t"] = base * float(default_win)
            print(f"[INFO] synthesized start_t from row_index * {default_win}s", file=sys.stderr)

    # 5) if end_t missing, infer from start_t + default_win
    if "end_t" not in wf.columns or wf["end_t"].isna().all():
        wf["end_t"] = wf["start_t"] + float(default_win)

    # clean
    wf = wf.dropna(subset=["start_t","end_t"]).sort_values("start_t").reset_index(drop=True)
    return wf

# ---------- joining & labeling ----------
def interval_join(base, other, tcol="t"):
    if other is None:
        return base
    other = other.copy()
    other.columns = [c.strip().lower() for c in other.columns]

    # pick a time column for 'other'
    t_candidates = [tcol, "time", "ts", "timestamp", "event_t", "evt_t", "start_t"]
    t_pick = pick_col(other, t_candidates)
    if t_pick is None:
        return base
    other[t_pick] = pd.to_numeric(other[t_pick], errors="coerce")
    other = other.dropna(subset=[t_pick]).sort_values(t_pick)

    # map each other-row to window index: start_t <= t < next_start_t
    idx = np.searchsorted(base["start_t"].to_numpy(), other[t_pick].to_numpy(), side="right") - 1
    mask = (idx>=0) & (idx < len(base))
    other = other.loc[mask].copy()
    other["__widx"] = idx[mask]

    agg = other.groupby("__widx").agg(["mean","std","min","max"]).reset_index()
    agg.columns = ["__widx"] + [f"{c}_{stat}" for c,stat in agg.columns if c!="__widx"]
    base = base.reset_index(drop=True)
    return base.join(agg.set_index("__widx"), how="left")

def label_windows(wf: pd.DataFrame, timeline: pd.DataFrame, blind_zone: float):
    if timeline is None:
        print("[WARN] No timeline: using 'module' from window_features if present.", file=sys.stderr)
        if "module" in wf.columns:
            return wf
        wf["module"] = "normal"
        return wf

    tl = normalize_cols(timeline)
    # detect event time representation
    # 1) interval [start,end]
    s = pick_col(tl, ["start_t","start","win_start","t_start","ts"])
    e = pick_col(tl, ["end_t","end","win_end","t_end","te"])
    # 2) point t
    tp = pick_col(tl, ["t","time","ts","timestamp","event_t","evt_t"])

    # ensure a module/category column
    if "module" not in tl.columns:
        for alt in ["attack_module","mod","name","label","class"]:
            if alt in tl.columns:
                tl["module"] = tl[alt]
                break
    if "module" not in tl.columns:
        tl["module"] = "unknown"

    base = wf.copy()

    if s and e:
        # interval labeling: mark windows overlapping [s,e]
        tl[s] = pd.to_numeric(tl[s], errors="coerce")
        tl[e] = pd.to_numeric(tl[e], errors="coerce")
        tl = tl.dropna(subset=[s,e]).sort_values(s)
        base["module"] = "normal"
        for _, row in tl.iterrows():
            ov = (base["start_t"] < float(row[e])) & (base["end_t"] > float(row[s]))
            base.loc[ov, "module"] = row["module"]
        # blind zone around s/e if requested
        if blind_zone and blind_zone > 0:
            for _, row in tl.iterrows():
                st, en = float(row[s]), float(row[e])
                base = base[~(((base["start_t"] >= st - blind_zone) & (base["start_t"] <= st + blind_zone)) |
                              ((base["start_t"] >= en - blind_zone) & (base["start_t"] <= en + blind_zone)))]
        base = base.reset_index(drop=True)
        return base

    # point labeling
    if tp:
        tl[tp] = pd.to_numeric(tl[tp], errors="coerce")
        tl = tl.dropna(subset=[tp]).sort_values(tp)
        idx = np.searchsorted(base["start_t"].to_numpy(), tl[tp].to_numpy(), side="right") - 1
        ok = (idx>=0) & (idx < len(base))
        tl = tl.loc[ok].copy()
        tl["__widx"] = idx[ok]
        # last event in the window wins
        win_lab = tl.groupby("__widx")["module"].agg(lambda x: list(x)[-1]).to_dict()
        base["module"] = base.index.map(lambda i: win_lab.get(i, "normal"))

        if blind_zone and blind_zone > 0:
            et = tl.groupby("__widx")[tp].first()
            base["__keep"] = True
            for widx, evt_t in et.items():
                base.loc[
                    (base["start_t"] >= evt_t - blind_zone) &
                    (base["start_t"] <= evt_t + blind_zone),
                    "__keep"
                ] = False
            base = base[base["__keep"]].drop(columns="__keep")
        return base

    # no recognizable time in timeline; fall back
    print("[WARN] timeline has no recognizable time columns; using module if any, else 'normal'.", file=sys.stderr)
    if "module" in tl.columns and "module" not in wf.columns:
        # no way to align by time; just mark all as unknown/normal
        wf = wf.copy(); wf["module"] = "unknown"
        return wf
    return wf

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attack-output", type=str, default="../attack_output")
    ap.add_argument("--outdir", type=str, default="../../supervised_data")
    ap.add_argument("--default-win", type=float, default=5.0, help="used if end_t absent OR no time columns at all")
    ap.add_argument("--blind", type=float, default=2.0, help="seconds to drop around events")
    args = ap.parse_args()

    ao = Path(args.attack_output)
    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)

    wf  = read_required_csv(ao/"window_features.csv")
    wf  = normalize_cols(wf)
    wf  = ensure_window_bounds(wf, args.default_win)

    tl  = read_optional_csv(ao/"effect_timeline.csv")
    ns3 = read_optional_csv(ao/"ns3_metrics.csv")
    bus = read_optional_csv(ao/"bus.log")

    # 라벨링
    labeled = label_windows(wf, tl, blind_zone=args.blind)

    # 보조 피처 조인(ns3, bus) — 각 윈도우로 평균/표준편차/최소/최대 집계
    labeled = interval_join(labeled, ns3, tcol="t")
    labeled = interval_join(labeled, bus,  tcol="t")

    # 저장
    outp = out/"unified_dataset.parquet"
    try:
        labeled.to_parquet(outp, index=False)
    except Exception:
        outp = out/"unified_dataset.csv"
        labeled.to_csv(outp, index=False)

    stats = labeled["module"].value_counts().to_dict()
    (out/"label_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[OK] dataset -> {outp}  rows={len(labeled)}  modules={list(stats.keys())}")

if __name__ == "__main__":
    main()
