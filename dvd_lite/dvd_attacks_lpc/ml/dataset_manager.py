#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 디렉토리: dvd_lite/dvd_attacks_lpc/ml
# 파일명: dataset_manager.py
# 설명: 전처리된 CSV 데이터를 Train/Test로 분리하고, 
#       [NEW] 학습 데이터(Train Set)의 소수 클래스 불균형을 해소하기 위한 데이터 증강 로직 추가

import os
import glob
import logging
import argparse
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils import resample

# ----------------------------
# 로깅 설정
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DatasetManager")

# ----------------------------
# 경로 설정
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROCESSED_DIR = os.path.join(BASE_DIR, "processed_data")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "output")

class DatasetManager:
    def __init__(
        self, 
        processed_dir=DEFAULT_PROCESSED_DIR, 
        output_dir=DEFAULT_OUTPUT_DIR,
        test_size=0.2
    ):
        self.processed_dir = processed_dir
        self.output_dir = output_dir
        self.test_size = test_size
        
        os.makedirs(self.output_dir, exist_ok=True)

    def get_latest_processed_file(self):
        """processed_data 디렉토리에서 가장 최근 생성된 CSV 파일을 찾습니다."""
        list_of_files = glob.glob(os.path.join(self.processed_dir, 'features_batch_*.csv'))
        if not list_of_files:
            return None
        return max(list_of_files, key=os.path.getctime)

    def augment_training_data(self, X_train, y_train, min_samples=1000):
        """
        [핵심 로직] 학습 데이터 내 소수 클래스를 증강합니다.
        - 단순히 복제만 하면 과적합되므로, 약간의 가우시안 노이즈를 추가합니다.
        - 목표 개수(min_samples)보다 적은 클래스만 증강합니다.
        """
        logger.info(f"⚖️ [Data Augmentation] 소수 클래스 증강 시작 (목표: 클래스 당 최소 {min_samples}개)...")
        
        # 데이터프레임으로 합치기 (편의상)
        train_df = pd.concat([X_train, y_train], axis=1)
        label_col = y_train.name
        
        # 클래스별 개수 확인
        class_counts = train_df[label_col].value_counts()
        augmented_dfs = []
        
        for label, count in class_counts.items():
            class_subset = train_df[train_df[label_col] == label]
            
            # 1. 메이저 클래스: 그대로 유지
            if count >= min_samples:
                augmented_dfs.append(class_subset)
                continue
                
            # 2. 마이너 클래스: 증강 (Oversampling with Noise)
            logger.info(f"   -> Label {label}: {count}개 -> {min_samples}개로 증강 (Noise Injection)")
            
            # 필요한 만큼 리샘플링 (복원 추출)
            resampled_subset = resample(
                class_subset,
                replace=True,
                n_samples=min_samples,
                random_state=42
            )
            
            # 수치형 컬럼에만 미세한 노이즈 추가 (표준편차의 1% 수준)
            # (문자열이나 범주형 데이터가 있다면 제외해야 함. 여기선 X_train이 대부분 수치형이라 가정)
            numeric_cols = resampled_subset.select_dtypes(include=[np.number]).columns.tolist()
            # 레이블 컬럼은 제외
            if label_col in numeric_cols:
                numeric_cols.remove(label_col)
                
            noise = np.random.normal(0, 0.01, resampled_subset[numeric_cols].shape)
            resampled_subset[numeric_cols] += noise
            
            augmented_dfs.append(resampled_subset)
            
        # 전체 병합 및 셔플
        final_train_df = pd.concat(augmented_dfs, axis=0)
        final_train_df = final_train_df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        logger.info(f"✅ 증강 완료: 총 {len(train_df)} -> {len(final_train_df)} 샘플로 증가.")
        
        return final_train_df.drop(columns=[label_col]), final_train_df[label_col]

    def run(self, input_file=None):
        logger.info("🚀 [Dataset Manager v5.0 (Augmented)] 데이터셋 분할 및 증강 시작.")
        
        # 1. 입력 파일 결정
        if not input_file:
            input_file = self.get_latest_processed_file()
            if not input_file:
                logger.error(f"❌ '{self.processed_dir}'에서 처리된 데이터 파일을 찾을 수 없습니다.")
                return
            logger.info(f"[*] 최신 파일 자동 선택: {input_file}")
        else:
            logger.info(f"[*] 지정된 파일 로드: {input_file}")

        # 2. 데이터 로드 (DtypeWarning 방지 옵션 추가)
        try:
            df = pd.read_csv(input_file, low_memory=False)
            
            # 혹시 모를 문자열 'None' 같은 값들 처리
            df = df.apply(pd.to_numeric, errors='ignore') # 가능한 것만 변환
            
        except Exception as e:
            logger.error(f"❌ 데이터 로드 실패: {e}")
            return

        logger.info(f"[*] 로드 완료: {len(df)} 샘플, {len(df.columns)} 컬럼")

        # 3. X, y 분리
        if 'label' not in df.columns:
            logger.error("❌ 'label' 컬럼이 없습니다. data_builder가 올바르게 실행되었는지 확인하세요.")
            return

        # 학습에 불필요한 메타데이터 컬럼 제외
        drop_cols = ['label', 'source', 'log_type', 'attack_name', 'scenario', 
                     'runner_event', 'timestamp', 'current_attack_name', 
                     'container_name', 'docker_name']
        # 실제 존재하는 컬럼만 drop
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        
        X = df.drop(columns=cols_to_drop)
        y = df['label']
        
        # 숫자가 아닌 컬럼은 학습에서 제외 (One-Hot Encoding 등이 없으므로)
        X = X.select_dtypes(include=[np.number])
        logger.info(f"[*] 학습용 피처 수(숫자형): {X.shape[1]}")

        # 4. Train / Test 분리 (Stratified)
        logger.info(f"[*] train/test 분할 (test_size={self.test_size}, stratify=y)...")
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, stratify=y, random_state=42
            )
        except ValueError as e:
            logger.warning(f"⚠️ 계층적 분할 실패 (일부 클래스 샘플 부족): {e}")
            logger.warning("-> 일반 랜덤 분할로 전환합니다.")
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, random_state=42
            )

        # 5. [NEW] 학습 데이터 증강 (오버샘플링)
        # 최소 샘플 수 설정: 전체 데이터의 1% 혹은 고정값 (예: 1000개)
        # Label 21, 22 같이 30개인 데이터를 1000개로 늘림
        X_train_aug, y_train_aug = self.augment_training_data(X_train, y_train, min_samples=2000)

        # 6. 저장
        train_output = pd.concat([X_train_aug, y_train_aug], axis=1)
        test_output = pd.concat([X_test, y_test], axis=1)

        train_path = os.path.join(self.output_dir, "train_dataset.csv")
        test_path = os.path.join(self.output_dir, "test_dataset.csv")

        train_output.to_csv(train_path, index=False)
        test_output.to_csv(test_path, index=False)

        logger.info(f"✅ train 데이터셋 저장 (증강됨): {train_path} ({len(train_output)} rows)")
        logger.info(f"✅ test  데이터셋 저장 (원본유지): {test_path} ({len(test_output)} rows)")
        logger.info("✅ [Dataset Manager] 완료.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--processed-dir", default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input", help="Direct path to input csv")
    
    args = parser.parse_args()
    
    manager = DatasetManager(
        processed_dir=args.processed_dir,
        output_dir=args.output_dir,
        test_size=args.test_size
    )
    manager.run(input_file=args.input)