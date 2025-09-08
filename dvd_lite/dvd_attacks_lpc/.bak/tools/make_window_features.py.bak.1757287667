
import os,glob,csv,math,subprocess,json,statistics as st, re
from collections import defaultdict
BASE="."
OUT="bus/window_features.csv"; os.makedirs("bus",exist_ok=True)
WINDOW_S=float(os.environ.get("WIN_S",5.0))

STD_RE = re.compile(r'^(?P<atk>.+)_(?P<lv>[^_]+)_(?P<mtd>[^_]+)_(?P<scn>.+)$')
LEGACY3_RE = re.compile(r'^(?P<atk>.+)_(?P<lv>[^_]+)_(?P<scn>.+)$')

def parse_xml(path):
    b=os.path.basename(path)
    if not b.endswith(".xml"): raise ValueError("not xml")
    stem=b[:-4]
    if not stem.startswith("dvd_netanim_"):
        raise ValueError("skip non dvd_netanim")
    rest=stem[len("dvd_netanim_"):]
    # 중복 접두가 붙은 레거시 이름 정리: "..._dvd_netanim_..."가 있으면 앞쪽만 사용
    rest=rest.split("_dvd_netanim_")[0]
    # 표준 패턴 우선
    m=STD_RE.match(rest)
    if m:
        atk=m.group("atk"); lv=m.group("lv"); mtd=m.group("mtd"); scn=m.group("scn")
        mtd=("on" if mtd.lower() in ("true","on") else "off") if mtd.lower() in ("true","false","on","off") else mtd
        return scn, atk, lv, mtd
    # 레거시 3필드(ATK_LV_SCN) → mtd=off 가정
    m=LEGACY3_RE.match(rest)
    if m:
        return m.group("scn"), m.group("atk"), m.group("lv"), "off"
    # 아주 레거시: 토큰이 하나뿐이면 SCN만 있다고 보고 나머지 unknown/off
    toks=rest.split("_")
    if len(toks)==1:
        return rest, "unknown", "unknown", "off"
    raise ValueError(f"unrecognized name: {rest}")

def ensure_timeline(scn):
    tl=f"bus/effect_timeline_{scn}.csv"
    if os.path.exists(tl): return tl
    ev=f"bus/events_{scn}.csv"
    if os.path.exists(ev):
        subprocess.run(["python3","tools/events_to_timeline.py","--events",ev,"--sim","40","-o",tl], check=False)
    return tl if os.path.exists(tl) else None

def pcap_stats(scn):
    pdir=f"bus/captures/pcap/{scn}"
    cand=[]
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            if f.endswith(".pcap") or f.endswith(".pcap.gz"):
                # gz면 tshark가 직접 읽기도 하지만, 우선 .pcap 우선
                cand.append(os.path.join(pdir,f))
    if not cand: return None
    pcap=sorted(cand)[0]
    try:
        cmd=f"tshark -r '{pcap}' -Y 'udp.port==14550' -T fields -e frame.time_epoch -e frame.len"
        out=subprocess.check_output(["bash","-lc",cmd], text=True)
        ts=[]; ln=[]
        for line in out.splitlines():
            parts=line.strip().split("\t")
            if len(parts)<2: continue
            t=float(parts[0]); l=int(parts[1])
            ts.append(t); ln.append(l)
        if not ts: return None
        t0=min(ts); t1=max(ts); duration=max(1e-6,t1-t0)
        bins=defaultdict(lambda: {"pkts":0,"bytes":0})
        for t,l in zip(ts,ln):
            w=int(math.floor((t-t0)/WINDOW_S))
            bins[w]["pkts"]+=1; bins[w]["bytes"]+=l
        mx=max(bins.keys()); out=[]
        for w in range(mx+1):
            d=bins[w]; out.append({"win":w,"pps": d["pkts"]/WINDOW_S, "bytes": d["bytes"]})
        return out, t0, t1, duration
    except Exception:
        return None

def impair_series(tl, sim=40.0):
    events=[]
    if not tl or not os.path.exists(tl):
        return [{"t":0.0,"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0},{"t":sim,"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0}]
    with open(tl) as f:
        R=csv.DictReader(f)
        for r in R:
            try:
                events.append((float(r.get("t_apply_s",0)) , float(r.get("loss_pct",0)), float(r.get("delay_ms",0)),
                               float(r.get("jitter_ms",0)), float(r.get("dup_pct",0))))
            except: pass
    events.sort()
    series=[]; cur=(0.0,0.0,0.0,0.0); t=0.0
    while t<=sim+1e-9:
        for e in events:
            if e[0]<=t: cur=e[1:]
        series.append({"t":t, "loss_pct":cur[0],"delay_ms":cur[1],"jitter_ms":cur[2],"dup_pct":cur[3]})
        t+=WINDOW_S
    return series

def sim_time_for_scn(scn):
    for f in glob.glob(f"bus/ns3_metrics_*_{scn}.csv"):
        try:
            with open(f) as fh:
                L=fh.read().strip().splitlines()
                if len(L)>=2:
                    return float(L[-1].split(",")[0])
        except: pass
    return 40.0

rows=[]
bad=[]
for xml in sorted(glob.glob("bus/dvd_netanim_*.xml")):
    try:
        scn, atk, lv, mtd = parse_xml(xml)
    except Exception as e:
        bad.append((os.path.basename(xml), str(e))); continue
    simT = sim_time_for_scn(scn)
    tl = ensure_timeline(scn)
    imp = impair_series(tl, simT)
    pcap = pcap_stats(scn)
    if pcap:
        wins, t0, t1, dur = pcap
        for w in wins:
            t0s=w["win"]*WINDOW_S; t1s=min(simT, t0s+WINDOW_S)
            idx=int(round(t0s/WINDOW_S))
            e=imp[idx] if idx < len(imp) else imp[-1]
            rows.append({
                "scn":scn,"atk":atk,"lv":lv,"mtd":mtd,
                "t0":t0s,"t1":t1s,
                "pps":round(w["pps"],4),"bytes":w["bytes"],
                "loss_pct":e["loss_pct"],"delay_ms":e["delay_ms"],"jitter_ms":e["jitter_ms"],"dup_pct":e["dup_pct"],
            })
    else:
        n=int(math.ceil(simT/WINDOW_S))
        for i in range(n):
            t0s=i*WINDOW_S; t1s=min(simT,t0s+WINDOW_S)
            idx=i if i < len(imp) else len(imp)-1
            e=imp[idx]
            rows.append({
                "scn":scn,"atk":atk,"lv":lv,"mtd":mtd,
                "t0":t0s,"t1":t1s,
                "pps":0.0,"bytes":0,
                "loss_pct":e["loss_pct"],"delay_ms":e["delay_ms"],"jitter_ms":e["jitter_ms"],"dup_pct":e["dup_pct"],
            })

os.makedirs("bus",exist_ok=True)
with open(OUT,"w",newline="") as f:
    w=csv.DictWriter(f, fieldnames=["scn","atk","lv","mtd","t0","t1","pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"])
    w.writeheader(); [w.writerow(r) for r in rows]
print("WROTE", OUT, "rows=",len(rows))
if bad:
    print("[WARN] skipped non-standard XML names:")
    for b in bad[-10:]:
        print(" -", b[0], "->", b[1])
