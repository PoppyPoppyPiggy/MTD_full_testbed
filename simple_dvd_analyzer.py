#!/usr/bin/env python3
"""
간단한 DVD 네트워크 분석기
"""

import subprocess
import json
import time
import docker
import sys
from datetime import datetime
import os

class SimpleDVDAnalyzer:
    def __init__(self, container_name):
        self.container_name = container_name
        self.docker_client = docker.from_env()
        self.results_dir = "./results"
        os.makedirs(self.results_dir, exist_ok=True)
        
    def get_container_info(self):
        """컨테이너 정보 가져오기"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            
            # 네트워크 정보
            networks = container.attrs['NetworkSettings']['Networks']
            container_ip = None
            for network_name, network_info in networks.items():
                if network_info.get('IPAddress'):
                    container_ip = network_info['IPAddress']
                    break
            
            return {
                'name': container.name,
                'status': container.status,
                'ip': container_ip,
                'image': container.image.tags[0] if container.image.tags else 'unknown',
                'ports': container.ports
            }
        except Exception as e:
            print(f"❌ 컨테이너 정보 조회 실패: {e}")
            return None
    
    def monitor_container_logs(self):
        """컨테이너 로그 모니터링"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            
            print(f"📋 {self.container_name} 로그 모니터링 시작...")
            
            # 로그 파일 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"{self.results_dir}/container_logs_{timestamp}.txt"
            
            with open(log_file, 'w') as f:
                f.write(f"=== {self.container_name} 로그 모니터링 시작 ===\n")
                f.write(f"시작 시간: {datetime.now()}\n\n")
                
                # 실시간 로그 스트림
                for log_line in container.logs(stream=True, follow=True):
                    log_text = log_line.decode('utf-8', errors='ignore').strip()
                    if log_text:
                        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        formatted_log = f"[{timestamp_str}] {log_text}"
                        
                        print(formatted_log)
                        f.write(formatted_log + "\n")
                        f.flush()
                        
        except KeyboardInterrupt:
            print("\n⏹️ 로그 모니터링 중지")
        except Exception as e:
            print(f"❌ 로그 모니터링 오류: {e}")
    
    def capture_network_traffic(self):
        """네트워크 트래픽 캡처 (tcpdump 사용)"""
        try:
            container_info = self.get_container_info()
            if not container_info or not container_info['ip']:
                print("❌ 컨테이너 IP 주소를 찾을 수 없습니다.")
                return
            
            container_ip = container_info['ip']
            print(f"📡 {container_ip}의 네트워크 트래픽 캡처 시작...")
            
            # tcpdump 명령
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pcap_file = f"{self.results_dir}/network_capture_{timestamp}.pcap"
            
            # MAVLink 포트 (14550, 14551) 캡처
            cmd = [
                "sudo", "tcpdump", 
                "-i", "any",
                "-w", pcap_file,
                f"host {container_ip} and (port 14550 or port 14551 or port 5760)"
            ]
            
            print(f"실행 명령: {' '.join(cmd)}")
            print("⚠️ sudo 권한이 필요합니다.")
            
            process = subprocess.Popen(cmd)
            
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n⏹️ 트래픽 캡처 중지")
                process.terminate()
                print(f"📄 캡처 파일 저장: {pcap_file}")
                
        except Exception as e:
            print(f"❌ 네트워크 캡처 오류: {e}")
            print("💡 대안: Wireshark를 사용하여 수동으로 캡처하세요.")
    
    def analyze_container_stats(self):
        """컨테이너 통계 분석"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            
            print(f"📊 {self.container_name} 통계 분석...")
            
            # 통계 파일 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stats_file = f"{self.results_dir}/container_stats_{timestamp}.json"
            
            stats_data = []
            
            for i in range(10):  # 10회 수집
                stats = container.stats(stream=False)
                stats['timestamp'] = datetime.now().isoformat()
                stats_data.append(stats)
                
                # CPU 사용률 계산 (간단한 버전)
                cpu_percent = 0.0
                if 'cpu_stats' in stats and 'precpu_stats' in stats:
                    cpu_stats = stats['cpu_stats']
                    precpu_stats = stats['precpu_stats']
                    
                    if 'cpu_usage' in cpu_stats and 'cpu_usage' in precpu_stats:
                        cpu_delta = cpu_stats['cpu_usage']['total_usage'] - precpu_stats['cpu_usage']['total_usage']
                        system_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']
                        
                        if system_delta > 0:
                            cpu_percent = (cpu_delta / system_delta) * 100.0
                
                # 메모리 사용률
                memory_usage = 0
                memory_limit = 0
                if 'memory_stats' in stats:
                    memory_usage = stats['memory_stats'].get('usage', 0)
                    memory_limit = stats['memory_stats'].get('limit', 0)
                
                print(f"📈 [{i+1}/10] CPU: {cpu_percent:.2f}%, 메모리: {memory_usage/1024/1024:.1f}MB")
                
                time.sleep(2)
            
            # 통계 저장
            with open(stats_file, 'w') as f:
                json.dump(stats_data, f, indent=2)
            
            print(f"📄 통계 파일 저장: {stats_file}")
            
        except Exception as e:
            print(f"❌ 통계 분석 오류: {e}")
    
    def run_analysis(self):
        """분석 실행"""
        print(f"🚀 {self.container_name} 분석 시작")
        
        # 컨테이너 정보 출력
        container_info = self.get_container_info()
        if container_info:
            print("\n📋 컨테이너 정보:")
            for key, value in container_info.items():
                print(f"  {key}: {value}")
        
        print("\n선택하세요:")
        print("1. 로그 모니터링")
        print("2. 네트워크 트래픽 캡처")
        print("3. 컨테이너 통계 분석")
        print("4. 전체 분석")
        
        try:
            choice = input("\n선택 (1-4): ").strip()
            
            if choice == "1":
                self.monitor_container_logs()
            elif choice == "2":
                self.capture_network_traffic()
            elif choice == "3":
                self.analyze_container_stats()
            elif choice == "4":
                print("🔄 전체 분석 모드")
                # 병렬 실행은 복잡하므로 순차 실행
                print("1️⃣ 통계 분석 시작...")
                self.analyze_container_stats()
                print("\n2️⃣ 로그 모니터링 시작 (Ctrl+C로 중지)...")
                self.monitor_container_logs()
            else:
                print("❌ 잘못된 선택입니다.")
                
        except KeyboardInterrupt:
            print("\n👋 분석이 중단되었습니다.")
        except Exception as e:
            print(f"❌ 분석 오류: {e}")

def main():
    if len(sys.argv) != 2:
        print("사용법: python3 simple_dvd_analyzer.py <container_name>")
        sys.exit(1)
    
    container_name = sys.argv[1]
    analyzer = SimpleDVDAnalyzer(container_name)
    analyzer.run_analysis()

if __name__ == "__main__":
    main()
