#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
import joblib
import json
import argparse
import sys
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# XGBoost & LightGBM (설치되어 있어야 함: pip install xgboost lightgbm)
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("[!] XGBoost not found. Installing via pip is recommended.")

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("[!] LightGBM not found. Installing via pip is recommended.")

# --- Path Configuration ---
ML_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.dirname(ML_DIR)
OUTPUT_DIR = os.path.join(ML_DIR, 'output')

# --- Matplotlib 백엔드 설정 ---
import matplotlib
try:
    matplotlib.use('Agg') 
except ImportError:
    print("Matplotlib 'Agg' 백엔드를 설정할 수 없습니다. GUI 환경이 필요할 수 있습니다.")


def plot_confusion_matrix(y_true, y_pred, labels, filepath):
    """Confusion Matrix를 시각화하고 파일로 저장합니다."""
    try:
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        cm_df = pd.DataFrame(cm, index=labels, columns=labels)

        plt.figure(figsize=(max(10, len(labels)*0.5), max(8, len(labels)*0.4))) 
        sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', linewidths=.5, linecolor='gray')
        plt.title('Confusion Matrix', fontsize=16)
        plt.xlabel('Predicted Label', fontsize=12)
        plt.ylabel('True Label', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close() 
        print(f"[*] Confusion Matrix 그림 저장 완료: '{filepath}'")
    except Exception as e:
        print(f"❌ 오류: Confusion Matrix 생성 또는 저장 실패: {e}", file=sys.stderr)


def plot_feature_importance(model, feature_names, filepath, top_n=30):
    """Feature Importance를 시각화하고 파일로 저장합니다."""
    # Pipeline인 경우 마지막 단계(모델) 추출
    if isinstance(model, Pipeline):
        est = model.steps[-1][1]
    else:
        est = model

    if not hasattr(est, 'feature_importances_'):
        print("[!] 정보: 이 모델은 Feature Importance를 제공하지 않습니다.")
        return
    try:
        importances = est.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        top_n = min(top_n, len(feature_names))
        top_indices = indices[:top_n]

        plt.figure(figsize=(12, max(6, top_n * 0.35))) 
        plt.title(f'Top {top_n} Feature Importances', fontsize=16)
        plt.barh(range(len(top_indices)), importances[top_indices][::-1], color='skyblue', align='center') 
        plt.yticks(range(len(top_indices)), [feature_names[i] for i in top_indices[::-1]]) 
        plt.xlabel('Relative Importance', fontsize=12)
        plt.ylabel('Feature', fontsize=12)
        plt.gca().invert_yaxis() 
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"[*] Feature Importance 그림 저장 완료: '{filepath}'")
    except Exception as e:
        print(f"❌ 오류: Feature Importance 생성 또는 저장 실패: {e}", file=sys.stderr)


def get_model_pipeline(model_type='rf'):
    """모델 타입에 따른 파이프라인(Scaler + Model)과 튜닝용 파라미터 그리드 반환"""
    if model_type == 'rf':
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', RandomForestClassifier(class_weight='balanced', n_jobs=-1, random_state=42))
        ])
        # 탐색할 파라미터 공간 (더 넓고 깊게 설정)
        param_dist = {
            'clf__n_estimators': [100, 200, 300, 500],
            'clf__max_depth': [None, 10, 20, 30, 50],
            'clf__min_samples_split': [2, 5, 10],
            'clf__min_samples_leaf': [1, 2, 4],
            'clf__max_features': ['sqrt', 'log2', None]
        }
        
    elif model_type == 'xgb' and HAS_XGBOOST:
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', XGBClassifier(eval_metric='mlogloss', n_jobs=-1, random_state=42, use_label_encoder=False))
        ])
        param_dist = {
            'clf__n_estimators': [100, 200, 300],
            'clf__learning_rate': [0.01, 0.05, 0.1, 0.2],
            'clf__max_depth': [3, 5, 7, 10],
            'clf__subsample': [0.6, 0.8, 1.0],
            'clf__colsample_bytree': [0.6, 0.8, 1.0]
        }

    elif model_type == 'lgbm' and HAS_LIGHTGBM:
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LGBMClassifier(class_weight='balanced', n_jobs=-1, random_state=42))
        ])
        param_dist = {
            'clf__n_estimators': [100, 200, 300],
            'clf__learning_rate': [0.01, 0.05, 0.1],
            'clf__num_leaves': [31, 50, 100],
            'clf__max_depth': [-1, 10, 20, 30],
            'clf__subsample': [0.6, 0.8, 1.0]
        }
    else:
        return None, None

    return pipeline, param_dist


def main():
    parser = argparse.ArgumentParser(description="CTI Classifier Trainer v5.0 (AutoML Enhanced)")
    parser.add_argument('--train-data', default=os.path.join(OUTPUT_DIR, 'train_dataset.csv'), help="훈련 데이터셋 CSV 파일 경로")
    parser.add_argument('--test-data', default=os.path.join(OUTPUT_DIR, 'test_dataset.csv'), help="테스트 데이터셋 CSV 파일 경로")
    parser.add_argument('--model-output', default=os.path.join(OUTPUT_DIR, 'cti_classifier_model.joblib'), help="훈련된 모델 저장 경로")
    parser.add_argument('--features-output', default=os.path.join(OUTPUT_DIR, 'training_features.json'), help="특징 목록 저장 경로")
    parser.add_argument('--cm-output', default=os.path.join(OUTPUT_DIR, 'confusion_matrix.png'), help="CM 그림 경로")
    parser.add_argument('--fi-output', default=os.path.join(OUTPUT_DIR, 'feature_importance.png'), help="FI 그림 경로")
    parser.add_argument('--report-output', default=os.path.join(OUTPUT_DIR, 'classification_report.json'), help="리포트 저장 경로")
    parser.add_argument('--model-type', default='rf', choices=['rf', 'xgb', 'lgbm', 'auto'], help="사용할 모델 (auto: 3개 다 해보고 최적 선택)")
    parser.add_argument('--n-iter', type=int, default=20, help="RandomizedSearch 반복 횟수 (높을수록 오래 걸림)")
    parser.add_argument('--cv', type=int, default=3, help="Cross Validation 폴드 수")

    args = parser.parse_args()

    print("🚀 [Classifier Trainer v5.0] 고성능 CTI 모델 학습 및 최적화 시작.")

    # 1. 데이터 로드
    if not os.path.exists(args.train_data):
        print(f"❌ 오류: 훈련 데이터 파일을 찾을 수 없습니다: {args.train_data}")
        sys.exit(1)

    train_df = pd.read_csv(args.train_data)
    test_df = pd.read_csv(args.test_data)
    
    # NaN/Inf 처리 (Robust)
    train_df = train_df.replace([np.inf, -np.inf], np.nan).fillna(0)
    test_df = test_df.replace([np.inf, -np.inf], np.nan).fillna(0)

    print(f"[*] Data Loaded: Train={len(train_df)}, Test={len(test_df)}")

    X_train = train_df.drop('label', axis=1)
    y_train = train_df['label']
    X_test = test_df.drop('label', axis=1)
    y_test = test_df['label']

    # Feature 저장
    training_features = list(X_train.columns)
    with open(args.features_output, 'w') as f:
        json.dump({'features': training_features}, f, indent=4)

    # Test셋 컬럼 매칭
    for col in training_features:
        if col not in X_test.columns:
            X_test[col] = 0
    X_test = X_test[training_features]

    # 2. 모델 선택 및 학습 (AutoML Logic)
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
        pipeline, param_dist = get_model_pipeline(m_name)
        
        if pipeline is None:
            continue

        # RandomizedSearchCV로 최적 하이퍼파라미터 탐색
        search = RandomizedSearchCV(
            pipeline, 
            param_distributions=param_dist,
            n_iter=args.n_iter,
            cv=args.cv,
            scoring='f1_macro', # 소수 클래스 중요하므로 macro F1 사용
            verbose=1,
            random_state=42,
            n_jobs=-1
        )
        
        start_time = time.time()
        search.fit(X_train, y_train)
        elapsed = time.time() - start_time
        
        print(f"   -> Best Params: {search.best_params_}")
        print(f"   -> Best CV F1-Macro: {search.best_score_:.4f} (Time: {elapsed:.1f}s)")

        if search.best_score_ > best_score:
            best_score = search.best_score_
            best_model = search.best_estimator_
            best_name = m_name

    print("\n" + "="*60)
    print(f"🏆 최종 선택 모델: {best_name.upper()} (CV Score: {best_score:.4f})")
    print("="*60)

    # 3. 최종 모델 저장
    joblib.dump(best_model, args.model_output)
    print(f"[*] Saved model to: {args.model_output}")

    # 4. 최종 평가
    y_pred = best_model.predict(X_test)
    class_labels = sorted(list(np.unique(np.concatenate((y_train, y_test)))))

    print("\n📊 [Final Evaluation on Test Set]")
    print(f"Accuracy : {accuracy_score(y_test, y_pred):.4f}")
    print(f"F1 (Macro): {f1_score(y_test, y_pred, average='macro', zero_division=0):.4f}")
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, labels=class_labels, zero_division=0))

    # 결과 저장
    report_dict = classification_report(y_test, y_pred, labels=class_labels, zero_division=0, output_dict=True)
    with open(args.report_output, 'w') as f:
        json.dump(report_dict, f, indent=4)

    # 시각화
    plot_confusion_matrix(y_test, y_pred, class_labels, args.cm_output)
    
    # Feature Importance (Pipeline인 경우 처리)
    final_estimator = best_model.named_steps['clf']
    plot_feature_importance(final_estimator, training_features, args.fi_output)

if __name__ == "__main__":
    main()