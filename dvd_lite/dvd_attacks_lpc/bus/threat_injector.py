#!/usr/bin/env python3
import argparse
from logger import log_bus_event

def inject_threat(ip=None, port=None, reason="Manual threat injection"):
    if not ip and not port:
        print("오류: IP 또는 포트 중 하나는 반드시 지정해야 합니다.")
        return
        
    threat_data = {"reason": reason}
    if ip:
        threat_data["target_ip"] = ip
    if port:
        threat_data["target_port"] = port
        
    log_bus_event("threat_detected", threat_data)
    print(f"성공: 위협 정보 주입 완료. 데이터: {threat_data}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MTD 엔진에 모의 위협 정보를 주입하는 도구")
    parser.add_argument("--ip", type=str, help="차단할 대상 IP 주소")
    parser.add_argument("--port", type=int, help="차단할 대상 포트")
    parser.add_argument("--reason", type=str, default="Manual threat injection", help="위협 탐지 사유")
    args = parser.parse_args()
    
    inject_threat(args.ip, args.port, args.reason)