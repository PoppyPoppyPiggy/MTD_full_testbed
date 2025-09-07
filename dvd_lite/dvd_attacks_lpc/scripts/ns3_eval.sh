#!/usr/bin/env bash
set -euo pipefail
SCN="$1"; ATK="$2"; LV="$3"; MTD="$4"
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; source "$BASE/00_env_ext.sh"

LABELS="GCS,CC,FC,SIM,ATTACKER"
POSCSV="20:20;60:40;60:0;100:20;0:60"
EVENTSCSV="$BASE/bus/events_${SCN}.csv"

if [[ -f "$BASE/bus/nodeinfo.json" ]]; then
  LABELS="$(jq -r '.labels' "$BASE/bus/nodeinfo.json" 2>/dev/null || echo "$LABELS")"
  POSCSV="$(jq -r '.posCSV' "$BASE/bus/nodeinfo.json" 2>/dev/null || echo "$POSCSV")"
fi

pushd /home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev >/dev/null
./ns3 run "scratch/drone_lpc_eval \
  --timeline=../../dvd_lite/dvd_attacks_lpc/bus/effect_timeline_${SCN}.csv \
  --simTime=${SIM_TIME:-35} \
  --animOut=../../dvd_lite/dvd_attacks_lpc/bus/dvd_netanim_${ATK}_${LV}_${MTD}_${SCN}.xml \
  --pcapPrefix=../../dvd_lite/dvd_attacks_lpc/bus/pcap/ns3_${ATK}_${LV}_${MTD}_${SCN} \
  --metricsOut=../../dvd_lite/dvd_attacks_lpc/bus/ns3_metrics_${ATK}_${LV}_${MTD}_${SCN}.csv \
  --nodeLabels='${LABELS}' \
  --posCSV='${POSCSV}' \
  --eventsCsv=../../dvd_lite/dvd_attacks_lpc/bus/events_${SCN}.csv"
popd >/dev/null
