from flask import Blueprint, jsonify, request
import subprocess
import json
import os
import pandas as pd
import time
from datetime import datetime

ns3_bp = Blueprint('ns3', __name__)

@ns3_bp.route('/status')
def get_ns3_status():
    """NS-3 시뮬레이션 상태"""
    try:
        # NS-3 디렉토리 확인
        ns3_paths = [
            '~/MTD/MTD_full_testbed/ns-3.45/ns-3-dev',
            '/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev'
        ]
        
        ns3_available = False
        ns3_path = None
        
        for path in ns3_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                ns3_available = True
                ns3_path = expanded_path
                break
        
        # 최근 시뮬레이션 결과 확인
        results_file = '../attack_output/ns3_honeydrone_metrics.csv'
        recent_results = None
        
        if os.path.exists(results_file):
            try:
                df = pd.read_csv(results_file)
                if not df.empty:
                    recent_results = {
                        'total_flows': len(df),
                        'avg_throughput': df['Throughput_Mbps'].mean(),
                        'avg_delay': df['MeanDelay_ms'].mean(),
                        'avg_packet_loss': df['PacketLossRate'].mean(),
                        'last_updated': time.ctime(os.path.getmtime(results_file))
                    }
            except Exception as e:
                print(f"NS-3 결과 파일 읽기 오류: {e}")
        
        return jsonify({
            'ns3_available': ns3_available,
            'ns3_path': ns3_path,
            'recent_results': recent_results,
            'simulation_running': _is_ns3_running()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ns3_bp.route('/run', methods=['POST'])
def run_ns3_simulation():
    """NS-3 시뮬레이션 실행"""
    try:
        data = request.get_json()
        sim_time = data.get('sim_time', 300)
        n_nodes = data.get('n_nodes', 12)
        scenario = data.get('scenario', 'honeydrone_network')
        
        # NS-3 실행 스크립트 호출
        cmd = ['../scripts/deployment/run_ns3_simulation.sh']
        
        # 환경 변수 설정
        env = os.environ.copy()
        env['SIM_TIME'] = str(sim_time)
        env['N_NODES'] = str(n_nodes)
        
        # 백그라운드에서 실행
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd='..'
        )
        
        return jsonify({
            'status': 'success',
            'message': f'NS-3 시뮬레이션이 시작되었습니다. (시간: {sim_time}초, 노드: {n_nodes}개)',
            'process_id': process.pid
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ns3_bp.route('/results')
def get_ns3_results():
    """NS-3 시뮬레이션 결과 조회"""
    try:
        results_file = '../attack_output/ns3_honeydrone_metrics.csv'
        
        if not os.path.exists(results_file):
            return jsonify({
                'status': 'no_data',
                'message': 'NS-3 시뮬레이션 결과가 없습니다.',
                'sample_data': _generate_sample_ns3_data()
            })
        
        # CSV 파일 읽기
        df = pd.read_csv(results_file)
        
        if df.empty:
            return jsonify({
                'status': 'empty',
                'message': '시뮬레이션 결과가 비어있습니다.'
            })
        
        # 통계 계산
        statistics = {
            'summary': {
                'total_flows': len(df),
                'simulation_time': df['FlowID'].max() if 'FlowID' in df.columns else 0,
                'total_packets_sent': df['TxPackets'].sum() if 'TxPackets' in df.columns else 0,
                'total_packets_received': df['RxPackets'].sum() if 'RxPackets' in df.columns else 0,
                'avg_throughput_mbps': df['Throughput_Mbps'].mean() if 'Throughput_Mbps' in df.columns else 0,
                'avg_delay_ms': df['MeanDelay_ms'].mean() if 'MeanDelay_ms' in df.columns else 0,
                'avg_jitter_ms': df['MeanJitter_ms'].mean() if 'MeanJitter_ms' in df.columns else 0,
                'avg_packet_loss_rate': df['PacketLossRate'].mean() if 'PacketLossRate' in df.columns else 0
            },
            'per_flow': df.to_dict('records')
        }
        
        return jsonify({
            'status': 'success',
            'statistics': statistics,
            'file_info': {
                'last_modified': time.ctime(os.path.getmtime(results_file)),
                'file_size': os.path.getsize(results_file)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ns3_bp.route('/scenarios')
def get_ns3_scenarios():
    """사용 가능한 NS-3 시나리오 목록"""
    scenarios = {
        'honeydrone_network': {
            'name': '허니드론 네트워크',
            'description': 'FANET 기반 허니드론 메시 네트워크 시뮬레이션',
            'default_nodes': 12,
            'default_time': 300
        },
        'basic_wifi': {
            'name': '기본 WiFi',
            'description': '단순 WiFi 네트워크 시뮬레이션',
            'default_nodes': 8,
            'default_time': 180
        },
        'mesh_network': {
            'name': '메시 네트워크',
            'description': '동적 메시 네트워크 시뮬레이션',
            'default_nodes': 15,
            'default_time': 420
        }
    }
    
    return jsonify({'scenarios': scenarios})

@ns3_bp.route('/topology')
def get_network_topology():
    """네트워크 토폴로지 정보"""
    try:
        # 시뮬레이션된 토폴로지 정보
        topology = {
            'nodes': [
                {'id': 'real_drone', 'type': 'real_drone', 'x': 0, 'y': 0, 'z': 100, 'ip': '10.13.0.2'},
                {'id': 'honeydrone_main', 'type': 'honeydrone', 'x': 50, 'y': 50, 'z': 100, 'ip': '172.20.0.10'},
                {'id': 'dummy_drone_1', 'type': 'dummy_drone', 'x': 100, 'y': 0, 'z': 80, 'ip': '172.30.1.10'},
                {'id': 'dummy_drone_2', 'type': 'dummy_drone', 'x': -50, 'y': 100, 'z': 90, 'ip': '172.30.1.11'},
                {'id': 'virtual_drone_1', 'type': 'virtual_drone', 'x': 75, 'y': -25, 'z': 85, 'ip': '172.30.2.10'},
                {'id': 'virtual_drone_2', 'type': 'virtual_drone', 'x': -25, 'y': 75, 'z': 95, 'ip': '172.30.2.11'},
                {'id': 'ground_control', 'type': 'ground_station', 'x': 0, 'y': 0, 'z': 0, 'ip': '10.13.0.3'}
            ],
            'links': [
                {'source': 'real_drone', 'target': 'ground_control', 'type': 'mavlink', 'bandwidth': '1Mbps'},
                {'source': 'honeydrone_main', 'target': 'dummy_drone_1', 'type': 'mesh', 'bandwidth': '54Mbps'},
                {'source': 'honeydrone_main', 'target': 'dummy_drone_2', 'type': 'mesh', 'bandwidth': '54Mbps'},
                {'source': 'dummy_drone_1', 'target': 'virtual_drone_1', 'type': 'wifi', 'bandwidth': '54Mbps'},
                {'source': 'dummy_drone_2', 'target': 'virtual_drone_2', 'type': 'wifi', 'bandwidth': '54Mbps'}
            ]
        }
        
        return jsonify({'topology': topology})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _is_ns3_running():
    """NS-3 시뮬레이션 실행 중인지 확인"""
    try:
        # ns-3 프로세스 확인
        result = subprocess.run(['pgrep', '-f', 'ns3'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def _generate_sample_ns3_data():
    """샘플 NS-3 데이터 생성"""
    import random
    
    sample_data = []
    for i in range(10):
        sample_data.append({
            'FlowID': i + 1,
            'SourceIP': f'172.20.0.{10 + i}',
            'DestIP': '172.20.0.1',
            'TxPackets': random.randint(800, 1200),
            'RxPackets': random.randint(750, 1150),
            'LostPackets': random.randint(0, 50),
            'Throughput_Mbps': round(random.uniform(45, 55), 2),
            'MeanDelay_ms': round(random.uniform(10, 50), 2),
            'MeanJitter_ms': round(random.uniform(1, 10), 2),
            'PacketLossRate': round(random.uniform(0, 5), 2)
        })
    
    return sample_data
