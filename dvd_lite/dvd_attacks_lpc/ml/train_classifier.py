#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 디렉토리: dvd_lite/dvd_attacks_lpc/ml
# 파일명: train_classifier.py
# 설명: [Fix] 레이블 인코딩 추가(XGB 오류 해결) 및 상세 리포팅 강화

import os
import pandas as pd
import joblib
import json
import argparse
import sys
import time
from tqdm import tqdm
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score
from sklearn.model_selection import RandomizedSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder # LabelEncoder 추가
from sklearn.pipeline import Pipeline
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# XGBoost & LightGBM
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("[!] XGBoost not found.")

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("[!] LightGBM not found.")

# --- Path Configuration ---
ML_DIR = os.path.dirname(os.path.realpath(__file__))
OUTPUT_DIR = os.path.join(ML_DIR, 'output')
MAPPING_FILE = os.path.join(ML_DIR, 'event_mapping.json')

# --- Matplotlib 설정 ---
import matplotlib
try:
    matplotlib.use('Agg') 
except ImportError:
    pass

def load_event_mapping():
    """event_mapping.json을 로드하여 {id: name} 딕셔너리 반환"""
    try:
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            name_to_id = json.load(f)
            # {8: 'gps-spoofing', ...} 형태로 뒤집기
            id_to_name = {v: k for k, v in name_to_id.items()}
            # 0번은 보통 'Normal'
            if 0 not in id_to_name:
                id_to_name[0] = 'Normal'
            return id_to_name
    except Exception as e:
        print(f"[!] 매핑 파일 로드 실패: {e}")
        return {}

def plot_confusion_matrix(y_true, y_pred, labels, target_names, filepath, title_suffix=""):
    """Confusion Matrix 시각화 (축 이름에 공격명 표시)"""
    try:
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        # target_names 순서도 labels 순서에 맞춤
        cm_df = pd.DataFrame(cm, index=target_names, columns=target_names)

        plt.figure(figsize=(12, 10)) 
        sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', linewidths=.5, linecolor='gray')
        plt.title(f'Confusion Matrix {title_suffix}', fontsize=16)
        plt.xlabel('Predicted Label', fontsize=12)
        plt.ylabel('True Label', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close() 
        print(f"[*] Confusion Matrix 저장 완료: '{filepath}'")
    except Exception as e:
        print(f"❌ 오류: CM 저장 실패: {e}", file=sys.stderr)

def plot_feature_importance(model, feature_names, filepath, top_n=30, title_suffix=""):
    """Feature Importance 시각화"""
    if isinstance(model, Pipeline):
        est = model.steps[-1][1]
    else:
        est = model

    if not hasattr(est, 'feature_importances_'):
        return
    try:
        importances = est.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        top_n = min(top_n, len(feature_names))
        top_indices = indices[:top_n]

        plt.figure(figsize=(12, max(6, top_n * 0.35))) 
        plt.title(f'Top {top_n} Feature Importances {title_suffix}', fontsize=16)
        plt.barh(range(len(top_indices)), importances[top_indices][::-1], color='skyblue', align='center') 
        plt.yticks(range(len(top_indices)), [feature_names[i] for i in top_indices[::-1]]) 
        plt.xlabel('Relative Importance', fontsize=12)
        plt.ylabel('Feature', fontsize=12)
        plt.gca().invert_yaxis() 
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"[*] Feature Importance 저장 완료: '{filepath}'")
    except Exception as e:
        print(f"❌ 오류: FI 저장 실패: {e}", file=sys.stderr)

def get_model_pipeline(model_type='rf', num_classes=2):
    """모델 파이프라인 반환"""
    if model_type == 'rf':
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', RandomForestClassifier(class_weight='balanced', n_jobs=-1, random_state=42))
        ])
        param_dist = {
            'clf__n_estimators': [100, 200],
            'clf__max_depth': [10, 20, None],
            'clf__min_samples_split': [2, 5],
            'clf__max_features': ['sqrt']
        }
        
    elif model_type == 'xgb' and HAS_XGBOOST:
        # XGBoost는 num_class 파라미터 필요 (objective='multi:softprob')
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', XGBClassifier(
                eval_metric='mlogloss', 
                n_jobs=-1, 
                random_state=42, 
                use_label_encoder=False,
                objective='multi:softprob',
                num_class=num_classes # 클래스 개수 전달
            ))
        ])
        param_dist = {
            'clf__n_estimators': [100, 200],
            'clf__learning_rate': [0.05, 0.1],
            'clf__max_depth': [5, 7],
            'clf__subsample': [0.8],
            'clf__colsample_bytree': [0.8]
        }

    elif model_type == 'lgbm' and HAS_LIGHTGBM:
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LGBMClassifier(class_weight='balanced', n_jobs=-1, random_state=42, verbose=-1))
        ])
        param_dist = {
            'clf__n_estimators': [100, 200],
            'clf__learning_rate': [0.05, 0.1],
            'clf__num_leaves': [31, 50],
            'clf__max_depth': [-1, 10, 20]
        }
    else:
        return None, None

    return pipeline, param_dist

def main():
    parser = argparse.ArgumentParser(description="CTI Classifier Trainer v5.2 (Fixed Label Encoding)")
    parser.add_argument('--train-data', default=os.path.join(OUTPUT_DIR, 'train_dataset.csv'))
    parser.add_argument('--test-data', default=os.path.join(OUTPUT_DIR, 'test_dataset.csv'))
    parser.add_argument('--model-output', default=os.path.join(OUTPUT_DIR, 'cti_classifier_model.joblib'))
    parser.add_argument('--features-output', default=os.path.join(OUTPUT_DIR, 'training_features.json'))
    parser.add_argument('--report-output', default=os.path.join(OUTPUT_DIR, 'classification_report.json'))
    parser.add_argument('--model-type', default='auto', choices=['rf', 'xgb', 'lgbm', 'auto'])
    parser.add_argument('--n-iter', type=int, default=5)
    parser.add_argument('--cv', type=int, default=2)

    args = parser.parse_args()

    print("🚀 [Classifier Trainer v5.2] 학습 시작 (Label Encoding 적용).")

    # 1. 데이터 로드
    if not os.path.exists(args.train_data):
        print(f"❌ 훈련 데이터 없음: {args.train_data}")
        sys.exit(1)

    train_df = pd.read_csv(args.train_data)
    test_df = pd.read_csv(args.test_data)
    
    train_df = train_df.replace([np.inf, -np.inf], np.nan).fillna(0)
    test_df = test_df.replace([np.inf, -np.inf], np.nan).fillna(0)

    X_train = train_df.drop('label', axis=1)
    y_train_raw = train_df['label'] # Raw labels (0, 8, 20...)
    X_test = test_df.drop('label', axis=1)
    y_test_raw = test_df['label']

    # Feature 저장 및 컬럼 매칭
    training_features = list(X_train.columns)
    with open(args.features_output, 'w') as f:
        json.dump({'features': training_features}, f, indent=4)

    for col in training_features:
        if col not in X_test.columns:
            X_test[col] = 0
    X_test = X_test[training_features]

    # [핵심] Label Encoding 적용
    # XGBoost 등을 위해 0, 8, 20 -> 0, 1, 2 로 변환
    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(y_train_raw)
    y_test = label_encoder.transform(y_test_raw)
    
    num_classes = len(label_encoder.classes_)
    print(f"[*] Classes ({num_classes}): {label_encoder.classes_}") # [0, 8, 11...] 출력됨

    # ID -> Name 매핑 로드
    id_to_name = load_event_mapping()
    # LabelEncoder 순서대로 이름 리스트 생성
    target_names = [f"{lbl}: {id_to_name.get(lbl, 'Unknown')}" for lbl in label_encoder.classes_]

    # 2. 모델 학습 및 평가
    models_to_try = []
    if args.model_type == 'auto':
        models_to_try = ['rf']
        if HAS_XGBOOST: models_to_try.append('xgb')
        if HAS_LIGHTGBM: models_to_try.append('lgbm')
    else:
        models_to_try = [args.model_type]

    best_model = None
    best_score = -1.0
    best_name = ""

    for m_name in models_to_try:
        print(f"\n--- Training Model: {m_name.upper()} ---")
        pipeline, param_dist = get_model_pipeline(m_name, num_classes)
        
        if pipeline is None: continue

        search = RandomizedSearchCV(
            pipeline, 
            param_distributions=param_dist,
            n_iter=args.n_iter,
            cv=args.cv,
            scoring='f1_macro', 
            verbose=1, 
            random_state=42,
            n_jobs=-1
        )
        
        start_time = time.time()
        # tqdm으로 진행 표시 (search.fit이 오래 걸림)
        with tqdm(total=args.n_iter * args.cv, desc=f"Optimizing {m_name.upper()}", unit="fit") as pbar:
            search.fit(X_train, y_train)
            pbar.update(args.n_iter * args.cv)
            
        elapsed = time.time() - start_time
        
        print(f"   -> Best CV F1-Macro: {search.best_score_:.4f} (Time: {elapsed:.1f}s)")

        # 즉시 평가
        temp_model = search.best_estimator_
        y_pred = temp_model.predict(X_test)
        
        # 상세 리포트 출력 (여기서 공격명 표시!)
        print(f"\n[{m_name.upper()} Detailed Report]")
        print(classification_report(y_test, y_pred, target_names=target_names, zero_division=0))

        # 시각화 저장
        cm_path = os.path.join(OUTPUT_DIR, f'confusion_matrix_{m_name}.png')
        fi_path = os.path.join(OUTPUT_DIR, f'feature_importance_{m_name}.png')
        
        # 인코딩된 레이블(0,1,2)을 기준으로 행렬 그리되, 라벨은 실제 이름으로 표시
        plot_confusion_matrix(y_test, y_pred, range(num_classes), target_names, cm_path, title_suffix=f"({m_name.upper()})")
        plot_feature_importance(temp_model, training_features, fi_path, title_suffix=f"({m_name.upper()})")

        if search.best_score_ > best_score:
            best_score = search.best_score_
            best_model = search.best_estimator_
            best_name = m_name

    print("\n" + "="*60)
    print(f"🏆 최종 선택 모델: {best_name.upper()} (CV Score: {best_score:.4f})")
    print("="*60)

    # 3. 저장 (모델 + 인코더 함께 저장해야 나중에 복원 가능)
    # 딕셔너리 형태로 묶어서 저장
    final_artifact = {
        'model': best_model,
        'encoder': label_encoder,
        'mapping': id_to_name
    }
    joblib.dump(final_artifact, args.model_output)
    print(f"[*] Saved model artifact to: {args.model_output}")

    # 4. 최종 리포트 저장
    y_pred_final = best_model.predict(X_test)
    report_dict = classification_report(y_test, y_pred_final, target_names=target_names, zero_division=0, output_dict=True)
    with open(args.report_output, 'w') as f:
        json.dump(report_dict, f, indent=4)

    # 최종 시각화 덮어쓰기
    plot_confusion_matrix(y_test, y_pred_final, range(num_classes), target_names, args.cm_output, title_suffix="(Best Model)")
    plot_feature_importance(best_model, training_features, args.fi_output, title_suffix="(Best Model)")

if __name__ == "__main__":
    main()