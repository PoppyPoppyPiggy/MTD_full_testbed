#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset Manager v4.3
- CTI Feature CSV (features_batch_*.csv) -> train/test 분할
- 경로 인자(--processed-dir) 추가로 DataBuilder와의 경로 불일치 해결
"""

import argparse
import glob
import logging
import math
import os
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


def find_latest_features_csv(processed_dir: str) -> Optional[str]:
    """지정된 경로에서 가장 최신 CSV 파일을 찾습니다."""
    pattern = os.path.join(processed_dir, "features_batch_*.csv")
    candidates = glob.glob(pattern)
    if not candidates:
        return None
    # 수정 시간 기준 정렬하여 가장 최근 파일 반환
    candidates.sort(key=os.path.getmtime)
    return candidates[-1]


def load_dataset(input_path: str) -> pd.DataFrame:
    log.info("[*] 원본 데이터셋 로드: %s", input_path)
    df = pd.read_csv(input_path)
    log.info("[*] 로드 완료: %d 샘플, %d 컬럼", len(df), len(df.columns))
    return df


def describe_labels(df: pd.DataFrame, label_col: str = "label"):
    if label_col not in df.columns:
        raise ValueError(f"'{label_col}' 컬럼이 데이터셋에 없습니다.")

    counts = df[label_col].value_counts().sort_index()
    total = counts.sum()

    log.info("[*] 고유 레이블 %d종: %s", len(counts.index), list(counts.index))
    log.info("[*] 전체 레이블 분포(분할 전):")
    for lbl, cnt in counts.items():
        pct = cnt / total * 100.0
        log.info("  - label %s: %d (%.4f%%)", lbl, cnt, pct)

    return counts


def filter_rare_classes(
    df: pd.DataFrame,
    label_col: str,
    min_samples_per_class: int
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    min_samples_per_class 미만인 레이블은 rare로 보고 제거합니다.
    """
    counts = df[label_col].value_counts()
    rare_labels = counts[counts < min_samples_per_class].index.tolist()

    if rare_labels:
        log.warning(
            "⚠ 희소(rare) 클래스 감지: %s (각 count < %d)",
            rare_labels, min_samples_per_class
        )
        log.warning(
            "  -> 현재 버전에서는 이 레이블 샘플은 train/test 분할에서 제외합니다."
        )
        df_filtered = df[~df[label_col].isin(rare_labels)].copy()
    else:
        df_filtered = df.copy()

    return df_filtered, counts


def split_dataset(
    df: pd.DataFrame,
    label_col: str,
    test_size: float,
    random_state: int
):
    """
    우선 stratify=y로 시도해보고,
    실패(ValueError - 클래스 샘플 부족 등)하면 stratify=None으로 fallback.
    """

    # 숫자형 특징만 선별 (label 제외)
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if label_col in num_cols:
        num_cols.remove(label_col)

    if not num_cols:
        raise RuntimeError("숫자형 특징 컬럼이 없습니다. data_builder 단계를 확인하세요.")

    X = df[num_cols].values
    y = df[label_col].values

    log.info("[*] 최종 학습 피처 수(숫자형만): %d", len(num_cols))
    log.info("[*] train/test 분할 (test_size=%.2f, stratify=y) 시도...", test_size)

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=y,
        )
        log.info("✅ 계층분할(stratify=y) 성공.")
    except ValueError as e:
        log.error("❌ 계층분할 실패: %s", e)
        log.warning("  -> stratify 없이 단순 분할로 fallback 합니다.")
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=None,
        )
        log.info("✅ fallback 분할(stratify=None) 성공.")

    return X_train, X_test, y_train, y_test, num_cols


def save_splits(
    X_train, X_test, y_train, y_test,
    feature_names,
    output_dir: str
):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 고정된 파일명 (Trainer가 쉽게 찾기 위함)
    train_path = os.path.join(output_dir, "train_dataset.csv")
    test_path = os.path.join(output_dir, "test_dataset.csv")
    
    # 백업용 파일명
    train_backup = os.path.join(output_dir, f"train_dataset_{ts}.csv")
    test_backup = os.path.join(output_dir, f"test_dataset_{ts}.csv")

    df_train = pd.DataFrame(X_train, columns=feature_names)
    df_train["label"] = y_train

    df_test = pd.DataFrame(X_test, columns=feature_names)
    df_test["label"] = y_test

    # 메인 저장
    df_train.to_csv(train_path, index=False)
    df_test.to_csv(test_path, index=False)
    
    # 백업 저장
    df_train.to_csv(train_backup, index=False)
    df_test.to_csv(test_backup, index=False)

    log.info("✅ train 데이터셋 저장: %s (rows=%d)", train_path, len(df_train))
    log.info("✅ test  데이터셋 저장: %s (rows=%d)", test_path, len(df_test))


def main():
    parser = argparse.ArgumentParser(
        description="CTI Dataset Manager v4.3 - train/test 분할 스크립트"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="입력 CSV. 미지정 시 processed-dir에서 최신 파일 자동 검색"
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="./processed_data",
        help="features_batch_*.csv가 저장된 디렉터리"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="train/test CSV를 저장할 디렉터리"
    )
    parser.add_argument(
        "--label-col",
        type=str,
        default="label",
        help="레이블 컬럼명 (기본: label)"
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="테스트 데이터 비율 (기본: 0.2)"
    )
    parser.add_argument(
        "--min-samples-per-class",
        type=int,
        default=2,
        help="이 값 미만인 클래스는 rare로 보고 분할에서 제외"
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="train/test 분할용 랜덤 시드"
    )

    args = parser.parse_args()

    log.info("🚀 [Dataset Manager v4.3] 데이터셋 분할 시작.")
    
    # 절대 경로 변환
    proc_dir = os.path.abspath(args.processed_dir)
    out_dir = os.path.abspath(args.output_dir)

    # 1) 입력 파일 결정
    if args.input is None:
        inp = find_latest_features_csv(proc_dir)
        if inp is None:
            log.critical("❌ processed_dir(%s)에 features_batch_*.csv가 없습니다.", proc_dir)
            raise SystemExit(1)
        log.info("[*] --input 미지정. '%s'에서 최신 파일 검색 -> %s", proc_dir, inp)
        input_path = inp
    else:
        input_path = args.input

    # 2) 데이터 로드 및 레이블 분포 출력
    df_raw = load_dataset(input_path)
    counts = describe_labels(df_raw, label_col=args.label_col)

    # 3) 희소 클래스 필터링
    if args.min_samples_per_class > 1:
        df, _ = filter_rare_classes(df_raw, args.label_col, args.min_samples_per_class)
        if len(df) < len(df_raw):
            log.warning(
                "⚠ 희소 클래스 제거 후 남은 샘플 수: %d (원래 %d)",
                len(df), len(df_raw)
            )
    else:
        df = df_raw

    # 4) train/test 분할
    min_required = math.ceil(1.0 / args.test_size)
    log.info(
        "[*] 테스트 비율 %.1f%% 기준 '이론상' 각 클래스 최소 필요 샘플 수 ≈ %d개",
        args.test_size * 100.0,
        min_required
    )

    X_train, X_test, y_train, y_test, feature_names = split_dataset(
        df,
        label_col=args.label_col,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    # 5) 저장
    save_splits(
        X_train, X_test, y_train, y_test,
        feature_names,
        out_dir
    )

    log.info("✅ [Dataset Manager v4.3] 완료.")


if __name__ == "__main__":
    main()