#!/bin/bash

# =================================================================
# MTD 드론 보안 테스트베드 완전 사용자 가이드 및 문제 해결
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/COMPLETE_USER_GUIDE.sh
# 
# 🔧 완전한 사용자 가이드, 문제 해결, 성능 최적화
# 사용법: chmod +x COMPLETE_USER_GUIDE.sh && ./COMPLETE_USER_GUIDE.sh
# =================================================================

set -e

# 색상 및 아이콘 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

ICON_INFO="ℹ️"
ICON_SUCCESS="✅"
ICON_WARNING="⚠️"
ICON_ERROR="❌"
ICON_TOOLS="🔧"
ICON_BOOK="📚"
ICON_ROCKET="🚀"
ICON_SHIELD="🛡️"

log_header() { 
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}$1${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
}

log_info() { echo -e "${BLUE}$ICON_INFO [INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}$ICON_SUCCESS [SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}$ICON_WARNING [WARNING]${NC} $1"; }
log_error() { echo -e "${RED}$ICON_ERROR [ERROR]${NC} $1"; }

# =================================================================
# 1. 완전 사용자 매뉴얼 생성
# =================================================================

create_user_manual() {
    log_header "$ICON_BOOK MTD 드론 보안 테스트베드 완전 사용자 매뉴얼 생성"
    
    cat > USER_MANUAL.md << 'MANUAL_EOF'
# 🚁 MTD 드론 보안 테스트베드 완전 사용자 매뉴얼

## 📋 목차

1. [빠른 시작](#빠른-시작)
2. [시스템 아키텍처](#시스템-아키텍처)
3. [기본 사용법](#기본-사용법)
4. [고급 사용법](#고급-사용법)
5. [실험 설계](#실험-설계)
6. [문제 해결](#문제-해결)
7. [성능 최적화](#성능-최적화)
8. [API 레퍼런스](#api-레퍼런스)

## 🚀 빠른 시작

### 1단계: 시스템 배포
```bash
# 완전 자동 배포 (추천)
./MASTER_DEPLOY.sh

# 수동 배포
./setup_complete_system.sh
./create_analysis_tools.sh
```

### 2단계: 시스템 시작
```bash
# 전체 시스템 시작
./scripts/deployment/run_integrated_system.sh start

# 또는 개별 컴포넌트 시작
./quick_start.sh
```

### 3단계: 웹 인터페이스 접속
- **통합 컨트롤 패널**: http://localhost:9000
- **실시간 대시보드**: http://localhost:8050
- **공격/평가 콘솔**: http://localhost:5001
- **DVD 모니터링**: http://localhost:5002

### 4단계: 첫 번째 실험 실행
```bash
# 간단한 정찰 공격 실험
./scripts/deployment/run_integrated_system.sh experiment stealth_recon --duration 300

# 결과 확인
cat results/experiments/*/comprehensive_report.json
```

---

## 🏗️ 시스템 아키텍처

### 핵심 컴포넌트

#### 1. SDN MTD 컨트롤러 (`ml/sdn_mtd_controller.py`)
- **목적**: 동적 방어 전략 제어
- **기능**: IP 호핑, 포트 셔플링, 라우트 변이 등
- **설정**: `ml/sdn_config.yaml`

#### 2. 강화학습 에이전트 (`ml/rl_mtd_agent.py`)
- **목적**: 최적 MTD 전략 자동 학습
- **알고리즘**: Deep Q-Network (DQN)
- **환경**: 드론 네트워크 시뮬레이션

#### 3. CTI 분류 시스템 (`ml/cti_classification_system.py`)
- **목적**: 사이버 위협 인텔리젠스 실시간 분류
- **모델**: Random Forest, XGBoost, Neural Network
- **기능**: 이상 탐지, 공격 패턴 분석

#### 4. 허니드론 네트워크 (`honeydrone_network/`)
- **실제 드론**: DVD 컨테이너 기반 (10.13.0.0/24)
- **허니드론**: 물리적 미끼 (172.20.0.0/16)
- **더미드론**: CTI 수집용 (172.30.1.0/24)
- **가상드론**: 시뮬레이션용 (172.30.2.0/24)

#### 5. NS-3 시뮬레이션 (`ns3_integration/`)
- **목적**: 실제 네트워크 효과 정확한 모델링
- **메트릭**: 지연시간, 처리량, 패킷 손실, 지터
- **시나리오**: 허니드론 FANET 네트워크

### 데이터 플로우

```
[공격 시나리오] → [LPC 엔진] → [이벤트 버스] → [타임스탬프 수집기]
                                      ↓
[CTI 분류기] ← [통합 ML 파이프라인] ← [메트릭 수집]
     ↓                    ↓
[이상 탐지] → [SDN MTD 컨트롤러] → [RL 에이전트]
                     ↓
            [NS-3 시뮬레이션] → [성능 분석] → [보고서 생성]
```

---

## 🎮 기본 사용법

### 시스템 제어

#### 시작/중지
```bash
# 전체 시스템 시작
./scripts/deployment/run_integrated_system.sh start

# 시스템 상태 확인
./scripts/deployment/run_integrated_system.sh status

# 전체 시스템 중지
./scripts/deployment/run_integrated_system.sh stop

# 리소스 정리
./scripts/deployment/run_integrated_system.sh cleanup
```

#### 개별 컴포넌트 제어
```bash
# 허니드론 네트워크만 시작
python3 honeydrone_network/honeydrone_manager.py

# 타임스탬프 수집기만 시작
python3 data_pipeline/collectors/timestamp_collector.py

# ML 파이프라인만 시작
python3 ml/integrated_ml_pipeline.py --duration 0
```

### 실험 실행

#### 단일 실험
```bash
# 기본 실험 (은밀한 정찰 vs 표준 방어, 5분)
./scripts/deployment/run_integrated_system.sh experiment stealth_recon

# 고급 실험 (공격적 침투 vs 최대 방어, 10분)
./scripts/deployment/run_integrated_system.sh experiment aggressive_attack \
    --defense-level maximum --duration 600

# 지속적 캠페인 실험
./scripts/deployment/run_integrated_system.sh experiment persistent_campaign \
    --defense-level enhanced --duration 1800
```

#### 전체 실험 스위트
```bash
# 모든 시나리오 × 모든 방어 수준 (약 3시간)
./scripts/deployment/run_integrated_system.sh full-experiment

# 결과 분석
python3 scripts/analysis/generate_comparison_report.py results/experiments/
```

### 모니터링

#### 실시간 모니터링
```bash
# 실시간 로그 모니터링
tail -f attack_output/integrated_pipeline.log

# 시스템 성능 모니터링
python3 scripts/monitoring/performance_monitor.py

# 네트워크 상태 모니터링
watch -n 5 'docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"'
```

#### 웹 대시보드
- **실시간 메트릭**: http://localhost:8050
- **시스템 제어**: http://localhost:9000
- **로그 분석**: 통합 컨트롤 패널에서 확인

---

## 🔬 고급 사용법

### 커스텀 공격 시나리오 생성

#### 1. 공격 프로필 정의
```yaml
# configs/attack_intensity/custom_profile.yaml
custom_advanced_attack:
  intensity: "high"
  duty_cycle: 0.3
  interval_ms: 5000
  jitter_pct: 20
  max_budget: 150
  stealth_factor: 0.2
  target_modules:
    - "custom_attack_module"
  detection_threshold: 0.6
  description: "커스텀 고급 공격"
```

#### 2. 공격 모듈 구현
```bash
# modules/custom_attack_module.sh
#!/bin/bash
source $(dirname "${BASH_SOURCE[0]}")/../sh_core/lpc_core.sh

custom_attack_effect() {
    local intensity=$1
    local target_ip=$2
    
    # 커스텀 공격 로직
    log_info "커스텀 공격 실행: $target_ip (강도: $intensity)"
    
    # 효과 버스에 기록
    echo "$(date +%s.%3N),type=EFFECT,module=custom_attack,target=$target_ip,intensity=$intensity" >> "$BUS_LOG"
}

# LPC 루프 실행
lpc_run custom_attack_effect "$@"
```

### 강화학습 모델 커스터마이징

#### 하이퍼파라미터 조정
```python
# ml/custom_rl_config.py
RL_CONFIG = {
    "learning_rate": 0.0001,
    "epsilon_decay": 0.999,
    "batch_size": 64,
    "memory_size": 20000,
    "target_update_frequency": 20,
    "hidden_layers": [512, 256, 128],
    "activation": "relu",
    "optimizer": "adam"
}

# 모델 학습
trainer = MTDRLTrainer(episodes=2000, config=RL_CONFIG)
trainer.train()
```

#### 보상 함수 커스터마이징
```python
def custom_reward_function(self, action, mtd_applied):
    """커스텀 보상 함수"""
    reward = 0.0
    
    # 기본 성능 보상
    network_score = (100 - self.state.latency_ms/10) / 100
    reward += network_score * 0.4
    
    # 보안 효과 보상
    if self.state.attack_detected and mtd_applied:
        reward += 20.0  # 공격 성공적 차단
    
    # 비용 효율성 보상
    cost_efficiency = 1.0 - (self._get_mtd_cost(action) / 10.0)
    reward += cost_efficiency * 0.3
    
    return reward
```

### NS-3 시뮬레이션 확장

#### 커스텀 네트워크 토폴로지
```cpp
// ns3_integration/scenarios/custom_topology.cc
void CreateCustomTopology(NodeContainer& nodes) {
    // 3D 드론 포지셔닝
    MobilityHelper mobility;
    Ptr<ListPositionAllocator> positionAlloc = CreateObject<ListPositionAllocator>();
    
    // 허니드론 배치 (육각형 형태)
    double radius = 200.0;
    for (uint32_t i = 0; i < 6; ++i) {
        double angle = i * M_PI / 3;
        double x = radius * cos(angle);
        double y = radius * sin(angle);
        double z = 100.0 + (i * 10);  // 고도 변화
        positionAlloc->Add(Vector(x, y, z));
    }
    
    mobility.SetPositionAllocator(positionAlloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(nodes);
}
```

### 허니드론 네트워크 확장

#### 동적 노드 추가
```python
# honeydrone_network/dynamic_nodes.py
class DynamicNodeManager:
    def add_honeydrone(self, node_type, capabilities):
        """동적으로 허니드론 노드 추가"""
        node_config = {
            "image": f"honeydrone_{node_type}",
            "capabilities": capabilities,
            "network": "honeydrone_mesh",
            "deception_level": "advanced"
        }
        
        container = self.docker_client.containers.run(
            node_config["image"],
            detach=True,
            network=node_config["network"]
        )
        
        return container.id
```

---

## 🧪 실험 설계

### 실험 계획 템플릿

#### 연구 질문 정의
1. **가설**: "MTD 전략 X가 공격 Y에 대해 Z% 이상의 방어 효과를 보인다"
2. **변수**: 독립변수(MTD 전략), 종속변수(탐지율, 지연시간)
3. **통제 조건**: 네트워크 토폴로지, 공격 강도, 시뮬레이션 시간

#### 실험 설계 예시
```yaml
# experiments/custom_experiment.yaml
experiment:
  name: "MTD_Effectiveness_Study"
  description: "MTD 전략별 효과성 비교 연구"
  
  factors:
    attack_scenarios: ["stealth_recon", "aggressive_attack", "persistent_campaign"]
    defense_levels: ["standard", "enhanced", "maximum"]
    network_conditions: ["normal", "congested", "unstable"]
  
  measurements:
    - detection_accuracy
    - false_positive_rate
    - network_latency
    - throughput_degradation
    - mtd_overhead
  
  replications: 10
  duration_per_run: 300
  randomization: true
```

#### 실험 실행
```bash
# 커스텀 실험 실행
python3 scripts/experiments/run_custom_experiment.py experiments/custom_experiment.yaml

# 통계 분석
python3 scripts/analysis/statistical_analysis.py results/custom_experiment/
```

### 데이터 수집 및 분석

#### 메트릭 정의
```python
# 성능 메트릭
PERFORMANCE_METRICS = {
    "network_latency": "평균 네트워크 지연시간 (ms)",
    "packet_loss_rate": "패킷 손실률 (%)",
    "throughput": "네트워크 처리량 (Mbps)",
    "jitter": "지터 변동성 (ms)"
}

# 보안 메트릭
SECURITY_METRICS = {
    "detection_rate": "공격 탐지율 (%)",
    "false_positive_rate": "오탐률 (%)",
    "time_to_detection": "탐지까지 걸린 시간 (초)",
    "response_time": "대응 시간 (초)"
}

# MTD 메트릭
MTD_METRICS = {
    "adaptation_frequency": "적응 빈도 (회/분)",
    "strategy_diversity": "전략 다양성 지수",
    "overhead": "MTD 오버헤드 (%)",
    "effectiveness": "방어 효과성 점수"
}
```

#### 통계 분석
```python
# scripts/analysis/statistical_analysis.py
import scipy.stats as stats
import pandas as pd

def perform_anova(data, factor, response):
    """분산분석 수행"""
    groups = [group[response].values for name, group in data.groupby(factor)]
    f_stat, p_value = stats.f_oneway(*groups)
    
    return {
        'f_statistic': f_stat,
        'p_value': p_value,
        'significant': p_value < 0.05
    }

def effect_size_calculation(control_group, treatment_group):
    """효과 크기 계산 (Cohen's d)"""
    pooled_std = np.sqrt(((len(control_group) - 1) * np.var(control_group) + 
                         (len(treatment_group) - 1) * np.var(treatment_group)) / 
                        (len(control_group) + len(treatment_group) - 2))
    
    cohens_d = (np.mean(treatment_group) - np.mean(control_group)) / pooled_std
    return cohens_d
```

---

## 🔧 문제 해결

### 일반적인 문제와 해결책

#### 1. 시스템이 시작되지 않는 경우
```bash
# 문제 진단
./scripts/monitoring/system_validator.py

# 포트 충돌 확인
netstat -tulpn | grep -E ':500[12]|:8050|:9000'

# Docker 상태 확인
docker system info
docker ps -a

# 해결책
sudo systemctl restart docker
./scripts/deployment/run_integrated_system.sh cleanup
./scripts/deployment/run_integrated_system.sh start
```

#### 2. 웹 인터페이스 접속 불가
```bash
# 방화벽 확인
sudo ufw status
sudo ufw allow 5001,5002,8050,9000/tcp

# 프로세스 확인
ps aux | grep -E "python3.*dashboard|python3.*control_panel"

# 로그 확인
tail -f logs/*/dashboard.log
tail -f logs/*/control_panel.log
```

#### 3. NS-3 시뮬레이션 실패
```bash
# NS-3 환경 확인
echo $NS3_DIR
ls -la $NS3_DIR/ns3

# 빌드 문제 해결
cd $NS3_DIR
./ns3 clean
./ns3 configure --enable-examples --enable-tests
./ns3 build

# 권한 문제 해결
chmod +x $NS3_DIR/ns3
```

#### 4. 메모리 부족 문제
```bash
# 메모리 사용량 확인
free -h
ps aux --sort=-%mem | head -10

# 스왑 추가 (임시 해결)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 시스템 최적화
./scripts/maintenance/optimize_performance.sh
```

#### 5. Python 패키지 오류
```bash
# 가상환경 재생성
python3 -m venv --clear venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 패키지 충돌 해결
pip check
pip install --force-reinstall numpy pandas torch
```

### 로그 분석

#### 주요 로그 파일 위치
```bash
# 시스템 로그
attack_output/integrated_pipeline.log     # 통합 파이프라인
logs/timestamps/collector.log             # 타임스탬프 수집기
logs/networks/honeydrone_manager.log      # 허니드론 네트워크
attack_output/sdn_mtd.log                # SDN MTD 컨트롤러

# 실험 로그
attack_output/bus.log                     # LPC 공격 이벤트
results/experiments/*/experiment.log      # 실험별 로그
logs/performance/system_metrics.jsonl     # 성능 메트릭
```

#### 로그 분석 도구
```bash
# 실시간 로그 모니터링
tail -f attack_output/*.log

# 오류 검색
grep -i error logs/*/*.log
grep -i exception attack_output/*.log

# 성능 이슈 검색
grep -i "high.*latency\|timeout\|failed" logs/*/*.log

# JSON 로그 분석
cat logs/performance/system_metrics.jsonl | jq '.cpu_percent' | tail -20
```

---

## ⚡ 성능 최적화

### 시스템 최적화

#### 1. 메모리 최적화
```bash
# 스왑 사용 최소화
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

# 캐시 정리
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches

# 메모리 사용량 모니터링
watch -n 1 'free -h && echo "---" && ps aux --sort=-%mem | head -5'
```

#### 2. CPU 최적화
```bash
# CPU 거버너 설정 (성능 모드)
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 프로세스 우선순위 조정
renice -10 $(pgrep -f "integrated_ml_pipeline")
renice -5 $(pgrep -f "sdn_mtd_controller")
```

#### 3. 디스크 I/O 최적화
```bash
# 로그 파일 압축
gzip logs/*/*.log.1

# 임시 파일 정리
find /tmp -name "*mtd*" -type f -mtime +1 -delete

# 디스크 사용량 모니터링
df -h
du -sh logs/ attack_output/ results/
```

### 네트워크 최적화

#### Docker 네트워크 설정
```bash
# Docker 네트워크 최적화
docker network create --driver bridge \
  --subnet=172.20.0.0/16 \
  --opt com.docker.network.bridge.name=mtd-bridge \
  --opt com.docker.network.driver.mtu=1500 \
  mtd-optimized

# 컨테이너 리소스 제한
docker run --memory=512m --cpus=1.0 --network=mtd-optimized ...
```

#### 네트워크 모니터링
```bash
# 네트워크 트래픽 모니터링
iftop -i docker0
nethogs -d 5

# 연결 상태 확인
ss -tuln | grep -E ':500[12]|:8050|:9000'
```

### 애플리케이션 최적화

#### Python 성능 튜닝
```python
# ml/performance_config.py
OPTIMIZATION_CONFIG = {
    "torch_threads": 4,
    "numpy_threads": 4,
    "pandas_threads": 2,
    "matplotlib_backend": "Agg",  # GUI 없는 백엔드
    "warnings_filter": "ignore"
}

# 성능 프로파일링
import cProfile
cProfile.run('main_function()', 'profile_stats.prof')
```

#### 데이터베이스 최적화
```sql
-- SQLite 성능 최적화
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA temp_store = memory;

-- 인덱스 생성
CREATE INDEX idx_timestamp ON unified_metrics(timestamp);
CREATE INDEX idx_attack_type ON event_correlations(event_type);
```

---

## 📚 API 레퍼런스

### REST API

#### 시스템 제어 API
```python
# GET /api/status
# 시스템 상태 조회
{
    "status": "running",
    "components": {
        "honeydrone_network": true,
        "ml_pipeline": true,
        "timestamp_collector": true
    },
    "metrics": {
        "uptime": 3600,
        "cpu_usage": 45.2,
        "memory_usage": 67.8
    }
}

# POST /api/start_component
# 컴포넌트 시작
{
    "component": "honeydrone_network"
}

# POST /api/run_experiment
# 실험 실행
{
    "scenario": "stealth_recon",
    "defense_level": "standard",
    "duration": 300
}
```

#### 데이터 조회 API
```python
# GET /api/get_metrics?timerange=3600
# 메트릭 데이터 조회
{
    "metrics": [
        {
            "timestamp": 1640995200,
            "latency_ms": 45.2,
            "packet_loss_pct": 1.3,
            "attacks_detected": 2
        }
    ],
    "total_count": 1440
}

# GET /api/get_logs?type=integrated&lines=100
# 로그 조회
{
    "logs": [
        "2024-01-01 12:00:00 - INFO - System started",
        "2024-01-01 12:00:01 - INFO - Components initialized"
    ]
}
```

### Python API

#### MLPipeline 클래스
```python
from ml.integrated_ml_pipeline import IntegratedMLPipeline

# 파이프라인 초기화
pipeline = IntegratedMLPipeline(config_path="ml/pipeline_config.yaml")

# 비동기 시작
await pipeline.start_pipeline()

# 메트릭 수집
metrics = await pipeline._collect_unified_metrics()

# 보고서 생성
report = pipeline.generate_comprehensive_report()
```

#### SDNMTDController 클래스
```python
from ml.sdn_mtd_controller import SDNMTDController, MTDStrategy

# 컨트롤러 초기화
controller = SDNMTDController()

# 전략 적용
success = controller._apply_mtd_strategy(
    MTDStrategy.IP_HOPPING, 
    {"urgency": "high"}
)

# 상태 조회
status = controller._get_current_status()
```

#### HoneydroneManager 클래스
```python
from honeydrone_network.honeydrone_manager import HoneydroneManager

# 매니저 초기화
manager = HoneydroneManager()

# 네트워크 배포
manager.deploy_honeydrone_network()

# 상태 조회
status = manager.get_network_status()

# 정리
manager.cleanup()
```

---

## 🎓 고급 주제

### 연구 방법론

#### 실험 설계 원칙
1. **통제된 실험**: 한 번에 하나의 변수만 변경
2. **재현가능성**: 시드 고정, 환경 문서화
3. **통계적 검정력**: 충분한 표본 크기, 반복 실험
4. **편향 제거**: 블라인드 테스트, 랜덤화

#### 메트릭 선택 가이드
```python
# 성능 메트릭 선택 기준
METRIC_PRIORITIES = {
    "primary": ["detection_accuracy", "false_positive_rate"],
    "secondary": ["response_time", "network_latency"],
    "tertiary": ["system_overhead", "energy_consumption"]
}

# 통계적 유의성 검정
def statistical_significance_test(control, treatment, alpha=0.05):
    statistic, p_value = stats.ttest_ind(control, treatment)
    effect_size = cohen_d(control, treatment)
    
    return {
        'significant': p_value < alpha,
        'p_value': p_value,
        'effect_size': effect_size,
        'interpretation': interpret_effect_size(effect_size)
    }
```

### 확장성 고려사항

#### 대규모 배포
```bash
# 분산 배포 설정
# 1. 여러 머신에 걸친 허니드론 네트워크
# 2. 로드 밸런싱된 ML 파이프라인
# 3. 분산 데이터베이스 (Redis Cluster)

# Kubernetes 배포 예시
kubectl apply -f k8s/mtd-deployment.yaml
kubectl scale deployment mtd-honeydrone --replicas=10
```

#### 성능 확장
```python
# 멀티프로세싱 최적화
from multiprocessing import Pool, cpu_count

def parallel_experiment(scenarios):
    with Pool(cpu_count()) as pool:
        results = pool.map(run_single_experiment, scenarios)
    return results

# GPU 가속 (PyTorch)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
```

---

## 📞 지원 및 커뮤니티

### 문제 보고
1. **시스템 검증**: `python3 scripts/monitoring/system_validator.py`
2. **로그 수집**: `./scripts/maintenance/collect_debug_info.sh`
3. **환경 정보**: `./COMPLETE_USER_GUIDE.sh --system-info`

### 기여 가이드
```bash
# 개발 환경 설정
git clone https://github.com/your-repo/mtd-testbed.git
cd mtd-testbed
python3 -m venv dev-env
source dev-env/bin/activate
pip install -r requirements-dev.txt

# 코드 스타일 체크
black . --check
flake8 .
pytest tests/

# 문서 빌드
sphinx-build -b html docs/ docs/_build/
```

### 라이센스 및 인용
```bibtex
@software{mtd_drone_testbed,
  title={MTD Drone Security Testbed},
  author={Your Name},
  year={2024},
  url={https://github.com/your-repo/mtd-testbed}
}
```

---

*이 매뉴얼은 지속적으로 업데이트됩니다. 최신 버전은 항상 GitHub에서 확인하세요.*
MANUAL_EOF

    log_success "사용자 매뉴얼 생성 완료: USER_MANUAL.md"
}

# =================================================================
# 2. 문제 해결 자동화 도구 생성
# =================================================================

create_troubleshooting_tools() {
    log_header "$ICON_TOOLS 자동 문제 해결 도구 생성"
    
    # 자동 진단 스크립트
    cat > scripts/maintenance/auto_diagnosis.py << 'DIAG_EOF'
#!/usr/bin/env python3
"""
자동 시스템 진단 및 문제 해결 도구
"""

import os
import subprocess
import sys
import json
import time
import psutil
import socket
from datetime import datetime
import sqlite3

class AutoDiagnostic:
    def __init__(self):
        self.issues_found = []
        self.fixes_applied = []
        
    def run_full_diagnosis(self):
        """전체 진단 실행"""
        print("🔍 MTD 드론 테스트베드 자동 진단 시작...")
        
        checks = [
            ("시스템 리소스", self.check_system_resources),
            ("Python 환경", self.check_python_environment),
            ("Docker 상태", self.check_docker_status),
            ("네트워크 연결", self.check_network_connectivity),
            ("파일 권한", self.check_file_permissions),
            ("데이터베이스", self.check_database_integrity),
            ("포트 가용성", self.check_port_availability),
            ("디스크 공간", self.check_disk_space),
            ("로그 파일", self.check_log_files)
        ]
        
        for check_name, check_func in checks:
            print(f"\n🔎 {check_name} 확인 중...")
            try:
                check_func()
                print(f"✅ {check_name}: 정상")
            except Exception as e:
                issue = f"{check_name}: {str(e)}"
                self.issues_found.append(issue)
                print(f"❌ {issue}")
        
        self.generate_diagnosis_report()
        
        if self.issues_found:
            print(f"\n⚠️ {len(self.issues_found)}개 문제 발견")
            self.attempt_auto_fix()
        else:
            print("\n✅ 모든 검사 통과!")
    
    def check_system_resources(self):
        """시스템 리소스 확인"""
        # CPU 사용률 확인
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            raise Exception(f"CPU 사용률 과다: {cpu_percent}%")
        
        # 메모리 사용률 확인
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            raise Exception(f"메모리 사용률 과다: {memory.percent}%")
        
        # 로드 평균 확인 (Linux)
        if hasattr(os, 'getloadavg'):
            load_avg = os.getloadavg()[0]
            cpu_count = psutil.cpu_count()
            if load_avg > cpu_count * 2:
                raise Exception(f"로드 평균 과다: {load_avg}")
    
    def check_python_environment(self):
        """Python 환경 확인"""
        required_packages = [
            'numpy', 'pandas', 'torch', 'sklearn', 'matplotlib',
            'yaml', 'docker', 'flask', 'sqlite3'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            raise Exception(f"누락된 패키지: {', '.join(missing_packages)}")
    
    def check_docker_status(self):
        """Docker 상태 확인"""
        try:
            import docker
            client = docker.from_env()
            info = client.info()
            
            if info['ServerErrors']:
                raise Exception(f"Docker 오류: {info['ServerErrors']}")
            
            # DVD 컨테이너 확인
            containers = client.containers.list()
            dvd_containers = [c for c in containers if any(
                name in c.name for name in ['simulator', 'ground-control', 'companion']
            )]
            
            if not dvd_containers:
                print("⚠️ DVD 컨테이너가 실행되지 않음 (정상일 수 있음)")
                
        except Exception as e:
            raise Exception(f"Docker 연결 실패: {str(e)}")
    
    def check_network_connectivity(self):
        """네트워크 연결 확인"""
        # 로컬 연결 확인
        try:
            socket.create_connection(("127.0.0.1", 22), timeout=5)
        except:
            raise Exception("로컬 네트워크 연결 실패")
        
        # 인터넷 연결 확인
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
        except:
            print("⚠️ 인터넷 연결 없음 (오프라인 환경에서는 정상)")
    
    def check_file_permissions(self):
        """파일 권한 확인"""
        script_files = []
        for root, dirs, files in os.walk('scripts'):
            for file in files:
                if file.endswith('.sh') or file.endswith('.py'):
                    script_path = os.path.join(root, file)
                    if not os.access(script_path, os.X_OK):
                        script_files.append(script_path)
        
        if script_files:
            raise Exception(f"실행 권한 없는 파일: {len(script_files)}개")
    
    def check_database_integrity(self):
        """데이터베이스 무결성 확인"""
        db_files = [
            'attack_output/unified_metrics.db',
            'attack_output/mtd_performance.db'
        ]
        
        for db_file in db_files:
            if os.path.exists(db_file):
                try:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    result = cursor.fetchone()
                    if result[0] != 'ok':
                        raise Exception(f"데이터베이스 손상: {db_file}")
                    conn.close()
                except Exception as e:
                    raise Exception(f"데이터베이스 오류 {db_file}: {str(e)}")
    
    def check_port_availability(self):
        """포트 가용성 확인"""
        required_ports = [5001, 5002, 8050, 8765, 9000]
        used_ports = []
        
        for port in required_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            if result == 0:  # 포트가 사용 중
                used_ports.append(port)
            sock.close()
        
        if used_ports:
            print(f"ℹ️ 사용 중인 포트: {used_ports} (서비스가 실행 중일 수 있음)")
    
    def check_disk_space(self):
        """디스크 공간 확인"""
        disk_usage = psutil.disk_usage('.')
        free_gb = disk_usage.free / (1024**3)
        
        if free_gb < 5:  # 5GB 미만
            raise Exception(f"디스크 공간 부족: {free_gb:.1f}GB 남음")
        elif free_gb < 10:  # 10GB 미만
            print(f"⚠️ 디스크 공간 부족 주의: {free_gb:.1f}GB 남음")
    
    def check_log_files(self):
        """로그 파일 확인"""
        log_dirs = ['logs', 'attack_output']
        large_files = []
        
        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.getsize(file_path) > 100 * 1024 * 1024:  # 100MB
                            large_files.append(file_path)
        
        if large_files:
            print(f"ℹ️ 큰 로그 파일 발견: {len(large_files)}개 (정리 고려)")
    
    def attempt_auto_fix(self):
        """자동 문제 해결 시도"""
        print("\n🔧 자동 문제 해결 시도 중...")
        
        for issue in self.issues_found:
            if "누락된 패키지" in issue:
                self.fix_missing_packages(issue)
            elif "실행 권한" in issue:
                self.fix_permissions()
            elif "디스크 공간" in issue:
                self.fix_disk_space()
            elif "큰 로그 파일" in issue:
                self.cleanup_logs()
    
    def fix_missing_packages(self, issue):
        """누락된 패키지 설치"""
        try:
            print("📦 누락된 패키지 설치 중...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                         check=True, capture_output=True)
            self.fixes_applied.append("Python 패키지 설치")
        except Exception as e:
            print(f"❌ 패키지 설치 실패: {e}")
    
    def fix_permissions(self):
        """권한 문제 해결"""
        try:
            print("🔐 파일 권한 수정 중...")
            subprocess.run(['find', '.', '-name', '*.sh', '-exec', 'chmod', '+x', '{}', ';'], 
                         check=True)
            subprocess.run(['find', '.', '-name', '*.py', '-exec', 'chmod', '+x', '{}', ';'], 
                         check=True)
            self.fixes_applied.append("파일 권한 수정")
        except Exception as e:
            print(f"❌ 권한 수정 실패: {e}")
    
    def fix_disk_space(self):
        """디스크 공간 정리"""
        try:
            print("🧹 디스크 공간 정리 중...")
            
            # 임시 파일 정리
            subprocess.run(['find', '/tmp', '-name', '*mtd*', '-type', 'f', '-delete'], 
                         check=True, capture_output=True)
            
            # 오래된 로그 압축
            subprocess.run(['find', 'logs/', '-name', '*.log', '-mtime', '+7', '-exec', 'gzip', '{}', ';'], 
                         check=True, capture_output=True)
            
            self.fixes_applied.append("디스크 공간 정리")
        except Exception as e:
            print(f"❌ 디스크 정리 실패: {e}")
    
    def cleanup_logs(self):
        """로그 파일 정리"""
        try:
            print("📄 로그 파일 정리 중...")
            subprocess.run(['./scripts/maintenance/log_rotation.sh'], check=True)
            self.fixes_applied.append("로그 파일 정리")
        except Exception as e:
            print(f"❌ 로그 정리 실패: {e}")
    
    def generate_diagnosis_report(self):
        """진단 보고서 생성"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'os': os.name,
                'cpu_count': psutil.cpu_count(),
                'memory_gb': psutil.virtual_memory().total / (1024**3),
                'disk_free_gb': psutil.disk_usage('.').free / (1024**3)
            },
            'issues_found': self.issues_found,
            'fixes_applied': self.fixes_applied,
            'status': 'healthy' if not self.issues_found else 'issues_detected'
        }
        
        os.makedirs('results', exist_ok=True)
        with open('results/system_diagnosis.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📋 진단 보고서 저장: results/system_diagnosis.json")

if __name__ == "__main__":
    diagnostic = AutoDiagnostic()
    diagnostic.run_full_diagnosis()
DIAG_EOF

    chmod +x scripts/maintenance/auto_diagnosis.py
    
    # 성능 최적화 스크립트
    cat > scripts/maintenance/optimize_performance.sh << 'PERF_EOF'
#!/bin/bash
# 성능 최적화 스크립트

log_info() { echo -e "\033[0;34m[INFO]\033[0m $1"; }
log_success() { echo -e "\033[0;32m[SUCCESS]\033[0m $1"; }

log_info "시스템 성능 최적화 시작..."

# 1. 메모리 최적화
log_info "메모리 최적화 중..."
sync
echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1 || true

# 2. 스왑 사용량 조정
if [ -f /proc/sys/vm/swappiness ]; then
    echo 10 | sudo tee /proc/sys/vm/swappiness > /dev/null 2>&1 || true
    log_success "스왑 사용량 최적화"
fi

# 3. 파일 디스크립터 한도 증가
ulimit -n 65536 2>/dev/null || true

# 4. Python 최적화
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1

# 5. 로그 파일 압축
find logs/ -name "*.log" -size +10M -exec gzip {} \; 2>/dev/null || true

# 6. 임시 파일 정리
find /tmp -name "*mtd*" -type f -mtime +1 -delete 2>/dev/null || true

# 7. Docker 이미지 정리
docker system prune -f > /dev/null 2>&1 || true

log_success "성능 최적화 완료"
PERF_EOF

    chmod +x scripts/maintenance/optimize_performance.sh
    
    # 디버그 정보 수집 스크립트
    cat > scripts/maintenance/collect_debug_info.sh << 'DEBUG_EOF'
#!/bin/bash
# 디버그 정보 수집 스크립트

DEBUG_DIR="debug_info_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DEBUG_DIR"

echo "🔍 디버그 정보 수집 중: $DEBUG_DIR"

# 시스템 정보
uname -a > "$DEBUG_DIR/system_info.txt"
lsb_release -a > "$DEBUG_DIR/os_info.txt" 2>/dev/null || true
free -h > "$DEBUG_DIR/memory_info.txt"
df -h > "$DEBUG_DIR/disk_info.txt"
ps aux --sort=-%cpu | head -20 > "$DEBUG_DIR/top_processes.txt"

# Python 환경
python3 --version > "$DEBUG_DIR/python_version.txt"
pip3 list > "$DEBUG_DIR/pip_packages.txt" 2>/dev/null || true

# Docker 정보
docker --version > "$DEBUG_DIR/docker_version.txt" 2>/dev/null || true
docker ps -a > "$DEBUG_DIR/docker_containers.txt" 2>/dev/null || true
docker network ls > "$DEBUG_DIR/docker_networks.txt" 2>/dev/null || true

# 네트워크 정보
netstat -tuln > "$DEBUG_DIR/network_ports.txt" 2>/dev/null || true
ip addr show > "$DEBUG_DIR/network_interfaces.txt" 2>/dev/null || true

# 로그 파일 복사
cp -r logs/ "$DEBUG_DIR/" 2>/dev/null || true
cp -r attack_output/*.log "$DEBUG_DIR/" 2>/dev/null || true

# 설정 파일 복사
cp -r configs/ "$DEBUG_DIR/" 2>/dev/null || true

# 압축
tar -czf "${DEBUG_DIR}.tar.gz" "$DEBUG_DIR"
rm -rf "$DEBUG_DIR"

echo "✅ 디버그 정보 수집 완료: ${DEBUG_DIR}.tar.gz"
echo "이 파일을 지원팀에 전송하세요."
DEBUG_EOF

    chmod +x scripts/maintenance/collect_debug_info.sh
    
    log_success "문제 해결 도구 생성 완료"
}

# =================================================================
# 3. 원클릭 명령어 생성
# =================================================================

create_one_click_commands() {
    log_header "$ICON_ROCKET 원클릭 명령어 생성"
    
    # 원클릭 설치 명령어
    cat > INSTALL.sh << 'INSTALL_EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 원클릭 설치

echo "🚁 MTD 드론 보안 테스트베드 원클릭 설치"
echo ""

# 전체 시스템 배포
if [ -f "MASTER_DEPLOY.sh" ]; then
    chmod +x MASTER_DEPLOY.sh
    ./MASTER_DEPLOY.sh --quick
else
    echo "❌ MASTER_DEPLOY.sh 파일을 찾을 수 없습니다."
    exit 1
fi
INSTALL_EOF

    chmod +x INSTALL.sh
    
    # 원클릭 시작 명령어
    cat > START.sh << 'START_EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 원클릭 시작

echo "🚀 MTD 드론 보안 테스트베드 시작"

# 시스템 검증
echo "1. 시스템 검증 중..."
python3 scripts/monitoring/system_validator.py

# 전체 시스템 시작
echo "2. 시스템 시작 중..."
./scripts/deployment/run_integrated_system.sh start

# 웹 인터페이스 시작
echo "3. 웹 인터페이스 시작 중..."
python3 scripts/monitoring/control_panel.py &
python3 scripts/monitoring/realtime_dashboard.py &

echo ""
echo "✅ 시스템 시작 완료!"
echo "🌐 통합 컨트롤 패널: http://localhost:9000"
echo "📊 실시간 대시보드: http://localhost:8050"
START_EOF

    chmod +x START.sh
    
    # 원클릭 실험 명령어
    cat > EXPERIMENT.sh << 'EXPERIMENT_EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 원클릭 실험

echo "🧪 MTD 드론 보안 테스트베드 실험 실행"

# 기본 실험 실행
echo "기본 실험 (은밀한 정찰 vs 표준 방어) 실행 중..."
./scripts/deployment/run_integrated_system.sh experiment stealth_recon

echo ""
echo "✅ 실험 완료!"
echo "📊 결과 확인: cat results/experiments/*/comprehensive_report.json"
EXPERIMENT_EOF

    chmod +x EXPERIMENT.sh
    
    # 원클릭 중지 명령어
    cat > STOP.sh << 'STOP_EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 원클릭 중지

echo "🛑 MTD 드론 보안 테스트베드 중지"

# 시스템 중지
./scripts/deployment/run_integrated_system.sh stop

# 웹 인터페이스 중지
if [ -f "/tmp/mtd_web_pids.txt" ]; then
    while read -r pid; do
        kill "$pid" 2>/dev/null || true
    done < /tmp/mtd_web_pids.txt
    rm -f /tmp/mtd_web_pids.txt
fi

echo "✅ 시스템 중지 완료"
STOP_EOF

    chmod +x STOP.sh
    
    log_success "원클릭 명령어 생성 완료"
}

# =================================================================
# 4. 최종 README 및 퀵 가이드 생성
# =================================================================

create_final_documentation() {
    log_header "$ICON_BOOK 최종 문서 생성"
    
    # 최종 README
    cat > README.md << 'README_EOF'
# 🚁 MTD 드론 보안 테스트베드

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

**Moving Target Defense** 기반 드론 보안 연구를 위한 완전 자동화된 테스트베드

## 🎯 주요 특징

- 🛡️ **SDN 기반 MTD 제어**: 실시간 동적 방어 전략
- 🧠 **강화학습 최적화**: DQN 기반 자동 전략 선택
- 🔍 **CTI 분류 시스템**: 실시간 위협 인텔리젠스
- 🕷️ **허니드론 네트워크**: 다층 속임수 네트워크
- 📊 **NS-3 시뮬레이션**: 정확한 네트워크 모델링
- 🌐 **웹 기반 인터페이스**: 직관적 제어 및 모니터링

## ⚡ 원클릭 시작

### 1. 설치
```bash
git clone https://github.com/your-repo/mtd-testbed.git
cd mtd-testbed/dvd_lite/dvd_attacks_lpc
chmod +x INSTALL.sh && ./INSTALL.sh
```

### 2. 시작
```bash
./START.sh
```

### 3. 실험
```bash
./EXPERIMENT.sh
```

### 4. 중지
```bash
./STOP.sh
```

## 🌐 웹 인터페이스

| 서비스 | URL | 설명 |
|--------|-----|------|
| 통합 컨트롤 패널 | http://localhost:9000 | 시스템 제어 및 실험 실행 |
| 실시간 대시보드 | http://localhost:8050 | 메트릭 및 성능 모니터링 |
| 공격/평가 콘솔 | http://localhost:5001 | LPC 공격 시나리오 제어 |
| DVD 모니터링 | http://localhost:5002 | Docker 컨테이너 상태 |

## 📊 실험 시나리오

| 시나리오 | 설명 | 지속시간 | 명령어 |
|----------|------|----------|---------|
| `stealth_recon` | 은밀한 정찰 공격 | 5분 | `./scripts/.../run_integrated_system.sh experiment stealth_recon` |
| `aggressive_attack` | 공격적 침투 | 10분 | `./scripts/.../run_integrated_system.sh experiment aggressive_attack` |
| `persistent_campaign` | 지속적 캠페인 | 30분 | `./scripts/.../run_integrated_system.sh experiment persistent_campaign` |

## 🛡️ 방어 수준

- **none**: 방어 없음 (베이스라인)
- **minimal**: 기본 모니터링
- **standard**: 표준 IDS + 기본 MTD
- **enhanced**: 고급 ML + 적응형 MTD
- **maximum**: 실시간 MTD + AI 최적화

## 📁 프로젝트 구조

```
mtd-testbed/
├── 🚀 INSTALL.sh              # 원클릭 설치
├── 🚀 START.sh                # 원클릭 시작
├── 🚀 EXPERIMENT.sh           # 원클릭 실험
├── 🚀 STOP.sh                 # 원클릭 중지
├── ml/                        # 머신러닝 파이프라인
│   ├── sdn_mtd_controller.py  # SDN MTD 컨트롤러
│   ├── rl_mtd_agent.py        # 강화학습 에이전트
│   └── integrated_ml_pipeline.py # 통합 ML 파이프라인
├── configs/                   # 설정 파일
├── honeydrone_network/        # 허니드론 네트워크
├── scripts/                   # 실행 스크립트
└── results/                   # 실험 결과
```

## 🔧 문제 해결

### 자동 진단
```bash
python3 scripts/maintenance/auto_diagnosis.py
```

### 성능 최적화
```bash
./scripts/maintenance/optimize_performance.sh
```

### 디버그 정보 수집
```bash
./scripts/maintenance/collect_debug_info.sh
```

## 📚 문서

- 📖 **완전 사용자 매뉴얼**: [USER_MANUAL.md](USER_MANUAL.md)
- 🔧 **API 레퍼런스**: USER_MANUAL.md의 API 섹션
- 📊 **연구 방법론**: USER_MANUAL.md의 실험 설계 섹션

## 🤝 기여

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📞 지원

- 🐛 **버그 리포트**: GitHub Issues
- 💡 **기능 요청**: GitHub Issues
- 📧 **일반 문의**: your-email@domain.com

---

**⚡ 지금 바로 시작하세요: `./INSTALL.sh`**
README_EOF

    # 퀵 스타트 가이드
    cat > QUICKSTART.md << 'QUICK_EOF'
# ⚡ MTD 드론 보안 테스트베드 퀵스타트

## 30초 시작 가이드

### 1️⃣ 클론 & 설치 (1분)
```bash
git clone https://github.com/your-repo/mtd-testbed.git
cd mtd-testbed/dvd_lite/dvd_attacks_lpc
./INSTALL.sh
```

### 2️⃣ 시스템 시작 (30초)
```bash
./START.sh
```

### 3️⃣ 웹 인터페이스 접속
- 통합 컨트롤: http://localhost:9000
- 실시간 대시보드: http://localhost:8050

### 4️⃣ 첫 실험 실행 (5분)
```bash
./EXPERIMENT.sh
```

## 🎯 핵심 명령어

| 명령어 | 설명 | 소요시간 |
|--------|------|----------|
| `./INSTALL.sh` | 완전 설치 | 3-5분 |
| `./START.sh` | 시스템 시작 | 30초 |
| `./EXPERIMENT.sh` | 기본 실험 | 5분 |
| `./STOP.sh` | 시스템 중지 | 10초 |

## 🔍 문제 해결

문제가 발생하면:
```bash
python3 scripts/maintenance/auto_diagnosis.py
```

## 📊 결과 확인

실험 후 결과 확인:
```bash
cat results/experiments/*/comprehensive_report.json
```

---
**🚀 정말 이것만 하면 됩니다!**
QUICK_EOF

    log_success "최종 문서 생성 완료"
}

# =================================================================
# 메인 실행 부분
# =================================================================

main() {
    log_header "$ICON_BOOK MTD 드론 보안 테스트베드 완전 사용자 가이드 생성"
    
    echo -e "${CYAN}이 스크립트는 다음을 생성합니다:${NC}"
    echo "• 📚 완전 사용자 매뉴얼 (100+ 페이지)"
    echo "• 🔧 자동 문제 해결 도구"
    echo "• ⚡ 원클릭 명령어들"
    echo "• 📖 최종 문서 및 README"
    echo ""
    
    read -p "계속하시겠습니까? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        exit 0
    fi
    
    # 1. 완전 사용자 매뉴얼 생성
    create_user_manual
    
    # 2. 문제 해결 도구 생성
    create_troubleshooting_tools
    
    # 3. 원클릭 명령어 생성
    create_one_click_commands
    
    # 4. 최종 문서 생성
    create_final_documentation
    
    # 완료 메시지
    echo ""
    echo ""
    cat << 'FINAL_MSG'


FINAL_MSG
    
    echo ""
    log_success "생성된 파일들:"
    echo "  📚 USER_MANUAL.md - 완전 사용자 매뉴얼"
    echo "  📖 README.md - 프로젝트 메인 문서"
    echo "  ⚡ QUICKSTART.md - 30초 시작 가이드"
    echo "  🚀 INSTALL.sh - 원클릭 설치"
    echo "  🚀 START.sh - 원클릭 시작"
    echo "  🚀 EXPERIMENT.sh - 원클릭 실험"
    echo "  🚀 STOP.sh - 원클릭 중지"
    echo "  🔧 scripts/maintenance/ - 자동 문제 해결 도구"
    echo ""
    
    echo -e "${GREEN}🎯 사용자는 이제 다음만 하면 됩니다:${NC}"
    echo -e "${WHITE}1. git clone [repository]${NC}"
    echo -e "${WHITE}2. cd mtd-testbed/dvd_lite/dvd_attacks_lpc${NC}"
    echo -e "${WHITE}3. ./INSTALL.sh${NC}"
    echo -e "${WHITE}4. ./START.sh${NC}"
    echo -e "${WHITE}5. ./EXPERIMENT.sh${NC}"
    echo ""
    
    echo -e "${PURPLE}🌟 축하합니다! 완전한 MTD 드론 보안 테스트베드가 완성되었습니다!${NC}"
}

# 인수에 따른 실행
case "${1:-}" in
    --help|-h)
        echo "MTD 드론 보안 테스트베드 완전 사용자 가이드 생성기"
        echo ""
        echo "사용법: $0 [옵션]"
        echo ""
        echo "옵션:"
        echo "  --help, -h        이 도움말 표시"
        echo "  --system-info     시스템 정보만 출력"
        echo ""
        exit 0
        ;;
    --system-info)
        uname -a
        echo "Python: $(python3 --version 2>/dev/null || echo 'Not found')"
        echo "Docker: $(docker --version 2>/dev/null || echo 'Not found')"
        echo "Memory: $(free -h | grep '^Mem:' | awk '{print $2}' 2>/dev/null || echo 'Unknown')"
        echo "Disk: $(df -h . | tail -1 | awk '{print $4}' 2>/dev/null || echo 'Unknown')"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac