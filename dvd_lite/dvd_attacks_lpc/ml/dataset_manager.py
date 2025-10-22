#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
from sklearn.model_selection import train_test_split
import argparse
import sys
import numpy as np # numpy 임포트 추가

# --- Path Configuration ---
ML_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.dirname(ML_DIR)
OUTPUT_DIR = os.path.join(ML_DIR, 'output')

def main():
    parser = argparse.ArgumentParser(description="CTI Dataset Manager v4.1 (Stability Improved)")
    parser.add_argument('--input', default=os.path.join(OUTPUT_DIR, 'cti_features_dataset.csv'), help="입력 데이터셋 CSV 파일 경로")
    parser.add_argument('--test-size', type=float, default=0.2, help="테스트셋 비율 (0.0 ~ 1.0)")
    parser.add_argument('--random-state', type=int, default=42, help="결과 재현을 위한 랜덤 시드")
    args = parser.parse_args()

    print("🚀 [Dataset Manager v4.1] 데이터셋 분할 시작.")

    if not os.path.exists(args.input):
        print(f"❌ 오류: 입력 파일 '{args.input}'을(를) 찾을 수 없습니다.")
        print("       먼저 data_builder.py를 실행하여 특징 데이터셋을 생성해야 합니다.")
        sys.exit(1)

    # 1. 데이터셋 로드
    try:
        df = pd.read_csv(args.input)
        print(f"[*] 원본 데이터셋 로드 완료: {df.shape[0]} 샘플, {df.shape[1]} 특징")
    except Exception as e:
        print(f"❌ 오류: 데이터셋 로드 실패 ({args.input}): {e}", file=sys.stderr)
        sys.exit(1)

    # 무한대 값 확인 및 처리 (RandomForest 등 일부 모델은 무한대 값 처리 못함)
    if np.isinf(df.drop('label', axis=1, errors='ignore')).any().any():
         print("[!] 경고: 데이터셋에 무한대(inf) 값이 포함되어 있습니다. 최대/최소값으로 대체합니다.")
         df = df.replace([np.inf, -np.inf], np.nan) # inf를 NaN으로 변경
         # 각 컬럼의 최대/최소값으로 NaN 채우기 (또는 0으로 채우기)
         # 여기서는 간단히 0으로 채움 (fillna(0)으로 대체 가능)
         print("    (무한대 값을 0으로 대체함)")


    # NaN 값 확인 및 0으로 채우기 (안정성 강화)
    if df.isnull().any().any():
         nan_cols = df.columns[df.isnull().any()].tolist()
         print(f"[!] 경고: 데이터셋에 NaN 값이 포함되어 있습니다 (컬럼: {nan_cols}). 0으로 대체합니다.")
         df = df.fillna(0)


    # 특징(X)과 레이블(y) 분리
    if 'label' not in df.columns:
         print("❌ 오류: 데이터셋에 'label' 컬럼이 없습니다.")
         sys.exit(1)

    X = df.drop('label', axis=1)
    y = df['label']

    # 레이블 종류 확인 (최소 2개 클래스 필요)
    unique_labels = y.unique()
    if len(unique_labels) < 2:
        print(f"❌ 오류: 데이터셋에 고유 레이블이 하나({unique_labels[0]})만 존재합니다. 계층적 분할(stratify)을 수행할 수 없습니다.")
        print("       정상 데이터와 최소 하나 이상의 공격 데이터가 포함되어야 합니다.")
        sys.exit(1)
    else:
        print(f"[*] 발견된 고유 레이블 ({len(unique_labels)}개): {', '.join(map(str, unique_labels))}")

    # 모든 특징이 숫자인지 확인 및 변환 (오류 발생 시 0으로 대체)
    try:
        X = X.apply(pd.to_numeric, errors='coerce').fillna(0)
    except Exception as e:
         print(f"❌ 오류: 특징 데이터를 숫자로 변환하는 중 오류 발생: {e}", file=sys.stderr)
         print("     data_builder.py 실행 결과를 확인해주세요.")
         sys.exit(1)


    # 2. 훈련/테스트 데이터 분할 (계층적 샘플링)
    print(f"[*] 데이터를 훈련셋({1-args.test_size:.0%})과 테스트셋({args.test_size:.0%})으로 분할 중...")
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=args.test_size,
            random_state=args.random_state,
            stratify=y # 중요: 클래스 비율을 유지하며 분할 (불균형 데이터 처리)
        )
    except ValueError as e:
         if "The least populated class" in str(e):
             print(f"❌ 오류: 계층적 분할 실패. 특정 클래스의 샘플 수가 너무 적습니다 (오류: {e}).")
             print("     데이터를 더 많이 수집하거나 test_size를 조정해야 할 수 있습니다.")
             label_counts = y.value_counts()
             print("\n현재 레이블 분포:\n", label_counts)
             minority_class = label_counts.idxmin()
             minority_count = label_counts.min()
             print(f"\n가장 적은 클래스 '{minority_class}'의 샘플 수: {minority_count}")
             print(f"테스트셋 크기({args.test_size*100:.1f}%)를 유지하려면 최소 {int(np.ceil(1/args.test_size))}개 이상의 샘플이 필요합니다.")
             # 비 계층적 분할 옵션 제공 (선택 사항)
             # print("\n계층화 없이 분할을 시도하려면 stratify=None 옵션을 사용하세요 (권장되지 않음).")
         else:
             print(f"❌ 오류: 데이터 분할 중 예상치 못한 오류 발생: {e}", file=sys.stderr)
         sys.exit(1)


    # 3. 분할된 데이터 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    train_path = os.path.join(OUTPUT_DIR, 'train_dataset.csv')
    test_path = os.path.join(OUTPUT_DIR, 'test_dataset.csv')

    try:
        pd.concat([X_train, y_train], axis=1).to_csv(train_path, index=False)
        pd.concat([X_test, y_test], axis=1).to_csv(test_path, index=False)
    except Exception as e:
        print(f"❌ 오류: 분할된 데이터 저장 실패: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "="*60)
    print("✅ 데이터셋 분할 및 저장 완료!")
    print(f"  - 훈련 데이터: {train_path} ({len(X_train)} 샘플)")
    print(f"  - 테스트 데이터: {test_path} ({len(X_test)} 샘플)")
    print("\n[훈련셋 레이블 분포]")
    print(y_train.value_counts(normalize=True).apply(lambda x: f'{x:.2%}'))
    print("\n[테스트셋 레이블 분포]")
    print(y_test.value_counts(normalize=True).apply(lambda x: f'{x:.2%}'))
    print("="*60)

if __name__ == "__main__":
    main()
