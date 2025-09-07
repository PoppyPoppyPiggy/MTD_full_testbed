#!/usr/bin/env python3
import re, csv, sys, time
from pathlib import Path

RE_S = re.compile(r'ATTACK_START .*role=(\S+) host=(\S+) port=(\d+)')

def main():
    if len(sys.argv)<3:
        print("usage: make_nodeinfo_from_dvd.py <bus.log> <out_dir>"); sys.exit(2)
    bus = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    nodes = {"attacker": {"id":0, "name":"attacker", "x":10, "y":30}}
    links = set()
    nid = 1
    for ln in bus.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = RE_S.search(ln)
        if not m: continue
        role, host, port = m.group(1), m.group(2), int(m.group(3))
        name = f"{role}-{host}"
        if name not in nodes:
            nodes[name] = {"id": nid, "name": name, "x": 30 + 20*nid, "y": 30 + (nid%2)*10}
            nid += 1
        links.add((0, nodes[name]["id"], f"mav/rtsp:{port}"))
    # nodes.csv
    with (out/"nodes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["nodeId","name","x","y"])
        for v in nodes.values(): w.writerow([v["id"], v["name"], v["x"], v["y"]])
    # links.csv
    with (out/"links.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["srcId","dstId","label"])
        for a,b,l in sorted(links): w.writerow([a,b,l])

if __name__ == "__main__": main()
