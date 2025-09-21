#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/compute_mtd_metrics.py
DVD 로그(bus.log, bus_dvd.log)를 읽어 고도화된 MTD 지표를 산출하고
Security-Agility-Cost-Deception 4축 기반 종합 스코어를 계산한다.

사용:
  python3 tools/compute_mtd_metrics.py --bus ./bus/bus.log --dvd ./bus/bus_dvd.log --out ./metrics_report.json
"""
import os, sys, json, argparse, math, statistics
from collections import defaultdict, deque
from datetime import datetime

def read_jsonl(path):
    events = []
    if not os.path.exists(path): return events
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            try:
                ev = json.loads(line)
                if 'ts' not in ev: continue
                events.append(ev)
            except json.JSONDecodeError:
                pass
    events.sort(key=lambda x: x['ts'])
    return events

def shannon_entropy(seq):
    if not seq: return 0.0
    from math import log2
    counts = defaultdict(int)
    for s in seq: counts[s] += 1
    n = len(seq)
    H = 0.0
    for c in counts.values():
        p = c / n
        H -= p * log2(p)
    return H

def normalize(v, lo, hi, invert=False):
    if hi <= lo: return 0.0
    x = (v - lo) / (hi - lo)
    x = max(0.0, min(1.0, x))
    return 1.0 - x if invert else x

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bus', default='./bus/bus.log')
    ap.add_argument('--dvd', default='./bus/bus_dvd.log')
    ap.add_argument('--out', default='./metrics_report.json')
    args = ap.parse_args()

    bus = read_jsonl(args.bus)
    dvd = read_jsonl(args.dvd)

    # --- (1) 핵심 이벤트 타임라인 추출 ---
    seeker_start_ts = None
    first_comp_ts = None
    attack_starts = []
    swaps = []
    reasons = []
    ip_seq, port_seq = [], []
    decoy_hits, total_probes = 0, 0

    alt_series = [(e.get('ts'), e.get('data', {}).get('alt_m')) for e in dvd if e.get('data', {}).get('alt_m') is not None]

    for e in bus:
        et, data, ts = e.get('type'), e.get('data', {}), e['ts']
        if et in ('prober_started', 'seeker_started') and seeker_start_ts is None: seeker_start_ts = ts
        if et in ('prober_target_confirmed', 'lpc_recon_success') and first_comp_ts is None: first_comp_ts = ts
        if et == 'attack_started': attack_starts.append(ts)
        if et == 'mtd_target_swap':
            frm, to, reason = data.get('from', ''), data.get('to', ''), data.get('reason', 'unknown')
            reasons.append(reason)
            if isinstance(to, str) and ':' in to:
                ip_seq.append(to.split(':')[0])
                port_seq.append(int(to.split(':')[1]))
            swaps.append(ts)
        if et in ('probe_to_decoy', 'attack_to_decoy'): decoy_hits += 1
        if et in ('prober_activity', 'scan_probe'): total_probes += 1

    # --- (2) 4-Axis 지표 계산 ---
    
    # (A) Security
    TFC = (first_comp_ts - seeker_start_ts) if (seeker_start_ts and first_comp_ts) else 0.0
    def effect_after(t0, window=10.0):
        relevant = [(t, a) for (t, a) in alt_series if t0 <= t <= t0 + window and a is not None]
        if not relevant: return False
        v = [a for (_, a) in relevant]
        return (max(v) - min(v)) >= 5.0
    A, B = len(attack_starts), sum(1 for t in attack_starts if effect_after(t))
    ASR = (B / A) if A > 0 else 0.0
    AWF = sum(1 for e in bus if e['ts'] < (first_comp_ts or float('inf')) and e.get('type') in ('prober_activity', 'scan_probe'))

    # (B) Agility/Entropy
    def count_swaps(t0, win=60.0, before=True):
        lo, hi = (t0 - win, t0) if before else (t0, t0 + win)
        return sum(1 for t in swaps if lo <= t < hi)
    asf_list = [(count_swaps(t, before=False) / count_swaps(t, before=True)) for t in attack_starts if count_swaps(t, before=True) > 0]
    ASF = statistics.mean(asf_list) if asf_list else 0.0
    H_total = shannon_entropy(ip_seq) + shannon_entropy(port_seq) + shannon_entropy(reasons)

    # (C) Cost (Placeholder - 실제 측정값으로 대체 필요)
    QoS_overhead_ms, Loss_overhead, Mig_cost, Energy_overhead = 0.0, 0.0, len(swaps) * 1.0, 0.0

    # (D) Deception
    DER = (decoy_hits / total_probes) if total_probes > 0 else 0.0
    Time_in_deception = 0.0 # TODO: 로그 이벤트 기반으로 실제 체류 시간 계산

    # --- (3) 정규화 및 가중합 ---
    sim_duration = (bus[-1]['ts'] - bus[0]['ts']) if bus else 1.0
    TFC_n = normalize(TFC, 0.0, sim_duration)
    AWF_n = normalize(AWF, 0, max(1, total_probes))
    Security = 0.5 * TFC_n + 0.3 * (1.0 - ASR) + 0.2 * AWF_n
    
    ASF_n = normalize(ASF, 0.0, 5.0) # 5배 이상 변화 시 만점
    H_n = normalize(H_total, 0.0, 8.0) # 엔트로피 8 이상 시 만점
    Agility = 0.5 * ASF_n + 0.5 * H_n

    Mig_n = normalize(Mig_cost, 0.0, 200.0, invert=True) # 200회 이상 셔플 시 0점
    Cost = Mig_n # 현재는 마이그레이션 비용만 반영

    Deception = normalize(DER, 0.0, 1.0)
    
    weights = {'wS': 0.4, 'wA': 0.2, 'wC': 0.2, 'wD': 0.2}
    Overall = weights['wS']*Security + weights['wA']*Agility + weights['wC']*Cost + weights['wD']*Deception

    report = {
        "scores": {"Overall": Overall, "Security": Security, "Agility": Agility, "Cost": Cost, "Deception": Deception},
        "raw_metrics": {"TFC": TFC, "ASR": ASR, "AWF": AWF, "ASF": ASF, "H_total": H_total, "Mig_cost": Mig_cost, "DER": DER}
    }

    with open(args.out, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"[OK] MTD 평가 보고서 생성: {os.path.abspath(args.out)}")
    print(json.dumps(report["scores"], indent=2))

if __name__ == "__main__":
    main()