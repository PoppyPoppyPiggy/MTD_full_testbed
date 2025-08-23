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
