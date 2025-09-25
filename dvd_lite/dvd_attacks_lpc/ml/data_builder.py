#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import time
import pandas as pd
import threading
import datetime
import numpy as np

# --- 경로 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUS_DIR = os.path.join(PROJECT_ROOT, 'bus')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
OUTPUT_CSV_PATH = os.path.join(OUTPUT_DIR, 'labeled_cti_dataset.csv')

# --- 데이터 소스 정의 (모든 버스 로그 포함) ---
LOG_SOURCES = {
    "events": os.path.join(BUS_DIR, 'bus.log'),
    "telemetry": os.path.join(BUS_DIR, 'bus_dvd.log'),
    "network": os.path.join(BUS_DIR, 'bus_network.log'),
    "system": os.path.join(BUS_DIR, 'bus_system_events.log'),
}

all_log_entries = []
data_lock = threading.Lock()
stop_event = threading.Event()

def log_monitor(log_name, file_path):
    """단일 로그 파일을 감시하고 전역 리스트에 로그를 추가합니다."""
    print(f"[*] [{log_name}] '{os.path.basename(file_path)}' 모니터링 시작...")
    while not os.path.exists(file_path) and not stop_event.is_set():
        time.sleep(1)

    try:
        with open(file_path, 'r', errors='ignore') as f:
            f.seek(0, os.SEEK_END)
            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                try:
                    log_entry = json.loads(line)
                    with data_lock:
                        all_log_entries.append(log_entry)
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        print(f"[!] [{log_name}] 로그 파일을 찾을 수 없습니다: {file_path}")

def label_and_enrich_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    'bus.log'의 공격 이벤트를 기준으로 모든 데이터에 라벨을 부여하고,
    실행 중인 공격의 이름을 명시적으로 추가합니다.
    """
    df = df.sort_values('ts').reset_index(drop=True)
    df['label_attack'] = "Normal"
    df['attack_name'] = None  # 현재 진행 중인 공격 이름을 저장할 컬럼

    event_logs = df[df['source'] == 'default_event'].copy() # attack_orchestrator가 기록한 로그
    
    start_time, attack_name = None, None
    for _, row in event_logs.iterrows():
        if row['type'] == 'attack_started':
            start_time = row['ts']
            attack_name = row.get('data', {}).get('attack')
        elif row['type'] == 'attack_finished' and start_time is not None:
            # 타임스탬프를 기준으로 해당 공격 기간 내의 모든 로그에 라벨과 공격 이름 부여
            attack_mask = (df['ts'] >= start_time) & (df['ts'] <= row['ts'])
            df.loc[attack_mask, 'label_attack'] = "Attack"
            df.loc[attack_mask, 'attack_name'] = attack_name
            start_time, attack_name = None, None
            
    # 마지막 공격이 끝나지 않은 경우 처리
    if start_time is not None:
        attack_mask = df['ts'] >= start_time
        df.loc[attack_mask, 'label_attack'] = "Attack"
        df.loc[attack_mask, 'attack_name'] = attack_name
        
    return df

def build_dataset_in_background():
    """백그라운드에서 주기적으로 모든 로그를 통합하여 최종 데이터셋을 생성합니다."""
    global all_log_entries
    processed_count = 0
    while not stop_event.is_set():
        time.sleep(15)
        with data_lock:
            if len(all_log_entries) == processed_count:
                continue
            current_logs = all_log_entries.copy()
        
        print(f"[*] [{datetime.datetime.now().strftime('%H:%M:%S')}] {len(current_logs)}개 로그 감지. 데이터셋 빌드 시작...")
        
        try:
            df = pd.json_normalize(current_logs, sep='_')
            
            # 모든 로그를 타임스탬프 기준으로 라벨링 및 보강
            df = label_and_enrich_data(df)
            
            # (옵션) 추가적인 피처 엔지니어링
            # df = enhanced_feature_engineering(df)
            
            df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
            processed_count = len(current_logs)
            print(f"[*] [{datetime.datetime.now().strftime('%H:%M:%S')}] {processed_count}개 로그 처리 완료. CSV 업데이트됨.")
        except Exception as e:
            print(f"[!] [Builder Error] 데이터셋 빌드 중 오류 발생: {e}", file=sys.stderr)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[*] CTI 통합 데이터 빌더 시작 -> 최종 데이터셋: {OUTPUT_CSV_PATH}")
    
    for name, path in LOG_SOURCES.items():
        if not os.path.exists(path):
            print(f"[*] '{os.path.basename(path)}' 파일을 기다리는 중...")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'a').close()

    threads = [threading.Thread(target=log_monitor, args=(name, path), daemon=True) for name, path in LOG_SOURCES.items()]
    builder_thread = threading.Thread(target=build_dataset_in_background, daemon=True)
    
    for t in threads:
        t.start()
    builder_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] 사용자 요청으로 데이터 빌더를 중지합니다. 최종 데이터셋 저장 중...")
        stop_event.set()
        time.sleep(2)
        with data_lock:
            df = pd.json_normalize(all_log_entries, sep='_')
            df = label_and_enrich_data(df)
            df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
            print(f"[*] 총 {len(df)}개 레코드가 '{os.path.basename(OUTPUT_CSV_PATH)}'에 저장되었습니다.")

if __name__ == "__main__":
    main()