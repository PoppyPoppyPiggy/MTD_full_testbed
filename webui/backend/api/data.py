from flask import Blueprint, request, jsonify, send_file
import sqlite3
import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta
import numpy as np

data_bp = Blueprint('data', __name__)

@data_bp.route('/metrics')
def get_metrics():
    """메트릭 데이터 조회"""
    try:
        timerange = request.args.get('timerange', '3600')  # 기본 1시간
        limit = request.args.get('limit', '1000')
        
        db_path = '../attack_output/unified_metrics.db'
        
        if not os.path.exists(db_path):
            # 시뮬레이션 데이터 생성
            return jsonify({'metrics': _generate_simulation_data()})
        
        conn = sqlite3.connect(db_path)
        
        query = """
        SELECT * FROM unified_metrics 
        WHERE timestamp > ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        """
        
        since_time = time.time() - int(timerange)
        df = pd.read_sql_query(query, conn, params=[since_time, int(limit)])
        conn.close()
        
        if df.empty:
            return jsonify({'metrics': _generate_simulation_data()})
        
        return jsonify({'metrics': df.to_dict('records')})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@data_bp.route('/statistics')
def get_statistics():
    """통계 데이터 조회"""
    try:
        timerange = request.args.get('timerange', '3600')
        
        db_path = '../attack_output/unified_metrics.db'
        
        if not os.path.exists(db_path):
            return jsonify({'statistics': _generate_simulation_stats()})
        
        conn = sqlite3.connect(db_path)
        
        since_time = time.time() - int(timerange)
        df = pd.read_sql_query("""
            SELECT * FROM unified_metrics 
            WHERE timestamp > ?
        """, conn, params=[since_time])
        
        conn.close()
        
        if df.empty:
            return jsonify({'statistics': _generate_simulation_stats()})
        
        stats = {
            'network_performance': {
                'avg_latency_ms': float(df['latency_ms'].mean()),
                'max_latency_ms': float(df['latency_ms'].max()),
                'avg_packet_loss_pct': float(df['packet_loss_pct'].mean()),
                'avg_throughput_mbps': float(df['throughput_mbps'].mean()) if 'throughput_mbps' in df.columns else 0
            },
            'security_metrics': {
                'total_attacks_detected': int(df['attacks_detected'].sum()),
                'avg_detection_accuracy': float(df['detection_accuracy'].mean()),
                'attack_rate_per_hour': float(df['attacks_detected'].sum() / (len(df) / 3600))
            },
            'mtd_effectiveness': {
                'total_mtd_activations': int(df['mtd_activations'].sum()),
                'most_used_strategy': df['mtd_strategy'].mode().iloc[0] if not df['mtd_strategy'].mode().empty else 'none',
                'strategy_distribution': df['mtd_strategy'].value_counts().to_dict()
            },
            'system_performance': {
                'avg_cpu_usage_pct': float(df['cpu_usage_pct'].mean()) if 'cpu_usage_pct' in df.columns else 0,
                'avg_memory_usage_pct': float(df['memory_usage_pct'].mean()) if 'memory_usage_pct' in df.columns else 0
            }
        }
        
        return jsonify({'statistics': stats})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@data_bp.route('/export/<format>')
def export_data(format):
    """데이터 내보내기"""
    try:
        timerange = request.args.get('timerange', '86400')  # 기본 24시간
        
        db_path = '../attack_output/unified_metrics.db'
        
        if not os.path.exists(db_path):
            return jsonify({'error': '데이터베이스가 존재하지 않습니다.'}), 404
        
        conn = sqlite3.connect(db_path)
        
        since_time = time.time() - int(timerange)
        df = pd.read_sql_query("""
            SELECT * FROM unified_metrics 
            WHERE timestamp > ?
            ORDER BY timestamp
        """, conn, params=[since_time])
        
        conn.close()
        
        if df.empty:
            return jsonify({'error': '데이터가 없습니다.'}), 404
        
        # 타임스탬프를 읽기 쉬운 형태로 변환
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format.lower() == 'csv':
            filename = f"mtd_data_{timestamp_str}.csv"
            filepath = f"../webui/data/{filename}"
            os.makedirs('../webui/data', exist_ok=True)
            df.to_csv(filepath, index=False)
            return send_file(filepath, as_attachment=True, download_name=filename)
        
        elif format.lower() == 'json':
            filename = f"mtd_data_{timestamp_str}.json"
            filepath = f"../webui/data/{filename}"
            os.makedirs('../webui/data', exist_ok=True)
            df.to_json(filepath, orient='records', date_format='iso')
            return send_file(filepath, as_attachment=True, download_name=filename)
        
        else:
            return jsonify({'error': '지원되지 않는 형식입니다.'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@data_bp.route('/realtime')
def get_realtime_data():
    """실시간 데이터 조회"""
    try:
        # 최근 30개 데이터 포인트
        db_path = '../attack_output/unified_metrics.db'
        
        if not os.path.exists(db_path):
            return jsonify({'data': _generate_realtime_simulation()})
        
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("""
            SELECT * FROM unified_metrics 
            ORDER BY timestamp DESC 
            LIMIT 30
        """, conn)
        conn.close()
        
        if df.empty:
            return jsonify({'data': _generate_realtime_simulation()})
        
        # 시간순 정렬
        df = df.sort_values('timestamp')
        
        return jsonify({'data': df.to_dict('records')})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _generate_simulation_data():
    """시뮬레이션 데이터 생성"""
    current_time = time.time()
    data = []
    
    for i in range(100):
        timestamp = current_time - (100-i) * 60  # 100분 전부터
        
        data.append({
            'timestamp': timestamp,
            'latency_ms': np.random.normal(50, 15),
            'packet_loss_pct': np.random.exponential(2),
            'throughput_mbps': np.random.normal(100, 20),
            'cpu_usage_pct': np.random.normal(45, 10),
            'memory_usage_pct': np.random.normal(60, 15),
            'attacks_detected': np.random.poisson(0.5),
            'mtd_activations': np.random.poisson(0.2),
            'detection_accuracy': np.random.beta(8, 2),
            'defense_level': np.random.choice(['standard', 'enhanced', 'maximum']),
            'mtd_strategy': np.random.choice(['none', 'ip_hopping', 'port_shuffling', 'decoy_deployment'])
        })
    
    return data

def _generate_simulation_stats():
    """시뮬레이션 통계 생성"""
    return {
        'network_performance': {
            'avg_latency_ms': 52.3,
            'max_latency_ms': 89.7,
            'avg_packet_loss_pct': 2.1,
            'avg_throughput_mbps': 98.5
        },
        'security_metrics': {
            'total_attacks_detected': 15,
            'avg_detection_accuracy': 0.847,
            'attack_rate_per_hour': 0.75
        },
        'mtd_effectiveness': {
            'total_mtd_activations': 8,
            'most_used_strategy': 'ip_hopping',
            'strategy_distribution': {
                'ip_hopping': 3,
                'port_shuffling': 2,
                'decoy_deployment': 2,
                'none': 1
            }
        },
        'system_performance': {
            'avg_cpu_usage_pct': 47.2,
            'avg_memory_usage_pct': 58.9
        }
    }

def _generate_realtime_simulation():
    """실시간 시뮬레이션 데이터"""
    current_time = time.time()
    data = []
    
    for i in range(30):
        timestamp = current_time - (30-i) * 2  # 2초 간격
        
        data.append({
            'timestamp': timestamp,
            'latency_ms': np.random.normal(50, 10),
            'packet_loss_pct': np.random.exponential(1.5),
            'attacks_detected': np.random.poisson(0.1),
            'mtd_activations': np.random.poisson(0.05),
            'detection_accuracy': np.random.beta(9, 1),
            'mtd_strategy': np.random.choice(['none', 'ip_hopping', 'port_shuffling'])
        })
    
    return data
