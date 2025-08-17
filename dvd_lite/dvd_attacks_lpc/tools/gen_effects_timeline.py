#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
버스 로그(bus.log) → effect_timeline.csv 변환기 (규칙파일 적용)
- 입력: bus.log (형식: [ISO8601] [module_name] key=val key=val ...)
- 규칙: effects_rules.json (module: {low/medium/high: {...}})
- 출력: effect_timeline.csv (t, loss_pct, delay_ms, jitter_ms, dup_pct, rate_limit_mbps)
사용 예:
  python3 tools/gen_effects_timeline.py attack_output/bus.log \
    -o attack_output/effect_timeline.csv \
    --rules tools/effects_rules.json
"""

import argparse, csv, json, os, re, sys
from datetime import datetime

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("buslog", help="path to attack_output/bus.log")
    ap.add_argument("-o", "--out", default="attack_output/effect_timeline.csv",
                    help="output CSV path (default: attack_output/effect_timeline.csv)")
    ap.add_argument("--rules", required=True, help="path to effects_rules.json")
    ap.add_argument("--tz-naive", action="store_true",
                    help="treat timestamps without timezone as localtime (default: parse as naive ISO)")
    return ap.parse_args()

# 버스 라인 포맷: [timestamp] [module] k=v k=v ...
RE_LINE = re.compile(r'^\s*\[(.*?)\]\s*\[(.*?)\]\s*(.*)$')

def parse_ts(s, tz_naive=False):
    """
    ts 문자열을 epoch(sec)로 변환.
    허용: ISO8601 ('2025-08-14T12:34:56' 혹은 '2025-08-14 12:34:56', '...Z', '+09:00' 등)
    """
    s = s.strip()
    # 공백 → T 치환
    s2 = s.replace(" ", "T")
    # Z → +00:00
    if s2.endswith("Z"):
        s2 = s2[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s2)
        # Python 3.11+: aware이면 utcoffset 적용, naive면 그대로 timestamp()
        if dt.tzinfo is None and tz_naive:
            # naive → 시스템 로컬 타임존 기준으로 간주하고 epoch 환산
            # (여기서는 naive 그대로 timestamp() 호출; 로컬 시스템 가정)
            return dt.timestamp()
        return dt.timestamp()
    except Exception:
        # 마지막 fallback: 숫자로 들어온 epoch 문자열
        try:
            return float(s)
        except Exception:
            return None

def main():
    args = parse_args()

    # 경로 검증
    if not os.path.isfile(args.buslog):
        print(f"[ERR] bus.log not found: {args.buslog}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(args.rules):
        print(f"[ERR] effects_rules.json not found: {args.rules}", file=sys.stderr)
        sys.exit(2)

    # 규칙 로드
    with open(args.rules, "r", encoding="utf-8") as f:
        rules = json.load(f)

    rows = []
    with open(args.buslog, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = RE_LINE.match(line.strip())
            if not m: 
                continue
            ts_raw, mod_raw, kv_str = m.groups()
            mod = (mod_raw or "").strip().lower()

            # k=v 파싱
            kv = {}
            for tok in kv_str.split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    kv[k.strip().lower()] = v.strip()

            # 강도 선택: phase 우선 → intensity → default=low
            phase = (kv.get("phase") or "").lower()
            intensity = (kv.get("intensity") or "low").lower()

            eff = None
            if mod in rules:
                r = rules[mod]
                if phase and phase in r:
                    eff = r[phase]
                elif intensity in r:
                    eff = r[intensity]

            if eff is None:
                # 규칙 없음 → 0으로 채움
                eff = {
                    "loss_pct": 0.0, "delay_ms": 0.0, "jitter_ms": 0.0,
                    "dup_pct": 0.0, "rate_limit_mbps": 0.0
                }

            t = parse_ts(ts_raw, tz_naive=args.tz_naive)
            if t is None:
                # 타임스탬프 파싱 실패 라인 스킵
                continue

            rows.append((
                t,
                float(eff.get("loss_pct", 0.0)),
                float(eff.get("delay_ms", 0.0)),
                float(eff.get("jitter_ms", 0.0)),
                float(eff.get("dup_pct", 0.0)),
                float(eff.get("rate_limit_mbps", 0.0)),
                mod,                               # 참고용: 어떤 모듈의 효과인지
                phase if phase else intensity      # 참고용: 강도
            ))

    rows.sort(key=lambda x: x[0])

    # 출력
    outp = args.out
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with open(outp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t","loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps","module","level"])
        for r in rows:
            w.writerow(r)

    print(f"[OK] effect timeline -> {outp} rows={len(rows)}")

if __name__ == "__main__":
    main()
