#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 디렉토리: dvd_lite/dvd_attacks_lpc/ml
# 파일명: dataset_manager.py
# 설명: [Enhanced] 데이터 불균형 해소를 위한 강력한 Resampling (Under + Over) 적용

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
        list_of_files = glob.glob(os.path.join(self.processed_dir, 'features_batch_*.csv'))
        if not list_of_files:
            return None
        return max(list_of_files, key=os.path.getctime)

    def balance_training_data(self, X_train, y_train, target_samples=2000, max_samples=5000):
        """
        [핵심] 학습 데이터 균형 맞추기 (Under + Over Sampling)
        - 소수 클래스: target_samples(2000개)까지 증강 (노이즈 추가)
        - 다수 클래스: max_samples(5000개)까지 축소 (무작위 선택)
        """
        logger.info(f"⚖️ [Balancing] 데이터 균형 조정 시작 (Target: {target_samples}, Max: {max_samples})...")
        
        train_df = pd.concat([X_train, y_train], axis=1)
        label_col = y_train.name
        
        class_counts = train_df[label_col].value_counts()
        balanced_dfs = []
        
        for label, count in class_counts.items():
            class_subset = train_df[train_df[label_col] == label]
            
            # 1. 과다 클래스 (Under-sampling)
            if count > max_samples:
                logger.info(f"   -> Label {label}: {count} -> {max_samples} (Under-sampling)")
                resampled_subset = resample(
                    class_subset,
                    replace=False, # 비복원 추출 (줄이기)
                    n_samples=max_samples,
                    random_state=42
                )
                balanced_dfs.append(resampled_subset)
                
            # 2. 소수 클래스 (Over-sampling with Noise)
            elif count < target_samples:
                logger.info(f"   -> Label {label}: {count} -> {target_samples} (Over-sampling + Noise)")
                resampled_subset = resample(
                    class_subset,
                    replace=True, # 복원 추출 (늘리기)
                    n_samples=target_samples,
                    random_state=42
                )
                
                # 수치형 컬럼에 노이즈 추가
                numeric_cols = resampled_subset.select_dtypes(include=[np.number]).columns.tolist()
                if label_col in numeric_cols:
                    numeric_cols.remove(label_col)
                
                # 노이즈 강도 설정 (표준편차의 1%)
                noise = np.random.normal(0, 0.01, resampled_subset[numeric_cols].shape)
                resampled_subset[numeric_cols] += noise
                
                balanced_dfs.append(resampled_subset)
                
            # 3. 적정 클래스 (유지)
            else:
                logger.info(f"   -> Label {label}: {count} (Keep)")
                balanced_dfs.append(class_subset)
            
        # 전체 병합 및 셔플
        final_train_df = pd.concat(balanced_dfs, axis=0)
        final_train_df = final_train_df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        logger.info(f"✅ 균형 조정 완료: 총 {len(train_df)} -> {len(final_train_df)} 샘플.")
        
        return final_train_df.drop(columns=[label_col]), final_train_df[label_col]

    def run(self, input_file=None):
        logger.info("🚀 [Dataset Manager v5.1 (Balanced)] 시작.")
        
        if not input_file:
            input_file = self.get_latest_processed_file()
            if not input_file:
                logger.error("❌ 입력 파일 없음.")
                return
            logger.info(f"[*] 파일 선택: {input_file}")
        
        try:
            df = pd.read_csv(input_file, low_memory=False)
            df = df.apply(pd.to_numeric, errors='ignore')
        except Exception as e:
            logger.error(f"❌ 로드 실패: {e}")
            return

        if 'label' not in df.columns:
            logger.error("❌ 'label' 컬럼 없음.")
            return

        # 학습에 불필요한 컬럼 제거
        drop_cols = ['source', 'log_type', 'attack_name', 'scenario', 
                     'runner_event', 'timestamp', 'current_attack_name', 
                     'container_name', 'docker_name']
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        
        X = df.drop(columns=cols_to_drop + ['label']) # label도 X에서 제외
        y = df['label']
        
        # 수치형만 선택
        X = X.select_dtypes(include=[np.number])
        
        # Train / Test 분리
        logger.info(f"[*] 분할 (test_size={self.test_size})...")
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, stratify=y, random_state=42
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, random_state=42
            )

        # [핵심] 학습 데이터 균형 맞추기 (Target: 2000, Max: 5000)
        X_train_bal, y_train_bal = self.balance_training_data(
            X_train, y_train, target_samples=2000, max_samples=5000
        )

        # 저장
        train_output = pd.concat([X_train_bal, y_train_bal], axis=1)
        test_output = pd.concat([X_test, y_test], axis=1)

        train_path = os.path.join(self.output_dir, "train_dataset.csv")
        test_path = os.path.join(self.output_dir, "test_dataset.csv")

        train_output.to_csv(train_path, index=False)
        test_output.to_csv(test_path, index=False)

        logger.info(f"✅ 저장 완료: Train({len(train_output)}), Test({len(test_output)})")

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