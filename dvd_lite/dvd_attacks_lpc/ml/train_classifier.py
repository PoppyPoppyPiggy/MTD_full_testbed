#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import sys

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# --- Path Configuration ---
ML_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.dirname(ML_DIR)
OUTPUT_DIR = os.path.join(ML_DIR, "output")

# --- Matplotlib 백엔드 설정 (GUI 없을 때 오류 방지) ---
try:
    matplotlib.use("Agg")  # 'Agg' 백엔드 사용
except ImportError:
    print(
        "Matplotlib 'Agg' 백엔드를 설정할 수 없습니다. GUI 환경이 필요할 수 있습니다."
    )

# Ensure output directory exists for all artifacts
os.makedirs(OUTPUT_DIR, exist_ok=True)


def plot_confusion_matrix(y_true, y_pred, labels, filepath):
    """Confusion Matrix를 시각화하고 파일로 저장합니다."""
    try:
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        cm_df = pd.DataFrame(cm, index=labels, columns=labels)

        plt.figure(figsize=(max(10, len(labels)*0.5), max(8, len(labels)*0.4))) # 클래스 수에 따라 크기 조절
        sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', linewidths=.5, linecolor='gray')
        plt.title('Confusion Matrix', fontsize=16)
        plt.xlabel('Predicted Label', fontsize=12)
        plt.ylabel('True Label', fontsize=12)
        plt.xticks(rotation=45, ha='right') # 레이블 길면 회전
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(filepath, dpi=150) # 해상도 조절
        plt.close() # 메모리 해제
        print(f"[*] Confusion Matrix 그림 저장 완료: '{filepath}'")
    except Exception as e:
        print(f"❌ 오류: Confusion Matrix 생성 또는 저장 실패: {e}", file=sys.stderr)


def plot_feature_importance(model, feature_names, filepath, top_n=30):
    """Feature Importance를 시각화하고 파일로 저장합니다."""
    if not hasattr(model, 'feature_importances_'):
        print("[!] 정보: 이 모델은 Feature Importance를 제공하지 않습니다 (예: SVM).")
        return
    try:
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1] # 중요도 순으로 정렬
        
        # [수정] top_n이 실제 피처 수보다 많으면 피처 수로 제한
        top_n = min(top_n, len(feature_names))
        top_indices = indices[:top_n]

        plt.figure(figsize=(12, max(6, top_n * 0.35))) # 특징 수에 따라 높이 조절
        plt.title(f'Top {top_n} Feature Importances', fontsize=16)
        plt.barh(range(len(top_indices)), importances[top_indices][::-1], color='skyblue', align='center') # 역순으로 플롯
        plt.yticks(range(len(top_indices)), [feature_names[i] for i in top_indices[::-1]]) # 역순으로 레이블
        plt.xlabel('Relative Importance', fontsize=12)
        plt.ylabel('Feature', fontsize=12)
        plt.gca().invert_yaxis() # 중요도 높은 것이 위로 오도록
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"[*] Feature Importance 그림 저장 완료: '{filepath}'")
    except Exception as e:
        print(f"❌ 오류: Feature Importance 생성 또는 저장 실패: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="CTI Classifier Trainer v4.1 (Evaluation Enhanced)")
    parser.add_argument('--train-data', default=os.path.join(OUTPUT_DIR, 'train_dataset.csv'), help="훈련 데이터셋 CSV 파일 경로")
    parser.add_argument('--test-data', default=os.path.join(OUTPUT_DIR, 'test_dataset.csv'), help="테스트 데이터셋 CSV 파일 경로")
    parser.add_argument('--model-output', default=os.path.join(OUTPUT_DIR, 'cti_classifier_model.joblib'), help="훈련된 모델 저장 경로 (.joblib)")
    parser.add_argument('--features-output', default=os.path.join(OUTPUT_DIR, 'training_features.json'), help="훈련에 사용된 특징 목록 저장 경로 (.json)")
    parser.add_argument('--cm-output', default=os.path.join(OUTPUT_DIR, 'confusion_matrix.png'), help="Confusion Matrix 그림 파일 경로")
    parser.add_argument('--fi-output', default=os.path.join(OUTPUT_DIR, 'feature_importance.png'), help="Feature Importance 그림 파일 경로")
    parser.add_argument('--report-output', default=os.path.join(OUTPUT_DIR, 'classification_report.json'), help="Classification Report 저장 경로 (.json)")

    args = parser.parse_args()

    print("🚀 [Classifier Trainer v4.1] CTI 모델 훈련 및 평가 시작.")

    # 1. 데이터 로드
    try:
        train_df = pd.read_csv(args.train_data)
        test_df = pd.read_csv(args.test_data)
        print(f"[*] 훈련 데이터 로드 완료: {len(train_df)} 샘플")
        print(f"[*] 테스트 데이터 로드 완료: {len(test_df)} 샘플")
    except FileNotFoundError as e:
        print(f"❌ 오류: 데이터 파일을 찾을 수 없습니다. '{e.filename}'")
        print("      먼저 data_builder.py와 dataset_manager.py를 실행해야 합니다.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 오류: 데이터 로드 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # NaN/inf 값 처리 (안정성)
    train_df = train_df.replace([np.inf, -np.inf], np.nan).fillna(0)
    test_df = test_df.replace([np.inf, -np.inf], np.nan).fillna(0)


    X_train = train_df.drop('label', axis=1)
    y_train = train_df['label']
    X_test = test_df.drop('label', axis=1)
    y_test = test_df['label']

    # 훈련 데이터 컬럼 순서 저장 (매우 중요!)
    training_features = list(X_train.columns)
    try:
        with open(args.features_output, 'w') as f:
            json.dump({'features': training_features}, f, indent=4)
        print(f"[*] {len(training_features)}개 특징 이름 저장 완료: '{args.features_output}'")
    except Exception as e:
        print(f"❌ 오류: 특징 목록 저장 실패 ({args.features_output}): {e}", file=sys.stderr)
        sys.exit(1)

    # 훈련/테스트 데이터 컬럼 일치 확인 및 조정 (더욱 안정적으로)
    missing_cols_test = set(training_features) - set(X_test.columns)
    extra_cols_test = set(X_test.columns) - set(training_features)

    if missing_cols_test:
        print(f"[!] 경고: 테스트 데이터에 훈련 시 사용된 특징 일부가 없습니다: {missing_cols_test}. 0으로 채웁니다.")
        for c in missing_cols_test:
            X_test[c] = 0
    if extra_cols_test:
        print(f"[!] 경고: 테스트 데이터에 훈련 시 사용되지 않은 특징이 있습니다: {extra_cols_test}. 제거합니다.")
        X_test = X_test.drop(columns=list(extra_cols_test))

    # 최종적으로 훈련 데이터의 컬럼 순서와 동일하게 맞춤
    X_test = X_test[training_features]


    # 2. 모델 훈련 (Random Forest 사용)
    print("[*] RandomForestClassifier 모델 훈련 중...")
    try:
        # n_jobs=-1 : 모든 CPU 코어 사용, class_weight='balanced' : 클래스 불균형 처리
        model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced', n_jobs=-1, max_depth=20, min_samples_split=5) # 하이퍼파라미터 예시 추가
        model.fit(X_train, y_train)
        print("✅ 모델 훈련 완료.")
    except Exception as e:
        print(f"❌ 오류: 모델 훈련 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. 모델 저장
    try:
        joblib.dump(model, args.model_output)
        print(f"[*] 훈련된 모델 저장 완료: '{args.model_output}'.")
    except Exception as e:
        print(f"❌ 오류: 모델 저장 실패 ({args.model_output}): {e}", file=sys.stderr)
        sys.exit(1)

    # 4. 모델 평가 (테스트셋 사용)
    print("\n" + "="*60)
    print("📊 모델 성능 평가 (테스트셋)")
    print("="*60)
    try:
        y_pred = model.predict(X_test)
        
        # [수정] y_train과 y_test에 있는 모든 레이블을 포함
        class_labels = sorted(list(np.unique(np.concatenate((y_train, y_test)))))

        accuracy = accuracy_score(y_test, y_pred)
        f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
        precision_macro = precision_score(y_test, y_pred, average='macro', zero_division=0)
        recall_macro = recall_score(y_test, y_pred, average='macro', zero_division=0)

        print(f"\n- 전체 정확도 (Accuracy) : {accuracy:.4f}")
        print(f"- Macro F1-Score         : {f1_macro:.4f}")
        print(f"- Macro Precision        : {precision_macro:.4f}")
        print(f"- Macro Recall           : {recall_macro:.4f}\n")

        print("- 상세 분류 리포트:")
        report_str = classification_report(y_test, y_pred, labels=class_labels, zero_division=0)
        print(report_str)

        # Classification Report를 JSON 파일로 저장
        try:
              report_dict = classification_report(y_test, y_pred, labels=class_labels, zero_division=0, output_dict=True)
              with open(args.report_output, 'w') as f:
                  json.dump(report_dict, f, indent=4)
              print(f"[*] Classification Report 저장 완료: '{args.report_output}'")
        except Exception as report_save_err:
              print(f"❌ 오류: Classification Report 저장 실패 ({args.report_output}): {report_save_err}", file=sys.stderr)

    except Exception as e:
        print(f"❌ 오류: 모델 평가 중 오류 발생: {e}", file=sys.stderr)
        # 평가 실패해도 시각화 시도
        y_pred = None # 예측 실패 표시
        class_labels = sorted(list(y_train.unique()))


    # 5. Confusion Matrix 시각화 및 저장
    if y_pred is not None:
          plot_confusion_matrix(y_test, y_pred, class_labels, args.cm_output)
    else:
          print("[!] 정보: 예측 실패로 Confusion Matrix를 생성할 수 없습니다.")

    # 6. Feature Importance 시각화 및 저장
    plot_feature_importance(model, training_features, args.fi_output)

    print("="*60)

if __name__ == "__main__":
    main()
