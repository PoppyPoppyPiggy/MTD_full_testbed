#!/bin/bash
# camera_discovery.sh - Camera Stream Discovery Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/camera_discovery.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Camera Stream Discovery"
LOG_FILE="$(get_log_dir)/camera_discovery.log"

# Target IPs
TARGETS=("10.13.0.2" "10.13.0.3" "10.13.0.4" "10.13.0.5")

# Video streaming ports
VIDEO_PORTS=(554 8554 1935 8000 8080 5000 3000 9002)

print_attack_banner() {
    echo -e "${CYAN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        Camera Stream Discovery       ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════╝${NC}"
}

execute_attack() {
    log_info "Starting Camera Stream Discovery"
    
    local ioc_file="/tmp/stream_iocs.txt"
    > "$ioc_file"
    
    local discovered_streams=0
    
    for target in "${TARGETS[@]}"; do
        log_info "Scanning $target for video streams..."
        
        # RTSP stream discovery
        discover_rtsp_streams "$target" "$ioc_file"
        
        # HTTP-based streams
        discover_http_streams "$target" "$ioc_file" 
        
        # MJPEG streams
        discover_mjpeg_streams "$target" "$ioc_file"
    done
    
    discovered_streams=$(grep -c "STREAM:" "$ioc_file" 2>/dev/null || echo "0")
    
    if [ "$discovered_streams" -gt 0 ]; then
        log_success "Found $discovered_streams video streams"
        show_discovered_streams "$ioc_file"
    else
        log_warning "No video streams discovered"
    fi
    
    return 0
}

discover_rtsp_streams() {
    local target="$1"
    local ioc_file="$2"
    
    local rtsp_ports=(554 8554 1935)
    
    for port in "${rtsp_ports[@]}"; do
        if is_port_open "$target" "$port"; then
            echo -e "${BLUE}[*] Testing RTSP on $target:$port${NC}"
            
            test_rtsp_connection "$target" "$port" "$ioc_file"
        fi
    done
}

test_rtsp_connection() {
    local host="$1"
    local port="$2"
    local ioc_file="$3"
    
    # RTSP connection tester
    cat > "/tmp/rtsp_tester_${host}_${port}.py" << PYEOF
#!/usr/bin/env python3
import socket
import sys
import time

def test_rtsp_connection(host, port):
    """Test RTSP connection and discover streams"""
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        
        # RTSP OPTIONS request
        options_request = f"OPTIONS rtsp://{host}:{port}/ RTSP/1.0\\r\\nCSeq: 1\\r\\nUser-Agent: DVD-Scanner\\r\\n\\r\\n"
        sock.send(options_request.encode())
        
        response = sock.recv(4096).decode('utf-8', errors='ignore')
        
        if 'RTSP/1.0 200 OK' in response:
            print(f"RTSP_SERVER_CONFIRMED:{host}:{port}")
            
            # Extract supported methods
            if 'Public:' in response:
                methods_line = [line for line in response.split('\\n') if 'Public:' in line]
                if methods_line:
                    methods = methods_line[0].split('Public:')[1].strip()
                    print(f"RTSP_METHODS:{host}:{port}:{methods}")
            
            # Try common RTSP paths
            common_paths = [
                '/',
                '/live',  
                '/stream',
                '/video',
                '/cam1',
                '/camera',
                '/mjpeg',
                '/h264',
                '/drone_stream'
            ]
            
            for path in common_paths:
                test_rtsp_stream_path(host, port, path)
        
        sock.close()
        
    except Exception as e:
        print(f"RTSP_ERROR:{host}:{port}:{e}")

def test_rtsp_stream_path(host, port, path):
    """Test specific RTSP stream path"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        
        # DESCRIBE request for stream path
        describe_request = f"DESCRIBE rtsp://{host}:{port}{path} RTSP/1.0\\r\\nCSeq: 2\\r\\nAccept: application/sdp\\r\\n\\r\\n"
        sock.send(describe_request.encode())
        
        response = sock.recv(4096).decode('utf-8', errors='ignore')
        
        if 'RTSP/1.0 200 OK' in response and 'Content-Type: application/sdp' in response:
            print(f"RTSP_STREAM_FOUND:rtsp://{host}:{port}{path}")
            
            # Extract SDP information
            if 'm=video' in response:
                print(f"RTSP_VIDEO_STREAM:rtsp://{host}:{port}{path}")
            if 'm=audio' in response:
                print(f"RTSP_AUDIO_STREAM:rtsp://{host}:{port}{path}")
        
        sock.close()
        
    except:
        pass

if __name__ == "__main__":
    test_rtsp_connection("$host", $port)
PYEOF
    
    local result=$(python3 "/tmp/rtsp_tester_${host}_${port}.py" 2>/dev/null)
    
    if [[ "$result" == *"RTSP_SERVER_CONFIRMED"* ]]; then
        echo -e "${GREEN}   ✓ RTSP server confirmed${NC}"
        echo "$result" >> "$ioc_file"
        
        # Extract stream URLs
        echo "$result" | grep "RTSP_STREAM_FOUND" | while read stream_line; do
            local stream_url=$(echo "$stream_line" | cut -d: -f2-)
            echo "STREAM:RTSP:$stream_url" >> "$ioc_file"
            echo -e "${GREEN}   📹 Stream: $stream_url${NC}"
        done
    fi
    
    # Cleanup
    rm -f "/tmp/rtsp_tester_${host}_${port}.py"
}

discover_http_streams() {
    local target="$1"
    local ioc_file="$2"
    
    local http_ports=(8000 8080 5000 3000 80 443)
    
    for port in "${http_ports[@]}"; do
        if is_port_open "$target" "$port"; then
            echo -e "${BLUE}[*] Testing HTTP streams on $target:$port${NC}"
            
            test_http_video_endpoints "$target" "$port" "$ioc_file"
        fi
    done
}

test_http_video_endpoints() {
    local host="$1"
    local port="$2"
    local ioc_file="$3"
    
    local video_paths=(
        "/video"
        "/stream"  
        "/live"
        "/mjpeg"
        "/camera"
        "/cam"
        "/webcam"
        "/video.mjpg"
        "/axis-cgi/mjpg/video.cgi"
        "/cgi-bin/viewer/video.jpg"
        "/drone/video"
        "/api/video"
    )
    
    for path in "${video_paths[@]}"; do
        local url="http://$host:$port$path"
        
        # Test for video content
        local headers=$(timeout 5 curl -s -I "$url" 2>/dev/null)
        
        if [[ $? -eq 0 ]] && [[ -n "$headers" ]]; then
            local content_type=$(echo "$headers" | grep -i "content-type" | head -1 | cut -d: -f2 | tr -d ' \r\n')
            local http_status=$(echo "$headers" | head -1 | awk '{print $2}')
            
            if [[ "$http_status" == "200" ]]; then
                case "$content_type" in
                    *"video"*|*"mjpeg"*|*"jpeg"*)
                        echo -e "${GREEN}   📹 Video stream: $url${NC}"
                        echo "STREAM:HTTP:$url" >> "$ioc_file"
                        echo "HTTP_VIDEO_CONTENT:$host:$port:$path:$content_type" >> "$ioc_file"
                        ;;
                    *"octet-stream"*|*"binary"*)
                        # Might be a video stream
                        echo -e "${YELLOW}   🔍 Potential stream: $url${NC}"
                        echo "POTENTIAL_STREAM:HTTP:$url" >> "$ioc_file"
                        ;;
                esac
            fi
        fi
    done
}

discover_mjpeg_streams() {
    local target="$1"
    local ioc_file="$2"
    
    echo -e "${BLUE}[*] Scanning for MJPEG streams on $target${NC}"
    
    # MJPEG stream scanner
    cat > "/tmp/mjpeg_scanner_${target}.py" << PYEOF
#!/usr/bin/env python3
import socket
import sys
import time

def scan_mjpeg_streams(host):
    """Scan for MJPEG streams"""
    
    ports = [8000, 8080, 8081, 8090, 9000]
    mjpeg_paths = [
        '/mjpeg',
        '/video.mjpeg', 
        '/stream.mjpeg',
        '/camera.mjpeg',
        '/cam.mjpeg'
    ]
    
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((host, port))
            sock.close()
            
            # Port is open, test MJPEG paths
            for path in mjpeg_paths:
                test_mjpeg_path(host, port, path)
                
        except:
            continue

def test_mjpeg_path(host, port, path):
    """Test specific MJPEG path"""
    try:
        import urllib.request
        import urllib.error
        
        url = f"http://{host}:{port}{path}"
        
        # Create request with video-accepting headers
        req = urllib.request.Request(url)
        req.add_header('Accept', 'multipart/x-mixed-replace,image/jpeg,*/*')
        req.add_header('User-Agent', 'DVD-Scanner')
        
        try:
            response = urllib.request.urlopen(req, timeout=5)
            content_type = response.headers.get('Content-Type', '')
            
            if 'multipart/x-mixed-replace' in content_type or 'image/jpeg' in content_type:
                print(f"MJPEG_STREAM_FOUND:{url}")
                
                # Try to read first few bytes to confirm
                data = response.read(1024)
                if b'\\xff\\xd8' in data:  # JPEG header
                    print(f"MJPEG_CONFIRMED:{url}")
            
            response.close()
            
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"MJPEG_AUTH_REQUIRED:{url}")
        except:
            pass
            
    except:
        pass

if __name__ == "__main__":
    scan_mjpeg_streams("$target")
PYEOF
    
    local result=$(python3 "/tmp/mjpeg_scanner_${target}.py" 2>/dev/null)
    
    if [[ -n "$result" ]]; then
        echo "$result" >> "$ioc_file"
        
        echo "$result" | grep "MJPEG_STREAM_FOUND" | while read stream_line; do
            local stream_url=$(echo "$stream_line" | cut -d: -f2-)
            echo "STREAM:MJPEG:$stream_url" >> "$ioc_file"
            echo -e "${GREEN}   📹 MJPEG Stream: $stream_url${NC}"
        done
    fi
    
    # Cleanup
    rm -f "/tmp/mjpeg_scanner_${target}.py"
}

show_discovered_streams() {
    local ioc_file="$1"
    
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║        Discovered Streams            ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    
    if [ -f "$ioc_file" ]; then
        grep "STREAM:" "$ioc_file" | while read stream_ioc; do
            local stream_type=$(echo "$stream_ioc" | cut -d: -f2)
            local stream_url=$(echo "$stream_ioc" | cut -d: -f3-)
            
            case "$stream_type" in
                "RTSP")
                    echo -e "${CYAN}📹 RTSP Stream: ${WHITE}$stream_url${NC}"
                    ;;
                "HTTP")
                    echo -e "${BLUE}🌐 HTTP Stream: ${WHITE}$stream_url${NC}"
                    ;;
                "MJPEG")
                    echo -e "${YELLOW}📸 MJPEG Stream: ${WHITE}$stream_url${NC}"
                    ;;
            esac
        done
        
        echo ""
        echo -e "${GREEN}💡 Testing streams:${NC}"
        echo -e "${CYAN}   RTSP: ffplay <rtsp_url>${NC}"
        echo -e "${CYAN}   HTTP: curl -v <http_url>${NC}"
        echo -e "${CYAN}   Browser: <http_url>${NC}"
    fi
}

# Main execution
main() {
    print_attack_banner
    
    check_required_tools "curl" "python3"
    
    execute_attack "$@"
}

main "$@"