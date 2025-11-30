#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iptables_mtd_controller.py (v07)
================================
Advanced Network MTD Controller - Testbed Aligned Version

공격자 환경변수와 동일한 매핑 사용:
- TARGET_FC, TARGET_CC, TARGET_GCS, TARGET_SIM, TARGET_DECOY
- PORT_MAVLINK, PORT_SITL, PORT_RTSP, PORT_WEB, PORT_ROS
"""

from __future__ import annotations

import logging
import random
import datetime
import json
import os
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field, asdict

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mtd_system.log", mode="a"),
    ],
)
logger = logging.getLogger("IptablesMTD")


# =============================================================================
# 공격자 환경변수와 동일한 매핑 (CRITICAL: 반드시 일치해야 함)
# =============================================================================
TESTBED_TARGETS = {
    "TARGET_FC": "10.13.0.2",
    "TARGET_CC": "10.13.0.3", 
    "TARGET_GCS": "10.13.0.4",
    "TARGET_SIM": "10.13.0.5",
    "TARGET_DECOY": "10.13.0.7",
    "TARGET_DECOY_2": "10.13.0.8",  # 추가 디코이
}

TESTBED_PORTS = {
    "PORT_MAVLINK": 14550,
    "PORT_SITL": 5760,
    "PORT_RTSP": 554,
    "PORT_WEB": 3000,
    "PORT_ROS": 11311,
}

TESTBED_INTERFACES = {
    "TARGET_CC_WIFI": "192.168.13.1",
}

# 서비스-포트 매핑 (어떤 타겟이 어떤 포트를 사용하는지)
SERVICE_PORT_MAP = {
    "TARGET_FC": ["PORT_MAVLINK"],
    "TARGET_CC": ["PORT_WEB", "PORT_MAVLINK"],
    "TARGET_GCS": ["PORT_MAVLINK", "PORT_WEB"],
    "TARGET_SIM": ["PORT_SITL", "PORT_ROS"],
    "TARGET_DECOY": ["PORT_MAVLINK", "PORT_WEB"],
    "TARGET_DECOY_2": ["PORT_WEB"],
}

# Critical Asset 정의
CRITICAL_ASSETS = ["TARGET_FC", "TARGET_GCS"]
DECOY_ASSETS = ["TARGET_DECOY", "TARGET_DECOY_2"]


# =============================================================================
# MTD State 데이터 구조 (RL 환경과 공유)
# =============================================================================
@dataclass
class ServiceMapping:
    """단일 서비스의 Real <-> Virtual 매핑 정보"""
    service_id: str
    target_key: str           # TARGET_FC, TARGET_CC, etc.
    port_key: str             # PORT_MAVLINK, PORT_WEB, etc.
    real_ip: str
    real_port: int
    virtual_ip: str
    virtual_port: int
    is_decoy_redirect: bool = False
    is_critical: bool = False
    last_shuffle_time: str = ""
    shuffle_count: int = 0


@dataclass
class MTDState:
    """전체 MTD 상태 (mtd_state.json과 동기화)"""
    version: str = "1.0.0"
    last_updated: str = ""
    
    # 서비스 매핑
    services: Dict[str, dict] = field(default_factory=dict)
    
    # 블랙리스트
    blacklist: Dict[str, int] = field(default_factory=dict)  # IP -> remaining_duration
    
    # 통계
    total_shuffles: int = 0
    total_port_hops: int = 0
    total_decoy_redirects: int = 0
    total_blocks: int = 0
    
    # 현재 엔트로피
    current_entropy_bits: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def save(self, filepath: str):
        self.last_updated = datetime.datetime.now().isoformat()
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'MTDState':
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
            state = cls()
            for key, value in data.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            return state
        return cls()


# =============================================================================
# 기본 iptables 컨트롤러
# =============================================================================
class IptablesController:
    """기본 iptables 명령 실행 클래스"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
    
    def _run_cmd(self, cmd: List[str], ignore_errors: bool = False) -> bool:
        """iptables 명령 실행"""
        import subprocess
        
        cmd_str = " ".join(cmd)
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] {cmd_str}")
            return True
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=10
            )
            if result.returncode != 0 and not ignore_errors:
                logger.error(f"Command failed: {cmd_str}\n{result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {cmd_str}")
            return False
        except Exception as e:
            if not ignore_errors:
                logger.error(f"Command error: {cmd_str} - {e}")
            return False


# =============================================================================
# MTD 컨트롤러 (메인 클래스)
# =============================================================================
class IptablesMTDController(IptablesController):
    """
    MTD 액션을 수행하고 상태를 관리하는 상위 컨트롤러.
    
    공격자 환경변수와 동일한 TARGET_*, PORT_* 키 사용.
    """
    
    def __init__(
        self,
        dry_run: bool = False,
        audit_file: str = "mtd_audit.log",
        state_file: str = "shared_state/mtd_state.json",
        vip_range: Tuple[str, int, int] = ("10.13.0", 100, 199),
        vport_range: Tuple[int, int] = (20000, 21000),
    ) -> None:
        super().__init__(dry_run=dry_run)
        
        self.audit_file = audit_file
        self.state_file = state_file
        self.vip_prefix, self.vip_start, self.vip_end = vip_range
        self.vport_start, self.vport_end = vport_range
        
        # MTD 상태 로드/초기화
        self.state = MTDState.load(state_file)
        
        # 서비스 매핑 (ServiceMapping 객체들)
        self.services: Dict[str, ServiceMapping] = {}
        
        # iptables 체인 초기화
        self._initialize_chains()
        self._log_audit("MTD Controller Initialized (v07 - Testbed Aligned)")
    
    # =========================================================================
    # 내부 유틸리티
    # =========================================================================
    def _initialize_chains(self) -> None:
        """MTD 전용 iptables 체인 생성"""
        chains = ["MTD-DNAT", "MTD-SNAT", "MTD-BLOCK"]
        
        for chain in chains:
            self._run_cmd(["iptables", "-t", "nat", "-N", chain], ignore_errors=True)
            self._run_cmd(["iptables", "-t", "nat", "-F", chain], ignore_errors=False)
        
        # filter 테이블에 블록 체인
        self._run_cmd(["iptables", "-N", "MTD-BLOCK"], ignore_errors=True)
        self._run_cmd(["iptables", "-F", "MTD-BLOCK"], ignore_errors=False)
        
        # 체인 연결
        self._run_cmd(["iptables", "-t", "nat", "-I", "PREROUTING", "1", "-j", "MTD-DNAT"], ignore_errors=True)
        self._run_cmd(["iptables", "-t", "nat", "-I", "POSTROUTING", "1", "-j", "MTD-SNAT"], ignore_errors=True)
        self._run_cmd(["iptables", "-I", "INPUT", "1", "-j", "MTD-BLOCK"], ignore_errors=True)
        
        # MASQUERADE
        self._run_cmd(["iptables", "-t", "nat", "-A", "MTD-SNAT", "-j", "MASQUERADE"], ignore_errors=True)
    
    def _get_random_vip(self) -> str:
        """랜덤 가상 IP 생성"""
        octet = random.randint(self.vip_start, self.vip_end)
        return f"{self.vip_prefix}.{octet}"
    
    def _get_random_vport(self) -> int:
        """랜덤 가상 포트 생성"""
        return random.randint(self.vport_start, self.vport_end)
    
    def _log_audit(self, message: str, mapping: Optional[ServiceMapping] = None) -> None:
        """감사 로그 기록"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        if mapping:
            log_entry += (
                f"\n    >> Real({mapping.real_ip}:{mapping.real_port})"
                f" <==> Virtual({mapping.virtual_ip}:{mapping.virtual_port})"
            )
            if mapping.is_decoy_redirect:
                log_entry += " [⚠️ DECOY REDIRECT]"
            if mapping.is_critical:
                log_entry += " [🔴 CRITICAL]"
        
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
        
        logger.info(log_entry.replace("\n", " | "))
    
    def _calculate_entropy(self) -> float:
        """현재 설정의 엔트로피 비트 계산"""
        import math
        ip_space = self.vip_end - self.vip_start + 1
        port_space = self.vport_end - self.vport_start + 1
        total_space = ip_space * port_space
        return math.log2(total_space) if total_space > 0 else 0.0
    
    def _sync_state(self) -> None:
        """상태를 파일에 저장"""
        # 서비스 매핑을 dict로 변환
        self.state.services = {
            name: asdict(svc) for name, svc in self.services.items()
        }
        self.state.current_entropy_bits = self._calculate_entropy()
        
        # 디렉토리 생성
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self.state.save(self.state_file)
    
    # =========================================================================
    # 공개 API - 서비스 등록
    # =========================================================================
    def register_service(
        self, 
        service_id: str, 
        target_key: str, 
        port_key: str
    ) -> bool:
        """
        서비스 등록 (공격자 환경변수와 동일한 키 사용)
        
        Args:
            service_id: 고유 서비스 ID (예: "fc_mavlink")
            target_key: TARGET_FC, TARGET_CC, etc.
            port_key: PORT_MAVLINK, PORT_WEB, etc.
        
        Returns:
            등록 성공 여부
        """
        if target_key not in TESTBED_TARGETS:
            logger.error(f"Unknown target: {target_key}")
            logger.info(f"Available: {list(TESTBED_TARGETS.keys())}")
            return False
        
        if port_key not in TESTBED_PORTS:
            logger.error(f"Unknown port: {port_key}")
            logger.info(f"Available: {list(TESTBED_PORTS.keys())}")
            return False
        
        real_ip = TESTBED_TARGETS[target_key]
        real_port = TESTBED_PORTS[port_key]
        
        mapping = ServiceMapping(
            service_id=service_id,
            target_key=target_key,
            port_key=port_key,
            real_ip=real_ip,
            real_port=real_port,
            virtual_ip=real_ip,      # 초기에는 동일
            virtual_port=real_port,  # 초기에는 동일
            is_critical=(target_key in CRITICAL_ASSETS),
        )
        
        self.services[service_id] = mapping
        self._sync_state()
        
        logger.info(
            f"✅ Service Registered: {service_id} "
            f"({target_key}:{port_key} = {real_ip}:{real_port})"
        )
        return True
    
    def register_all_services(self) -> None:
        """모든 표준 서비스 자동 등록"""
        for target_key, port_keys in SERVICE_PORT_MAP.items():
            for port_key in port_keys:
                service_id = f"{target_key.lower()}_{port_key.lower()}"
                self.register_service(service_id, target_key, port_key)
    
    # =========================================================================
    # 공개 API - MTD 액션
    # =========================================================================
    def shuffle_ip(self, service_id: str) -> bool:
        """IP 셔플 (단일 서비스)"""
        if service_id not in self.services:
            logger.warning(f"Service not found: {service_id}")
            return False
        
        svc = self.services[service_id]
        old_vip = svc.virtual_ip
        svc.virtual_ip = self._get_random_vip()
        svc.shuffle_count += 1
        svc.last_shuffle_time = datetime.datetime.now().isoformat()
        
        self._apply_dnat_rule(svc)
        self.state.total_shuffles += 1
        self._sync_state()
        
        self._log_audit(f"🔀 IP Shuffle: {old_vip} -> {svc.virtual_ip}", svc)
        return True
    
    def shuffle_port(self, service_id: str) -> bool:
        """Port 셔플 (단일 서비스)"""
        if service_id not in self.services:
            logger.warning(f"Service not found: {service_id}")
            return False
        
        svc = self.services[service_id]
        old_vport = svc.virtual_port
        svc.virtual_port = self._get_random_vport()
        
        self._apply_dnat_rule(svc)
        self.state.total_port_hops += 1
        self._sync_state()
        
        self._log_audit(f"🔀 Port Hop: {old_vport} -> {svc.virtual_port}", svc)
        return True
    
    def shuffle_all(self, intensity: float = 1.0) -> Dict[str, bool]:
        """
        모든 서비스에 대해 셔플 수행
        
        Args:
            intensity: 0.0~1.0, 셔플 확률
        
        Returns:
            {service_id: success} 딕셔너리
        """
        results = {}
        for service_id in self.services:
            if random.random() < intensity:
                ip_ok = self.shuffle_ip(service_id)
                port_ok = self.shuffle_port(service_id)
                results[service_id] = ip_ok and port_ok
            else:
                results[service_id] = False
        return results
    
    def enable_decoy_redirect(self, service_id: str, decoy_target: str = "TARGET_DECOY") -> bool:
        """
        서비스 트래픽을 디코이로 리다이렉트
        
        Args:
            service_id: 리다이렉트할 서비스
            decoy_target: 디코이 타겟 키 (TARGET_DECOY, TARGET_DECOY_2)
        """
        if service_id not in self.services:
            logger.warning(f"Service not found: {service_id}")
            return False
        
        if decoy_target not in TESTBED_TARGETS:
            logger.error(f"Unknown decoy target: {decoy_target}")
            return False
        
        svc = self.services[service_id]
        svc.is_decoy_redirect = True
        
        # 디코이 IP로 리다이렉트 규칙 적용
        decoy_ip = TESTBED_TARGETS[decoy_target]
        self._apply_dnat_rule(svc, override_dest_ip=decoy_ip)
        
        self.state.total_decoy_redirects += 1
        self._sync_state()
        
        self._log_audit(f"⚠️ DECOY REDIRECT: {service_id} -> {decoy_ip}", svc)
        return True
    
    def disable_decoy_redirect(self, service_id: str) -> bool:
        """디코이 리다이렉트 해제"""
        if service_id not in self.services:
            return False
        
        svc = self.services[service_id]
        svc.is_decoy_redirect = False
        
        self._apply_dnat_rule(svc)
        self._sync_state()
        
        self._log_audit(f"✅ Decoy Disabled: {service_id} restored", svc)
        return True
    
    def block_ip(self, attacker_ip: str, duration: int = 300) -> bool:
        """
        공격자 IP 차단
        
        Args:
            attacker_ip: 차단할 IP
            duration: 차단 지속 시간 (초), -1이면 영구
        """
        # MTD-BLOCK 체인에 DROP 규칙 추가
        cmd = ["iptables", "-A", "MTD-BLOCK", "-s", attacker_ip, "-j", "DROP"]
        success = self._run_cmd(cmd)
        
        if success:
            self.state.blacklist[attacker_ip] = duration
            self.state.total_blocks += 1
            self._sync_state()
            self._log_audit(f"🚫 BLOCKED: {attacker_ip} (duration: {duration}s)")
        
        return success
    
    def unblock_ip(self, attacker_ip: str) -> bool:
        """IP 차단 해제"""
        cmd = ["iptables", "-D", "MTD-BLOCK", "-s", attacker_ip, "-j", "DROP"]
        success = self._run_cmd(cmd, ignore_errors=True)
        
        if attacker_ip in self.state.blacklist:
            del self.state.blacklist[attacker_ip]
            self._sync_state()
            self._log_audit(f"✅ UNBLOCKED: {attacker_ip}")
        
        return success
    
    # =========================================================================
    # iptables 규칙 적용
    # =========================================================================
    def _apply_dnat_rule(
        self, 
        svc: ServiceMapping, 
        override_dest_ip: Optional[str] = None
    ) -> None:
        """DNAT 규칙 적용"""
        # 목적지 IP 결정
        if override_dest_ip:
            dest_ip = override_dest_ip
        elif svc.is_decoy_redirect:
            dest_ip = TESTBED_TARGETS.get("TARGET_DECOY", svc.real_ip)
        else:
            dest_ip = svc.real_ip
        
        dest_port = svc.real_port
        vip = svc.virtual_ip
        vport = svc.virtual_port
        
        # 기존 규칙 삭제 (서비스별로 관리하려면 comment 사용)
        # 여기서는 간단히 체인 플러시 후 재적용
        self._rebuild_all_dnat_rules()
    
    def _rebuild_all_dnat_rules(self) -> None:
        """모든 DNAT 규칙 재구축"""
        # MTD-DNAT 체인 플러시
        self._run_cmd(["iptables", "-t", "nat", "-F", "MTD-DNAT"], ignore_errors=True)
        
        for svc in self.services.values():
            # 목적지 결정
            if svc.is_decoy_redirect:
                dest_ip = TESTBED_TARGETS.get("TARGET_DECOY", svc.real_ip)
            else:
                dest_ip = svc.real_ip
            
            dest_port = svc.real_port
            vip = svc.virtual_ip
            vport = svc.virtual_port
            
            # TCP DNAT
            tcp_cmd = [
                "iptables", "-t", "nat", "-A", "MTD-DNAT",
                "-p", "tcp",
                "-d", vip, "--dport", str(vport),
                "-j", "DNAT", "--to-destination", f"{dest_ip}:{dest_port}",
            ]
            self._run_cmd(tcp_cmd)
            
            # UDP DNAT (MAVLink은 UDP도 사용)
            udp_cmd = [
                "iptables", "-t", "nat", "-A", "MTD-DNAT",
                "-p", "udp",
                "-d", vip, "--dport", str(vport),
                "-j", "DNAT", "--to-destination", f"{dest_ip}:{dest_port}",
            ]
            self._run_cmd(udp_cmd)
    
    # =========================================================================
    # RL 환경 인터페이스
    # =========================================================================
    def apply_rl_action(self, action_params: Dict[str, float]) -> Dict[str, any]:
        """
        RL 환경에서 호출하는 통합 MTD 액션 인터페이스
        
        Args:
            action_params: {
                "shuffle_intensity": 0.0~1.0,
                "port_hop_intensity": 0.0~1.0,
                "decoy_activation_level": 0.0~1.0,
                "blacklist_aggression": 0.0~1.0,
            }
        
        Returns:
            적용 결과 딕셔너리
        """
        results = {
            "shuffle_count": 0,
            "port_hop_count": 0,
            "decoy_activated": 0,
            "total_cost": 0.0,
        }
        
        shuffle_intensity = action_params.get("shuffle_intensity", 0.0)
        port_hop_intensity = action_params.get("port_hop_intensity", 0.0)
        decoy_level = action_params.get("decoy_activation_level", 0.0)
        
        # IP Shuffle
        if shuffle_intensity >= 0.3:
            for service_id in self.services:
                if random.random() < shuffle_intensity:
                    self.shuffle_ip(service_id)
                    results["shuffle_count"] += 1
        
        # Port Hop
        if port_hop_intensity >= 0.3:
            for service_id in self.services:
                if random.random() < port_hop_intensity:
                    self.shuffle_port(service_id)
                    results["port_hop_count"] += 1
        
        # Decoy Activation
        if decoy_level >= 0.2:
            # Critical이 아닌 서비스 중 일부를 디코이로 리다이렉트
            non_critical = [
                sid for sid, svc in self.services.items() 
                if not svc.is_critical
            ]
            num_to_redirect = int(len(non_critical) * decoy_level)
            for service_id in random.sample(non_critical, min(num_to_redirect, len(non_critical))):
                self.enable_decoy_redirect(service_id)
                results["decoy_activated"] += 1
        
        # 비용 계산 (단순화)
        results["total_cost"] = (
            results["shuffle_count"] * 0.012 +
            results["port_hop_count"] * 0.1 +
            results["decoy_activated"] * 0.5
        )
        
        return results
    
    def get_current_mappings(self) -> Dict[str, Dict]:
        """
        현재 매핑 정보 반환 (공격자가 알아야 할 정보)
        
        Returns:
            {service_id: {
                "target": "TARGET_FC",
                "port": "PORT_MAVLINK", 
                "virtual_ip": "10.13.0.xxx",
                "virtual_port": xxxxx,
                "real_ip": "10.13.0.2",
                "real_port": 14550,
            }}
        """
        return {
            sid: {
                "target": svc.target_key,
                "port": svc.port_key,
                "virtual_ip": svc.virtual_ip,
                "virtual_port": svc.virtual_port,
                "real_ip": svc.real_ip,
                "real_port": svc.real_port,
                "is_decoy": svc.is_decoy_redirect,
            }
            for sid, svc in self.services.items()
        }
    
    def export_attacker_env(self) -> Dict[str, str]:
        """
        공격자 컨테이너에 전달할 환경변수 형식으로 export
        
        Returns:
            {"TARGET_FC": "10.13.0.xxx", "PORT_MAVLINK": "20xxx", ...}
        """
        env = {}
        
        # 가상 IP로 타겟 덮어쓰기
        for sid, svc in self.services.items():
            # 타겟별로 가상 IP 설정 (마지막 것이 적용됨)
            env[svc.target_key] = svc.virtual_ip
        
        # 가상 포트로 포트 덮어쓰기
        port_mapping = {}
        for sid, svc in self.services.items():
            if svc.port_key not in port_mapping:
                port_mapping[svc.port_key] = svc.virtual_port
        
        for port_key, vport in port_mapping.items():
            env[port_key] = str(vport)
        
        # 인터페이스는 그대로
        env.update({k: v for k, v in TESTBED_INTERFACES.items()})
        
        return env
    
    def print_status(self) -> None:
        """현재 상태 출력"""
        print("\n" + "="*60)
        print("MTD Controller Status (v07)")
        print("="*60)
        print(f"Total Shuffles: {self.state.total_shuffles}")
        print(f"Total Port Hops: {self.state.total_port_hops}")
        print(f"Total Decoy Redirects: {self.state.total_decoy_redirects}")
        print(f"Current Entropy: {self._calculate_entropy():.2f} bits")
        print(f"Blocked IPs: {len(self.state.blacklist)}")
        print("-"*60)
        print("Service Mappings:")
        for sid, svc in self.services.items():
            status = "🔴 CRITICAL" if svc.is_critical else ""
            status += " ⚠️ DECOY" if svc.is_decoy_redirect else ""
            print(f"  {sid}:")
            print(f"    Real:    {svc.real_ip}:{svc.real_port}")
            print(f"    Virtual: {svc.virtual_ip}:{svc.virtual_port} {status}")
        print("="*60 + "\n")


# =============================================================================
# 테스트
# =============================================================================
if __name__ == "__main__":
    # Dry-run 모드로 테스트
    ctl = IptablesMTDController(dry_run=True)
    
    # 모든 서비스 자동 등록
    ctl.register_all_services()
    
    print("\n--- [Test 1] Initial Status ---")
    ctl.print_status()
    
    print("\n--- [Test 2] Shuffle All (intensity=0.8) ---")
    results = ctl.shuffle_all(intensity=0.8)
    print(f"Results: {results}")
    
    print("\n--- [Test 3] Enable Decoy ---")
    ctl.enable_decoy_redirect("target_cc_port_web")
    
    print("\n--- [Test 4] Block Attacker ---")
    ctl.block_ip("192.168.1.100", duration=300)
    
    print("\n--- [Test 5] Export Attacker Env ---")
    env = ctl.export_attacker_env()
    print(json.dumps(env, indent=2))
    
    print("\n--- [Test 6] RL Action Interface ---")
    rl_results = ctl.apply_rl_action({
        "shuffle_intensity": 0.7,
        "port_hop_intensity": 0.5,
        "decoy_activation_level": 0.3,
    })
    print(f"RL Action Results: {rl_results}")
    
    print("\n--- Final Status ---")
    ctl.print_status()