#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
: > attack_output/bus.log; : > attack_output/run.log

sudo -v
kill $(cat /tmp/cti_ip.pid 2>/dev/null) 2>/dev/null || true
bash cti/cti_watch_ip.sh > attack_output/cti_watch_ip.out 2>&1 & echo $! > /tmp/cti_ip.pid

for i in $(seq 1 ${N:=10}); do
  echo "[*] run $i"
  modules/mtd_ip_shuffle.sh CIDR=24 NEW_LAST=$((100+RANDOM%100)) ANNOUNCE_MS=600 DROP_OLD=$((RANDOM%2))
  sleep 0.5
  modules/atk_follow_mavlink.sh COUNT=$((100+RANDOM%100)) SLEEP_MS=5
done

python3 tools/gen_effects_timeline.py attack_output/bus.log -o attack_output/effect_timeline.csv \
  --rules tools/effects_rules.json --mode hold

NS3ROOT=~/MTD/MTD_full_testbed/ns-3.45/ns-3-dev
cd "$NS3ROOT"
./ns3 run "scratch/drone_lpc_eval --timeline=../../dvd_lite/dvd_attacks_lpc/attack_output/effect_timeline.csv --simTime=60"
