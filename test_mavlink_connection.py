#!/usr/bin/env python3
"""
MAVLink 연결 및 통신 테스트
"""
import socket
import time
import struct

def test_mavlink_heartbeat():
    """MAVLink HEARTBEAT 메시지 테스트"""
    
    # UDP 소켓 생성
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    
    try:
        # MAVLink HEARTBEAT 메시지 구성 (MAVLink 1.0)
        # 메시지 ID: 0 (HEARTBEAT)
        heartbeat = struct.pack('<BBBBBBBBBBBBBBBBBBBB',
            0xfe,  # STX
            0x09,  # 페이로드 길이
            0x00,  # 패킷 시퀀스
            0xff,  # 시스템 ID (GCS)
            0x00,  # 컴포넌트 ID
            0x00,  # 메시지 ID (HEARTBEAT)
            0x00, 0x00, 0x00, 0x00,  # type, autopilot, base_mode, custom_mode
            0x03,  # system_status
            0x03,  # mavlink_version
            0x00, 0x00  # 체크섬
        )
        
        print("MAVLink HEARTBEAT 전송 중...")
        sock.sendto(heartbeat, ("10.13.0.2", 14550))
        
        try:
            data, addr = sock.recvfrom(1024)
            print(f"✅ 응답 받음: {len(data)} bytes from {addr}")
            print(f"📊 응답 데이터: {data[:20].hex()}")
            return True
        except socket.timeout:
            print("⏳ 응답 없음 (타임아웃)")
            return False
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        return False
    finally:
        sock.close()

if __name__ == "__main__":
    test_mavlink_heartbeat()
