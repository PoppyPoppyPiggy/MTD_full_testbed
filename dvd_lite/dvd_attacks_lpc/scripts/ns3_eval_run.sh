#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../00_env_ext.sh"

SCN="${1:-run-$(date +%s)}"
ATTK="${2:-generic}"
LVL="${3:-low}"
MTD="${4:-off}"

RUN_DIR="$OUT_DIR/${ATTK}/${LVL}/mtd_${MTD}/${SCN}"
mkdir -p "$RUN_DIR" "$RUN_DIR/pcap"
chmod -R a+rwX "$RUN_DIR"

# 1) 타임라인
python3 "$BASE/tools/gen_effect_timestamp.py" "$BUS_LOG" --out "$RUN_DIR/effect_timeline.csv"

# 2) 노드/링크 정보
python3 "$BASE/tools/make_nodeinfo_from_dvd.py" "$BUS_LOG" "$RUN_DIR"

# 3) ns-3 (비루트로)
sudo -u kali -E bash -lc "
  cd /home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev && \
  ./ns3 build --quiet --run 'scratch/drone_lpc_eval --timeline=$RUN_DIR/effect_timeline.csv --nodeinfo=$RUN_DIR/nodes.csv --simTime=35 --animOut=$RUN_DIR/dvd_netanim.xml --metricsOut=$RUN_DIR/ns3_metrics.csv'"

echo "[ns3_eval] outputs in: $RUN_DIR"
