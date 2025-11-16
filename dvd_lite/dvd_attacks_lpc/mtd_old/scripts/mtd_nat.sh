#!/usr/bin/env bash
set -euo pipefail

# --- Backend auto detect ---
if command -v nft >/dev/null 2>&1; then BACKEND="${BACKEND:-nft}"; else BACKEND="${BACKEND:-iptables}"; fi

# --- Params ---
PROTO="${PROTO:-udp}"                 # udp|tcp
PUB_PORT="${PUB_PORT:-14550}"         # 공개 포트 (nodeport)
MODE="${MODE:-nodeport}"              # nodeport | flatlan
BR_IF="${BR_IF:-}"                    # flatlan 모드일 때 브리지 IF
CONNTRACK_KICK="${CONNTRACK_KICK:-1}" # 스위치 시 conntrack 삭제(1/0)

CHAIN_NFT="prerouting"                # nftables nat hook chain
TABLE_FAM="ip"
TABLE_NFT="mtd"
CHAIN_IPT="MTD_DNAT"

need_root(){ if [[ $EUID -ne 0 ]]; then echo "Run as root"; exit 1; fi; }

# ---------- nftables: simple rule replace (no maps) ----------
nft_init() {
  need_root
  # table/chain 준비
  nft list table ${TABLE_FAM} ${TABLE_NFT} >/dev/null 2>&1 || nft add table ${TABLE_FAM} ${TABLE_NFT}
  nft list chain ${TABLE_FAM} ${TABLE_NFT} ${CHAIN_NFT} >/dev/null 2>&1 || \
    nft add chain ${TABLE_FAM} ${TABLE_NFT} ${CHAIN_NFT} "{ type nat hook prerouting priority -100; }"
}

# 현재 dport 규칙의 handle를 찾는다
nft_find_handle() {
  nft --numeric --handle list chain ${TABLE_FAM} ${TABLE_NFT} ${CHAIN_NFT} 2>/dev/null \
    | awk -v p="${PUB_PORT}" -v proto="${PROTO}" '
        /handle/ && $0 ~ proto" dport "p && $0 ~ /dnat/ { for(i=1;i<=NF;i++){ if($i=="handle"){print $(i+1)} } }' \
    | tail -n1
}

# 룰 문자열 생성 (ip:port 시도, 안 되면 ip-only로 대체)
nft_build_rule() {
  local ip="$1"; local pr="$2"
  if [[ "${MODE}" == "nodeport" ]]; then
    echo "${PROTO} dport ${PUB_PORT} dnat to ${ip}:${pr}"
  else
    echo "iif \"${BR_IF}\" ${PROTO} dport ${PUB_PORT} dnat to ${ip}:${pr}"
  fi
}
nft_build_rule_iponly() {
  local ip="$1"
  if [[ "${MODE}" == "nodeport" ]]; then
    echo "${PROTO} dport ${PUB_PORT} dnat to ${ip}"
  else
    echo "iif \"${BR_IF}\" ${PROTO} dport ${PUB_PORT} dnat to ${ip}"
  fi
}

nft_swap() {
  need_root
  local ipport="$1"
  local ip="${ipport%:*}"; local pr="${ipport#*:}"

  # 체인 보장
  nft_init

  # 먼저 ip:port 규칙 시도(검증 모드 -c)
  local rule rule_iponly handle
  rule="$(nft_build_rule "${ip}" "${pr}")"
  if nft -c add rule ${TABLE_FAM} ${TABLE_NFT} ${CHAIN_NFT} ${rule} >/dev/null 2>&1; then
    :
  else
    # ip:port를 지원하지 않는 경우 ip-only로 폴백
    rule="$(nft_build_rule_iponly "${ip}")"
  fi

  handle="$(nft_find_handle)"
  if [[ -n "${handle}" ]]; then
    nft replace rule ${TABLE_FAM} ${TABLE_NFT} ${CHAIN_NFT} handle "${handle}" ${rule}
  else
    nft add rule ${TABLE_FAM} ${TABLE_NFT} ${CHAIN_NFT} ${rule}
  fi
}

# ---------- iptables fallback ----------
ipt_init() {
  need_root
  iptables -t nat -N "${CHAIN_IPT}" 2>/dev/null || true
  if ! iptables -t nat -C PREROUTING -p ${PROTO} --dport ${PUB_PORT} -j "${CHAIN_IPT}" 2>/dev/null; then
    iptables -t nat -A PREROUTING -p ${PROTO} --dport ${PUB_PORT} -j "${CHAIN_IPT}"
  fi
  iptables -t nat -F "${CHAIN_IPT}"
}

ipt_switch() {
  need_root
  local ipport="$1"
  local ip="${ipport%:*}"; local pr="${ipport#*:}"
  iptables -t nat -F "${CHAIN_IPT}"
  iptables -t nat -A "${CHAIN_IPT}" -p ${PROTO} --dport ${PUB_PORT} -j DNAT --to-destination "${ip}:${pr}"
}

# ---------- conntrack ----------
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
    [[ -n "${2:-}" ]] || { echo "usage: $0 swap <ip:port> [old_ip:old_port]"; exit 2; }
    if [[ "${BACKEND}" == "nft" ]]; then nft_swap "$2"; else ipt_switch "$2"; fi
    if [[ -n "${3:-}" && "${CONNTRACK_KICK}" == "1" ]]; then kick_conntrack_dst "${3%:*}" "${3#*:}"; fi
    ;;
  kick)
    [[ -n "${2:-}" && -n "${3:-}" ]] || { echo "usage: $0 kick <ip> <port>"; exit 2; }
    kick_conntrack_dst "$2" "$3"
    ;;
  *)
    echo "usage: $0 {init|swap <ip:port> [old_ip:old_port]|kick <ip> <port>}"
    exit 2
    ;;
esac
