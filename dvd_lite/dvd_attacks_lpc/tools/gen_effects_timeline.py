#!/usr/bin/env python3
import re, json, sys, csv, os, datetime

root = os.path.dirname(os.path.dirname(__file__))
base = os.path.join(root, "dvd_attacks_lpc")
log = os.path.join(base, "attack_output", "bus.log")
rules_path = os.path.join(base, "tools", "effects_rules.json")

if not os.path.isfile(rules_path):
    print("effects_rules.json not found", file=sys.stderr); sys.exit(1)
rules = json.load(open(rules_path))

pat = re.compile(r'^\[(.*?)\]\s+\[(.*?)\]\s+(.*)$')
rows = []
if os.path.isfile(log):
    with open(log, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pat.match(line.strip())
            if not m: continue
            ts, mod, kvs = m.groups()
            mod = mod.strip().lower()
            kv = dict(x.split('=',1) for x in kvs.split() if '=' in x)
            # phase 우선, 없으면 intensity → 없으면 low
            phase = (kv.get('phase') or '').lower()
            intensity = (kv.get('intensity') or 'low').lower()
            eff = None
            if phase and mod in rules and phase in rules[mod]:
                eff = rules[mod][phase]
            elif mod in rules and intensity in rules[mod]:
                eff = rules[mod][intensity]
            else:
                eff = {"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0,"rate_limit_mbps":0}

            t = datetime.datetime.fromisoformat(ts).timestamp()
            rows.append( (t, eff.get("loss_pct",0), eff.get("delay_ms",0),
                          eff.get("jitter_ms",0), eff.get("dup_pct",0),
                          eff.get("rate_limit_mbps",0)) )

rows.sort()
out = os.path.join(base, "attack_output", "effect_timeline.csv")
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t_sec","loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"])
    for r in rows:
        w.writerow(r)
print(out)
