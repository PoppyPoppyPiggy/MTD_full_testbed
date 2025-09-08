#!/usr/bin/env bash
set -euo pipefail
SCN="$1"; ATK="$2"; LV="$3"; MTD="$4"
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; source "$BASE/00_env_ext.sh"
mkdir -p "$BASE/bus/pcap" "$BASE/bus" || true
TL=$(realpath "$BASE/bus/effect_timeline_${SCN}.csv")
ANIM=$(realpath "$BASE/bus/dvd_netanim_${ATK}_${LV}_${MTD}_${SCN}.xml")
PCAP=$(realpath "$BASE/bus/pcap/ns3_${ATK}_${LV}_${MTD}_${SCN}")
MET=$(realpath "$BASE/bus/ns3_metrics_${ATK}_${LV}_${MTD}_${SCN}.csv")
pushd /home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev >/dev/null
./ns3 run "scratch/drone_lpc_eval --timeline=${TL} --simTime=${SIM_TIME:-35} --animOut=${ANIM} --pcapPrefix=${PCAP} --metricsOut=${MET}"
popd >/dev/null
echo "[ns3_eval] wrote:"; ls -lh "${ANIM}" || true; ls -lh "${MET}" || true
