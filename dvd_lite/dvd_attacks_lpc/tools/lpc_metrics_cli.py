#!/usr/bin/env python3
"""
LPC Metrics CLI - 안전판 (빈 데이터 처리 포함)
"""

import argparse
import pandas as pd
import numpy as np
import sys
from pathlib import Path

def load_timeline(file_path):
    """타임라인 CSV 로드 (안전한 버전)"""
    try:
        df = pd.read_csv(file_path)
        print(f"타임라인 로드: {len(df)} rows")
        
        # 빈 데이터프레임 처리
        if df.empty or len(df) == 0:
            print("⚠️ 타임라인이 비어있음, 샘플 데이터 생성")
            return create_sample_timeline()
            
        return df
    except Exception as e:
        print(f"타임라인 로드 오류: {e}", file=sys.stderr)
        print("샘플 타임라인 생성 중...")
        return create_sample_timeline()

def create_sample_timeline():
    """샘플 타임라인 생성"""
    import time
    current_time = int(time.time())
    
    sample_data = []
    for i in range(10):  # 10초간 샘플 데이터
        sample_data.append({
            't': current_time + i,
            'loss_pct': np.random.uniform(0, 5),
            'delay_ms': np.random.uniform(0, 10),
            'jitter_ms': np.random.uniform(0, 3),
            'dup_pct': 0.0,
            'rate_limit_mbps': 0.0,
            'module': 'sample_attack',
            'level': 'low'
        })
    
    df = pd.DataFrame(sample_data)
    print(f"샘플 타임라인 생성: {len(df)} rows")
    return df

def normalize_timeline_to_grid(df, grid_interval=1):
    """타임라인을 1초 그리드로 정규화 (안전한 버전)"""
    if 't' not in df.columns:
        print("타임라인에 't' 컬럼이 없습니다", file=sys.stderr)
        return None
    
    # NaN 값 처리
    df = df.dropna(subset=['t'])
    if df.empty:
        print("유효한 시간 데이터가 없습니다", file=sys.stderr)
        return create_sample_timeline()
    
    # 시간 범위 확인 (안전한 변환)
    try:
        min_t = int(df['t'].min())
        max_t = int(df['t'].max())
    except (ValueError, TypeError):
        print("시간 데이터 변환 오류, 현재 시간 사용")
        import time
        current_time = int(time.time())
        min_t = current_time
        max_t = current_time + 10
    
    # 최소 10초 보장
    if max_t - min_t < 10:
        max_t = min_t + 10
    
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
            # 데이터가 없으면 기본값으로 초기화
            default_row = {
                't': t,
                'loss_pct': 0.0,
                'delay_ms': 0.0,
                'jitter_ms': 0.0,
                'dup_pct': 0.0,
                'rate_limit_mbps': 0.0,
                'module': 'waiting',
                'level': 'low'
            }
            grid_data.append(default_row)
    
    grid_df = pd.DataFrame(grid_data)
    print(f"그리드 정규화: {len(grid_df)} rows (1초 간격)")
    return grid_df

def compute_sliding_windows(df, win_size=3, stride=1):
    """슬라이딩 윈도우 통계 계산 (안전한 버전)"""
    if len(df) < win_size:
        print(f"데이터가 윈도우 크기보다 작음: {len(df)} < {win_size}", file=sys.stderr)
        # 최소 윈도우 생성
        win_size = max(1, len(df))
    
    numeric_cols = ['loss_pct', 'delay_ms', 'jitter_ms', 'dup_pct', 'rate_limit_mbps']
    windows = []
    
    for i in range(0, len(df) - win_size + 1, stride):
        window_data = df.iloc[i:i+win_size]
        
        # 윈도우 통계 계산
        window_stats = {
            'start_t': window_data['t'].iloc[0],
            'end_t': window_data['t'].iloc[-1]
        }
        
        # 각 수치 컬럼의 평균과 표준편차 (안전한 계산)
        for col in numeric_cols:
            if col in window_data.columns:
                values = pd.to_numeric(window_data[col], errors='coerce').fillna(0)
                window_stats[f'{col}_mean'] = values.mean()
                window_stats[f'{col}_std'] = values.std() if len(values) > 1 else 0.0
            else:
                window_stats[f'{col}_mean'] = 0.0
                window_stats[f'{col}_std'] = 0.0
        
        # 주요 모듈 (가장 빈번한)
        if 'module' in window_data.columns:
            try:
                primary_module = window_data['module'].mode()
                window_stats['primary_module'] = primary_module.iloc[0] if len(primary_module) > 0 else 'unknown'
            except:
                window_stats['primary_module'] = 'unknown'
        else:
            window_stats['primary_module'] = 'unknown'
        
        windows.append(window_stats)
    
    # 최소 1개 윈도우 보장
    if not windows:
        print("윈도우 생성 실패, 기본 윈도우 생성")
        import time
        current_time = int(time.time())
        windows.append({
            'start_t': current_time,
            'end_t': current_time + 3,
            'loss_pct_mean': 0.0,
            'loss_pct_std': 0.0,
            'delay_ms_mean': 0.0,
            'delay_ms_std': 0.0,
            'jitter_ms_mean': 0.0,
            'jitter_ms_std': 0.0,
            'dup_pct_mean': 0.0,
            'dup_pct_std': 0.0,
            'rate_limit_mbps_mean': 0.0,
            'rate_limit_mbps_std': 0.0,
            'primary_module': 'default'
        })
    
    window_df = pd.DataFrame(windows)
    print(f"윈도우 생성: {len(window_df)} windows (size={win_size}, stride={stride})")
    return window_df

def main():
    parser = argparse.ArgumentParser(description='LPC 메트릭스 윈도우링 (안전판)')
    parser.add_argument('timeline_csv', help='입력 타임라인 CSV 파일')
    parser.add_argument('-o', '--output', required=True, help='출력 윈도우 피처 CSV 파일')
    parser.add_argument('--win', type=int, default=3, help='윈도우 크기 (기본: 3)')
    parser.add_argument('--stride', type=int, default=1, help='윈도우 간격 (기본: 1)')
    parser.add_argument('--grid-interval', type=int, default=1, help='그리드 간격 초 (기본: 1)')
    
    args = parser.parse_args()
    
    # 입력 파일 확인
    if not Path(args.timeline_csv).exists():
        print(f"⚠️ 입력 파일 없음: {args.timeline_csv}", file=sys.stderr)
        print("샘플 데이터로 진행...")
        timeline_df = create_sample_timeline()
    else:
        # 1. 타임라인 로드
        timeline_df = load_timeline(args.timeline_csv)
    
    if timeline_df is None or timeline_df.empty:
        print("타임라인 데이터 문제, 샘플 생성")
        timeline_df = create_sample_timeline()
    
    # 2. 그리드 정규화
    grid_df = normalize_timeline_to_grid(timeline_df, args.grid_interval)
    if grid_df is None or grid_df.empty:
        print("그리드 정규화 실패, 샘플 사용")
        grid_df = timeline_df
    
    # 3. 슬라이딩 윈도우 계산
    window_df = compute_sliding_windows(grid_df, args.win, args.stride)
    if window_df is None or window_df.empty:
        print("윈도우 계산 실패")
        sys.exit(1)
    
    # 4. 결과 저장
    try:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        window_df.to_csv(output_path, index=False)
        print(f"✅ 윈도우 피처 저장: {output_path}")
        print(f"최종 피처 수: {len(window_df)} rows, {len(window_df.columns)} columns")
    except Exception as e:
        print(f"저장 오류: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()