
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
