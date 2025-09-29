#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
from sklearn.model_selection import train_test_split
import argparse
import sys

# --- 경로 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'ml', 'output')

def main():
    parser = argparse.ArgumentParser(description="CTI 데이터셋 관리자 v4.0")
    parser.add_argument('--input', default=os.path.join(OUTPUT_DIR, 'cti_features_dataset.csv'), help="입력 데이터셋 CSV 파일 경로")
    parser.add_argument('--test-size', type=float, default=0.2, help="테스트 세트의 비율 (0.0 ~ 1.0)")
    parser.add_argument('--random-state', type=int, default=42, help="결과 재현을 위한 랜덤 시드")
    args = parser.parse_args()

    print("🚀 [Dataset Manager v4.0] 데이터셋 분할을 시작합니다.")
    
    if not os.path.exists(args.input):
        print(f"❌ 오류: 입력 파일 '{args.input}'을 찾을 수 없습니다.")
        sys.exit(1)
        
    # 1. 데이터셋 로드
    df = pd.read_csv(args.input)
    print(f"[*] 원본 데이터셋 로드 완료: {df.shape[0]} 샘플, {df.shape[1]} 특징")

    X = df.drop('label', axis=1)
    y = df['label']
    
    # 레이블 클래스가 2개 미만이면 계층적 분할 불가
    if y.nunique() < 2:
        print("❌ 오류: 레이블에 클래스가 하나뿐입니다. 계층적 분할을 수행할 수 없습니다.")
        print("    데이터에 'normal' 외에 최소 하나 이상의 공격 레이블이 포함되어야 합니다.")
        sys.exit(1)

    # 2. 훈련/테스트 데이터 분할 (계층적 샘플링)
    print(f"[*] 데이터를 훈련 세트({1-args.test_size:.0%})와 테스트 세트({args.test_size:.0%})로 분할합니다.")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=args.test_size, 
        random_state=args.random_state,
        stratify=y  # ⭐️ 중요: 레이블 분포를 유지하며 분할
    )

    # 3. 분할된 데이터 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    train_path = os.path.join(OUTPUT_DIR, 'train_dataset.csv')
    test_path = os.path.join(OUTPUT_DIR, 'test_dataset.csv')
    
    pd.concat([X_train, y_train], axis=1).to_csv(train_path, index=False)
    pd.concat([X_test, y_test], axis=1).to_csv(test_path, index=False)

    print("\n" + "="*60)
    print("✅ 데이터셋 분할 및 저장을 완료했습니다!")
    print(f"  - 훈련 데이터: {train_path} ({len(X_train)} 샘플)")
    print(f"  - 테스트 데이터: {test_path} ({len(X_test)} 샘플)")
    print("\n[훈련 세트 레이블 분포]")
    print(y_train.value_counts(normalize=True))
    print("\n[테스트 세트 레이블 분포]")
    print(y_test.value_counts(normalize=True))
    print("="*60)

if __name__ == "__main__":
    main()