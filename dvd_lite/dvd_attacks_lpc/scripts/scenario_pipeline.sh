#!/usr/bin/env bash
#
# scenario_pipeline.sh
#
# Top level pipeline for running MTD/DVD scenarios end‑to‑end.  This script
# orchestrates attack execution against the Damn Vulnerable Drone (DVD),
# captures CTI and attack artefacts into a unified bus.log, converts the
# bus.log into an effect timeline for NS‑3, optionally invokes the NS‑3
# evaluation, and finally generates scoring, dataset and training outputs.
#
# The intent of this wrapper is to provide a single entry‑point that hides
# the individual moving parts (auto_collect.sh, gen_effects_timeline.py,
# run_ns3_eval.sh, scoring/dataset scripts, etc.) while exposing a simple
# interface for common workflows such as "quick" (few runs, no NS‑3),
# "standard" (dozens of runs with NS‑3), and "aggressive" (hundreds of
# runs with NS‑3).  It also offers helpers for running continuous data
# collection in the background and rebuilding the timeline independently
# of a collection run.

set -Eeuo pipefail

# Determine the repository root relative to this script.  All relative
# paths are resolved from here.
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

# Default configuration.  These values may be overridden via environment
# variables or by editing scripts/scenario.pipeline.yaml.  When the
# YAML file is present, we will attempt to pull the settings from it; if
# parsing fails, the defaults below are used.
DEFAULT_RUNS=60
DEFAULT_RUN_NS3=1
DEFAULT_SIM_TIME=60
DEFAULT_ATK_RATE_MBPS=30
DEFAULT_COOLDOWN_S=0.2
DEFAULT_CTI_WAIT_S=0.5
DEFAULT_PORT_HOP_PROB=50
DEFAULT_FOLLOW_FLOOD_PROB=60
DEFAULT_RULES_PATH="tools/effects_rules.json"

# Attempt to parse scenario.pipeline.yaml for overrides.  We avoid
# depending on external tools (like yq) by using simple grep/awk
# heuristics.  If the file does not exist or parsing fails, we fall back
# to the defaults above.
SCENARIO_YAML="scripts/scenario.pipeline.yaml"
if [[ -f "$SCENARIO_YAML" ]]; then
  # Extract YAML meta values into variables, stripping quotes
  _get_yaml() {
    local key="$1"
    local val
    val=$(grep -E "^[[:space:]]*$key:" "$SCENARIO_YAML" | head -n1 | awk '{print $2}') || return 1
    echo "${val//\"/}" | sed 's/,//g'
  }
  runs=$(_get_yaml runs 2>/dev/null || echo "$DEFAULT_RUNS")
  run_ns3=$(_get_yaml run_ns3 2>/dev/null || echo "$DEFAULT_RUN_NS3")
  sim_time=$(_get_yaml sim_time 2>/dev/null || echo "$DEFAULT_SIM_TIME")
  atk_rate_mbps=$(_get_yaml atk_rate_mbps 2>/dev/null || echo "$DEFAULT_ATK_RATE_MBPS")
  cooldown_s=$(_get_yaml cooldown_s 2>/dev/null || echo "$DEFAULT_COOLDOWN_S")
  cti_wait_s=$(_get_yaml cti_wait_s 2>/dev/null || echo "$DEFAULT_CTI_WAIT_S")
  port_hop_prob=$(_get_yaml port_hop_prob 2>/dev/null || echo "$DEFAULT_PORT_HOP_PROB")
  follow_flood_prob=$(_get_yaml follow_flood_prob 2>/dev/null || echo "$DEFAULT_FOLLOW_FLOOD_PROB")
  rules_path=$(_get_yaml rules 2>/dev/null || echo "$DEFAULT_RULES_PATH")
else
  runs="$DEFAULT_RUNS"
  run_ns3="$DEFAULT_RUN_NS3"
  sim_time="$DEFAULT_SIM_TIME"
  atk_rate_mbps="$DEFAULT_ATK_RATE_MBPS"
  cooldown_s="$DEFAULT_COOLDOWN_S"
  cti_wait_s="$DEFAULT_CTI_WAIT_S"
  port_hop_prob="$DEFAULT_PORT_HOP_PROB"
  follow_flood_prob="$DEFAULT_FOLLOW_FLOOD_PROB"
  rules_path="$DEFAULT_RULES_PATH"
fi

# Override variables from environment if provided.  Use uppercase names
# for environment variables to emphasise they are user‑supplied.  If the
# environment variable is non‑empty, override the parsed default.
runs="${RUNS:-$runs}"
run_ns3="${RUN_NS3:-$run_ns3}"
sim_time="${SIM_TIME:-$sim_time}"
atk_rate_mbps="${ATK_RATE_MBPS:-$atk_rate_mbps}"
cooldown_s="${COOLDOWN_S:-$cooldown_s}"
cti_wait_s="${CTI_WAIT_S:-$cti_wait_s}"
port_hop_prob="${PORT_HOP_PROB:-$port_hop_prob}"
follow_flood_prob="${FOLLOW_FLOOD_PROB:-$follow_flood_prob}"
rules_path="${EFFECTS_RULES:-$rules_path}"

# Helper: print current configuration.
print_config() {
  cat <<EOF
Current configuration:
  runs           : $runs
  run_ns3        : $run_ns3
  sim_time       : $sim_time
  atk_rate_mbps  : $atk_rate_mbps
  cooldown_s     : $cooldown_s
  cti_wait_s     : $cti_wait_s
  port_hop_prob  : $port_hop_prob
  follow_flood_prob: $follow_flood_prob
  rules_path     : $rules_path
EOF
}

# run_collect orchestrates a single data collection run consisting of
# N iterations of MTD and attack modules, followed by timeline
# generation, NS‑3 evaluation (optional) and downstream ML stages.  It
# relies on scripts/auto_collect.sh for the heavy lifting.  The
# environment variables passed to auto_collect.sh control the run.
run_collect() {
  echo "[scenario_pipeline] Starting data collection run (runs=$runs)"
  print_config
  # Export environment for auto_collect.sh
  export N="$runs"
  export RUN_NS3="$run_ns3"
  export SIM_TIME="$sim_time"
  export ATK_RATE_MBPS="$atk_rate_mbps"
  export PORT_HOP_PROB="$port_hop_prob"
  export FOLLOW_FLOOD_PROB="$follow_flood_prob"
  export COOLDOWN_S="$cooldown_s"
  export CTI_WAIT_S="$cti_wait_s"
  export EFFECTS_RULES="$rules_path"
  # Call the auto_collect script
  bash "$BASE_DIR/scripts/auto_collect.sh"
}

# run_stream_bg starts continuous data collection in the background.  It
# repeatedly invokes run_collect until stopped.  A PID file is written
# into attack_output/.  To stop the stream, call stop_stream_bg.
run_stream_bg() {
  mkdir -p attack_output
  local pidfile="attack_output/stream.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile" 2>/dev/null)" 2>/dev/null; then
    echo "[scenario_pipeline] Stream is already running with PID $(cat "$pidfile")"
    return 1
  fi
  echo "[scenario_pipeline] Starting continuous data collection in background..."
  (
    while true; do
      run_collect || true
      # brief cooldown between runs to avoid thrashing the container
      sleep 1
    done
  ) &
  echo $! > "$pidfile"
  echo "[scenario_pipeline] Background stream PID: $(cat "$pidfile")"
}

# stop_stream_bg kills the background data collection started via
# run_stream_bg.  It reads the PID from the pidfile and terminates it.
stop_stream_bg() {
  local pidfile="attack_output/stream.pid"
  if [[ -f "$pidfile" ]]; then
    local pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "[scenario_pipeline] Stopping background stream (PID=$pid)"
      kill "$pid" || true
    else
      echo "[scenario_pipeline] No active stream process found"
    fi
    rm -f "$pidfile"
  else
    echo "[scenario_pipeline] Stream PID file not found"
  fi
}

# rebuild_timeline regenerates effect_timeline.csv from bus.log using
# gen_effects_timeline.py.  This is useful when tweaking the rules
# file or after manual edits to bus.log without rerunning the full
# pipeline.  The bus.log file is read from attack_output/bus.log and
# the output is written to attack_output/effect_timeline.csv.
rebuild_timeline() {
  if [[ ! -f attack_output/bus.log ]]; then
    echo "[scenario_pipeline] bus.log not found.  Run a collection first."
    return 1
  fi
  mkdir -p attack_output
  local rules_file="$rules_path"
  if [[ ! -f "$rules_file" ]]; then
    echo "[scenario_pipeline] rules file not found: $rules_file"
    return 2
  fi
  echo "[scenario_pipeline] Rebuilding effect_timeline.csv from bus.log using $rules_file"
  python3 tools/gen_effects_timeline.py attack_output/bus.log \
    -o attack_output/effect_timeline.csv --rules "$rules_file" --mode hold
  echo "[scenario_pipeline] effect_timeline.csv regenerated"
}

# run_ns3_once executes the NS‑3 simulation using the current
# effect_timeline.csv.  It is a convenience wrapper around
# run_ns3_eval.sh.  Users should run rebuild_timeline first if
# bus.log has been modified since the last timeline generation.
run_ns3_once() {
  if [[ ! -f attack_output/effect_timeline.csv ]]; then
    echo "[scenario_pipeline] effect_timeline.csv not found.  Run a collection or rebuild the timeline first."
    return 1
  fi
  # Use run_ns3_eval.sh with explicit parameters
  echo "[scenario_pipeline] Running NS‑3 evaluation with timeline"
  TIMELINE="attack_output/effect_timeline.csv" \
  OUT="attack_output/ns3_metrics.csv" \
  SIM_TIME="$sim_time" PKT_SIZE="${PKT_SIZE:-512}" \
  bash "$BASE_DIR/scripts/run_ns3_eval.sh"
  echo "[scenario_pipeline] NS‑3 evaluation complete"
}

# brief_summary prints a quick summary of key outputs (line counts and
# sizes) to help gauge data collection progress.
brief_summary() {
  echo "[scenario_pipeline] Summary of outputs:"
  wc -l attack_output/bus.log attack_output/effect_timeline.csv attack_output/ns3_metrics.csv 2>/dev/null || true
  ls -lh attack_output/bus.log attack_output/effect_timeline.csv attack_output/ns3_metrics.csv 2>/dev/null || true
}

# usage prints a simple help message.  It lists available commands
# together with a short description.
usage() {
  cat <<'EOF'
Usage: scenario_pipeline.sh [command]

Commands:
  run            Run a single data collection cycle (default when no command provided)
  stream         Start continuous data collection in the background
  stop           Stop the background data collection started with 'stream'
  rebuild        Regenerate effect_timeline.csv from the current bus.log
  ns3            Run the NS‑3 evaluation using the existing timeline
  summary        Show a brief summary of output file sizes and line counts
  config         Print the current configuration (runs, sim_time, etc.)
  help           Show this help message

Environment variables override defaults:
  RUNS, RUN_NS3, SIM_TIME, ATK_RATE_MBPS, COOLDOWN_S, CTI_WAIT_S,
  PORT_HOP_PROB, FOLLOW_FLOOD_PROB, EFFECTS_RULES
EOF
}

# If no command is supplied, default to 'run'.  Parse the first CLI
# argument and dispatch to the corresponding function.  Unknown
# commands cause the usage to be printed.
cmd="${1:-run}"
case "$cmd" in
  run)
    run_collect
    ;;
  stream)
    run_stream_bg
    ;;
  stop)
    stop_stream_bg
    ;;
  rebuild)
    rebuild_timeline
    ;;
  ns3)
    run_ns3_once
    ;;
  summary)
    brief_summary
    ;;
  config)
    print_config
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo "[scenario_pipeline] Unknown command: $cmd"
    usage
    exit 1
    ;;
esac