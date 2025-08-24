# dvd_lite/dvd_attacks_lpc/scripts/netem_follow_timeline.sh
#!/usr/bin/env bash
set -Eeuo pipefail

CSV="${1:-attack_output/effect_timeline.csv}"
DEV="${2:-br-honey}"
SLEEP=${SLEEP:-1}

need(){ command -v "$1" >/dev/null 2>&1 || { echo "need $1"; exit 1; }; }
need tc; need awk; need bc

echo "[*] netem on $DEV <- $CSV"
sudo tc qdisc del dev "$DEV" root 2>/dev/null || true
sudo tc qdisc add dev "$DEV" root handle 1: prio
sudo tc qdisc add dev "$DEV" parent 1:1 handle 10: netem
sudo tc qdisc add dev "$DEV" parent 1:2 handle 20: tbf rate 1000mbit burst 32kbit latency 50ms

tail -n +2 "$CSV" | while IFS=, read -r t loss delay jitter dup rate; do
  loss=${loss:-0}; delay=${delay:-0}; jitter=${jitter:-0}; dup=${dup:-0}; rate=${rate:-0}
  sudo tc qdisc change dev "$DEV" parent 1:1 handle 10: netem \
      loss "${loss}%" duplicate "${dup}%" delay "${delay}ms" "${jitter}ms" 2>/dev/null || true
  if (( $(echo "$rate > 0.0" | bc -l) )); then
    sudo tc qdisc change dev "$DEV" parent 1:2 handle 20: tbf rate "${rate}mbit" burst 32kbit latency 50ms
  else
    sudo tc qdisc change dev "$DEV" parent 1:2 handle 20: tbf rate 1000mbit burst 32kbit latency 50ms
  fi
  sleep "$SLEEP"
done

echo "[OK] netem finished"
