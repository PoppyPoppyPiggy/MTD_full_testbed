#!/usr/bin/env bash
# lpc_run.sh — 범용 실행기 (모듈 N개 + SCENARIO/MODS 파서 + NS3_BUILD_MODE 패스)
set -euo pipefail

BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
ATT_OUT="$BASE/attack_output"
BUS="$ATT_OUT/bus.log"
TL="$ATT_OUT/effect_timeline.csv"
FEATS="$ATT_OUT/window_features.csv"
NS3_ROOT_DEFAULT="$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev"
NS3="${NS3_ROOT:-$NS3_ROOT_DEFAULT}"
NS3_MET="$ATT_OUT/ns3_metrics.csv"
RUN_NS3_EVAL="$BASE/scripts/run_ns3_eval.sh"

# shellcheck disable=SC1091
[[ -f "$BASE/00_env.sh" ]] && source "$BASE/00_env.sh" || true
[[ -n "${NS3:-}" && -d "$NS3" ]] || { [[ -n "${NS3_ROOT:-}" && -d "$NS3_ROOT" ]] && NS3="$NS3_ROOT"; }

mkdir -p "$ATT_OUT"
: > "$BUS"
export BUS_LOG="$BUS" LPC_LOG_DIR="$ATT_OUT"

_norm_int(){ local v="${1:-}"; v="$(echo "$v" | sed -E 's/[^0-9]//g')"; echo "${v:-0}"; }
_resolve_module(){
  local name="$1"
  [[ -x "$name" || -f "$name" ]] && { echo "$name"; return; }
  [[ -x "$BASE/$name" || -f "$BASE/$name" ]] && { echo "$BASE/$name"; return; }
  [[ -x "$BASE/modules/$name" ]] && { echo "$BASE/modules/$name"; return; }
  [[ -x "$BASE/modules/$name.sh" ]] && { echo "$BASE/modules/$name.sh"; return; }
  return 1
}
_die(){ echo "[run][FATAL] $*" >&2; exit 2; }

DUR="$(_norm_int "${DUR:-20}")"; (( DUR>0 )) || DUR=20
WIN="$(_norm_int "${WIN:-3}")"; (( WIN>0 )) || WIN=3
STRIDE="$(_norm_int "${STRIDE:-1}")"; (( STRIDE>0 )) || STRIDE=1
SIM_TIME="$(_norm_int "${SIM_TIME:-60}")"; (( SIM_TIME>0 )) || SIM_TIME=60
PKT_SIZE="$(_norm_int "${PKT_SIZE:-512}")"; (( PKT_SIZE>0 )) || PKT_SIZE=512
NS3_BUILD_MODE="${NS3_BUILD_MODE:-once}"

EFFECTS_RULES="${EFFECTS_RULES:-$BASE/tools/effects_rules.json}"
[[ -f "$EFFECTS_RULES" ]] || _die "effects_rules.json not found: $EFFECTS_RULES"
LPC_METRICS_CLI="$BASE/tools/lpc_metrics_cli.py"
[[ -f "$LPC_METRICS_CLI" ]] || _die "lpc_metrics_cli.py missing: $LPC_METRICS_CLI"
GEN_TL="$BASE/tools/gen_effects_timeline.py"
[[ -f "$GEN_TL" ]] || _die "gen_effects_timeline.py missing: $GEN_TL"

SCENARIO="${SCENARIO:-}"
declare -a MOD_CMDS=()

if [[ -n "$SCENARIO" && -f "$SCENARIO" ]]; then
  while IFS= read -r line; do
    line="$(echo "$line" | sed -E 's/^\s+|\s+$//g')"
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    module=""; interval=""; budget=""; declare -a envs=()
    for tok in $line; do
      [[ "$tok" == module=*   ]] && module="${tok#module=}"
      [[ "$tok" == interval=* ]] && interval="$(_norm_int "${tok#interval=}")"
      [[ "$tok" == budget=*   ]] && budget="$(_norm_int "${tok#budget=}")"
      [[ "$tok" == ENV:*      ]] && envs+=("${tok#ENV:}")
    done
    [[ -n "$module" ]] || _die "SCENARIO line missing module: $line"
    mod_path="$(_resolve_module "$module")" || _die "module not found: $module"
    (( interval>0 )) || interval=1000; (( budget>0 )) || budget=30
    MOD_CMDS+=("LPC_INTERVAL_MS=$interval LPC_MAX_BUDGET=$budget ${envs[*]:-} -- $mod_path")
  done < "$SCENARIO"
fi

if [[ ${#MOD_CMDS[@]} -eq 0 && -n "${MODS:-}" ]]; then
  IFS=';' read -r -a items <<< "$MODS"
  for item in "${items[@]}"; do
    item="$(echo "$item" | sed -E 's/^\s+|\s+$//g')"; [[ -z "$item" ]] && continue
    name="${item%%:*}"; opts="${item#*:}"
    mod_path="$(_resolve_module "$name")" || _die "module not found: $name"
    interval=1000; budget=30; declare -a envs=()
    IFS=',' read -r -a kvs <<< "$opts"
    for kv in "${kvs[@]}"; do
      kv="$(echo "$kv" | sed -E 's/^\s+|\s+$//g')"; [[ -z "$kv" ]] && continue
      [[ "$kv" == interval=* ]] && interval="$(_norm_int "${kv#interval=}")"
      [[ "$kv" == budget=*   ]] && budget="$(_norm_int "${kv#budget=}")"
      [[ "$kv" == ENV:*      ]] && envs+=("${kv#ENV:}")
    done
    MOD_CMDS+=("LPC_INTERVAL_MS=$interval LPC_MAX_BUDGET=$budget ${envs[*]:-} -- $mod_path")
  done
fi

if [[ ${#MOD_CMDS[@]} -eq 0 ]]; then
  MOD_CMDS+=("LPC_INTERVAL_MS=200 LPC_MAX_BUDGET=30 -- $BASE/modules/mavlink_param_drift.sh")
  MOD_CMDS+=("LPC_INTERVAL_MS=250 LPC_MAX_BUDGET=30 ENV:INTENSITY=mid -- $BASE/modules/telemetry_trickle_jam.sh")
fi

_build_env_prefix(){
  local s="$1"; local out=()
  for tok in $s; do
    if [[ "$tok" == ENV:* ]]; then out+=("export ${tok#ENV:};")
    elif [[ "$tok" == *"="* ]]; then out+=("export $tok;")
    fi
  done
  echo "${out[*]}"
}

echo "[run] duration=${DUR}s, modules=${#MOD_CMDS[@]}"
for i in "${!MOD_CMDS[@]}"; do echo "[run] M$((i+1)): ${MOD_CMDS[$i]}"; done

declare -a PIDS=()
for spec in "${MOD_CMDS[@]}"; do
  envspec="${spec%%--*}"
  modpath="$(echo "${spec#*--}" | sed -E 's/^\s+|\s+$//g')"
  envprefix="$(_build_env_prefix "$envspec")"
  ( cd "$BASE"; eval "$envprefix"; exec "$modpath" ) & PIDS+=($!)
done

trap 'echo; echo "[run] stopping..."; kill "${PIDS[@]}" 2>/dev/null || true' INT TERM

start=$(date +%s)
while :; do
  now=$(date +%s); elapsed=$((now-start))
  printf "\r[run] elapsed: %02d:%02d / %02d:%02d  events=%-6s" \
    $((elapsed/60)) $((elapsed%60)) $((DUR/60)) $((DUR%60)) "$(wc -l < "$BUS")"
  (( elapsed >= DUR )) && break
  sleep 1
done
echo
kill "${PIDS[@]}" 2>/dev/null || true
wait 2>/dev/null || true
echo "[run] events written: $(wc -l < "$BUS")"

echo "[run] generating timeline..."
if ! python3 "$GEN_TL" "$BUS" -o "$TL" --rules "$EFFECTS_RULES"; then
  echo "[run][WARN] timeline generation failed; minimal sample injected"
fi
if [[ ! -s "$TL" ]] || ! head -n1 "$TL" | grep -q '^t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps'; then
  cat > "$TL" <<'CSV'
t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps
0,0,0,0,0,10
10,2,5,2,0,8
20,3,8,3,0,7
30,5,10,4,0,5
40,6,12,6,0,4
50,8,15,8,0,3
CSV
fi
echo "[run] timeline head:"; head -n 5 "$TL" || true

echo "[run] building features..."
python3 "$LPC_METRICS_CLI" "$TL" -o "$FEATS" --win "$WIN" --stride "$STRIDE"
echo "[run] feature head:"; head -n 5 "$FEATS" || true

echo "[run] ns-3 eval..."
TIMELINE="$TL" OUT="$NS3_MET" SIM_TIME="$SIM_TIME" PKT_SIZE="$PKT_SIZE" \
NS3_BUILD_MODE="$NS3_BUILD_MODE" \
bash "$RUN_NS3_EVAL"
echo "[run] ns-3 metrics head:"; head -n 5 "$NS3_MET" || true

echo; echo "[OK] done"
echo "  bus.log:              $BUS"
echo "  effect_timeline.csv:  $TL"
echo "  window_features.csv:  $FEATS"
echo "  ns3_metrics.csv:      $NS3_MET"
