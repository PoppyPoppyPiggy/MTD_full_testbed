#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset Manager v2.0 (Paper-Ready)
===================================
데이터 불균형 해소 및 Train/Test 분리
"""

import os
import glob
import json
import logging
import argparse
from typing import Optional

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils import resample

try:
    from imblearn.over_sampling import SMOTE
    HAS_IMBLEARN = True
except ImportError:
    HAS_IMBLEARN = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DatasetManager")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROCESSED_DIR = os.path.join(BASE_DIR, "processed_data")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DEFAULT_TACTIC_FILE = os.path.join(BASE_DIR, "tactic_mapping.json")


class DatasetManager:
    def __init__(
        self, 
        processed_dir: str = DEFAULT_PROCESSED_DIR, 
        output_dir: str = DEFAULT_OUTPUT_DIR,
        tactic_file: str = DEFAULT_TACTIC_FILE,
        test_size: float = 0.2,
        use_tactic_labels: bool = False
    ):
        self.processed_dir = processed_dir
        self.output_dir = output_dir
        self.test_size = test_size
        self.use_tactic_labels = use_tactic_labels
        
        self.tactic_mapping = {}
        self.tactic_names = {}
        
        os.makedirs(self.output_dir, exist_ok=True)

        if os.path.exists(tactic_file):
            try:
                with open(tactic_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tactic_mapping = {int(k): int(v) for k, v in data.get("attack_to_tactic", {}).items()}
                    self.tactic_names = {int(k): v for k, v in data.get("tactic_names", {}).items()}
                logger.info(f"✓ Tactic mapping: {len(self.tactic_names)} 전술")
            except Exception as e:
                logger.error(f"Tactic mapping 로드 실패: {e}")

    def get_latest_processed_file(self) -> Optional[str]:
        list_of_files = glob.glob(os.path.join(self.processed_dir, 'features_batch_*.csv'))
        if not list_of_files:
            return None
        return max(list_of_files, key=os.path.getctime)

    def convert_to_tactic_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'label' not in df.columns:
            return df
        df['original_label'] = df['label'].copy()
        df['label'] = df['label'].map(lambda x: self.tactic_mapping.get(int(x), 0))
        logger.info("✓ 전술 레벨 라벨 변환 완료")
        return df

    def balance_training_data(
        self, 
        X_train: pd.DataFrame, 
        y_train: pd.Series, 
        target_samples: int = 3000, 
        max_samples: int = 5000,
        min_samples: int = 500
    ) -> tuple:
        logger.info(f"⚖️ [Balancing] Target: {target_samples}, Max: {max_samples}, Min: {min_samples}")
        
        train_df = pd.concat([X_train, y_train], axis=1)
        label_col = y_train.name
        
        class_counts = train_df[label_col].value_counts()
        balanced_dfs = []
        
        for label, count in class_counts.items():
            class_subset = train_df[train_df[label_col] == label]
            
            if count > max_samples:
                logger.info(f"   -> Label {label}: {count:,} -> {max_samples:,} (Under)")
                resampled = resample(class_subset, replace=False, n_samples=max_samples, random_state=42)
                balanced_dfs.append(resampled)
                
            elif count < min_samples:
                actual_target = max(target_samples, min_samples)
                logger.info(f"   -> Label {label}: {count:,} -> {actual_target:,} (Over+Noise)")
                
                resampled = resample(class_subset, replace=True, n_samples=actual_target, random_state=42)
                
                numeric_cols = resampled.select_dtypes(include=[np.number]).columns.tolist()
                if label_col in numeric_cols:
                    numeric_cols.remove(label_col)
                
                for col in numeric_cols:
                    col_std = resampled[col].std()
                    if col_std > 0:
                        noise = np.random.normal(0, col_std * 0.05, len(resampled))
                        resampled[col] = resampled[col] + noise
                
                balanced_dfs.append(resampled)
                
            elif count < target_samples:
                logger.info(f"   -> Label {label}: {count:,} -> {target_samples:,} (Over)")
                resampled = resample(class_subset, replace=True, n_samples=target_samples, random_state=42)
                balanced_dfs.append(resampled)
                
            else:
                logger.info(f"   -> Label {label}: {count:,} (Keep)")
                balanced_dfs.append(class_subset)
        
        final_df = pd.concat(balanced_dfs, axis=0)
        final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        logger.info(f"✅ 균형 조정 완료: {len(train_df):,} -> {len(final_df):,}")
        
        return final_df.drop(columns=[label_col]), final_df[label_col]

    def balance_with_smote(self, X_train: pd.DataFrame, y_train: pd.Series) -> tuple:
        if not HAS_IMBLEARN:
            logger.warning("⚠️ imbalanced-learn 없음")
            return self.balance_training_data(X_train, y_train)
            
        logger.info("⚖️ [SMOTE] 합성 샘플 생성...")
        
        class_counts = y_train.value_counts()
        min_samples = class_counts.min()
        k = min(5, min_samples - 1) if min_samples > 1 else 1
        
        if k < 1:
            return self.balance_training_data(X_train, y_train)
        
        try:
            smote = SMOTE(sampling_strategy='not majority', k_neighbors=k, random_state=42)
            X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
            logger.info(f"✅ SMOTE: {len(X_train):,} -> {len(X_resampled):,}")
            return X_resampled, y_resampled
        except Exception as e:
            logger.error(f"SMOTE 실패: {e}")
            return self.balance_training_data(X_train, y_train)

    def run(self, input_file: Optional[str] = None, use_smote: bool = False):
        logger.info("🚀 [Dataset Manager v2.0] 시작")
        
        if not input_file:
            input_file = self.get_latest_processed_file()
            if not input_file:
                logger.error("❌ 입력 파일 없음")
                return
            logger.info(f"[*] 파일: {input_file}")
        
        try:
            df = pd.read_csv(input_file, low_memory=False)
            cols = df.columns
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce').fillna(0)
        except Exception as e:
            logger.error(f"❌ 로드 실패: {e}")
            return

        if 'label' not in df.columns:
            logger.error("❌ 'label' 컬럼 없음")
            return

        if self.use_tactic_labels:
            df = self.convert_to_tactic_labels(df)

        drop_cols = ['source', 'log_type', 'attack_name', 'scenario', 
                     'runner_event', 'current_attack_name', 'timestamp',
                     'original_label', 'tactic_label']
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        
        X = df.drop(columns=cols_to_drop + ['label'], errors='ignore')
        y = df['label']
        X = X.select_dtypes(include=[np.number])
        
        logger.info(f"[*] 분할 (test_size={self.test_size})...")
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, stratify=y, random_state=42
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, random_state=42
            )

        if use_smote and HAS_IMBLEARN:
            X_train_bal, y_train_bal = self.balance_with_smote(X_train, y_train)
        else:
            X_train_bal, y_train_bal = self.balance_training_data(
                X_train, y_train, target_samples=3000, max_samples=5000, min_samples=500
            )

        train_output = pd.concat([X_train_bal, y_train_bal], axis=1)
        test_output = pd.concat([X_test, y_test], axis=1)

        train_path = os.path.join(self.output_dir, "train_dataset.csv")
        test_path = os.path.join(self.output_dir, "test_dataset.csv")

        train_output.to_csv(train_path, index=False)
        test_output.to_csv(test_path, index=False)

        logger.info(f"✅ 저장: Train({len(train_output):,}), Test({len(test_output):,})")
        
        self._print_distribution(y_train_bal, "Train (Balanced)")
        self._print_distribution(y_test, "Test")

    def _print_distribution(self, y: pd.Series, name: str):
        logger.info(f"\n📊 {name} 분포:")
        counts = y.value_counts().sort_index()
        for label, count in counts.items():
            label_name = self.tactic_names.get(int(label), f"Label-{label}")
            pct = count / len(y) * 100
            logger.info(f"   [{label}] {label_name}: {count:,} ({pct:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dataset Manager v2.0")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--processed-dir", default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input", help="Direct input CSV path")
    parser.add_argument("--smote", action="store_true")
    parser.add_argument("--tactic-level", action="store_true")
    args = parser.parse_args()
    
    manager = DatasetManager(
        processed_dir=args.processed_dir,
        output_dir=args.output_dir,
        test_size=args.test_size,
        use_tactic_labels=args.tactic_level
    )
    manager.run(input_file=args.input, use_smote=args.smote)
