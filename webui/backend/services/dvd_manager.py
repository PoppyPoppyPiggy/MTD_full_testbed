import docker
import time
import json

class DVDManager:
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.docker_available = True
        except:
            self.client = None
            self.docker_available = False
    
    def get_status(self):
        """DVD 시스템 상태 조회"""
        if not self.docker_available:
            return self._get_simulated_status()
        
        try:
            containers = self.client.containers.list(all=True)
            dvd_containers = []
            
            for container in containers:
                if any(name in container.name for name in ['simulator', 'ground-control', 'companion', 'flight']):
                    dvd_containers.append({
                        'name': container.name,
                        'status': container.status,
                        'id': container.id[:12]
                    })
            
            return {
                'docker_available': True,
                'containers': dvd_containers,
                'total_containers': len(dvd_containers)
            }
            
        except Exception as e:
            return {
                'docker_available': False,
                'error': str(e),
                'containers': []
            }
    
    def get_realtime_status(self):
        """실시간 상태 조회"""
        status = self.get_status()
        status['timestamp'] = time.time()
        return status
    
    def _get_simulated_status(self):
        """시뮬레이션된 상태"""
        return {
            'docker_available': False,
            'simulation_mode': True,
            'containers': [
                {
                    'name': 'simulator',
                    'status': 'running',
                    'id': 'sim_001'
                },
                {
                    'name': 'ground-control-station',
                    'status': 'running',
                    'id': 'gcs_001'
                }
            ],
            'total_containers': 2
        }
