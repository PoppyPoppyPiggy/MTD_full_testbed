import json
import pathlib
import os
from datetime import datetime

class RLExportHook:
    """
    MTD 상태와 선택된 정책을 JSON 파일로 내보내어
    RL 에이전트(또는 다른 프로세스)가 읽을 수 있도록 합니다.
    """
    def __init__(self, state_file_path: str, policy_file_path: str):
        """
        RLExportHook을 초기화합니다.

        Args:
            state_file_path (str): MTD 상태를 쓸 JSON 파일 경로.
            policy_file_path (str): 선택된 MTD 정책을 쓸 JSON 파일 경로.
        """
        self.state_file = pathlib.Path(state_file_path)
        self.policy_file = pathlib.Path(policy_file_path)
        
        # 파일이 위치할 디렉토리가 존재하지 않으면 생성합니다.
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.policy_file.parent.mkdir(parents=True, exist_ok=True)

    def export_state_and_policy(self, state_data: dict, action_id: int):
        """
        현재 MTD 상태와 선택된 행동(정책 ID)을 파일에 씁니다.

        Args:
            state_data (dict): MTDStateReader에서 받은 현재 상태 사전.
            action_id (int): RL 에이전트가 선택한 행동 ID.
        """
        try:
            # 1. MTD 상태 내보내기
            # state_data에 타임스탬프 추가
            state_data_with_timestamp = state_data.copy()
            state_data_with_timestamp['timestamp'] = datetime.utcnow().isoformat()
            self.state_file.write_text(json.dumps(state_data_with_timestamp, indent=2))

            # 2. MTD 정책(행동) 내보내기
            policy_data = {
                "policy_id": action_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.policy_file.write_text(json.dumps(policy_data, indent=2))
            
        except IOError as e:
            print(f"오류: 상태 또는 정책 파일 쓰기 실패: {e}")
        except Exception as e:
            print(f"오류: 내보내기 중 예기치 않은 오류 발생: {e}")

# --- 사용자가 제공한 기존 함수 ---
# 이 함수는 RLDrivenDeceptionManager에서는 사용되지 않지만,
# 다른 모듈에서 사용할 수 있으므로 파일에 그대로 둡니다.
def export_rl_policy_means(out_path: str, metrics: dict):
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ip_cd_mean": float(metrics.get("ip_cd_mean", 30.0)),
        "decoy_ratio_mean": float(metrics.get("decoy_ratio_mean", 0.1)),
        "bl_level_mean": float(metrics.get("bl_level_mean", 1.0))
    }
    p.write_text(json.dumps(data, indent=2))