#!/usr/bin/env python3
# effect_timeline.csv -> window_features.csv (WIN/STRIDE 슬라이딩 평균, 안정판 CLI)
import argparse, pandas as pd, numpy as np

ap=argparse.ArgumentParser()
ap.add_argument("timeline", help="attack_output/effect_timeline.csv (absolute path OK)")
ap.add_argument("-o","--out", default="attack_output/window_features.csv")
ap.add_argument("--win", type=float, default=3.0)
ap.add_argument("--stride", type=float, default=1.0)
args=ap.parse_args()

tl = pd.read_csv(args.timeline)
if "t" not in tl.columns:
    raise SystemExit("[ERR] timeline has no 't'")

cols = ["rate_limit_mbps","delay_ms","jitter_ms","loss_pct","dup_pct"]
for c in cols:
    if c not in tl.columns: tl[c]=np.nan
tl = tl.sort_values("t").reset_index(drop=True)

# 1초 그리드로 forward-fill (효과는 다음 이벤트 전까지 유지 가정)
t0, t1 = float(tl["t"].min()), float(tl["t"].max())
grid = pd.DataFrame({"t": np.arange(np.floor(t0), np.ceil(t1)+1, 1.0)})
tl_ff = pd.merge_asof(grid, tl[["t"]+cols].sort_values("t"), on="t", direction="backward")

# WIN/STRIDE 창 평균
rows=[]; cur = float(grid["t"].min())
while cur <= float(grid["t"].max()):
    w = tl_ff[(tl_ff["t"]>=cur) & (tl_ff["t"]<cur+args.win)]
    if len(w)>0:
        rows.append({
            "start_t":cur, "end_t":cur+args.win,
            "rate_mean":   float(np.nanmean(w["rate_limit_mbps"])),
            "delay_mean":  float(np.nanmean(w["delay_ms"])),
            "jitter_mean": float(np.nanmean(w["jitter_ms"])),
            "loss_mean":   float(np.nanmean(w["loss_pct"])),
            "dup_mean":    float(np.nanmean(w["dup_pct"])),
        })
    cur += args.stride

out = pd.DataFrame(rows)
out.to_csv(args.out, index=False)
print(f"[OK] window_features from timeline -> {args.out} rows={len(out)}")
