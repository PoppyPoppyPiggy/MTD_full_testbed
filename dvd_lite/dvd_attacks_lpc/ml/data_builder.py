#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import pandas as pd
from tqdm import tqdm
import numpy as np
import argparse

# --- Path Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUS_DIR = os.path.join(PROJECT_ROOT, 'bus')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'ml', 'output')
# ⭐️ Corrected LOG_FILES_INFO to reflect unique log paths from monitors
LOG_FILES_INFO = {
    "system_events": os.path.join(BUS_DIR, 'bus.log'), # Ground Truth (Attack Orchestrator)
    "telemetry": os.path.join(BUS_DIR, 'bus_telemetry.log'),
    "network": os.path.join(BUS_DIR, 'bus_network.log'),
    "qos": os.path.join(BUS_DIR, 'bus_qos.log'), 
    "event_relay": os.path.join(BUS_DIR, 'bus_system_events.log'),
}

# --- Constants Definition ---
TIME_WINDOW_SEC = 5.0 # Time window for feature extraction (seconds)

def parse_log_file(filepath: str) -> pd.DataFrame:
    """Reads a single JSONL log file and converts it to a DataFrame."""
    records = []
    if not os.path.exists(filepath):
        return pd.DataFrame()
        
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
    """Extracts attack_started/finished events from 'bus.log' to create an attack timeline."""
    timeline = []
    
    # Check if 'data.attack_category' column exists
    category_col = 'data.attack_category'
    if category_col not in df_events.columns:
        print("[!] 경고: 'data.attack_category' 열이 이벤트 로그에 없습니다. 공격 타임라인을 생성할 수 없습니다.")
        return []

    # 1. attack_started 이벤트 필터링
    # ⭐️ 수정: df_events[category_col]을 직접 사용하여 시리즈의 .notna() 메서드를 호출
    attack_starts = df_events[
        (df_events['type'] == 'attack_started') & (df_events[category_col].notna())
    ].sort_values('ts').to_dict('records')
    
    # 2. attack_finished 이벤트 필터링
    attack_fins = df_events[
        (df_events['type'] == 'attack_finished') & (df_events[category_col].notna())
    ].sort_values('ts')

    for start_event in attack_starts:
        start_time = start_event['ts']
        attack_category = start_event.get(category_col, 'unknown_attack')

        # 해당 공격의 가장 가까운 종료 이벤트를 찾음
        matching_fins = attack_fins[
             (attack_fins[category_col] == attack_category) & 
             (attack_fins['ts'] > start_time)
        ]
        
        corresponding_fin = matching_fins.iloc[0] if not matching_fins.empty else None
        
        # Assume 60 seconds if no explicit end event is found
        end_time = corresponding_fin['ts'] if corresponding_fin is not None else start_time + 60 

        timeline.append({
            'start': start_time,
            'end': end_time,
            'label': attack_category
        })
        
    return sorted(timeline, key=lambda x: x['start'])

def label_dataframe(df: pd.DataFrame, timeline: list) -> pd.DataFrame:
    """Assigns labels to each row of the DataFrame based on the timeline."""
    df['label'] = 'normal'
    df = df.sort_values('ts')
    
    for attack in timeline:
        attack_indices = (df['ts'] >= attack['start']) & (df['ts'] <= attack['end'])
        df.loc[attack_indices, 'label'] = attack['label']
        
    return df

def create_features_from_window(df_window: pd.DataFrame) -> pd.Series:
    """Generates a statistical feature vector from the time window DataFrame."""
    # Ensure all time windows generate a feature vector, even if empty (labeled 'normal')
    if df_window.empty:
        return pd.Series({'label': 'normal', 'is_empty': 1.0}, dtype=object).fillna(0)

    features = {'is_empty': 0.0}
    
    # 1. Event count per type
    event_counts = df_window['type'].value_counts()
    for event_type, count in event_counts.items():
        features[f'event_count_{event_type}'] = count

    # 2. Statistical features for key numerical data (min, max, mean, std)
    numeric_cols = {
        'data.alt_m': 'alt', 'data.relative_alt_m': 'rel_alt',
        'data.groundspeed_ms': 'gs', 'data.vx': 'vx', 'data.vy': 'vy', 'data.vz': 'vz',
        'data.xacc': 'xacc', 'data.yacc': 'yacc', 'data.zacc': 'zacc',
        'data.pitch_deg': 'pitch', 'data.roll_deg': 'roll', 'data.yaw_deg': 'yaw',
        'data.avg_rtt_ms': 'rtt', 'data.jitter_ms': 'jitter', 'data.packet_loss_pct': 'loss',
        'data.length': 'pkt_len', 'data.inter_arrival_time_ms': 'pkt_iat',
        'data.cpu_load_pct': 'cpu',
    }
    
    for col, prefix in numeric_cols.items():
        if col in df_window.columns:
            series = pd.to_numeric(df_window[col], errors='coerce').dropna()
            if not series.empty:
                features[f'{prefix}_mean'] = series.mean()
                features[f'{prefix}_std'] = series.std()
                features[f'{prefix}_max'] = series.max()
                features[f'{prefix}_min'] = series.min()

    # 3. Categorical data processing (e.g., Drone Mode)
    if 'data.mode' in df_window.columns:
        # ⭐️ IMPROVED: Use mode ratio for consistency with cti_agent
        mode_counts = df_window['data.mode'].value_counts(normalize=True)
        for mode, ratio in mode_counts.items():
            # Clean mode name (e.g., 'AUTO.RTL' -> 'AUTO_RTL')
            safe_mode = mode.replace('.', '_').replace(' ', '_').upper()
            features[f'mode_ratio_{safe_mode}'] = ratio
    
    # Label is determined by the most frequent value in the window
    label = df_window['label'].mode()
    features['label'] = label[0] if not label.empty else 'normal'

    return pd.Series(features)

def main():
    parser = argparse.ArgumentParser(description="CTI Data Builder v4.0 (Time-series Feature Extraction)")
    parser.add_argument('--output', default=os.path.join(OUTPUT_DIR, 'cti_features_dataset.csv'), help="Path to the generated feature dataset CSV file")
    args = parser.parse_args()

    print("🚀 [Data Builder v4.0] Starting CTI dataset generation.")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Load and Merge all Log Files
    all_dfs = []
    for name, path in LOG_FILES_INFO.items():
        if os.path.exists(path):
            print(f"[*] Loading log file: {path}")
            df = parse_log_file(path)
            if not df.empty:
                # Remove attack_label from monitor logs before merging to avoid contamination of Ground Truth
                if name != "system_events" and 'attack_label' in df.columns:
                    df = df.drop(columns=['attack_label'], errors='ignore')
                all_dfs.append(df)
        else:
            print(f"[!] Warning: Log file not found: {path}")
    
    if not all_dfs:
        print("❌ Error: No log data to process. Exiting.")
        return
        
    combined_df = pd.concat(all_dfs, ignore_index=True).sort_values('ts').reset_index(drop=True)
    print(f"[*] Integrated {len(combined_df)} log events in total.")

    # 2. Extract Attack Timeline and Label Data
    # Ground Truth is derived from the attack_orchestrator log (bus.log).
    # 'attack_orchestrator' source is typically only present in bus.log
    orchestrator_events = combined_df[combined_df['source'] == 'attack_orchestrator']
    
    if orchestrator_events.empty:
        print("[!] Warning: 'attack_orchestrator' 이벤트를 찾을 수 없습니다. 공격 레이블링 없이 'normal'로 처리합니다.")
        # Create a dataframe with all data labeled 'normal' if no orchestrator events exist
        labeled_df = combined_df.copy()
        labeled_df['label'] = 'normal'
        attack_timeline = [] # Empty timeline
    else:
        attack_timeline = extract_attack_timeline(orchestrator_events)
        if not attack_timeline:
            print("[!] Warning: 'attack_started' 이벤트를 찾을 수 없습니다. 공격 레이블링 없이 'normal'로 처리합니다.")
            labeled_df = combined_df.copy()
            labeled_df['label'] = 'normal'
        else:
            print(f"[*] Identified {len(attack_timeline)} attack sequences.")
            labeled_df = label_dataframe(combined_df, attack_timeline)

    print("[*] 전체 데이터에 레이블링을 완료했습니다.")
    print(labeled_df['label'].value_counts())

    # 3. Time-Series Feature Extraction
    print(f"[*] Starting feature extraction with {TIME_WINDOW_SEC}s time windows...")
    
    labeled_df['datetime'] = pd.to_datetime(labeled_df['ts'], unit='s')
    labeled_df = labeled_df.set_index('datetime')
    
    feature_list = []
    # Resample to generate window features
    for _, window_df in tqdm(labeled_df.resample(f'{TIME_WINDOW_SEC}S'), desc="[+] Extracting Features"):
        features = create_features_from_window(window_df)
        feature_list.append(features)

    if not feature_list:
        print("❌ Error: Could not extract features. Data might be too sparse or improperly formatted.")
        return
        
    final_dataset = pd.concat(feature_list, axis=1).T
    
    # Convert all columns to numeric (coercing errors to NaN)
    for col in final_dataset.columns:
        if col != 'label':
            final_dataset[col] = pd.to_numeric(final_dataset[col], errors='coerce')
    
    # Fill NaN values (e.g., from features not present in a window) with 0
    final_dataset = final_dataset.fillna(0) 
    
    # 4. Save Results
    final_dataset.to_csv(args.output, index=False)
    print("\n" + "="*60)
    print(f"✅ Final feature dataset generation complete!")
    print(f"  - Save Path: {args.output}")
    print(f"  - Dataset Size: {final_dataset.shape[0]} samples, {final_dataset.shape[1]} features")
    print(f"  - Label Distribution:\n{final_dataset['label'].value_counts()}")
    print("="*60)

if __name__ == "__main__":
    main()
