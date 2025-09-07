#!/usr/bin/env python3
import os, sys, re, json, subprocess, time, csv, math
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BUS_DIR   = os.path.join(BASE, "bus")
BUS_LOG   = os.path.join(BUS_DIR, "bus.log")
TARGETS_Y = os.path.join(BASE, "modules", "attacks", "targets", "targets.yml")
RESOLVE   = os.path.join(BASE, "modules", "attacks", "resolve_target.py")

def sh(cmd): return subprocess.check_output(cmd, shell=True, text=True).strip()

def get_role_ip(role, service=None):
    cmd = f"python3 '{RESOLVE}' '{TARGETS_Y}' {role}"
    if service: cmd += f" {service}"
    try:
        j = json.loads(sh(cmd))
        return j.get("container",""), j.get("ip","")
    except Exception as e:
        return "", ""

def last_attack_start():
    # [t] BUS ATK ATTACK_START key=... level=... role=... host=... port=...
    if not os.path.exists(BUS_LOG): return None
    last = None
    with open(BUS_LOG,"r",encoding="utf-8") as f:
        for line in f:
            if "BUS ATK ATTACK_START" in line:
                last = line.strip()
    if not last: return None
    d = {}
    m = re.search(r"\[(\d+)\]", last)
    if m: d["t"] = int(m.group(1))
    for k in ["key","level","role","host","port"]:
        m = re.search(rf"{k}=([^\s]+)", last)
        if m: d[k] = m.group(1)
    return d

def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",newline="",encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

def main():
    out_dir = sys.argv[1] if len(sys.argv)>1 else os.path.join(BUS_DIR, "tmp")
    atk = last_attack_start() or {}
    atk_key   = atk.get("key","unknown_attack")
    atk_level = atk.get("level","low")
    atk_host  = atk.get("host","")
    # 1) nodes (order: attacker, gcs, flight, companion, simulator)
    roles = [("attacker",""), ("gcs","mavlink"), ("flight","mavlink"), ("companion","rtsp"), ("sim","http_cam")]
    nodes = []
    for role, svc in roles:
        if role=="attacker":
            name, ip = "attacker", ""
        else:
            name, ip = get_role_ip(role, svc)
            if not name: name = role
        nodes.append({"name":name, "ip":ip, "role":role})

    # positions: attacker left, gcs center, others in semicircle
    pos = {0:(-120,0), 1:(0,0), 2:(80,30), 3:(80,-30), 4:(140,0)}
    node_rows = []
    for i,n in enumerate(nodes):
        x,y = pos.get(i,(i*40,0))
        node_rows.append([i, n["name"], x, y])

    # 2) links: default benign flows + attack flow
    links = []
    def add(src,dst,rate,psz,label): links.append([src,dst,rate,psz,label])

    # benign (approx of DVD-lite):
    # GCS->FLIGHT MAVLink, GCS->COMPANION MAVLink-ish, COMPANION->SIM (camera)
    add(1,2,"1Mbps",512,"mavlink")
    add(1,3,"0.5Mbps",512,"mavlink")
    add(3,4,"0.6Mbps",600,"cam")

    # attack edge (attacker -> node matching atk_host)
    target_idx = None
    if atk_host:
        for i,n in enumerate(nodes):
            if n["ip"] == atk_host: target_idx = i; break
    if target_idx is None:
        # fallback: if role hints
        r = atk.get("role","")
        role_map = {"gcs":1, "flight":2, "companion":3, "sim":4}
        target_idx = role_map.get(r, 1)
    rate_map = {"low":"0.2Mbps","mid":"0.8Mbps","high":"2Mbps"}
    add(0, target_idx, rate_map.get(atk_level,"0.2Mbps"), 400, f"attack:{atk_key}:{atk_level}")

    # 3) write CSVs
    nodeinfo_csv = os.path.join(out_dir, "nodeinfo.csv")
    links_csv    = os.path.join(out_dir, "links.csv")
    write_csv(nodeinfo_csv, ["idx","name","x","y"], node_rows)
    write_csv(links_csv,    ["src","dst","rate","pktsize","label"], links)
    print(json.dumps({"nodeinfo":nodeinfo_csv,"links":links_csv,"attack":atk}, ensure_ascii=False))

if __name__=="__main__": main()
