#!/bin/bash
# component_enum.sh - Drone Component Enumeration Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/component_enum.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Drone Component Enumeration"
LOG_FILE="$(get_log_dir)/component_enum.log"

# DVD Networks
DVD_NETWORKS=("10.13.0.0/24" "192.168.13.0/24")

print_attack_banner() {
    echo -e "${CYAN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║      Component Enumeration            ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════╝${NC}"
}

execute_attack() {
    log_info "Starting Drone Component Enumeration"
    
    local ioc_file="/tmp/component_iocs.txt"
    > "$ioc_file"
    
    for network in "${DVD_NETWORKS[@]}"; do
        log_info "Scanning network: $network"
        scan_network "$network" "$ioc_file"
    done
    
    # Additional service discovery
    discover_web_services "$ioc_file"
    discover_rtsp_streams "$ioc_file"
    
    local total_components=$(grep -c "COMPONENT:" "$ioc_file" 2>/dev/null || echo "0")
    log_success "Component enumeration completed. Found $total_components components"
    
    return 0
}

scan_network() {
    local network="$1"
    local ioc_file="$2"
    
    log_info "Running comprehensive scan on $network"
    
    local nmap_output="$(get_output_dir)/nmap_$(echo "$network" | tr '/' '_')_$(date +%s).xml"
    
    # Comprehensive nmap scan
    nmap -sS -sU -sV -O --script=default,discovery,vuln \
         --version-intensity 5 \
         -T4 -oX "$nmap_output" "$network" 2>/dev/null &
    
    local nmap_pid=$!
    
    # Progress indicator
    echo -ne "${BLUE}[*] Scanning in progress"
    while kill -0 $nmap_pid 2>/dev/null; do
        echo -ne "."
        sleep 2
    done
    echo -e " Done!${NC}"
    
    wait $nmap_pid
    
    if [ -f "$nmap_output" ]; then
        parse_nmap_results "$nmap_output" "$ioc_file"
    else
        log_error "Nmap scan failed for $network"
    fi
}

parse_nmap_results() {
    local xml_file="$1"
    local ioc_file="$2"
    
    # Python XML parser
    cat > "/tmp/nmap_parser.py" << 'PYEOF'
#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import sys

def parse_nmap_xml(xml_file, ioc_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        components = []
        
        for host in root.findall('host'):
            if host.find('status').get('state') != 'up':
                continue
                
            addr_elem = host.find('address')
            if addr_elem is None:
                continue
                
            ip = addr_elem.get('addr')
            
            # Host info
            host_info = {
                'ip': ip,
                'hostname': '',
                'os': '',
                'ports': [],
                'services': []
            }
            
            # Hostname
            hostnames = host.find('hostnames')
            if hostnames is not None:
                hostname_elem = hostnames.find('hostname')
                if hostname_elem is not None:
                    host_info['hostname'] = hostname_elem.get('name', '')
            
            # OS detection
            os_elem = host.find('os')
            if os_elem is not None:
                osmatch = os_elem.find('osmatch')
                if osmatch is not None:
                    host_info['os'] = osmatch.get('name', '')
            
            # Ports and services
            ports_elem = host.find('ports')
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    state = port.find('state')
                    if state is None or state.get('state') != 'open':
                        continue
                    
                    port_id = port.get('portid')
                    protocol = port.get('protocol')
                    
                    service_elem = port.find('service')
                    service_info = {
                        'port': port_id,
                        'protocol': protocol,
                        'name': service_elem.get('name', 'unknown') if service_elem is not None else 'unknown',
                        'product': service_elem.get('product', '') if service_elem is not None else '',
                        'version': service_elem.get('version', '') if service_elem is not None else ''
                    }
                    
                    host_info['ports'].append(f"{port_id}/{protocol}")
                    host_info['services'].append(service_info)
            
            components.append(host_info)
        
        # Write results
        with open(ioc_file, 'a') as f:
            for comp in components:
                # Identify component type
                comp_type = identify_component_type(comp)
                
                f.write(f"COMPONENT:{comp['ip']}:{comp_type}\n")
                
                if comp['hostname']:
                    f.write(f"HOSTNAME:{comp['ip']}:{comp['hostname']}\n")
                
                if comp['os']:
                    f.write(f"OS_INFO:{comp['ip']}:{comp['os']}\n")
                
                for service in comp['services']:
                    f.write(f"SERVICE:{comp['ip']}:{service['port']}:{service['name']}\n")
                    
                    if service['product']:
                        f.write(f"SERVICE_PRODUCT:{comp['ip']}:{service['port']}:{service['product']}\n")
                
                # Print results
                print(f"🔍 {comp['ip']} ({comp_type})")
                if comp['hostname']:
                    print(f"   Hostname: {comp['hostname']}")
                if comp['os']:
                    print(f"   OS: {comp['os']}")
                
                for service in comp['services']:
                    service_desc = f"{service['name']}"
                    if service['product']:
                        service_desc += f" ({service['product']}"
                        if service['version']:
                            service_desc += f" {service['version']}"
                        service_desc += ")"
                    
                    print(f"   📡 {service['port']}/{service['protocol']}: {service_desc}")
                
                print()
        
        return True
        
    except Exception as e:
        print(f"Error parsing XML: {e}")
        return False

def identify_component_type(host_info):
    """Identify drone component type based on services and ports"""
    services = [s['name'].lower() for s in host_info['services']]
    ports = [int(s['port']) for s in host_info['services']]
    
    # Flight Controller patterns
    if 14550 in ports or 14551 in ports or any('mavlink' in s for s in services):
        return 'flight_controller'
    
    # Ground Control Station patterns  
    if 14550 in ports and any('http' in s for s in services):
        return 'ground_control_station'
    
    # Companion Computer patterns
    if any(p in ports for p in [5000, 8080, 22]) and any('http' in s or 'ssh' in s for s in services):
        return 'companion_computer'
    
    # Simulator patterns
    if any(p in ports for p in [8000, 11345]) or any('gazebo' in s for s in services):
        return 'simulator'
    
    # Camera/Video streaming
    if any(p in ports for p in [554, 8554, 1935]) or any('rtsp' in s for s in services):
        return 'camera_system'
    
    return 'unknown_component'

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 nmap_parser.py <xml_file> <ioc_file>")
        sys.exit(1)
    
    xml_file, ioc_file = sys.argv[1], sys.argv[2]
    parse_nmap_xml(xml_file, ioc_file)
PYEOF
    
    python3 "/tmp/nmap_parser.py" "$xml_file" "$ioc_file"
}

discover_web_services() {
    local ioc_file="$1"
    
    log_info "Discovering web services and APIs"
    
    local web_ports=(80 443 8000 8080 8443 5000 3000 9000)
    local targets=("10.13.0.2" "10.13.0.3" "10.13.0.4" "10.13.0.5")
    
    for target in "${targets[@]}"; do
        for port in "${web_ports[@]}"; do
            if is_port_open "$target" "$port"; then
                discover_web_endpoints "$target" "$port" "$ioc_file"
            fi
        done
    done
}

discover_web_endpoints() {
    local host="$1"
    local port="$2"
    local ioc_file="$3"
    
    local base_url="http://$host:$port"
    
    # Common endpoints to test
    local endpoints=("/" "/api" "/status" "/config" "/admin" "/debug" "/info" "/version" "/docs" "/swagger")
    
    echo -e "${BLUE}[*] Testing web endpoints on $host:$port${NC}"
    
    for endpoint in "${endpoints[@]}"; do
        local url="$base_url$endpoint"
        local response=$(timeout 5 curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
        
        if [[ "$response" =~ ^[2-3][0-9]{2}$ ]]; then
            echo -e "${GREEN}   ✓ $endpoint (HTTP $response)${NC}"
            echo "WEB_ENDPOINT:$host:$port:$endpoint:$response" >> "$ioc_file"
            
            # Check for interesting content
            if [[ "$endpoint" == "/api" ]] || [[ "$endpoint" == "/swagger" ]]; then
                echo "API_ENDPOINT:$host:$port:$endpoint" >> "$ioc_file"
            fi
        fi
    done
}

discover_rtsp_streams() {
    local ioc_file="$1"
    
    log_info "Discovering RTSP video streams"
    
    local rtsp_ports=(554 8554 1935)
    local targets=("10.13.0.2" "10.13.0.3" "10.13.0.4" "10.13.0.5")
    
    for target in "${targets[@]}"; do
        for port in "${rtsp_ports[@]}"; do
            if is_port_open "$target" "$port"; then
                test_rtsp_stream "$target" "$port" "$ioc_file"
            fi
        done
    done
}

test_rtsp_stream() {
    local host="$1"
    local port="$2"
    local ioc_file="$3"
    
    echo -e "${BLUE}[*] Testing RTSP on $host:$port${NC}"
    
    # Python RTSP tester
    cat > "/tmp/rtsp_test.py" << PYEOF
#!/usr/bin/env python3
import socket
import sys

def test_rtsp(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        
        # RTSP OPTIONS request
        request = f"OPTIONS rtsp://{host}:{port}/ RTSP/1.0\\r\\nCSeq: 1\\r\\n\\r\\n"
        sock.send(request.encode())
        
        response = sock.recv(1024).decode()
        
        if 'RTSP/1.0' in response:
            print(f"RTSP_CONFIRMED:{host}:{port}")
            if 'Public:' in response:
                methods = response.split('Public:')[1].split('\\r\\n')[0].strip()
                print(f"RTSP_METHODS:{host}:{port}:{methods}")
        
        sock.close()
    except Exception as e:
        print(f"RTSP_ERROR:{host}:{port}:{e}")

if __name__ == "__main__":
    test_rtsp("$host", $port)
PYEOF
    
    local result=$(python3 "/tmp/rtsp_test.py")
    
    if [[ "$result" == *"RTSP_CONFIRMED"* ]]; then
        echo -e "${GREEN}   ✓ RTSP stream confirmed${NC}"
        echo "$result" >> "$ioc_file"
    fi
}

# Main execution
main() {
    print_attack_banner
    
    check_required_tools "nmap" "curl" "python3"
    
    execute_attack "$@"
}

main "$@"