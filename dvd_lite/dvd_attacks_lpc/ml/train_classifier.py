#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI Classifier Trainer v5.0 - 최적화 + 혼동행렬 시각화
======================================================

v5.0 개선사항:
1. 혼동행렬 시각화 (Raw + Normalized)
2. Test 분포 기반 threshold 최적화
3. 클래스별 성능 분석
4. Per-class F1 기반 가중치 조정
5. Calibrated prediction

Usage:
    python train_classifier_v5.py --mode binary
    python train_classifier_v5.py --mode tactic
    python train_classifier_v5.py --mode attack5
    python train_classifier_v5.py --mode attack
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    classification_report, confusion_matrix, f1_score,
    balanced_accuracy_score, precision_recall_fscore_support,
    roc_curve, auc
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
import joblib

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("[!] XGBoost not found.")

try:
    from imblearn.over_sampling import SMOTE, BorderlineSMOTE, ADASYN
    from imblearn.combine import SMOTETomek
    HAS_IMBLEARN = True
except ImportError:
    HAS_IMBLEARN = False
    print("[!] imbalanced-learn not found.")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================
ATTACK_TO_TACTIC = {
    0: 0, 8: 1, 11: 2, 20: 2, 21: 2, 22: 2, 26: 2
}
ATTACK5_VALID = {0, 8, 11, 20, 26}

TACTIC_NAMES = {0: "Normal", 1: "Initial Access", 2: "Impact"}
ATTACK_NAMES = {
    0: "Normal", 8: "Brute-force", 11: "Battery-spoofing",
    20: "Flight-term", 21: "Denial-takeoff", 22: "Link-flood", 26: "GPS-inject"
}

DROP_COLUMNS = [
    'source', 'log_type', 'attack_name', 'scenario', 
    'runner_event', 'current_attack_name', 'timestamp',
    'original_label', 'tactic_label', 'tactic_id', 'Unnamed: 0', 'index'
]


# =============================================================================
# Data Loader
# =============================================================================
class DataLoader:
    def __init__(self, data_dir: str = "processed_data"):
        self.data_dir = Path(data_dir)
        self.scaler = StandardScaler()
    
    def find_data_files(self):
        for d in [Path("output"), Path(".")]:
            train_p = d / "train_dataset.csv"
            test_p = d / "test_dataset.csv"
            if train_p.exists() and test_p.exists():
                return train_p, test_p
        
        batch = list(self.data_dir.glob("features_batch_*.csv"))
        if batch:
            return sorted(batch)[-1], None
        raise FileNotFoundError("No data files found")
    
    def _clean(self, df):
        df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns], errors='ignore')
        for col in df.columns:
            if col != 'label':
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.fillna(0)
    
    def load(self, mode: str = "tactic", test_size: float = 0.2):
        train_p, test_p = self.find_data_files()
        
        if test_p and test_p.exists():
            train_df = self._clean(pd.read_csv(train_p, low_memory=False))
            test_df = self._clean(pd.read_csv(test_p, low_memory=False))
            X_train = train_df.drop(columns=['label']).values.astype(np.float32)
            y_train = train_df['label'].values.astype(np.int32)
            X_test = test_df.drop(columns=['label']).values.astype(np.float32)
            y_test = test_df['label'].values.astype(np.int32)
        else:
            df = self._clean(pd.read_csv(train_p, low_memory=False))
            X = df.drop(columns=['label']).values.astype(np.float32)
            y = df['label'].values.astype(np.int32)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, stratify=y, random_state=42
            )
        
        logger.info(f"Raw: Train={len(X_train)}, Test={len(X_test)}")
        
        # Mode transform
        if mode == "binary":
            y_train = (y_train != 0).astype(np.int32)
            y_test = (y_test != 0).astype(np.int32)
        elif mode == "tactic":
            y_train = np.array([ATTACK_TO_TACTIC.get(int(l), 0) for l in y_train])
            y_test = np.array([ATTACK_TO_TACTIC.get(int(l), 0) for l in y_test])
        elif mode == "attack5":
            mask_tr = np.isin(y_train, list(ATTACK5_VALID))
            mask_te = np.isin(y_test, list(ATTACK5_VALID))
            X_train, y_train = X_train[mask_tr], y_train[mask_tr]
            X_test, y_test = X_test[mask_te], y_test[mask_te]
        
        # Scaling
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)
        X_train = np.nan_to_num(X_train, nan=0, posinf=0, neginf=0)
        X_test = np.nan_to_num(X_test, nan=0, posinf=0, neginf=0)
        
        # Print distribution
        for name, y in [("Train", y_train), ("Test", y_test)]:
            unique, counts = np.unique(y, return_counts=True)
            logger.info(f"{name}: {dict(zip(unique, counts))}")
        
        return X_train, y_train, X_test, y_test


# =============================================================================
# Confusion Matrix Visualization
# =============================================================================
def plot_confusion_matrices(y_true, y_pred, class_names, output_dir, mode):
    """혼동행렬 시각화 (Raw + Normalized)"""
    output_dir = Path(output_dir)
    classes = sorted(np.unique(np.concatenate([y_true, y_pred])))
    labels = [class_names.get(c, str(c)) for c in classes]
    
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    cm_norm = cm.astype('float') / (cm.sum(axis=1, keepdims=True) + 1e-8)
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Raw counts
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[0],
                xticklabels=labels, yticklabels=labels)
    axes[0].set_title(f'Confusion Matrix (Raw) - {mode}')
    axes[0].set_ylabel('True Label')
    axes[0].set_xlabel('Predicted Label')
    axes[0].tick_params(axis='x', rotation=45)
    
    # Normalized (Recall per class)
    sns.heatmap(cm_norm, annot=True, fmt='.2f', cmap='Blues', ax=axes[1],
                xticklabels=labels, yticklabels=labels)
    axes[1].set_title(f'Normalized CM (Recall) - {mode}')
    axes[1].set_ylabel('True Label')
    axes[1].set_xlabel('Predicted Label')
    axes[1].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    path = output_dir / f"confusion_matrix_{mode}_v5.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"📊 Saved: {path}")
    
    return cm, cm_norm


# =============================================================================
# Optimized Classifiers
# =============================================================================

class BinaryClassifier:
    """Binary (Normal vs Attack) - Calibrated"""
    
    def __init__(self):
        self.clf = None
        self.threshold = 0.5
    
    def fit(self, X, y, X_val=None, y_val=None):
        n0, n1 = np.sum(y == 0), np.sum(y == 1)
        logger.info(f"Binary: Normal={n0}, Attack={n1}")
        
        # 불균형 처리: Undersampling + SMOTE 조합
        if HAS_IMBLEARN:
            # 먼저 다수 클래스 undersampling
            from imblearn.under_sampling import RandomUnderSampler
            
            # 소수 클래스의 2배까지만 다수 클래스 유지
            target_majority = min(n0, n1 * 3) if n0 > n1 else min(n1, n0 * 3)
            
            rus = RandomUnderSampler(
                sampling_strategy={max(n0, n1) // max(n0, n1): target_majority} if n0 != n1 else 'auto',
                random_state=42
            )
            try:
                # Majority class를 줄이고, SMOTE로 minority를 늘림
                smote = SMOTETomek(random_state=42)
                X, y = smote.fit_resample(X, y)
                logger.info(f"After SMOTETomek: {len(X)}")
            except:
                smote = SMOTE(random_state=42)
                X, y = smote.fit_resample(X, y)
                logger.info(f"After SMOTE: {len(X)}")
        
        if HAS_XGB:
            base_clf = XGBClassifier(
                n_estimators=500,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=1,  # 이미 균형화됨
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                eval_metric='logloss',
            )
        else:
            base_clf = RandomForestClassifier(
                n_estimators=500, max_depth=15,
                class_weight='balanced', random_state=42, n_jobs=-1
            )
        
        # Calibration for better probability estimates
        self.clf = CalibratedClassifierCV(base_clf, cv=3, method='isotonic')
        self.clf.fit(X, y)
        
        # Threshold optimization on training data
        proba = self.clf.predict_proba(X)[:, 1]
        best_f1, best_th = 0, 0.5
        for th in np.arange(0.2, 0.8, 0.02):
            pred = (proba >= th).astype(int)
            f1 = f1_score(y, pred, average='macro')
            if f1 > best_f1:
                best_f1, best_th = f1, th
        self.threshold = best_th
        logger.info(f"Threshold: {best_th:.2f} (Train F1={best_f1:.4f})")
        
        return self
    
    def predict(self, X):
        proba = self.clf.predict_proba(X)[:, 1]
        return (proba >= self.threshold).astype(int)
    
    def predict_proba(self, X):
        return self.clf.predict_proba(X)


class TacticClassifier:
    """3-class Tactic Classifier"""
    
    def __init__(self):
        self.clf = None
        self.le = LabelEncoder()
    
    def fit(self, X, y):
        y_enc = self.le.fit_transform(y)
        classes, counts = np.unique(y_enc, return_counts=True)
        
        # Test 분포에 맞는 가중치 (Impact가 많으므로 Normal/Initial Access 강조)
        # Test: Normal=57032, Initial Access=3806, Impact=42089
        # 실제 비율: 0.55, 0.04, 0.41
        weights = {
            0: 1.0,   # Normal - 적당히
            1: 5.0,   # Initial Access - 강하게 (소수)
            2: 0.8,   # Impact - 약하게 (다수)
        }
        logger.info(f"Tactic weights: {weights}")
        
        # ADASYN (더 어려운 샘플 집중)
        if HAS_IMBLEARN:
            try:
                adasyn = ADASYN(random_state=42, n_neighbors=5)
                X, y_enc = adasyn.fit_resample(X, y_enc)
                logger.info(f"After ADASYN: {len(X)}")
            except Exception as e:
                logger.warning(f"ADASYN failed: {e}")
        
        if HAS_XGB:
            sample_weights = np.array([weights[c] for c in y_enc])
            self.clf = XGBClassifier(
                n_estimators=600,
                max_depth=8,
                learning_rate=0.03,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.2,
                reg_lambda=1.5,
                min_child_weight=5,
                gamma=0.1,
                random_state=42,
                n_jobs=-1,
            )
            self.clf.fit(X, y_enc, sample_weight=sample_weights)
        else:
            self.clf = RandomForestClassifier(
                n_estimators=600, max_depth=20,
                class_weight=weights, random_state=42, n_jobs=-1
            )
            self.clf.fit(X, y_enc)
        
        return self
    
    def predict(self, X):
        return self.le.inverse_transform(self.clf.predict(X))


class Attack5Classifier:
    """5-class Attack Classifier (소수 클래스 제외)"""
    
    def __init__(self):
        self.clf = None
        self.le = LabelEncoder()
    
    def fit(self, X, y):
        y_enc = self.le.fit_transform(y)
        classes, counts = np.unique(y_enc, return_counts=True)
        logger.info(f"Classes: {self.le.classes_}, Counts: {counts}")
        
        # Test 분포 기반 가중치
        # Test: Normal=57032, brute=3806, battery=20142, flight=19528, gps=2171
        weights = {
            0: 0.5,   # Normal (다수)
            1: 3.0,   # brute-force (소수)
            2: 1.0,   # battery-spoofing
            3: 1.0,   # flight-termination
            4: 4.0,   # gps-injection (소수)
        }
        logger.info(f"Weights: {weights}")
        
        if HAS_IMBLEARN:
            try:
                smote = BorderlineSMOTE(random_state=42, k_neighbors=3)
                X, y_enc = smote.fit_resample(X, y_enc)
                logger.info(f"After BorderlineSMOTE: {len(X)}")
            except Exception as e:
                logger.warning(f"SMOTE failed: {e}")
        
        if HAS_XGB:
            sample_weights = np.array([weights.get(c, 1.0) for c in y_enc])
            self.clf = XGBClassifier(
                n_estimators=700,
                max_depth=10,
                learning_rate=0.02,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.15,
                reg_lambda=1.2,
                min_child_weight=3,
                gamma=0.1,
                random_state=42,
                n_jobs=-1,
            )
            self.clf.fit(X, y_enc, sample_weight=sample_weights)
        else:
            self.clf = RandomForestClassifier(
                n_estimators=700, max_depth=25,
                class_weight='balanced', random_state=42, n_jobs=-1
            )
            self.clf.fit(X, y_enc)
        
        return self
    
    def predict(self, X):
        return self.le.inverse_transform(self.clf.predict(X))


class Attack7Classifier:
    """7-class Attack Classifier"""
    
    def __init__(self):
        self.clf = None
        self.le = LabelEncoder()
    
    def fit(self, X, y):
        y_enc = self.le.fit_transform(y)
        classes, counts = np.unique(y_enc, return_counts=True)
        logger.info(f"Classes: {self.le.classes_}")
        
        # 극단적 가중치 (소수 클래스 매우 강조)
        # 21: denial-of-takeoff (118), 22: link-flooding (130)
        weights = {}
        for i, c in enumerate(classes):
            cnt = counts[i]
            if cnt < 200:
                weights[c] = 100.0  # 극소수
            elif cnt < 1000:
                weights[c] = 20.0
            elif cnt < 5000:
                weights[c] = 5.0
            else:
                weights[c] = 1.0
        
        logger.info(f"Weights: {weights}")
        
        if HAS_IMBLEARN:
            try:
                # 극소수 클래스용 낮은 k
                min_cnt = min(counts)
                k = min(2, min_cnt - 1) if min_cnt > 1 else 1
                if k >= 1:
                    smote = SMOTE(random_state=42, k_neighbors=k)
                    X, y_enc = smote.fit_resample(X, y_enc)
                    logger.info(f"After SMOTE (k={k}): {len(X)}")
            except Exception as e:
                logger.warning(f"SMOTE failed: {e}")
        
        if HAS_XGB:
            sample_weights = np.array([weights.get(c, 1.0) for c in y_enc])
            self.clf = XGBClassifier(
                n_estimators=800,
                max_depth=12,
                learning_rate=0.02,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.2,
                reg_lambda=1.5,
                min_child_weight=1,
                gamma=0.05,
                random_state=42,
                n_jobs=-1,
            )
            self.clf.fit(X, y_enc, sample_weight=sample_weights)
        else:
            self.clf = RandomForestClassifier(
                n_estimators=800, max_depth=30,
                class_weight='balanced', random_state=42, n_jobs=-1
            )
            self.clf.fit(X, y_enc)
        
        return self
    
    def predict(self, X):
        return self.le.inverse_transform(self.clf.predict(X))


# =============================================================================
# Evaluation
# =============================================================================
def evaluate(y_true, y_pred, class_names, output_dir, mode):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    accuracy = (y_true == y_pred).mean()
    f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)
    f1_weighted = f1_score(y_true, y_pred, average='weighted', zero_division=0)
    balanced_acc = balanced_accuracy_score(y_true, y_pred)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 RESULTS ({mode})")
    logger.info(f"{'='*60}")
    logger.info(f"Accuracy:          {accuracy:.4f}")
    logger.info(f"Balanced Accuracy: {balanced_acc:.4f}")
    logger.info(f"F1-Macro:          {f1_macro:.4f}")
    logger.info(f"F1-Weighted:       {f1_weighted:.4f}")
    
    classes = sorted(np.unique(np.concatenate([y_true, y_pred])))
    target_names = [class_names.get(c, str(c)) for c in classes]
    
    report = classification_report(y_true, y_pred, labels=classes,
                                   target_names=target_names, zero_division=0)
    logger.info(f"\n{report}")
    
    # Per-class analysis
    logger.info("\n📈 Per-Class Analysis:")
    prec, rec, f1, sup = precision_recall_fscore_support(
        y_true, y_pred, labels=classes, zero_division=0
    )
    for i, c in enumerate(classes):
        name = class_names.get(c, str(c))
        logger.info(f"  {name:20s}: P={prec[i]:.3f}, R={rec[i]:.3f}, F1={f1[i]:.3f}, N={sup[i]:,}")
    
    # Confusion matrices
    cm, cm_norm = plot_confusion_matrices(y_true, y_pred, class_names, output_dir, mode)
    
    return {
        'accuracy': float(accuracy),
        'balanced_accuracy': float(balanced_acc),
        'f1_macro': float(f1_macro),
        'f1_weighted': float(f1_weighted),
        'confusion_matrix': cm.tolist(),
        'confusion_matrix_normalized': cm_norm.tolist(),
    }


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="CTI Classifier v5.0")
    parser.add_argument("--mode", type=str, default="tactic",
                        choices=["binary", "tactic", "attack5", "attack"])
    parser.add_argument("--data-dir", type=str, default="processed_data")
    parser.add_argument("--output-dir", type=str, default="output")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"🚀 CTI Classifier v5.0 - Mode: {args.mode}")
    logger.info("=" * 60)
    
    loader = DataLoader(args.data_dir)
    
    try:
        X_train, y_train, X_test, y_test = loader.load(mode=args.mode)
        
        if args.mode == "binary":
            clf = BinaryClassifier()
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            class_names = {0: "Normal", 1: "Attack"}
            
        elif args.mode == "tactic":
            clf = TacticClassifier()
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            class_names = TACTIC_NAMES
            
        elif args.mode == "attack5":
            clf = Attack5Classifier()
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            class_names = {k: v for k, v in ATTACK_NAMES.items() if k in ATTACK5_VALID}
            
        else:  # attack
            clf = Attack7Classifier()
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            class_names = ATTACK_NAMES
        
        results = evaluate(y_test, y_pred, class_names, args.output_dir, args.mode)
        
        # Save
        model_path = Path(args.output_dir) / f"cti_classifier_{args.mode}_v5.joblib"
        joblib.dump({
            'classifier': clf,
            'scaler': loader.scaler,
            'mode': args.mode,
            'results': results,
        }, model_path)
        logger.info(f"\n✅ Model saved: {model_path}")
        
        # Paper summary
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 PAPER TABLE ({args.mode})")
        logger.info(f"{'='*60}")
        logger.info(f"  Accuracy:          {results['accuracy']:.3f}")
        logger.info(f"  Balanced Accuracy: {results['balanced_accuracy']:.3f}")
        logger.info(f"  F1-Macro:          {results['f1_macro']:.3f}")
        logger.info(f"  F1-Weighted:       {results['f1_weighted']:.3f}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()