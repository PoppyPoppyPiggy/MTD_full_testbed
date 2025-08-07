#!/usr/bin/env python3
"""
DVD 시스템 연결 확인 및 테스트 스크립트
현재 상황에 최적화됨 - 시스템이 활성화된 상태
"""

import asyncio
import socket
import time
import json
import urllib.request
import urllib.error
from datetime import datetime

class DVDConnectionTester:
    def __init__(self):
        self.target_ips = {
            "simulator": "10.13.0.5",
            "flight-controller": "10.13.0.2", 
            "companion-computer": "10.13.0.3",
            "ground-control-station": "10.13.0.4"
        }
        
        self.test_results = {}
    
    def test_http_service(self, ip, port, path="/"):
        """HTTP 서비스 테스트"""
        url = f"http://{ip}:{port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                status = response.status
                content_length = len(response.read())
                return True, {
                    "status": status,
                    "content_length": content_length,
                    "url": url
                }
        except Exception as e:
            return False, {"error": str(e), "url": url}
    
    async def test_tcp_port(self, ip, port, timeout=5):
        """TCP 포트 연결 테스트"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True, "connected"
        except asyncio.TimeoutError:
            return False, "timeout"
        except ConnectionRefusedError:
            return False, "refused"
        except Exception as e:
            return False, f"error: {str(e)}"
    
    def test_udp_port(self, ip, port, timeout=3):
        """UDP 포트 테스트 (MAVLink용)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            # MAVLink HEARTBEAT 요청 시뮬레이션
            heartbeat_request = b'\xfe\x09\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            sock.sendto(heartbeat_request, (ip, port))
            
            # 응답 대기
            try:
                data, addr = sock.recvfrom(1024)
                return True, {"response_length": len(data), "from": addr}
            except socket.timeout:
                return False, {"error": "no_response"}
            
        except Exception as e:
            return False, {"error": str(e)}
        finally:
            sock.close()
    
    async def comprehensive_test(self):
        """종합 연결 테스트"""
        print("🔍 DVD 시스템 종합 연결 테스트 시작")
        print("=" * 60)
        
        # 1. 웹 서비스 테스트
        print("\n🌐 웹 서비스 테스트:")
        
        # Simulator 웹 인터페이스
        success, result = self.test_http_service("10.13.0.5", 8000)
        if success:
            print(f"✅ Simulator Web UI: {result['url']}")
            print(f"   📄 상태: {result['status']}, 크기: {result['content_length']} bytes")
        else:
            print(f"❌ Simulator Web UI 실패: {result['error']}")
        
        # Simulator API
        success, result = self.test_http_service("10.13.0.5", 8080)
        if success:
            print(f"✅ Simulator API: {result['url']}")
            print(f"   📄 상태: {result['status']}, 크기: {result['content_length']} bytes")
        else:
            print(f"❌ Simulator API 실패: {result['error']}")
        
        # Companion Computer Flask
        success, result = self.test_http_service("10.13.0.3", 5000)
        if success:
            print(f"✅ Companion Computer Flask: {result['url']}")
        else:
            print(f"⏳ Companion Computer Flask: {result['error']}")
        
        # 2. TCP 포트 테스트
        print("\n🔌 TCP 포트 테스트:")
        
        tcp_ports = [
            ("10.13.0.2", 5760, "Flight Controller TCP"),
            ("10.13.0.3", 5000, "Companion Computer Flask"),
            ("10.13.0.5", 8000, "Simulator Web"),
            ("10.13.0.5", 8080, "Simulator API")
        ]
        
        for ip, port, service in tcp_ports:
            success, status = await self.test_tcp_port(ip, port)
            icon = "✅" if success else "⏳"
            print(f"   {icon} {service} ({ip}:{port}): {status}")
        
        # 3. MAVLink UDP 포트 테스트
        print("\n📡 MAVLink UDP 포트 테스트:")
        
        mavlink_ports = [
            ("10.13.0.2", 14550, "Flight Controller MAVLink"),
            ("10.13.0.2", 14551, "Flight Controller Secondary"),
            ("10.13.0.4", 14550, "Ground Control Station")
        ]
        
        for ip, port, service in mavlink_ports:
            success, result = self.test_udp_port(ip, port)
            if success:
                print(f"✅ {service} ({ip}:{port}): 응답 받음")
                if 'response_length' in result:
                    print(f"   📊 응답 길이: {result['response_length']} bytes")
            else:
                print(f"⏳ {service} ({ip}:{port}): {result.get('error', 'no response')}")
        
        # 4. 특별 테스트: Gazebo 시뮬레이터
        print("\n🎮 Gazebo 시뮬레이터 테스트:")
        
        # Gazebo Web UI 확인
        gazebo_ports = [9002, 11345]  # Gazebo web interface, Gazebo master
        for port in gazebo_ports:
            success, status = await self.test_tcp_port("10.13.0.5", port)
            service_name = "Gazebo Web" if port == 9002 else "Gazebo Master"
            icon = "✅" if success else "⏳"
            print(f"   {icon} {service_name} (10.13.0.5:{port}): {status}")
    
    def create_attack_config(self):
        """공격 테스트용 설정 생성"""
        config = {
            "timestamp": datetime.now().isoformat(),
            "target_system": {
                "primary_target": "10.13.0.5",  # Simulator
                "flight_controller": "10.13.0.2",
                "companion_computer": "10.13.0.3",
                "ground_control": "10.13.0.4"
            },
            "available_interfaces": {
                "web_ui": "http://10.13.0.5:8000",
                "api_endpoint": "http://10.13.0.5:8080",
                "mavlink_tcp": "10.13.0.2:5760",
                "mavlink_udp": "10.13.0.2:14550",
                "companion_flask": "http://10.13.0.3:5000"
            },
            "attack_vectors": {
                "web_attacks": [
                    {"type": "directory_traversal", "target": "http://10.13.0.5:8000"},
                    {"type": "api_enumeration", "target": "http://10.13.0.5:8080"},
                    {"type": "flask_debug", "target": "http://10.13.0.3:5000"}
                ],
                "network_attacks": [
                    {"type": "mavlink_injection", "target": "10.13.0.2:14550"},
                    {"type": "tcp_scan", "target": "10.13.0.0/24"},
                    {"type": "service_discovery", "target": "all"}
                ],
                "drone_specific": [
                    {"type": "gps_spoofing", "target": "mavlink"},
                    {"type": "command_injection", "target": "mavlink"},
                    {"type": "parameter_manipulation", "target": "mavlink"}
                ]
            }
        }
        
        with open("dvd_attack_config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        return config
    
    def generate_test_scripts(self):
        """테스트 스크립트 생성"""
        
        # 1. MAVLink 연결 테스트
        mavlink_test = '''#!/usr/bin/env python3
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
'''
        
        with open("test_mavlink_connection.py", "w") as f:
            f.write(mavlink_test)
        
        # 2. 웹 인터페이스 탐색 스크립트
        web_explorer = '''#!/usr/bin/env python3
"""
DVD 웹 인터페이스 탐색 스크립트
"""
import urllib.request
import urllib.error
import json

def explore_web_interface():
    """웹 인터페이스 탐색"""
    
    base_urls = [
        "http://10.13.0.5:8000",
        "http://10.13.0.5:8080", 
        "http://10.13.0.3:5000"
    ]
    
    common_paths = [
        "/",
        "/api",
        "/status",
        "/config",
        "/admin",
        "/debug",
        "/info",
        "/version"
    ]
    
    for base_url in base_urls:
        print(f"\\n🔍 탐색 중: {base_url}")
        
        for path in common_paths:
            url = base_url + path
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    if response.status == 200:
                        content = response.read().decode('utf-8', errors='ignore')
                        print(f"✅ {path}: {response.status} ({len(content)} chars)")
                        
                        # JSON 응답인지 확인
                        if 'application/json' in response.headers.get('content-type', ''):
                            try:
                                json_data = json.loads(content)
                                print(f"   📊 JSON 키: {list(json_data.keys())}")
                            except:
                                pass
                    else:
                        print(f"⚠️  {path}: {response.status}")
                        
            except urllib.error.HTTPError as e:
                if e.code != 404:  # 404는 일반적이므로 무시
                    print(f"⚠️  {path}: HTTP {e.code}")
            except Exception as e:
                print(f"❌ {path}: {str(e)}")

if __name__ == "__main__":
    explore_web_interface()
'''
        
        with open("explore_web_interfaces.py", "w") as f:
            f.write(web_explorer)
        
        return ["test_mavlink_connection.py", "explore_web_interfaces.py"]

async def main():
    """메인 실행 함수"""
    print("🎯 DVD 시스템 연결 확인 및 테스트")
    print("시스템이 활성화된 상태에 최적화됨")
    print()
    
    tester = DVDConnectionTester()
    
    # 종합 테스트 실행
    await tester.comprehensive_test()
    
    # 공격 설정 생성
    print("\n⚙️  공격 테스트 설정 생성 중...")
    config = tester.create_attack_config()
    print("✅ 설정 저장: dvd_attack_config.json")
    
    # 테스트 스크립트 생성
    print("\n📝 테스트 스크립트 생성 중...")
    scripts = tester.generate_test_scripts()
    print("✅ 생성된 스크립트:")
    for script in scripts:
        print(f"   • {script}")
    
    print(f"\n🎉 DVD 시스템 준비 완료!")
    print(f"\n📋 다음 단계:")
    print(f"  1. 생성된 스크립트 실행:")
    print(f"     python3 test_mavlink_connection.py")
    print(f"     python3 explore_web_interfaces.py")
    print(f"  2. 웹 인터페이스 접속: http://10.13.0.5:8000")
    print(f"  3. 논문용 공격 테스트 시작")
    
    print(f"\n🔗 주요 접속 정보:")
    print(f"  🌐 시뮬레이터 웹 UI: http://10.13.0.5:8000")
    print(f"  🔌 시뮬레이터 API: http://10.13.0.5:8080") 
    print(f"  📡 MAVLink 연결: 10.13.0.2:14550 (UDP)")
    print(f"  🖥️  Flask 앱: http://10.13.0.3:5000")

if __name__ == "__main__":
    asyncio.run(main())