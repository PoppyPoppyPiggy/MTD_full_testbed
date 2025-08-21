import subprocess
import threading
import time
import json
import os
from datetime import datetime

class ExperimentRunner:
    def __init__(self):
        self.running_experiments = {}
    
    def run_experiment(self, config):
        """실험 실행"""
        try:
            experiment_id = config['id']
            
            # 실험 실행 명령
            cmd = [
                '../scripts/deployment/run_integrated_system.sh',
                'experiment',
                config['scenario'],
                '--defense-level', config['defense_level'],
                '--duration', str(config['duration'])
            ]
            
            # 백그라운드에서 실행
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd='..'
            )
            
            # 실험 정보 저장
            self.running_experiments[experiment_id] = {
                'process': process,
                'config': config,
                'start_time': time.time()
            }
            
            # 완료 모니터링 스레드 시작
            threading.Thread(
                target=self._monitor_experiment,
                args=(experiment_id,),
                daemon=True
            ).start()
            
            return True
            
        except Exception as e:
            print(f"실험 실행 오류: {e}")
            return False
    
    def _monitor_experiment(self, experiment_id):
        """실험 모니터링"""
        try:
            exp_info = self.running_experiments[experiment_id]
            process = exp_info['process']
            config = exp_info['config']
            
            # 프로세스 완료 대기
            stdout, stderr = process.communicate()
            
            # 결과 처리
            if process.returncode == 0:
                self._handle_experiment_success(experiment_id, stdout)
            else:
                self._handle_experiment_error(experiment_id, stderr)
            
            # 실행 목록에서 제거
            del self.running_experiments[experiment_id]
            
        except Exception as e:
            print(f"실험 모니터링 오류: {e}")
    
    def _handle_experiment_success(self, experiment_id, stdout):
        """실험 성공 처리"""
        try:
            config = self.running_experiments[experiment_id]['config']
            
            # 결과 파일 생성
            exp_dir = f"../results/experiments/{experiment_id}"
            
            results = {
                'status': 'completed',
                'end_time': datetime.now().isoformat(),
                'duration': time.time() - self.running_experiments[experiment_id]['start_time'],
                'stdout': stdout[:1000],  # 처음 1000자만 저장
                'success': True
            }
            
            with open(f"{exp_dir}/experiment_results.json", 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f"실험 {experiment_id} 성공 완료")
            
        except Exception as e:
            print(f"실험 성공 처리 오류: {e}")
    
    def _handle_experiment_error(self, experiment_id, stderr):
        """실험 오류 처리"""
        try:
            config = self.running_experiments[experiment_id]['config']
            
            # 오류 결과 파일 생성
            exp_dir = f"../results/experiments/{experiment_id}"
            
            results = {
                'status': 'failed',
                'end_time': datetime.now().isoformat(),
                'duration': time.time() - self.running_experiments[experiment_id]['start_time'],
                'stderr': stderr[:1000],  # 처음 1000자만 저장
                'success': False
            }
            
            with open(f"{exp_dir}/experiment_results.json", 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f"실험 {experiment_id} 실행 실패: {stderr}")
            
        except Exception as e:
            print(f"실험 오류 처리 오류: {e}")
    
    def get_running_experiments(self):
        """실행 중인 실험 목록"""
        return list(self.running_experiments.keys())
    
    def stop_experiment(self, experiment_id):
        """실험 중지"""
        try:
            if experiment_id in self.running_experiments:
                process = self.running_experiments[experiment_id]['process']
                process.terminate()
                return True
            return False
        except Exception as e:
            print(f"실험 중지 오류: {e}")
            return False
