#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CTI Dataset Manager v4.2 (Stable)
----------------------------------
* 자동으로 ``processed_data`` 하위의 최신 ``features_batch_*.csv``를 찾음
* 계층적(train/test) 분할 후 ``ml/output``에 저장
"""

import os
import sys
import argparse
import pathlib
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# --- Path Configuration ---
ML_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.dirname(ML_DIR)

PROCESSED_DATA_DIR = os.path.join(ML_DIR, "processed_data")
OUTPUT_DIR = os.path.join(ML_DIR, "output")


class DatasetManager:
    """data_builder.py가 import 해서 쓰는 간단 저장기"""
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        if not isinstance(df, pd.DataFrame):
            print("❌ [DatasetManager Error] df가 DataFrame이 아닙니다.", file=sys.stderr)
            return
        try:
            path = os.path.join(self.output_dir, filename)
            df.to_csv(path, index=False)
        except Exception as e:
            print(f"❌ [DatasetManager Error] 저장 실패({filename}): {e}", file=sys.stderr)


def find_latest_features_file(directory: str) -> Optional[str]:
    """processed_data에서 최신 features_batch_*.csv 찾기"""
    try:
        d = pathlib.Path(directory)
        if not d.is_dir():
            print(f"❌ [오류] 디렉토리 없음: {directory}", file=sys.stderr)
            return None
        files = sorted(
            (f for f in d.glob("features_batch_*.csv") if f.is_file()),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not files:
            print(f"❌ [오류] '{directory}'에 features_batch_*.csv 없음", file=sys.stderr)
            return None
        print(f"[*] 최신 특징 데이터 파일 발견: {files[0].name}")
        return str(files[0])
    except Exception as e:
        print(f"❌ [오류] 최신 파일 검색 실패: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="CTI Dataset Manager v4.2")
    parser.add_argument("--input", default=None, help="입력 CSV 경로(미지정 시 processed_data 최신 파일 자동 사용)")
    parser.add_argument("--test-size", type=float, default=0.2, help="테스트셋 비율 (0~1)")
    parser.add_argument("--random-state", type=int, default=42, help="재현을 위한 시드")
    args = parser.parse_args()

    print("🚀 [Dataset Manager v4.2] 데이터셋 분할 시작.")

    input_path = args.input
    if input_path is None:
        print(f"[*] --input 미지정. '{PROCESSED_DATA_DIR}'에서 최신 파일 검색...")
        input_path = find_latest_features_file(PROCESSED_DATA_DIR)

    if input_path is None or not os.path.exists(input_path):
        if input_path:
            print(f"❌ 오류: 입력 파일 없음: {input_path}")
        print("    먼저 data_builder.py로 특징 데이터셋을 생성하세요.")
        sys.exit(1)

    # 1) 로드
    try:
        df = pd.read_csv(input_path)
        print(f"[*] 원본 데이터셋 로드 완료: {df.shape[0]} 샘플, {df.shape[1]} 특징")
    except Exception as e:
        print(f"❌ 오류: 로드 실패 ({input_path}): {e}", file=sys.stderr)
        sys.exit(1)

    # 2) 라벨 확인
    if "label" not in df.columns:
        print("❌ 오류: 'label' 컬럼이 없습니다. data_builder 설정을 확인하세요.")
        sys.exit(1)

    # 3) 무한대/NaN 정리
    if np.isinf(df.select_dtypes(include=np.number).values).any():
        print("[!] 경고: 무한대 값 존재 → NaN으로 전환")
        df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # 4) 불리언/카테고리 정리
    bool_cols = df.select_dtypes(include=["bool"]).columns.tolist()
    if bool_cols:
        df[bool_cols] = df[bool_cols].astype("int64")

    # 5) NaN 일괄 처리(라벨 제외 전체)
    nan_cols = df.columns[df.isnull().any()].tolist()
    if nan_cols:
        print(f"[!] 경고: NaN 포함 컬럼: {nan_cols} → 0으로 대체")
        df.fillna(0, inplace=True)

    # 6) X/y 분리
    y = df["label"].astype("int64")
    # 숫자형만 선택해서 X 구성
    X = df.drop(columns=["label"], errors="ignore").select_dtypes(include=[np.number])

    if X.empty:
        print("❌ 오류: 숫자형 학습 피처가 없습니다. one-hot/전처리 파이프를 확인하세요.")
        sys.exit(1)

    print(f"[*] 최종 학습 피처 수(숫자형만): {X.shape[1]}")

    # 7) 레이블 유효성
    unique_labels = sorted(y.unique().tolist())
    if len(unique_labels) < 2:
        print(f"❌ 오류: 고유 레이블이 1개({unique_labels})뿐입니다. stratify 분할 불가.")
        print("    정상(0) + 최소 하나 이상 공격 라벨 필요.")
        print("\n현재 레이블 분포:\n", y.value_counts())
        sys.exit(1)
    else:
        print(f"[*] 고유 레이블 {len(unique_labels)}종: {unique_labels}")
        print("\n[*] 전체 레이블 분포(분할 전):")
        print(y.value_counts(normalize=True).sort_index().apply(lambda x: f"{x:.4%}"))

    # 8) 분할(계층적)
    print(f"[*] 분할 진행: train {(1-args.test_size):.0%} / test {args.test_size:.0%}")
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=args.test_size,
            random_state=args.random_state,
            stratify=y
        )
    except ValueError as e:
        if "The least populated class" in str(e):
            print(f"❌ 오류: 계층분할 실패(소수 클래스 샘플 부족): {e}")
            cnt = y.value_counts()
            print("\n현재 레이블 분포:\n", cnt)
            print(f"\n테스트 비율 {args.test_size*100:.1f}%면 각 클래스 최소 {int(np.floor(1/args.test_size))}개 이상 필요")
        else:
            print(f"❌ 오류: 데이터 분할 중 예외: {e}", file=sys.stderr)
        sys.exit(1)

    # 9) 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    train_path = os.path.join(OUTPUT_DIR, "train_dataset.csv")
    test_path  = os.path.join(OUTPUT_DIR, "test_dataset.csv")
    try:
        pd.concat([X_train, y_train], axis=1).to_csv(train_path, index=False)
        pd.concat([X_test,  y_test ], axis=1).to_csv(test_path,  index=False)
    except Exception as e:
        print(f"❌ 오류: 저장 실패: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "="*60)
    print("✅ 데이터셋 분할 및 저장 완료!")
    print(f"  - 훈련: {train_path} ({len(X_train)} 샘플)")
    print(f"  - 테스트: {test_path} ({len(X_test)} 샘플)")
    print("\n[훈련 레이블 분포]")
    print(y_train.value_counts(normalize=True).sort_index().apply(lambda x: f"{x:.4%}"))
    print("\n[테스트 레이블 분포]")
    print(y_test.value_counts(normalize=True).sort_index().apply(lambda x: f"{x:.4%}"))
    print("="*60)


if __name__ == "__main__":
    main()
