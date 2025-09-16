#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
아주 간단한 정책 루프(강화학습 자리에 들어갈 '작동하는' 버전)
- 슬라이딩 윈도우 내 UDP 히트: Drone IP(.3) 는 페널티, Decoy(.100)은 보상
- 보상에 따라 shuffle_interval_s ↑/↓ 조정
- 결과를 /shared/mtd_policy.json 에 반영 → mtd_engine v6 가 즉시 적용
"""

import os, sys, json, time, collections
from datetime import datetime, timezone

LPC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BUS_LOG = os.path.join(LPC_DIR, "bus", "bus.log")
POLICY_FILE = os.getenv("POLICY_FILE", os.path.join(LPC_DIR, "mtd", "shared_state", "..", "shared", "mtd_policy.json"))
STATE_FILE  = os.getenv("STATE_FILE",  os.path.join(LPC_DIR, "mtd", "shared_state", "mtd_state.json"))

WINDOW_SEC = float(os.getenv("RL_WINDOW_SEC", "20"))
ADJUST_COOLDOWN = float(os.getenv("RL_ADJUST_COOLDOWN", "5"))
MIN_INTERVAL = 3.0
MAX_INTERVAL = 60.0
STEP = 2.0  # 초 단위

def iso_now():
    return datetime.now(timezone.utc).isoformat()

def read_policy():
    try:
        with open(POLICY_FILE, "r", encoding="utf-8") as f:
            p = json.load(f)
            if isinstance(p, dict): return p
    except Exception: pass
    return {"strategy":"ip_shuffle","shuffle_interval_s":15}

def write_policy(pol):
    os.makedirs(os.path.dirname(POLICY_FILE), exist_ok=True)
    with open(POLICY_FILE, "w", encoding="utf-8") as f:
        json.dump(pol, f, indent=2)

def current_target_ip():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
            cur = s.get("current_target","")
            if ":" in cur: return cur.split(":")[0]
            return cur
    except Exception:
        return ""

def reward_of(evt) -> float:
    # drone: 10.13.0.3, decoy: 10.13.0.100 가정
    dip = evt.get("dst_ip")
    if not dip: return 0.0
    if dip.endswith(".3"):    # 진짜 드론
        return -1.0
    if dip.endswith(".100"):  # 디코이
        return +0.5
    return 0.0

def main():
    # 초간단 tail
    last_adj = 0.0
    hits = collections.deque() # (ts, reward)
    pol = read_policy()
    interval = float(pol.get("shuffle_interval_s", 15))

    # bus.log 끝으로
    try:
        f = open(BUS_LOG, "r", encoding="utf-8")
        f.seek(0, os.SEEK_END)
    except Exception as e:
        print(f"[rl] cannot open bus: {e}")
        return

    print(f"[rl] start | interval={interval}s | window={WINDOW_SEC}s | step={STEP}s")
    while True:
        p = f.tell()
        line = f.readline()
        if not line:
            time.sleep(0.2)
            f.seek(p)
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue

        etype = evt.get("type") or evt.get("event_type") or ""
        data  = evt.get("data") or {}
        # udp_packet 스키마 흡수
        dip = evt.get("dst_ip") or data.get("dst_ip")
        dport = evt.get("dst_port") or data.get("dst_port")
        ts = evt.get("ts") or time.time()

        if etype in ("udp_packet","udp_packet_rx","udp_packet_tx","net_packet"):
            if str(dport) == "14550":
                r = reward_of({"dst_ip": dip})
                hits.append((ts, r))
                # 슬라이딩
                while hits and (ts - hits[0][0] > WINDOW_SEC):
                    hits.popleft()

                R = sum(x for _,x in hits)
                # 간단 정책: 보상이 낮으면 인터벌 ↓, 높으면 ↑
                if (ts - last_adj) > ADJUST_COOLDOWN:
                    if R < -2.0 and interval > MIN_INTERVAL:
                        interval = max(MIN_INTERVAL, interval - STEP)
                    elif R > +2.0 and interval < MAX_INTERVAL:
                        interval = min(MAX_INTERVAL, interval + STEP)
                    # 정책 저장
                    pol["shuffle_interval_s"] = float(interval)
                    write_policy(pol)
                    last_adj = ts
                    # 메타 이벤트: 보상/정책 기록
                    meta = {
                        "timestamp": iso_now(),
                        "ts": ts,
                        "type": "mtd_policy_update",
                        "interval_s": interval,
                        "reward_window": R,
                        "window_len": len(hits)
                    }
                    print(json.dumps(meta), flush=True)

if __name__ == "__main__":
    main()
