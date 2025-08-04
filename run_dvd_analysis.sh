#!/bin/bash
# 수정된 DVD 네트워크 분석 실행 스크립트
# 위치: /home/kali/MTD/MTD_full_testbed/run_dvd_analysis_fixed.sh

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 로고
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║    🚁 DVD 네트워크 분석기 (수정됨)                             ║"
echo "║                                                                  ║"
echo "║    • 실제 DVD 컨테이너 이름 감지                               ║"
echo "║    • 실시간 MAVLink 트래픽 분석                                 ║"
echo "║    • 공격 패턴 탐지 및 CTI 생성                                ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 함수 정의
check_requirements() {
    echo -e "${BLUE}📋 시스템 요구사항 확인...${NC}"
    
    # Docker 확인
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    # Python 3 확인
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 모든 요구사항이 충족되었습니다.${NC}"
}

detect_dvd_containers() {
    echo -e "${BLUE}🔍 DVD 컨테이너 감지...${NC}"
    
    # 실행 중인 모든 컨테이너 확인
    echo -e "${CYAN}현재 실행 중인 컨테이너:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    
    # DVD 관련 컨테이너 찾기
    DVD_CONTAINERS=($(docker ps --format "{{.Names}}" | grep -E "(dvd|companion|flight|ground|simulator)" || true))
    
    if [ ${#DVD_CONTAINERS[@]} -eq 0 ]; then
        echo -e "${RED}❌ DVD 관련 컨테이너를 찾을 수 없습니다.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ 발견된 DVD 컨테이너:${NC}"
    for container in "${DVD_CONTAINERS[@]}"; do
        echo -e "${CYAN}  • ${container}${NC}"
        
        # 컨테이너 네트워크 정보 확인
        CONTAINER_IP=$(docker inspect "$container" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || echo "N/A")
        echo -e "${YELLOW}    IP: ${CONTAINER_IP}${NC}"
    done
    
    # 메인 컨테이너 선택 (companion-computer 우선)
    MAIN_CONTAINER=""
    for container in "${DVD_CONTAINERS[@]}"; do
        if [[ "$container" == *"companion"* ]]; then
            MAIN_CONTAINER="$container"
            break
        fi
    done
    
    # companion이 없으면 첫 번째 컨테이너 사용
    if [ -z "$MAIN_CONTAINER" ]; then
        MAIN_CONTAINER="${DVD_CONTAINERS[0]}"
    fi
    
    echo -e "${GREEN}🎯 메인 분석 대상: ${MAIN_CONTAINER}${NC}"
    return 0
}

check_dvd_status() {
    echo -e "${BLUE}🔍 DVD 환경 상태 확인...${NC}"
    
    if detect_dvd_containers; then
        return 0
    else
        echo -e "${YELLOW}⚠️ DVD 컨테이너가 실행되지 않았습니다.${NC}"
        return 1
    fi
}

start_dvd_environment() {
    echo -e "${BLUE}🚀 DVD 환경 시작...${NC}"
    
    # DVD 디렉토리 확인
    if [ ! -d "./Damn-Vulnerable-Drone" ]; then
        echo -e "${RED}❌ Damn-Vulnerable-Drone 디렉토리를 찾을 수 없습니다.${NC}"
        echo -e "${YELLOW}다음 명령으로 DVD를 클론하세요:${NC}"
        echo "git clone https://github.com/nicholasaleks/Damn-Vulnerable-Drone.git"
        exit 1
    fi
    
    # DVD docker-compose 실행
    cd Damn-Vulnerable-Drone
    
    # 기존 컨테이너 정리
    echo -e "${YELLOW}기존 컨테이너 정리...${NC}"
    docker-compose down -v --remove-orphans 2>/dev/null || true
    
    # 새로 시작
    echo -e "${YELLOW}DVD 컨테이너 시작...${NC}"
    docker-compose up -d
    
    cd ..
    
    echo -e "${YELLOW}⏳ DVD 컨테이너 초기화 대기 (15초)...${NC}"
    sleep 15
    
    if detect_dvd_containers; then
        echo -e "${GREEN}✅ DVD 환경 시작 완료${NC}"
        return 0
    else
        echo -e "${RED}❌ DVD 환경 시작 실패${NC}"
        return 1
    fi
}

create_simple_network_analyzer() {
    echo -e "${BLUE}🐍 간단한 네트워크 분석기 생성...${NC}"
    
    cat > simple_dvd_analyzer.py << 'EOF'
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
EOF

    chmod +x simple_dvd_analyzer.py
    echo -e "${GREEN}✅ 간단한 네트워크 분석기 생성 완료${NC}"
}

install_python_dependencies() {
    echo -e "${BLUE}📦 Python 의존성 설치...${NC}"
    
    # 기본 패키지 설치
    python3 -m pip install --user docker scapy numpy pandas matplotlib > /dev/null 2>&1 || {
        echo -e "${YELLOW}⚠️ 일부 패키지 설치 실패. 기본 기능만 사용합니다.${NC}"
    }
    
    echo -e "${GREEN}✅ Python 의존성 설치 완료${NC}"
}

run_simple_analysis() {
    echo -e "${BLUE}🔬 간단한 분석 실행...${NC}"
    
    if [ -z "$MAIN_CONTAINER" ]; then
        echo -e "${RED}❌ 분석할 컨테이너가 없습니다.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}🎯 분석 대상: ${MAIN_CONTAINER}${NC}"
    
    # Python 분석기 실행
    python3 simple_dvd_analyzer.py "$MAIN_CONTAINER"
}

show_status() {
    echo -e "${BLUE}📊 시스템 상태${NC}"
    echo "================================"
    
    # 모든 컨테이너 상태
    echo -e "${CYAN}전체 컨테이너:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    
    # DVD 관련 컨테이너만
    if detect_dvd_containers > /dev/null 2>&1; then
        echo -e "${CYAN}DVD 컨테이너 상세 정보:${NC}"
        for container in "${DVD_CONTAINERS[@]}"; do
            echo -e "${YELLOW}📦 ${container}:${NC}"
            
            # IP 주소
            CONTAINER_IP=$(docker inspect "$container" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || echo "N/A")
            echo "  IP: $CONTAINER_IP"
            
            # 포트 정보
            PORTS=$(docker port "$container" 2>/dev/null || echo "No ports")
            echo "  포트: $PORTS"
            
            # 상태
            STATUS=$(docker inspect "$container" --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
            echo "  상태: $STATUS"
            echo ""
        done
    fi
    
    echo -e "${CYAN}📡 접속 가능한 서비스:${NC}"
    echo "• DVD 웹 인터페이스: http://localhost (포트가 매핑된 경우)"
    echo "• MAVLink: udp://localhost:14550 (포트가 매핑된 경우)"
    echo "• 결과 파일: ./results/ 디렉토리"
    echo ""
}

stop_dvd() {
    echo -e "${YELLOW}🛑 DVD 환경 중지...${NC}"
    
    cd Damn-Vulnerable-Drone 2>/dev/null || {
        echo -e "${YELLOW}⚠️ DVD 디렉토리를 찾을 수 없습니다.${NC}"
        return
    }
    
    docker-compose down
    cd ..
    
    echo -e "${GREEN}✅ DVD 환경이 중지되었습니다.${NC}"
}

cleanup() {
    echo -e "${YELLOW}🧹 시스템 정리...${NC}"
    
    # 백그라운드 프로세스 중지
    pkill -f "simple_dvd_analyzer.py" 2>/dev/null || true
    
    echo -e "${GREEN}✅ 정리 완료${NC}"
}

# 시그널 핸들러
trap cleanup SIGINT SIGTERM

# 메인 로직
case "${1:-auto}" in
    "check")
        check_requirements
        check_dvd_status
        ;;
    "start-dvd")
        check_requirements
        start_dvd_environment
        ;;
    "status")
        show_status
        ;;
    "analyze")
        check_requirements
        if check_dvd_status; then
            create_simple_network_analyzer
            install_python_dependencies
            run_simple_analysis
        else
            echo -e "${RED}❌ DVD 컨테이너가 실행되지 않았습니다.${NC}"
            echo -e "${YELLOW}다음 명령으로 DVD를 시작하세요: $0 start-dvd${NC}"
        fi
        ;;
    "stop")
        stop_dvd
        ;;
    "clean")
        cleanup
        ;;
    "auto"|*)
        echo -e "${CYAN}🤖 자동 실행 모드${NC}"
        check_requirements
        
        if ! check_dvd_status; then
            echo -e "${YELLOW}DVD 환경을 시작합니다...${NC}"
            if ! start_dvd_environment; then
                echo -e "${RED}❌ DVD 환경 시작에 실패했습니다.${NC}"
                echo -e "${YELLOW}수동으로 DVD를 시작해보세요:${NC}"
                echo "cd Damn-Vulnerable-Drone && docker-compose up -d"
                exit 1
            fi
        fi
        
        echo -e "${YELLOW}분석 도구 준비...${NC}"
        create_simple_network_analyzer
        install_python_dependencies
        
        show_status
        
        echo -e "${GREEN}🎉 분석 환경이 준비되었습니다!${NC}"
        echo -e "${CYAN}분석을 시작하려면: $0 analyze${NC}"
        ;;
esac

# 사용법 도움말
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "사용법: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  auto      모든 환경 자동 설정 (기본값)"
    echo "  check     시스템 요구사항 및 DVD 상태 확인"
    echo "  start-dvd DVD 환경 시작"
    echo "  analyze   네트워크 분석 실행"
    echo "  status    시스템 상태 확인"
    echo "  stop      DVD 환경 중지"
    echo "  clean     시스템 정리"
    echo ""
    echo "예제:"
    echo "  $0              # 자동 환경 설정"
    echo "  $0 analyze      # 분석 실행"
    echo "  $0 status       # 상태 확인"
    echo ""
fi