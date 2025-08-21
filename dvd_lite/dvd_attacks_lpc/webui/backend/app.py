#!/usr/bin/env python3
"""
MTD 드론 보안 테스트베드 WebUI 백엔드
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import sqlite3
import pandas as pd
import json
import time
import os
import subprocess
import threading
from datetime import datetime, timedelta
import logging

# API 모듈 import
from api.experiments import experiments_bp
from api.data import data_bp
from api.dvd import dvd_bp
from api.ns3 import ns3_bp
from services.data_collector import DataCollector
from services.experiment_runner import ExperimentRunner
from services.dvd_manager import DVDManager

app = Flask(__name__, 
           template_folder='../frontend/templates',
           static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'mtd-drone-security-testbed'

# SocketIO 초기화
socketio = SocketIO(app, cors_allowed_origins="*")

# 블루프린트 등록
app.register_blueprint(experiments_bp, url_prefix='/api/experiments')
app.register_blueprint(data_bp, url_prefix='/api/data')
app.register_blueprint(dvd_bp, url_prefix='/api/dvd')
app.register_blueprint(ns3_bp, url_prefix='/api/ns3')

# 서비스 초기화
data_collector = DataCollector()
experiment_runner = ExperimentRunner()
dvd_manager = DVDManager()

# 글로벌 상태
app_state = {
    'system_running': False,
    'current_experiment': None,
    'connected_clients': 0
}

@app.route('/')
def index():
    """메인 대시보드"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """실시간 대시보드"""
    return render_template('dashboard.html')

@app.route('/experiments')
def experiments():
    """실험 제어 패널"""
    return render_template('experiments.html')

@app.route('/analysis')
def analysis():
    """데이터 분석 페이지"""
    return render_template('analysis.html')

@app.route('/dvd')
def dvd():
    """DVD 통합 페이지"""
    return render_template('dvd.html')

@app.route('/api/system/status')
def system_status():
    """시스템 상태 API"""
    try:
        # 시스템 프로세스 확인
        running_processes = []
        pid_files = [
            '/tmp/honeydrone.pid',
            '/tmp/ml_pipeline.pid', 
            '/tmp/sdn_controller.pid'
        ]
        
        for pid_file in pid_files:
            if os.path.exists(pid_file):
                with open(pid_file) as f:
                    pid = f.read().strip()
                try:
                    os.kill(int(pid), 0)  # 프로세스 존재 확인
                    running_processes.append(os.path.basename(pid_file).replace('.pid', ''))
                except:
                    pass
        
        # 최신 메트릭 조회
        latest_metrics = data_collector.get_latest_metrics()
        
        status = {
            'timestamp': time.time(),
            'system_running': len(running_processes) > 0,
            'running_processes': running_processes,
            'latest_metrics': latest_metrics,
            'dvd_status': dvd_manager.get_status(),
            'connected_clients': app_state['connected_clients']
        }
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/start', methods=['POST'])
def start_system():
    """시스템 시작"""
    try:
        # 통합 시스템 시작
        result = subprocess.run([
            './scripts/deployment/run_integrated_system.sh', 'start'
        ], capture_output=True, text=True, cwd='..')
        
        if result.returncode == 0:
            app_state['system_running'] = True
            return jsonify({'status': 'success', 'message': '시스템이 시작되었습니다.'})
        else:
            return jsonify({'status': 'error', 'message': result.stderr}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/stop', methods=['POST'])
def stop_system():
    """시스템 중지"""
    try:
        result = subprocess.run([
            './scripts/deployment/run_integrated_system.sh', 'stop'
        ], capture_output=True, text=True, cwd='..')
        
        app_state['system_running'] = False
        return jsonify({'status': 'success', 'message': '시스템이 중지되었습니다.'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """클라이언트 연결"""
    app_state['connected_clients'] += 1
    emit('status', {'connected': True})
    print(f"클라이언트 연결됨. 총 {app_state['connected_clients']}명")

@socketio.on('disconnect')
def handle_disconnect():
    """클라이언트 연결 해제"""
    app_state['connected_clients'] -= 1
    print(f"클라이언트 연결 해제됨. 총 {app_state['connected_clients']}명")

@socketio.on('request_data')
def handle_data_request(data):
    """실시간 데이터 요청"""
    try:
        data_type = data.get('type', 'metrics')
        
        if data_type == 'metrics':
            metrics = data_collector.get_realtime_metrics()
            emit('metrics_update', metrics)
        elif data_type == 'dvd_status':
            status = dvd_manager.get_realtime_status()
            emit('dvd_update', status)
        elif data_type == 'ns3_results':
            results = data_collector.get_ns3_results()
            emit('ns3_update', results)
            
    except Exception as e:
        emit('error', {'message': str(e)})

def background_data_stream():
    """백그라운드 데이터 스트림"""
    while True:
        try:
            if app_state['connected_clients'] > 0:
                # 실시간 메트릭 브로드캐스트
                metrics = data_collector.get_realtime_metrics()
                socketio.emit('metrics_broadcast', metrics)
                
                # DVD 상태 브로드캐스트
                dvd_status = dvd_manager.get_realtime_status()
                socketio.emit('dvd_broadcast', dvd_status)
            
            time.sleep(1)  # 1초마다 업데이트
            
        except Exception as e:
            print(f"백그라운드 스트림 오류: {e}")
            time.sleep(5)

if __name__ == '__main__':
    # 백그라운드 스레드 시작
    threading.Thread(target=background_data_stream, daemon=True).start()
    
    # 서비스 초기화
    data_collector.start()
    
    print("🌐 MTD 드론 보안 테스트베드 WebUI 시작")
    print("📊 대시보드: http://localhost:5000")
    print("🧪 실험 제어: http://localhost:5000/experiments")
    print("📈 데이터 분석: http://localhost:5000/analysis")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
