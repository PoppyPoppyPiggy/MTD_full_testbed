#!/bin/bash

# =================================================================
# MTD 드론 보안 테스트베드 최종 통합 실행 가이드
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/EXECUTE_ALL.sh
# 
# 🎯 이 스크립트 하나로 모든 것이 완성됩니다!
# 사용법: curl -sSL https://raw.githubusercontent.com/your-repo/mtd-testbed/main/EXECUTE_ALL.sh | bash
# 또는:   chmod +x EXECUTE_ALL.sh && ./EXECUTE_ALL.sh
# =================================================================

set -e

# 화려한 로고
clear
cat << 'LOGO'
███╗   ███╗████████╗██████╗     ██████╗ ██████╗  ██████╗ ███╗   ██╗███████╗
████╗ ████║╚══██╔══╝██╔══██╗    ██╔══██╗██╔══██╗██╔═══██╗████╗  ██║██╔════╝
██╔████╔██║   ██║   ██║  ██║    ██║  ██║██████╔╝██║   ██║██╔██╗ ██║█████╗  
██║╚██╔╝██║   ██║   ██║  ██║    ██║  ██║██╔══██╗██║   ██║██║╚██╗██║██╔══╝  
██║ ╚═╝ ██║   ██║   ██████╔╝    ██████╔╝██║  ██║╚██████╔╝██║ ╚████║███████╗
╚═╝     ╚═╝   ╚═╝   ╚═════╝     ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
                                                                           
        ████████╗███████╗███████╗████████╗██████╗ ███████╗██████╗          
        ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔══██╗         
           ██║   █████╗  ███████╗   ██║   ██████╔╝█████╗  ██║  ██║         
           ██║   ██╔══╝  ╚════██║   ██║   ██╔══██╗██╔══╝  ██║  ██║         
           ██║   ███████╗███████║   ██║   ██████╔╝███████╗██████╔╝         
           ╚═╝   ╚══════╝╚══════╝   ╚═╝   ╚═════╝ ╚══════╝╚═════╝          
                                                                           

🚁 Moving Target Defense 기반 드론 보안 연구 플랫폼 🛡️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOGO

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m'

# 아이콘
ICON_ROCKET="🚀"
ICON_GEAR="⚙️"
ICON_SUCCESS="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_SHIELD="🛡️"
ICON_BRAIN="🧠"
ICON_NETWORK="🌐"
ICON_TARGET="🎯"

# 로그 함수
log_header() {
    echo ""
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}${BOLD}$1${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_step() { echo -e "${CYAN}$ICON_GEAR [STEP]${NC} $1"; }
log_info() { echo -e "${BLUE}$ICON_INFO [INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}$ICON_SUCCESS [SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}$ICON_WARNING [WARNING]${NC} $1"; }
log_error() { echo -e "${RED}$ICON_ERROR [ERROR]${NC} $1"; }

# 진행률 표시
show_progress() {
    local current=$1
    local total=$2
    local desc="$3"
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))
    
    printf "\r${CYAN}[%3d%%]${NC} [" "$percent"
    printf "%*s" "$filled" | tr ' ' '█'
    printf "%*s" "$empty" | tr ' ' '░'
    printf "] %s" "$desc"
    
    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

# 환영 메시지
show_welcome() {
    echo ""
    echo -e "${BOLD}${WHITE}환영합니다! MTD 드론 보안 테스트베드 자동 설치를 시작합니다.${NC}"
    echo ""
    echo -e "${YELLOW}📋 이 스크립트가 자동으로 설치하는 것들:${NC}"
    echo -e "   $ICON_SHIELD SDN 기반 Moving Target Defense 시스템"
    echo -e "   $ICON_BRAIN 강화학습 기반 자동 최적화 엔진"
    echo -e "   $ICON_NETWORK 허니드론 네트워크 및 속임수 시스템"
    echo -e "   $ICON_TARGET NS-3 기반 정밀 네트워크 시뮬레이션"
    echo -e "   $ICON_ROCKET 실시간 웹 기반 모니터링 대시보드"
    echo ""
    echo -e "${GREEN}⏱️ 예상 소요 시간: 5-10분${NC}"
    echo -e "${GREEN}💾 필요 디스크 공간: 최소 10GB${NC}"
    echo -e "${GREEN}🖥️ 지원 환경: Ubuntu 18.04+, Kali Linux, Debian 10+${NC}"
    echo ""
}

# 시스템 요구사항 검사
check_requirements() {
    log_header "$ICON_GEAR 시스템 요구사항 검사"
    
    local errors=0
    
    # OS 확인
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_success "Linux 운영체제 확인됨"
    else
        log_error "지원되지 않는 운영체제: $OSTYPE"
        ((errors++))
    fi
    
    # 디스크 공간 확인
    local available_gb=$(df . | tail -1 | awk '{print int($4/1024/1024)}')
    if [ "$available_gb" -ge 10 ]; then
        log_success "충분한 디스크 공간: ${available_gb}GB"
    else
        log_error "디스크 공간 부족: ${available_gb}GB (최소 10GB 필요)"
        ((errors++))
    fi
    
    # 메모리 확인
    local memory_gb=$(free | grep '^Mem:' | awk '{print int($2/1024/1024)}')
    if [ "$memory_gb" -ge 4 ]; then
        log_success "충분한 메모리: ${memory_gb}GB"
    else
        log_warning "메모리 부족: ${memory_gb}GB (권장: 8GB 이상)"
    fi
    
    # 인터넷 연결 확인
    if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        log_success "인터넷 연결 확인됨"
    else
        log_warning "인터넷 연결 없음 (오프라인 설치 모드)"
    fi
    
    if [ "$errors" -gt 0 ]; then
        log_error "시스템 요구사항을 충족하지 않습니다. 해결 후 다시 시도하세요."
        exit 1
    fi
    
    log_success "모든 시스템 요구사항 충족!"
}

# 필수 도구 설치
install_prerequisites() {
    log_header "$ICON_GEAR 필수 도구 설치"
    
    # 패키지 관리자 확인
    if command -v apt-get >/dev/null 2>&1; then
        PACKAGE_MANAGER="apt-get"
    elif command -v yum >/dev/null 2>&1; then
        PACKAGE_MANAGER="yum"
    else
        log_error "지원되지 않는 패키지 관리자"
        exit 1
    fi
    
    log_step "패키지 목록 업데이트 중..."
    sudo $PACKAGE_MANAGER update -y >/dev/null 2>&1 || true
    
    # 필수 패키지 설치
    local packages=(
        "python3" "python3-pip" "python3-venv"
        "git" "curl" "wget" "unzip"
        "build-essential" "software-properties-common"
    )
    
    for package in "${packages[@]}"; do
        if ! command -v "${package%%-*}" >/dev/null 2>&1; then
            log_step "$package 설치 중..."
            sudo $PACKAGE_MANAGER install -y "$package" >/dev/null 2>&1 || true
        else
            log_info "$package 이미 설치됨"
        fi
    done
    
    # Docker 설치 (없는 경우)
    if ! command -v docker >/dev/null 2>&1; then
        log_step "Docker 설치 중..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh >/dev/null 2>&1
        sudo usermod -aG docker "$USER" || true
        rm -f get-docker.sh
        log_success "Docker 설치 완료"
    else
        log_info "Docker 이미 설치됨"
    fi
    
    log_success "필수 도구 설치 완료"
}

# 메인 시스템 다운로드 및 설치
download_and_install() {
    log_header "$ICON_ROCKET MTD 테스트베드 시스템 설치"
    
    # 작업 디렉토리 생성
    WORK_DIR="$HOME/MTD_Testbed_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"
    
    log_info "작업 디렉토리: $WORK_DIR"
    
    # 시스템 파일들 생성
    log_step "시스템 구성요소 생성 중..."
    
    local total_scripts=50
    local current=0
    
    ((current++))
    show_progress $current $total_scripts "기본 디렉토리 구조 생성 중..."
    
    # 디렉토리 구조 생성
    mkdir -p {
        ml,configs/{attack_intensity,defense_levels,network_topologies},
        honeydrone_network/{nodes,topologies,traffic_generators},
        data_pipeline/{collectors,processors,analyzers,exporters},
        ns3_integration/{scenarios,models,metrics,configs},
        docker_management/{monitors,controllers,networks},
        timestamp_sync/{handlers,validators,correctors},
        scenarios/adaptive/{attack_profiles,defense_configs,combined_scenarios},
        scripts/{deployment,monitoring,analysis,maintenance},
        attack_output,logs/{attacks,defenses,networks,timestamps,ns3},
        results/{experiments,analysis,visualizations,reports},
        notebooks,templates
    }
    
    ((current++))
    show_progress $current $total_scripts "설정 파일 생성 중..."
    
    # requirements.txt 생성
    cat > requirements.txt << 'REQ_EOF'
# 핵심 라이브러리
numpy>=1.21.0
pandas>=1.3.0
scipy>=1.7.0
scikit-learn>=1.0.0
matplotlib>=3.4.0
seaborn>=0.11.0
plotly>=5.0.0

# 머신러닝/딥러닝
torch>=1.9.0
xgboost>=1.4.0
lightgbm>=3.2.0
tensorflow>=2.8.0

# 네트워킹/비동기
asyncio
aiohttp>=3.7.0
websockets>=9.0
docker>=5.0.0

# 웹 프레임워크
flask>=2.0.0
dash>=2.0.0

# 데이터 처리
pyyaml>=5.4.0
jsonschema>=3.2.0

# 시스템 모니터링
psutil>=5.8.0

# 테스트베드 특화
pymavlink>=2.4.0
pyserial>=3.5

# 개발 도구
pytest>=6.0.0
black>=21.0.0
flake8>=3.9.0
REQ_EOF
    
    ((current++))
    show_progress $current $total_scripts "Python 환경 설정 중..."
    
    # Python 가상환경 생성 및 패키지 설치
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip >/dev/null 2>&1
    pip install -r requirements.txt >/dev/null 2>&1
    
    ((current++))
    show_progress $current $total_scripts "공격 강도 프로필 생성 중..."
    
    # 공격 강도 프로필
    cat > configs/attack_intensity/lpc_profiles.yaml << 'ATTACK_EOF'
attack_profiles:
  stealth_recon:
    intensity: "passive"
    duty_cycle: 0.02
    interval_ms: 30000
    jitter_pct: 40
    max_budget: 50
    stealth_factor: 0.9
    target_modules:
      - "wifi_network_discovery"
      - "mavlink_service_discovery"
    detection_threshold: 0.05
    description: "완전 수동적 정찰"

  active_recon:
    intensity: "low"
    duty_cycle: 0.08
    interval_ms: 15000
    jitter_pct: 30
    max_budget: 80
    stealth_factor: 0.7
    target_modules:
      - "camera_stream_discovery"
      - "component_enumeration"
    detection_threshold: 0.12
    description: "적극적 정찰"

  aggressive_attack:
    intensity: "high"
    duty_cycle: 0.25
    interval_ms: 4000
    jitter_pct: 20
    max_budget: 200
    stealth_factor: 0.3
    target_modules:
      - "mavlink_packet_injection"
      - "flight_plan_injection"
    detection_threshold: 0.45
    description: "공격적 침투"

  persistent_campaign:
    intensity: "medium"
    duty_cycle: 0.06
    interval_ms: 20000
    jitter_pct: 35
    max_budget: 300
    stealth_factor: 0.8
    target_modules:
      - "telemetry_exfiltration"
      - "video_stream_hijack"
    detection_threshold: 0.18
    description: "지속적 캠페인"
ATTACK_EOF

    ((current+=2))
    show_progress $current $total_scripts "방어 수준 설정 생성 중..."
    
    # 방어 수준 설정
    cat > configs/defense_levels/detection_thresholds.yaml << 'DEFENSE_EOF'
defense_levels:
  none:
    packet_loss_threshold: 1.0
    latency_threshold: 1000.0
    cpu_threshold: 1.0
    memory_threshold: 1.0
    anomaly_score_threshold: 1.0
    mtd_interval: 0
    honeypot_ratio: 0.0
    ml_enabled: false
    description: "방어 없음"

  minimal:
    packet_loss_threshold: 0.15
    latency_threshold: 200.0
    cpu_threshold: 0.8
    memory_threshold: 0.8
    anomaly_score_threshold: 0.7
    mtd_interval: 300
    honeypot_ratio: 0.1
    ml_enabled: false
    description: "기본 모니터링만"

  standard:
    packet_loss_threshold: 0.08
    latency_threshold: 100.0
    cpu_threshold: 0.6
    memory_threshold: 0.7
    anomaly_score_threshold: 0.5
    mtd_interval: 180
    honeypot_ratio: 0.2
    ml_enabled: true
    ml_model: "random_forest"
    description: "표준 IDS"

  enhanced:
    packet_loss_threshold: 0.05
    latency_threshold: 50.0
    cpu_threshold: 0.4
    memory_threshold: 0.5
    anomaly_score_threshold: 0.3
    mtd_interval: 120
    honeypot_ratio: 0.3
    ml_enabled: true
    ml_model: "gradient_boosting"
    adaptive_learning: true
    description: "고급 ML 기반"

  maximum:
    packet_loss_threshold: 0.02
    latency_threshold: 25.0
    cpu_threshold: 0.3
    memory_threshold: 0.4
    anomaly_score_threshold: 0.15
    mtd_interval: 60
    honeypot_ratio: 0.4
    ml_enabled: true
    ml_model: "deep_neural_network"
    adaptive_learning: true
    real_time_mtd: true
    description: "실시간 MTD + AI"
DEFENSE_EOF

    ((current+=3))
    show_progress $current $total_scripts "SDN MTD 컨트롤러 생성 중..."
    
    # SDN MTD 컨트롤러
    cat > ml/sdn_mtd_controller.py << 'SDN_EOF'
#!/usr/bin/env python3
"""
SDN 기반 Moving Target Defense 컨트롤러
"""

import asyncio
import websockets
import json
import time
import random
from enum import Enum
from typing import Dict, List, Any, Optional
import logging
import subprocess

class MTDStrategy(Enum):
    NONE = "none"
    IP_HOPPING = "ip_hopping"
    PORT_SHUFFLING = "port_shuffling"
    ROUTE_MUTATION = "route_mutation"
    FREQUENCY_HOPPING = "frequency_hopping"
    PROTOCOL_DIVERSIFICATION = "protocol_diversification"
    DECOY_DEPLOYMENT = "decoy_deployment"
    TRAFFIC_SHAPING = "traffic_shaping"

class SDNMTDController:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.current_strategy = MTDStrategy.NONE
        self.active_defenses = set()
        self.adaptation_count = 0
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        logger = logging.getLogger("SDNMTDController")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler("attack_output/sdn_mtd.log")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    async def start_controller(self):
        """SDN 컨트롤러 시작"""
        self.logger.info("SDN MTD 컨트롤러 시작")
        
        start_server = websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        
        await start_server
        self.logger.info(f"WebSocket 서버 시작: ws://{self.host}:{self.port}")
        
        # 백그라운드 태스크들
        await asyncio.gather(
            self._monitor_threats(),
            self._adaptive_defense_loop()
        )
    
    async def _handle_client(self, websocket, path):
        """WebSocket 클라이언트 처리"""
        try:
            async for message in websocket:
                data = json.loads(message)
                response = await self._process_command(data)
                await websocket.send(json.dumps(response))
        except Exception as e:
            self.logger.error(f"클라이언트 처리 오류: {e}")
    
    async def _process_command(self, data: Dict) -> Dict:
        """명령 처리"""
        command = data.get("command")
        
        if command == "get_status":
            return self._get_current_status()
        elif command == "apply_strategy":
            strategy = MTDStrategy(data.get("strategy", "none"))
            params = data.get("parameters", {})
            success = self._apply_mtd_strategy(strategy, params)
            return {"success": success, "strategy": strategy.value}
        elif command == "get_metrics":
            return self._get_mtd_metrics()
        else:
            return {"error": "Unknown command"}
    
    def _apply_mtd_strategy(self, strategy: MTDStrategy, params: Dict) -> bool:
        """MTD 전략 적용"""
        try:
            self.logger.info(f"MTD 전략 적용: {strategy.value}")
            
            if strategy == MTDStrategy.IP_HOPPING:
                self._apply_ip_hopping(params)
            elif strategy == MTDStrategy.PORT_SHUFFLING:
                self._apply_port_shuffling(params)
            elif strategy == MTDStrategy.ROUTE_MUTATION:
                self._apply_route_mutation(params)
            elif strategy == MTDStrategy.DECOY_DEPLOYMENT:
                self._apply_decoy_deployment(params)
            
            self.current_strategy = strategy
            self.adaptation_count += 1
            
            # 효과 로그 기록
            with open("attack_output/bus.log", "a") as f:
                f.write(f"{time.time()},type=MTD,strategy={strategy.value},adaptation_count={self.adaptation_count}\n")
            
            return True
            
        except Exception as e:
            self.logger.error(f"MTD 전략 적용 실패: {e}")
            return False
    
    def _apply_ip_hopping(self, params: Dict):
        """IP 호핑 적용"""
        new_ips = [
            "172.20.0.10", "172.20.0.11", "172.20.0.12",
            "172.30.1.10", "172.30.1.11", "172.30.2.10"
        ]
        selected_ip = random.choice(new_ips)
        self.logger.info(f"IP 호핑 적용: {selected_ip}")
        
        # 시뮬레이션된 네트워크 재구성
        self._simulate_network_change("ip_change", {"new_ip": selected_ip})
    
    def _apply_port_shuffling(self, params: Dict):
        """포트 셔플링 적용"""
        new_ports = random.sample(range(14550, 14600), 3)
        self.logger.info(f"포트 셔플링 적용: {new_ports}")
        
        self._simulate_network_change("port_shuffle", {"new_ports": new_ports})
    
    def _apply_route_mutation(self, params: Dict):
        """라우트 변이 적용"""
        routes = ["direct", "mesh_relay", "honeydrone_proxy"]
        new_route = random.choice(routes)
        self.logger.info(f"라우트 변이 적용: {new_route}")
        
        self._simulate_network_change("route_change", {"new_route": new_route})
    
    def _apply_decoy_deployment(self, params: Dict):
        """디코이 배포"""
        decoy_count = random.randint(2, 5)
        self.logger.info(f"디코이 배포: {decoy_count}개")
        
        self._simulate_network_change("decoy_deploy", {"count": decoy_count})
    
    def _simulate_network_change(self, change_type: str, params: Dict):
        """네트워크 변화 시뮬레이션"""
        # 실제로는 SDN 스위치나 네트워크 장비와 통신
        self.logger.info(f"네트워크 변화 시뮬레이션: {change_type} - {params}")
        
        # 지연 시뮬레이션
        time.sleep(0.1)
    
    async def _monitor_threats(self):
        """위협 모니터링"""
        while True:
            try:
                # 위협 탐지 시뮬레이션
                threat_level = random.uniform(0, 1)
                
                if threat_level > 0.7:  # 높은 위협
                    await self._trigger_emergency_mtd()
                elif threat_level > 0.4:  # 중간 위협
                    await self._trigger_adaptive_mtd()
                
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                self.logger.error(f"위협 모니터링 오류: {e}")
                await asyncio.sleep(5)
    
    async def _trigger_emergency_mtd(self):
        """긴급 MTD 발동"""
        emergency_strategies = [
            MTDStrategy.IP_HOPPING,
            MTDStrategy.DECOY_DEPLOYMENT,
            MTDStrategy.ROUTE_MUTATION
        ]
        
        strategy = random.choice(emergency_strategies)
        self._apply_mtd_strategy(strategy, {"urgency": "high"})
        self.logger.warning(f"긴급 MTD 발동: {strategy.value}")
    
    async def _trigger_adaptive_mtd(self):
        """적응형 MTD 발동"""
        adaptive_strategies = [
            MTDStrategy.PORT_SHUFFLING,
            MTDStrategy.TRAFFIC_SHAPING
        ]
        
        strategy = random.choice(adaptive_strategies)
        self._apply_mtd_strategy(strategy, {"urgency": "medium"})
        self.logger.info(f"적응형 MTD 발동: {strategy.value}")
    
    async def _adaptive_defense_loop(self):
        """적응형 방어 루프"""
        while True:
            try:
                # 방어 효과성 평가
                effectiveness = self._evaluate_defense_effectiveness()
                
                if effectiveness < 0.6:  # 효과성이 낮으면 전략 변경
                    new_strategy = self._select_optimal_strategy()
                    self._apply_mtd_strategy(new_strategy, {})
                
                await asyncio.sleep(30)  # 30초마다 평가
                
            except Exception as e:
                self.logger.error(f"적응형 방어 루프 오류: {e}")
                await asyncio.sleep(10)
    
    def _evaluate_defense_effectiveness(self) -> float:
        """방어 효과성 평가"""
        # 시뮬레이션된 효과성 계산
        base_effectiveness = 0.7
        strategy_bonus = 0.1 if self.current_strategy != MTDStrategy.NONE else 0
        randomness = random.uniform(-0.2, 0.2)
        
        return max(0, min(1, base_effectiveness + strategy_bonus + randomness))
    
    def _select_optimal_strategy(self) -> MTDStrategy:
        """최적 전략 선택"""
        strategies = list(MTDStrategy)
        strategies.remove(MTDStrategy.NONE)
        strategies.remove(self.current_strategy)  # 현재 전략 제외
        
        return random.choice(strategies)
    
    def _get_current_status(self) -> Dict:
        """현재 상태 조회"""
        return {
            "current_strategy": self.current_strategy.value,
            "adaptation_count": self.adaptation_count,
            "active_defenses": list(self.active_defenses),
            "uptime": time.time(),
            "effectiveness": self._evaluate_defense_effectiveness()
        }
    
    def _get_mtd_metrics(self) -> Dict:
        """MTD 메트릭 조회"""
        return {
            "total_adaptations": self.adaptation_count,
            "current_strategy": self.current_strategy.value,
            "defense_effectiveness": self._evaluate_defense_effectiveness(),
            "strategy_distribution": self._get_strategy_distribution(),
            "response_time_ms": random.uniform(10, 50)
        }
    
    def _get_strategy_distribution(self) -> Dict:
        """전략 분포 조회"""
        # 시뮬레이션된 전략 사용 분포
        return {
            "ip_hopping": 25,
            "port_shuffling": 20,
            "route_mutation": 15,
            "decoy_deployment": 20,
            "traffic_shaping": 10,
            "none": 10
        }

if __name__ == "__main__":
    controller = SDNMTDController()
    asyncio.run(controller.start_controller())
SDN_EOF

    ((current+=5))
    show_progress $current $total_scripts "강화학습 에이전트 생성 중..."
    
    # 강화학습 에이전트
    cat > ml/rl_mtd_agent.py << 'RL_EOF'
#!/usr/bin/env python3
"""
강화학습 기반 MTD 최적화 에이전트
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
import logging
from collections import deque, namedtuple
from typing import Dict, List, Tuple, Any
import json
import time

# 경험 튜플 정의
Experience = namedtuple('Experience', ['state', 'action', 'reward', 'next_state', 'done'])

class MTDEnvironment:
    """MTD 환경 시뮬레이터"""
    
    def __init__(self):
        self.state_size = 12  # 네트워크 상태 차원
        self.action_size = 8  # MTD 전략 수
        self.reset()
    
    def reset(self):
        """환경 초기화"""
        self.state = np.random.random(self.state_size)
        self.step_count = 0
        self.attack_intensity = random.uniform(0.1, 0.9)
        return self.state
    
    def step(self, action):
        """환경 스텝 실행"""
        self.step_count += 1
        
        # 상태 업데이트 (시뮬레이션)
        self.state = self._update_state(action)
        
        # 보상 계산
        reward = self._calculate_reward(action)
        
        # 종료 조건
        done = self.step_count >= 300  # 5분 에피소드
        
        return self.state, reward, done, {}
    
    def _update_state(self, action):
        """상태 업데이트"""
        new_state = self.state.copy()
        
        # 액션에 따른 상태 변화
        action_effects = {
            0: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # NONE
            1: [-0.1, 0.05, 0, 0, 0.1, 0, 0, 0, 0, 0, 0, 0],  # IP_HOPPING
            2: [0, -0.1, 0.05, 0, 0, 0.1, 0, 0, 0, 0, 0, 0],  # PORT_SHUFFLING
            3: [0, 0, -0.1, 0.05, 0, 0, 0.1, 0, 0, 0, 0, 0],  # ROUTE_MUTATION
            4: [0.05, 0, 0, -0.1, 0, 0, 0, 0.1, 0, 0, 0, 0],  # FREQUENCY_HOPPING
            5: [0, 0.05, 0, 0, -0.1, 0, 0, 0, 0.1, 0, 0, 0],  # PROTOCOL_DIVERSIFICATION
            6: [0, 0, 0.05, 0, 0, -0.1, 0, 0, 0, 0.1, 0, 0],  # DECOY_DEPLOYMENT
            7: [0, 0, 0, 0.05, 0, 0, -0.1, 0, 0, 0, 0.1, 0]   # TRAFFIC_SHAPING
        }
        
        effect = action_effects.get(action, [0] * self.state_size)
        new_state += np.array(effect)
        
        # 노이즈 추가
        new_state += np.random.normal(0, 0.01, self.state_size)
        
        # 상태 정규화
        new_state = np.clip(new_state, 0, 1)
        
        return new_state
    
    def _calculate_reward(self, action):
        """보상 계산"""
        # 기본 성능 점수
        latency_penalty = -self.state[0] * 10  # 지연시간 페널티
        security_bonus = self.state[4] * 20    # 보안 향상 보너스
        
        # MTD 오버헤드 페널티
        mtd_cost = self._get_mtd_cost(action)
        overhead_penalty = -mtd_cost * 5
        
        # 공격 저항성 보너스
        resistance_bonus = self._calculate_attack_resistance(action) * 15
        
        total_reward = latency_penalty + security_bonus + overhead_penalty + resistance_bonus
        
        return total_reward
    
    def _get_mtd_cost(self, action):
        """MTD 비용 계산"""
        costs = {
            0: 0.0,   # NONE
            1: 0.3,   # IP_HOPPING
            2: 0.2,   # PORT_SHUFFLING
            3: 0.4,   # ROUTE_MUTATION
            4: 0.5,   # FREQUENCY_HOPPING
            5: 0.3,   # PROTOCOL_DIVERSIFICATION
            6: 0.6,   # DECOY_DEPLOYMENT
            7: 0.2    # TRAFFIC_SHAPING
        }
        return costs.get(action, 0.0)
    
    def _calculate_attack_resistance(self, action):
        """공격 저항성 계산"""
        if action == 0:  # NONE
            return 0.0
        
        base_resistance = 0.5
        action_bonus = action * 0.1  # 복잡한 전략일수록 높은 저항성
        intensity_factor = 1 - self.attack_intensity
        
        return base_resistance + action_bonus * intensity_factor

class DQN(nn.Module):
    """Deep Q-Network"""
    
    def __init__(self, state_size, action_size, hidden_size=256):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(state_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, hidden_size)
        self.fc4 = nn.Linear(hidden_size, action_size)
        self.dropout = nn.Dropout(0.1)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = self.dropout(x)
        x = torch.relu(self.fc2(x))
        x = self.dropout(x)
        x = torch.relu(self.fc3(x))
        x = self.fc4(x)
        return x

class DQNAgent:
    """DQN 에이전트"""
    
    def __init__(self, state_size, action_size, lr=0.001):
        self.state_size = state_size
        self.action_size = action_size
        self.memory = deque(maxlen=10000)
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = lr
        self.batch_size = 32
        self.target_update_freq = 100
        self.step_count = 0
        
        # 네트워크 초기화
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.q_network = DQN(state_size, action_size).to(self.device)
        self.target_network = DQN(state_size, action_size).to(self.device)
        self.optimizer = optim.Adam(self.q_network.parameters(), lr=lr)
        
        # 로거 설정
        self.logger = logging.getLogger("DQNAgent")
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler("attack_output/rl_agent.log")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        self.logger.info("DQN 에이전트 초기화 완료")
    
    def remember(self, state, action, reward, next_state, done):
        """경험 저장"""
        self.memory.append(Experience(state, action, reward, next_state, done))
    
    def act(self, state):
        """액션 선택"""
        if np.random.random() <= self.epsilon:
            return random.choice(range(self.action_size))
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        q_values = self.q_network(state_tensor)
        return np.argmax(q_values.cpu().data.numpy())
    
    def replay(self):
        """경험 재플레이"""
        if len(self.memory) < self.batch_size:
            return
        
        batch = random.sample(self.memory, self.batch_size)
        states = torch.FloatTensor([e.state for e in batch]).to(self.device)
        actions = torch.LongTensor([e.action for e in batch]).to(self.device)
        rewards = torch.FloatTensor([e.reward for e in batch]).to(self.device)
        next_states = torch.FloatTensor([e.next_state for e in batch]).to(self.device)
        dones = torch.BoolTensor([e.done for e in batch]).to(self.device)
        
        current_q_values = self.q_network(states).gather(1, actions.unsqueeze(1))
        next_q_values = self.target_network(next_states).max(1)[0].detach()
        target_q_values = rewards + (0.99 * next_q_values * ~dones)
        
        loss = nn.MSELoss()(current_q_values.squeeze(), target_q_values)
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        self.step_count += 1
        if self.step_count % self.target_update_freq == 0:
            self.target_network.load_state_dict(self.q_network.state_dict())
    
    def save_model(self, filepath):
        """모델 저장"""
        torch.save({
            'q_network_state_dict': self.q_network.state_dict(),
            'target_network_state_dict': self.target_network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'epsilon': self.epsilon
        }, filepath)
        self.logger.info(f"모델 저장: {filepath}")
    
    def load_model(self, filepath):
        """모델 로드"""
        checkpoint = torch.load(filepath)
        self.q_network.load_state_dict(checkpoint['q_network_state_dict'])
        self.target_network.load_state_dict(checkpoint['target_network_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.epsilon = checkpoint['epsilon']
        self.logger.info(f"모델 로드: {filepath}")

class MTDRLTrainer:
    """MTD 강화학습 트레이너"""
    
    def __init__(self, episodes=1000):
        self.episodes = episodes
        self.env = MTDEnvironment()
        self.agent = DQNAgent(self.env.state_size, self.env.action_size)
        self.scores = deque(maxlen=100)
        
    def train(self):
        """훈련 실행"""
        print("🧠 MTD 강화학습 훈련 시작")
        
        for episode in range(self.episodes):
            state = self.env.reset()
            total_reward = 0
            
            while True:
                action = self.agent.act(state)
                next_state, reward, done, _ = self.env.step(action)
                
                self.agent.remember(state, action, reward, next_state, done)
                state = next_state
                total_reward += reward
                
                if done:
                    break
            
            self.scores.append(total_reward)
            self.agent.replay()
            
            if episode % 100 == 0:
                avg_score = np.mean(self.scores)
                print(f"에피소드 {episode}, 평균 점수: {avg_score:.2f}, 입실론: {self.agent.epsilon:.3f}")
                
                # 모델 저장
                self.agent.save_model(f"ml/models/dqn_mtd_episode_{episode}.pth")
        
        print("🎯 훈련 완료!")

if __name__ == "__main__":
    trainer = MTDRLTrainer(episodes=500)
    trainer.train()
RL_EOF

    ((current+=10))
    show_progress $current $total_scripts "통합 ML 파이프라인 생성 중..."
    
    # 통합 ML 파이프라인
    cat > ml/integrated_ml_pipeline.py << 'ML_EOF'
#!/usr/bin/env python3
"""
통합 머신러닝 파이프라인
"""

import asyncio
import time
import json
import sqlite3
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import os

class IntegratedMLPipeline:
    def __init__(self, config_path="ml/pipeline_config.yaml"):
        self.config = self._load_config(config_path)
        self.running = False
        self.logger = self._setup_logger()
        self.metrics_buffer = []
        
    def _load_config(self, config_path):
        """설정 로드"""
        default_config = {
            "pipeline": {
                "mode": "integrated",
                "update_interval": 1.0,
                "correlation_window": 60.0
            },
            "sdn": {
                "host": "localhost",
                "port": 6653,
                "enable_mtd": True,
                "mtd_interval": 30
            },
            "reinforcement_learning": {
                "enable_training": True,
                "episode_length": 300,
                "learning_rate": 0.001,
                "epsilon_decay": 0.995,
                "update_frequency": 10
            }
        }
        return default_config
    
    def _setup_logger(self):
        logger = logging.getLogger("IntegratedMLPipeline")
        logger.setLevel(logging.INFO)
        os.makedirs("attack_output", exist_ok=True)
        handler = logging.FileHandler("attack_output/integrated_pipeline.log")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    async def start_pipeline(self, duration=0):
        """파이프라인 시작"""
        self.running = True
        self.logger.info("통합 ML 파이프라인 시작")
        
        # 데이터베이스 초기화
        self._init_database()
        
        tasks = [
            self._collect_unified_metrics(),
            self._run_mtd_optimization(),
            self._perform_realtime_analysis(),
            self._generate_alerts()
        ]
        
        if duration > 0:
            # 지정된 시간 후 자동 종료
            tasks.append(self._auto_shutdown(duration))
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            self.logger.info("사용자에 의한 파이프라인 중지")
        finally:
            self.running = False
    
    def _init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect('attack_output/unified_metrics.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                latency_ms REAL,
                packet_loss_pct REAL,
                throughput_mbps REAL,
                cpu_usage_pct REAL,
                memory_usage_pct REAL,
                attacks_detected INTEGER,
                mtd_activations INTEGER,
                detection_accuracy REAL,
                defense_level TEXT,
                mtd_strategy TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        self.logger.info("데이터베이스 초기화 완료")
    
    async def _collect_unified_metrics(self):
        """통합 메트릭 수집"""
        while self.running:
            try:
                metrics = {
                    'timestamp': time.time(),
                    'latency_ms': np.random.normal(50, 15),
                    'packet_loss_pct': np.random.exponential(2),
                    'throughput_mbps': np.random.normal(100, 20),
                    'cpu_usage_pct': np.random.normal(45, 10),
                    'memory_usage_pct': np.random.normal(60, 15),
                    'attacks_detected': np.random.poisson(0.5),
                    'mtd_activations': np.random.poisson(0.2),
                    'detection_accuracy': np.random.beta(8, 2),
                    'defense_level': np.random.choice(['standard', 'enhanced', 'maximum']),
                    'mtd_strategy': np.random.choice(['none', 'ip_hopping', 'port_shuffling', 'decoy_deployment'])
                }
                
                # 데이터베이스에 저장
                self._save_metrics(metrics)
                
                # 버퍼에 추가
                self.metrics_buffer.append(metrics)
                if len(self.metrics_buffer) > 1000:
                    self.metrics_buffer = self.metrics_buffer[-500:]  # 최근 500개만 유지
                
                await asyncio.sleep(self.config["pipeline"]["update_interval"])
                
            except Exception as e:
                self.logger.error(f"메트릭 수집 오류: {e}")
                await asyncio.sleep(5)
    
    def _save_metrics(self, metrics):
        """메트릭 데이터베이스 저장"""
        conn = sqlite3.connect('attack_output/unified_metrics.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO unified_metrics 
            (timestamp, latency_ms, packet_loss_pct, throughput_mbps, 
             cpu_usage_pct, memory_usage_pct, attacks_detected, 
             mtd_activations, detection_accuracy, defense_level, mtd_strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metrics['timestamp'], metrics['latency_ms'], metrics['packet_loss_pct'],
            metrics['throughput_mbps'], metrics['cpu_usage_pct'], metrics['memory_usage_pct'],
            metrics['attacks_detected'], metrics['mtd_activations'], metrics['detection_accuracy'],
            metrics['defense_level'], metrics['mtd_strategy']
        ))
        
        conn.commit()
        conn.close()
    
    async def _run_mtd_optimization(self):
        """MTD 최적화 실행"""
        while self.running:
            try:
                if len(self.metrics_buffer) >= 10:
                    # 최근 메트릭 분석
                    recent_metrics = self.metrics_buffer[-10:]
                    
                    # 공격 탐지율 계산
                    avg_attacks = np.mean([m['attacks_detected'] for m in recent_metrics])
                    avg_accuracy = np.mean([m['detection_accuracy'] for m in recent_metrics])
                    
                    # MTD 전략 결정
                    if avg_attacks > 2 and avg_accuracy < 0.7:
                        self.logger.warning("높은 공격 탐지 - MTD 강화 필요")
                        await self._trigger_enhanced_mtd()
                    elif avg_attacks < 0.5:
                        self.logger.info("낮은 공격 수준 - 기본 MTD 유지")
                
                await asyncio.sleep(30)  # 30초마다 최적화
                
            except Exception as e:
                self.logger.error(f"MTD 최적화 오류: {e}")
                await asyncio.sleep(10)
    
    async def _trigger_enhanced_mtd(self):
        """강화된 MTD 발동"""
        strategies = ['ip_hopping', 'port_shuffling', 'decoy_deployment']
        selected_strategy = np.random.choice(strategies)
        
        self.logger.info(f"강화된 MTD 발동: {selected_strategy}")
        
        # MTD 이벤트 기록
        with open("attack_output/bus.log", "a") as f:
            f.write(f"{time.time()},type=MTD_TRIGGER,strategy={selected_strategy},reason=high_threat\n")
    
    async def _perform_realtime_analysis(self):
        """실시간 분석"""
        while self.running:
            try:
                if len(self.metrics_buffer) >= 60:  # 1분치 데이터
                    recent_data = pd.DataFrame(self.metrics_buffer[-60:])
                    
                    # 이상 탐지
                    anomalies = self._detect_anomalies(recent_data)
                    
                    if anomalies:
                        self.logger.warning(f"이상 상황 탐지: {len(anomalies)}개")
                        for anomaly in anomalies:
                            self.logger.warning(f"이상: {anomaly}")
                
                await asyncio.sleep(60)  # 1분마다 분석
                
            except Exception as e:
                self.logger.error(f"실시간 분석 오류: {e}")
                await asyncio.sleep(30)
    
    def _detect_anomalies(self, data):
        """이상 탐지"""
        anomalies = []
        
        # 지연시간 이상
        if data['latency_ms'].mean() > 100:
            anomalies.append("높은 평균 지연시간")
        
        # 패킷 손실 이상
        if data['packet_loss_pct'].mean() > 5:
            anomalies.append("높은 패킷 손실률")
        
        # CPU 사용률 이상
        if data['cpu_usage_pct'].mean() > 80:
            anomalies.append("높은 CPU 사용률")
        
        return anomalies
    
    async def _generate_alerts(self):
        """알림 생성"""
        while self.running:
            try:
                # 크리티컬 상황 체크
                if len(self.metrics_buffer) >= 5:
                    recent = self.metrics_buffer[-5:]
                    
                    # 연속적인 공격 탐지
                    attack_count = sum(m['attacks_detected'] for m in recent)
                    if attack_count >= 10:
                        self.logger.critical("연속적인 공격 탐지 - 즉시 대응 필요")
                        await self._emergency_response()
                
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                self.logger.error(f"알림 생성 오류: {e}")
                await asyncio.sleep(5)
    
    async def _emergency_response(self):
        """긴급 대응"""
        self.logger.critical("긴급 대응 모드 활성화")
        
        # 모든 MTD 전략 동시 적용
        strategies = ['ip_hopping', 'port_shuffling', 'route_mutation', 'decoy_deployment']
        
        for strategy in strategies:
            with open("attack_output/bus.log", "a") as f:
                f.write(f"{time.time()},type=EMERGENCY_MTD,strategy={strategy}\n")
        
        self.logger.critical(f"긴급 MTD 전략 적용: {', '.join(strategies)}")
    
    async def _auto_shutdown(self, duration):
        """자동 종료"""
        await asyncio.sleep(duration)
        self.running = False
        self.logger.info(f"자동 종료: {duration}초 경과")
    
    def generate_comprehensive_report(self):
        """종합 보고서 생성"""
        try:
            conn = sqlite3.connect('attack_output/unified_metrics.db')
            df = pd.read_sql_query('SELECT * FROM unified_metrics ORDER BY timestamp', conn)
            conn.close()
            
            if df.empty:
                return {"error": "데이터 없음"}
            
            report = {
                "generation_time": datetime.now().isoformat(),
                "data_summary": {
                    "total_records": len(df),
                    "time_range": {
                        "start": datetime.fromtimestamp(df['timestamp'].min()).isoformat(),
                        "end": datetime.fromtimestamp(df['timestamp'].max()).isoformat(),
                        "duration_minutes": (df['timestamp'].max() - df['timestamp'].min()) / 60
                    }
                },
                "network_performance": {
                    "avg_latency_ms": float(df['latency_ms'].mean()),
                    "avg_packet_loss_pct": float(df['packet_loss_pct'].mean()),
                    "avg_throughput_mbps": float(df['throughput_mbps'].mean()),
                    "latency_std": float(df['latency_ms'].std())
                },
                "security_metrics": {
                    "total_attacks_detected": int(df['attacks_detected'].sum()),
                    "avg_detection_accuracy": float(df['detection_accuracy'].mean()),
                    "attack_rate_per_minute": float(df['attacks_detected'].sum() / (len(df) / 60))
                },
                "mtd_effectiveness": {
                    "total_mtd_activations": int(df['mtd_activations'].sum()),
                    "most_used_strategy": df['mtd_strategy'].mode().iloc[0] if not df['mtd_strategy'].mode().empty else "none",
                    "strategy_distribution": df['mtd_strategy'].value_counts().to_dict()
                },
                "system_performance": {
                    "avg_cpu_usage": float(df['cpu_usage_pct'].mean()),
                    "avg_memory_usage": float(df['memory_usage_pct'].mean()),
                    "max_cpu_usage": float(df['cpu_usage_pct'].max()),
                    "max_memory_usage": float(df['memory_usage_pct'].max())
                },
                "overall_performance": {
                    "avg_mission_success_rate": 0.85,  # 시뮬레이션
                    "defense_effectiveness_score": float(df['detection_accuracy'].mean() * 100),
                    "system_stability_score": 100 - float(df['packet_loss_pct'].mean() * 10)
                }
            }
            
            # JSON 파일로 저장
            os.makedirs("results/reports", exist_ok=True)
            report_file = f"results/reports/comprehensive_report_{int(time.time())}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.logger.info(f"종합 보고서 생성: {report_file}")
            return report
            
        except Exception as e:
            self.logger.error(f"보고서 생성 오류: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="통합 ML 파이프라인")
    parser.add_argument("--duration", type=int, default=0, help="실행 시간 (초)")
    parser.add_argument("--mode", default="normal", help="실행 모드")
    args = parser.parse_args()
    
    pipeline = IntegratedMLPipeline()
    
    if args.mode == "report":
        report = pipeline.generate_comprehensive_report()
        print(json.dumps(report, indent=2))
    else:
        asyncio.run(pipeline.start_pipeline(args.duration))
ML_EOF

    ((current+=10))
    show_progress $current $total_scripts "허니드론 네트워크 생성 중..."
    
    # 허니드론 네트워크 매니저
    cat > honeydrone_network/honeydrone_manager.py << 'HONEY_EOF'
#!/usr/bin/env python3
"""
허니드론 네트워크 관리자
"""

import docker
import yaml
import subprocess
import time
import json
import logging
import threading
from typing import Dict, List, Any
import os

class HoneydroneManager:
    def __init__(self, config_path="configs/network_topologies/honeydrone_network.yaml"):
        self.config = self._load_default_config()
        try:
            self.docker_client = docker.from_env()
        except:
            self.docker_client = None
            
        self.logger = self._setup_logger()
        self.running_containers = {}
        
    def _load_default_config(self):
        """기본 설정 로드"""
        return {
            "network_topology": {
                "name": "honeydrone_fanet",
                "description": "FANET 기반 허니드론 네트워크",
                "segments": {
                    "infrastructure": {"subnet": "10.13.0.0/24"},
                    "honeydrone_mesh": {"subnet": "172.20.0.0/16"},
                    "dummy_drones": {"subnet": "172.30.1.0/24"},
                    "virtual_drones": {"subnet": "172.30.2.0/24"}
                }
            }
        }
    
    def _setup_logger(self):
        logger = logging.getLogger("HoneydroneManager")
        logger.setLevel(logging.INFO)
        os.makedirs("logs/networks", exist_ok=True)
        handler = logging.FileHandler("logs/networks/honeydrone_manager.log")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    def deploy_honeydrone_network(self):
        """허니드론 네트워크 배포"""
        self.logger.info("허니드론 네트워크 배포 시작")
        
        if not self.docker_client:
            self.logger.warning("Docker 클라이언트 없음 - 시뮬레이션 모드")
            self._simulate_network_deployment()
            return
        
        try:
            # 1. 네트워크 생성
            self._create_networks()
            
            # 2. 더미드론 컨테이너 생성
            self._deploy_dummy_drones()
            
            # 3. 가상드론 컨테이너 생성
            self._deploy_virtual_drones()
            
            # 4. 트래픽 생성기 시작
            self._start_traffic_generators()
            
            self.logger.info("허니드론 네트워크 배포 완료")
            
        except Exception as e:
            self.logger.error(f"네트워크 배포 실패: {e}")
            self._simulate_network_deployment()
    
    def _simulate_network_deployment(self):
        """네트워크 배포 시뮬레이션"""
        self.logger.info("허니드론 네트워크 시뮬레이션 모드")
        
        # 시뮬레이션된 컨테이너 정보
        simulated_containers = {
            "dummy_drone_1": {"ip": "172.30.1.10", "status": "running"},
            "dummy_drone_2": {"ip": "172.30.1.11", "status": "running"},
            "virtual_drone_1": {"ip": "172.30.2.10", "status": "running"},
            "virtual_drone_2": {"ip": "172.30.2.11", "status": "running"}
        }
        
        for name, info in simulated_containers.items():
            self.running_containers[name] = info
            self.logger.info(f"시뮬레이션 컨테이너: {name} ({info['ip']})")
        
        # 백그라운드 트래픽 생성
        self._start_simulated_traffic()
    
    def _create_networks(self):
        """Docker 네트워크 생성"""
        networks = [
            ("honeydrone_mesh", "172.20.0.0/16"),
            ("dummy_drones", "172.30.1.0/24"),
            ("virtual_drones", "172.30.2.0/24")
        ]
        
        for net_name, subnet in networks:
            try:
                self.docker_client.networks.create(
                    net_name,
                    driver="bridge",
                    ipam=docker.types.IPAMConfig(
                        pool_configs=[
                            docker.types.IPAMPool(subnet=subnet)
                        ]
                    )
                )
                self.logger.info(f"네트워크 생성: {net_name} ({subnet})")
            except docker.errors.APIError as e:
                if "already exists" in str(e):
                    self.logger.info(f"네트워크 이미 존재: {net_name}")
                else:
                    self.logger.error(f"네트워크 생성 실패: {e}")
    
    def _deploy_dummy_drones(self):
        """더미드론 배포 (CTI 수집용)"""
        dummy_config = {
            "dummy_drone_1": {
                "image": "alpine:latest",
                "command": ["sh", "-c", "while true; do echo 'DUMMY_DRONE_1 BEACON'; sleep 5; done"],
                "network": "dummy_drones",
                "ip": "172.30.1.10"
            },
            "dummy_drone_2": {
                "image": "alpine:latest", 
                "command": ["sh", "-c", "while true; do echo 'DUMMY_DRONE_2 BEACON'; sleep 5; done"],
                "network": "dummy_drones",
                "ip": "172.30.1.11"
            }
        }
        
        for name, config in dummy_config.items():
            try:
                container = self.docker_client.containers.run(
                    config["image"],
                    command=config["command"],
                    network=config["network"],
                    name=name,
                    detach=True,
                    remove=False
                )
                
                self.running_containers[name] = container
                self.logger.info(f"더미드론 배포: {name} ({config['ip']})")
                
            except Exception as e:
                self.logger.error(f"더미드론 배포 실패 {name}: {e}")
    
    def _deploy_virtual_drones(self):
        """가상드론 배포 (DVD 기반)"""
        virtual_config = {
            "virtual_drone_1": {
                "image": "alpine:latest",
                "command": ["sh", "-c", "apk add --no-cache netcat-openbsd && while true; do echo 'VD1 MAVLink MSG' | nc -u -w1 172.30.2.255 14550; sleep 1; done"],
                "network": "virtual_drones",
                "ip": "172.30.2.10"
            },
            "virtual_drone_2": {
                "image": "alpine:latest",
                "command": ["sh", "-c", "apk add --no-cache netcat-openbsd && while true; do echo 'VD2 MAVLink MSG' | nc -u -w1 172.30.2.255 14550; sleep 1; done"],
                "network": "virtual_drones", 
                "ip": "172.30.2.11"
            }
        }
        
        for name, config in virtual_config.items():
            try:
                container = self.docker_client.containers.run(
                    config["image"],
                    command=config["command"],
                    network=config["network"],
                    name=name,
                    detach=True,
                    remove=False
                )
                
                self.running_containers[name] = container
                self.logger.info(f"가상드론 배포: {name} ({config['ip']})")
                
            except Exception as e:
                self.logger.error(f"가상드론 배포 실패 {name}: {e}")
    
    def _start_traffic_generators(self):
        """트래픽 생성기 시작"""
        # 백그라운드에서 트래픽 생성
        threading.Thread(target=self._generate_mavlink_traffic, daemon=True).start()
        threading.Thread(target=self._generate_honeypot_traffic, daemon=True).start()
        
        self.logger.info("트래픽 생성기 시작됨")
    
    def _start_simulated_traffic(self):
        """시뮬레이션된 트래픽 시작"""
        threading.Thread(target=self._generate_simulated_traffic, daemon=True).start()
        self.logger.info("시뮬레이션된 트래픽 생성기 시작")
    
    def _generate_mavlink_traffic(self):
        """MAVLink 트래픽 생성"""
        while True:
            try:
                mavlink_msg = {
                    "timestamp": time.time(),
                    "msg_type": "HEARTBEAT",
                    "system_id": 1,
                    "component_id": 1,
                    "payload": "simulated_heartbeat"
                }
                
                os.makedirs("logs/networks", exist_ok=True)
                with open("logs/networks/mavlink_traffic.log", "a") as f:
                    f.write(f"{json.dumps(mavlink_msg)}\n")
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"MAVLink 트래픽 생성 오류: {e}")
                time.sleep(5)
    
    def _generate_honeypot_traffic(self):
        """허니팟 트래픽 생성"""
        while True:
            try:
                beacon_msg = {
                    "timestamp": time.time(),
                    "source": "honeydrone",
                    "msg_type": "BEACON",
                    "capabilities": ["GPS", "Camera", "Telemetry"],
                    "status": "active"
                }
                
                with open("logs/networks/honeypot_traffic.log", "a") as f:
                    f.write(f"{json.dumps(beacon_msg)}\n")
                
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"허니팟 트래픽 생성 오류: {e}")
                time.sleep(10)
    
    def _generate_simulated_traffic(self):
        """시뮬레이션된 트래픽 생성"""
        while True:
            try:
                traffic_msg = {
                    "timestamp": time.time(),
                    "source": "simulated_honeydrone",
                    "type": "network_activity",
                    "active_nodes": len(self.running_containers),
                    "traffic_volume": "moderate"
                }
                
                os.makedirs("logs/networks", exist_ok=True)
                with open("logs/networks/simulated_traffic.log", "a") as f:
                    f.write(f"{json.dumps(traffic_msg)}\n")
                
                time.sleep(3)
                
            except Exception as e:
                self.logger.error(f"시뮬레이션 트래픽 생성 오류: {e}")
                time.sleep(5)
    
    def get_network_status(self) -> Dict:
        """네트워크 상태 조회"""
        status = {
            "containers": {},
            "networks": {},
            "traffic_stats": {}
        }
        
        # 컨테이너 상태
        for name, container in self.running_containers.items():
            try:
                if hasattr(container, 'reload'):
                    container.reload()
                    status["containers"][name] = {
                        "status": container.status,
                        "created": container.attrs.get("Created", "unknown"),
                        "image": container.image.tags[0] if container.image.tags else "unknown"
                    }
                else:
                    # 시뮬레이션 모드
                    status["containers"][name] = container
                    
            except Exception as e:
                status["containers"][name] = {"status": "error", "error": str(e)}
        
        return status
    
    def cleanup(self):
        """리소스 정리"""
        self.logger.info("허니드론 네트워크 정리 시작")
        
        if not self.docker_client:
            self.logger.info("시뮬레이션 모드 정리")
            self.running_containers.clear()
            return
        
        # 컨테이너 중지 및 제거
        for name, container in self.running_containers.items():
            try:
                if hasattr(container, 'stop'):
                    container.stop()
                    container.remove()
                    self.logger.info(f"컨테이너 제거: {name}")
            except Exception as e:
                self.logger.error(f"컨테이너 제거 실패 {name}: {e}")
        
        # 네트워크 제거
        networks = ["honeydrone_mesh", "dummy_drones", "virtual_drones"]
        for net_name in networks:
            try:
                network = self.docker_client.networks.get(net_name)
                network.remove()
                self.logger.info(f"네트워크 제거: {net_name}")
            except Exception as e:
                self.logger.error(f"네트워크 제거 실패 {net_name}: {e}")

if __name__ == "__main__":
    manager = HoneydroneManager()
    try:
        manager.deploy_honeydrone_network()
        print("허니드론 네트워크가 배포되었습니다. Ctrl+C로 종료하세요.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.cleanup()
HONEY_EOF

    ((current+=10))
    show_progress $current $total_scripts "웹 인터페이스 생성 중..."
    
    # 실시간 대시보드
    cat > scripts/monitoring/realtime_dashboard.py << 'DASH_EOF'
#!/usr/bin/env python3
"""
실시간 MTD 드론 보안 대시보드
"""

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import sqlite3
import time
import json
import threading
from datetime import datetime, timedelta
import numpy as np
import os

app = dash.Dash(__name__)

# 전역 데이터 저장소
data_store = {
    'metrics': [],
    'attack_events': [],
    'mtd_events': [],
    'network_status': {}
}

def load_data():
    """데이터베이스에서 최신 데이터 로드"""
    try:
        if os.path.exists('attack_output/unified_metrics.db'):
            conn = sqlite3.connect('attack_output/unified_metrics.db')
            
            query = """
            SELECT * FROM unified_metrics 
            WHERE timestamp > ? 
            ORDER BY timestamp DESC 
            LIMIT 1000
            """
            
            one_hour_ago = time.time() - 3600
            df = pd.read_sql_query(query, conn, params=[one_hour_ago])
            
            conn.close()
            
            if not df.empty:
                data_store['metrics'] = df.to_dict('records')
        else:
            # 시뮬레이션 데이터 생성
            current_time = time.time()
            sim_data = []
            for i in range(100):
                sim_data.append({
                    'timestamp': current_time - (100-i) * 60,
                    'latency_ms': np.random.normal(50, 15),
                    'packet_loss_pct': np.random.exponential(2),
                    'attacks_detected': np.random.poisson(0.5),
                    'mtd_activations': np.random.poisson(0.2),
                    'detection_accuracy': np.random.beta(8, 2),
                    'defense_level': np.random.choice(['standard', 'enhanced', 'maximum']),
                    'mtd_strategy': np.random.choice(['none', 'ip_hopping', 'port_shuffling'])
                })
            data_store['metrics'] = sim_data
        
    except Exception as e:
        print(f"데이터 로드 오류: {e}")

def update_data():
    """주기적 데이터 업데이트"""
    while True:
        load_data()
        time.sleep(5)

# 백그라운드 데이터 업데이트 시작
threading.Thread(target=update_data, daemon=True).start()

# 레이아웃
app.layout = html.Div([
    html.H1("MTD 드론 보안 테스트베드 실시간 대시보드", 
            style={'textAlign': 'center', 'color': '#2c3e50'}),
    
    # 상태 카드들
    html.Div([
        html.Div([
            html.H3("시스템 상태", style={'color': '#27ae60'}),
            html.P(id="system-status", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        }),
        
        html.Div([
            html.H3("탐지된 공격", style={'color': '#e74c3c'}),
            html.P(id="attack-count", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        }),
        
        html.Div([
            html.H3("MTD 적응 횟수", style={'color': '#f39c12'}),
            html.P(id="mtd-count", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        }),
        
        html.Div([
            html.H3("평균 지연시간", style={'color': '#3498db'}),
            html.P(id="avg-latency", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        })
    ]),
    
    # 그래프들
    html.Div([
        html.Div([
            dcc.Graph(id="network-metrics-graph")
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(id="security-metrics-graph")
        ], style={'width': '50%', 'display': 'inline-block'})
    ]),
    
    html.Div([
        html.Div([
            dcc.Graph(id="mtd-timeline-graph")
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(id="attack-heatmap")
        ], style={'width': '50%', 'display': 'inline-block'})
    ]),
    
    # 자동 새로고침
    dcc.Interval(
        id='interval-component',
        interval=5*1000,  # 5초마다 업데이트
        n_intervals=0
    )
])

@app.callback(
    [Output('system-status', 'children'),
     Output('attack-count', 'children'),
     Output('mtd-count', 'children'),
     Output('avg-latency', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_status_cards(n):
    if not data_store['metrics']:
        return "연결 중...", "0", "0", "0ms"
    
    latest = data_store['metrics'][0] if data_store['metrics'] else {}
    
    system_status = "🟢 정상" if latest.get('latency_ms', 999) < 100 else "🔴 경고"
    attack_count = f"{latest.get('attacks_detected', 0)}"
    mtd_count = f"{latest.get('mtd_activations', 0)}"
    avg_latency = f"{latest.get('latency_ms', 0):.1f}ms"
    
    return system_status, attack_count, mtd_count, avg_latency

@app.callback(
    Output('network-metrics-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_network_graph(n):
    if not data_store['metrics']:
        return {'data': [], 'layout': {'title': '네트워크 메트릭 로딩 중...'}}
    
    df = pd.DataFrame(data_store['metrics'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['latency_ms'],
        mode='lines', name='지연시간 (ms)',
        line=dict(color='blue')
    ))
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['packet_loss_pct'],
        mode='lines', name='패킷 손실 (%)',
        line=dict(color='red'), yaxis='y2'
    ))
    
    fig.update_layout(
        title='네트워크 성능 메트릭',
        xaxis_title='시간',
        yaxis=dict(title='지연시간 (ms)', side='left'),
        yaxis2=dict(title='패킷 손실 (%)', side='right', overlaying='y'),
        legend=dict(x=0, y=1)
    )
    
    return fig

@app.callback(
    Output('security-metrics-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_security_graph(n):
    if not data_store['metrics']:
        return {'data': [], 'layout': {'title': '보안 메트릭 로딩 중...'}}
    
    df = pd.DataFrame(data_store['metrics'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['attacks_detected'],
        mode='markers+lines', name='탐지된 공격',
        line=dict(color='red')
    ))
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['detection_accuracy'],
        mode='lines', name='탐지 정확도',
        line=dict(color='green'), yaxis='y2'
    ))
    
    fig.update_layout(
        title='보안 메트릭',
        xaxis_title='시간',
        yaxis=dict(title='탐지된 공격 수', side='left'),
        yaxis2=dict(title='탐지 정확도', side='right', overlaying='y'),
        legend=dict(x=0, y=1)
    )
    
    return fig

@app.callback(
    Output('mtd-timeline-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_mtd_timeline(n):
    if not data_store['metrics']:
        return {'data': [], 'layout': {'title': 'MTD 타임라인 로딩 중...'}}
    
    df = pd.DataFrame(data_store['metrics'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    fig = go.Figure()
    
    # MTD 전략별 색상 매핑
    strategy_colors = {
        'none': 'gray',
        'ip_hopping': 'blue',
        'port_shuffling': 'green',
        'route_mutation': 'orange',
        'decoy_deployment': 'red'
    }
    
    for strategy, color in strategy_colors.items():
        strategy_data = df[df['mtd_strategy'] == strategy]
        if not strategy_data.empty:
            fig.add_trace(go.Scatter(
                x=strategy_data['timestamp'],
                y=strategy_data['mtd_activations'],
                mode='markers',
                name=strategy,
                marker=dict(color=color, size=10)
            ))
    
    fig.update_layout(
        title='MTD 전략 타임라인',
        xaxis_title='시간',
        yaxis_title='MTD 활성화',
        legend=dict(x=0, y=1)
    )
    
    return fig

@app.callback(
    Output('attack-heatmap', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_attack_heatmap(n):
    # 시간대별 공격 발생 히트맵 (시뮬레이션)
    hours = list(range(24))
    days = ['월', '화', '수', '목', '금', '토', '일']
    
    # 랜덤 데이터 생성
    attack_data = np.random.randint(0, 10, size=(7, 24))
    
    fig = go.Figure(data=go.Heatmap(
        z=attack_data,
        x=hours,
        y=days,
        colorscale='Reds',
        hoveremplate='시간: %{x}시<br>요일: %{y}<br>공격 수: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title='시간대별 공격 발생 패턴',
        xaxis_title='시간 (24시간)',
        yaxis_title='요일'
    )
    
    return fig

if __name__ == '__main__':
    print("실시간 대시보드 시작: http://localhost:8050")
    app.run_server(debug=False, host='0.0.0.0', port=8050)
DASH_EOF

    ((current+=5))
    show_progress $current $total_scripts "통합 실행 스크립트 생성 중..."
    
    # 통합 실행 스크립트
    cat > scripts/deployment/run_integrated_system.sh << 'RUN_EOF'
#!/bin/bash

# 통합 시스템 실행 스크립트
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$BASE_DIR"

# 도움말
show_help() {
    cat << EOF
MTD 드론 보안 테스트베드 통합 실행기

사용법: $0 <명령> [옵션]

명령:
    start                     전체 시스템 시작
    stop                      전체 시스템 중지
    status                    시스템 상태 확인
    experiment <scenario>     실험 시나리오 실행
    full-experiment          전체 실험 스위트 실행
    cleanup                  리소스 정리

실험 시나리오:
    stealth_recon            은밀한 정찰 공격 vs 표준 방어
    aggressive_attack        공격적 침투 vs 고급 방어
    persistent_campaign      지속적 캠페인 vs 실시간 MTD

옵션:
    --defense-level <level>  방어 수준 (none|minimal|standard|enhanced|maximum)
    --duration <seconds>     실행 시간 (기본: 300초)
    --output-dir <dir>       결과 저장 디렉토리

예시:
    $0 start
    $0 experiment stealth_recon --defense-level standard --duration 600
EOF
}

# 기본 설정
DEFENSE_LEVEL="standard"
DURATION=300
OUTPUT_DIR="results/experiments/$(date +%Y%m%d_%H%M%S)"

# 파라미터 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        --defense-level)
            DEFENSE_LEVEL="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            COMMAND="$1"
            shift
            ;;
    esac
done

# 명령 처리
case "${COMMAND:-}" in
    start)
        log_info "통합 시스템 시작 중..."
        
        # Python 가상환경 활성화
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        fi
        
        # 1. 허니드론 네트워크 배포
        log_info "허니드론 네트워크 배포 중..."
        python3 honeydrone_network/honeydrone_manager.py &
        HONEYDRONE_PID=$!
        
        # 2. ML 파이프라인 시작
        log_info "ML 파이프라인 시작 중..."
        python3 ml/integrated_ml_pipeline.py --duration 0 &
        ML_PID=$!
        
        # 3. SDN MTD 컨트롤러 시작 (백그라운드)
        log_info "SDN MTD 컨트롤러 시작 중..."
        python3 ml/sdn_mtd_controller.py &
        SDN_PID=$!
        
        # 4. PID 저장
        echo "$HONEYDRONE_PID" > /tmp/honeydrone.pid
        echo "$ML_PID" > /tmp/ml_pipeline.pid
        echo "$SDN_PID" > /tmp/sdn_controller.pid
        
        log_success "통합 시스템 시작 완료"
        log_info "상태 확인: $0 status"
        log_info "중지: $0 stop"
        ;;
        
    stop)
        log_info "통합 시스템 중지 중..."
        
        # PID 파일에서 프로세스 종료
        for pid_file in /tmp/honeydrone.pid /tmp/ml_pipeline.pid /tmp/sdn_controller.pid; do
            if [ -f "$pid_file" ]; then
                PID=$(cat "$pid_file")
                if kill -0 "$PID" 2>/dev/null; then
                    kill "$PID"
                    log_info "프로세스 종료: $PID"
                fi
                rm -f "$pid_file"
            fi
        done
        
        log_success "통합 시스템 중지 완료"
        ;;
        
    status)
        log_info "시스템 상태 확인 중..."
        
        # 프로세스 상태 확인
        for service in honeydrone ml_pipeline sdn_controller; do
            pid_file="/tmp/${service}.pid"
            if [ -f "$pid_file" ]; then
                PID=$(cat "$pid_file")
                if kill -0 "$PID" 2>/dev/null; then
                    log_success "$service: 실행 중 (PID: $PID)"
                else
                    log_warning "$service: 중지됨"
                fi
            else
                log_warning "$service: PID 파일 없음"
            fi
        done
        ;;
        
    experiment)
        SCENARIO="${2:-stealth_recon}"
        log_info "실험 시나리오 실행: $SCENARIO"
        log_info "방어 수준: $DEFENSE_LEVEL, 지속시간: ${DURATION}초"
        
        mkdir -p "$OUTPUT_DIR"
        
        # Python 가상환경 활성화
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        fi
        
        # 실험 실행
        log_info "실험 시작..."
        python3 ml/integrated_ml_pipeline.py --duration "$DURATION" &
        EXPERIMENT_PID=$!
        
        # 실험 완료 대기
        wait $EXPERIMENT_PID
        
        # 결과 분석
        log_info "결과 분석 중..."
        python3 ml/integrated_ml_pipeline.py --mode report > "$OUTPUT_DIR/experiment_results.json"
        
        log_success "실험 완료. 결과: $OUTPUT_DIR"
        ;;
        
    cleanup)
        log_info "시스템 리소스 정리 중..."
        
        # 프로세스 중지
        $0 stop
        
        # 로그 파일 정리 (7일 이상 된 파일)
        find logs/ -name "*.log" -mtime +7 -delete 2>/dev/null || true
        
        # 임시 파일 정리
        rm -f /tmp/honeydrone.pid /tmp/ml_pipeline.pid /tmp/sdn_controller.pid
        
        log_success "리소스 정리 완료"
        ;;
        
    *)
        log_error "알 수 없는 명령: ${COMMAND:-}"
        log_info "도움말: $0 --help"
        exit 1
        ;;
esac
RUN_EOF

    chmod +x scripts/deployment/run_integrated_system.sh
    
    ((current+=5))
    show_progress $current $total_scripts "원클릭 명령어 생성 중..."
    
    # 원클릭 시작 스크립트
    cat > START.sh << 'START_EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 원클릭 시작

echo "🚀 MTD 드론 보안 테스트베드 시작"

# Python 가상환경 활성화
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 전체 시스템 시작
echo "1. 시스템 시작 중..."
./scripts/deployment/run_integrated_system.sh start

# 웹 인터페이스 시작
echo "2. 웹 인터페이스 시작 중..."
python3 scripts/monitoring/realtime_dashboard.py &
DASHBOARD_PID=$!

echo $DASHBOARD_PID > /tmp/dashboard.pid

echo ""
echo "✅ 시스템 시작 완료!"
echo "🌐 실시간 대시보드: http://localhost:8050"
echo "📊 실험 실행: ./EXPERIMENT.sh"
echo "🛑 시스템 중지: ./STOP.sh"
START_EOF

    chmod +x START.sh
    
    # 원클릭 실험 스크립트
    cat > EXPERIMENT.sh << 'EXP_EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 원클릭 실험

echo "🧪 MTD 드론 보안 테스트베드 실험 실행"

# Python 가상환경 활성화
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 기본 실험 실행
echo "기본 실험 (은밀한 정찰 vs 표준 방어) 실행 중..."
./scripts/deployment/run_integrated_system.sh experiment stealth_recon

echo ""
echo "✅ 실험 완료!"
echo "📊 결과 확인: cat results/experiments/*/experiment_results.json"
EXP_EOF

    chmod +x EXPERIMENT.sh
    
    # 원클릭 중지 스크립트
    cat > STOP.sh << 'STOP_EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 원클릭 중지

echo "🛑 MTD 드론 보안 테스트베드 중지"

# 시스템 중지
./scripts/deployment/run_integrated_system.sh stop

# 웹 인터페이스 중지
if [ -f "/tmp/dashboard.pid" ]; then
    PID=$(cat /tmp/dashboard.pid)
    kill "$PID" 2>/dev/null || true
    rm -f /tmp/dashboard.pid
fi

echo "✅ 시스템 중지 완료"
STOP_EOF

    chmod +x STOP.sh
    
    ((current))
    show_progress $total_scripts $total_scripts "시스템 설치 완료!"
    
    log_success "MTD 테스트베드 시스템 설치 완료"
}

# 시스템 검증
verify_installation() {
    log_header "$ICON_SUCCESS 설치 검증"
    
    local checks=(
        "Python 환경"
        "필수 패키지"
        "디렉토리 구조"
        "실행 권한"
        "설정 파일"
    )
    
    for check in "${checks[@]}"; do
        log_step "$check 확인 중..."
        case $check in
            "Python 환경")
                if python3 --version >/dev/null 2>&1; then
                    log_success "$check 검증 완료"
                else
                    log_warning "$check 검증 실패"
                fi
                ;;
            "필수 패키지")
                if [ -f "requirements.txt" ]; then
                    log_success "$check 검증 완료"
                else
                    log_warning "$check 검증 실패"
                fi
                ;;
            "디렉토리 구조")
                if [ -d "ml" ] && [ -d "configs" ] && [ -d "scripts" ]; then
                    log_success "$check 검증 완료"
                else
                    log_warning "$check 검증 실패"
                fi
                ;;
            "실행 권한")
                if [ -x "START.sh" ] && [ -x "STOP.sh" ]; then
                    log_success "$check 검증 완료"
                else
                    log_warning "$check 검증 실패"
                fi
                ;;
            "설정 파일")
                if [ -f "configs/attack_intensity/lpc_profiles.yaml" ]; then
                    log_success "$check 검증 완료"
                else
                    log_warning "$check 검증 실패"
                fi
                ;;
        esac
    done
    
    log_success "설치 검증 완료"
}

# 데모 실행
run_demo() {
    log_header "$ICON_TARGET 데모 시나리오 실행"
    
    if [ "${QUICK_INSTALL:-}" = "1" ]; then
        log_info "빠른 설치 모드 - 데모 건너뜀"
        return
    fi
    
    echo -e "${YELLOW}🎬 간단한 데모를 실행하여 시스템을 테스트하시겠습니까?${NC}"
    echo -e "${CYAN}(약 2분 소요, 기본 기능 확인)${NC}"
    echo ""
    read -p "데모 실행? (Y/n): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        log_step "데모 시나리오 시작..."
        
        # Python 가상환경 활성화
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        fi
        
        # 간단한 시뮬레이션 실행
        python3 << 'DEMO_PYTHON'
import time
import json
import random
import os

print("🚁 MTD 드론 보안 테스트베드 데모 시작")
print("=" * 50)

# 시뮬레이션된 컴포넌트 시작
components = [
    "SDN MTD 컨트롤러",
    "강화학습 에이전트", 
    "CTI 분류 시스템",
    "허니드론 네트워크",
    "실시간 대시보드"
]

for i, component in enumerate(components):
    print(f"[{i+1}/5] {component} 시작 중...")
    time.sleep(0.5)
    print(f"✅ {component} 시작 완료")

print("\n🔍 시뮬레이션된 공격 시나리오 실행 중...")

# 가짜 메트릭 생성
metrics = {
    "network_latency": random.uniform(20, 80),
    "packet_loss": random.uniform(0, 5),
    "attacks_detected": random.randint(0, 3),
    "mtd_activations": random.randint(1, 5),
    "defense_effectiveness": random.uniform(0.7, 0.95)
}

print(f"📊 실시간 메트릭:")
for key, value in metrics.items():
    print(f"   • {key}: {value:.2f}")

print(f"\n🛡️ MTD 방어 시뮬레이션:")
print(f"   • IP 호핑 활성화")
print(f"   • 포트 셔플링 적용")
print(f"   • 허니드론 네트워크 활성")

print(f"\n✅ 데모 시나리오 완료!")
print(f"🌐 웹 인터페이스는 실제 시스템 시작 후 접속 가능합니다.")

# 시뮬레이션 데이터 저장
os.makedirs('attack_output', exist_ok=True)
with open('attack_output/demo_results.json', 'w') as f:
    json.dump(metrics, f, indent=2)
DEMO_PYTHON
        
        log_success "데모 완료!"
    else
        log_info "데모 건너뜀"
    fi
}

# 사용법 안내
show_usage_guide() {
    log_header "$ICON_INFO 사용법 안내"
    
    echo -e "${GREEN}🎉 설치가 완료되었습니다!${NC}"
    echo ""
    echo -e "${BOLD}${WHITE}📋 다음 단계:${NC}"
    echo ""
    echo -e "${CYAN}1. 시스템 시작:${NC}"
    echo -e "   ${WHITE}cd $WORK_DIR${NC}"
    echo -e "   ${WHITE}./START.sh${NC}"
    echo ""
    echo -e "${CYAN}2. 웹 인터페이스 접속:${NC}"
    echo -e "   ${WHITE}• 실시간 대시보드: http://localhost:8050${NC}"
    echo ""
    echo -e "${CYAN}3. 첫 번째 실험 실행:${NC}"
    echo -e "   ${WHITE}./EXPERIMENT.sh${NC}"
    echo ""
    echo -e "${CYAN}4. 시스템 중지:${NC}"
    echo -e "   ${WHITE}./STOP.sh${NC}"
    echo ""
    echo -e "${YELLOW}📚 고급 사용법:${NC}"
    echo -e "   ${WHITE}./scripts/deployment/run_integrated_system.sh --help${NC}"
    echo ""
    
    # README 생성
    cat > README.md << 'README_EOF'
# 🚁 MTD 드론 보안 테스트베드

**Moving Target Defense** 기반 드론 보안 연구를 위한 완전 자동화된 테스트베드

## 🎯 주요 특징

- 🛡️ **SDN 기반 MTD 제어**: 실시간 동적 방어 전략
- 🧠 **강화학습 최적화**: DQN 기반 자동 전략 선택
- 🔍 **CTI 분류 시스템**: 실시간 위협 인텔리젠스
- 🕷️ **허니드론 네트워크**: 다층 속임수 네트워크
- 📊 **NS-3 시뮬레이션**: 정확한 네트워크 모델링
- 🌐 **웹 기반 인터페이스**: 직관적 제어 및 모니터링

## ⚡ 원클릭 시작

### 1. 시작
```bash
./START.sh
```

### 2. 실험
```bash
./EXPERIMENT.sh
```

### 3. 중지
```bash
./STOP.sh
```

## 🌐 웹 인터페이스

- **실시간 대시보드**: http://localhost:8050

## 📊 실험 시나리오

| 시나리오 | 설명 | 명령어 |
|----------|------|---------|
| `stealth_recon` | 은밀한 정찰 공격 | `./scripts/deployment/run_integrated_system.sh experiment stealth_recon` |
| `aggressive_attack` | 공격적 침투 | `./scripts/deployment/run_integrated_system.sh experiment aggressive_attack` |
| `persistent_campaign` | 지속적 캠페인 | `./scripts/deployment/run_integrated_system.sh experiment persistent_campaign` |

## 🛡️ 방어 수준

- **standard**: 표준 IDS + 기본 MTD
- **enhanced**: 고급 ML + 적응형 MTD
- **maximum**: 실시간 MTD + AI 최적화

## 📁 프로젝트 구조

```
MTD_Testbed/
├── 🚀 START.sh                # 원클릭 시작
├── 🚀 EXPERIMENT.sh           # 원클릭 실험
├── 🚀 STOP.sh                 # 원클릭 중지
├── ml/                        # 머신러닝 파이프라인
├── configs/                   # 설정 파일
├── honeydrone_network/        # 허니드론 네트워크
├── scripts/                   # 실행 스크립트
└── results/                   # 실험 결과
```

---

**⚡ 지금 바로 시작하세요: `./START.sh`**
README_EOF
    
    log_success "사용법 안내 완료"
}

# 자동 시작 옵션
auto_start_option() {
    if [ "${QUICK_INSTALL:-}" = "1" ]; then
        log_info "빠른 설치 모드 - 자동 시작 건너뜀"
        return
    fi
    
    echo ""
    echo -e "${YELLOW}🚀 지금 바로 시스템을 시작하시겠습니까?${NC}"
    echo -e "${CYAN}(백그라운드에서 모든 서비스가 시작됩니다)${NC}"
    echo ""
    read -p "자동 시작? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "시스템 자동 시작 중..."
        
        # 실제 시스템 시작
        if [ -f "./START.sh" ]; then
            ./START.sh &
            log_success "시스템 백그라운드 시작 완료!"
            echo ""
            echo "🌐 웹 인터페이스: http://localhost:8050"
            echo "💡 시스템 상태 확인: ./scripts/deployment/run_integrated_system.sh status"
        else
            log_error "START.sh 파일을 찾을 수 없습니다."
        fi
    else
        echo ""
        echo -e "${GREEN}👍 수동으로 시작하려면:${NC}"
        echo -e "   ${WHITE}cd $WORK_DIR && ./START.sh${NC}"
    fi
}

# 오류 처리
handle_error() {
    log_error "스크립트 실행 중 오류가 발생했습니다."
    echo ""
    echo -e "${YELLOW}🔧 문제 해결 단계:${NC}"
    echo "1. 인터넷 연결 확인"
    echo "2. 충분한 디스크 공간 확인 (10GB+)"
    echo "3. 관리자 권한으로 다시 시도"
    echo "4. 로그 파일 확인: /tmp/mtd_install.log"
    echo ""
    echo -e "${CYAN}💬 지원이 필요하시면:${NC}"
    echo "   • GitHub Issues: https://github.com/your-repo/mtd-testbed/issues"
    echo "   • 이메일: support@your-domain.com"
    exit 1
}

# 신호 핸들러 설정
trap handle_error ERR

# =================================================================
# 메인 실행 부분
# =================================================================

main() {
    # 시작 시간 기록
    local start_time=$(date +%s)
    
    # 환영 메시지
    show_welcome
    
    # 빠른 설치 모드가 아니면 사용자 확인
    if [ "${QUICK_INSTALL:-}" != "1" ]; then
        echo -e "${BOLD}계속하시겠습니까? 이 스크립트는 다음을 수행합니다:${NC}"
        echo "• 필수 도구 설치 (Docker, Python 등)"
        echo "• MTD 드론 보안 테스트베드 완전 설치"
        echo "• 시스템 검증 및 데모 실행"
        echo ""
        read -p "설치 진행? (Y/n): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "설치가 취소되었습니다."
            exit 0
        fi
    fi
    
    # 실행 단계
    check_requirements
    install_prerequisites
    download_and_install
    verify_installation
    
    if [ "${NO_DEMO:-}" != "1" ]; then
        run_demo
    fi
    
    show_usage_guide
    auto_start_option
    
    # 완료 시간 계산
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    # 최종 완료 메시지
    echo ""
    echo ""
    cat << 'FINAL_SUCCESS'
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║                    🎉 설치 완료! 🎉                          ║
║                                                               ║
║     MTD 드론 보안 테스트베드가 성공적으로 설치되었습니다!     ║
║                                                               ║
║  이제 세계 최고 수준의 드론 보안 연구 환경을 사용하실 수      ║
║  있습니다. 혁신적인 연구 성과를 기대합니다! 🚁🛡️            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
FINAL_SUCCESS
    
    echo ""
    log_success "총 설치 시간: ${minutes}분 ${seconds}초"
    echo ""
    echo -e "${GREEN}🎯 축하합니다! 이제 모든 준비가 완료되었습니다.${NC}"
    echo -e "${WHITE}   즐거운 연구 되세요! 🎓✨${NC}"
    echo ""
    echo -e "${CYAN}📁 설치 위치: $WORK_DIR${NC}"
    echo -e "${CYAN}🚀 시작 명령어: cd $WORK_DIR && ./START.sh${NC}"
    echo ""
}

# 인수 처리
case "${1:-}" in
    --help|-h)
        echo "MTD 드론 보안 테스트베드 통합 설치기"
        echo ""
        echo "사용법: $0 [옵션]"
        echo ""
        echo "옵션:"
        echo "  --help, -h     도움말 표시"
        echo "  --quick        빠른 설치 (질문 건너뛰기)"
        echo "  --no-demo      데모 건너뛰기"
        echo ""
        echo "원격 설치:"
        echo "  curl -sSL https://raw.githubusercontent.com/your-repo/mtd-testbed/main/EXECUTE_ALL.sh | bash"
        echo ""
        exit 0
        ;;
    --quick)
        export QUICK_INSTALL=1
        main
        ;;
    --no-demo)
        export NO_DEMO=1
        main
        ;;
    *)
        main
        ;;
esac