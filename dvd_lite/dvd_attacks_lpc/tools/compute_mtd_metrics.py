#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_mtd_metrics.py
- Damn-Vulnerable-Drone 테스트베드(bus.log, bus_dvd.log)에서 MTD 성능 지표 계산
- 지표: DIVERSITY / SHUFFLE / REDUNDANCY / SURVIVABILITY / ENERGY
"""

import os, sys, json, math, argparse, time, datetime
from collections import defaultdict, deque
from statistics import mean
from typing import Optional, Dict, Any, Tuple, List

# --------------------------
# 기본 파라미터(테스트베드 기본값)
# --------------------------
DEF_BUS      = "/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus.log"
DEF_BUS_DVD  = "/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus_dvd.log"
DEF_OUTDIR   = "/home/kali/MTD_full_testbed/test_output/latest/metrics"

DEF_DRONE_IP = "10.13.0.3"
DEF_DECOY_IP = "10.13.0.100"
DEF_PORT     = 14550

# SHUFFLE 분석 파라미터
SHUFFLE_WINDOW_S    = 5.0     # 전/후 히트율 비교 윈도우
EFFICIENCY_BETA     = 3.0     # 셔플 패널티 민감도
ATTACK_HEAVY_THR_HZ = 2.0     # REDUNDANCY에서 '공격 심함' 판단 히트율(Hz)

# --------------------------
# 공통 유틸
# --------------------------
def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def _etype(evt: Dict[str, Any]) -> str:
    return evt.get("type") or evt.get("event_type") or \
           (evt.get("data", {}) or {}).get("type") or (evt.get("data", {}) or {}).get("event_type") or ""

def _get(evt: Dict[str, Any], *keys, default=None):
    cur = evt
    try:
        for k in keys:
            cur = cur[k]
        return cur
    except Exception:
        return default

def _ts(evt: Dict[str, Any]) -> Optional[float]:
    t = evt.get("ts")
    if isinstance(t, (int, float)): return float(t)
    # 일부는 timestamp ISO만 있을 수 있음
    iso = evt.get("timestamp") or evt.get("@timestamp")
    if isinstance(iso, str):
        try:
            return datetime.datetime.fromisoformat(iso.replace("Z","+00:00")).timestamp()
        except Exception:
            return None
    return None

def _try_int(v) -> Optional[int]:
    try: return int(v)
    except Exception: return None

def _dst_port(evt: Dict[str, Any]) -> Optional[int]:
    v = evt.get("dst_port") or _get(evt, "data", "dst_port") or _get(evt, "net", "dst_port")
    if v is None:
        # attack_surface_hit → "target": "ip:port"
        tgt = evt.get("target") or _get(evt, "data", "target")
        if isinstance(tgt, str) and ":" in tgt:
            v = tgt.split(":")[1]
    return _try_int(v)

def _src_ip(evt): 
    return evt.get("src_ip") or _get(evt, "data","src_ip") or _get(evt,"net","src_ip")

def _dst_ip(evt):
    dip = (evt.get("dst_ip") or _get(evt,"data","dst_ip") or _get(evt,"net","dst_ip"))
    if dip: return dip
    # attack_surface_hit fallback
    tgt = evt.get("target") or _get(evt, "data", "target")
    if isinstance(tgt, str) and ":" in tgt:
        return tgt.split(":")[0]
    return None

def _safe_open(path: str):
    try:
        return open(path, "r", encoding="utf-8")
    except FileNotFoundError:
        return None

# --------------------------
# 로그 파싱(스트리밍)
# --------------------------
def iter_events(path: str, tmin: Optional[float], tmax: Optional[float]):
    f = _safe_open(path)
    if not f: 
        return
    with f:
        for line in f:
            try:
                evt = json.loads(line)
            except Exception:
                continue
            ts = _ts(evt)
            if ts is None: 
                continue
            if (tmin is not None and ts < tmin) or (tmax is not None and ts > tmax):
                continue
            yield evt

# --------------------------
# DIVERSITY
# --------------------------
def shannon_evenness(counts: Dict[str,int]) -> Tuple[float,int,float]:
    total = sum(counts.values())
    if total == 0:
        return 0.0, 0, 0.0
    ps = [c/total for c in counts.values() if c>0]
    H = -sum(p*math.log(p,2) for p in ps)
    N = len(ps)
    even = (H / math.log(N,2)) if N>1 else 1.0
    top1 = max(ps) if ps else 0.0
    return even, N, top1

def compute_diversity(bus_path: str, port: int, tmin, tmax) -> Dict[str,Any]:
    dst_counts = defaultdict(int)
    total = 0
    for evt in iter_events(bus_path, tmin, tmax):
        typ = _etype(evt)
        if typ not in ("udp_packet","net_packet","attack_surface_hit","udp_packet_tx","udp_packet_rx",
                       "arp_packet"):  # arp는 제외되지만 혹시 dst_port 없는 케이스 피함
            continue
        dp = _dst_port(evt)
        if dp != port:
            continue
        dip = _dst_ip(evt)
        if not dip:
            continue
        dst_counts[dip] += 1
        total += 1
    even, nuniq, top1 = shannon_evenness(dst_counts)
    return {
        "total_hits": total,
        "unique_endpoints": nuniq,
        "diversity_evenness": round(even, 4),
        "top1_share": round(top1, 4),
        "by_endpoint": dict(sorted(dst_counts.items(), key=lambda x: -x[1]))
    }

# --------------------------
# SHUFFLE
# --------------------------
def compute_shuffle(bus_path: str, port: int, window_s: float, beta: float, tmin, tmax) -> Dict[str,Any]:
    # 1) 셔플 이벤트 수집
    shuffles = []  # (ts, new_target_ip, old_target_ip)
    cur_target = None
    cur_ts = None

    # 먼저 current_target을 알면 좋으나, 로그만으로 old_target 추정:
    # → 직전 히트의 dst_ip를 old로 사용(동일 포트 14550).
    last_hit_dst_ip: Optional[str] = None

    # 모든 이벤트를 1pass 하면서 셔플/히트 추출
    hits_by_time: List[Tuple[float,str]] = []
    for evt in iter_events(bus_path, tmin, tmax):
        typ = _etype(evt)
        ts  = _ts(evt)
        if typ in ("udp_packet","net_packet","attack_surface_hit","udp_packet_tx","udp_packet_rx"):
            if _dst_port(evt) == port:
                dip = _dst_ip(evt)
                if dip:
                    hits_by_time.append((ts, dip))
                    last_hit_dst_ip = dip
        elif typ in ("mtd_action","mtd_target_swap","mtd_applied"):
            act = evt.get("action") or _get(evt,"data","action") or ""
            if act == "ip_shuffle" or typ in ("mtd_target_swap","mtd_applied"):
                tstr = evt.get("new_target") or evt.get("to") or _get(evt,"data","new_target") or _get(evt,"data","to")
                nip = None
                if isinstance(tstr, str) and ":" in tstr: nip = tstr.split(":")[0]
                if not nip:
                    # fallback: dst_ip?
                    nip = evt.get("dst_ip") or _get(evt,"data","dst_ip")
                if ts and nip:
                    shuffles.append((ts, nip, last_hit_dst_ip))

    shuffles.sort(key=lambda x: x[0])
    hits_by_time.sort(key=lambda x: x[0])

    # 2) 전/후 히트율 계산
    def rate_in_window(center_ts: float, target_ip: str, before: bool) -> float:
        start = center_ts - window_s if before else center_ts
        end   = center_ts          if before else center_ts + window_s
        if end <= start: return 0.0
        cnt = 0
        for ts, dip in hits_by_time:
            if ts < start: continue
            if ts > end: break
            if dip == target_ip:
                cnt += 1
        return cnt / (end - start)

    drops, retargets = [], []
    for i,(ts, new_ip, old_ip) in enumerate(shuffles):
        if not old_ip:  # 직전 히트 없으면 스킵
            continue
        pre  = rate_in_window(ts, old_ip, before=True)
        post = rate_in_window(ts, old_ip, before=False)
        drop = 0.0 if pre <= 1e-9 else max(0.0, min(1.0, (pre - post) / pre))
        drops.append(drop)

        # 재적응 시간: 셔플 이후 new_ip 첫 히트 시각- ts
        first = None
        for hts, dip in hits_by_time:
            if hts <= ts: continue
            if dip == new_ip:
                first = hts; break
        if first is not None:
            retargets.append(first - ts)

    total_time = 0.0
    if hits_by_time:
        total_time = (hits_by_time[-1][0] - hits_by_time[0][0]) or 0.0

    rate_per_min = (len(shuffles) / (total_time/60.0)) if total_time>0 else 0.0
    mean_drop = round(mean(drops), 4) if drops else 0.0
    mean_ret  = round(mean(retargets), 3) if retargets else None

    # 효율: 과다 셔플 패널티
    efficiency = mean_drop / (1.0 + rate_per_min / beta) if beta>0 else mean_drop

    return {
        "shuffle_count": len(shuffles),
        "shuffle_rate_per_min": round(rate_per_min, 3),
        "mean_pre_post_drop": mean_drop,
        "mean_retarget_time_s": mean_ret,
        "efficiency_score": round(efficiency, 4),
        "window_s": window_s,
        "beta": beta,
        "samples_used": len(drops)
    }

# --------------------------
# REDUNDANCY
# --------------------------
def compute_redundancy(bus_path: str, drone_ip: str, decoy_ip: str, port: int, tmin, tmax) -> Dict[str,Any]:
    # 1s 버킷 히트율
    bucket = defaultdict(lambda: {"drone":0, "decoy":0})
    t0 = None; t1 = None
    for evt in iter_events(bus_path, tmin, tmax):
        typ = _etype(evt)
        if typ not in ("udp_packet","net_packet","attack_surface_hit","udp_packet_tx","udp_packet_rx"):
            continue
        if _dst_port(evt) != port:
            continue
        dip = _dst_ip(evt)
        ts  = math.floor(_ts(evt) or 0)
        if t0 is None: t0 = ts
        t1 = ts
        if dip == drone_ip:
            bucket[ts]["drone"] += 1
        elif dip == decoy_ip:
            bucket[ts]["decoy"] += 1

    if not bucket:
        return {"decoy_share_during_attacks": 0.0, "failover_incidents": 0, "time_buckets": 0}

    # 공격 심한 구간: drone rate >= ATTACK_HEAVY_THR_HZ
    incidents = 0
    shares = []
    for ts in sorted(bucket.keys()):
        d = bucket[ts]["drone"]
        # 1초 버킷이므로 '히트율' ~ count
        if d >= ATTACK_HEAVY_THR_HZ:
            inc_total = d + bucket[ts]["decoy"]
            if inc_total > 0:
                shares.append(bucket[ts]["decoy"]/inc_total)
                if bucket[ts]["decoy"] >= 1:
                    incidents += 1

    decoy_share = round(mean(shares), 4) if shares else 0.0
    return {
        "decoy_share_during_attacks": decoy_share,
        "failover_incidents": incidents,
        "time_buckets": len(bucket)
    }

# --------------------------
# SURVIVABILITY
# --------------------------
def compute_survivability(bus_dvd_path: str, tmin, tmax) -> Dict[str,Any]:
    # state: MAV_STATE_ACTIVE(=4), MAV_STATE_UNINIT(=0), armed(bool)
    # 균일 가중치: 표본 간 Δt 반영(샘플 간 시간간격 기준 가중)
    last_ts = None
    active_time = 0.0
    armed_time  = 0.0
    total_time  = 0.0
    last_active = None
    last_armed  = None
    last_state_raw = None
    uninit_flaps = 0

    for evt in iter_events(bus_dvd_path, tmin, tmax):
        typ = _etype(evt)
        if typ != "drone_state_detailed":
            continue
        data = evt.get("data", {})
        ts = _ts(evt)
        if ts is None: 
            continue

        active = (data.get("system_status_raw") == 4) or (data.get("system_status_name") == "MAV_STATE_ACTIVE")
        armed  = bool(data.get("armed"))
        state_raw = data.get("system_status_raw")

        if last_ts is not None:
            dt = ts - last_ts
            if dt > 0:
                total_time += dt
                if last_active: active_time += dt
                if last_armed:  armed_time  += dt

        if last_state_raw is not None and last_state_raw != state_raw and state_raw == 0:
            uninit_flaps += 1

        last_ts = ts
        last_active = active
        last_armed  = armed
        last_state_raw = state_raw

    if total_time <= 0:
        return {"active_ratio": 0.0, "armed_ratio": 0.0, "uninit_flaps": 0, "sampled": 0}

    return {
        "active_ratio": round(active_time/total_time, 4),
        "armed_ratio":  round(armed_time/total_time, 4),
        "uninit_flaps": uninit_flaps,
        "sampled": int(total_time)
    }

# --------------------------
# ENERGY
# --------------------------
def compute_energy(bus_dvd_path: str, tmin, tmax) -> Dict[str,Any]:
    # 에너지 Wh = ∫ V*I dt / 3600
    last_ts = None
    last_V = None
    last_I = None
    E_Wh = 0.0
    P_samples = []

    for evt in iter_events(bus_dvd_path, tmin, tmax):
        typ = _etype(evt)
        if typ != "drone_state_detailed":
            continue
        data = evt.get("data", {})
        ts = _ts(evt)
        if ts is None: 
            continue
        volts = None
        arr = data.get("battery_voltages_v")
        if isinstance(arr, list) and arr:
            volts = float(arr[0])
        amps = data.get("battery_current_a")
        amps = float(amps) if amps is not None else None

        if volts is None or amps is None:
            continue

        if last_ts is not None:
            dt = ts - last_ts
            if dt > 0 and last_V is not None and last_I is not None:
                P = last_V * last_I  # W
                E_Wh += P * dt / 3600.0
                P_samples.append(P)

        last_ts = ts
        last_V = volts
        last_I = amps

    avg_P = mean(P_samples) if P_samples else 0.0

    # 총 길이 추정
    t0 = tmin
    t1 = tmax
    if t0 is None or t1 is None:
        # rough: 샘플 개수/평균 간격이 없으면 생략
        pass
    total_minutes = (t1 - t0)/60.0 if (t0 is not None and t1 is not None and t1>t0) else None
    energy_per_min = (E_Wh / total_minutes) if (total_minutes and total_minutes>0) else None

    return {
        "energy_Wh": round(E_Wh, 3),
        "avg_power_W": round(avg_P, 2),
        "energy_per_min_Wh": round(energy_per_min, 4) if energy_per_min else None
    }

# --------------------------
# MAIN
# --------------------------
def main():
    ap = argparse.ArgumentParser(description="Compute MTD metrics from bus logs")
    ap.add_argument("--bus", default=DEF_BUS)
    ap.add_argument("--bus-dvd", default=DEF_BUS_DVD)
    ap.add_argument("--outdir", default=DEF_OUTDIR)
    ap.add_argument("--drone-ip", default=DEF_DRONE_IP)
    ap.add_argument("--decoy-ip", default=DEF_DECOY_IP)
    ap.add_argument("--port", type=int, default=DEF_PORT)
    ap.add_argument("--tmin", type=float, default=None, help="start ts (epoch seconds)")
    ap.add_argument("--tmax", type=float, default=None, help="end ts (epoch seconds)")
    ap.add_argument("--shuffle-window", type=float, default=SHUFFLE_WINDOW_S)
    ap.add_argument("--eff-beta", type=float, default=EFFICIENCY_BETA)
    ap.add_argument("--attack-thr", type=float, default=ATTACK_HEAVY_THR_HZ)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # 시간 경계가 없으면 전체 파일에서 첫/마지막 ts 추정
    def _peek_range(path: str) -> Tuple[Optional[float], Optional[float]]:
        t0, t1 = None, None
        for evt in iter_events(path, None, None):
            ts = _ts(evt)
            if ts is None: continue
            if t0 is None: t0 = ts
            t1 = ts
        return t0, t1

    tmin, tmax = args.tmin, args.tmax
    if tmin is None or tmax is None:
        a0,a1 = _peek_range(args.bus)     or (None,None)
        b0,b1 = _peek_range(args.bus_dvd) or (None,None)
        cand = [x for x in [a0,b0] if x is not None]
        if cand: tmin = min(cand) if tmin is None else tmin
        cand = [x for x in [a1,b1] if x is not None]
        if cand: tmax = max(cand) if tmax is None else tmax

    # 계산
    diversity = compute_diversity(args.bus, args.port, tmin, tmax)
    shuffle   = compute_shuffle(args.bus, args.port, args.shuffle_window, args.eff_beta, tmin, tmax)
    redundancy= compute_redundancy(args.bus, args.drone_ip, args.decoy_ip, args.port, tmin, tmax)
    surv      = compute_survivability(args.bus_dvd, tmin, tmax)
    energy    = compute_energy(args.bus_dvd, tmin, tmax)

    report = {
        "meta": {
            "generated_at": _now_iso(),
            "bus": args.bus,
            "bus_dvd": args.bus_dvd,
            "tmin": tmin,
            "tmax": tmax,
            "port": args.port,
            "drone_ip": args.drone_ip,
            "decoy_ip": args.decoy_ip
        },
        "DIVERSITY": diversity,
        "SHUFFLE": shuffle,
        "REDUNDANCY": redundancy,
        "SURVIVABILITY": surv,
        "ENERGY": energy
    }

    # 저장
    out_json = os.path.join(args.outdir, "mtd_metrics.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 요약 텍스트
    out_md = os.path.join(args.outdir, "mtd_metrics_summary.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# MTD Metrics Summary\n\n")
        f.write(f"- 기간: {tmin} ~ {tmax} (epoch)\n")
        f.write(f"- 포트: {args.port}, 드론: {args.drone_ip}, 디코이: {args.decoy_ip}\n\n")

        div = report["DIVERSITY"]
        f.write("## DIVERSITY\n")
        f.write(f"- total_hits: {div['total_hits']}\n")
        f.write(f"- unique_endpoints: {div['unique_endpoints']}\n")
        f.write(f"- diversity_evenness: {div['diversity_evenness']}\n")
        f.write(f"- top1_share: {div['top1_share']}\n\n")

        sh  = report["SHUFFLE"]
        f.write("## SHUFFLE\n")
        f.write(f"- shuffle_count: {sh['shuffle_count']}\n")
        f.write(f"- shuffle_rate_per_min: {sh['shuffle_rate_per_min']}\n")
        f.write(f"- mean_pre_post_drop: {sh['mean_pre_post_drop']}\n")
        f.write(f"- mean_retarget_time_s: {sh['mean_retarget_time_s']}\n")
        f.write(f"- efficiency_score: {sh['efficiency_score']}\n\n")

        red = report["REDUNDANCY"]
        f.write("## REDUNDANCY\n")
        f.write(f"- decoy_share_during_attacks: {red['decoy_share_during_attacks']}\n")
        f.write(f"- failover_incidents: {red['failover_incidents']}\n\n")

        sv  = report["SURVIVABILITY"]
        f.write("## SURVIVABILITY\n")
        f.write(f"- active_ratio: {sv['active_ratio']}\n")
        f.write(f"- armed_ratio: {sv['armed_ratio']}\n")
        f.write(f"- uninit_flaps: {sv['uninit_flaps']}\n\n")

        en  = report["ENERGY"]
        f.write("## ENERGY\n")
        f.write(f"- energy_Wh: {en['energy_Wh']}\n")
        f.write(f"- avg_power_W: {en['avg_power_W']}\n")
        f.write(f"- energy_per_min_Wh: {en['energy_per_min_Wh']}\n")

    print(f"✅ saved: {out_json}")
    print(f"✅ saved: {out_md}")

if __name__ == "__main__":
    main()
