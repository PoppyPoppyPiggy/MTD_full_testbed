#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iptables MTD Controller v08.4 - JSON Serialization 오류 해결
==========================================================

실제 테스트베드에서 iptables를 제어하여 MTD를 구현하는 컨트롤러.

v08.3 → v08.4 주요 수정:
- JSON serialization 오류 해결 (numpy float32 타입 지원)
- 안전한 JSON 직렬화 함수 추가
- RL 환경과의 호환성 개선

기능:
1. IP/Port Shuffling (DNAT/SNAT)
2. Decoy Activation (Honeypot 리다이렉션)
3. Blacklist (공격 IP 차단)
4. Service Swap (서비스 매핑 변경)
5. Rate Limiting (트래픽 제한)

환경:
- Docker 네트워크: 10.13.0.0/24 (simulator)
- 서비스: FC(10.13.0.2), CC(10.13.0.3), GCS(10.13.0.4), SIM(10.13.0.5)

작성자: MTD-RL Research Team
버전: 0.8.4 (JSON Fix)
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
import random
import threading

# NumPy 타입 처리
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [MTD-Controller] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("IptablesMTDController")


# =============================================================================
# JSON 직렬화 안전 함수
# =============================================================================
def make_json_safe(obj: Any) -> Any:
    """JSON 직렬화를 위해 numpy 타입을 Python 기본 타입으로 변환"""
    if NUMPY_AVAILABLE:
        if isinstance(obj, (np.integer)):
            return int(obj)  # numpy int → Python int
        elif isinstance(obj, (np.floating)):
            return float(obj)  # numpy float → Python float
        elif isinstance(obj, np.ndarray):
            return obj.tolist()  # numpy array → Python list
        elif isinstance(obj, (np.bool_)):
            return bool(obj)  # numpy bool → Python bool
    
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    elif hasattr(obj, '__dataclass_fields__'):
        # dataclass의 경우
        return make_json_safe(asdict(obj))
    elif hasattr(obj, '__dict__') and not isinstance(obj, (str, int, float, bool)):
        # 일반 객체의 경우 (기본 타입 제외)
        return make_json_safe(obj.__dict__)
    else:
        return obj


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """안전한 JSON 직렬화"""
    try:
        safe_obj = make_json_safe(obj)
        return json.dumps(safe_obj, **kwargs)
    except (TypeError, ValueError) as e:
        logger.warning(f"JSON serialization fallback: {e}")
        # 최후의 수단: 문자열 변환
        safe_obj = make_json_safe_fallback(obj)
        return json.dumps(safe_obj, **kwargs)


def make_json_safe_fallback(obj: Any) -> Any:
    """Fallback JSON 안전화 - 모든 값을 문자열로 변환"""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, dict):
        return {str(k): make_json_safe_fallback(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe_fallback(item) for item in obj]
    else:
        return str(obj)


# =============================================================================
# 설정 상수
# =============================================================================
NETWORK_PREFIX = "10.13.0"
DOCKER_BRIDGE = "br-simulator"

DEFAULT_SERVICES = {
    "fc_mavlink": {
        "name": "Flight Controller MAVLink",
        "real_ip": "10.13.0.2",
        "real_port": 14550,
        "protocol": "udp",
        "container": "flight-controller-lite",
        "priority": 1,
        "swappable_with": ["decoy_fc_mavlink"],
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

VIP_POOL_START = 100
VIP_POOL_END = 199
PORT_POOL_START = 10000
PORT_POOL_END = 59999

DECOY_IP_START = 200
DECOY_IP_END = 249
HONEYPOT_PORT = 9999


# =============================================================================
# Service Swap Cost Model
# =============================================================================
@dataclass
class ServiceSwapCostModel:
    """서비스 스왑 비용 모델 - 레퍼런스 기반 파라미터"""
    swap_latency_ms: float = 75.0
    swap_sync_time_ms: float = 25.0
    swap_bandwidth_overhead: float = 0.05
    swap_connection_reset_prob: float = 0.15
    connection_recovery_ms: float = 500.0
    swap_cpu_overhead: float = 0.08
    swap_memory_overhead_mb: float = 64.0
    swap_energy_joule: float = 0.12
    swap_availability_impact: float = 0.02
    confusion_duration_steps: int = 20
    belief_invalidation_factor: float = 0.3
    exploit_protection_factor: float = 0.25
    protection_duration_steps: int = 10


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
    swap_count: int = 0
    last_swap_step: int = 0
    original_role: Optional[str] = None
    swapped_with: Optional[str] = None


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
    """서비스 스왑 기록"""
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
    total_shuffles: int = 0
    total_port_hops: int = 0
    total_decoy_activations: int = 0
    total_decoy_hits: int = 0
    total_blacklist_adds: int = 0
    total_blacklist_blocks: int = 0
    total_service_swaps: int = 0
    total_swap_confusion_caused: float = 0.0
    total_swap_connection_resets: int = 0
    total_swap_latency_ms: float = 0.0
    total_cost: float = 0.0
    start_time: float = field(default_factory=time.time)
    last_action_time: Optional[float] = None
    last_swap_time: Optional[float] = None

    def to_dict(self) -> Dict:
        return make_json_safe(asdict(self))


# =============================================================================
# iptables MTD Controller
# =============================================================================
class IptablesMTDController:
    """iptables 기반 MTD 컨트롤러 (JSON 직렬화 안전 버전)"""

    COST_WEIGHTS = {
        "shuffle": 0.3,
        "port_hop": 0.2,
        "decoy": 0.15,
        "blacklist": 0.1,
        "rate_limit": 0.05,
        "service_swap": 0.4,
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
        self.dry_run = dry_run
        self.network_prefix = network_prefix
        self.services_config = services or DEFAULT_SERVICES

        self.service_mappings: Dict[str, ServiceMapping] = {}
        self.decoys: Dict[str, DecoyService] = {}
        self.blacklist: Dict[str, BlacklistEntry] = {}
        self.used_virtual_ips: Set[str] = set()
        self.used_virtual_ports: Set[int] = set()

        self.active_swaps: Dict[str, ServiceSwapRecord] = {}
        self.swap_history: List[ServiceSwapRecord] = []
        self.swap_cost_model = swap_cost_model or ServiceSwapCostModel()
        self.current_step: int = 0

        self.stats = MTDStatistics()

        self.state_file = Path(state_file) if state_file else None
        self.log_file = Path(log_file) if log_file else None

        self._lock = threading.RLock()

        self._initialize_services()

        if self.state_file and self.state_file.exists():
            self._load_state()

        logger.info(
            f"IptablesMTDController v08.4 initialized "
            f"(dry_run={dry_run}, services={len(self.services_config)})"
        )

    def _initialize_services(self):
        """서비스 초기 매핑 설정"""
        for svc_name, svc_config in self.services_config.items():
            self.service_mappings[svc_name] = ServiceMapping(
                service_name=svc_name,
                real_ip=svc_config["real_ip"],
                real_port=svc_config["real_port"],
                virtual_ip=svc_config["real_ip"],
                virtual_port=svc_config["real_port"],
                protocol=svc_config["protocol"],
                is_decoy=svc_config.get("is_decoy", False),
                original_role=svc_name,
            )

    def _save_state(self):
        """현재 상태 파일로 저장 (JSON 안전)"""
        if not self.state_file:
            return

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mappings": {k: make_json_safe(asdict(v)) for k, v in self.service_mappings.items()},
            "decoys": {k: make_json_safe(asdict(v)) for k, v in self.decoys.items()},
            "blacklist": {k: make_json_safe(asdict(v)) for k, v in self.blacklist.items()},
            "active_swaps": {k: make_json_safe(asdict(v)) for k, v in self.active_swaps.items()},
            "stats": self.stats.to_dict(),
        }

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(make_json_safe(state), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        """저장된 상태 로드"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)

            for svc_name, mapping_dict in state.get("mappings", {}).items():
                if svc_name in self.service_mappings:
                    for key, value in mapping_dict.items():
                        if hasattr(self.service_mappings[svc_name], key):
                            setattr(self.service_mappings[svc_name], key, value)

            logger.info(f"State loaded from {self.state_file}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")

    def _log_action(self, action_type: str, details: Dict):
        """MTD 액션 로깅 (JSON 안전)"""
        if not self.log_file:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "details": make_json_safe(details),
        }

        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, 'a') as f:
                f.write(safe_json_dumps(entry) + '\n')
        except Exception as e:
            logger.warning(f"Failed to log action: {e}")

    def set_step(self, step: int):
        """현재 스텝 설정"""
        self.current_step = step

    def _run_iptables(self, cmd: str, table: str = "nat") -> Tuple[bool, str]:
        """iptables 명령 실행"""
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

    def _allocate_virtual_ip(self) -> str:
        """새로운 Virtual IP 할당"""
        with self._lock:
            for suffix in range(VIP_POOL_START, VIP_POOL_END + 1):
                vip = f"{self.network_prefix}.{suffix}"
                if vip not in self.used_virtual_ips:
                    self.used_virtual_ips.add(vip)
                    return vip

        suffix = random.randint(VIP_POOL_START, VIP_POOL_END)
        return f"{self.network_prefix}.{suffix}"

    def _allocate_virtual_port(self) -> int:
        """새로운 Virtual Port 할당"""
        with self._lock:
            for _ in range(100):
                port = random.randint(PORT_POOL_START, PORT_POOL_END)
                if port not in self.used_virtual_ports:
                    self.used_virtual_ports.add(port)
                    return port

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
    # MTD 액션: Network Shuffle (RL 인터페이스 호환)
    # =========================================================================
    def shuffle(self, intensity: Union[float, int, Any] = 0.5) -> float:
        """모든 서비스 셔플 (RL 인터페이스 호환)"""
        # numpy 타입 안전 변환
        intensity = float(make_json_safe(intensity))
        
        if intensity < 0.1:  # 너무 낮은 강도는 무시
            return 0.0
        
        success_count = 0
        for svc_name in self.service_mappings:
            if self.shuffle_network(svc_name, intensity):
                success_count += 1
        
        return self.COST_WEIGHTS["shuffle"] * intensity

    def port_hop(self, intensity: Union[float, int, Any] = 0.5) -> float:
        """모든 서비스 포트 호핑 (RL 인터페이스 호환)"""
        intensity = float(make_json_safe(intensity))
        
        if intensity < 0.1:
            return 0.0
        
        success_count = 0
        for svc_name in self.service_mappings:
            if self.shuffle_network(svc_name, intensity, change_ip=False, change_port=True):
                success_count += 1
        
        return self.COST_WEIGHTS["port_hop"] * intensity

    def activate_decoys(self, ratio: Union[float, int, Any] = 0.5) -> float:
        """디코이 활성화 (RL 인터페이스 호환)"""
        ratio = float(make_json_safe(ratio))
        
        if ratio < 0.1:
            return 0.0
        
        decoy_count = max(1, int(ratio * 3))  # 최대 3개 디코이
        created = self.activate_decoy("fc_mavlink", decoy_count)
        
        return self.COST_WEIGHTS["decoy"] * ratio * len(created)

    def blacklist_update(self, aggression: Union[float, int, Any] = 0.5, duration: Union[float, int, Any] = 300) -> float:
        """블랙리스트 업데이트 (RL 인터페이스 호환)"""
        aggression = float(make_json_safe(aggression))
        duration = float(make_json_safe(duration))
        
        if aggression < 0.3:
            return 0.0
        
        # 가상의 의심스러운 IP 차단
        suspicious_ip = f"192.168.1.{random.randint(100, 200)}"
        self.add_to_blacklist(suspicious_ip, duration_sec=duration, reason="rl_triggered")
        
        return self.COST_WEIGHTS["blacklist"] * aggression

    def swap(self, intensity: Union[float, int, Any] = 0.5, target_critical: bool = True) -> float:
        """서비스 스왑 (RL 인터페이스 호환)"""
        intensity = float(make_json_safe(intensity))
        
        if intensity < 0.2:
            return 0.0
        
        # fc_mavlink과 해당 디코이 간 스왑
        success, cost_info = self.service_swap("fc_mavlink", "decoy_fc_mavlink", intensity)
        
        if success:
            return cost_info.get("total", self.COST_WEIGHTS["service_swap"] * intensity)
        else:
            return 0.0

    def shuffle_network(
        self,
        service_name: str,
        intensity: Union[float, int, Any] = 0.5,
        change_ip: bool = True,
        change_port: bool = True,
    ) -> bool:
        """네트워크 셔플: Virtual IP/Port 재할당"""
        with self._lock:
            # 타입 안전 변환
            intensity = float(make_json_safe(intensity))
            
            if service_name not in self.service_mappings:
                logger.warning(f"Unknown service: {service_name}")
                return False

            mapping = self.service_mappings[service_name]
            old_vip = mapping.virtual_ip
            old_vport = mapping.virtual_port

            do_change_ip = change_ip and intensity >= 0.3
            do_change_port = change_port and intensity >= 0.1

            new_vip = self._allocate_virtual_ip() if do_change_ip else old_vip
            new_vport = self._allocate_virtual_port() if do_change_port else old_vport

            if old_vip != mapping.real_ip or old_vport != mapping.real_port:
                self._run_iptables(
                    f"-D PREROUTING -d {old_vip} -p {mapping.protocol} "
                    f"--dport {old_vport} -j DNAT "
                    f"--to-destination {mapping.real_ip}:{mapping.real_port}"
                )

            if new_vip != mapping.real_ip or new_vport != mapping.real_port:
                ok, err = self._run_iptables(
                    f"-A PREROUTING -d {new_vip} -p {mapping.protocol} "
                    f"--dport {new_vport} -j DNAT "
                    f"--to-destination {mapping.real_ip}:{mapping.real_port}"
                )

                if not ok:
                    logger.error(f"Failed to add DNAT rule: {err}")
                    return False

            if do_change_ip:
                self._release_virtual_ip(old_vip)
            if do_change_port:
                self._release_virtual_port(old_vport)

            mapping.virtual_ip = new_vip
            mapping.virtual_port = new_vport
            mapping.shuffle_count += 1

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

    # =========================================================================
    # MTD 액션: Service Swap  
    # =========================================================================
    def service_swap(
        self,
        service_a: str,
        service_b: str,
        intensity: Union[float, int, Any] = 0.5,
        duration_sec: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, float]]:
        """서비스 스왑: 두 서비스의 가상 주소를 교환"""
        with self._lock:
            # 타입 안전 변환
            intensity = float(make_json_safe(intensity))
            
            cost_info = {
                "latency_ms": 0.0,
                "bandwidth_overhead": 0.0,
                "connection_resets": 0,
                "energy": 0.0,
                "availability_loss": 0.0,
                "total": 0.0,
            }

            if service_a not in self.service_mappings:
                logger.warning(f"Unknown service: {service_a}")
                return False, cost_info

            if service_b not in self.service_mappings:
                logger.warning(f"Unknown service: {service_b}")
                return False, cost_info

            mapping_a = self.service_mappings[service_a]
            mapping_b = self.service_mappings[service_b]

            if mapping_a.protocol != mapping_b.protocol:
                logger.warning(
                    f"Protocol mismatch: {service_a}({mapping_a.protocol}) vs "
                    f"{service_b}({mapping_b.protocol})"
                )
                return False, cost_info

            scm = self.swap_cost_model

            base_latency = scm.swap_latency_ms * intensity
            sync_latency = scm.swap_sync_time_ms * intensity
            total_latency = base_latency + sync_latency

            bandwidth = scm.swap_bandwidth_overhead * intensity

            connection_resets = 0
            if random.random() < scm.swap_connection_reset_prob * intensity:
                connection_resets = random.randint(1, 5)

            energy = scm.swap_energy_joule * intensity
            availability_loss = scm.swap_availability_impact * intensity

            total_cost = (
                total_latency / 1000 +
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

            old_vip_a, old_vport_a = mapping_a.virtual_ip, mapping_a.virtual_port
            old_vip_b, old_vport_b = mapping_b.virtual_ip, mapping_b.virtual_port

            # 기존 DNAT 규칙 제거
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

            # Virtual 주소 교환
            mapping_a.virtual_ip = old_vip_b
            mapping_a.virtual_port = old_vport_b
            mapping_b.virtual_ip = old_vip_a
            mapping_b.virtual_port = old_vport_a

            # 새 DNAT 규칙 추가
            if mapping_a.virtual_ip != mapping_a.real_ip or mapping_a.virtual_port != mapping_a.real_port:
                self._run_iptables(
                    f"-A PREROUTING -d {mapping_a.virtual_ip} -p {mapping_a.protocol} "
                    f"--dport {mapping_a.virtual_port} -j DNAT "
                    f"--to-destination {mapping_a.real_ip}:{mapping_a.real_port}"
                )

            if mapping_b.virtual_ip != mapping_b.real_ip or mapping_b.virtual_port != mapping_b.real_port:
                self._run_iptables(
                    f"-A PREROUTING -d {mapping_b.virtual_ip} -p {mapping_b.protocol} "
                    f"--dport {mapping_b.virtual_port} -j DNAT "
                    f"--to-destination {mapping_b.real_ip}:{mapping_b.real_port}"
                )

            # 통계 업데이트
            mapping_a.swap_count += 1
            mapping_a.last_swap_step = self.current_step
            mapping_a.swapped_with = service_b

            mapping_b.swap_count += 1
            mapping_b.last_swap_step = self.current_step
            mapping_b.swapped_with = service_a

            # 스왑 기록
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

            # 전체 통계 업데이트
            self.stats.total_service_swaps += 1
            self.stats.total_swap_connection_resets += connection_resets
            self.stats.total_swap_latency_ms += total_latency
            self.stats.total_cost += self.COST_WEIGHTS["service_swap"] * intensity
            self.stats.last_swap_time = time.time()
            self.stats.last_action_time = time.time()

            logger.info(
                f"[SERVICE_SWAP] {service_a} ↔ {service_b}: "
                f"({old_vip_a}:{old_vport_a}) ↔ ({old_vip_b}:{old_vport_b}) "
                f"(intensity={intensity:.2f}, latency={total_latency:.1f}ms)"
            )

            self._log_action("service_swap", {
                "service_a": service_a,
                "service_b": service_b,
                "intensity": intensity,
                "cost": cost_info,
            })

            self._save_state()
            return True, cost_info

    # =========================================================================
    # MTD 액션: Decoy Activation
    # =========================================================================
    def activate_decoy(
        self,
        target_service: str,
        decoy_count: int = 1,
    ) -> List[str]:
        """디코이 활성화"""
        with self._lock:
            created_decoys = []

            for _ in range(decoy_count):
                decoy_suffix = random.randint(DECOY_IP_START, DECOY_IP_END)
                decoy_ip = f"{self.network_prefix}.{decoy_suffix}"
                decoy_port = random.randint(PORT_POOL_START, PORT_POOL_END)

                decoy_id = f"decoy_{target_service}_{len(self.decoys)}"

                protocol = "tcp"
                if target_service in self.services_config:
                    protocol = self.services_config[target_service].get("protocol", "tcp")

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
                        f"[DECOY] Activated {decoy_id} at {decoy_ip}:{decoy_port}"
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

            self._run_iptables(
                f"-D PREROUTING -d {decoy.decoy_ip} -p {decoy.protocol} "
                f"--dport {decoy.decoy_port} -j REDIRECT --to-port {HONEYPOT_PORT}"
            )

            del self.decoys[decoy_id]
            logger.info(f"[DECOY] Deactivated {decoy_id}")

            self._save_state()
            return True

    # =========================================================================
    # MTD 액션: Blacklist
    # =========================================================================
    def add_to_blacklist(
        self,
        ip: str,
        duration_sec: float = 300,
        reason: str = "suspicious_activity",
    ) -> bool:
        """IP를 블랙리스트에 추가"""
        with self._lock:
            if ip in self.blacklist:
                self.blacklist[ip].expires_at = time.time() + duration_sec
                logger.info(f"[BLACKLIST] Extended {ip} for {duration_sec}s")
                return True

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

                logger.info(f"[BLACKLIST] Added {ip} for {duration_sec}s")

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
    # 상태 조회
    # =========================================================================
    def get_current_mapping(self, service_name: str) -> Optional[Dict]:
        """현재 서비스 매핑 조회"""
        if service_name not in self.service_mappings:
            return None
        return make_json_safe(asdict(self.service_mappings[service_name]))

    def get_all_mappings(self) -> Dict[str, Dict]:
        """모든 서비스 매핑 조회"""
        return {k: make_json_safe(asdict(v)) for k, v in self.service_mappings.items()}

    def get_statistics(self) -> Dict:
        """MTD 통계 조회"""
        stats_dict = self.stats.to_dict()
        stats_dict["active_decoys"] = len(self.decoys)
        stats_dict["blacklist_size"] = len(self.blacklist)
        stats_dict["active_swaps"] = len(self.active_swaps)
        stats_dict["confusion_level"] = self.get_confusion_level()
        stats_dict["uptime"] = time.time() - self.stats.start_time
        return make_json_safe(stats_dict)

    def get_cdi(self) -> float:
        """CDI (Configuration Diversity Index) 계산"""
        return self.get_diversity_score()

    def get_ned(self) -> float:
        """NED (Normalized Entropy of Defense) 계산"""
        if len(self.active_swaps) == 0:
            return 0.3
        
        # 활성 스왑의 다양성 기반 계산
        confusion = self.get_confusion_level()
        return min(1.0, 0.3 + confusion * 0.4)

    def get_redundancy(self) -> float:
        """중복성 점수 계산 (논문 Eq. 12 호환)"""
        n_decoys = len(self.decoys)
        n_swaps = len(self.active_swaps)
        
        # 0.6 * (n_decoy/N_d) + 0.3 * (n_swap/N_s) + 0.1
        decoy_term = 0.6 * min(1.0, n_decoys / 4.0)  # 최대 4개 디코이 가정
        swap_term = 0.3 * min(1.0, n_swaps / 3.0)    # 최대 3개 스왑 가정
        base_term = 0.1
        
        return decoy_term + swap_term + base_term

    def get_diversity_score(self) -> float:
        """현재 다양성 점수 계산"""
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

        base_diversity = different_count / total
        swap_bonus = (swapped_count / total) * 0.2

        return min(1.0, base_diversity + swap_bonus)

    def get_confusion_level(self) -> float:
        """현재 전체 혼란도 반환"""
        if not self.active_swaps:
            return 0.0

        now = time.time()
        confusion = 0.0

        for swap_record in self.active_swaps.values():
            if swap_record.active:
                age = now - swap_record.swap_time
                decay = max(0, 1.0 - age / 300)
                confusion += swap_record.intensity * decay * 0.3

        return min(1.0, confusion)

    def get_mtd_state_for_attacker(self) -> Dict:
        """공격자용 MTD 상태 JSON 생성"""
        primary_service = "cc_sitl"
        if primary_service in self.service_mappings:
            mapping = self.service_mappings[primary_service]
            current_target = f"{mapping.virtual_ip}:{mapping.virtual_port}"
        else:
            current_target = "10.13.0.3:5760"

        return make_json_safe({
            "current_target": current_target,
            "mtd_active": self.get_diversity_score() > 0,
            "diversity_score": self.get_diversity_score(),
            "redundancy_score": self.get_redundancy(),
            "confusion_level": self.get_confusion_level(),
            "decoy_count": len(self.decoys),
            "blacklist_count": len(self.blacklist),
            "active_swap_count": len(self.active_swaps),
            "last_shuffle_time": self.stats.last_action_time,
            "last_swap_time": self.stats.last_swap_time,
        })

    def save_mtd_state_json(self, filepath: str):
        """mtd_state.json 파일로 저장"""
        state = self.get_mtd_state_for_attacker()
        state["timestamp"] = datetime.now(timezone.utc).isoformat()

        with open(filepath, 'w') as f:
            json.dump(make_json_safe(state), f, indent=2)

    def cleanup(self):
        """모든 MTD 규칙 정리"""
        logger.info("Cleaning up all MTD rules...")

        # 활성 스왑 정리
        for swap_id in list(self.active_swaps.keys()):
            self.active_swaps[swap_id].active = False
            del self.active_swaps[swap_id]

        # 디코이 정리
        for decoy_id in list(self.decoys.keys()):
            self.deactivate_decoy(decoy_id)

        # 블랙리스트 정리
        for ip in list(self.blacklist.keys()):
            self.remove_from_blacklist(ip)

        # 서비스 매핑 원상복구
        for svc_name, mapping in self.service_mappings.items():
            if mapping.virtual_ip != mapping.real_ip or mapping.virtual_port != mapping.real_port:
                self._run_iptables(
                    f"-D PREROUTING -d {mapping.virtual_ip} -p {mapping.protocol} "
                    f"--dport {mapping.virtual_port} -j DNAT "
                    f"--to-destination {mapping.real_ip}:{mapping.real_port}"
                )

                mapping.virtual_ip = mapping.real_ip
                mapping.virtual_port = mapping.real_port

            mapping.swapped_with = None

        self._save_state()
        logger.info("Cleanup completed")


# =============================================================================
# 메인 (테스트용)
# =============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="iptables MTD Controller v08.4 (JSON Fix)")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--test-swap", action="store_true")
    parser.add_argument("--test-numpy", action="store_true", help="Test numpy type compatibility")
    args = parser.parse_args()

    controller = IptablesMTDController(dry_run=args.dry_run)

    if args.test_numpy:
        print("\n=== Testing NumPy Type Compatibility ===\n")
        
        # numpy 타입 테스트
        if NUMPY_AVAILABLE:
            print("Testing numpy types...")
            
            # float32 타입 테스트
            intensity_np = np.float32(0.7)
            print(f"numpy float32: {intensity_np} -> {make_json_safe(intensity_np)} ({type(make_json_safe(intensity_np))})")
            
            # 실제 MTD 액션 테스트
            cost = controller.shuffle(intensity_np)
            print(f"Shuffle cost: {cost}")
            
            # 배열 타입 테스트
            action_array = np.array([0.5, 0.3, 0.8])
            print(f"numpy array: {action_array} -> {make_json_safe(action_array)}")
            
        else:
            print("NumPy not available, skipping numpy tests")

    if args.test or args.test_swap:
        print("\n=== Testing MTD Controller v08.4 ===\n")

        print("1. Testing shuffle...")
        controller.shuffle_network("fc_mavlink", intensity=0.7)
        controller.shuffle_network("cc_sitl", intensity=0.5)

        print("\n2. Testing decoy...")
        decoys = controller.activate_decoy("fc_mavlink", decoy_count=2)
        print(f"   Created decoys: {decoys}")

        print("\n3. Testing blacklist...")
        controller.add_to_blacklist("192.168.1.100", duration_sec=60)

        if args.test_swap:
            print("\n4. Testing service swap...")
            success, cost = controller.service_swap(
                "fc_mavlink",
                "decoy_fc_mavlink",
                intensity=0.7
            )
            print(f"   Swap result: success={success}")
            print(f"   Swap cost: {json.dumps(cost, indent=6)}")

        print("\n5. Current state:")
        print(f"   Diversity: {controller.get_diversity_score():.2f}")
        print(f"   Redundancy: {controller.get_redundancy():.2f}")
        print(f"   Stats: {safe_json_dumps(controller.get_statistics(), indent=2)}")

        print("\n6. Cleanup...")
        controller.cleanup()

        print("\n=== Test Complete ===")