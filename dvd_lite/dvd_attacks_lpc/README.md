FANET HoneyDrone MTD 테스트베드 — LPC 생애주기 & NS-3 연동 운영서
개요

목표: 공격–방어(MTD)–재탐색(Probe)의 LPC(Loose Persistent Campaign) 생애주기를 표준 로그(bus.log)로 수집 → 규칙 기반 effect_timeline.csv로 정량화 → NS-3에서 성능지표(ns3_metrics.csv*) 산출 → MTD 점수로 보고.

적용 코드: dvd_lite/dvd_attacks_lpc/*(공격/방어/재탐색), tools/*(로거/워처/타임라인/스코어러), ns-3.45/ns-3-dev/scratch/*(drone_lpc_eval.cc, honeydrone_netanim.cc).

생애주기(End-to-End) 플로우

환경 로드: DVD 도커 컨테이너 기동, NS-3 초기화.

시나리오 선택: 연속/동시/사용자 정의(예: scenarios/S_lpc_multi.pipeline).

공격 수행: 모듈 실행(예: follow_flood, wifi_slow_scan 등).

이벤트 로깅: 모든 공격/방어/CTI 이벤트를 bus.log에 표준 스키마로 기록.

타임라인 생성: gen_effects_timeline.py → effect_timeline.csv (열: time,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps).

NS-3 시뮬레이션

단일 드론 평가: drone_lpc_eval (DVD 컨테이너 인터페이스와 직접 연계된 CSMA 링크·서비스 포트 RX 측정).

허니드론 네트워크 평가: honeydrone_netanim (여러 드론/디코이 노드, 802.11 ad-hoc, TapBridge 옵션).

특성/메트릭 추출: ns3_metrics*.csv, ns3_metrics_summary*.csv 생성.

강화학습·최적화 입력: bus/타임라인/NS-3 메트릭을 에피소드 데이터로 적재.

정책 평가: MTD 빈도·복구 속도·비용 분석.

시각화/리포트: NetAnim XML, MTD 점수표(Markdown/CSV) 출력.

역할 정리

drone_lpc_eval → 단일 드론(GCS/CC/FC/SIM, CSMA) 서비스 포트 기반 직접 패킷 영향 분석.

honeydrone_netanim → 허니드론 네트워크(Wi-Fi ad-hoc, 다노드)에서 공격의 네트워크 관점 영향도와 MTD에 의한 경로·가용성 회복을 정량화.

표준 로그 스키마

파일: dvd_lite/dvd_attacks_lpc/attack_output/bus.log

형식(공통):
time=<epoch> tag=<attack|mtd|cti|probe|obs> module=<name> k=v …

예시:

공격: time=12 tag=attack module=follow_flood ip=10.30.0.5 port=14550 pps=1000 pkt=250 dur=8

MTD: time=30 tag=mtd action=ip_shuffle old=10.30.0.5 new=10.30.0.77 cutover=1

CTI(도커 변화 감지): time=31 tag=cti type=port_change svc=mavlink old=14550 new=18321 src=dvd_fc

관측: time=32 tag=obs name=rx_delta node=GCS:14550 rx_pkts=0->250

실행 예시
(A) DVD 기동
# DVD Lite 모드 기동(예: 무선 비활성)
sudo ./start.sh --mode lite --no-wifi

(B) 공격/방어 실행 & 이벤트 로깅
# bus.log 위치 지정(없으면 자동 생성)
export BUS_LOG=$PWD/dvd_lite/dvd_attacks_lpc/attack_output/bus.log

# 도커 변화도 워처(CTI) 상시 구동
bash dvd_lite/dvd_attacks_lpc/tools/cti_watch_dvd.sh --interval 1s &

# 예: follow_flood 60초, 중간에 PortHop + IPShuffle 트리거
python3 dvd_lite/dvd_attacks_lpc/run_attack.py \
  --module follow_flood --dur 60 --intensity med --allow-real-effects 0

# (필요 시) 방어: mtd_port_hop_mavlink.sh, mtd_ip_shuffle.sh 직접 실행 가능

(C) 타임라인 생성
python3 dvd_lite/dvd_attacks_lpc/tools/gen_effects_timeline.py \
  --bus $BUS_LOG \
  --rules dvd_lite/dvd_attacks_lpc/tools/effects_rules.json \
  --out  dvd_lite/dvd_attacks_lpc/attack_output/effect_timeline.csv

D) NS-3 실행 (./ns3 런처 사용)

먼저 ns-3 루트로 이동:

cd ns-3.45/ns-3-dev

1) 설정 & 빌드
# (최초 1회) 구성
./ns3 configure --build-profile=optimized --enable-examples --enable-tests

# 빌드
./ns3 build


참고

scratch/drone_lpc_eval.cc, scratch/honeydrone_netanim.cc가 그대로 감지되어 빌드됩니다.

다시 빌드 없이 바로 실행하려면 뒤의 run에 --no-build 옵션을 붙이세요.

2) 단일 드론 평가 — drone_lpc_eval
./ns3 run "drone_lpc_eval \
  --module=follow_flood \
  --level=med \
  --mtd=1 \
  --simTime=60 \
  --animMaxPkts=200000"

# 출력(변경 없음):
# dvd_lite/dvd_attacks_lpc/attack_output/follow_flood/mtd/
#  ├─ ns3_metrics_follow_flood_mtd.csv
#  ├─ ns3_metrics_summary_follow_flood_mtd.csv
#  └─ follow_flood_mtd.xml (NetAnim)


옵션 요약

--module: 공격 모듈(follow_flood | wifi_slow_scan | telemetry_trickle_jam …)

--level: low | med | high (효과 매핑 테이블 적용)

--mtd=1: 포트홉/아이피 셔플/브리지 홉 스케줄 적용

--simTime: 시뮬레이션 총 시간(초)

--animMaxPkts: NetAnim 기록 패킷 상한(0=무제한)

3) 허니드론 네트워크 평가 — honeydrone_netanim
./ns3 run "honeydrone_netanim \
  --timeline=../../dvd_lite/dvd_attacks_lpc/attack_output/effect_timeline.csv \
  --module=follow_flood \
  --simTime=60 \
  --honey=4 \
  --pcap=1"

# 출력(변경 없음):
# dvd_lite/dvd_attacks_lpc/attack_output/
#  ├─ ns3_wifi-*.pcap
#  ├─ ns3_metrics.csv
#  ├─ ns3_metrics_summary.csv
#  └─ follow_flood.xml (NetAnim)


옵션 요약

--timeline: gen_effects_timeline.py로 만든 effect_timeline.csv 경로

--honey: 가상 허니드론 노드 수

--pcap=1: 무선 캡처 파일 저장

4) (선택) 빠른 재실행

빌드된 상태에서 빠르게 돌릴 땐:

./ns3 run --no-build "drone_lpc_eval --module=wifi_slow_scan --mtd=0 --simTime=30"
./ns3 run --no-build "honeydrone_netanim --timeline=../../dvd_lite/dvd_attacks_lpc/attack_output/effect

(E) MTD 점수 산출(정량)
python3 dvd_lite/dvd_attacks_lpc/tools/score_mtd.py \
  --bus    dvd_lite/dvd_attacks_lpc/attack_output/bus.log \
  --ns3dir dvd_lite/dvd_attacks_lpc/attack_output/follow_flood/mtd \
  --out    dvd_lite/dvd_attacks_lpc/attack_output/mtd_report.md

2) “도커 인스턴스 변화도”를 어디서/어떻게 잡아 bus.log에 남기나?

아래 두 유틸을 표준으로 추가합니다.

(A) 표준 로거: tools/log_event.sh
#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/tools/log_event.sh
set -euo pipefail
LOG=${BUS_LOG:-"$(pwd)/dvd_lite/dvd_attacks_lpc/attack_output/bus.log"}
mkdir -p "$(dirname "$LOG")"
ts=$(date +%s)
tag=$1; shift || true
printf "time=%s tag=%s %s\n" "$ts" "$tag" "$*" >> "$LOG"


모든 공격/MTD/Probe 스크립트에서 source tools/log_event.sh 후
log_event attack module=follow_flood ip=... port=... 처럼 호출.

(B) 도커 변화도 워처(CTI): tools/cti_watch_dvd.sh
#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/tools/cti_watch_dvd.sh
# DVD 컨테이너(GCS/CC/FC/SIM)의 IP/포트/브리지 상태를 주기적으로 스냅샷.
set -euo pipefail
. "$(dirname "$0")/log_event.sh"
INTERVAL="${1:-1s}"

STATE="$(mktemp)"; trap 'rm -f "$STATE"' EXIT

function snap_json() {
  # 컨테이너 목록은 환경에 맞게 조정
  local arr=(dvd_gcs dvd_cc dvd_fc dvd_sim)
  echo "{"; for c in "${arr[@]}"; do
    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$c" 2>/dev/null || echo "")
    # MAVLink/서비스 포트(UDP listen) 수집
    ports=$(docker exec "$c" sh -lc "ss -lunH | awk '{print \$5}' | awk -F: '{print \$NF}' | sort -n | tr '\n' ','" 2>/dev/null || echo "")
    br=$(docker exec "$c" sh -lc "brctl show 2>/dev/null | awk 'NR>1{print \$1\":\"\$4}' | tr '\n' ','" 2>/dev/null || echo "")
    printf '"%s":{"ip":"%s","udp":"%s","bridge":"%s"},' "$c" "$ip" "$ports" "$br"
  done | sed 's/,$//'
  echo "}"
}

function diff_and_log() {
  local old="$1" new="$2"
  # ip 변화
  for c in dvd_gcs dvd_cc dvd_fc dvd_sim; do
    old_ip=$(jq -r --arg c "$c" '.[$c].ip // empty' "$old" 2>/dev/null || true)
    new_ip=$(jq -r --arg c "$c" '.[$c].ip // empty' "$new" 2>/dev/null || true)
    if [[ -n "$old_ip" && -n "$new_ip" && "$old_ip" != "$new_ip" ]]; then
      log_event cti type=ip_change src="$c" old="$old_ip" new="$new_ip"
    fi
    old_ports=$(jq -r --arg c "$c" '.[$c].udp // empty' "$old" 2>/dev/null || true)
    new_ports=$(jq -r --arg c "$c" '.[$c].udp // empty' "$new" 2>/dev/null || true)
    if [[ -n "$old_ports" && -n "$new_ports" && "$old_ports" != "$new_ports" ]]; then
      log_event cti type=port_change src="$c" udp_old="$old_ports" udp_new="$new_ports"
    fi
    old_br=$(jq -r --arg c "$c" '.[$c].bridge // empty' "$old" 2>/dev/null || true)
    new_br=$(jq -r --arg c "$c" '.[$c].bridge // empty' "$new" 2>/dev/null || true)
    if [[ -n "$old_br" && -n "$new_br" && "$old_br" != "$new_br" ]]; then
      log_event cti type=bridge_change src="$c" old="$old_br" new="$new_br"
    fi
  done
}

# 루프
prev="$(mktemp)"
snap_json > "$prev"
while true; do
  sleep "$INTERVAL"
  now="$(mktemp)"; snap_json > "$now"
  diff_and_log "$prev" "$now"
  mv "$now" "$prev"
done


어디서 파악? docker inspect(IP), docker exec ss -lun(UDP 리슨 포트), brctl show(브리지/포워딩).

어떻게 남기나? 변화 감지 시 tag=cti 라인의 키–값 로그로 bus.log에 기록.

MTD 연계: mtd_ip_shuffle.sh, mtd_port_hop_mavlink.sh, mtd_bridge_hop.sh 실행 즉시 선언적 MTD 이벤트를 남기고, 워처가 **사실 변화(실제 IP/포트/브리지 변경)**를 별도로 검증·추적해 cti 이벤트를 남깁니다. 두 라인이 시간상 붙어서 찍히므로 정책엔진/NS-3 타임라인 생성이 쉬워집니다.

원 DVD는 start.sh가 자체 dvd.log를 만들지만, 공격/방어/탐지의 연구용 근거는 본 테스트베드 bus.log에 통일합니다. 원 프로젝트의 로그 존재(운영 로그)는 참고만 하세요. 
GitHub

3) MTD 스코어링(정량) — tools/score_mtd.py

아래 스코어러는 NS-3 요약/시계열과 bus.log를 함께 읽어 “MTD 성능 지표”를 계산합니다.
(그림의 KPI 5종: DIVERSITY/SHUFFLE/REDUNDANCY/SURVIVABILITY/ENERGY 반영)

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

4) 공격/방어 모듈에서의 로그 합의(계약)

각 스크립트 상단에 공통 include:

# 예: dvd_lite/dvd_attacks_lpc/modules/atk_follow_flood.sh
. "$(dirname "$0")/../tools/log_event.sh"
log_event attack module=follow_flood ip="$DST_IP" port="$DST_PORT" pps="$RATE_PPS" pkt="$PKT"
# … 실행 …
log_event obs name=tx_start flow=atk_flood_gcs


MTD 스크립트 예(포트 홉):

# dvd_lite/dvd_attacks_lpc/modules/mtd_port_hop_mavlink.sh
. "$(dirname "$0")/../tools/log_event.sh"
log_event mtd action=port_hop proto=udp old="$OLD" new="$NEW" grace="$GRACE"
# 실제 iptables/socat 설정 …
sleep "$GRACE"
log_event mtd action=port_hop_cutover old="$OLD" new="$NEW" drop_old=1


Probe/CTI 예:

# probe_follow_mavlink.sh 가 새 포트 확인 시
log_event cti type=port_change svc=mavlink old="$OLD" new="$NEW" src=dvd_fc
log_event probe name=follow_mavlink status=resume port="$NEW"


이렇게 남긴 bus.log + cti_watch_dvd.sh의 사실 변화 기록이 합쳐져, tools/gen_effects_timeline.py가 **규칙(effects_rules.json)**에 따라 손실/지연/지터/레이트 리밋을 시간축으로 생성합니다. (ns-3 두 프로그램은 이미 effect_timeline.csv를 읽어 전송 손실/중복률/레이트 제한을 실효 적용하고, 요약·시계열 CSV를 생성하도록 구현돼 있습니다: drone_lpc_eval.cc / honeydrone_netanim.cc.)

5) 산출물(예시)

attack_output/bus.log

attack_output/effect_timeline.csv

attack_output/follow_flood/mtd/ns3_metrics_follow_flood_mtd.csv

attack_output/follow_flood/mtd/ns3_metrics_summary_follow_flood_mtd.csv

attack_output/follow_flood/mtd/follow_flood_mtd.xml (NetAnim)

attack_output/mtd_report.md (MTD 점수표)

부록 A — 왜 “단일/허니드론” 두 평가가 필요한가?

drone_lpc_eval: 서비스 포트 기반으로 DVD 컨테이너와 직접 연계하여 공격·MTD가 업무 트래픽(GCS↔Flight/Companion/Simulator)에 미친 영향(손실/중복/처리량)을 정밀하게 얻습니다.

honeydrone_netanim: 실제 현장과 유사한 다수 노드의 무선 토폴로지에서, 동일 타임라인을 **네트워크 관점(경로, 캡처, NetAnim)**으로 재현해 분산·복구·분리 효과를 확인합니다.

부록 B — 원 프로젝트 참고(운영 로그)

Damn-Vulnerable-Drone의 start.sh/stop.sh/status.sh는 시뮬레이터 운영 로그 dvd.log를 남깁니다. 본 연구 파이프라인의 근거 데이터는 bus.log이므로, 공격/방어/CTI 이벤트는 반드시 위 표준 로거로 남겨 주세요. 
GitHub

바로 적용 체크리스트

 tools/log_event.sh, tools/cti_watch_dvd.sh 추가 및 공격/MTD/Probe 스크립트에서 호출

 BUS_LOG 환경변수 지정(미지정 시 기본 경로 자동 생성)

 gen_effects_timeline.py 실행으로 effect_timeline.csv 생성

 drone_lpc_eval/honeydrone_netanim 실행

 tools/score_mtd.py로 MTD 점수표 생성

메모

위 스코어링 식/가중치는 리포트의 DIVERSITY/SHUFFLE/REDUNDANCY/SURVIVABILITY/ENERGY 프레임과 1:1 매핑되도록 설계했습니다. 필요 시 환경(링크 대역/패킷크기/시뮬시간)에 따라 정규화 구간(pct() 인자)만 조정하면 됩니다.

NetAnim XML은 결과 재생용이며, drone_lpc_eval에서는 서비스 포트별 cti_events_*.csv도 함께 출력되도록(이미 코드 반영됨) 구성해서, 로그(bu s.log)–타임라인–NS-3가 서로 참조 가능합니다.