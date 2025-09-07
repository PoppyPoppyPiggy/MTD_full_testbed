#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc"
BUS="$ROOT/bus"
NS3="/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev"

ATTACK_KEY="${1:-}"   # 비워두면 bus.log에서 자동 추출
LEVEL="${2:-}"        # 비워두면 bus.log에서 자동 추출
MTD="${3:-off}"       # on|off
SIM="${4:-fanet}"     # fanet|drone

BUS_LOG="$BUS/bus.log"
BUS_DVD="$BUS/bus_dvd.log"

extract_field () {
  local line="$1" key="$2"
  echo "$line" | sed -nE "s/.*${key}=([^ ]+).*/\1/p"
}

last="$(grep 'BUS ATK ATTACK_START' -a "$BUS_LOG" | tail -n1 || true)"
if [[ -z "${ATTACK_KEY}" ]]; then ATTACK_KEY="$(extract_field "$last" 'key')"; fi
if [[ -z "${LEVEL}" ]];      then LEVEL="$(extract_field "$last" 'level')";   fi
: "${ATTACK_KEY:=unknown_attack}"
: "${LEVEL:=low}"

# 1) run dir
base_dir="$BUS/${ATTACK_KEY}/${LEVEL}/mtd_${MTD}"
mkdir -p "$base_dir"
idx=1
while [[ -d "${base_dir}/run_${idx}" ]]; do idx=$((idx+1)); done
RUN_DIR="${base_dir}/run_${idx}"
mkdir -p "$RUN_DIR/pcap" "$RUN_DIR/tmp"
echo "[ns3_eval] RUN_DIR=$RUN_DIR"

# 2) timeline
TIMELINE="$RUN_DIR/effect_timeline.csv"
python3 "$ROOT/tools/gen_effect_timestamp.py" "$BUS_LOG" --dvd "$BUS_DVD" -o "$TIMELINE"
echo "[ns3_eval] timeline -> $TIMELINE"
tail -n 2 "$TIMELINE" || true

# 3) nodeinfo/links
NI_JSON="$(python3 "$ROOT/tools/make_nodeinfo_from_dvd.py" "$RUN_DIR/tmp")"
NODECSV="$(echo "$NI_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["nodeinfo"])')"
LINKSCV="$(echo "$NI_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["links"])')"

# 4) ns-3 실행 (fanet 멀티노드 평가)
cd "$NS3"
./ns3 build >/dev/null
LABEL="${ATTACK_KEY}:${LEVEL}:mtd_${MTD}"

if [[ "$SIM" == "fanet" ]]; then
  ./ns3 run "scratch/honeydrone_net_lpc_eval \
    --timeline=${TIMELINE} \
    --nodeInfoCsv=${NODECSV} \
    --linksCsv=${LINKSCV} \
    --simTime=35 \
    --labelPrefix=${LABEL} \
    --animOut=${RUN_DIR}/dvd_netanim.xml \
    --pcapPrefix=${RUN_DIR}/pcap/ns3 \
    --metricsOut=${RUN_DIR}/ns3_metrics.csv"
else
  ./ns3 run "scratch/drone_lpc_eval \
    --timeline=${TIMELINE} \
    --simTime=35 \
    --animOut=${RUN_DIR}/dvd_netanim.xml \
    --pcapPrefix=${RUN_DIR}/pcap/ns3 \
    --metricsOut=${RUN_DIR}/ns3_metrics.csv"
fi

echo "[ns3_eval] outputs:"
ls -lh "$RUN_DIR"
