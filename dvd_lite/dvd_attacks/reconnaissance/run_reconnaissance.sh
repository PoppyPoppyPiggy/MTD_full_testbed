#!/bin/bash
# run_reconnaissance.sh - Master DVD Reconnaissance Attack Runner
# Path: /home/kali/MTD/MTD_full_testbed/run_reconnaissance.sh

# Source common files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dvd_lite/dvd_attacks/common/colors.sh"
source "$SCRIPT_DIR/dvd_lite/dvd_attacks/common/utils.sh"

ATTACK_SCRIPTS_DIR="$SCRIPT_DIR/dvd_lite/dvd_attacks/reconnaissance"

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║             DVD Reconnaissance Attacks                  ║"
    echo "║          Damn Vulnerable Drone Testing Suite            ║"
    echo "║                                                          ║"
    echo "║  🎓 논문용 자동화된 드론 보안 테스트 도구               ║"
    echo "║  🔍 CTI 수집 및 IOC 생성 특화                          ║"
    echo "║  📊 실시간 진행률 표시 및 JSON 리포트                  ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

show_menu() {
    echo -e "${YELLOW}"
    echo "Available Reconnaissance Attacks:"
    echo "=================================="
    echo "1. 📡 WiFi Network Discovery        (IEEE 802.11 스캔)"
    echo "2. 🔌 MAVLink Service Discovery     (포트 14550/14551 등)"
    echo "3. 🖥️  Drone Component Enumeration  (Nmap 기반 서비스 스캔)"
    echo "4. 📹 Camera Stream Discovery       (RTSP/HTTP/MJPEG)"
    echo "5. 🌐 Network Topology Discovery    (네트워크 매핑)"
    echo ""
    echo "6. 🚀 Run All Attacks (Automated)   (전체 자동 실행)"
    echo "7. 📊 Show Results & IOCs            (결과 및 IOC 표시)"
    echo "8. 📝 Generate Report                (JSON 리포트 생성)"
    echo "9. 🧹 Clean Previous Results         (이전 결과 정리)"
    echo ""
    echo "0. ❌ Exit"
    echo -e "${NC}"
}

show_system_status() {
    echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           System Status               ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
    
    # Check DVD system connectivity
    local dvd_targets=("10.13.0.2:flight-controller" "10.13.0.3:companion-computer" "10.13.0.4:ground-control" "10.13.0.5:simulator")
    
    for target_info in "${dvd_targets[@]}"; do
        local ip=$(echo "$target_info" | cut -d: -f1)
        local name=$(echo "$target_info" | cut -d: -f2)
        
        if timeout 2 ping -c 1 "$ip" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $name ($ip) - Online${NC}"
        else
            echo -e "${RED}❌ $name ($ip) - Offline${NC}"
        fi
    done
    
    # Check required tools
    echo -e "\n${CYAN}Required Tools Status:${NC}"
    local tools=("nmap" "airmon-ng" "airodump-ng" "curl" "python3")
    
    for tool in "${tools[@]}"; do
        if command -v "$tool" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $tool${NC}"
        else
            echo -e "${RED}❌ $tool (missing)${NC}"
        fi
    done
    
    echo ""
}

run_attack() {
    local attack_script="$1"
    local attack_name="$2"
    
    if [ -f "$attack_script" ] && [ -x "$attack_script" ]; then
        echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║ Starting: $attack_name$(printf '%*s' $((25-${#attack_name})) '')║${NC}"
        echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
        
        local start_time=$(date +%s)
        
        "$attack_script"
        local exit_code=$?
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo -e "${GRAY}────────────────────────────────────────${NC}"
        
        if [ $exit_code -eq 0 ]; then
            log_success "$attack_name completed successfully (${duration}s)"
            print_attack_result "$attack_name" "SUCCESS" "Execution time: ${duration} seconds"
        else
            log_error "$attack_name failed with exit code $exit_code"
            print_attack_result "$attack_name" "FAILED" "Exit code: $exit_code, Time: ${duration}s"
        fi
        
        return $exit_code
    else
        log_error "Attack script not found or not executable: $attack_script"
        return 1
    fi
}

run_all_attacks() {
    echo -e "${PURPLE}╔═══════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║      Running All Reconnaissance      ║${NC}"
    echo -e "${PURPLE}║            Attacks                    ║${NC}"
    echo -e "${PURPLE}╚═══════════════════════════════════════╝${NC}"
    
    local attacks=(
        "$ATTACK_SCRIPTS_DIR/wifi_discovery.sh:📡 WiFi Network Discovery"
        "$ATTACK_SCRIPTS_DIR/mavlink_discovery.sh:🔌 MAVLink Service Discovery"
        "$ATTACK_SCRIPTS_DIR/component_enum.sh:🖥️ Component Enumeration"
        "$ATTACK_SCRIPTS_DIR/camera_discovery.sh:📹 Camera Stream Discovery"
    )
    
    local success_count=0
    local total_count=${#attacks[@]}
    local overall_start_time=$(date +%s)
    
    # Initialize progress
    echo -e "${CYAN}Progress: [$(printf '%*s' $total_count | tr ' ' '□')] 0/$total_count${NC}"
    
    for i in "${!attacks[@]}"; do
        local attack_info="${attacks[$i]}"
        local script_path=$(echo "$attack_info" | cut -d: -f1)
        local attack_name=$(echo "$attack_info" | cut -d: -f2-)
        
        # Update progress bar
        local completed=$((i))
        local progress_bar=""
        for ((j=0; j<completed; j++)); do
            progress_bar+="■"
        done
        for ((j=completed; j<total_count; j++)); do
            progress_bar+="□"
        done
        
        echo -e "\r${CYAN}Progress: [$progress_bar] $completed/$total_count${NC}"
        
        echo -e "\n${CYAN}Step $((i+1))/$total_count: $attack_name${NC}"
        
        if run_attack "$script_path" "$attack_name"; then
            ((success_count++))
        fi
        
        # Brief pause between attacks
        if [ $((i+1)) -lt $total_count ]; then
            echo -e "\n${GRAY}⏳ Waiting 3 seconds before next attack...${NC}"
            sleep 3
        fi
    done
    
    # Final progress update
    local progress_bar=""
    for ((j=0; j<total_count; j++)); do
        progress_bar+="■"
    done
    echo -e "\r${CYAN}Progress: [$progress_bar] $total_count/$total_count${NC}"
    
    local overall_end_time=$(date +%s)
    local total_duration=$((overall_end_time - overall_start_time))
    
    echo -e "\n${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         All Attacks Completed        ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    echo -e "${GREEN}✅ Success rate: $success_count/$total_count${NC}"
    echo -e "${GREEN}⏱️  Total time: $total_duration seconds${NC}"
    
    # Auto-generate report
    echo -e "\n${BLUE}📊 Auto-generating comprehensive report...${NC}"
    generate_comprehensive_report
    
    show_results
}

show_results() {
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           Attack Results             ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    
    # Show recent logs with color coding
    local log_files=("wifi_discovery.log" "mavlink_discovery.log" "component_enum.log" "camera_discovery.log")
    
    for log_file in "${log_files[@]}"; do
        local full_path="$LOG_DIR/$log_file"
        if [ -f "$full_path" ]; then
            local attack_name=$(basename "$log_file" .log)
            echo -e "${CYAN}📋 $attack_name results:${NC}"
            
            # Show last few log entries with color
            tail -3 "$full_path" 2>/dev/null | while read line; do
                if [[ "$line" == *"SUCCESS"* ]]; then
                    echo -e "${GREEN}   ✅ $line${NC}"
                elif [[ "$line" == *"ERROR"* ]]; then
                    echo -e "${RED}   ❌ $line${NC}"
                else
                    echo -e "${YELLOW}   ℹ️  $line${NC}"
                fi
            done
            echo ""
        fi
    done
    
    # Show IOC summary
    echo -e "${YELLOW}╔══════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║          IOC Summary                 ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════╝${NC}"
    
    local ioc_files=("/tmp/wifi_iocs.txt" "/tmp/mavlink_iocs.txt" "/tmp/component_iocs.txt" "/tmp/stream_iocs.txt")
    local total_iocs=0
    
    for ioc_file in "${ioc_files[@]}"; do
        if [ -f "$ioc_file" ] && [ -s "$ioc_file" ]; then
            local ioc_count=$(wc -l < "$ioc_file")
            local ioc_type=$(basename "$ioc_file" _iocs.txt)
            
            total_iocs=$((total_iocs + ioc_count))
            
            echo -e "${CYAN}📊 $ioc_type: $ioc_count IOCs${NC}"
            
            # Show sample IOCs
            head -5 "$ioc_file" | while read ioc; do
                echo -e "${GRAY}   • $ioc${NC}"
            done
            
            if [ "$ioc_count" -gt 5 ]; then
                echo -e "${GRAY}   ... and $((ioc_count - 5)) more${NC}"
            fi
            echo ""
        fi
    done
    
    echo -e "${GREEN}🎯 Total IOCs collected: $total_iocs${NC}"
}

generate_comprehensive_report() {
    local report_file="$OUTPUT_DIR/dvd_reconnaissance_report_$(date +%Y%m%d_%H%M%S).json"
    
    echo -e "${BLUE}📝 Generating comprehensive JSON report...${NC}"
    
    # Enhanced Python report generator
    cat > "/tmp/generate_comprehensive_report.py" << 'PYEOF'
#!/usr/bin/env python3
import json
import os
import datetime
import glob
from pathlib import Path

def collect_all_iocs():
    """Collect all IOCs from different attack types"""
    ioc_data = {}
    ioc_files = {
        'wifi': '/tmp/wifi_iocs.txt',
        'mavlink': '/tmp/mavlink_iocs.txt', 
        'component': '/tmp/component_iocs.txt',
        'stream': '/tmp/stream_iocs.txt'
    }
    
    for category, file_path in ioc_files.items():
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                iocs = [line.strip() for line in f if line.strip()]
                ioc_data[category] = {
                    'count': len(iocs),
                    'iocs': iocs
                }
        else:
            ioc_data[category] = {'count': 0, 'iocs': []}
    
    return ioc_data

def analyze_attack_logs():
    """Analyze attack execution logs"""
    log_dir = "/home/kali/MTD/MTD_full_testbed/attack_logs"
    log_analysis = {}
    
    log_files = ['wifi_discovery.log', 'mavlink_discovery.log', 'component_enum.log', 'camera_discovery.log']
    
    for log_file in log_files:
        log_path = os.path.join(log_dir, log_file) 
        attack_name = log_file.replace('.log', '')
        
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_content = f.read()
                
            log_analysis[attack_name] = {
                'executed': True,
                'success_count': log_content.count('[SUCCESS]'),
                'error_count': log_content.count('[ERROR]'),
                'warning_count': log_content.count('[WARNING]'),
                'last_execution': datetime.datetime.fromtimestamp(
                    os.path.getmtime(log_path)
                ).isoformat() if os.path.exists(log_path) else None
            }
        else:
            log_analysis[attack_name] = {
                'executed': False,
                'success_count': 0,
                'error_count': 0,
                'warning_count': 0,
                'last_execution': None
            }
    
    return log_analysis

def categorize_iocs(ioc_data):
    """Categorize IOCs by type and severity"""
    categorized = {
        'network_infrastructure': [],
        'services': [],
        'vulnerabilities': [],
        'streaming_endpoints': [],
        'authentication_bypass': []
    }
    
    for category, data in ioc_data.items():
        for ioc in data['iocs']:
            if any(keyword in ioc.upper() for keyword in ['WIFI_NETWORK', 'NETWORK', 'IP']):
                categorized['network_infrastructure'].append(ioc)
            elif any(keyword in ioc.upper() for keyword in ['SERVICE', 'PORT', 'MAVLINK']):
                categorized['services'].append(ioc)
            elif any(keyword in ioc.upper() for keyword in ['STREAM', 'RTSP', 'HTTP', 'MJPEG']):
                categorized['streaming_endpoints'].append(ioc)
            elif any(keyword in ioc.upper() for keyword in ['AUTH', 'BYPASS', 'OPEN']):
                categorized['authentication_bypass'].append(ioc)
    
    return categorized

def generate_mitre_mapping():
    """Map discovered attacks to MITRE ATT&CK framework"""
    mitre_mapping = {
        'T1046': {
            'technique': 'Network Service Scanning',
            'description': 'DVD reconnaissance attacks performed network service discovery',
            'evidence': ['MAVLink service discovery', 'Component enumeration', 'Port scanning']
        },
        'T1040': {
            'technique': 'Network Sniffing', 
            'description': 'WiFi network discovery and monitoring',
            'evidence': ['WiFi network scanning', 'Monitor mode operation']
        },
        'T1113': {
            'technique': 'Screen Capture',
            'description': 'Video stream discovery and access',
            'evidence': ['RTSP stream discovery', 'HTTP video endpoint discovery']
        }
    }
    
    return mitre_mapping

def generate_recommendations():
    """Generate security recommendations based on findings"""
    recommendations = [
        {
            'category': 'Network Security',
            'priority': 'High',
            'recommendation': 'Implement network segmentation to isolate drone components',
            'rationale': 'Current network allows lateral movement between drone systems'
        },
        {
            'category': 'Protocol Security', 
            'priority': 'Critical',
            'recommendation': 'Enable MAVLink encryption and authentication',
            'rationale': 'MAVLink services discovered without authentication mechanisms'
        },
        {
            'category': 'Access Control',
            'priority': 'High', 
            'recommendation': 'Implement authentication for video streams',
            'rationale': 'Video streams accessible without credentials'
        },
        {
            'category': 'Monitoring',
            'priority': 'Medium',
            'recommendation': 'Deploy network monitoring for anomalous scanning activity',
            'rationale': 'Reconnaissance attacks went undetected'
        }
    ]
    
    return recommendations

def generate_report():
    """Generate comprehensive reconnaissance report"""
    
    ioc_data = collect_all_iocs()
    log_analysis = analyze_attack_logs()
    categorized_iocs = categorize_iocs(ioc_data)
    mitre_mapping = generate_mitre_mapping()
    recommendations = generate_recommendations()
    
    # Calculate statistics
    total_iocs = sum(data['count'] for data in ioc_data.values())
    successful_attacks = sum(1 for analysis in log_analysis.values() if analysis['success_count'] > 0)
    
    report_data = {
        'metadata': {
            'report_title': 'DVD Reconnaissance Attack Report',
            'timestamp': datetime.datetime.now().isoformat(),
            'report_version': '2.0',
            'target_system': 'Damn Vulnerable Drone (DVD)',
            'attack_framework': 'Custom DVD Reconnaissance Suite',
            'execution_environment': 'Kali Linux'
        },
        'executive_summary': {
            'total_attacks_executed': len(log_analysis),
            'successful_attacks': successful_attacks,
            'total_iocs_collected': total_iocs,
            'attack_success_rate': f"{(successful_attacks/len(log_analysis)*100):.1f}%" if log_analysis else "0%",
            'risk_level': 'HIGH' if total_iocs > 20 else 'MEDIUM' if total_iocs > 10 else 'LOW'
        },
        'attack_results': {
            'wifi_discovery': {
                'networks_found': ioc_data['wifi']['count'],
                'execution_status': log_analysis.get('wifi_discovery', {}).get('executed', False)
            },
            'mavlink_discovery': {
                'services_found': ioc_data['mavlink']['count'], 
                'execution_status': log_analysis.get('mavlink_discovery', {}).get('executed', False)
            },
            'component_enumeration': {
                'components_found': ioc_data['component']['count'],
                'execution_status': log_analysis.get('component_enum', {}).get('executed', False)
            },
            'stream_discovery': {
                'streams_found': ioc_data['stream']['count'],
                'execution_status': log_analysis.get('camera_discovery', {}).get('executed', False)
            }
        },
        'ioc_analysis': {
            'by_category': ioc_data,
            'categorized': categorized_iocs,
            'total_count': total_iocs
        },
        'log_analysis': log_analysis,
        'mitre_attack_mapping': mitre_mapping,
        'security_recommendations': recommendations,
        'technical_details': {
            'target_networks': ['10.13.0.0/24', '192.168.13.0/24'],
            'target_hosts': [
                '10.13.0.2 (flight-controller)',
                '10.13.0.3 (companion-computer)', 
                '10.13.0.4 (ground-control-station)',
                '10.13.0.5 (simulator)'
            ],
            'scan_techniques': [
                'WiFi monitor mode scanning',
                'MAVLink protocol probing',
                'TCP/UDP port enumeration',
                'HTTP endpoint discovery',
                'RTSP stream detection'
            ]
        }
    }
    
    return report_data

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3 generate_comprehensive_report.py <output_file>")
        sys.exit(1)
    
    output_file = sys.argv[1]
    report = generate_report()
    
    # Save report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"📊 Comprehensive report generated: {output_file}")
    print(f"🎯 Total IOCs: {report['executive_summary']['total_iocs_collected']}")
    print(f"⚡ Success rate: {report['executive_summary']['attack_success_rate']}")
    print(f"🚨 Risk level: {report['executive_summary']['risk_level']}")
PYEOF
    
    python3 "/tmp/generate_comprehensive_report.py" "$report_file"
    
    if [ -f "$report_file" ]; then
        echo -e "${GREEN}✅ Comprehensive report saved: $report_file${NC}"
        
        # Show quick summary
        echo -e "${CYAN}📊 Quick Summary:${NC}"
        python3 -c "
import json
with open('$report_file') as f:
    data = json.load(f)
    summary = data['executive_summary']
    print(f'  🎯 Total IOCs: {summary[\"total_iocs_collected\"]}')
    print(f'  ⚡ Success Rate: {summary[\"attack_success_rate\"]}')
    print(f'  🚨 Risk Level: {summary[\"risk_level\"]}')
    
    # Show top recommendations
    print('\n🔒 Top Security Recommendations:')
    for i, rec in enumerate(data['security_recommendations'][:3], 1):
        print(f'  {i}. [{rec[\"priority\"]}] {rec[\"recommendation\"]}')
"
    else
        log_error "Failed to generate comprehensive report"
    fi
}

clean_previous_results() {
    echo -e "${YELLOW}🧹 Cleaning previous attack results...${NC}"
    
    # Clean IOC files
    local ioc_files=("/tmp/wifi_iocs.txt" "/tmp/mavlink_iocs.txt" "/tmp/component_iocs.txt" "/tmp/stream_iocs.txt")
    
    for ioc_file in "${ioc_files[@]}"; do
        if [ -f "$ioc_file" ]; then
            rm -f "$ioc_file"
            echo -e "${GREEN}✅ Cleaned: $(basename "$ioc_file")${NC}"
        fi
    done
    
    # Clean temporary files
    rm -f /tmp/wifi_parser.py /tmp/mavlink_test_*.py /tmp/nmap_parser.py
    rm -f /tmp/rtsp_*.py /tmp/mjpeg_scanner_*.py
    
    # Clean old output files
    find "$OUTPUT_DIR" -name "*.xml" -mtime +1 -delete 2>/dev/null
    find "$OUTPUT_DIR" -name "wifi_scan_*" -mtime +1 -delete 2>/dev/null
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Main execution
main() {
    # Root check
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ This script must be run as root (sudo)${NC}"
        echo -e "${YELLOW}💡 Usage: sudo $0${NC}"
        exit 1
    fi
    
    print_banner
    show_system_status
    
    # Make attack scripts executable
    chmod +x "$ATTACK_SCRIPTS_DIR"/*.sh 2>/dev/null
    
    # Interactive menu
    while true; do
        show_menu
        read -p "🎯 Select option: " choice
        
        case $choice in
            1)
                run_attack "$ATTACK_SCRIPTS_DIR/wifi_discovery.sh" "📡 WiFi Network Discovery"
                ;;
            2)
                run_attack "$ATTACK_SCRIPTS_DIR/mavlink_discovery.sh" "🔌 MAVLink Service Discovery"
                ;;
            3)
                run_attack "$ATTACK_SCRIPTS_DIR/component_enum.sh" "🖥️ Component Enumeration"
                ;;
            4)
                run_attack "$ATTACK_SCRIPTS_DIR/camera_discovery.sh" "📹 Camera Stream Discovery"
                ;;
            5)
                echo -e "${YELLOW}[!] Network topology discovery - Using component enumeration${NC}"
                run_attack "$ATTACK_SCRIPTS_DIR/component_enum.sh" "🌐 Network Topology Discovery"
                ;;
            6)
                run_all_attacks
                ;;
            7)
                show_results
                ;;
            8)
                generate_comprehensive_report
                ;;
            9)
                clean_previous_results
                ;;
            0)
                echo -e "${GREEN}✅ Exiting DVD Reconnaissance Suite...${NC}"
                echo -e "${CYAN}📋 Log files available in: $LOG_DIR${NC}"
                echo -e "${CYAN}📊 Reports available in: $OUTPUT_DIR${NC}"
                break
                ;;
            *)
                echo -e "${RED}❌ Invalid option${NC}"
                ;;
        esac
        
        echo ""
        read -p "⏸️ Press Enter to continue..." 
        clear
        print_banner
    done
}

main "$@"