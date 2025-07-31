#!/bin/bash
# drone_discovery.sh - Drone Network Discovery Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/drone_discovery.sh
# Purpose: Pure drone network discovery attack execution

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Drone Network Discovery"
TARGET_NETWORK="192.168.13.0/24"
DOCKER_NETWORK="10.13.0.0/24"
MAVLINK_PORTS=(14550 14551 14552 5760 5762 5763 14540 14560 14580)

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}      Drone Network Discovery Attack       ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_drone_discovery() {
    log_info "Starting drone network discovery attack"
    
    # Check environment
    check_environment
    
    local networks=("$TARGET_NETWORK" "$DOCKER_NETWORK")
    local success_count=0
    
    for network in "${networks[@]}"; do
        echo -e "\n${BLUE}Attacking network: $network${NC}"
        
        if attack_network "$network"; then
            ((success_count++))
        fi
    done
    
    if [ $success_count -gt 0 ]; then
        log_success "Drone discovery attack completed - found targets in $success_count networks"
        return 0
    else
        log_warning "Drone discovery attack completed - no drone services found"
        return 1
    fi
}

check_environment() {
    log_info "Checking environment..."
    
    # Check for DVD environment
    if ip addr show | grep -q "10.13.0"; then
        log_success "Docker bridge network detected"
    fi
    
    if docker ps 2>/dev/null | grep -q "dvd\|drone"; then
        log_success "DVD container environment detected"
    fi
    
    # Check required tools
    local required_tools=("nmap")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        return 1
    fi
    
    return 0
}

attack_network() {
    local network="$1"
    local found_targets=false
    
    # Step 1: Host discovery
    log_info "Step 1: Discovering hosts on $network"
    local active_hosts
    active_hosts=$(discover_hosts "$network")
    
    if [ -z "$active_hosts" ]; then
        log_warning "No active hosts found on $network"
        return 1
    fi
    
    echo -e "${GREEN}Active hosts found:${NC}"
    echo "$active_hosts" | while read -r host; do
        echo "  • $host"
    done
    
    # Step 2: MAVLink service discovery
    log_info "Step 2: Scanning for MAVLink services"
    if scan_mavlink_services "$network" "$active_hosts"; then
        found_targets=true
    fi
    
    # Step 3: Service fingerprinting
    log_info "Step 3: Fingerprinting drone services"
    if fingerprint_drone_services "$network"; then
        found_targets=true
    fi
    
    $found_targets && return 0 || return 1
}

discover_hosts() {
    local network="$1"
    
    # Set exclusion IPs
    local exclude_ips=""
    case "$network" in
        "10.13.0.0/24")
            exclude_ips="--exclude 10.13.0.1,10.13.0.5"
            ;;
        "192.168.13.0/24")
            exclude_ips="--exclude 192.168.13.10"
            ;;
    esac
    
    echo -e "${YELLOW}Scanning for active hosts...${NC}"
    
    # Host discovery using nmap
    nmap -sn $network $exclude_ips 2>/dev/null | \
        grep -oP '(?<=Nmap scan report for )[0-9.]+' | \
        head -20  # Limit to first 20 hosts for performance
}

scan_mavlink_services() {
    local network="$1"
    local active_hosts="$2"
    local services_found=false
    
    echo -e "${YELLOW}Scanning MAVLink ports...${NC}"
    
    local port_list=$(IFS=,; echo "${MAVLINK_PORTS[*]}")
    
    # Scan individual hosts first
    echo "$active_hosts" | while read -r host; do
        [ -z "$host" ] && continue
        
        echo -ne "\rScanning MAVLink on $host..."
        
        # UDP scan (primary MAVLink protocol)
        local udp_results=$(nmap -sU -p "$port_list" --open "$host" 2>/dev/null | grep -E "^[0-9]+/udp.*open")
        
        # TCP scan (some GCS use TCP)
        local tcp_results=$(nmap -sT -p "$port_list" --open "$host" 2>/dev/null | grep -E "^[0-9]+/tcp.*open")
        
        if [ -n "$udp_results" ] || [ -n "$tcp_results" ]; then
            echo -e "\n${GREEN}🎯 MAVLink services found on $host:${NC}"
            
            if [ -n "$udp_results" ]; then
                echo "$udp_results" | while read -r service; do
                    local port=$(echo "$service" | grep -oE '^[0-9]+')
                    local service_type=$(get_mavlink_service_type "$port")
                    echo "  • UDP/$port - $service_type"
                done
            fi
            
            if [ -n "$tcp_results" ]; then
                echo "$tcp_results" | while read -r service; do
                    local port=$(echo "$service" | grep -oE '^[0-9]+')
                    local service_type=$(get_mavlink_service_type "$port")
                    echo "  • TCP/$port - $service_type"
                done
            fi
            
            services_found=true
        fi
    done
    echo ""
    
    # Network-wide scan if no services found on individual hosts
    if [ "$services_found" = false ]; then
        echo -e "${CYAN}Performing network-wide MAVLink scan...${NC}"
        
        local exclude_ips=""
        case "$network" in
            "10.13.0.0/24") exclude_ips="--exclude 10.13.0.1,10.13.0.5" ;;
            "192.168.13.0/24") exclude_ips="--exclude 192.168.13.10" ;;
        esac
        
        local network_results=$(nmap -sU -sT -p "$port_list" --open $network $exclude_ips 2>/dev/null | grep -E "^[0-9]+/(udp|tcp).*open")
        
        if [ -n "$network_results" ]; then
            echo -e "${GREEN}🎯 MAVLink services found on network:${NC}"
            echo "$network_results" | while read -r service; do
                local port=$(echo "$service" | grep -oE '^[0-9]+')
                local protocol=$(echo "$service" | grep -oE '(tcp|udp)')
                local service_type=$(get_mavlink_service_type "$port")
                echo "  • $protocol/$port - $service_type"
            done
            services_found=true
        fi
    fi
    
    $services_found && return 0 || return 1
}

get_mavlink_service_type() {
    local port="$1"
    
    case "$port" in
        14550) echo "Flight Controller (Standard)" ;;
        14551) echo "Ground Control Station" ;;
        14552) echo "Companion Computer" ;;
        14540) echo "SITL Simulator (Primary)" ;;
        14560) echo "SITL Simulator (Secondary)" ;;
        14580) echo "MAVLink Router" ;;
        5760) echo "ArduPilot SITL" ;;
        5762) echo "Secondary GCS Connection" ;;
        5763) echo "MAVLink Relay Node" ;;
        *) echo "Unknown MAVLink Service" ;;
    esac
}

fingerprint_drone_services() {
    local network="$1"
    local services_found=false
    
    echo -e "${YELLOW}Fingerprinting drone services...${NC}"
    
    # Common drone-related ports
    local common_ports="22,23,80,443,8080,9000,5760,14550,14551,14552"
    
    local exclude_ips=""
    case "$network" in
        "10.13.0.0/24") exclude_ips="--exclude 10.13.0.1,10.13.0.5" ;;
        "192.168.13.0/24") exclude_ips="--exclude 192.168.13.10" ;;
    esac
    
    # Service version detection
    local fingerprint_results=$(nmap -sV -p "$common_ports" $network $exclude_ips 2>/dev/null)
    
    # Extract and display open services
    local open_services=$(echo "$fingerprint_results" | grep -E "^[0-9]+/(tcp|udp).*open")
    
    if [ -n "$open_services" ]; then
        echo -e "${GREEN}🔍 Services discovered:${NC}"
        echo "$open_services" | while read -r service; do
            echo "  • $service"
        done
        services_found=true
    fi
    
    # Check for drone-specific services
    if echo "$fingerprint_results" | grep -qi "ardupilot\|mavlink\|px4\|qgroundcontrol\|ros"; then
        echo -e "${GREEN}🎯 Drone-specific services detected:${NC}"
        echo "$fingerprint_results" | grep -i "ardupilot\|mavlink\|px4\|qgroundcontrol\|ros" | while read -r line; do
            echo "  🚁 $line"
        done
        services_found=true
    fi
    
    # Check for web interfaces (companion computers)
    if echo "$fingerprint_results" | grep -q ":80\|:8080\|:443"; then
        echo -e "${GREEN}🌐 Web interfaces found (potential companion computers)${NC}"
        echo "$fingerprint_results" | grep -E ":(80|8080|443).*open" | while read -r web_service; do
            echo "  • $web_service"
        done
        services_found=true
    fi
    
    $services_found && return 0 || return 1
}

# Main execution function
main() {
    print_attack_banner
    
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Check required tools
    if ! command -v nmap >/dev/null 2>&1; then
        log_error "nmap is required but not installed"
        log_info "Install with: sudo apt-get install nmap"
        exit 1
    fi
    
    # Execute attack
    execute_drone_discovery "$@"
    exit $?
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi