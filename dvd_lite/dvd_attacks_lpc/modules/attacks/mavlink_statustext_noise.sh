#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_runner.shlib"
run_attack "mavlink_statustext_noise" "${1:-high}"
