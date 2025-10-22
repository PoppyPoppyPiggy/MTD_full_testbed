#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import pandas as pd
from tqdm import tqdm
import numpy as np
import argparse
from typing import List, Dict, Any, Tuple # Tuple 추가

# --- Path Configuration ---
# 이 파일(data_builder.py)은 ml 디렉토리 안에 있다고 가정
ML_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.dirname(ML_DIR) # 상위 디렉토리 (dvd_attacks_lpc)
BUS_DIR = os.path.join(PROJECT_ROOT, 'bus')
OUTPUT_DIR = os.path.join(ML_DIR, 'output') # ml/output

# ⭐️ 로그 파일 경로와 소스 이름 매핑 (정확하게 지정)
LOG_FILES_INFO = {
    "system_events": os.path.join(BUS_DIR, 'bus_system_events.log'), # system_event_monitor 출력
    "telemetry": os.path.join(BUS_DIR, 'bus_telemetry.log'),         # dvd_telemetry_monitor 출력
    "network": os.path.join(BUS_DIR, 'bus_network.log'),           # network_traffic_monitor 출력
    "qos": os.path.join(BUS_DIR, 'bus_qos.log'),                   # qos_monitor 출력
    # 추가: 컨테이너 모니터 로그도 포함 가능 (선택 사항)
    "container_telemetry": os.path.join(BUS_DIR, 'bus_container_telemetry.log'),
    # 추가: 공격 오케스트레이터 로그 (공격 타임라인 추출용)
    "orchestrator_events": os.path.join(BUS_DIR, 'bus.log') # attack_orchestrator 출력
}

# --- Constants Definition ---
TIME_WINDOW_SEC = 5.0 # 특징 추출 시간 창 (초)

def parse_log_file(filepath: str) -> pd.DataFrame:
    """단일 JSONL 로그 파일을 읽어 Pandas DataFrame으로 변환합니다."""
    records = []
    if not os.path.exists(filepath):
        print(f"[!] 경고: 로그 파일을 찾을 수 없습니다: {filepath}")
        return pd.DataFrame() # 빈 DataFrame 반환

    # 파일 크기가 너무 큰 경우 샘플링 또는 분할 처리 고려 (여기서는 전체 로드)
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if file_size_mb > 500: # 예: 500MB 이상이면 경고
         print(f"[!] 경고: 로그 파일 '{os.path.basename(filepath)}'의 크기가 큽니다 ({file_size_mb:.1f} MB). 처리 시간이 오래 걸릴 수 있습니다.")

    print(f"[*] 로그 파일 로딩 중: {os.path.basename(filepath)} ({file_size_mb:.1f} MB)")
    line_count = 0
    error_count = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        # tqdm으로 진행률 표시
        for line in tqdm(f, desc=f"  - Parsing {os.path.basename(filepath)}", unit=" lines"):
            line_count += 1
            try:
                # 빈 줄이나 공백만 있는 줄은 건너뜀
                if not line.strip(): continue
                records.append(json.loads(line))
            except json.JSONDecodeError:
                error_count += 1
                # print(f"[!] 경고: JSON 파싱 오류 (Line {line_count}): {line[:100]}...", file=sys.stderr) # 너무 많은 오류 로그 방지
                continue # 오류 발생 시 해당 라인 건너뜀
            except Exception as e:
                 error_count += 1
                 print(f"[!] 경고: 예상치 못한 오류 (Line {line_count}): {e} - {line[:100]}...", file=sys.stderr)
                 continue

    if error_count > 0:
         print(f"[!] 경고: 총 {error_count}개의 라인에서 파싱 오류 발생 ({filepath})")

    if not records:
        print(f"[*] 정보: 로그 파일이 비어있거나 유효한 JSON 라인이 없습니다: {filepath}")
        return pd.DataFrame()

    try:
        # 데이터 정규화 (nested JSON -> 평탄화)
        df = pd.json_normalize(records, sep='_') # 구분자를 '.' 대신 '_' 사용 (Pandas/Sklearn 호환성)
        print(f"  - 로드 완료: {len(df)}개 레코드")
        return df
    except Exception as e:
        print(f"❌ 오류: DataFrame 변환 중 오류 발생 ({filepath}): {e}", file=sys.stderr)
        return pd.DataFrame() # 오류 시 빈 DataFrame 반환

def extract_attack_timeline(df_orchestrator_events: pd.DataFrame) -> List[Dict[str, Any]]:
    """'bus.log'(오케스트레이터 로그)에서 attack_started/finished 이벤트를 추출하여 공격 타임라인 생성."""
    timeline = []
    if df_orchestrator_events.empty:
         print("[!] 경고: 오케스트레이터 로그가 비어있어 공격 타임라인을 생성할 수 없습니다.")
         return []

    # 필요한 컬럼 확인
    required_cols = ['ts', 'type', 'data_attack_category']
    if not all(col in df_orchestrator_events.columns for col in required_cols):
        print("[!] 경고: 오케스트레이터 로그에 필요한 컬럼(ts, type, data_attack_category)이 없습니다.")
        print("       사용 가능한 컬럼:", df_orchestrator_events.columns.tolist())
        return []

    # 'attack_started' 이벤트 필터링 및 시간순 정렬
    attack_starts = df_orchestrator_events[
        (df_orchestrator_events['type'] == 'attack_started') &
        (df_orchestrator_events['data_attack_category'].notna())
    ].sort_values('ts').to_dict('records')

    # 'attack_finished' 이벤트 필터링 및 시간순 정렬
    attack_fins = df_orchestrator_events[
        (df_orchestrator_events['type'] == 'attack_finished') &
        (df_orchestrator_events['data_attack_category'].notna())
    ].sort_values('ts')

    print(f"[*] 공격 시작 이벤트 {len(attack_starts)}개 발견.")

    processed_fin_indices = set() # 이미 매칭된 종료 이벤트 인덱스 추적

    for start_event in attack_starts:
        start_time = start_event['ts']
        attack_category = start_event['data_attack_category'] # 예: 'gps-spoofing'

        # 동일 카테고리 & 시작 시간 이후의 종료 이벤트 찾기
        matching_fins = attack_fins[
            (attack_fins['data_attack_category'] == attack_category) &
            (attack_fins['ts'] > start_time) &
            (~attack_fins.index.isin(processed_fin_indices)) # 아직 매칭되지 않은 종료 이벤트만
        ]

        end_time = None
        if not matching_fins.empty:
            # 가장 가까운 종료 이벤트 선택
            corresponding_fin = matching_fins.iloc[0]
            end_time = corresponding_fin['ts']
            processed_fin_indices.add(corresponding_fin.name) # 사용된 인덱스 기록
        else:
            # 매칭되는 종료 이벤트가 없으면, 다음 공격 시작 시간 또는 임의의 시간(예: 60초)까지로 간주
            # 다음 공격 시작 시간 찾기
            next_start_time = df_orchestrator_events[
                (df_orchestrator_events['ts'] > start_time) &
                (df_orchestrator_events['type'] == 'attack_started')
            ]['ts'].min()

            if pd.notna(next_start_time):
                end_time = next_start_time - 0.001 # 다음 시작 직전까지
            else:
                end_time = start_time + 60 # 기본 60초 지속으로 가정

            print(f"  - 경고: '{attack_category}' (시작: {start_time:.2f})에 대한 종료 이벤트 없음. 종료 시간 추정: {end_time:.2f}")

        timeline.append({
            'start': start_time,
            'end': end_time,
            'label': attack_category # 고유 레이블 사용
        })

    # 시간순으로 정렬하여 반환
    return sorted(timeline, key=lambda x: x['start'])


def label_dataframe(df: pd.DataFrame, timeline: List[Dict[str, Any]]) -> pd.DataFrame:
    """타임라인 정보를 기반으로 DataFrame의 각 행에 'label'을 할당합니다."""
    if 'ts' not in df.columns:
         print("❌ 오류: DataFrame에 'ts' 컬럼이 없어 레이블링할 수 없습니다.")
         df['label'] = 'normal' # 기본값 할당
         return df

    # 기본 레이블 'normal'로 초기화
    df['label'] = 'normal'
    # 'ts' 기준으로 정렬 (효율적인 레이블링 위해)
    df = df.sort_values('ts')

    print(f"[*] 공격 타임라인 ({len(timeline)}개) 기준으로 데이터 레이블링 시작...")
    labeled_count = 0
    # 타임라인 순회하며 레이블 적용
    # DataFrame이 크면 이 방식은 느릴 수 있음 (최적화 가능: merge_asof 등)
    for attack in tqdm(timeline, desc="  - Labeling data", unit=" attacks"):
        # 해당 시간 범위 내의 인덱스 찾기
        attack_indices = df[(df['ts'] >= attack['start']) & (df['ts'] < attack['end'])].index
        if not attack_indices.empty:
            df.loc[attack_indices, 'label'] = attack['label']
            labeled_count += len(attack_indices)

    print(f"  - 레이블링 완료: 총 {labeled_count}개 레코드에 공격 레이블 할당됨.")
    return df

# ⭐️ 실시간 에이전트와 특징 추출 로직 통일 (별도 파일 분리 또는 함수 공유 권장)
def create_features_from_window(df_window: pd.DataFrame) -> pd.Series:
    """주어진 시간 창(DataFrame)으로부터 통계적 특징 벡터(Series)를 생성합니다."""
    # 실시간 에이전트(ai_cti_agent.py)의 로직과 동일하게 유지

    if df_window.empty:
        # 빈 윈도우일 경우, 'label'='normal'과 'is_empty'=1만 포함하고 나머지는 0으로 채움
        # (학습 데이터 생성 시 이 경우는 거의 없지만, 일관성을 위해)
        return pd.Series({'label': 'normal', 'is_empty': 1.0}, dtype=object).fillna(0)

    features = {'is_empty': 0.0} # 데이터가 있음을 표시

    # 1. 이벤트 타입별 발생 빈도
    # 'type' 컬럼이 없으면 건너뜀 (오류 방지)
    if 'type' in df_window.columns:
        event_counts = df_window['type'].value_counts()
        for event_type, count in event_counts.items():
            # 컬럼 이름에 포함될 수 없는 문자 제거/치환 (예: '/')
            safe_event_type = str(event_type).replace('/', '_').replace('.', '_')
            features[f'event_count_{safe_event_type}'] = count

    # 2. 주요 수치 데이터 통계량 (mean, std, max, min)
    # ⭐️ 컬럼 이름 prefix를 '_'로 변경 (json_normalize 구분자와 일치)
    numeric_cols = {
        'data_alt_m': 'alt', 'data_relative_alt_m': 'rel_alt',
        'data_groundspeed_ms': 'gs', 'data_vx': 'vx', 'data_vy': 'vy', 'data_vz': 'vz',
        'data_xacc': 'xacc', 'data_yacc': 'yacc', 'data_zacc': 'zacc',
        'data_pitch_deg': 'pitch', 'data_roll_deg': 'roll', 'data_yaw_deg': 'yaw',
        'data_avg_rtt_ms': 'rtt', 'data_jitter_ms': 'jitter', 'data_packet_loss_pct': 'loss',
        'data_length': 'pkt_len', 'data_inter_arrival_time_ms': 'pkt_iat',
        'data_cpu_load_pct': 'cpu', # telemetry 모니터에서 생성
        # 'data_memory_mb': 'mem', # 메모리 정보는 현재 수집되지 않음
        # 추가: 배터리 정보
        'data_battery_v': 'bat_v',
        'data_battery_pct': 'bat_pct',
    }

    for col, prefix in numeric_cols.items():
        if col in df_window.columns:
            # 숫자로 변환 시도, 실패 시 NaN으로 변환 후 제거
            series = pd.to_numeric(df_window[col], errors='coerce').dropna()
            if not series.empty:
                features[f'{prefix}_mean'] = series.mean()
                features[f'{prefix}_std'] = series.std() # 분산이 0이면 std는 0
                features[f'{prefix}_max'] = series.max()
                features[f'{prefix}_min'] = series.min()
                features[f'{prefix}_count'] = series.count() # 해당 시간 창 내 유효 데이터 개수

    # 3. 카테고리 데이터 처리 (드론 모드 비율)
    if 'data_mode' in df_window.columns:
        # 결측치 제외하고 비율 계산
        mode_counts = df_window['data_mode'].dropna().value_counts(normalize=True)
        for mode, ratio in mode_counts.items():
            # 안전한 컬럼 이름 생성
            safe_mode = str(mode).replace('.', '_').replace(' ', '_').upper()
            features[f'mode_ratio_{safe_mode}'] = ratio

    # 4. ARP Spoofing 관련 특징 추가
    if 'data_arp_op' in df_window.columns:
        arp_ops = pd.to_numeric(df_window['data_arp_op'], errors='coerce').dropna()
        if not arp_ops.empty:
            features['arp_request_count'] = (arp_ops == 1).sum() # ARP 요청 횟수
            features['arp_reply_count'] = (arp_ops == 2).sum()   # ARP 응답 횟수

    # 5. TCP 플래그 카운트 추가
    if 'data_tcp_flags' in df_window.columns:
         # 'S' (SYN), 'R' (RST), 'F' (FIN) 플래그가 포함된 패킷 수 계산
         flags_series = df_window['data_tcp_flags'].dropna().astype(str)
         features['tcp_syn_count'] = flags_series.str.contains('S').sum()
         features['tcp_rst_count'] = flags_series.str.contains('R').sum()
         features['tcp_fin_count'] = flags_series.str.contains('F').sum()


    # 윈도우 내에서 가장 빈번하게 나타난 레이블을 해당 윈도우의 대표 레이블로 설정
    label = df_window['label'].mode()
    features['label'] = label[0] if not label.empty else 'normal'

    # 생성된 특징들을 Series 객체로 변환하여 반환
    return pd.Series(features)

def main():
    parser = argparse.ArgumentParser(description="CTI Data Builder v4.2 (Feature Consistency & Stability)")
    parser.add_argument('--output', default=os.path.join(OUTPUT_DIR, 'cti_features_dataset.csv'), help="생성될 특징 데이터셋 CSV 파일 경로")
    parser.add_argument('--window-size', type=float, default=TIME_WINDOW_SEC, help="특징 추출 시간 창 크기 (초)")
    args = parser.parse_args()

    print(f"🚀 [Data Builder v4.2] CTI 데이터셋 생성 시작 (Window: {args.window_size}s)")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 모든 로그 파일 로드 및 병합
    all_dfs: List[pd.DataFrame] = []
    orchestrator_df = pd.DataFrame() # 오케스트레이터 로그는 따로 저장

    for name, path in LOG_FILES_INFO.items():
        df = parse_log_file(path)
        if not df.empty:
            if name == "orchestrator_events":
                 orchestrator_df = df
            # 오케스트레이터 로그 외에는 'attack_label' 컬럼 제거 (레이블링은 타임라인 기준으로)
            elif 'attack_label' in df.columns:
                 df = df.drop(columns=['attack_label'], errors='ignore')

            # 'ts' 컬럼이 없으면 추가 (파일 수정 시간 기반 - 부정확할 수 있음)
            if 'ts' not in df.columns:
                 print(f"[!] 경고: '{os.path.basename(path)}' 로그에 'ts' 필드 없음. 파일 수정 시간 사용.")
                 try:
                      mtime = os.path.getmtime(path)
                      # 모든 레코드에 동일한 시간 적용 (개선 필요)
                      df['ts'] = mtime
                 except Exception:
                       print(f"  - 파일 수정 시간 읽기 실패. 해당 로그 무시.")
                       continue # ts 없으면 병합 불가

            all_dfs.append(df)

    if not all_dfs:
        print("❌ 오류: 처리할 로그 데이터가 없습니다. bus/ 디렉토리를 확인하세요.")
        return

    # 'ts' 기준으로 모든 로그 병합 및 정렬
    combined_df = pd.concat(all_dfs, ignore_index=True).sort_values('ts').reset_index(drop=True)
    # 메모리 사용량 확인 (디버깅용)
    # print(f"[*] Combined DataFrame memory usage: {combined_df.memory_usage(deep=True).sum() / (1024*1024):.2f} MB")
    print(f"[*] 총 {len(combined_df)}개의 로그 이벤트 통합 완료.")

    # 2. 공격 타임라인 추출 및 데이터 레이블링
    attack_timeline = extract_attack_timeline(orchestrator_df)
    labeled_df = label_dataframe(combined_df, attack_timeline)

    # 메모리 정리 (필요 없는 원본 DataFrame 삭제)
    del all_dfs, combined_df, orchestrator_df

    print("[*] 레이블 분포 확인:")
    print(labeled_df['label'].value_counts())

    # 3. 시간 단위 특징 추출 (Resampling)
    print(f"[*] {args.window_size}초 시간 창 단위로 특징 추출 시작...")

    # 'ts'를 datetime 인덱스로 변환 (메모리 사용량 증가 주의)
    try:
        labeled_df['datetime'] = pd.to_datetime(labeled_df['ts'], unit='s')
        labeled_df = labeled_df.set_index('datetime')
    except Exception as e:
         print(f"❌ 오류: 'ts' 컬럼을 datetime 인덱스로 변환 실패: {e}", file=sys.stderr)
         # 여기서 실패하면 진행 불가
         return

    feature_list = []
    # resample: 시간 기준으로 그룹화 (지정된 시간 간격: '5S', '1T' 등)
    # 각 그룹(시간 창)에 대해 create_features_from_window 함수 적용
    resampler = labeled_df.resample(f'{args.window_size}S')
    total_windows = len(resampler) # tqdm을 위한 전체 윈도우 수 계산

    for name, window_df in tqdm(resampler, total=total_windows, desc="  - Extracting features", unit=" window"):
        if window_df.empty: # 빈 시간 창은 건너뜀
             continue
        features = create_features_from_window(window_df)
        if features is not None:
             # 생성된 특징 Series에 시간 정보(윈도우 시작 시간) 추가 (선택 사항)
             # features['window_start_ts'] = name.timestamp()
             feature_list.append(features)

    if not feature_list:
        print("❌ 오류: 특징을 추출할 수 없었습니다. 로그 데이터 또는 시간 창 설정을 확인하세요.")
        return

    # 추출된 특징 리스트를 하나의 DataFrame으로 결합
    final_dataset = pd.DataFrame(feature_list) # 리스트로부터 생성

    # 모든 특징 컬럼을 숫자로 변환 (레이블 제외), 변환 불가 시 0으로 채움
    feature_cols = [col for col in final_dataset.columns if col != 'label']
    final_dataset[feature_cols] = final_dataset[feature_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

    # 불필요한 컬럼 제거 (예: 모든 값이 0인 컬럼 - 선택 사항)
    # cols_to_drop = [col for col in feature_cols if final_dataset[col].sum() == 0]
    # if cols_to_drop:
    #     print(f"[*] 정보: 모든 값이 0인 {len(cols_to_drop)}개 컬럼 제거됨: {cols_to_drop}")
    #     final_dataset = final_dataset.drop(columns=cols_to_drop)

    # 4. 결과 저장
    try:
        final_dataset.to_csv(args.output, index=False)
        print("\n" + "="*60)
        print(f"✅ 최종 특징 데이터셋 생성 완료!")
        print(f"  - 저장 경로: {args.output}")
        print(f"  - 데이터셋 크기: {final_dataset.shape[0]} 샘플, {final_dataset.shape[1]} 특징 (레이블 포함)")
        print(f"  - 레이블 분포:\n{final_dataset['label'].value_counts()}")
        print("="*60)
    except Exception as e:
        print(f"❌ 오류: 최종 데이터셋 저장 실패 ({args.output}): {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
