#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
import joblib
import json
import argparse
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import matplotlib.pyplot as plt
import seaborn as sns

# --- 경로 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'ml', 'output')

def main():
    parser = argparse.ArgumentParser(description="CTI 분류기 학습기 v4.0 (다중 클래스)")
    parser.add_argument('--train-data', default=os.path.join(OUTPUT_DIR, 'train_dataset.csv'), help="훈련 데이터셋 CSV 파일 경로")
    parser.add_argument('--test-data', default=os.path.join(OUTPUT_DIR, 'test_dataset.csv'), help="테스트 데이터셋 CSV 파일 경로")
    args = parser.parse_args()
    
    print("🚀 [Classifier Trainer v4.0] CTI 모델 학습을 시작합니다.")

    # 1. 데이터 로드
    try:
        train_df = pd.read_csv(args.train_data)
        test_df = pd.read_csv(args.test_data)
    except FileNotFoundError as e:
        print(f"❌ 오류: 데이터 파일을 찾을 수 없습니다. '{e.filename}'")
        print("    먼저 data_builder.py와 dataset_manager.py를 실행했는지 확인하세요.")
        sys.exit(1)

    X_train = train_df.drop('label', axis=1)
    y_train = train_df['label']
    X_test = test_df.drop('label', axis=1)
    y_test = test_df['label']

    # ⭐️ 중요: 학습에 사용된 피처 이름 저장
    training_features = list(X_train.columns)
    features_path = os.path.join(OUTPUT_DIR, 'training_features.json')
    with open(features_path, 'w') as f:
        json.dump({'features': training_features}, f, indent=4)
    print(f"[*] 모델 학습에 사용될 {len(training_features)}개의 피처 이름을 '{features_path}'에 저장했습니다.")

    # 2. 모델 학습
    print("[*] RandomForestClassifier 모델 학습 중...")
    # class_weight='balanced' 옵션으로 데이터 불균형 처리
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced', n_jobs=-1)
    model.fit(X_train, y_train)
    print("✅ 모델 학습 완료.")

    # 3. 모델 저장
    model_path = os.path.join(OUTPUT_DIR, 'cti_classifier_model.joblib')
    joblib.dump(model, model_path)
    print(f"[*] 학습된 모델을 '{model_path}'에 저장했습니다.")
    
    # 4. 모델 성능 평가
    print("\n" + "="*60)
    print("📊 모델 성능 평가 (테스트 세트 기준)")
    print("="*60)
    y_pred = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n- 전체 정확도 (Accuracy): {accuracy:.4f}\n")
    
    print("- 분류 리포트 (Classification Report):")
    # zero_division=0: 특정 클래스 예측이 없어 0으로 나누는 경우 경고 대신 0으로 처리
    print(classification_report(y_test, y_pred, zero_division=0))

    # 5. 혼동 행렬 (Confusion Matrix) 시각화
    print("- 혼동 행렬 (Confusion Matrix):")
    cm = confusion_matrix(y_test, y_pred, labels=model.classes_)
    print(pd.DataFrame(cm, index=model.classes_, columns=model.classes_))
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=model.classes_, yticklabels=model.classes_)
    plt.title('Confusion Matrix')
    plt.xlabel('Predicted Label')
    plt.ylabel('True Label')
    
    cm_path = os.path.join(OUTPUT_DIR, 'confusion_matrix.png')
    plt.savefig(cm_path)
    print(f"\n[*] 혼동 행렬 그래프를 '{cm_path}'에 저장했습니다.")
    print("="*60)

if __name__ == "__main__":
    main()