#!/bin/bash
# gcs_discovery.sh - Ground Control Station Discovery Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/gcs_discovery.sh
# Purpose: Locate and identify Ground Control Stations via MAVLink traffic analysis

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Ground Control Station Discovery"

# Network configurations
DOCKER_NETWORK="10.13.0.0/24"
WIFI_NETWORK="192.168.13.0/24"
MAVLINK_PORTS=(14550 14551 14552 5760 5762 5763)

# Known GCS IP patterns
DOCKER_GCS_IPS=("10.13.0.4")
WIFI_GCS_IPS=("192.168.13.14")
COMPANION_IPS=("10.13.0.3" "192.168.13.1")

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}    Ground Control Station Discovery       ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_gcs_discovery() {
    local capture_duration=${1:-60}  # Default 1 minute capture
    local analysis_mode=${2:-both}   # both, docker, wifi
    
    log_info "Starting Ground Control Station discovery attack"
    log_info "Capture duration: ${capture_duration} seconds"
    log_info "Analysis mode: $analysis_mode"
    
    # Check environment and tools
    if ! check_prerequisites; then
        return 1
    fi
    
    local networks_to_scan=()
    case "$analysis_mode" in
        "docker")
            networks_to_scan=("$DOCKER_NETWORK")
            ;;
        "wifi") 
            networks_to_scan=("$WIFI_NETWORK")
            ;;
        "both"|*)
            networks_to_scan=("$DOCKER_NETWORK" "$WIFI_NETWORK")
            ;;
    esac
    
    local gcs_found=false
    
    for network in "${networks_to_scan[@]}"; do
        echo -e "\n${BLUE}Analyzing network: $network${NC}"
        
        if analyze_network_for_gcs "$network" "$capture_duration"; then
            gcs_found=true
        fi
    done
    
    if $gcs_found; then
        log_success "GCS discovery attack completed - Ground Control Stations identified"
        return 0
    else
        log_warning "GCS discovery attack completed - No Ground Control Stations found"
        return 1
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    local required_tools=("nmap" "tshark")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install with: sudo apt-get install nmap tshark"
        return 1
    fi
    
    # Check network interfaces
    local has_network=false
    
    if ip addr show | grep -q "10.13.0"; then
        log_success "Docker bridge network detected"
        has_network=true
    fi
    
    if ip addr show | grep -q "192.168.13"; then
        log_success "WiFi network detected"
        has_network=true
    fi
    
    if ! $has_network; then
        log_warning "No DVD networks detected - results may be limited"
    fi
    
    return 0
}

analyze_network_for_gcs() {
    local network="$1"
    local capture_duration="$2"
    local gcs_found=false
    
    # Step 1: Host discovery
    log_info "Step 1: Discovering active hosts on $network"
    local active_hosts
    active_hosts=$(discover_gcs_hosts "$network")
    
    if [ -z "$active_hosts" ]; then
        log_warning "No active hosts found on $network"
        return 1
    fi
    
    echo -e "${GREEN}Active hosts discovered:${NC}"
    echo "$active_hosts" | while read -r host; do
        echo "  • $host"
    done
    
    # Step 2: MAVLink traffic capture and analysis
    log_info "Step 2: Capturing and analyzing MAVLink traffic"
    if capture_and_analyze_mavlink "$network" "$capture_duration" "$active_hosts"; then
        gcs_found=true
    fi
    
    $gcs_found && return 0 || return 1
}

discover_gcs_hosts() {
    local network="$1"
    
    echo -e "${YELLOW}Scanning for active hosts...${NC}"
    
    # Set exclusion IPs based on network
    local exclude_ips=""
    case "$network" in
        "10.13.0.0/24")
            exclude_ips="--exclude 10.13.0.1,10.13.0.5"
            ;;
        "192.168.13.0/24")
            exclude_ips="--exclude 192.168.13.10"
            ;;
    esac
    
    # Host discovery
    nmap -sn $network $exclude_ips 2>/dev/null | \
        grep -oP '(?<=Nmap scan report for )[0-9.]+' | \
        head -20  # Limit results for performance
}

capture_and_analyze_mavlink() {
    local network="$1"
    local duration="$2"
    local active_hosts="$3"
    local timestamp=$(date +%s)
    local capture_file="/tmp/gcs_mavlink_$timestamp.pcap"
    local gcs_identified=false
    
    # Determine network interface for capture
    local capture_interface
    capture_interface=$(get_capture_interface "$network")
    
    if [ -z "$capture_interface" ]; then
        log_error "No suitable interface found for packet capture"
        return 1
    fi
    
    log_info "Using interface: $capture_interface"
    
    # Start packet capture
    echo -e "${YELLOW}Starting MAVLink traffic capture...${NC}"
    
    # Build tshark filter for MAVLink traffic
    local mavlink_filter="udp and ("
    local first_port=true
    for port in "${MAVLINK_PORTS[@]}"; do
        if [ "$first_port" = true ]; then
            mavlink_filter+="port $port"
            first_port=false
        else
            mavlink_filter+=" or port $port"
        fi
    done
    mavlink_filter+=")"
    
    # Start capture in background
    tshark -i "$capture_interface" -f "$mavlink_filter" -w "$capture_file" -q &
    local capture_pid=$!
    
    # Wait for capture to start
    sleep 2
    
    # Generate traffic if possible
    log_info "Generating MAVLink traffic..."
    stimulate_mavlink_traffic "$network" &
    local stimulate_pid=$!
    
    # Monitor capture progress
    monitor_mavlink_capture "$duration"
    
    # Stop capture and traffic generation
    kill $capture_pid $stimulate_pid 2>/dev/null
    sleep 2
    
    # Analyze captured traffic
    if [ -f "$capture_file" ] && [ -s "$capture_file" ]; then
        log_info "Step 3: Analyzing captured MAVLink traffic"
        if analyze_mavlink_traffic "$capture_file" "$network"; then
            gcs_identified=true
        fi
    else
        log_warning "No MAVLink traffic captured"
    fi
    
    # Cleanup
    rm -f "$capture_file" 2>/dev/null
    
    $gcs_identified && return 0 || return 1
}

get_capture_interface() {
    local network="$1"
    
    # For Docker network, use docker bridge interface
    if [[ "$network" == "10.13.0.0/24" ]]; then
        # Find docker bridge interface
        local docker_iface=$(ip route | grep "10.13.0" | awk '{print $3}' | head -1)
        if [ -n "$docker_iface" ]; then
            echo "$docker_iface"
            return 0
        fi
        
        # Fallback to common docker interfaces
        for iface in docker0 br-* eth0; do
            if ip link show "$iface" >/dev/null 2>&1; then
                echo "$iface"
                return 0
            fi
        done
    fi
    
    # For WiFi network, use wireless interface
    if [[ "$network" == "192.168.13.0/24" ]]; then
        local wifi_iface=$(get_wireless_interface)
        if [ -n "$wifi_iface" ]; then
            echo "$wifi_iface"
            return 0
        fi
    fi
    
    # Default to any available interface
    local default_iface=$(ip route | grep default | awk '{print $5}' | head -1)
    if [ -n "$default_iface" ]; then
        echo "$default_iface"
        return 0
    fi
    
    return 1
}

stimulate_mavlink_traffic() {
    local network="$1"
    
    # Try to generate some network activity to stimulate MAVLink traffic
    # This is a passive approach - just ping potential GCS hosts
    
    local target_ips=()
    case "$network" in
        "10.13.0.0/24")
            target_ips=("${DOCKER_GCS_IPS[@]}" "${COMPANION_IPS[@]}")
            ;;
        "192.168.13.0/24")
            target_ips=("${WIFI_GCS_IPS[@]}" "${COMPANION_IPS[@]}")
            ;;
    esac
    
    for ip in "${target_ips[@]}"; do
        ping -c 3 -i 2 "$ip" >/dev/null 2>&1 &
    done
    
    # Try to connect to common MAVLink ports to trigger responses
    for ip in "${target_ips[@]}"; do
        for port in "${MAVLINK_PORTS[@]}"; do
            timeout 1 nc -u -z "$ip" "$port" 2>/dev/null &
        done
    done
    
    wait
}

monitor_mavlink_capture() {
    local duration="$1"
    
    echo -e "${YELLOW}Capturing MAVLink traffic...${NC}"
    
    for ((i=1; i<=duration; i++)); do
        echo -ne "\rCapturing... [$i/$duration seconds]"
        sleep 1
    done
    echo ""
}

analyze_mavlink_traffic() {
    local capture_file="$1"
    local network="$2"
    local gcs_found=false
    
    echo -e "${YELLOW}Analyzing captured packets...${NC}"
    
    # Extract unique IP conversations from the capture
    local conversations=$(tshark -r "$capture_file" -T fields -e ip.src -e ip.dst 2>/dev/null | sort -u)
    
    if [ -z "$conversations" ]; then
        log_warning "No IP conversations found in capture"
        return 1
    fi
    
    echo -e "${GREEN}MAVLink traffic conversations detected:${NC}"
    
    # Analyze conversations to identify GCS patterns
    local potential_gcs=()
    local companion_ips=()
    
    while IFS=$'\t' read -r src_ip dst_ip; do
        [ -z "$src_ip" ] || [ -z "$dst_ip" ] && continue
        
        echo "  • $src_ip ↔ $dst_ip"
        
        # Check if this matches known GCS patterns
        case "$network" in
            "10.13.0.0/24")
                if [[ "$src_ip" == "10.13.0.4" ]] || [[ "$dst_ip" == "10.13.0.4" ]]; then
                    potential_gcs+=("10.13.0.4")
                fi
                if [[ "$src_ip" == "10.13.0.3" ]] || [[ "$dst_ip" == "10.13.0.3" ]]; then
                    companion_ips+=("10.13.0.3")
                fi
                ;;
            "192.168.13.0/24")
                if [[ "$src_ip" == "192.168.13.14" ]] || [[ "$dst_ip" == "192.168.13.14" ]]; then
                    potential_gcs+=("192.168.13.14")
                fi
                if [[ "$src_ip" == "192.168.13.1" ]] || [[ "$dst_ip" == "192.168.13.1" ]]; then
                    companion_ips+=("192.168.13.1")
                fi
                ;;
        esac
    done <<< "$conversations"
    
    # Analyze packet counts and directions to confirm GCS behavior
    if [ ${#potential_gcs[@]} -gt 0 ]; then
        echo -e "\n${GREEN}🎯 Ground Control Stations identified:${NC}"
        
        for gcs_ip in "${potential_gcs[@]}"; do
            # Count packets from and to this GCS
            local from_gcs=$(tshark -r "$capture_file" -Y "ip.src == $gcs_ip" 2>/dev/null | wc -l)
            local to_gcs=$(tshark -r "$capture_file" -Y "ip.dst == $gcs_ip" 2>/dev/null | wc -l)
            
            echo "  🚁 GCS: $gcs_ip"
            echo "    • Commands sent: $from_gcs packets"
            echo "    • Telemetry received: $to_gcs packets"
            
            # Analyze traffic patterns
            analyze_gcs_traffic_patterns "$capture_file" "$gcs_ip"
            
            gcs_found=true
        done
    fi
    
    if [ ${#companion_ips[@]} -gt 0 ]; then
        echo -e "\n${BLUE}📡 Companion computers detected:${NC}"
        for comp_ip in "${companion_ips[@]}"; do
            local comp_packets=$(tshark -r "$capture_file" -Y "ip.src == $comp_ip or ip.dst == $comp_ip" 2>/dev/null | wc -l)
            echo "  • Companion: $comp_ip ($comp_packets packets)"
        done
    fi
    
    $gcs_found && return 0 || return 1
}

analyze_gcs_traffic_patterns() {
    local capture_file="$1"
    local gcs_ip="$2"
    
    # Try to identify MAVLink message types if possible
    local gcs_filter="ip.src == $gcs_ip"
    local message_analysis=$(tshark -r "$capture_file" -Y "$gcs_filter" -T fields -e udp.dstport 2>/dev/null | sort | uniq -c | sort -nr)
    
    if [ -n "$message_analysis" ]; then
        echo "    • Port usage:"
        echo "$message_analysis" | head -3 | while read -r count port; do
            local port_desc="Unknown"
            case "$port" in
                14550) port_desc="Flight Controller" ;;
                14551) port_desc="Ground Control" ;;
                5760) port_desc="SITL Connection" ;;
            esac
            echo "      - Port $port: $count packets ($port_desc)"
        done
    fi
}

# Main execution function
main() {
    print_attack_banner
    
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Execute attack
    execute_gcs_discovery "$@"
    exit $?
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi