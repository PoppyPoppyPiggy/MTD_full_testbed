#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/scripts/docker_observer.sh
# Snapshot docker containers & networks into bus.log (pre/post/snap)
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/attack_output"
OBS_DIR="${OUT_DIR}/obs"
BUS="${OUT_DIR}/bus.log"
mkdir -p "${OBS_DIR}"

PHASE="${1:-snap}"                    # pre | post | snap
NAME_FILTER="${NAME_FILTER:-(ground|companion|flight|sim)}"  # damn-vulnerable-drone 기본 4컨테이너 매칭
NET_FILTER="${NET_FILTER:-}"          # 비우면 전체
ONLY_RUNNING="${ONLY_RUNNING:-1}"
TIMEOUT_S="${TIMEOUT_S:-6}"

TS(){ date +%s%3N; }
emit(){ echo -e "$(TS)\t$1\t$2" | tee -a "${BUS}" >/dev/null; }
enc(){ python3 - "$1" <<'PY'
import sys,urllib.parse as u; print(u.quote(sys.argv[1], safe='-_.:/,@'))
PY
}

docker_ok(){
  command -v docker >/dev/null 2>&1 || return 1
  docker info >/dev/null 2>&1 || return 1
  return 0
}

_exec(){
  local id="$1" name="$2" phase="$3" cmd="$4" fn="$5"
  local dir="${OBS_DIR}/${phase}/${name}"; mkdir -p "$dir"
  if timeout "${TIMEOUT_S}" docker exec "$id" sh -lc "$cmd" > "${dir}/${fn}" 2>/dev/null; then
    emit docker_exec "phase=${phase} name=$(enc "$name") ok=1 cmd=$(enc "$cmd") out=$(enc "$fn")"
  else
    emit docker_exec "phase=${phase} name=$(enc "$name") ok=0 cmd=$(enc "$cmd")"
  fi
}

inspect_one(){
  local id="$1" name="$2" phase="$3"
  local dir="${OBS_DIR}/${phase}/${name}"; mkdir -p "$dir"

  # 단일 객체로 저장
  local js; js="$(docker inspect --format '{{json .}}' "$id" 2>/dev/null || true)"
  [[ -z "$js" ]] && return 0
  printf '%s\n' "$js" > "${dir}/inspect.json"

  # 요약/세부 분리 저장
  python3 - "${dir}" <<'PY'
import json,sys,os
dstd=sys.argv[1]
doc=json.load(open(os.path.join(dstd,"inspect.json"),encoding="utf-8"))
cfg=doc.get("Config",{}); st=doc.get("State",{}); h=doc.get("HostConfig",{}); ns=doc.get("NetworkSettings",{})

def w(n,o): open(os.path.join(dstd,n),"w",encoding="utf-8").write(json.dumps(o,ensure_ascii=False,indent=2))

env=cfg.get("Env") or []
pref=("DVD_","MAV","SIM_","GCS_","PX4","ARDU","ROS_","QGC_","APP_","HTTP_")
env_sel=[e for e in env if any(e.startswith(p) for p in pref)]
w("env.all.json",env); w("env.sel.json",env_sel)
w("ports.exposed.json", cfg.get("ExposedPorts") or {})
w("ports.bindings.json", h.get("PortBindings") or {})
w("security.json", {k:h.get(k) for k in ("Privileged","CapAdd","CapDrop","SecurityOpt","CgroupnsMode")})
w("resources.json", {k:h.get(k) for k in ("NanoCpus","CpuShares","Memory","MemoryReservation","PidsLimit")})
w("mounts.json", doc.get("Mounts") or [])
w("networks.json", ns.get("Networks") or {})

sumj={"Id":doc.get("Id"),"Name":doc.get("Name"),"Image":cfg.get("Image"),
      "Status":st.get("Status"),"Running":st.get("Running"),"Pid":st.get("Pid"),"StartedAt":st.get("StartedAt")}
w("summary.json", sumj)
PY

  local img status pid
  img="$(python3 -c "import json;print(json.load(open('${dir}/summary.json'))['Image'])" 2>/dev/null || echo '?')"
  status="$(python3 -c "import json;print(json.load(open('${dir}/summary.json'))['Status'])" 2>/dev/null || echo '?')"
  pid="$(python3 -c "import json;print(json.load(open('${dir}/summary.json'))['Pid'])" 2>/dev/null || echo '0')"
  emit docker_obs "phase=${phase} name=$(enc "$name") image=$(enc "$img") state=$(enc "$status") pid=${pid}"

  # 내부 상태 스냅샷
  _exec "$id" "$name" "$phase" "ip -j a"                                        "ip.addr.json"
  _exec "$id" "$name" "$phase" "ip -j r"                                        "ip.route.json"
  _exec "$id" "$name" "$phase" "sh -lc 'ss -tunap 2>/dev/null || netstat -tunap 2>/dev/null || true'" "sockets.txt"
  _exec "$id" "$name" "$phase" "sh -lc 'tc qdisc show 2>/dev/null || true'"     "tc.qdisc.txt"
  _exec "$id" "$name" "$phase" "sh -lc 'which nft >/dev/null 2>&1 && nft list ruleset || iptables-save 2>/dev/null || true'" "fw.txt"
  _exec "$id" "$name" "$phase" "tr '\\0' '\\n' </proc/1/environ"                "env.proc1.txt" || true
}

snapshot_containers(){
  docker_ok || { emit docker_warn "msg=docker_unavailable"; return 0; }
  local lines
  if [[ "${ONLY_RUNNING}" == "1" ]]; then
    if [[ -n "${NAME_FILTER}" ]]; then
      lines="$(docker ps --filter status=running --format '{{.ID}} {{.Names}}' | grep -E "${NAME_FILTER}" || true)"
    else
      lines="$(docker ps --filter status=running --format '{{.ID}} {{.Names}}' || true)"
    fi
  else
    if [[ -n "${NAME_FILTER}" ]]; then
      lines="$(docker ps --all --format '{{.ID}} {{.Names}}' | grep -E "${NAME_FILTER}" || true)"
    else
      lines="$(docker ps --all --format '{{.ID}} {{.Names}}' || true)"
    fi
  fi
  [[ -z "$lines" ]] && { emit docker_obs "phase=${PHASE} msg=$(enc 'no containers match')"; return 0; }
  while read -r id name; do
    [[ -z "$id" || -z "$name" ]] && continue
    inspect_one "$id" "$name" "$PHASE"
  done <<< "$lines"
}

snapshot_networks(){
  docker_ok || return 0
  local dir="${OBS_DIR}/${PHASE}/_networks"; mkdir -p "$dir"
  local nets
  if [[ -n "${NET_FILTER}" ]]; then
    nets="$(docker network ls --format '{{.Name}}' | grep -E "${NET_FILTER}" || true)"
  else
    nets="$(docker network ls --format '{{.Name}}')"
  fi
  for n in $nets; do
    docker network inspect "$n" > "${dir}/${n}.json" 2>/dev/null || true
    emit docker_net "phase=${PHASE} net=$(enc "$n") saved=1"
  done
}

case "${PHASE}" in pre|post|snap) ;; *) PHASE="snap";; esac
emit docker_marker "phase=${PHASE}"
snapshot_containers
snapshot_networks
emit docker_marker "phase=${PHASE}_done"
