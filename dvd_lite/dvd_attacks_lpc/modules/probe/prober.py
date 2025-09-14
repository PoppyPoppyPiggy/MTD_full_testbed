import subprocess

class TargetProber:
    def __init__(self, timeout=0.2):
        self.timeout = timeout

    def is_alive_from_container(self, ip, port, container_name="attacker"):
        """
        지정된 컨테이너 내부에서 타겟의 활성 상태를 확인합니다.
        """
        if not ip or not port:
            return False
        
        # nc (netcat)을 사용하여 TCP 포트 스캔
        # -z: 제로 I/O 모드 (데이터 전송 없이 포트 스캔)
        # -w: 타임아웃
        cmd = f"docker exec {container_name} nc -z -w 1 {ip} {port}"
        
        # 실행 결과가 0이면 성공(포트 열림)
        result = subprocess.run(cmd, shell=True, capture_output=True)
        is_up = result.returncode == 0
        
        status = "ALIVE" if is_up else "DEAD"
        print(f"PROBER: Target {ip}:{port} from '{container_name}' is {status}.")
        return is_up