import pandas as pd
from sklearn.utils import resample

class ExperimentDataset:
    """연구용 데이터셋을 체계적으로 생성하고 관리합니다."""

    def __init__(self, full_dataset_path: str):
        self.df = pd.read_csv(full_dataset_path)
        print(f"[*] 원본 데이터셋 로드 완료: {len(self.df)}개 레코드")

    def create_balanced_dataset(self, attack_name: str, flight_mode: str, normal_ratio=1.0):
        """특정 공격과 비행 시나리오에 맞는 균형잡힌 데이터셋을 생성합니다."""
        
        # (구현 필요) 이 부분은 로그에서 공격 유형과 비행 모드를 정확히 식별하는 로직이 필요.
        # 지금은 'label_attack'과 'data_mode'로 단순화하여 예시를 작성.
        
        attack_data = self.df[(self.df['label_attack'] == 'Attack')] # & (df['attack_type'] == attack_name)
        normal_data = self.df[(self.df['label_attack'] == 'Normal') & (self.df['data_mode'] == flight_mode)]

        if attack_data.empty or normal_data.empty:
            print(f"[!] 경고: '{attack_name}' 공격 또는 '{flight_mode}' 모드에 대한 데이터가 부족합니다.")
            return pd.DataFrame()

        # Normal 데이터를 Attack 데이터 수에 맞춰 언더샘플링
        n_samples = int(len(attack_data) * normal_ratio)
        normal_sampled = resample(normal_data, 
                                  replace=False, 
                                  n_samples=n_samples, 
                                  random_state=42)

        balanced_df = pd.concat([attack_data, normal_sampled])
        print(f"[*] '{attack_name}'/'{flight_mode}' 시나리오용 균형 데이터셋 생성 완료.")
        print(f"    (Normal: {len(normal_sampled)}, Attack: {len(attack_data)})")
        
        return balanced_df.sample(frac=1, random_state=42).reset_index(drop=True)

if __name__ == '__main__':
    manager = ExperimentDataset('output/labeled_cti_dataset.csv')
    
    # 예시: GPS 스푸핑 공격 & LOITER 모드에서의 데이터셋 생성
    exp_df = manager.create_balanced_dataset('gps-spoofing.sh', 'LOITER')
    
    if not exp_df.empty:
        print("\n생성된 실험 데이터셋 정보:")
        print(exp_df['label_attack'].value_counts())