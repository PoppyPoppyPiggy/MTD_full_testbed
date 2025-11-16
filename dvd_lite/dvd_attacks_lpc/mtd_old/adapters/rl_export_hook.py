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
        # [수정] state_file_path가 None일 수 있으므로(Manager가 None 전달),
        # None이 아닐 경우에만 Path 객체 생성
        if state_file_path:
            self.state_file = pathlib.Path(state_file_path)
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.state_file = None

        self.policy_file = pathlib.Path(policy_file_path)
        self.policy_file.parent.mkdir(parents=True, exist_ok=True)

    def export_state_and_policy(self, state_data: dict, policy_data: dict):
        """
        현재 MTD 상태와 선택된 행동(정책 ID)을 파일에 씁니다.

        [수정] action_id: int 대신 policy_data: dict 를 받도록 변경

        Args:
            state_data (dict): MTDStateReader에서 받은 현재 상태 사전. (None일 수 있음)
            policy_data (dict): RLDrivenDeceptionManager가 생성한 정책 사전.
        """
        try:
            # 1. MTD 상태 내보내기 (state_data가 None이 아니고, state_file이 설정되었을 때만)
            if state_data is not None and self.state_file is not None:
                state_data_with_timestamp = state_data.copy()
                state_data_with_timestamp['timestamp'] = datetime.utcnow().isoformat()
                self.state_file.write_text(json.dumps(state_data_with_timestamp, indent=2))

            # 2. MTD 정책(행동) 내보내기
            # [수정] policy_data를 직접 만들지 않고, Manager로부터 받은 dict를 사용
            policy_data_with_timestamp = policy_data.copy()
            policy_data_with_timestamp["timestamp"] = datetime.utcnow().isoformat()
            
            self.policy_file.write_text(json.dumps(policy_data_with_timestamp, indent=2))
            
        except IOError as e:
            print(f"오류: 상태 또는 정책 파일 쓰기 실패: {e}")
        except Exception as e:
            print(f"오류: 내보내기 중 예기치 않은 오류 발생: {e}")

# --- 사용자가 제공한 기존 함수 ---
def export_rl_policy_means(out_path: str, metrics: dict):
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ip_cd_mean": float(metrics.get("ip_cd_mean", 30.0)),
        "decoy_ratio_mean": float(metrics.get("decoy_ratio_mean", 0.1)),
        "bl_level_mean": float(metrics.get("bl_level_mean", 1.0))
    }
    p.write_text(json.dumps(data, indent=2))