#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import pandas as pd
from tqdm import tqdm
import numpy as np
import argparse

# --- 경로 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUS_DIR = os.path.join(PROJECT_ROOT, 'bus')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'ml', 'output')
LOG_FILES_INFO = {
    "system_events": os.path.join(BUS_DIR, 'bus.log'),
    "telemetry": os.path.join(BUS_DIR, 'bus_dvd.log'),
    "network": os.path.join(BUS_DIR, 'bus_network.log'),
    "unified": os.path.join(BUS_DIR, 'bus_unified.log'),
}

# --- 상수 정의 ---
TIME_WINDOW_SEC = 5.0 # 특징 추출을 위한 시간 창 (초)

def parse_log_file(filepath: str) -> pd.DataFrame:
    """단일 JSONL 로그 파일을 읽어 데이터프레임으로 변환합니다."""
    records = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not records:
        return pd.DataFrame()
    return pd.json_normalize(records, sep='.')

def extract_attack_timeline(df_events: pd.DataFrame) -> list:
    """'bus.log'에서 attack_started/finished 이벤트를 추출하여 공격 타임라인을 생성합니다."""
    timeline = []
    # 'data.attack' 필드가 있는 attack_started 이벤트만 필터링
    attack_starts = df_events[
        (df_events['type'] == 'attack_started') & (df_events['data.attack'].notna())
    ].sort_values('ts').to_dict('records')
    
    attack_fins = df_events[
        (df_events['type'] == 'attack_finished') & (df_events['data.attack'].notna())
    ].sort_values('ts')

    for start_event in attack_starts:
        start_time = start_event['ts']
        attack_name = start_event['data.attack']
        # ⭐️ 업그레이드: data.attack_category 필드를 레이블로 사용
        attack_category = start_event.get('data.attack_category', 'unknown_attack')

        # 해당 공격의 가장 가까운 종료 이벤트를 찾음
        corresponding_fin = attack_fins[
            (attack_fins['data.attack'] == attack_name) & (attack_fins['ts'] > start_time)
        ].iloc[0] if not attack_fins.empty else None
        
        end_time = corresponding_fin['ts'] if corresponding_fin is not None else start_time + 60 # 종료 이벤트 없으면 60초 가정

        timeline.append({
            'start': start_time,
            'end': end_time,
            'label': attack_category # ⭐️ 구체적인 공격 카테고리를 레이블로 사용
        })
        
    return sorted(timeline, key=lambda x: x['start'])

def label_dataframe(df: pd.DataFrame, timeline: list) -> pd.DataFrame:
    """데이터프레임의 각 행에 타임라인을 기반으로 레이블을 할당합니다."""
    df['label'] = 'normal'
    df = df.sort_values('ts')
    
    for attack in timeline:
        attack_indices = (df['ts'] >= attack['start']) & (df['ts'] <= attack['end'])
        df.loc[attack_indices, 'label'] = attack['label']
        
    return df

def create_features_from_window(df_window: pd.DataFrame) -> pd.Series:
    """시간 창 데이터프레임으로부터 통계적 특징 벡터를 생성합니다."""
    if df_window.empty:
        return pd.Series(dtype='float64')

    features = {}
    
    # 1. 이벤트 타입별 발생 빈도 계산
    event_counts = df_window['type'].value_counts()
    for event_type, count in event_counts.items():
        features[f'event_count_{event_type}'] = count

    # 2. 주요 수치 데이터에 대한 통계량 계산
    numeric_cols = {
        'data.alt_m': 'alt', 'data.relative_alt_m': 'rel_alt',
        'data.groundspeed_ms': 'gs', 'data.vx': 'vx', 'data.vy': 'vy', 'data.vz': 'vz',
        'data.xacc': 'xacc', 'data.yacc': 'yacc', 'data.zacc': 'zacc',
        'data.pitch_deg': 'pitch', 'data.roll_deg': 'roll', 'data.yaw_deg': 'yaw',
        'data.avg_rtt_ms': 'rtt', 'data.jitter_ms': 'jitter', 'data.packet_loss_pct': 'loss',
        'data.length': 'pkt_len', 'data.inter_arrival_time_ms': 'pkt_iat',
        'data.cpu_percent': 'cpu', 'data.memory_mb': 'mem',
    }
    
    for col, prefix in numeric_cols.items():
        if col in df_window.columns:
            series = pd.to_numeric(df_window[col], errors='coerce').dropna()
            if not series.empty:
                features[f'{prefix}_mean'] = series.mean()
                features[f'{prefix}_std'] = series.std()
                features[f'{prefix}_max'] = series.max()
                features[f'{prefix}_min'] = series.min()

    # 3. 카테고리 데이터 처리 (예: 드론 모드)
    if 'data.mode' in df_window.columns:
        # 가장 빈번하게 나타난 모드를 사용
        top_mode = df_window['data.mode'].mode()
        if not top_mode.empty:
            features[f'mode_{top_mode[0]}'] = 1
    
    # 레이블은 시간 창에서 가장 빈번한 값으로 결정
    label = df_window['label'].mode()
    features['label'] = label[0] if not label.empty else 'normal'

    return pd.Series(features)

def main():
    parser = argparse.ArgumentParser(description="CTI 데이터 빌더 v4.0 (시계열 특징 추출)")
    parser.add_argument('--output', default=os.path.join(OUTPUT_DIR, 'cti_features_dataset.csv'), help="생성될 최종 피처 데이터셋 CSV 파일 경로")
    args = parser.parse_args()

    print("🚀 [Data Builder v4.0] CTI 데이터셋 생성을 시작합니다.")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 모든 로그 파일 로드 및 병합
    all_dfs = []
    for name, path in LOG_FILES_INFO.items():
        if os.path.exists(path):
            print(f"[*] 로그 파일 로딩 중: {path}")
            df = parse_log_file(path)
            if not df.empty:
                all_dfs.append(df)
        else:
            print(f"[!] 경고: 로그 파일을 찾을 수 없습니다: {path}")
    
    if not all_dfs:
        print("❌ 오류: 처리할 로그 데이터가 없습니다. 프로그램을 종료합니다.")
        return
        
    combined_df = pd.concat(all_dfs, ignore_index=True).sort_values('ts').reset_index(drop=True)
    print(f"[*] 총 {len(combined_df)}개의 로그 이벤트를 통합했습니다.")

    # 2. 공격 타임라인 추출 및 데이터 레이블링
    attack_timeline = extract_attack_timeline(combined_df[combined_df['source'] == 'attack_orchestrator'])
    if not attack_timeline:
        print("[!] 경고: 'attack_started' 이벤트가 없어 공격 레이블링을 수행할 수 없습니다.")
    else:
        print(f"[*] {len(attack_timeline)}개의 공격 시퀀스를 식별했습니다.")
        
    labeled_df = label_dataframe(combined_df, attack_timeline)
    print("[*] 전체 데이터에 레이블링을 완료했습니다.")
    print(labeled_df['label'].value_counts())

    # 3. 시계열 특징 추출
    print(f"[*] {TIME_WINDOW_SEC}초 간격의 시계열 윈도우로 특징 추출을 시작합니다...")
    
    # 타임스탬프를 datetime 객체로 변환 (resample을 위해)
    labeled_df['datetime'] = pd.to_datetime(labeled_df['ts'], unit='s')
    labeled_df = labeled_df.set_index('datetime')
    
    # resample을 사용하여 시간 윈도우별 특징 생성
    feature_list = []
    # tqdm을 사용하여 진행 상황 표시
    for _, window_df in tqdm(labeled_df.resample(f'{TIME_WINDOW_SEC}S'), desc="[+] 특징 추출 중"):
        if not window_df.empty:
            features = create_features_from_window(window_df)
            feature_list.append(features)

    if not feature_list:
        print("❌ 오류: 특징을 추출할 수 없었습니다. 데이터가 너무 적거나 형식이 맞지 않을 수 있습니다.")
        return
        
    final_dataset = pd.concat(feature_list, axis=1).T
    
    # 모든 열을 수치형으로 변환 (오류 발생 시 NaN으로)
    for col in final_dataset.columns:
        if col != 'label':
            final_dataset[col] = pd.to_numeric(final_dataset[col], errors='coerce')
    
    final_dataset = final_dataset.fillna(0) # 통계 계산 후 발생한 NaN 값을 0으로 채움
    
    # 4. 결과 저장
    final_dataset.to_csv(args.output, index=False)
    print("\n" + "="*60)
    print(f"✅ 최종 특징 데이터셋 생성을 완료했습니다!")
    print(f"  - 저장 경로: {args.output}")
    print(f"  - 데이터셋 크기: {final_dataset.shape[0]} 샘플, {final_dataset.shape[1]} 특징")
    print(f"  - 레이블 분포:\n{final_dataset['label'].value_counts()}")
    print("="*60)

if __name__ == "__main__":
    main()