import pandas as pd

class AttackTypeClassifier:
    """공격 유형별 특화된 룰 기반 및 통계적 탐지 시스템입니다."""

    def __init__(self, telemetry_df: pd.DataFrame):
        self.telemetry = telemetry_df.sort_values('ts').reset_index(drop=True)
        self.detectors = {
            'gps_spoofing': self.detect_gps_anomalies,
            'sensor_jamming': self.detect_sensor_failures,
            'command_injection': self.detect_command_anomalies,
        }

    def detect_gps_anomalies(self) -> pd.Series:
        """GPS 스푸핑 의심 점수를 계산합니다."""
        # 위치의 급격한 변화(점프) 계산
        lat_diff = self.telemetry['data_lat'].diff().abs()
        lon_diff = self.telemetry['data_lon'].diff().abs()
        position_jump_score = (lat_diff + lon_diff) * 1e5 # 스케일링
        
        # 속도와 위치 변화의 불일치성
        # (구현 필요: GPS 속도와 IMU 기반 속도 추정치 비교)
        
        return position_jump_score.fillna(0)

    def detect_sensor_failures(self) -> pd.Series:
        """센서 재밍(값 고정 등) 의심 점수를 계산합니다."""
        # 특정 시간 윈도우 내에서 센서 값의 표준편차가 0에 가까운지 확인
        rolling_std = self.telemetry['data_pitch_deg'].rolling(window=10).std()
        jamming_score = (1 / (rolling_std + 0.001)).fillna(0) # 표준편차가 0일수록 점수 높음
        return jamming_score

    def detect_command_anomalies(self) -> pd.Series:
        """비정상적인 명령 패턴을 탐지합니다."""
        # (구현 필요: STATUSTEXT 로그 분석, 비정상적인 모드 변경 빈도 등)
        return pd.Series(0, index=self.telemetry.index)

    def run_all_detectors(self) -> pd.DataFrame:
        """모든 특화 탐지기를 실행하고 결과를 데이터프레임으로 반환합니다."""
        results = pd.DataFrame(index=self.telemetry.index)
        results['ts'] = self.telemetry['ts']
        for name, func in self.detectors.items():
            results[f'score_{name}'] = func()
        return results

if __name__ == '__main__':
    # 예시: 데이터셋을 로드하여 각 공격 유형에 대한 의심 점수를 계산
    try:
        df = pd.read_csv('output/labeled_cti_dataset.csv')
        telemetry_data = df[df['type'] == 'drone_state_detailed'].copy()
        
        special_detector = AttackTypeClassifier(telemetry_data)
        scores_df = special_detector.run_all_detectors()
        
        print("특화 탐지기 실행 결과 (상위 5개):")
        print(scores_df.head())
        
        scores_df.to_csv('output/specialized_detection_scores.csv', index=False)
        print("\n결과를 'output/specialized_detection_scores.csv'에 저장했습니다.")
        
    except FileNotFoundError:
        print("[!] 'labeled_cti_dataset.csv' 파일이 필요합니다. data_builder.py를 먼저 실행하세요.")