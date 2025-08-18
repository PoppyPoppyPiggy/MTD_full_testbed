# tools/collect_docker_stats.sh
#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-attack_output/docker_stats.csv}"; INTERVAL="${2:-1}"
echo "ts,container,cpu_perc,mem_mb,net_rx_kb,net_tx_kb" > "$OUT"
while true; do
  while read -r id name; do
    s=$(docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}" "$id" | tr -d '%')
    cpu=$(echo "$s" | cut -d',' -f1)
    mem=$(echo "$s" | cut -d',' -f2 | awk '{print $1}')      # MB 가정
    rx=$(echo "$s" | cut -d',' -f3 | awk '{print $1}')
    tx=$(echo "$s" | cut -d',' -f3 | awk '{print $3}')
    echo "$(date +%s),$name,$cpu,$mem,$rx,$tx"
  done < <(docker ps --format '{{.ID}} {{.Names}}')
  sleep "$INTERVAL"
done | tee -a "$OUT"
