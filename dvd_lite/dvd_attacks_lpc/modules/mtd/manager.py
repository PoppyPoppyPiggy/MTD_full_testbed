import os
import json
import random
import time
import threading
import subprocess

# simulator-lite 컨테이너 내부 경로 기준
STATE_FILE = "/shared/mtd_state.json"
HIT_LOG_FILE = "/shared/hit.log"
IFACE = "eth0" 

class MTDManager:
    def __init__(self, evaluator, effects_logger, interval=15, ip_range="10.13.100-110", port_range="10000-11000"):
        self.evaluator = evaluator
        self.effects_logger = effects_logger
        self.interval = interval
        
        ip_parts = ip_range.split('-')
        self.ip_base = ".".join(ip_parts[0].split('.')[:2])
        self.ip_subnet_start = int(ip_parts[0].split('.')[2])
        self.ip_subnet_end = int(ip_parts[1]) if len(ip_parts) > 1 else self.ip_subnet_start
        self.port_range_start, self.port_range_end = [int(p) for p in port_range.split('-')]

        self.current_surface = {}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run_loop)
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    def _run_command(self, cmd):
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)

    def start(self):
        print("MTD Manager: Starting inside simulator-lite...")
        try:
            self._run_command(f"ip addr flush dev {IFACE} label {IFACE}:*")
            self._run_command("iptables -t nat -F PREROUTING")
            # simulator-lite의 IP 포워딩 기능 활성화
            self._run_command("sysctl -w net.ipv4.ip_forward=1")
            # 히트 감지를 위한 iptables LOG 룰 추가
            self._run_command(f"iptables -A FORWARD -d {self.evaluator.target_drone_ip} -p tcp -j LOG --log-prefix '[HIT_DETECTED] '")
        except subprocess.CalledProcessError as e:
            print(f"Error during MTD Manager initialization: {e.stderr}")
            raise
        self.thread.start()

    def stop(self):
        print("MTD Manager: Stopping...")
        self.stop_event.set()
        self.thread.join()
        try:
            self._run_command(f"ip addr flush dev {IFACE} label {IFACE}:*")
            self._run_command("iptables -t nat -F PREROUTING")
            self._run_command("iptables -F FORWARD")
        except subprocess.CalledProcessError:
            pass # 컨테이너가 종료된 후에는 실패할 수 있음

    def _run_loop(self):
        while not self.stop_event.is_set():
            self.change_attack_surface()
            for _ in range(self.interval):
                if self.stop_event.is_set(): break
                # 히트 감지를 dmesg 로그 파싱으로 변경
                self.evaluator.check_hits_from_dmesg()
                time.sleep(1)

    def change_attack_surface(self):
        if self.current_surface:
            old_ip = self.current_surface['ip']
            old_port = self.current_surface['port']
            target_ip = self.current_surface['target_drone_ip']
            self._run_command(f"ip addr del {old_ip}/24 dev {IFACE}")
            self._run_command(f"iptables -t nat -D PREROUTING -d {old_ip} -p tcp --dport {old_port} -j DNAT --to-destination {target_ip}:{old_port}")

        new_subnet = random.randint(self.ip_subnet_start, self.ip_subnet_end)
        new_ip = f"{self.ip_base}.{new_subnet}.{random.randint(2, 254)}"
        new_port = random.randint(self.port_range_start, self.port_range_end)
        
        self.current_surface = {"ip": new_ip, "port": new_port, "target_drone_ip": self.evaluator.target_drone_ip}
        
        self._run_command(f"ip addr add {new_ip}/24 dev {IFACE}")
        self._run_command(f"iptables -t nat -A PREROUTING -d {new_ip} -p tcp --dport {new_port} -j DNAT --to-destination {self.evaluator.target_drone_ip}:{new_port}")
        
        with open(STATE_FILE, 'w') as f:
            json.dump(self.current_surface, f)
        
        print("\n" + "="*50)
        print(f"MTD ACTION: Attack surface changed to -> {new_ip}:{new_port}")
        print(f"(Traffic will be forwarded to {self.evaluator.target_drone_ip}:{new_port})")
        print("="*50 + "\n")
        
        self.effects_logger.record_effect("MTD_CHANGE", packet_loss=0.1, delay=50)
        time.sleep(0.1)
        self.effects_logger.record_effect("NETWORK_STABLE")
        self.evaluator.reset_due_to_mtd()

# dmesg를 파싱하여 히트를 감지하는 로직을 evaluator에 추가해야 함
# 여기서는 간단하게 기존 파일 기반 로직을 유지