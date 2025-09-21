#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# data_builder.py (v2.0 - Real-time Data Aggregator)
import os
import json
import time
import pandas as pd
import threading
import datetime

# --- 경로 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUS_DIR = os.path.join(PROJECT_ROOT, 'bus')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output') # 출력 폴더
OUTPUT_CSV_PATH = os.path.join(OUTPUT_DIR, 'labeled_cti_dataset.csv')

LOG_SOURCES = {
    "events": os.path.join(BUS_DIR, 'bus.log'),
    "telemetry": os.path.join(BUS_DIR, 'bus_dvd.log'),
}

all_log_entries = []
data_lock = threading.Lock()
stop_event = threading.Event()

def log_monitor(log_name, file_path):
    """단일 로그 파일을 실시간으로 감시하고 전역 리스트에 추가하는 스레드 함수"""
    print(f"[{log_name}] '{os.path.basename(file_path)}' 모니터링 시작...")
    while not os.path.exists(file_path) and not stop_event.is_set():
        time.sleep(1)

    with open(file_path, 'r', errors='ignore') as f:
        f.seek(0, os.SEEK_END)
        while not stop_event.is_set():
            line = f.readline()
            if not line:
                time.sleep(0.05)
                continue
            try:
                log_entry = json.loads(line)
                log_entry['log_source'] = log_name
                log_entry['log_type'] = log_entry.get('type', 'unknown')
                
                with data_lock:
                    all_log_entries.append(log_entry)
            except json.JSONDecodeError:
                pass

def build_dataset_in_background():
    """백그라운드에서 주기적으로 데이터프레임을 만들고 CSV로 저장하는 함수"""
    global all_log_entries
    processed_count = 0
    while not stop_event.is_set():
        time.sleep(10) # 10초마다 데이터셋 업데이트
        with data_lock:
            if len(all_log_entries) == processed_count:
                continue
            current_logs = all_log_entries.copy()
        
        try:
            df = pd.json_normalize(current_logs, sep='_')
            df = df.sort_values(by='ts').reset_index(drop=True)
            
            df['label_attack'] = "Normal"
            attack_start_indices = df[df['log_type'] == 'attack_started'].index
            for start_idx in attack_start_indices:
                df.loc[start_idx:, 'label_attack'] = "Attack"
                
            df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
            processed_count = len(current_logs)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {processed_count}개 로그 처리 완료. CSV 업데이트됨.")
        except Exception as e:
            print(f"[Builder Error] {e}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"데이터 빌더 시작 -> 최종 데이터셋: {OUTPUT_CSV_PATH}")

    threads = [threading.Thread(target=log_monitor, args=(name, path), daemon=True) for name, path in LOG_SOURCES.items()]
    builder_thread = threading.Thread(target=build_dataset_in_background, daemon=True)
    
    for t in threads: t.start()
    builder_thread.start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n사용자 요청으로 데이터 빌더를 중지합니다.")
        stop_event.set()
        print("최종 데이터셋을 저장합니다...")
        df = pd.json_normalize(all_log_entries, sep='_').sort_values(by='ts')
        df['label_attack'] = "Normal"
        attack_start_indices = df[df['log_type'] == 'attack_started'].index
        for start_idx in attack_start_indices:
            df.loc[start_idx:, 'label_attack'] = "Attack"
        df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
        print(f"✅ 총 {len(df)}개 레코드가 '{os.path.basename(OUTPUT_CSV_PATH)}'에 저장되었습니다.")

if __name__ == "__main__":
    main()