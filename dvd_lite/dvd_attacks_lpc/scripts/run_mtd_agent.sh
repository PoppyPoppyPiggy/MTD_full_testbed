#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-$PWD/dvd_lite/dvd_attacks_lpc}"
export BASE

# 의존 패키지(최초 1회)
python3 - <<'PY'
import sys,subprocess
pkgs=['scapy','pyyaml']
subprocess.run([sys.executable,'-m','pip','install','--quiet',*pkgs],check=False)
PY

# 버스 스니퍼 (백그라운드)
sudo -E python3 "$BASE/modules/bus/sniffer.py" &

# MTD 엔진 (포그라운드)
sudo -E python3 "$BASE/modules/mtd/engine.py"
