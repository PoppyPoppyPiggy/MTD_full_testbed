import os
import json
import time
from scapy.all import IP, TCP
from netfilterqueue import NetfilterQueue

STATE_FILE = "/shared/mtd_state.json"
HIT_LOG_FILE = "/shared/hit.log"

def get_current_surface():
    """현재 공격 표면 정보를 state 파일에서 읽어옵니다."""
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            return state['ip'], int(state['port']), state['target_drone_ip']
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return "0.0.0.0", 0, "172.18.0.11" # 기본값

def log_hit(attacker_ip):
    """탐지된 히트 정보를 파일에 기록합니다."""
    with open(HIT_LOG_FILE, 'a') as f:
        f.write(f"{attacker_ip}\n")

def process_packet(packet):
    """NetfilterQueue를 통해 들어오는 패킷을 처리하는 콜백 함수"""
    try:
        pkt = IP(packet.get_payload())
        current_ip, current_port, target_drone_ip = get_current_surface()

        if TCP in pkt and pkt[IP].dst == current_ip and pkt[TCP].dport == current_port:
            attacker_ip = pkt[IP].src
            print(f"GATEWAY: HIT from {attacker_ip} to {current_ip}:{current_port}")
            log_hit(attacker_ip)
            
            pkt[IP].dst = target_drone_ip
            del pkt[IP].chksum
            del pkt[TCP].chksum
            
            packet.set_payload(bytes(pkt))
    except Exception:
        pass # 비 IP 패킷 등은 무시
    
    packet.accept()

def main():
    time.sleep(2)
    print("GATEWAY: Initializing iptables rules...")
    os.system("iptables -t nat -A PREROUTING -i eth0 -j NFQUEUE --queue-num 1")
    nfqueue = NetfilterQueue()
    nfqueue.bind(1, process_packet)
    
    print("GATEWAY: Controller started. Waiting for packets...")
    try:
        nfqueue.run()
    except (KeyboardInterrupt, OSError):
        print("GATEWAY: Stopping Controller.")
    finally:
        print("GATEWAY: Flushing iptables rules.")
        os.system("iptables -t nat -F")
        try:
            nfqueue.unbind()
        except Exception:
            pass

if __name__ == "__main__":
    main()