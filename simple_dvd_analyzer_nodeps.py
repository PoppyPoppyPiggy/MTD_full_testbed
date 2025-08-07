#!/usr/bin/env python3
"""
의존성 없는 간단한 DVD 분석기
Docker API 대신 shell 명령 사용
"""

import subprocess
import json
import time
import sys
import os
import signal
from datetime import datetime
import threading

class SimpleDVDAnalyzer:
    def __init__(self, container_name):
        self.container_name = container_name
        self.results_dir = "./results"
        self.running = True
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        print(f"\n⏹️ 신호 {signum} 수신. 정리 중...")
        self.running = False
        sys.exit(0)
    
    def run_command(self, cmd):
        """Shell 명령 실행"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return "", "Timeout", -1
        except Exception as e:
            return "", str(e), -1
    
    def get_container_info(self):
        """컨테이너 정보 가져오기 (Docker CLI 사용)"""
        try:
            # 컨테이너 존재 확인
            cmd = f"docker inspect {self.container_name}"
            stdout, stderr, code = self.run_command(cmd)
            
            if code != 0:
                print(f"❌ 컨테이너 {self.container_name}을 찾을 수 없습니다.")
                return None
            
            # JSON 파싱
            container_data = json.loads(stdout)[0]
            
            # 네트워크 정보 추출
            networks = container_data.get('NetworkSettings', {}).get('Networks', {})
            container_ip = None
            for network_name, network_info in networks.items():
                if network_info.get('IPAddress'):
                    container_ip = network_info['IPAddress']
                    break
            
            # 포트 정보 추출
            ports = container_data.get('NetworkSettings', {}).get('Ports', {})
            port_mappings = {}
            for container_port, host_info in ports.items():
                if host_info:
                    for mapping in host_info:
                        host_port = mapping.get('HostPort', 'N/A')
                        port_mappings[container_port] = host_port
            
            return {
                'name': container_data.get('Name', '').lstrip('/'),
                'status': container_data.get('State', {}).get('Status', 'unknown'),
                'ip': container_ip,
                'image': container_data.get('Config', {}).get('Image', 'unknown'),
                'ports': port_mappings,
                'created': container_data.get('Created', ''),
                'started': container_data.get('State', {}).get('StartedAt', '')
            }
        except json.JSONDecodeError:
            print(f"❌ 컨테이너 정보 파싱 실패")
            return None
        except Exception as e:
            print(f"❌ 컨테이너 정보 조회 실패: {e}")
            return None
    
    def monitor_container_logs(self):
        """컨테이너 로그 모니터링"""
        print(f"📋 {self.container_name} 로그 모니터링 시작...")
        print("⏹️ Ctrl+C로 중지")
        
        # 로그 파일 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"{self.results_dir}/container_logs_{timestamp}.txt"
        
        try:
            with open(log_file, 'w') as f:
                f.write(f"=== {self.container_name} 로그 모니터링 ===\n")
                f.write(f"시작 시간: {datetime.now()}\n\n")
                
                # Docker logs -f 명령 실행
                cmd = f"docker logs -f --timestamps {self.container_name}"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, 
                                         stderr=subprocess.STDOUT, text=True)
                
                line_count = 0
                while self.running:
                    line = process.stdout.readline()
                    if not line:
                        break
                    
                    line = line.strip()
                    if line:
                        print(line)
                        f.write(line + "\n")
                        f.flush()
                        
                        line_count += 1
                        if line_count % 10 == 0:
                            print(f"📊 로그 라인 수: {line_count}")
                
                process.terminate()
                process.wait()
                
        except KeyboardInterrupt:
            print("\n⏹️ 로그 모니터링 중지")
        except Exception as e:
            print(f"❌ 로그 모니터링 오류: {e}")
        
        print(f"📄 로그 파일 저장: {log_file}")
    
    def capture_network_traffic(self):
        """네트워크 트래픽 캡처"""
        container_info = self.get_container_info()
        if not container_info or not container_info['ip']:
            print("❌ 컨테이너 IP 주소를 찾을 수 없습니다.")
            return
        
        container_ip = container_info['ip']
        print(f"📡 {container_ip}의 네트워크 트래픽 캡처 시작...")
        print("⏹️ Ctrl+C로 중지")
        
        # tcpdump 명령
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pcap_file = f"{self.results_dir}/network_capture_{timestamp}.pcap"
        
        # MAVLink 포트 (14550, 14551) 및 웹 포트 캡처
        cmd = f"timeout 60 tcpdump -i any -w {pcap_file} 'host {container_ip} and (port 14550 or port 14551 or port 5760 or port 3000 or port 8080)'"
        
        print(f"실행 명령: {cmd}")
        print("⚠️ sudo 권한이 필요할 수 있습니다.")
        
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            while self.running and process.poll() is None:
                time.sleep(1)
            
            if process.poll() is None:
                process.terminate()
                process.wait()
            
            stdout, stderr = process.communicate()
            
            if os.path.exists(pcap_file):
                file_size = os.path.getsize(pcap_file)
                print(f"📄 캡처 파일 저장: {pcap_file} ({file_size} bytes)")
                
                # 간단한 분석
                self._analyze_pcap_file(pcap_file)
            else:
                print("❌ 캡처 파일이 생성되지 않았습니다.")
                if stderr:
                    print(f"오류: {stderr}")
                
        except Exception as e:
            print(f"❌ 네트워크 캡처 오류: {e}")
            print("💡 대안: sudo 권한으로 실행하거나 Wireshark를 사용하세요.")
    
    def _analyze_pcap_file(self, pcap_file):
        """PCAP 파일 간단 분석"""
        try:
            # tcpdump를 사용한 간단한 분석
            cmd = f"tcpdump -r {pcap_file} -c 10"
            stdout, stderr, code = self.run_command(cmd)
            
            if code == 0 and stdout:
                print(f"\n📊 캡처된 패킷 샘플 (처음 10개):")
                print(stdout)
            
            # 패킷 수 세기
            cmd = f"tcpdump -r {pcap_file} | wc -l"
            stdout, stderr, code = self.run_command(cmd)
            
            if code == 0:
                packet_count = stdout.strip()
                print(f"📈 총 캡처된 패킷 수: {packet_count}")
                
        except Exception as e:
            print(f"❌ PCAP 분석 오류: {e}")
    
    def analyze_container_stats(self):
        """컨테이너 통계 분석"""
        print(f"📊 {self.container_name} 통계 분석...")
        
        # 통계 파일 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = f"{self.results_dir}/container_stats_{timestamp}.json"
        
        stats_data = []
        
        try:
            for i in range(10):  # 10회 수집
                print(f"📈 [{i+1}/10] 통계 수집 중...")
                
                # Docker stats 명령 사용
                cmd = f"docker stats {self.container_name} --no-stream --format 'table {{{{.Container}}}}\\t{{{{.CPUPerc}}}}\\t{{{{.MemUsage}}}}\\t{{{{.NetIO}}}}\\t{{{{.BlockIO}}}}'"
                stdout, stderr, code = self.run_command(cmd)
                
                if code == 0:
                    lines = stdout.strip().split('\n')
                    if len(lines) >= 2:  # 헤더 + 데이터
                        data_line = lines[1]
                        parts = data_line.split('\t')
                        
                        stats_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'container': parts[0] if len(parts) > 0 else 'N/A',
                            'cpu_percent': parts[1] if len(parts) > 1 else 'N/A',
                            'memory_usage': parts[2] if len(parts) > 2 else 'N/A',
                            'network_io': parts[3] if len(parts) > 3 else 'N/A',
                            'block_io': parts[4] if len(parts) > 4 else 'N/A'
                        }
                        
                        stats_data.append(stats_entry)
                        
                        print(f"   CPU: {stats_entry['cpu_percent']}, 메모리: {stats_entry['memory_usage']}")
                else:
                    print(f"   ❌ 통계 수집 실패: {stderr}")
                
                if not self.running:
                    break
                    
                time.sleep(2)
            
            # 통계 저장
            with open(stats_file, 'w') as f:
                json.dump(stats_data, f, indent=2)
            
            print(f"📄 통계 파일 저장: {stats_file}")
            
        except KeyboardInterrupt:
            print("\n⏹️ 통계 수집 중지")
        except Exception as e:
            print(f"❌ 통계 분석 오류: {e}")
    
    def real_time_monitoring(self):
        """실시간 모니터링 (로그 + 통계)"""
        print(f"🔄 {self.container_name} 실시간 모니터링 시작")
        print("⏹️ Ctrl+C로 중지")
        
        # 로그 모니터링 스레드
        log_thread = threading.Thread(target=self._monitor_logs_background)
        log_thread.daemon = True
        log_thread.start()
        
        # 통계 모니터링
        try:
            while self.running:
                # 5초마다 간단한 통계 출력
                cmd = f"docker stats {self.container_name} --no-stream --format '{{{{.CPUPerc}}}} {{{{.MemUsage}}}}'"
                stdout, stderr, code = self.run_command(cmd)
                
                if code == 0:
                    parts = stdout.split()
                    cpu = parts[0] if len(parts) > 0 else 'N/A'
                    memory = parts[1] if len(parts) > 1 else 'N/A'
                    
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"[{current_time}] 📊 CPU: {cpu}, 메모리: {memory}")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n⏹️ 실시간 모니터링 중지")
        
        self.running = False
    
    def _monitor_logs_background(self):
        """백그라운드 로그 모니터링"""
        cmd = f"docker logs -f --tail=5 {self.container_name}"
        
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT, text=True)
            
            while self.running:
                line = process.stdout.readline()
                if not line:
                    break
                
                line = line.strip()
                if line and 'ERROR' in line.upper() or 'WARNING' in line.upper():
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"[{current_time}] 🚨 {line}")
            
            process.terminate()
            process.wait()
            
        except Exception as e:
            pass  # 백그라운드에서는 조용히 실패
    
    def quick_health_check(self):
        """빠른 건강 상태 확인"""
        print(f"🔍 {self.container_name} 건강 상태 확인")
        
        container_info = self.get_container_info()
        if not container_info:
            return
        
        print(f"\n📋 컨테이너 정보:")
        print(f"  이름: {container_info['name']}")
        print(f"  상태: {container_info['status']}")
        print(f"  IP: {container_info['ip']}")
        print(f"  이미지: {container_info['image']}")
        
        if container_info['ports']:
            print(f"  포트 매핑:")
            for container_port, host_port in container_info['ports'].items():
                print(f"    {container_port} -> {host_port}")
        
        # 프로세스 확인
        cmd = f"docker exec {self.container_name} ps aux"
        stdout, stderr, code = self.run_command(cmd)
        
        if code == 0:
            process_lines = stdout.strip().split('\n')
            print(f"\n🔧 실행 중인 프로세스 ({len(process_lines)-1}개):")
            
            # 처음 5개 프로세스만 표시
            for line in process_lines[:6]:
                print(f"  {line}")
        
        # 네트워크 연결 확인
        if container_info['ip']:
            cmd = f"ping -c 3 {container_info['ip']}"
            stdout, stderr, code = self.run_command(cmd)
            
            if code == 0:
                print(f"✅ 네트워크 연결 정상: {container_info['ip']}")
            else:
                print(f"❌ 네트워크 연결 실패: {container_info['ip']}")
    
    def run_analysis(self):
        """분석 실행"""
        print(f"🚀 {self.container_name} 분석 시작")
        
        # 빠른 건강 상태 확인
        self.quick_health_check()
        
        print("\n📋 분석 옵션:")
        print("1. 빠른 건강 상태 확인")
        print("2. 로그 모니터링")
        print("3. 네트워크 트래픽 캡처")
        print("4. 컨테이너 통계 분석")
        print("5. 실시간 모니터링 (로그 + 통계)")
        print("6. 종료")
        
        try:
            while self.running:
                choice = input("\n선택 (1-6): ").strip()
                
                if choice == "1":
                    self.quick_health_check()
                elif choice == "2":
                    self.monitor_container_logs()
                elif choice == "3":
                    self.capture_network_traffic()
                elif choice == "4":
                    self.analyze_container_stats()
                elif choice == "5":
                    self.real_time_monitoring()
                elif choice == "6":
                    print("👋 분석을 종료합니다.")
                    break
                else:
                    print("❌ 잘못된 선택입니다. 1-6 사이의 숫자를 입력하세요.")
                    
        except KeyboardInterrupt:
            print("\n👋 분석이 중단되었습니다.")
        except Exception as e:
            print(f"❌ 분석 오류: {e}")
        finally:
            self.running = False

def main():
    if len(sys.argv) != 2:
        print("사용법: python3 simple_dvd_analyzer_nodeps.py <container_name>")
        print("예제: python3 simple_dvd_analyzer_nodeps.py companion-computer")
        sys.exit(1)
    
    container_name = sys.argv[1]
    analyzer = SimpleDVDAnalyzer(container_name)
    analyzer.run_analysis()

if __name__ == "__main__":
    main()