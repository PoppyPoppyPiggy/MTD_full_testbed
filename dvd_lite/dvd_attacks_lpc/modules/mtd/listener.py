import socket
import json

HIT_LOG_FILE = "/shared/hit.log"
STATE_FILE = "/shared/mtd_state.json"

def main():
    print("LISTENER: Starting hit listener...")
    # MTD Manager가 생성/업데이트하는 IP/Port 정보를 동적으로 읽어옴
    while True:
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                listen_ip = state['ip']
                listen_port = int(state['port'])
                
                # 새로운 소켓을 열기 전에 이전 소켓이 있다면 닫아야 할 수 있지만,
                # 여기서는 간단하게 새 정보를 계속 폴링하는 형태로 구현
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((listen_ip, listen_port))
                    s.listen()
                    # 이 리스너는 실제 데이터 전송이 아닌 '접속 시도' 자체를 감지하는 역할
                    conn, addr = s.accept()
                    with conn:
                        print(f"LISTENER: Hit detected from {addr[0]}")
                        with open(HIT_LOG_FILE, 'a') as f:
                            f.write(f"{addr[0]}\n")

        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # MTD Manager가 아직 state 파일을 생성하지 않음
            time.sleep(1)
        except Exception as e:
            # 포트가 아직 사용 가능하지 않은 경우 등
            print(f"LISTENER: Error - {e}, retrying...")
            time.sleep(1)

if __name__ == "__main__":
    # 이 구현은 개념 증명용입니다. 실제로는 iptables의 LOG 타겟을 사용하거나
    # 더 정교한 패킷 스니핑 방식으로 히트를 감지하는 것이 더 효율적입니다.
    # 위의 manager.py는 iptables DNAT를 사용하므로 별도 listener 없이도 동작합니다.
    # 이 파일은 개념 설명을 위해 남겨둡니다.
    print("This listener is for conceptual demonstration.")
    print("The primary hit detection is handled by the iptables rules in manager.py")
    pass