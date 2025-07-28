#!/usr/bin/env python3
"""
수정된 MAVLink 연결 테스트 스크립트
"""
import socket
import struct
import time

def create_mavlink_heartbeat():
    """올바른 MAVLink HEARTBEAT 메시지 생성"""
    # MAVLink 2.0 HEARTBEAT 메시지
    payload = struct.pack('<BBBBBB',
        6,    # type (MAV_TYPE_GCS)
        0,    # autopilot
        0,    # base_mode
        0, 0, 0  # custom_mode (처음 3바이트)
    )
    
    # 추가 바이트 (system_status, mavlink_version)
    payload += struct.pack('<BB', 3, 3)
    
    # MAVLink 2.0 헤더
    header = struct.pack('<BBBBBB',
        0xFD,  # STX (MAVLink 2.0) 
        len(payload),  # payload length
        0,     # incompatible flags
        0,     # compatible flags
        1,     # sequence
        255    # system ID (GCS)
    )
    
    return header + b'\x00' + payload

def test_mavlink_connection():
    """MAVLink 연결 테스트"""
    
    targets = [
        ("10.13.0.2", 14550, "Flight Controller"),
        ("10.13.0.4", 14550, "Ground Control Station")
    ]
    
    for host, port, name in targets:
        print(f"\n🔍 {name} 테스트 ({host}:{port})")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            
            heartbeat = create_mavlink_heartbeat()
            print(f"📡 HEARTBEAT 전송 중... ({len(heartbeat)} bytes)")
            
            sock.sendto(heartbeat, (host, port))
            
            try:
                data, addr = sock.recvfrom(1024)
                print(f"✅ 응답 받음: {len(data)} bytes from {addr}")
                print(f"📊 응답 데이터: {data[:20].hex()}")
                
                # MAVLink 메시지 파싱 시도
                if len(data) >= 8:
                    if data[0] == 0xFD:  # MAVLink 2.0
                        print("📡 MAVLink 2.0 메시지 확인됨")
                    elif data[0] == 0xFE:  # MAVLink 1.0
                        print("📡 MAVLink 1.0 메시지 확인됨")
                
            except socket.timeout:
                print("⏳ 응답 없음 (타임아웃)")
                
        except Exception as e:
            print(f"❌ 연결 오류: {e}")
        finally:
            sock.close()

if __name__ == "__main__":
    print("🎯 MAVLink 연결 테스트 시작")
    test_mavlink_connection()
