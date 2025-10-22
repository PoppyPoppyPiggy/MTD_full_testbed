#!/usr/bin/env bash
set -euo pipefail

# 백엔드 자동 감지(nft 가능하면 nft 우선)
if command -v nft >/dev/null 2>&1; then BACKEND="${BACKEND:-nft}"; else BACKEND="${BACKEND:-iptables}"; fi

PROTO="${PROTO:-udp}"           # udp|tcp
PUB_PORT="${PUB_PORT:-14550}"   # nodeport 모드 공개포트
BR_IF="${BR_IF:-}"              # flatlan 모드 인터페이스
ACTIVE_IPPORT_FILE="${ACTIVE_IPPORT_FILE:-/tmp/mtd_active_ipport}"  # iptables fallback
CHAIN_NAT="MTD_DNAT"
SET_OLD="mtd_old"   # (선택) 이전 목적지 추적용 ipset (conntrack drop와 함께 사용)

need_root() {
  if [[ $EUID -ne 0 ]]; then echo "Run as root"; exit 1; fi
}

# ---------- nftables 구현: set swap로 원자적 스위칭 ----------
nft_init() {
  need_root
  nft list table ip mtd >/dev/null 2>&1 || nft add table ip mtd
  # nodeport: port만 기준으로 dnat map (inet_service -> ipv4_addr . inet_service)
  nft list set ip mtd dstmap >/dev/null 2>&1 || nft add set ip mtd dstmap { type inet_service : ipv4_addr . inet_service; }
  nft list chain ip mtd prerouting >/dev/null 2>&1 || nft add chain ip mtd prerouting { type nat hook prerouting priority -100; }

  if [[ "${MODE:-nodeport}" == "nodeport" ]]; then
    # 공개포트로 들어오는 패킷을 dstmap으로 DNAT
    nft list ruleset | grep -q "ip mtd prerouting" | grep -q "dport ${PUB_PORT}" || \
      nft add rule ip mtd prerouting ${PROTO} dport ${PUB_PORT} dnat to numgen inc mod 1 map @dstmap
  else
    # flatlan: 브리지로 들어오고, dport=PUB_PORT이면 dstmap
    [[ -z "$BR_IF" ]] && { echo "BR_IF required for flatlan mode"; exit 2; }
    nft list ruleset | grep -q "iif \"$BR_IF\"" || \
      nft add rule ip mtd prerouting iif \"$BR_IF\" ${PROTO} dport ${PUB_PORT} dnat to numgen inc mod 1 map @dstmap
  fi
}

nft_swap() {
  need_root
  # 인자: "10.13.0.2:14550" 형태 하나만 활성화(원자 스왑)
  local ipport="$1"
  local ip="${ipport%:*}"; local pr="${ipport#*:}"
  # 임시 세트 생성 후 swap
  nft add set ip mtd newmap { type inet_service : ipv4_addr . inet_service; } 2>/dev/null || true
  nft flush set ip mtd newmap
  nft add element ip mtd newmap { ${PUB_PORT} : ${ip} . ${pr} }
  nft swap set ip mtd dstmap newmap
  nft delete set ip mtd newmap 2>/dev/null || true
}

# ---------- iptables fallback: DNAT 룰 자체를 교체 ----------
ipt_init() {
  need_root
  iptables -t nat -N "${CHAIN_NAT}" 2>/dev/null || true
  # PREROUTING → MTD_DNAT 연결
  if ! iptables -t nat -C PREROUTING -p ${PROTO} --dport ${PUB_PORT} -j "${CHAIN_NAT}" 2>/dev/null; then
    iptables -t nat -A PREROUTING -p ${PROTO} --dport ${PUB_PORT} -j "${CHAIN_NAT}"
  fi
  # 체인 비움(최상단 1개 DNAT로 운영)
  iptables -t nat -F "${CHAIN_NAT}"
  : > "${ACTIVE_IPPORT_FILE}"
}

ipt_switch() {
  need_root
  local ipport="$1"
  local ip="${ipport%:*}"; local pr="${ipport#*:}"
  iptables -t nat -F "${CHAIN_NAT}"
  iptables -t nat -A "${CHAIN_NAT}" -p ${PROTO} --dport ${PUB_PORT} -j DNAT --to-destination ${ip}:${pr}
  echo "${ipport}" > "${ACTIVE_IPPORT_FILE}"
}

# ---------- conntrack 부분 삭제 ----------
kick_conntrack_dst() {
  need_root
  local ip="$1"; local pr="$2"
  if command -v conntrack >/dev/null 2>&1; then
    case "${PROTO}" in
      udp) conntrack -D -p udp --dport "${pr}" -d "${ip}" || true ;;
      tcp) conntrack -D -p tcp --dport "${pr}" -d "${ip}" || true ;;
    esac
  fi
}

# ---------- ENTRY ----------
case "${1:-}" in
  init)
    if [[ "${BACKEND}" == "nft" ]]; then nft_init; else ipt_init; fi
    ;;
  swap)
    # $2 = "ip:port", [$3="old_ip:old_port" (optional, conntrack kick)]
    [[ -z "${2:-}" ]] && { echo "usage: $0 swap <ip:port> [old_ip:old_port]"; exit 2; }
    if [[ "${BACKEND}" == "nft" ]]; then nft_swap "$2"; else ipt_switch "$2"; fi
    if [[ -n "${3:-}" && "${CONNTRACK_KICK:-1}" == "1" ]]; then
      kick_conntrack_dst "${3%:*}" "${3#*:}"
    fi
    ;;
  kick)
    # $2=ip $3=port
    [[ -n "${2:-}" && -n "${3:-}" ]] || { echo "usage: $0 kick <ip> <port>"; exit 2; }
    kick_conntrack_dst "$2" "$3"
    ;;
  *)
    echo "usage: $0 {init|swap <ip:port> [old_ip:old_port]|kick <ip> <port>}"
    exit 2
    ;;
esac
