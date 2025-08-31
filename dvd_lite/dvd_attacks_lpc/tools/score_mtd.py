#!/usr/bin/env python3
# dvd_lite/dvd_attacks_lpc/tools/score_mtd.py
import re, csv, argparse, json, os, glob, statistics as st
from datetime import datetime

def read_bus(path):
    evts=[]
    kv = re.compile(r'(\w+)=("[^"]*"|\S+)')
    with open(path,'r') as f:
        for line in f:
            d={'raw':line.strip()}
            for k,v in kv.findall(line):
                d[k]=v.strip('"')
            evts.append(d)
    return evts

def read_ns3_summary(ns3dir):
    rows=[]
    for p in glob.glob(os.path.join(ns3dir,'ns3_metrics_summary_*.csv')) + \
             glob.glob(os.path.join(ns3dir,'ns3_metrics_summary.csv')):
        with open(p,'r') as f:
            rd=csv.DictReader(f)
            for r in rd: rows.append(r)
    return rows

def read_ns3_timeseries(ns3dir):
    rows=[]
    for p in glob.glob(os.path.join(ns3dir,'ns3_metrics_*.csv')) + \
             glob.glob(os.path.join(ns3dir,'ns3_metrics.csv')):
        with open(p,'r') as f:
            rd=csv.DictReader(f)
            for r in rd: rows.append(r)
    return rows

def pct(x,lo,hi): 
    return 0 if hi<=lo else max(0,min(1,(x-lo)/(hi-lo)))

def score(bus, sumrows, tsrows):
    # ===== DIVERSITY: 공격 표적 엔드포인트 다양성(공격 적응 난이도)
    endpoints=set()
    for e in bus:
        if e.get('tag')=='attack':
            ep=(e.get('ip','?'), e.get('port','?'), e.get('module','?'))
            endpoints.add(ep)
    diversity = pct(len(endpoints), 1, 6)  # 1~6 스케일 정규화

    # ===== SHUFFLE 효율(빈도-복구시간-오버헤드 균형)
    mtd_times=[int(e['time']) for e in bus if e.get('tag')=='mtd']
    cti_changes=[int(e['time']) for e in bus if e.get('tag')=='cti']
    # 복구시간: MTD 이후 다음 5초 평균 손실률 저하
    loss_by_t={}
    for r in tsrows:
        t=int(float(r.get('time',0)))
        loss=float(r.get('loss_pct', r.get('loss%','0')))
        loss_by_t[t]=loss
    def avg_loss(t0,t1):
        xs=[loss_by_t.get(t,0) for t in range(t0,t1+1)]
        return sum(xs)/len(xs) if xs else 0
    recovs=[]
    for t in mtd_times:
        before=avg_loss(max(0,t-3),t-1)
        after =avg_loss(t+1, t+5)
        if before>0: recovs.append(max(0,(before-after)/max(1e-9,before)))
    recover = sum(recovs)/len(recovs) if recovs else 0  # 0~1
    freq = pct(len(mtd_times), 0, 6)  # 너무 많아도 비용↑, 가중 0.5 반영
    shuffle = 0.7*recover + 0.3*(1-abs(freq-0.4))  # 0.4 부근이 sweet-spot

    # ===== REDUNDANCY: 대체 경로 실효(처리량 회복)
    thr=[float(r['throughput_bps']) for r in sumrows if 'throughput_bps' in r]
    thr_avg = st.mean(thr) if thr else 0.0
    thr_nominal=2e6  # 링크 기준치(시뮬 파라미터에 맞게 조정)
    redundancy = pct(thr_avg, 4e5, thr_nominal)  # 0.4Mbps~nominal 스케일

    # ===== SURVIVABILITY: 임무 가용성(손실률/지연/지터)
    rx=[int(r.get('rx', r.get('rx_pkts','0'))) for r in sumrows]
    tx=[int(r.get('tx', r.get('tx_pkts','0'))) for r in sumrows]
    lost=sum(t-x for t,x in zip(tx,rx)) if tx and rx else 0
    loss_rate = lost/max(1,sum(tx)) if tx else 0
    surv = 1 - pct(loss_rate, 0.05, 0.5)  # 5% 이하는 정상, 50%는 치명적

    # ===== ENERGY(비용): 방어 횟수 + 손실/지연 오버헤드
    energy = max(0, 1 - pct(len(mtd_times), 0, 8)*0.6 - pct(sum(loss_by_t.values()), 0, 500)*0.4)

    # 가중합(가중치는 필요 시 조정)
    total = 0.22*diversity + 0.24*shuffle + 0.18*redundancy + 0.24*surv + 0.12*energy
    return {
      "DIVERSITY": round(diversity,3),
      "SHUFFLE"  : round(shuffle,3),
      "REDUNDANCY": round(redundancy,3),
      "SURVIVABILITY": round(surv,3),
      "ENERGY": round(energy,3),
      "MTD_SCORE": round(total,3)
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--bus', required=True)
    ap.add_argument('--ns3dir', required=True)
    ap.add_argument('--out', default='mtd_report.md')
    args=ap.parse_args()
    bus=read_bus(args.bus)
    sumrows=read_ns3_summary(args.ns3dir)
    tsrows=read_ns3_timeseries(args.ns3dir)
    s=score(bus,sumrows,tsrows)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out,'w') as f:
        f.write("# MTD 평가 리포트\n\n")
        f.write("|지표|점수|\n|---|---|\n")
        for k in ["DIVERSITY","SHUFFLE","REDUNDANCY","SURVIVABILITY","ENERGY","MTD_SCORE"]:
            f.write(f"|{k}|{s[k]:.3f}|\n")
        f.write("\n*0~1 정규화 점수, 가중합으로 MTD_SCORE 산출*\n")

if __name__=="__main__":
    main()
