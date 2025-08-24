#!/usr/bin/env bash
# 대량 수집 파이프라인 (공격/CTI/MTD -> bus.log -> timeline -> (옵션) NS-3 -> score/dataset/train)
# 사용 예:
#   N=200 RUN_NS3=0 scripts/auto_collect.sh          # 아주 빠르게 공격데이터만 모으기
#   N=50  RUN_NS3=1 ATK_RATE_MBPS=30 scripts/auto_collect.sh
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"

# ---------- 옵션/환경 ----------
: "${ALLOW_REAL_EFFECTS:=1}"            # DVD 내부에서만 1
: "${DVD_C_GCS:=ground-control-station}"
: "${DVD_TARGET_IF:=eth0}"
: "${DVD_MAVLINK_PORT:=14550}"
: "${N:=50}"                             # 반복 횟수
: "${RUN_NS3:=1}"                        # 0=생략, 1=실행
: "${ATK_RATE_MBPS:=30}"                 # NS-3 공격 onoff 레이트 (Mbps)
: "${SIM_TIME:=60}"                      # NS-3 시뮬 시간(sec)
: "${PORT_HOP_PROB:=50}"                 # 매 라운드 포트 hop 수행 확률(%)
: "${FOLLOW_FLOOD_PROB:=50}"             # follow_flood 선택 확률(%), 아니면 follow_mavlink
: "${CTI_WAIT_S:=0.5}"                   # MTD 직후 CTI 반영 대기(sec)

# ---------- 로그 초기화 ----------
mkdir -p attack_output
: > attack_output/bus.log
: > attack_output/run.log

# ---------- Docker 네트워크/CTI IF ----------
NET_NAME="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' "$DVD_C_GCS" 2>/dev/null || true)"
if [[ -z "${NET_NAME:-}" ]]; then
  echo "[ERR] cannot detect docker network for $DVD_C_GCS"; exit 2
fi
NET_ID="$(docker network inspect "$NET_NAME" -f '{{.Id}}')"
export CTI_IFACE="br-${NET_ID:0:12}"

# ---------- CTI 초기화 ----------
TARGET_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$DVD_C_GCS")"
printf "TARGET_IP=%s\nMAVLINK_PORT=%s\n" "$TARGET_IP" "$DVD_MAVLINK_PORT" > attack_output/cti_targets.env
echo "[*] CTI_IFACE=$CTI_IFACE  TARGET_IP=$TARGET_IP  MAVLINK_PORT=$DVD_MAVLINK_PORT"

# ---------- CTI Watcher/Sniffer ----------
sudo -v
kill $(cat /tmp/cti_ip.pid 2>/dev/null) 2>/dev/null || true
bash cti/cti_watch_ip.sh > attack_output/cti_watch_ip.out 2>&1 & echo $! > /tmp/cti_ip.pid
kill $(cat /tmp/cti_sniff.pid 2>/dev/null) 2>/dev/null || true
# 스니퍼 실패해도 파이프라인 계속 진행
if ! sudo -n -E python3 cti/cti_sniff_mavlink.py --iface "$CTI_IFACE" --target-ip "$TARGET_IP" \
  > attack_output/cti_sniff_port.out 2>&1 & echo $! > /tmp/cti_sniff.pid; then
  echo "[WARN] cti_sniff_mavlink 실패(권한/iface). 계속 진행."
fi

# ---------- 유틸 ----------
_now_ms(){ date +%s%3N; }
emit(){ printf "%s\t%s\t%s\n" "$(_now_ms)" "$1" "$2" >> attack_output/bus.log; }

# ---------- N회 반복 ----------
echo "[*] runs=$N"
for i in $(seq 1 "$N"); do
  echo "[*] run $i / $N"

  # 1) MTD: IP shuffle
  NEW_LAST=$((100 + RANDOM % 100))
  modules/mtd_ip_shuffle.sh CIDR=24 NEW_LAST="$NEW_LAST" ANNOUNCE_MS=600 DROP_OLD=$((RANDOM%2))
  sleep "$CTI_WAIT_S"  # CTI 반영 여유

  # 2) 확률적으로 Port hop (iptables 없으면 socat 폴백)
  if (( RANDOM % 100 < PORT_HOP_PROB )); then
    NEWP=$((20000 + RANDOM % 5000)); OLDP="${DVD_MAVLINK_PORT}"
    if command -v iptables >/dev/null 2>&1; then
      modules/mtd_port_hop_mavlink.sh OLD_PORT="$OLDP" NEW_PORT="$NEWP" GRACE=5 DROP_OLD=1 || true
    else
      docker exec -d "$DVD_C_GCS" bash -lc "nohup socat -T0 -u UDP-RECVFROM:${NEWP},fork,reuseaddr UDP-SENDTO:127.0.0.1:${OLDP} >/dev/null 2>&1 & echo \$! > /tmp/mtd_socat_${NEWP}.pid"
      echo "MAVLINK_PORT=${NEWP}" >> attack_output/cti_targets.env
      emit "mtd" "mode=REAL actor=defender action=port_hop_socat new=${NEWP} old=${OLDP} target=${DVD_C_GCS}"
    fi
    sleep 0.3
  fi

  # 3) 공격: follow_* 랜덤 선택
  if (( RANDOM % 100 < FOLLOW_FLOOD_PROB )); then
    modules/atk_follow_flood.sh DUR=$((4 + RANDOM % 6)) PKT_SIZE=250 RATE_PPS=$((800 + RANDOM % 800))
  else
    modules/atk_follow_mavlink.sh COUNT=$((100 + RANDOM % 200)) SLEEP_MS=5
  fi

  # (옵션) 라운드 쿨다운
  sleep 0.2
done

# ---------- 타임라인 ----------
python3 tools/gen_effects_timeline.py attack_output/bus.log \
  -o attack_output/effect_timeline.csv --rules tools/effects_rules.json --mode hold

# ---------- (옵션) NS-3 ----------
if [[ "$RUN_NS3" == "1" ]]; then
  NS3ROOT=~/MTD/MTD_full_testbed/ns-3.45/ns-3-dev
  cd "$NS3ROOT"
  ./ns3 run "scratch/drone_lpc_eval \
    --timeline=../../dvd_lite/dvd_attacks_lpc/attack_output/effect_timeline.csv \
    --simTime=${SIM_TIME} --animMaxPkts=8000000 --atkRateMbps=${ATK_RATE_MBPS}" || true
  cd "$BASE"
fi

# ---------- 스코어/데이터/학습 ----------
python3 tools/score_cti_mtd.py attack_output/bus.log attack_output/effect_timeline.csv \
  --ns3 attack_output/ns3_metrics.csv -o attack_output/score.json || true
python3 tools/make_ml_dataset.py attack_output/bus.log attack_output/effect_timeline.csv \
  --ns3 attack_output/ns3_metrics.csv -o attack_output/dataset.csv || true
python3 tools/train_mtd_policy.py attack_output/dataset.csv || true

echo "[DONE] outputs:"
ls -lh attack_output/effect_timeline.csv attack_output/ns3_metrics.csv attack_output/score.json attack_output/dataset.csv 2>/dev/null || true
