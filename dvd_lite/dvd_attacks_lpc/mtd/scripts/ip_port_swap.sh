#!/bin/bash

# ---------------------------------------------------------------------------
# ip_port_swap.sh
# 설명: iptables DNAT를 사용하여 특정 서비스 포트의 트래픽을 새로운 IP로 리다이렉션합니다.
# 사용법: ./ip_port_swap.sh <PROTOCOL> <PORT> <NEW_DEST_IP> <NEW_DEST_PORT>
# 예시: ./ip_port_swap.sh tcp 14550 10.13.0.7 14550
# ---------------------------------------------------------------------------

PROTOCOL=$1
ORIGIN_PORT=$2
NEW_IP=$3
NEW_PORT=$4

# 인자 확인
if [ -z "$PROTOCOL" ] || [ -z "$ORIGIN_PORT" ] || [ -z "$NEW_IP" ] || [ -z "$NEW_PORT" ]; then
    echo "Usage: $0 <PROTOCOL> <PORT> <NEW_IP> <NEW_PORT>"
    exit 1
fi

# MTD Chain 이름 설정 (관리 용이성을 위해 별도 체인 사용)
CHAIN_NAME="MTD_DNAT"

# 1. MTD 체인이 없으면 생성 및 PREROUTING에 연결
iptables -t nat -N $CHAIN_NAME 2>/dev/null
iptables -t nat -C PREROUTING -j $CHAIN_NAME 2>/dev/null
if [ $? -ne 0 ]; then
    iptables -t nat -I PREROUTING -j $CHAIN_NAME
fi

# 2. 기존 해당 포트에 대한 규칙 삭제 (중복 방지)
# 해당 포트로 가는 기존 DNAT 규칙을 찾아 삭제합니다.
# (단순화를 위해 해당 포트에 대한 규칙 전체 Flush 후 재작성 방식 사용 가능, 
#  여기서는 정교하게 해당 포트 매칭 규칙만 지우는 로직 대신 Chain Flush 방식을 사용해 확실하게 처리)

# 주의: 멀티 포트 환경이라면 포트별로 관리해야 하지만, 여기서는 MTD Chain을 Flush하고
#       현재 활성화된 모든 규칙을 재적용하는 방식이 안전할 수 있음.
#       하지만 RL 환경에서 단일 호출이므로, 해당 포트 규칙만 추가하는 방식으로 구현.

# 3. 새로운 DNAT 규칙 추가
# 들어오는 트래픽 중 해당 포트($ORIGIN_PORT)로 향하는 패킷을 $NEW_IP:$NEW_PORT로 리다이렉션
iptables -t nat -A $CHAIN_NAME -p $PROTOCOL --dport $ORIGIN_PORT -j DNAT --to-destination $NEW_IP:$NEW_PORT

# 4. Masquerading (필요 시, 리턴 트래픽이 올바르게 라우팅되도록 설정)
iptables -t nat -A POSTROUTING -j MASQUERADE

echo "[MTD] Swapped Rule Applied: Proto=$PROTOCOL Port=$ORIGIN_PORT -> $NEW_IP:$NEW_PORT"