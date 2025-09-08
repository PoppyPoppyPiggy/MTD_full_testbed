
import csv, json, gzip, re, os
from pathlib import Path
import pandas as pd

WIN_S=int(os.environ.get("WIN_S","5"))
BUS=Path("bus")
OUT=str(BUS/"window_features.csv")

def parse_name(xml):
    b=Path(xml).stem
    if not b.startswith("dvd_netanim_"): return None
    rest=b[len("dvd_netanim_"):]
    parts=rest.split("_")
    if len(parts)<3: return None
    scn = parts[-1]
    mtd = parts[-2].lower()
    lv  = parts[-3].lower()
    atk = "_".join(parts[:-3])
    if mtd in ("true","false"): mtd = "on" if mtd=="true" else "off"
    return scn, atk, lv, mtd

def standard_label(atk):
    if atk.startswith("eval") or atk.startswith("fanet") or atk in ("dvd","netanim"):
        return "baseline"
    return atk

def load_cti():
    j=BUS/"cti.jsonl"
    if not j.exists(): return pd.DataFrame()
    rows=[]
    for line in open(j,"r",errors="ignore"):
        try: rows.append(json.loads(line))
        except: pass
    return pd.DataFrame(rows)

def sim_time(scn):
    # ns3 metrics 파일에서 time_s (없으면 40초)
    mets=list(BUS.glob(f"ns3_metrics_*_{scn}.csv"))
    for m in mets:
        try:
            df=pd.read_csv(m)
            if "time_s" in df.columns:
                return int(float(df["time_s"].iloc[0]))
            if "sim_t_s" in df.columns:
                return int(float(df["sim_t_s"].iloc[0]))
        except: pass
    return 40

def densify_windows(scn):
    T=sim_time(scn)
    # effect timeline 로드(없으면 0값 이벤트 하나)
    etf=BUS/f"effect_timeline_{scn}.csv"
    if etf.exists():
        df=pd.read_csv(etf)
    else:
        df=pd.DataFrame([{"t0":0,"t1":T,"pps":0,"bytes":0,"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0}])
    # 윈도우 슬라이스
    out=[]
    for w0 in range(0, T, WIN_S):
        w1=min(w0+WIN_S, T)
        sub=df[(df["t1"]>w0) & (df["t0"]<w1)]
        if sub.empty:
            row={"t0":w0,"t1":w1,"pps":0,"bytes":0,"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0}
        else:
            # 평균값(완만한 LPC에 적합)
            row={"t0":w0,"t1":w1,
                 "pps":float(sub.get("pps",pd.Series([0])).mean()),
                 "bytes":float(sub.get("bytes",pd.Series([0])).mean()),
                 "loss_pct":float(sub.get("loss_pct",pd.Series([0])).mean()),
                 "delay_ms":float(sub.get("delay_ms",pd.Series([0])).mean()),
                 "jitter_ms":float(sub.get("jitter_ms",pd.Series([0])).mean()),
                 "dup_pct":float(sub.get("dup_pct",pd.Series([0])).mean())}
        out.append(row)
    return pd.DataFrame(out)

def main():
    rows=[]
    bad=[]
    for x in sorted(BUS.glob("dvd_netanim_*.xml")):
        parsed=parse_name(x.name)
        if not parsed: bad.append((x.name,"unrecognized")); continue
        scn, atk, lv, mtd = parsed
        atk=standard_label(atk)
        wdf=densify_windows(scn)
        wdf["scn"]=scn; wdf["atk"]=atk; wdf["lv"]=lv; wdf["mtd"]=mtd
        rows.append(wdf)

    if not rows:
        print("WROTE",OUT,"rows= 0"); open(OUT,"w").write("scn,atk,lv,mtd,t0,t1,pps,bytes,loss_pct,delay_ms,jitter_ms,dup_pct\n"); return
    df=pd.concat(rows, ignore_index=True)

    # CTI 조인(있으면)
    cti=load_cti()
    if not cti.empty and "scn" in cti.columns:
        agg={}
        if "status_len" in cti.columns: agg["status_len_mean"]=("status_len","mean")
        if "param_id"   in cti.columns: agg["param_id_nuniq"]=("param_id",pd.Series.nunique)
        if "pps"        in cti.columns: agg["atk_pps_mean"]=("pps","mean")
        if agg:
            csum=cti.groupby("scn").agg(**agg).reset_index()
            df=df.merge(csum,on="scn",how="left")

    cols=["scn","atk","lv","mtd","t0","t1","pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"]
    extra=[c for c in ["status_len_mean","param_id_nuniq","atk_pps_mean"] if c in df.columns]
    df[cols+extra].to_csv(OUT,index=False)

    print("WROTE",OUT,"rows=",len(df))
    if bad:
        print("[WARN] skipped non-standard XML names:")
        for b,_ in bad[-10:]: print(" -",b)
if __name__=="__main__": main()


# --- RESCUE_FROM_METRICS: if no rows, backfill from ns3_metrics_* ---
def _rescue_from_metrics(out_csv):
    import glob, csv
    from pathlib import Path
    rows=[]
    def parse_xml_name(p):
        b=Path(p).stem
        if not b.startswith("dvd_netanim_"): return None
        b=b[len("dvd_netanim_"):]
        parts=b.split("_")
        if len(parts)<4: return None
        scn=parts[-1]
        mtd=parts[-2].lower()
        if mtd in ('true','on'): mtd='on'
        elif mtd in ('false','off'): mtd='off'
        lv=parts[-3]; atk="_".join(parts[:-3])
        return scn, atk, lv, mtd
    for xml in sorted(glob.glob("bus/dvd_netanim_*.xml")):
        parsed=parse_xml_name(xml)
        if not parsed: continue
        scn,atk,lv,mtd=parsed
        mets=sorted(glob.glob(f"bus/ns3_metrics_*_{scn}.csv"))
        if not mets: mets=sorted(glob.glob(f"bus/ns3_metrics_{atk}_{lv}_{mtd}_{scn}.csv"))
        if not mets: continue
        met=mets[-1]
        # metrics 포맷: time_s,rx_bytes,drop_cnt,dup_cnt
        last=None
        with open(met) as f:
            for line in f: last=line.strip()
        if not last or "," not in last: continue
        parts=last.split(",")
        try:
            t=float(parts[0]); rx=int(parts[1])
        except: 
            continue
        pps = (rx/100.0/t) if t>0 else 0.0
        rows.append({"scn":scn,"atk":atk,"lv":lv,"mtd":mtd,
                     "t0":0.0,"t1":t,"pps":pps,"bytes":rx,
                     "loss_pct":0.0,"delay_ms":0.0,"jitter_ms":0.0,"dup_pct":0.0})
    if rows:
        with open(out_csv,"w",newline="") as f:
            w=csv.DictWriter(f, fieldnames=["scn","atk","lv","mtd","t0","t1","pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"])
            w.writeheader(); w.writerows(rows)
        print(f"[RESCUE_FROM_METRICS] wrote {out_csv} rows={len(rows)}")
    else:
        print("[RESCUE_FROM_METRICS] nothing to write")

if __name__=="__main__":
    try:
        import csv
        with open("bus/window_features.csv") as f:
            r=list(csv.DictReader(f))
        if not r:
            _rescue_from_metrics("bus/window_features.csv")
    except Exception as e:
        print("[RESCUE_FROM_METRICS] skip due to", e)
