# Directory: dvd_lite/dvd_attacks_lpc/mtd/
# Filename: iptables_channel_switch.py

import subprocess
import random

class IptablesChannelSwitcher:
    """
    Docker 컨테이너 환경 내부 또는 호스트에서 iptables를 조작하여
    '가상 노드 이동' 및 '통신 채널 변경(대체 노드 통신)'을 수행하는 액추에이터입니다.
    """
    def __init__(self):
        # Docker Network 설정에 따른 IP 주소 (docker-compose.yaml 참조)
        self.target_ip = "10.13.0.2"   # Flight Controller (실제 드론 제어기)
        self.backup_ip = "10.13.0.200" # Attacker가 아닌 Decoy/Backup Container IP로 설정해야 함
                                       # 예: 10.13.0.7 (decoy-gateway)
        
        self.gcs_ip = "10.13.0.4"      # Ground Control Station (아군)
        self.attacker_ip_prefix = "10.13.0.200" # 공격자 IP (시뮬레이터상 고정 혹은 대역)

        self.current_port = 14550
        self.available_ports = [14550, 14560, 14570, 14580]

    def _run_cmd(self, cmd):
        """Shell 명령어 실행 및 에러 처리"""
        try:
            # stdout=subprocess.DEVNULL로 설정하여 로그를 깔끔하게 유지
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError as e:
            print(f"[IPTables] Error executing '{cmd}': {e}")
            return False

    def rotate_ip(self):
        """
        [MTD: IP Shuffle]
        가상 IP(VIP)를 생성하여 마치 드론이 다른 IP로 이동한 것처럼 속입니다.
        실제로는 DNAT를 통해 원본 Flight Controller로 연결됩니다.
        """
        new_fake_last_octet = random.randint(10, 90)
        new_vip = f"10.13.0.{new_fake_last_octet}"
        
        print(f"[MTD] Rotating Virtual IP to {new_vip}")
        
        # 1. 기존 PREROUTING 규칙 삭제 (Flush는 주의 필요, 특정 체인만 관리 권장)
        # 여기서는 예시로 nat 테이블의 PREROUTING 전체를 초기화합니다.
        self._run_cmd("iptables -t nat -F PREROUTING")
        
        # 2. DNAT 규칙 추가
        # GCS나 외부에서 New VIP로 요청이 오면 -> 실제 Target IP로 전달
        # 공격자가 기존 IP를 스캔 중이라면 연결이 끊기거나 실패하게 됨
        cmd = f"iptables -t nat -A PREROUTING -d {new_vip} -j DNAT --to-destination {self.target_ip}"
        self._run_cmd(cmd)
        
        # (Optional) SNAT: 돌아가는 패킷의 소스 IP도 VIP로 변조해야 완벽한 속임수 가능
        cmd_snat = f"iptables -t nat -A POSTROUTING -s {self.target_ip} -j SNAT --to-source {new_vip}"
        self._run_cmd(cmd_snat)

    def rotate_port(self):
        """
        [MTD: Port Hopping]
        MAVLink 통신 포트를 변경하여 스캐닝을 혼란스럽게 합니다.
        """
        new_port = random.choice([p for p in self.available_ports if p != self.current_port])
        print(f"[MTD] Hopping Port {self.current_port} -> {new_port}")
        
        # 기존 규칙 초기화
        self._run_cmd("iptables -t nat -F PREROUTING")
        
        # 외부에서 New Port로 들어오면 -> 내부 14550(실제 서비스 포트)으로 전달
        # 이렇게 하면 Flight Controller 설정을 바꾸지 않고도 포트 변경 효과를 냄
        cmd = f"iptables -t nat -A PREROUTING -p udp --dport {new_port} -j REDIRECT --to-port 14550"
        self._run_cmd(cmd)
        
        self.current_port = new_port

    def activate_backup_channel(self):
        """
        [Critical Defense: Alternate Node Communication]
        주요 통신 채널이 심각하게 침해당했을 때, 
        1. 공격자 트래픽 차단 (Blackhole)
        2. 아군(GCS) 트래픽은 Backup Node(Decoy Gateway 등)로 우회
        """
        print("[MTD] ! CRITICAL THREAT DETECTED ! ACTIVATING BACKUP CHANNEL !")
        
        # 1. 공격자(Attacker)로부터 오는 트래픽은 명시적 차단 (DROP)
        # 시뮬레이션 환경에서 Attacker IP가 10.13.0.200이라 가정
        self._run_cmd(f"iptables -A INPUT -s {self.attacker_ip_prefix} -j DROP")
        self._run_cmd(f"iptables -A FORWARD -s {self.attacker_ip_prefix} -j DROP")
        
        # 2. GCS(아군) 트래픽은 Backup IP 경로로 리다이렉트 (Failover Simulation)
        # 마치 로드밸런서가 트래픽을 다른 서버로 넘기듯 처리
        # self.backup_ip는 실제 살아있는 컨테이너(예: 10.13.0.7)여야 핑 등이 응답함
        cmd = f"iptables -t nat -A PREROUTING -s {self.gcs_ip} -j DNAT --to-destination {self.backup_ip}"
        self._run_cmd(cmd)
        
        print(f"[MTD] GCS traffic redirected to Backup Node: {self.backup_ip}")