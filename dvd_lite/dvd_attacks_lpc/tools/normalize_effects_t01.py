#!/usr/bin/env python3
import glob, pandas as pd, os, sys

BUS = os.environ.get("OUT_DIR", "bus")
paths = glob.glob(f"{BUS}/events_*.csv") + glob.glob(f"{BUS}/effect_timeline_*.csv")
fixed = 0

def pick(d, names):
    for n in names:
        if n in d: return d[n]
    return None

for f in sorted(paths):
    try:
        df = pd.read_csv(f)
    except Exception as e:
        print(f"[SKIP] {f}: read failed ({e})")
        continue

    low = {c.lower(): c for c in df.columns}
    changed = False

    # --- ensure t0 ---
    if "t0" not in low:
        base = pick(low, ["start","ts","time","timestamp","t"])
        if base:
            df["t0"] = pd.to_numeric(df[base], errors="coerce").fillna(0.0)
            changed = True
        else:
            # fallback: monotonic index as seconds
            df["t0"] = pd.RangeIndex(len(df)).astype(float)
            changed = True
    else:
        df["t0"] = pd.to_numeric(df[low["t0"]], errors="coerce").fillna(0.0)

    # --- ensure t1 ---
    if "t1" not in low:
        # try end column
        endc = pick(low, ["end","t_stop","stop"])
        if endc:
            df["t1"] = pd.to_numeric(df[endc], errors="coerce").fillna(df["t0"])
            changed = True
        else:
            # try duration columns
            durc = pick(low, ["dur","dur_s","duration","len","length","dt"])
            if durc:
                df["t1"] = df["t0"] + pd.to_numeric(df[durc], errors="coerce").fillna(0.0)
                changed = True
            else:
                # point events → make t1 == t0
                df["t1"] = df["t0"]
                changed = True
    else:
        df["t1"] = pd.to_numeric(df[low["t1"]], errors="coerce").fillna(df["t0"])

    if changed:
        try:
            df.to_csv(f, index=False)
            fixed += 1
            print(f"[FIXED] {f}")
        except Exception as e:
            print(f"[ERR] write {f}: {e}")

print(f"[SUMMARY] files_fixed={fixed} / files_seen={len(paths)}")
