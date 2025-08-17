#!/usr/bin/env python3
"""
LPC Metrics CLI - 안정판 윈도우링 도구
타임라인을 1초 그리드로 forward-fill 후 슬라이딩 윈도우 통계 생성
"""

import argparse
import pandas as pd
import numpy as np
import sys
from pathlib import Path

def load_timeline(file_path):
    """타임라인 CSV 로드"""
    try:
        df = pd.read_csv(file_path)
        print(f"타임라인 로드: {len(df)} rows")
        return df
    except Exception as e:
        print(f"타임라인 로드 오류: {e}", file=sys.stderr)
        return None

def normalize_timeline_to_grid(df, grid_interval=1):
    """타임라인을 1초 그리드로 정규화 (forward-fill)"""
    if 't' not in df.columns:
        print("타임라인에 't' 컬럼이 없습니다", file=sys.stderr)
        return None
    
    # 시간 범위 확인
    min_t = int(df['t'].min())
    max_t = int(df['t'].max())
    
    # 1초 간격 그리드 생성
    grid_times = np.arange(min_t, max_t + 1, grid_interval)
    
    # 그리드에 맞춰 forward-fill
    df_sorted = df.sort_values('t').reset_index(drop=True)
    
    grid_data = []
    for t in grid_times:
        # 현재 시간 이하의 가장 최신 데이터 찾기
        mask = df_sorted['t'] <= t
        if mask.any():
            latest_row = df_sorted[mask].iloc[-1].copy()
            latest_row['t'] = t
            grid_data.append(latest_row)
        else:
            # 데이터가 없으면 0으로 초기화
            zero_row = df_sorted.iloc[0].copy()
            for col in ['loss_pct', 'delay_ms', 'jitter_ms', 'dup_pct', 'rate_limit_mbps']:
                if col in zero_row:
                    zero_row[col] = 0.0
            zero_row['t'] = t
            zero_row['module'] = 'waiting'
            zero_row['level'] = 'low'
            grid_data.append(zero_row)
    
    grid_df = pd.DataFrame(grid_data)
    print(f"그리드 정규화: {len(grid_df)} rows (1초 간격)")
    return grid_df

def compute_sliding_windows(df, win_size=3, stride=1):
    """슬라이딩 윈도우 통계 계산"""
    if len(df) < win_size:
        print(f"데이터가 윈도우 크기보다 작음: {len(df)} < {win_size}", file=sys.stderr)
        return None
    
    numeric_cols = ['loss_pct', 'delay_ms', 'jitter_ms', 'dup_pct', 'rate_limit_mbps']
    windows = []
    
    for i in range(0, len(df) - win_size + 1, stride):
        window_data = df.iloc[i:i+win_size]
        
        # 윈도우 통계 계산
        window_stats = {
            'start_t': window_data['t'].iloc[0],
            'end_t': window_data['t'].iloc[-1]
        }
        
        # 각 수치 컬럼의 평균과 표준편차
        for col in numeric_cols:
            if col in window_data.columns:
                window_stats[f'{col}_mean'] = window_data[col].mean()
                window_stats[f'{col}_std'] = window_data[col].std()
        
        # 주요 모듈 (가장 빈번한)
        if 'module' in window_data.columns:
            window_stats['primary_module'] = window_data['module'].mode().iloc[0] if len(window_data['module'].mode()) > 0 else 'unknown'
        
        windows.append(window_stats)
    
    window_df = pd.DataFrame(windows)
    print(f"윈도우 생성: {len(window_df)} windows (size={win_size}, stride={stride})")
    return window_df

def main():
    parser = argparse.ArgumentParser(description='LPC 메트릭스 윈도우링 (안정판)')
    parser.add_argument('timeline_csv', help='입력 타임라인 CSV 파일')
    parser.add_argument('-o', '--output', required=True, help='출력 윈도우 피처 CSV 파일')
    parser.add_argument('--win', type=int, default=3, help='윈도우 크기 (기본: 3)')
    parser.add_argument('--stride', type=int, default=1, help='윈도우 간격 (기본: 1)')
    parser.add_argument('--grid-interval', type=int, default=1, help='그리드 간격 초 (기본: 1)')
    
    args = parser.parse_args()
    
    # 입력 파일 확인
    if not Path(args.timeline_csv).exists():
        print(f"입력 파일 없음: {args.timeline_csv}", file=sys.stderr)
        sys.exit(1)
    
    # 1. 타임라인 로드
    timeline_df = load_timeline(args.timeline_csv)
    if timeline_df is None:
        sys.exit(1)
    
    # 2. 그리드 정규화
    grid_df = normalize_timeline_to_grid(timeline_df, args.grid_interval)
    if grid_df is None:
        sys.exit(1)
    
    # 3. 슬라이딩 윈도우 계산
    window_df = compute_sliding_windows(grid_df, args.win, args.stride)
    if window_df is None:
        sys.exit(1)
    
    # 4. 결과 저장
    try:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        window_df.to_csv(output_path, index=False)
        print(f"윈도우 피처 저장: {output_path}")
        print(f"최종 피처 수: {len(window_df)} rows, {len(window_df.columns)} columns")
    except Exception as e:
        print(f"저장 오류: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()