#!/usr/bin/env bash
set -Eeuo pipefail
# 전역 타임라인 → 시나리오별 타임라인(+레벨 강도, MTD 감쇠, 교차 영향, zero 보정)
# 사용: mk_timeline_for_scenario.sh <module> <mode> <level> <global_timeline.csv> <out_csv>

mod="${1:?module}"; mode="${2:?mode(no_mtd|mtd)}"; level="${3:?level(low|med|high)}"
in="${4:?global timeline csv}"; out="${5:?out csv}"
mkdir -p "$(dirname "$out")"

# --- 대상 포트 매핑(공격 타깃) ---
# 합법 포트(교차 영향 시 사용)
LEGIT_PORTS=(5760 5000 8000)
case "$mod" in
  follow_flood)          TARGET_PORTS=(14550 8000)  ; CROSS_IMPACT=1 ;; # 플러드 → 합법 흐름도 흔들림
  follow_mavlink)        TARGET_PORTS=(14550)       ; CROSS_IMPACT=0 ;;
  wifi_slow_scan)        TARGET_PORTS=(8080)        ; CROSS_IMPACT=1 ;; # 스캔 → 채널 혼잡 전파
  telemetry_trickle_jam) TARGET_PORTS=(5760)        ; CROSS_IMPACT=0 ;;
  *)                     TARGET_PORTS=(14550)       ; CROSS_IMPACT=0 ;;
esac

# --- 레벨별 강도 스케일(원 타임라인 값에 곱; rate_limit는 나눔) ---
# 필요시 환경변수로 덮어쓰기 가능: SCALE_LOW=0.7 SCALE_MED=1.0 SCALE_HIGH=1.5
SCALE_LOW="${SCALE_LOW:-0.7}"
SCALE_MED="${SCALE_MED:-1.0}"
SCALE_HIGH="${SCALE_HIGH:-1.5}"
case "$level" in
  low)  SCALE="$SCALE_LOW" ;;
  med)  SCALE="$SCALE_MED" ;;
  high) SCALE="$SCALE_HIGH" ;;
esac

# --- MTD 감쇠(모드별 완화 정도; 값이 작을수록 방어가 강함) ---
# 필요시 환경변수로 덮어쓰기: ATTEN_NO=1.0 ATTEN_LOW=0.8 ATTEN_MED=0.6 ATTEN_HIGH=0.4
ATTEN_NO="${ATTEN_NO:-1.0}"
ATTEN_LOW="${ATTEN_LOW:-0.8}"
ATTEN_MED="${ATTEN_MED:-0.6}"
ATTEN_HIGH="${ATTEN_HIGH:-0.4}"
if [[ "$mode" == "no_mtd" ]]; then
  ATTEN="$ATTEN_NO"
else
  case "$level" in
    low)  ATTEN="$ATTEN_LOW" ;;
    med)  ATTEN="$ATTEN_MED" ;;
    high) ATTEN="$ATTEN_HIGH" ;;
  esac
fi

# --- zero 타임라인(전역이 전부 0) 보정용 모듈/레벨 기본 프로파일 ---
# 값은 ns-3 내부 fallback(effects)와 일관되게 설정
default_profile_json="$(cat <<'JSON'
{
  "follow_mavlink":        {"low":{"loss":0.0,"jitter":1.0,"delay":0.0,"dup":0.0,"rate":0.0},
                            "med":{"loss":0.0,"jitter":1.0,"delay":0.0,"dup":0.0,"rate":0.0},
                            "high":{"loss":0.0,"jitter":1.0,"delay":0.0,"dup":0.0,"rate":0.0}},
  "follow_flood":          {"low":{"loss":2.0,"jitter":2.0,"delay":0.0,"dup":0.0,"rate":0.0},
                            "med":{"loss":4.0,"jitter":4.0,"delay":0.0,"dup":0.0,"rate":0.0},
                            "high":{"loss":6.0,"jitter":6.0,"delay":0.0,"dup":0.0,"rate":0.0}},
  "wifi_slow_scan":        {"low":{"loss":1.5,"jitter":0.8,"delay":0.5,"dup":0.0,"rate":0.0},
                            "med":{"loss":3.2,"jitter":2.1,"delay":1.2,"dup":0.1,"rate":0.0},
                            "high":{"loss":6.8,"jitter":4.5,"delay":2.8,"dup":0.3,"rate":0.0}},
  "telemetry_trickle_jam": {"low":{"loss":2.1,"jitter":1.5,"delay":2.0,"dup":0.0,"rate":0.0},
                            "med":{"loss":5.5,"jitter":4.2,"delay":8.0,"dup":0.2,"rate":0.0},
                            "high":{"loss":8.0,"jitter":6.0,"delay":12.0,"dup":0.4,"rate":0.0}}
}
JSON
)"

python3 - "$in" "$out" "$mod" "$mode" "$level" "$SCALE" "$ATTEN" "$CROSS_IMPACT" "${TARGET_PORTS[@]}" "${LEGIT_PORTS[@]}" <<'PY'
import sys, csv, json, math
src,dst,mod,mode,level,scale,atten,cross=sys.argv[1:9]
scale=float(scale); atten=float(atten); cross=int(cross)
argv=sys.argv[9:]
# split target and legit arrays (half-half)
n_t=int((len(argv))/2)
tports=list(map(int,argv[:n_t])); lports=list(map(int,argv[n_t:]))

default=json.loads("""__DEFAULT__""".replace("__DEFAULT__", """REPLACE_ME"""))
prof=default.get(mod, default["follow_flood"])[level]

rows=[]
with open(src,newline='') as f:
    r=csv.DictReader(f)
    base_cols=["t","loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"]
    for k in base_cols:
        assert k in r.fieldnames, f"missing column {k}"
    zero=True
    buf=[]
    for row in r:
        vals=[float(row["loss_pct"]),float(row["delay_ms"]),float(row["jitter_ms"]),
              float(row["dup_pct"]),float(row["rate_limit_mbps"])]
        if any(v!=0.0 for v in vals): zero=False
        buf.append(row)
    # zero → 기본 프로파일로 채움(상시 일정 효과)
    if zero:
        for row in buf:
            row["loss_pct"]=prof["loss"]
            row["delay_ms"]=prof["delay"]
            row["jitter_ms"]=prof["jitter"]
            row["dup_pct"]=prof["dup"]
            row["rate_limit_mbps"]=prof["rate"]
    # 스케일/감쇠 적용
    for row in buf:
        for k in ("loss_pct","delay_ms","jitter_ms","dup_pct"):
            row[k]=float(row[k]) * scale * atten
        # rate_limit: 값이 0보다 크면 스케일은 더 엄격 → 값/scale, 이후 MTD는 완화 → 값/atten (atten<1이면 증가)
        rl=float(row["rate_limit_mbps"])
        if rl>0:
            rl=rl/max(scale,1e-9)
            rl=rl/max(atten,1e-9)
        row["rate_limit_mbps"]=rl
    rows=buf

# 교차 영향: 필요 모듈은 합법 포트에도 적용
apply_ports=set(tports)
if cross:
    apply_ports.update(lports)

# 출력
hdr = list(rows[0].keys())
if "dstPort" not in hdr: hdr += ["dstPort"]
if "flowTag" not in hdr: hdr += ["flowTag"]

with open(dst,'w',newline='') as g:
    w=csv.writer(g); w.writerow(hdr)
    for row in rows:
        base=[row.get(k,"") for k in hdr]
        for p in sorted(apply_ports):
            rr=base[:]
            # dstPort 채우기
            if "dstPort" in hdr:
                idx=hdr.index("dstPort")
                if len(rr)<=idx: rr+=[""]*(idx-len(rr)+1)
                rr[idx]=str(p)
            # flowTag 비움
            if "flowTag" in hdr:
                idx=hdr.index("flowTag")
                if len(rr)<=idx: rr+=[""]*(idx-len(rr)+1)
                rr[idx]=""
            w.writerow(rr)
print(f"[mk_timeline_for_scenario] scale={scale} atten={atten} cross={cross} targets={sorted(apply_ports)} → {dst}")
PY
