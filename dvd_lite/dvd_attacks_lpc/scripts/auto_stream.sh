#!/usr/bin/env bash
# 끝날 때까지 무제한 라운드로 bus.log만 계속 늘리기 (Ctrl+C로 중단)
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"

: "${DVD_C_GCS:=ground-control-station}"
: "${DVD_MAVLINK_PORT:=14550}"
: "${CTI_WAIT_S:=0.4}"
: "${PORT_HOP_PROB:=40}"
: "${FOLLOW_FLOOD_PROB:=60}"

mkdir -p attack_output
touch attack_output/bus.log attack_output/run.log

NET_NAME="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' "$DVD_C_GCS" 2>/dev/null || true)"
NET_ID="$(docker network inspect "$NET_NAME" -f '{{.Id}}')"
export CTI_IFACE="br-${NET_ID:0:12}"
TARGET_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$DVD_C_GCS")"
printf "TARGET_IP=%s\nMAVLINK_PORT=%s\n" "$TARGET_IP" "$DVD_MAVLINK_PORT" > attack_output/cti_targets.env

sudo -v
kill $(cat /tmp/cti_ip.pid 2>/dev/null) 2>/dev/null || true
bash cti/cti_watch_ip.sh > attack_output/cti_watch_ip.out 2>&1 & echo $! > /tmp/cti_ip.pid

_now_ms(){ date +%s%3N; }
emit(){ printf "%s\t%s\t%s\n" "$(_now_ms)" "$1" "$2" >> attack_output/bus.log; }

i=0
while true; do
  i=$((i+1))
  echo "[*] stream run $i"

  modules/mtd_ip_shuffle.sh CIDR=24 NEW_LAST=$((100 + RANDOM % 100)) ANNOUNCE_MS=600 DROP_OLD=$((RANDOM%2))
  sleep "$CTI_WAIT_S"

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

  if (( RANDOM % 100 < FOLLOW_FLOOD_PROB )); then
    modules/atk_follow_flood.sh DUR=$((4 + RANDOM % 6)) PKT_SIZE=250 RATE_PPS=$((800 + RANDOM % 800))
  else
    modules/atk_follow_mavlink.sh COUNT=$((100 + RANDOM % 200)) SLEEP_MS=5
  fi
  sleep 0.2
done
