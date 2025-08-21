from flask import Blueprint, jsonify
import docker
import subprocess
import json
import os

dvd_bp = Blueprint('dvd', __name__)

@dvd_bp.route('/status')
def get_dvd_status():
    """DVD 컨테이너 상태 조회"""
    try:
        # Docker 클라이언트 초기화
        try:
            client = docker.from_env()
        except:
            return jsonify({
                'status': 'error',
                'message': 'Docker에 연결할 수 없습니다.',
                'containers': [],
                'simulation_mode': True
            })
        
        # DVD 관련 컨테이너 목록
        dvd_containers = [
            'simulator', 'ground-control-station', 
            'companion-computer', 'flight-controller'
        ]
        
        containers_status = []
        
        # 모든 컨테이너 조회
        all_containers = client.containers.list(all=True)
        
        for container in all_containers:
            container_name = container.name
            
            # DVD 관련 컨테이너만 필터링
            if any(dvd_name in container_name for dvd_name in dvd_containers):
                try:
                    container.reload()
                    
                    # 네트워크 정보 추출
                    networks = {}
                    if container.attrs.get('NetworkSettings', {}).get('Networks'):
                        for net_name, net_info in container.attrs['NetworkSettings']['Networks'].items():
                            networks[net_name] = {
                                'ip_address': net_info.get('IPAddress', ''),
                                'gateway': net_info.get('Gateway', ''),
                                'mac_address': net_info.get('MacAddress', '')
                            }
                    
                    containers_status.append({
                        'name': container_name,
                        'id': container.id[:12],
                        'status': container.status,
                        'image': container.image.tags[0] if container.image.tags else 'unknown',
                        'created': container.attrs.get('Created', ''),
                        'networks': networks,
                        'ports': container.attrs.get('NetworkSettings', {}).get('Ports', {}),
                        'labels': container.labels,
                        'cpu_usage': _get_container_stats(container, 'cpu'),
                        'memory_usage': _get_container_stats(container, 'memory')
                    })
                    
                except Exception as e:
                    containers_status.append({
                        'name': container_name,
                        'id': container.id[:12],
                        'status': 'error',
                        'error': str(e)
                    })
        
        # 시뮬레이션 모드 확인
        simulation_mode = len(containers_status) == 0
        
        if simulation_mode:
            containers_status = _get_simulated_dvd_status()
        
        return jsonify({
            'status': 'success',
            'containers': containers_status,
            'total_containers': len(containers_status),
            'running_containers': len([c for c in containers_status if c.get('status') == 'running']),
            'simulation_mode': simulation_mode,
            'docker_info': _get_docker_info(client) if not simulation_mode else None
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dvd_bp.route('/container/<container_name>/logs')
def get_container_logs(container_name):
    """컨테이너 로그 조회"""
    try:
        try:
            client = docker.from_env()
            container = client.containers.get(container_name)
            
            logs = container.logs(tail=100, timestamps=True).decode('utf-8')
            
            return jsonify({
                'status': 'success',
                'logs': logs.split('\n')
            })
            
        except docker.errors.NotFound:
            return jsonify({
                'status': 'error',
                'message': f'컨테이너 {container_name}을 찾을 수 없습니다.'
            }), 404
        except:
            # 시뮬레이션 로그 반환
            return jsonify({
                'status': 'success',
                'logs': _get_simulated_logs(container_name),
                'simulation_mode': True
            })
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dvd_bp.route('/container/<container_name>/restart', methods=['POST'])
def restart_container(container_name):
    """컨테이너 재시작"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        container.restart()
        
        return jsonify({
            'status': 'success',
            'message': f'컨테이너 {container_name}이 재시작되었습니다.'
        })
        
    except docker.errors.NotFound:
        return jsonify({
            'status': 'error',
            'message': f'컨테이너 {container_name}을 찾을 수 없습니다.'
        }), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dvd_bp.route('/network')
def get_dvd_network():
    """DVD 네트워크 토폴로지 정보"""
    try:
        client = docker.from_env()
        networks = client.networks.list()
        
        dvd_networks = []
        for network in networks:
            # DVD 관련 네트워크 필터링
            if any(keyword in network.name for keyword in ['dvd', 'drone', 'mtd']):
                network_info = {
                    'name': network.name,
                    'id': network.id[:12],
                    'driver': network.attrs.get('Driver', ''),
                    'scope': network.attrs.get('Scope', ''),
                    'subnet': '',
                    'gateway': '',
                    'containers': []
                }
                
                # IPAM 정보 추출
                ipam_config = network.attrs.get('IPAM', {}).get('Config', [])
                if ipam_config:
                    config = ipam_config[0]
                    network_info['subnet'] = config.get('Subnet', '')
                    network_info['gateway'] = config.get('Gateway', '')
                
                # 연결된 컨테이너들
                containers = network.attrs.get('Containers', {})
                for container_id, container_info in containers.items():
                    network_info['containers'].append({
                        'name': container_info.get('Name', ''),
                        'ipv4_address': container_info.get('IPv4Address', ''),
                        'mac_address': container_info.get('MacAddress', '')
                    })
                
                dvd_networks.append(network_info)
        
        return jsonify({
            'status': 'success',
            'networks': dvd_networks
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def _get_container_stats(container, stat_type):
    """컨테이너 통계 조회"""
    try:
        if container.status != 'running':
            return 0
        
        stats = container.stats(stream=False)
        
        if stat_type == 'cpu':
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100
                return round(cpu_percent, 2)
        
        elif stat_type == 'memory':
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100
            return round(memory_percent, 2)
        
    except:
        pass
    
    return 0

def _get_docker_info(client):
    """Docker 시스템 정보"""
    try:
        info = client.info()
        return {
            'version': client.version(),
            'containers_running': info.get('ContainersRunning', 0),
            'containers_total': info.get('Containers', 0),
            'images': info.get('Images', 0),
            'server_version': info.get('ServerVersion', ''),
            'operating_system': info.get('OperatingSystem', ''),
            'total_memory': info.get('MemTotal', 0)
        }
    except:
        return None

def _get_simulated_dvd_status():
    """시뮬레이션된 DVD 상태"""
    return [
        {
            'name': 'simulator',
            'id': 'sim_001',
            'status': 'running',
            'image': 'radarku/damn-vulnerable-drone:simulator',
            'created': '2024-01-01T12:00:00Z',
            'networks': {
                'dvd_network': {
                    'ip_address': '10.13.0.2',
                    'gateway': '10.13.0.1',
                    'mac_address': '02:42:0a:0d:00:02'
                }
            },
            'cpu_usage': 15.3,
            'memory_usage': 45.7
        },
        {
            'name': 'ground-control-station',
            'id': 'gcs_001',
            'status': 'running',
            'image': 'radarku/damn-vulnerable-drone:ground-control-station',
            'created': '2024-01-01T12:00:00Z',
            'networks': {
                'dvd_network': {
                    'ip_address': '10.13.0.3',
                    'gateway': '10.13.0.1',
                    'mac_address': '02:42:0a:0d:00:03'
                }
            },
            'cpu_usage': 8.2,
            'memory_usage': 32.1
        }
    ]

def _get_simulated_logs(container_name):
    """시뮬레이션된 로그"""
    import time
    from datetime import datetime
    
    current_time = datetime.now()
    logs = []
    
    for i in range(20):
        timestamp = (current_time - timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M:%S')
        
        if container_name == 'simulator':
            logs.append(f"[{timestamp}] MAVLink heartbeat sent")
            logs.append(f"[{timestamp}] GPS coordinates updated: lat=37.7749, lon=-122.4194")
        elif container_name == 'ground-control-station':
            logs.append(f"[{timestamp}] GCS connection established")
            logs.append(f"[{timestamp}] Telemetry data received from UAV")
    
    return logs[::-1]  # 최신 순으로 정렬
