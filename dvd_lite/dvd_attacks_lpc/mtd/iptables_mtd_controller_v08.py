#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iptables MTD Controller v08 - Service Swap 기능 추가
=====================================================

실제 테스트베드에서 iptables를 제어하여 MTD를 구현하는 컨트롤러.

기능:
1. IP/Port Shuffling (DNAT/SNAT)
2. Decoy Activation (Honeypot 리다이렉션)
3. Blacklist (공격 IP 차단)
4. Service Swap (서비스 매핑 변경) - [NEW]
5. Rate Limiting (트래픽 제한)

Service Swap References:
- Container Live Migration: 10-100ms downtime (Govindaraj & Artemenko, IEEE ETFA 2018)
- MiGrror Migration: <10ms downtime with minimal bandwidth overhead (arXiv:2305.10977)
- SDN-based MTD: <7% overhead for resilience (ScienceDirect Topics)
- Service Migration Latency: 50-150ms typical (IEEE/ACM ToN 2019)
- IP Shuffling Connection Reset: 15-20% connection loss (IEEE ETFA 2018)

환경:
- Docker 네트워크: 10.13.0.0/24 (simulator)
- 서비스: FC(10.13.0.2), CC(10.13.0.3), GCS(10.13.0.4), SIM(10.13.0.5)

작성자: MTD-RL Research Team
버전: 0.8.1
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import random
import threading

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [MTD-Controller] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("IptablesMTDController")


# =============================================================================
# 설정 상수
# =============================================================================

# 네트워크 설정
NETWORK_PREFIX = "10.13.0"
DOCKER_BRIDGE = "br-simulator"

# 서비스 정의
DEFAULT_SERVICES = {
    "fc_mavlink": {
        "name": "Flight Controller MAVLink",
        "real_ip": "10.13.0.2",
        "real_port": 14550,
        "protocol": "udp",
        "container": "flight-controller-lite",
        "priority": 1,  # 높을수록 중요
        "swappable_with": ["decoy_fc_mavlink"],  # [NEW] 스왑 가능 서비스
    },
    "cc_sitl": {
        "name": "Companion Computer SITL",
        "real_ip": "10.13.0.3",
        "real_port": 5760,
        "protocol": "tcp",
        "container": "companion-computer-lite",
        "priority": 1,
        "swappable_with": ["sim_sitl"],
    },
    "cc_mavlink": {
        "name": "Companion Computer MAVLink",
        "real_ip": "10.13.0.3",
        "real_port": 14550,
        "protocol": "udp",
        "container": "companion-computer-lite",
        "priority": 1,
        "swappable_with": [],
    },
    "cc_web": {
        "name": "Companion Computer Web UI",
        "real_ip": "10.13.0.3",
        "real_port": 3000,
        "protocol": "tcp",
        "container": "companion-computer-lite",
        "priority": 2,
        "swappable_with": [],
    },
    "gcs_mavlink": {
        "name": "Ground Control Station MAVLink",
        "real_ip": "10.13.0.4",
        "real_port": 14550,
        "protocol": "udp",
        "container": "ground-control-station-lite",
        "priority": 1,
        "swappable_with": ["decoy_gcs_mavlink"],
    },
    "sim_sitl": {
        "name": "Simulator SITL",
        "real_ip": "10.13.0.5",
        "real_port": 5501,
        "protocol": "tcp",
        "container": "simulator-lite",
        "priority": 2,
        "swappable_with": ["cc_sitl"],
    },
    # [NEW] 디코이 서비스 정의
    "decoy_fc_mavlink": {
        "name": "Decoy Flight Controller MAVLink",
        "real_ip": "10.13.0.7",
        "real_port": 14550,
        "protocol": "udp",
        "container": "honeypot-fc",
        "priority": 3,
        "is_decoy": True,
        "swappable_with": ["fc_mavlink"],
    },
    "decoy_gcs_mavlink": {
        "name": "Decoy Ground Control Station MAVLink",
        "real_ip": "10.13.0.8",
        "real_port": 14550,
        "protocol": "udp",
        "container": "honeypot-gcs",
        "priority": 3,
        "is_decoy": True,
        "swappable_with": ["gcs_mavlink"],
    },
}

# Virtual IP/Port 풀
VIP_POOL_START = 100
VIP_POOL_END = 199
PORT_POOL_START = 10000
PORT_POOL_END = 59999

# 디코이 설정
DECOY_IP_START = 200
DECOY_IP_END = 249
HONEYPOT_PORT = 9999  # 모든 디코이가 리다이렉트될 포트


# =============================================================================
# [NEW] Service Swap Cost Model - Reference-based Parameters
# =============================================================================
@dataclass
class ServiceSwapCostModel:
    """
    서비스 스왑 비용 모델 - 레퍼런스 기반 파라미터
    
    References:
    - IEEE ETFA 2018: Container live migration 10-100ms downtime
    - arXiv:2305.10977 (MiGrror): <10ms downtime for microservices
    - ScienceDirect Topics: SDN-based MTD <7% overhead
    - IEEE/ACM ToN 2019: Service migration 50-150ms typical latency
    """
    # 레이턴시 파라미터 (ms)
    swap_latency_ms: float = 75.0           # 평균 75ms (10-100ms range)
    swap_sync_time_ms: float = 25.0         # 상태 동기화 시간
    
    # 대역폭 오버헤드
    swap_bandwidth_overhead: float = 0.05   # 5% bandwidth overhead during swap
    
    # 연결 영향 (Reference: 15-20% connection loss from IEEE ETFA 2018)
    swap_connection_reset_prob: float = 0.15  # 연결 리셋 확률 15%
    connection_recovery_ms: float = 500.0     # 연결 복구 시간
    
    # CPU/메모리 오버헤드
    swap_cpu_overhead: float = 0.08         # 8% CPU overhead
    swap_memory_overhead_mb: float = 64.0   # 임시 메모리 사용
    
    # 에너지 소모
    swap_energy_joule: float = 0.12         # 셔플보다 높은 에너지 소모
    
    # 가용성 영향
    swap_availability_impact: float = 0.02  # 2% availability reduction
    
    # 보안 효과 파라미터
    confusion_duration_steps: int = 20      # 공격자 혼란 지속 시간
    belief_invalidation_factor: float = 0.3 # belief 무효화 비율
    exploit_protection_factor: float = 0.25 # 스왑 직후 익스플로잇 성공률 감소
    protection_duration_steps: int = 10     # 보호 효과 지속 시간


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class ServiceMapping:
    """서비스 매핑 정보"""
    service_name: str
    real_ip: str
    real_port: int
    virtual_ip: str
    virtual_port: int
    protocol: str
    active: bool = True
    is_decoy: bool = False
    created_at: float = field(default_factory=time.time)
    shuffle_count: int = 0
    # [NEW] 서비스 스왑 관련 필드
    swap_count: int = 0
    last_swap_step: int = 0
    original_role: Optional[str] = None
    swapped_with: Optional[str] = None  # 현재 스왑된 서비스 이름


@dataclass
class DecoyService:
    """디코이 서비스 정보"""
    decoy_id: str
    target_service: str
    decoy_ip: str
    decoy_port: int
    protocol: str
    hits: int = 0
    created_at: float = field(default_factory=time.time)
    last_hit: Optional[float] = None


@dataclass
class BlacklistEntry:
    """블랙리스트 항목"""
    ip: str
    reason: str
    created_at: float
    expires_at: float
    hits_before_block: int = 0


@dataclass
class ServiceSwapRecord:
    """[NEW] 서비스 스왑 기록"""
    swap_id: str
    service_a: str
    service_b: str
    swap_time: float
    intensity: float
    latency_ms: float
    connection_resets: int
    active: bool = True
    expires_at: Optional[float] = None


@dataclass
class MTDStatistics:
    """MTD 통계"""
    # 카운터
    total_shuffles: int = 0
    total_port_hops: int = 0
    total_decoy_activations: int = 0
    total_decoy_hits: int = 0
    total_blacklist_adds: int = 0
    total_blacklist_blocks: int = 0
    # [NEW] 서비스 스왑 통계
    total_service_swaps: int = 0
    total_swap_confusion_caused: float = 0.0
    total_swap_connection_resets: int = 0
    total_swap_latency_ms: float = 0.0
    
    # 비용 (가중치 적용)
    total_cost: float = 0.0
    
    # 시간
    start_time: float = field(default_factory=time.time)
    last_action_time: Optional[float] = None
    last_swap_time: Optional[float] = None  # [NEW]
    
    def to_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# iptables MTD Controller
# =============================================================================

class IptablesMTDController:
    """
    iptables 기반 MTD 컨트롤러 - Service Swap 기능 추가
    
    실제 iptables 명령을 실행하여 MTD를 구현합니다.
    dry_run=True이면 명령을 로깅만 합니다.
    """
    
    # 비용 가중치
    COST_WEIGHTS = {
        "shuffle": 0.3,
        "port_hop": 0.2,
        "decoy": 0.15,
        "blacklist": 0.1,
        "rate_limit": 0.05,
        "service_swap": 0.4,  # [NEW] 서비스 스왑은 비용이 더 높음
    }
    
    def __init__(
        self,
        dry_run: bool = True,
        network_prefix: str = NETWORK_PREFIX,
        services: Optional[Dict] = None,
        state_file: Optional[str] = None,
        log_file: Optional[str] = None,
        swap_cost_model: Optional[ServiceSwapCostModel] = None,
    ):
        """
        Args:
            dry_run: True이면 실제 명령 실행 안함
            network_prefix: 네트워크 프리픽스 (예: "10.13.0")
            services: 서비스 정의 (None이면 기본값 사용)
            state_file: 상태 저장 파일 경로
            log_file: MTD 액션 로그 파일
            swap_cost_model: [NEW] 서비스 스왑 비용 모델
        """
        self.dry_run = dry_run
        self.network_prefix = network_prefix
        self.services_config = services or DEFAULT_SERVICES
        
        # 현재 상태
        self.service_mappings: Dict[str, ServiceMapping] = {}
        self.decoys: Dict[str, DecoyService] = {}
        self.blacklist: Dict[str, BlacklistEntry] = {}
        self.used_virtual_ips: Set[str] = set()
        self.used_virtual_ports: Set[int] = set()
        
        # [NEW] 서비스 스왑 관련 상태
        self.active_swaps: Dict[str, ServiceSwapRecord] = {}
        self.swap_history: List[ServiceSwapRecord] = []
        self.swap_cost_model = swap_cost_model or ServiceSwapCostModel()
        self.current_step: int = 0  # 현재 스텝 (스왑 보호 효과 계산용)
        
        # 통계
        self.stats = MTDStatistics()
        
        # 파일 경로
        self.state_file = Path(state_file) if state_file else None
        self.log_file = Path(log_file) if log_file else None
        
        # 락 (thread-safe)
        self._lock = threading.RLock()
        
        # 초기화
        self._initialize_services()
        
        if self.state_file and self.state_file.exists():
            self._load_state()
        
        logger.info(
            f"IptablesMTDController initialized "
            f"(dry_run={dry_run}, services={len(self.services_config)}, "
            f"swap_enabled=True)"
        )
    
    # =========================================================================
    # 초기화 및 상태 관리
    # =========================================================================
    
    def _initialize_services(self):
        """서비스 초기 매핑 설정"""
        for svc_name, svc_config in self.services_config.items():
            self.service_mappings[svc_name] = ServiceMapping(
                service_name=svc_name,
                real_ip=svc_config["real_ip"],
                real_port=svc_config["real_port"],
                virtual_ip=svc_config["real_ip"],  # 초기: 실제 IP = 가상 IP
                virtual_port=svc_config["real_port"],
                protocol=svc_config["protocol"],
                is_decoy=svc_config.get("is_decoy", False),
                original_role=svc_name,  # [NEW] 원래 역할 기록
            )
    
    def _save_state(self):
        """현재 상태 파일로 저장"""
        if not self.state_file:
            return
        
        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mappings": {k: asdict(v) for k, v in self.service_mappings.items()},
            "decoys": {k: asdict(v) for k, v in self.decoys.items()},
            "blacklist": {k: asdict(v) for k, v in self.blacklist.items()},
            "active_swaps": {k: asdict(v) for k, v in self.active_swaps.items()},
            "stats": self.stats.to_dict(),
        }
        
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _load_state(self):
        """저장된 상태 로드"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # 매핑 복원
            for svc_name, mapping_dict in state.get("mappings", {}).items():
                if svc_name in self.service_mappings:
                    for key, value in mapping_dict.items():
                        if hasattr(self.service_mappings[svc_name], key):
                            setattr(self.service_mappings[svc_name], key, value)
            
            logger.info(f"State loaded from {self.state_file}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    
    def _log_action(self, action_type: str, details: Dict):
        """MTD 액션 로깅"""
        if not self.log_file:
            return
        
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "details": details,
        }
        
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.warning(f"Failed to log action: {e}")
    
    def set_step(self, step: int):
        """[NEW] 현재 스텝 설정 (환경에서 호출)"""
        self.current_step = step
    
    # =========================================================================
    # iptables 명령 실행
    # =========================================================================
    
    def _run_iptables(self, cmd: str, table: str = "nat") -> Tuple[bool, str]:
        """
        iptables 명령 실행
        
        Args:
            cmd: iptables 명령 (iptables 키워드 제외)
            table: 테이블 (nat, filter, mangle)
        
        Returns:
            (성공 여부, 에러 메시지)
        """
        full_cmd = f"iptables -t {table} {cmd}"
        
        if self.dry_run:
            logger.debug(f"[DRY-RUN] {full_cmd}")
            return True, ""
        
        try:
            result = subprocess.run(
                full_cmd.split(),
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"iptables error: {error_msg}")
                return False, error_msg
            
            return True, ""
            
        except subprocess.TimeoutExpired:
            logger.error("iptables command timeout")
            return False, "timeout"
        except Exception as e:
            logger.error(f"iptables execution failed: {e}")
            return False, str(e)
    
    def _run_iptables_batch(self, commands: List[str], table: str = "nat") -> int:
        """여러 iptables 명령 일괄 실행"""
        success_count = 0
        for cmd in commands:
            ok, _ = self._run_iptables(cmd, table)
            if ok:
                success_count += 1
        return success_count
    
    # =========================================================================
    # IP/Port 할당
    # =========================================================================
    
    def _allocate_virtual_ip(self) -> str:
        """새로운 Virtual IP 할당"""
        with self._lock:
            for suffix in range(VIP_POOL_START, VIP_POOL_END + 1):
                vip = f"{self.network_prefix}.{suffix}"
                if vip not in self.used_virtual_ips:
                    self.used_virtual_ips.add(vip)
                    return vip
        
        # 풀 소진 시 랜덤 선택 (재사용)
        suffix = random.randint(VIP_POOL_START, VIP_POOL_END)
        return f"{self.network_prefix}.{suffix}"
    
    def _allocate_virtual_port(self) -> int:
        """새로운 Virtual Port 할당"""
        with self._lock:
            for _ in range(100):  # 최대 100번 시도
                port = random.randint(PORT_POOL_START, PORT_POOL_END)
                if port not in self.used_virtual_ports:
                    self.used_virtual_ports.add(port)
                    return port
        
        # 랜덤 선택
        return random.randint(PORT_POOL_START, PORT_POOL_END)
    
    def _release_virtual_ip(self, vip: str):
        """Virtual IP 해제"""
        with self._lock:
            self.used_virtual_ips.discard(vip)
    
    def _release_virtual_port(self, port: int):
        """Virtual Port 해제"""
        with self._lock:
            self.used_virtual_ports.discard(port)
    
    # =========================================================================
    # MTD 액션: Network Shuffle
    # =========================================================================
    
    def shuffle_network(
        self,
        service_name: str,
        intensity: float = 0.5,
        change_ip: bool = True,
        change_port: bool = True,
    ) -> bool:
        """
        네트워크 셔플: Virtual IP/Port 재할당
        
        Args:
            service_name: 서비스 이름
            intensity: 셔플 강도 (0-1)
                - < 0.3: 포트만 변경
                - 0.3-0.7: IP + 포트 변경
                - > 0.7: 완전 새로운 매핑
            change_ip: IP 변경 여부
            change_port: 포트 변경 여부
        
        Returns:
            성공 여부
        """
        with self._lock:
            if service_name not in self.service_mappings:
                logger.warning(f"Unknown service: {service_name}")
                return False
            
            mapping = self.service_mappings[service_name]
            old_vip = mapping.virtual_ip
            old_vport = mapping.virtual_port
            
            # intensity에 따라 변경 범위 결정
            do_change_ip = change_ip and intensity >= 0.3
            do_change_port = change_port and intensity >= 0.1
            
            # 새 IP/Port 할당
            new_vip = self._allocate_virtual_ip() if do_change_ip else old_vip
            new_vport = self._allocate_virtual_port() if do_change_port else old_vport
            
            # 기존 규칙 삭제
            if old_vip != mapping.real_ip or old_vport != mapping.real_port:
                self._run_iptables(
                    f"-D PREROUTING -d {old_vip} -p {mapping.protocol} "
                    f"--dport {old_vport} -j DNAT "
                    f"--to-destination {mapping.real_ip}:{mapping.real_port}"
                )
            
            # 새 규칙 추가
            if new_vip != mapping.real_ip or new_vport != mapping.real_port:
                ok, err = self._run_iptables(
                    f"-A PREROUTING -d {new_vip} -p {mapping.protocol} "
                    f"--dport {new_vport} -j DNAT "
                    f"--to-destination {mapping.real_ip}:{mapping.real_port}"
                )
                
                if not ok:
                    logger.error(f"Failed to add DNAT rule: {err}")
                    return False
            
            # 이전 IP/Port 해제
            if do_change_ip:
                self._release_virtual_ip(old_vip)
            if do_change_port:
                self._release_virtual_port(old_vport)
            
            # 매핑 업데이트
            mapping.virtual_ip = new_vip
            mapping.virtual_port = new_vport
            mapping.shuffle_count += 1
            
            # 통계 업데이트
            self.stats.total_shuffles += 1
            self.stats.total_cost += self.COST_WEIGHTS["shuffle"] * intensity
            self.stats.last_action_time = time.time()
            
            logger.info(
                f"[SHUFFLE] {service_name}: {old_vip}:{old_vport} → "
                f"{new_vip}:{new_vport} (intensity={intensity:.2f})"
            )
            
            self._log_action("shuffle", {
                "service": service_name,
                "old_ip": old_vip,
                "old_port": old_vport,
                "new_ip": new_vip,
                "new_port": new_vport,
                "intensity": intensity,
            })
            
            self._save_state()
            return True
    
    def shuffle_all_services(self, intensity: float = 0.5) -> int:
        """모든 서비스 셔플"""
        success_count = 0
        for svc_name in self.service_mappings:
            if self.shuffle_network(svc_name, intensity):
                success_count += 1
        return success_count
    
    # =========================================================================
    # MTD 액션: Port Hop
    # =========================================================================
    
    def port_hop(self, service_name: str, intensity: float = 0.5) -> bool:
        """
        포트 호핑: 포트만 변경
        
        Args:
            service_name: 서비스 이름
            intensity: 호핑 강도
        """
        return self.shuffle_network(
            service_name,
            intensity=intensity,
            change_ip=False,
            change_port=True,
        )
    
    # =========================================================================
    # [NEW] MTD 액션: Service Swap
    # =========================================================================
    
    def service_swap(
        self,
        service_a: str,
        service_b: str,
        intensity: float = 0.5,
        duration_sec: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, float]]:
        """
        [NEW] 서비스 스왑: 두 서비스의 가상 주소를 교환
        
        이 기능은 공격자의 belief를 무효화하고 혼란을 유발합니다.
        공격자가 서비스 A를 발견했다고 생각해도, 실제로는 서비스 B로 
        연결되어 예상과 다른 결과를 얻게 됩니다.
        
        References:
        - Container Live Migration: 10-100ms downtime (IEEE ETFA 2018)
        - MiGrror: <10ms downtime with pre-copy (arXiv:2305.10977)
        - SDN MTD: <7% overhead (ScienceDirect Topics)
        
        Args:
            service_a: 첫 번째 서비스 이름
            service_b: 두 번째 서비스 이름
            intensity: 스왑 강도 (0-1, 높을수록 완전한 스왑)
            duration_sec: 스왑 지속 시간 (None이면 영구)
        
        Returns:
            (성공 여부, 비용 정보 딕셔너리)
        """
        with self._lock:
            cost_info = {
                "latency_ms": 0.0,
                "bandwidth_overhead": 0.0,
                "connection_resets": 0,
                "energy": 0.0,
                "availability_loss": 0.0,
                "total": 0.0,
            }
            
            # 서비스 존재 확인
            if service_a not in self.service_mappings:
                logger.warning(f"Unknown service: {service_a}")
                return False, cost_info
            
            if service_b not in self.service_mappings:
                logger.warning(f"Unknown service: {service_b}")
                return False, cost_info
            
            mapping_a = self.service_mappings[service_a]
            mapping_b = self.service_mappings[service_b]
            
            # 프로토콜 호환성 확인
            if mapping_a.protocol != mapping_b.protocol:
                logger.warning(
                    f"Protocol mismatch: {service_a}({mapping_a.protocol}) vs "
                    f"{service_b}({mapping_b.protocol})"
                )
                return False, cost_info
            
            # 스왑 가능 여부 확인
            swappable = self.services_config.get(service_a, {}).get("swappable_with", [])
            if service_b not in swappable and not self.dry_run:
                logger.warning(f"{service_a} cannot swap with {service_b}")
                # dry_run에서는 테스트 목적으로 허용
            
            # 비용 계산 (레퍼런스 기반)
            scm = self.swap_cost_model
            
            # 기본 레이턴시
            base_latency = scm.swap_latency_ms * intensity
            sync_latency = scm.swap_sync_time_ms * intensity
            total_latency = base_latency + sync_latency
            
            # 대역폭 오버헤드
            bandwidth = scm.swap_bandwidth_overhead * intensity
            
            # 연결 리셋 시뮬레이션 (Reference: 15% connection reset prob)
            connection_resets = 0
            if random.random() < scm.swap_connection_reset_prob * intensity:
                connection_resets = random.randint(1, 5)
            
            # 에너지 소모
            energy = scm.swap_energy_joule * intensity
            
            # 가용성 영향
            availability_loss = scm.swap_availability_impact * intensity
            
            # 총 비용
            total_cost = (
                total_latency / 1000 +  # ms → s
                bandwidth +
                connection_resets * 0.05 +
                energy +
                availability_loss * 2.0
            )
            
            cost_info = {
                "latency_ms": total_latency,
                "sync_latency_ms": sync_latency,
                "bandwidth_overhead": bandwidth,
                "connection_resets": connection_resets,
                "energy": energy,
                "availability_loss": availability_loss,
                "total": total_cost,
            }
            
            # 이전 가상 주소 저장
            old_vip_a, old_vport_a = mapping_a.virtual_ip, mapping_a.virtual_port
            old_vip_b, old_vport_b = mapping_b.virtual_ip, mapping_b.virtual_port
            
            # 기존 규칙 삭제
            if old_vip_a != mapping_a.real_ip or old_vport_a != mapping_a.real_port:
                self._run_iptables(
                    f"-D PREROUTING -d {old_vip_a} -p {mapping_a.protocol} "
                    f"--dport {old_vport_a} -j DNAT "
                    f"--to-destination {mapping_a.real_ip}:{mapping_a.real_port}"
                )
            
            if old_vip_b != mapping_b.real_ip or old_vport_b != mapping_b.real_port:
                self._run_iptables(
                    f"-D PREROUTING -d {old_vip_b} -p {mapping_b.protocol} "
                    f"--dport {old_vport_b} -j DNAT "
                    f"--to-destination {mapping_b.real_ip}:{mapping_b.real_port}"
                )
            
            # 가상 주소 교환
            mapping_a.virtual_ip = old_vip_b
            mapping_a.virtual_port = old_vport_b
            mapping_b.virtual_ip = old_vip_a
            mapping_b.virtual_port = old_vport_a
            
            # 새 규칙 추가 (교환된 가상 주소로)
            # A의 가상 주소(이전 B) → A의 실제 주소
            if mapping_a.virtual_ip != mapping_a.real_ip or mapping_a.virtual_port != mapping_a.real_port:
                self._run_iptables(
                    f"-A PREROUTING -d {mapping_a.virtual_ip} -p {mapping_a.protocol} "
                    f"--dport {mapping_a.virtual_port} -j DNAT "
                    f"--to-destination {mapping_a.real_ip}:{mapping_a.real_port}"
                )
            
            # B의 가상 주소(이전 A) → B의 실제 주소
            if mapping_b.virtual_ip != mapping_b.real_ip or mapping_b.virtual_port != mapping_b.real_port:
                self._run_iptables(
                    f"-A PREROUTING -d {mapping_b.virtual_ip} -p {mapping_b.protocol} "
                    f"--dport {mapping_b.virtual_port} -j DNAT "
                    f"--to-destination {mapping_b.real_ip}:{mapping_b.real_port}"
                )
            
            # 스왑 기록 업데이트
            mapping_a.swap_count += 1
            mapping_a.last_swap_step = self.current_step
            mapping_a.swapped_with = service_b
            
            mapping_b.swap_count += 1
            mapping_b.last_swap_step = self.current_step
            mapping_b.swapped_with = service_a
            
            # 스왑 레코드 생성
            swap_id = f"swap_{service_a}_{service_b}_{int(time.time())}"
            swap_record = ServiceSwapRecord(
                swap_id=swap_id,
                service_a=service_a,
                service_b=service_b,
                swap_time=time.time(),
                intensity=intensity,
                latency_ms=total_latency,
                connection_resets=connection_resets,
                active=True,
                expires_at=time.time() + duration_sec if duration_sec else None,
            )
            
            self.active_swaps[swap_id] = swap_record
            self.swap_history.append(swap_record)
            
            # 통계 업데이트
            self.stats.total_service_swaps += 1
            self.stats.total_swap_connection_resets += connection_resets
            self.stats.total_swap_latency_ms += total_latency
            self.stats.total_cost += self.COST_WEIGHTS["service_swap"] * intensity
            self.stats.last_swap_time = time.time()
            self.stats.last_action_time = time.time()
            
            logger.info(
                f"[SERVICE_SWAP] {service_a} ↔ {service_b}: "
                f"({old_vip_a}:{old_vport_a}) ↔ ({old_vip_b}:{old_vport_b}) "
                f"(intensity={intensity:.2f}, latency={total_latency:.1f}ms, "
                f"resets={connection_resets})"
            )
            
            self._log_action("service_swap", {
                "service_a": service_a,
                "service_b": service_b,
                "old_a_addr": f"{old_vip_a}:{old_vport_a}",
                "old_b_addr": f"{old_vip_b}:{old_vport_b}",
                "new_a_addr": f"{mapping_a.virtual_ip}:{mapping_a.virtual_port}",
                "new_b_addr": f"{mapping_b.virtual_ip}:{mapping_b.virtual_port}",
                "intensity": intensity,
                "cost": cost_info,
            })
            
            self._save_state()
            return True, cost_info
    
    def swap_with_decoy(
        self,
        service_name: str,
        intensity: float = 0.5,
    ) -> Tuple[bool, Dict[str, float]]:
        """
        [NEW] 서비스와 해당 디코이 간 스왑
        
        실제 서비스를 디코이 위치로, 디코이를 실제 서비스 위치로 이동
        
        Args:
            service_name: 실제 서비스 이름
            intensity: 스왑 강도
        
        Returns:
            (성공 여부, 비용 정보)
        """
        # 해당 서비스의 디코이 찾기
        swappable = self.services_config.get(service_name, {}).get("swappable_with", [])
        decoy_service = None
        
        for svc in swappable:
            if self.services_config.get(svc, {}).get("is_decoy", False):
                decoy_service = svc
                break
        
        if not decoy_service:
            logger.warning(f"No decoy found for service: {service_name}")
            return False, {"total": 0.0}
        
        return self.service_swap(service_name, decoy_service, intensity)
    
    def revert_swap(self, swap_id: str) -> bool:
        """
        [NEW] 서비스 스왑 되돌리기
        
        Args:
            swap_id: 스왑 레코드 ID
        
        Returns:
            성공 여부
        """
        with self._lock:
            if swap_id not in self.active_swaps:
                logger.warning(f"Swap not found or already reverted: {swap_id}")
                return False
            
            swap_record = self.active_swaps[swap_id]
            if not swap_record.active:
                return False
            
            # 다시 스왑하여 원래대로 복구
            success, _ = self.service_swap(
                swap_record.service_a,
                swap_record.service_b,
                intensity=0.3,  # 복구는 낮은 intensity로
            )
            
            if success:
                swap_record.active = False
                del self.active_swaps[swap_id]
                
                # 스왑 상태 초기화
                if swap_record.service_a in self.service_mappings:
                    self.service_mappings[swap_record.service_a].swapped_with = None
                if swap_record.service_b in self.service_mappings:
                    self.service_mappings[swap_record.service_b].swapped_with = None
                
                logger.info(f"[SWAP_REVERTED] {swap_id}")
            
            return success
    
    def cleanup_expired_swaps(self) -> int:
        """[NEW] 만료된 스왑 정리"""
        with self._lock:
            now = time.time()
            expired = [
                swap_id for swap_id, record in self.active_swaps.items()
                if record.expires_at and record.expires_at < now
            ]
            
            reverted_count = 0
            for swap_id in expired:
                if self.revert_swap(swap_id):
                    reverted_count += 1
            
            return reverted_count
    
    def get_swap_protection_factor(self, service_name: str) -> float:
        """
        [NEW] 서비스의 현재 스왑 보호 효과 반환
        
        스왑 직후에는 공격자의 익스플로잇 성공률이 감소합니다.
        
        Args:
            service_name: 서비스 이름
        
        Returns:
            보호 계수 (0-1, 높을수록 보호 효과 큼)
        """
        if service_name not in self.service_mappings:
            return 0.0
        
        mapping = self.service_mappings[service_name]
        steps_since_swap = self.current_step - mapping.last_swap_step
        
        if steps_since_swap >= self.swap_cost_model.protection_duration_steps:
            return 0.0
        
        # 선형 감소하는 보호 효과
        protection = self.swap_cost_model.exploit_protection_factor * (
            1.0 - steps_since_swap / self.swap_cost_model.protection_duration_steps
        )
        
        return max(0.0, protection)
    
    def get_confusion_level(self) -> float:
        """
        [NEW] 현재 전체 혼란도 반환
        
        활성 스왑이 많을수록, 최근 스왑이 많을수록 혼란도 증가
        
        Returns:
            혼란도 (0-1)
        """
        if not self.active_swaps:
            return 0.0
        
        now = time.time()
        confusion = 0.0
        
        for swap_record in self.active_swaps.values():
            if swap_record.active:
                # 최근 스왑일수록 혼란도 높음
                age = now - swap_record.swap_time
                decay = max(0, 1.0 - age / 300)  # 5분에 걸쳐 감소
                confusion += swap_record.intensity * decay * 0.3
        
        return min(1.0, confusion)
    
    # =========================================================================
    # MTD 액션: Decoy Activation
    # =========================================================================
    
    def activate_decoy(
        self,
        target_service: str,
        decoy_count: int = 1,
    ) -> List[str]:
        """
        디코이 활성화: 가짜 서비스 생성
        
        Args:
            target_service: 모방할 서비스
            decoy_count: 생성할 디코이 수
        
        Returns:
            생성된 디코이 ID 목록
        """
        with self._lock:
            created_decoys = []
            
            for _ in range(decoy_count):
                # 디코이 IP/Port 할당
                decoy_suffix = random.randint(DECOY_IP_START, DECOY_IP_END)
                decoy_ip = f"{self.network_prefix}.{decoy_suffix}"
                decoy_port = random.randint(PORT_POOL_START, PORT_POOL_END)
                
                # 디코이 ID 생성
                decoy_id = f"decoy_{target_service}_{len(self.decoys)}"
                
                # 프로토콜 결정
                protocol = "tcp"
                if target_service in self.services_config:
                    protocol = self.services_config[target_service].get("protocol", "tcp")
                
                # iptables 규칙: 디코이 IP로 오는 트래픽을 honeypot으로 리다이렉트
                ok, _ = self._run_iptables(
                    f"-A PREROUTING -d {decoy_ip} -p {protocol} --dport {decoy_port} "
                    f"-j REDIRECT --to-port {HONEYPOT_PORT}"
                )
                
                if ok:
                    decoy = DecoyService(
                        decoy_id=decoy_id,
                        target_service=target_service,
                        decoy_ip=decoy_ip,
                        decoy_port=decoy_port,
                        protocol=protocol,
                    )
                    self.decoys[decoy_id] = decoy
                    created_decoys.append(decoy_id)
                    
                    self.stats.total_decoy_activations += 1
                    self.stats.total_cost += self.COST_WEIGHTS["decoy"]
                    
                    logger.info(
                        f"[DECOY] Activated {decoy_id} at {decoy_ip}:{decoy_port} "
                        f"(mimicking {target_service})"
                    )
            
            self.stats.last_action_time = time.time()
            self._save_state()
            
            return created_decoys
    
    def deactivate_decoy(self, decoy_id: str) -> bool:
        """디코이 비활성화"""
        with self._lock:
            if decoy_id not in self.decoys:
                return False
            
            decoy = self.decoys[decoy_id]
            
            # iptables 규칙 삭제
            self._run_iptables(
                f"-D PREROUTING -d {decoy.decoy_ip} -p {decoy.protocol} "
                f"--dport {decoy.decoy_port} -j REDIRECT --to-port {HONEYPOT_PORT}"
            )
            
            del self.decoys[decoy_id]
            logger.info(f"[DECOY] Deactivated {decoy_id}")
            
            self._save_state()
            return True
    
    def record_decoy_hit(self, decoy_id: str):
        """디코이 히트 기록"""
        with self._lock:
            if decoy_id in self.decoys:
                self.decoys[decoy_id].hits += 1
                self.decoys[decoy_id].last_hit = time.time()
                self.stats.total_decoy_hits += 1
                
                logger.info(f"[DECOY HIT] {decoy_id} (total: {self.decoys[decoy_id].hits})")
    
    # =========================================================================
    # MTD 액션: Blacklist
    # =========================================================================
    
    def add_to_blacklist(
        self,
        ip: str,
        duration_sec: float = 300,
        reason: str = "suspicious_activity",
    ) -> bool:
        """
        IP를 블랙리스트에 추가
        
        Args:
            ip: 차단할 IP
            duration_sec: 차단 기간 (초)
            reason: 차단 사유
        """
        with self._lock:
            # 이미 블랙리스트에 있으면 기간 연장
            if ip in self.blacklist:
                self.blacklist[ip].expires_at = time.time() + duration_sec
                logger.info(f"[BLACKLIST] Extended {ip} for {duration_sec}s")
                return True
            
            # iptables 규칙 추가
            ok, _ = self._run_iptables(
                f"-A INPUT -s {ip} -j DROP",
                table="filter"
            )
            
            if ok:
                self.blacklist[ip] = BlacklistEntry(
                    ip=ip,
                    reason=reason,
                    created_at=time.time(),
                    expires_at=time.time() + duration_sec,
                )
                
                self.stats.total_blacklist_adds += 1
                self.stats.total_cost += self.COST_WEIGHTS["blacklist"]
                self.stats.last_action_time = time.time()
                
                logger.info(f"[BLACKLIST] Added {ip} for {duration_sec}s (reason: {reason})")
                
                self._log_action("blacklist_add", {
                    "ip": ip,
                    "duration": duration_sec,
                    "reason": reason,
                })
                
                self._save_state()
                return True
            
            return False
    
    def remove_from_blacklist(self, ip: str) -> bool:
        """블랙리스트에서 제거"""
        with self._lock:
            if ip not in self.blacklist:
                return False
            
            self._run_iptables(f"-D INPUT -s {ip} -j DROP", table="filter")
            del self.blacklist[ip]
            
            logger.info(f"[BLACKLIST] Removed {ip}")
            self._save_state()
            return True
    
    def cleanup_expired_blacklist(self) -> int:
        """만료된 블랙리스트 항목 정리"""
        with self._lock:
            now = time.time()
            expired = [ip for ip, entry in self.blacklist.items() if entry.expires_at < now]
            
            for ip in expired:
                self.remove_from_blacklist(ip)
            
            return len(expired)
    
    # =========================================================================
    # MTD 액션: Rate Limiting
    # =========================================================================
    
    def apply_rate_limit(
        self,
        service_name: str,
        limit_rate: str = "10/second",
        burst: int = 20,
    ) -> bool:
        """
        Rate Limiting 적용
        
        Args:
            service_name: 서비스 이름
            limit_rate: 제한율 (예: "10/second")
            burst: 버스트 허용량
        """
        with self._lock:
            if service_name not in self.service_mappings:
                return False
            
            mapping = self.service_mappings[service_name]
            
            # hashlimit 규칙 추가
            ok, _ = self._run_iptables(
                f"-A INPUT -d {mapping.virtual_ip} -p {mapping.protocol} "
                f"--dport {mapping.virtual_port} "
                f"-m hashlimit --hashlimit-above {limit_rate} --hashlimit-burst {burst} "
                f"--hashlimit-mode srcip --hashlimit-name {service_name}_limit "
                f"-j DROP",
                table="filter"
            )
            
            if ok:
                self.stats.total_cost += self.COST_WEIGHTS["rate_limit"]
                logger.info(f"[RATE LIMIT] {service_name}: {limit_rate}, burst={burst}")
            
            return ok
    
    # =========================================================================
    # 상태 조회
    # =========================================================================
    
    def get_current_mapping(self, service_name: str) -> Optional[Dict]:
        """현재 서비스 매핑 조회"""
        if service_name not in self.service_mappings:
            return None
        return asdict(self.service_mappings[service_name])
    
    def get_all_mappings(self) -> Dict[str, Dict]:
        """모든 서비스 매핑 조회"""
        return {k: asdict(v) for k, v in self.service_mappings.items()}
    
    def get_statistics(self) -> Dict:
        """MTD 통계 조회"""
        stats_dict = self.stats.to_dict()
        stats_dict["active_decoys"] = len(self.decoys)
        stats_dict["blacklist_size"] = len(self.blacklist)
        stats_dict["active_swaps"] = len(self.active_swaps)
        stats_dict["confusion_level"] = self.get_confusion_level()
        stats_dict["uptime"] = time.time() - self.stats.start_time
        return stats_dict
    
    def get_diversity_score(self) -> float:
        """
        현재 다양성 점수 계산
        
        - 실제 IP와 다른 가상 IP 비율
        - 실제 Port와 다른 가상 Port 비율
        - [NEW] 스왑된 서비스 비율 추가 반영
        """
        if not self.service_mappings:
            return 0.0
        
        different_count = 0
        swapped_count = 0
        total = len(self.service_mappings)
        
        for mapping in self.service_mappings.values():
            if (mapping.virtual_ip != mapping.real_ip or 
                mapping.virtual_port != mapping.real_port):
                different_count += 1
            if mapping.swapped_with:
                swapped_count += 1
        
        # 기본 다양성 + 스왑 보너스
        base_diversity = different_count / total
        swap_bonus = (swapped_count / total) * 0.2  # 스왑은 추가 20% 보너스
        
        return min(1.0, base_diversity + swap_bonus)
    
    def get_redundancy_score(self) -> float:
        """[NEW] 중복성 점수 계산 (디코이 + 스왑)"""
        if not self.service_mappings:
            return 0.0
        
        active_decoys = len(self.decoys)
        active_swaps = len(self.active_swaps)
        
        # 디코이와 활성 스왑의 조합으로 중복성 계산
        redundancy = min(1.0, (active_decoys * 0.15 + active_swaps * 0.25))
        
        return redundancy
    
    # =========================================================================
    # mtd_state.json 호환 인터페이스
    # =========================================================================
    
    def get_mtd_state_for_attacker(self) -> Dict:
        """
        공격자(Seeker)가 사용할 MTD 상태 JSON 생성
        
        attack_orchestrator.py의 resolve_targets()가 읽는 형식
        """
        # 현재 타겟 (공격자 관점에서 보이는 주소)
        primary_service = "cc_sitl"
        if primary_service in self.service_mappings:
            mapping = self.service_mappings[primary_service]
            current_target = f"{mapping.virtual_ip}:{mapping.virtual_port}"
        else:
            current_target = "10.13.0.3:5760"
        
        return {
            "current_target": current_target,
            "mtd_active": self.get_diversity_score() > 0,
            "diversity_score": self.get_diversity_score(),
            "redundancy_score": self.get_redundancy_score(),
            "confusion_level": self.get_confusion_level(),
            "decoy_count": len(self.decoys),
            "blacklist_count": len(self.blacklist),
            "active_swap_count": len(self.active_swaps),
            "last_shuffle_time": self.stats.last_action_time,
            "last_swap_time": self.stats.last_swap_time,
        }
    
    def save_mtd_state_json(self, filepath: str):
        """mtd_state.json 파일로 저장"""
        state = self.get_mtd_state_for_attacker()
        state["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
    
    # =========================================================================
    # 정리
    # =========================================================================
    
    def cleanup(self):
        """모든 MTD 규칙 정리"""
        logger.info("Cleaning up all MTD rules...")
        
        # 활성 스왑 정리
        for swap_id in list(self.active_swaps.keys()):
            self.revert_swap(swap_id)
        
        # 디코이 정리
        for decoy_id in list(self.decoys.keys()):
            self.deactivate_decoy(decoy_id)
        
        # 블랙리스트 정리
        for ip in list(self.blacklist.keys()):
            self.remove_from_blacklist(ip)
        
        # 서비스 매핑 초기화
        for svc_name, mapping in self.service_mappings.items():
            if mapping.virtual_ip != mapping.real_ip or mapping.virtual_port != mapping.real_port:
                # 기존 규칙 삭제
                self._run_iptables(
                    f"-D PREROUTING -d {mapping.virtual_ip} -p {mapping.protocol} "
                    f"--dport {mapping.virtual_port} -j DNAT "
                    f"--to-destination {mapping.real_ip}:{mapping.real_port}"
                )
                
                # 원래 값으로 복원
                mapping.virtual_ip = mapping.real_ip
                mapping.virtual_port = mapping.real_port
            
            # 스왑 상태 초기화
            mapping.swapped_with = None
        
        self._save_state()
        logger.info("Cleanup completed")


# =============================================================================
# 메인 (테스트용)
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="iptables MTD Controller v08")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="실제 iptables 변경 없이 테스트")
    parser.add_argument("--test", action="store_true", help="테스트 실행")
    parser.add_argument("--test-swap", action="store_true", help="서비스 스왑 테스트")
    args = parser.parse_args()
    
    controller = IptablesMTDController(dry_run=args.dry_run)
    
    if args.test or args.test_swap:
        print("\n=== Testing MTD Controller v08 (with Service Swap) ===\n")
        
        # 1. 셔플 테스트
        print("1. Testing shuffle...")
        controller.shuffle_network("fc_mavlink", intensity=0.7)
        controller.shuffle_network("cc_sitl", intensity=0.5)
        
        # 2. 디코이 테스트
        print("\n2. Testing decoy...")
        decoys = controller.activate_decoy("fc_mavlink", decoy_count=2)
        print(f"   Created decoys: {decoys}")
        
        # 3. 블랙리스트 테스트
        print("\n3. Testing blacklist...")
        controller.add_to_blacklist("192.168.1.100", duration_sec=60)
        
        # 4. [NEW] 서비스 스왑 테스트
        if args.test_swap:
            print("\n4. Testing service swap...")
            
            # 현재 매핑 확인
            print("   Before swap:")
            print(f"   fc_mavlink: {controller.get_current_mapping('fc_mavlink')}")
            print(f"   decoy_fc_mavlink: {controller.get_current_mapping('decoy_fc_mavlink')}")
            
            # 서비스 스왑 실행
            success, cost = controller.service_swap(
                "fc_mavlink", 
                "decoy_fc_mavlink", 
                intensity=0.7
            )
            print(f"\n   Swap result: success={success}")
            print(f"   Swap cost: {json.dumps(cost, indent=6)}")
            
            # 스왑 후 매핑 확인
            print("\n   After swap:")
            print(f"   fc_mavlink: {controller.get_current_mapping('fc_mavlink')}")
            print(f"   decoy_fc_mavlink: {controller.get_current_mapping('decoy_fc_mavlink')}")
            
            # 보호 효과 확인
            controller.set_step(1)
            protection = controller.get_swap_protection_factor("fc_mavlink")
            print(f"\n   Protection factor (step 1): {protection:.3f}")
            
            controller.set_step(5)
            protection = controller.get_swap_protection_factor("fc_mavlink")
            print(f"   Protection factor (step 5): {protection:.3f}")
            
            # 혼란도 확인
            confusion = controller.get_confusion_level()
            print(f"\n   Confusion level: {confusion:.3f}")
        
        # 5. 상태 출력
        print("\n5. Current state:")
        print(f"   Mappings: {json.dumps(controller.get_all_mappings(), indent=2)}")
        print(f"   Stats: {json.dumps(controller.get_statistics(), indent=2)}")
        print(f"   Diversity: {controller.get_diversity_score():.2f}")
        print(f"   Redundancy: {controller.get_redundancy_score():.2f}")
        
        # 6. mtd_state.json 형식
        print("\n6. MTD State (for attacker):")
        print(json.dumps(controller.get_mtd_state_for_attacker(), indent=2))
        
        # 7. 정리
        print("\n7. Cleanup...")
        controller.cleanup()
        
        print("\n=== Test Complete ===")