#!/usr/bin/env python3
import re, csv, sys, json, time
from pathlib import Path

MAP = {
  # (loss_pct, delay_ms, jitter_ms, rate_mbps) by level
  "mavlink_statustext_noise": {"low": (0.5, 3,  1,  50), "mid": (1.5, 6,  2,  30), "high": (3.0, 12, 4,  15)},
  "mavlink_param_poll":       {"low": (0.3, 2,  1,  60), "mid": (0.8, 5,  2,  40), "high": (1.5, 10, 3,  25)},
  "mavlink_cmdlong_tease":    {"low": (0.5, 4,  2,  40), "mid": (1.5, 8,  3,  25), "high": (3.0, 15, 5,  12)},
  "mavlink_mission_trickle":  {"low": (0.5, 5,  2,  35), "mid": (1.0, 8,  3,  20), "high": (2.0, 12, 4,  12)},
  "gps_slow_spoof":           {"low": (0.5, 6,  3,  40), "mid": (1.0, 10, 4, 25), "high": (2.0, 16, 6,  15)},
  "rtsp_slowpull":            {"low": (0.5, 8,  4,  60), "mid": (1.0, 12, 5, 40), "high": (2.0, 20, 7,  25)},
  "telemetry_slow_exfil":     {"low": (0.3, 2,  1,  60), "mid": (0.6, 4,  2,  50), "high": (1.2, 8,  3,  35)}
}

# BUS 로그 파서
RE_S = re.compile(r'\[(\d+)\]\s+BUS ATK ATTACK_START key=(\S+) level=(\S+) .*host=(\S+) port=(\d+)')
RE_E = re.compile(r'\[(\d+)\]\s+BUS ATK ATTACK_END key=(\S+) level=(\S+)')

def parse(log_path: Path):
    starts = {}
    rows = []
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = RE_S.search(line)
        if m:
            t, key, lvl, host, port = int(m.group(1)), m.group(2), m.group(3), m.group(4), int(m.group(5))
            starts[(key,lvl)] = (t, host, port)
        m = RE_E.search(line)
        if m:
            t2, key, lvl = int(m.group(1)), m.group(2), m.group(3)
            if (key,lvl) in starts:
                t1, host, port = starts.pop((key,lvl))
                if key in MAP and lvl in MAP[key]:
                    loss, delay, jitter, rate = MAP[key][lvl]
                    rows.append({"t_start": t1, "t_end": t2, "src":"attacker", "dst": host, "dst_port": port,
                                 "loss_pct": loss, "delay_ms": delay, "jitter_ms": jitter, "rate_mbps": rate,
                                 "label": f"{key}:{lvl}"})
    return rows

def write_csv(rows, out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_start","t_end","src","dst","dst_port","loss_pct","delay_ms","jitter_ms","rate_mbps","label"])
        for r in rows:
            w.writerow([r[k] for k in ["t_start","t_end","src","dst","dst_port","loss_pct","delay_ms","jitter_ms","rate_mbps","label"]])

def main():
    if len(sys.argv)<3:
        print("usage: gen_effect_timestamp.py <bus.log> --out <csv>"); sys.exit(2)
    bus = Path(sys.argv[1])
    out = Path(sys.argv[sys.argv.index("--out")+1]) if "--out" in sys.argv else Path("bus/effect_timeline.csv")
    rows = parse(bus)
    write_csv(rows, out)

if __name__ == "__main__": main()
