#!/usr/bin/env bash
set -Eeuo pipefail

FC="flight-controller-lite"

# 0) GCS IP
GCS_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ground-control-station-lite 2>/dev/null || true)"
if [[ -z "${GCS_IP}" ]]; then
  echo "[ERR] ground-control-station-lite IP 탐지 실패"; exit 1
fi
echo "[*] GCS_IP=${GCS_IP}"

# 1) 컨테이너 기본 정보 & 파이썬 디텍션 (실패해도 계속)
docker exec "${FC}" sh -lc '
set +e
echo "[-] FC uname: $(uname -a)"
echo "[-] which python3: $(which python3 || echo NA)"
python3 -V 2>/dev/null || echo "python3 NA"
python3 -c "import sys; print(\"[-] sys.path entries:\", len(sys.path))" 2>/dev/null || true
' || true

# 2) pip 보장 및 MAVProxy 설치 시도 (실패해도 계속 진행)
docker exec "${FC}" sh -lc '
set +e
PY=python3
$PY -m ensurepip >/dev/null 2>&1 || true
$PY -m pip --version >/dev/null 2>&1 || $PY -c "import sys,ensurepip; print(\"[i] ensurepip fallback...\");" 2>/dev/null
$PY -m pip install -q --upgrade pip 2>/dev/null || true
$PY - <<EOF
import importlib, sys, subprocess
try:
    import MAVProxy
    print("[i] MAVProxy already present")
except Exception as e:
    print("[i] Installing MAVProxy in container ...")
    try:
        subprocess.check_call([sys.executable,"-m","pip","install","-q","MAVProxy==1.8.74","pyserial"])
        print("[i] MAVProxy install OK")
    except Exception as ex:
        print("[WARN] MAVProxy install failed:", ex)
        sys.exit(0)  # 실패해도 브릿지 대안으로 넘어가도록 0으로 종료
EOF
' || true

# 3) 기존 브릿지 종료
docker exec "${FC}" sh -lc 'pkill -f "MAVProxy.mavproxy" >/dev/null 2>&1 || true' || true

# 4) MAVProxy 브릿지 우선 기동 시도
echo "[*] trying: MAVProxy tcpin:5760 <= udpin:14550 => udp:${GCS_IP}:14550"
docker exec -d "${FC}" sh -lc "
set +e
LOG=/tmp/mavproxy_bridge.log
nohup python3 -m MAVProxy.mavproxy \\
  --daemon --non-interactive \\
  --state-basedir=/tmp/mavp \\
  --master=udpin:0.0.0.0:14550 \\
  --out=udp:${GCS_IP}:14550 \\
  --out=tcpin:0.0.0.0:5760 \\
  --cmd=\"set heartbeat 1\" \\
  >\"\$LOG\" 2>&1 &
sleep 1
test -s \"\$LOG\" && tail -n 40 \"\$LOG\" | sed -n \"1,40p\" || echo \"[i] LOG not ready yet\"
" || true

# 5) 포트 살아있는지 간이 체크 (컨테이너 내부)
docker exec "${FC}" sh -lc '
set +e
python3 - <<EOF
import socket,sys
s=socket.socket(); s.settimeout(0.5)
try:
    s.connect(("0.0.0.0",5760))
    print("[OK] tcpin:5760 is LISTENING in-container")
except Exception as e:
    print("[WARN] tcpin:5760 not listening yet:",e)
finally:
    try: s.close()
    except: pass
EOF
' || true

# 6) 최종 확인 메세지
FC_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${FC})"
echo "[i] FC_IP=${FC_IP}"
echo "[i] 상태 확인: docker exec ${FC} sh -lc 'pgrep -fa MAVProxy || true; tail -n 50 /tmp/mavproxy_bridge.log || true'"
echo "[i] 호스트에서 포트체크: nc -zv ${FC_IP} 5760"