from flask import Blueprint, request, jsonify
import subprocess
import json
import os
import time
from datetime import datetime

experiments_bp = Blueprint('experiments', __name__)

# 사용 가능한 실험 시나리오
AVAILABLE_SCENARIOS = {
    'stealth_recon': {
        'name': '은밀한 정찰',
        'description': '수동적 네트워크 스캔 및 정보 수집',
        'duration': 300,
        'intensity': 'low'
    },
    'active_recon': {
        'name': '적극적 정찰',
        'description': '능동적 서비스 탐지 및 취약점 스캔',
        'duration': 420,
        'intensity': 'medium'
    },
    'aggressive_attack': {
        'name': '공격적 침투',
        'description': 'MAVLink 프로토콜 공격 및 명령 주입',
        'duration': 600,
        'intensity': 'high'
    },
    'persistent_campaign': {
        'name': '지속적 캠페인',
        'description': '장기간 은밀한 데이터 수집 및 조작',
        'duration': 1800,
        'intensity': 'medium'
    }
}

DEFENSE_LEVELS = {
    'none': '방어 없음',
    'minimal': '기본 모니터링',
    'standard': '표준 IDS',
    'enhanced': '고급 ML 기반',
    'maximum': '실시간 MTD + AI'
}

@experiments_bp.route('/scenarios')
def get_scenarios():
    """사용 가능한 실험 시나리오 목록"""
    return jsonify({
        'scenarios': AVAILABLE_SCENARIOS,
        'defense_levels': DEFENSE_LEVELS
    })

@experiments_bp.route('/run', methods=['POST'])
def run_experiment():
    """실험 실행"""
    try:
        data = request.get_json()
        scenario = data.get('scenario', 'stealth_recon')
        defense_level = data.get('defense_level', 'standard')
        duration = data.get('duration', 300)
        custom_params = data.get('params', {})
        
        if scenario not in AVAILABLE_SCENARIOS:
            return jsonify({'error': '유효하지 않은 시나리오'}), 400
        
        # 실험 설정 생성
        experiment_config = {
            'id': f"exp_{int(time.time())}",
            'scenario': scenario,
            'defense_level': defense_level,
            'duration': duration,
            'start_time': datetime.now().isoformat(),
            'params': custom_params,
            'status': 'starting'
        }
        
        # 실험 실행 명령
        cmd = [
            '../scripts/deployment/run_integrated_system.sh',
            'experiment',
            scenario,
            '--defense-level', defense_level,
            '--duration', str(duration)
        ]
        
        # 백그라운드에서 실험 실행
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd='..'
        )
        
        # 실험 정보 저장
        exp_dir = f"../results/experiments/{experiment_config['id']}"
        os.makedirs(exp_dir, exist_ok=True)
        
        with open(f"{exp_dir}/config.json", 'w') as f:
            json.dump(experiment_config, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'experiment_id': experiment_config['id'],
            'message': f'{AVAILABLE_SCENARIOS[scenario]["name"]} 실험이 시작되었습니다.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@experiments_bp.route('/status/<experiment_id>')
def get_experiment_status(experiment_id):
    """실험 상태 조회"""
    try:
        exp_dir = f"../results/experiments/{experiment_id}"
        
        if not os.path.exists(exp_dir):
            return jsonify({'error': '실험을 찾을 수 없습니다.'}), 404
        
        # 설정 파일 로드
        with open(f"{exp_dir}/config.json") as f:
            config = json.load(f)
        
        # 결과 파일 확인
        results_file = f"{exp_dir}/experiment_results.json"
        if os.path.exists(results_file):
            with open(results_file) as f:
                results = json.load(f)
            config['results'] = results
            config['status'] = 'completed'
        else:
            # 진행 중인지 확인
            config['status'] = 'running' if _is_experiment_running(experiment_id) else 'failed'
        
        return jsonify(config)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@experiments_bp.route('/list')
def list_experiments():
    """실험 목록 조회"""
    try:
        experiments = []
        results_dir = "../results/experiments"
        
        if os.path.exists(results_dir):
            for exp_id in os.listdir(results_dir):
                exp_dir = os.path.join(results_dir, exp_id)
                config_file = os.path.join(exp_dir, "config.json")
                
                if os.path.exists(config_file):
                    with open(config_file) as f:
                        config = json.load(f)
                    
                    # 상태 업데이트
                    results_file = os.path.join(exp_dir, "experiment_results.json")
                    if os.path.exists(results_file):
                        config['status'] = 'completed'
                    else:
                        config['status'] = 'running' if _is_experiment_running(exp_id) else 'failed'
                    
                    experiments.append(config)
        
        # 시간순 정렬 (최신 순)
        experiments.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        
        return jsonify({'experiments': experiments})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@experiments_bp.route('/stop/<experiment_id>', methods=['POST'])
def stop_experiment(experiment_id):
    """실험 중지"""
    try:
        # 시스템 중지
        subprocess.run([
            '../scripts/deployment/run_integrated_system.sh', 'stop'
        ], cwd='..', check=True)
        
        return jsonify({'status': 'success', 'message': '실험이 중지되었습니다.'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _is_experiment_running(experiment_id):
    """실험 실행 중인지 확인"""
    # PID 파일들 확인
    pid_files = ['/tmp/honeydrone.pid', '/tmp/ml_pipeline.pid']
    
    for pid_file in pid_files:
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)  # 프로세스 존재 확인
                return True
            except:
                continue
    
    return False
