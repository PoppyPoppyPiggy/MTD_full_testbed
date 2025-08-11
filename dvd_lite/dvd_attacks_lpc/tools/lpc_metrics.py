#!/usr/bin/env python3
# effect_timeline.csv → 임팩트 메트릭 산출 (합계/누적 중심)
import sys, csv, re, os

TL = sys.argv[1] if len(sys.argv)>1 else "attack_output/effect_timeline.csv"
OUT= sys.argv[2] if len(sys.argv)>2 else "attack_output/metrics.csv"

effects=[]
with open(TL) as f:
    r=csv.DictReader(f)
    for row in r:
        effects.append(row)

def sum_numeric(prefix, absval=False, percent_as_abs=False):
    s=0.0
    for e in effects:
        if e["effect"].startswith(prefix):
            m=re.findall(r'[-+]?\d*\.?\d+', e["value"])
            if not m: continue
            v=float(m[0])
            if percent_as_abs and "%" in e["value"]:
                v=abs(v)  # 퍼센트는 절댓값 합산 권장
            elif absval:
                v=abs(v)
            s+=v
    return s

metrics = {
  # 항법/임무 편향
  "position_drift_m":    sum_numeric("position_drift", absval=False),
  "mission_bias_sum":    sum_numeric("mission_bias", absval=False),
  "wp_deviation_m":      sum_numeric("wp_deviation", absval=False),

  # 에너지/비행시간 (기존 모듈과 호환)
  "energy_delta_Wh":     sum_numeric("energy_delta", absval=False),
  "flight_time_loss":    sum_numeric("flight_time_loss", absval=False),

  # 링크 품질 (ns-3로 일부 재현)
  "link_jitter_ms":      sum_numeric("link_jitter", absval=False),
  "packet_loss_pct":     sum_numeric("packet_loss", absval=False),

  # 융합/운용
  "sensor_residual":     sum_numeric("sensor_residual", absval=True),
  "rth_margin_pct":      sum_numeric("rth_margin", percent_as_abs=True),

  # 전체 이벤트 수
  "events_total":        len(effects),
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT,'w',newline='') as f:
    w=csv.writer(f); w.writerow(["metric","value"])
    for k,v in metrics.items(): w.writerow([k,v])

print(f"[metrics] wrote {OUT}")
