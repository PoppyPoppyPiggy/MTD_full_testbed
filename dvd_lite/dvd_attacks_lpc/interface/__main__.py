import json
import os
import sys

def get_active_target():
    """
    MTD 상태 파일을 읽어 현재 활성화된 타겟 정보를 반환합니다.
    """
    # 이 스크립트의 위치를 기준으로 mtd_state.json 파일의 절대 경로를 계산합니다.
    # __file__ -> /home/kali/.../dvd_attacks_lpc/interface/__main__.py
    # os.path.dirname -> .../interface
    # '..', 'mtd', 'shared_state', 'mtd_state.json' -> ../mtd/shared_state/mtd_state.json
    state_file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'mtd', 'shared_state', 'mtd_state.json')
    )

    if not os.path.exists(state_file_path):
        # print() 대신 sys.stderr.write()를 사용하여 쉘 스크립트가 에러 메시지를
        # TARGET_ADDR 변수에 담는 것을 방지합니다.
        sys.stderr.write(f"ERROR: MTD state file not found at {state_file_path}\n")
        return None

    try:
        with open(state_file_path, 'r') as f:
            state = json.load(f)
        
        return state.get("current_target")

    except json.JSONDecodeError:
        sys.stderr.write(f"ERROR: Could not parse MTD state file {state_file_path}\n")
        return None

if __name__ == "__main__":
    target = get_active_target()
    if target:
        # 성공적으로 타겟을 찾으면, 결과(예: "10.13.0.3:14550")를 표준 출력으로 인쇄합니다.
        # 이 출력값을 쉘 스크립트의 TARGET_ADDR 변수가 받아가게 됩니다.
        print(target)
    else:
        # 실패 시, 쉘 스크립트가 에러를 감지할 수 있도록 0이 아닌 코드로 종료합니다.
        sys.exit(1)
