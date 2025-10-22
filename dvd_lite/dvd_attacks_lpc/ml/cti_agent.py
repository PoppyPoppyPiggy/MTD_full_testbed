#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import joblib # 모델 로딩
import pandas as pd
import numpy as np
from collections import deque
import threading
from typing import Dict, Any, Optional, List # List 추가

# --- 경로 설정 ---
ML_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.dirname(ML_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BUS_LOG_PATH = os.path.join(PROJECT_ROOT, 'bus', 'bus.log') # Alert 로깅 경로
import datetime

def log_bus_event(type: str, data: Dict[str, Any], source_override: str = "ai_cti_agent"):
    """간단한 버스 이벤트 로깅 함수 (ML alert용)"""
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": time.time(),
        "source": source_override,
        "type": type,
        "data": data,
    }
    try:
        # bus.log 파일에 append 모드로 기록
        with open(BUS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"Warning: Failed to write alert to bus.log: {e}")
        # 실패 시 stdout으로라도 출력
        # print(json.dumps(record, ensure_ascii=False, default=str))


# --- 상수 정의 ---
MODEL_PATH = os.path.join(PROJECT_ROOT, 'ml', 'output', 'cti_classifier_model.joblib')
FEATURES_PATH = os.path.join(PROJECT_ROOT, 'ml', 'output', 'training_features.json')
# ⭐️ 실시간으로 감시할 로그 파일 경로 (data_builder와 일치)
LOG_SOURCES = {
    "system_events": os.path.join(PROJECT_ROOT, 'bus', 'bus_system_events.log'),
    "telemetry": os.path.join(PROJECT_ROOT, 'bus', 'bus_telemetry.log'),
    "network": os.path.join(PROJECT_ROOT, 'bus', 'bus_network.log'),
    "qos": os.path.join(PROJECT_ROOT, 'bus', 'bus_qos.log'),
    "container_telemetry": os.path.join(PROJECT_ROOT, 'bus', 'bus_container_telemetry.log'),
    # 오케스트레이터 로그는 타임라인 생성용, 실시간 분석에는 불필요
}
TIME_WINDOW_SEC = 5.0  # 특징 추출 시간 창 (data_builder와 동일)
PREDICTION_INTERVAL_SEC = 1.0 # 예측 수행 주기 (초)
CONFIDENCE_THRESHOLD = 0.70 # 위협 탐지 신뢰도 임계값

# ==============================================================================
# 실시간 특징 공학 (data_builder.py와 로직 동일화)
# ==============================================================================
def create_features_from_window(df_window: pd.DataFrame) -> Optional[pd.Series]:
    """시간 창 데이터프레임으로부터 통계적 특징 벡터(Series)를 생성합니다."""
    # data_builder.py의 함수와 동일한 로직 사용

    if df_window.empty:
        # 빈 윈도우 -> 특징 없음 (None 반환 또는 기본 'normal' 특징 반환 선택 가능)
        # 여기서는 None 반환하여 예측 스킵
        return None

    features = {'is_empty': 0.0}

    # 1. 이벤트 타입별 발생 빈도
    if 'type' in df_window.columns:
        event_counts = df_window['type'].value_counts()
        for event_type, count in event_counts.items():
            safe_event_type = str(event_type).replace('/', '_').replace('.', '_')
            features[f'event_count_{safe_event_type}'] = count

    # 2. 주요 수치 데이터 통계량
    # data_builder와 동일한 컬럼 및 prefix 사용
    numeric_cols = {
        'data_alt_m': 'alt', 'data_relative_alt_m': 'rel_alt',
        'data_groundspeed_ms': 'gs', 'data_vx': 'vx', 'data_vy': 'vy', 'data_vz': 'vz',
        'data_xacc': 'xacc', 'data_yacc': 'yacc', 'data_zacc': 'zacc',
        'data_pitch_deg': 'pitch', 'data_roll_deg': 'roll', 'data_yaw_deg': 'yaw',
        'data_avg_rtt_ms': 'rtt', 'data_jitter_ms': 'jitter', 'data_packet_loss_pct': 'loss',
        'data_length': 'pkt_len', 'data_inter_arrival_time_ms': 'pkt_iat',
        'data_cpu_load_pct': 'cpu', # telemetry 또는 container 모니터
        'data_battery_v': 'bat_v', # telemetry 또는 container 모니터
        'data_battery_pct': 'bat_pct', # telemetry 또는 container 모니터
    }

    for col, prefix in numeric_cols.items():
        if col in df_window.columns:
            series = pd.to_numeric(df_window[col], errors='coerce').dropna()
            if not series.empty:
                features[f'{prefix}_mean'] = series.mean()
                features[f'{prefix}_std'] = series.std(ddof=0) # ddof=0 for population std if needed, default is 1
                features[f'{prefix}_max'] = series.max()
                features[f'{prefix}_min'] = series.min()
                features[f'{prefix}_count'] = series.count()

    # 3. 카테고리 데이터 (드론 모드 비율)
    if 'data_mode' in df_window.columns:
        mode_counts = df_window['data_mode'].dropna().value_counts(normalize=True)
        for mode, ratio in mode_counts.items():
            safe_mode = str(mode).replace('.', '_').replace(' ', '_').upper()
            features[f'mode_ratio_{safe_mode}'] = ratio

    # 4. ARP 특징
    if 'data_arp_op' in df_window.columns:
        arp_ops = pd.to_numeric(df_window['data_arp_op'], errors='coerce').dropna()
        if not arp_ops.empty:
            features['arp_request_count'] = (arp_ops == 1).sum()
            features['arp_reply_count'] = (arp_ops == 2).sum()

    # 5. TCP 플래그 카운트
    if 'data_tcp_flags' in df_window.columns:
         flags_series = df_window['data_tcp_flags'].dropna().astype(str)
         features['tcp_syn_count'] = flags_series.str.contains('S').sum()
         features['tcp_rst_count'] = flags_series.str.contains('R').sum()
         features['tcp_fin_count'] = flags_series.str.contains('F').sum()

    if not features: return None # 특징이 하나도 없으면 None 반환

    # Series로 변환
    feature_series = pd.Series(features)

    # NaN 값 0으로 채우기 (std 계산 시 0 나올 수 있음)
    return feature_series.fillna(0)


# ==============================================================================
# 실시간 로그 팔로워
# ==============================================================================
# ⭐️ 로그 파일 팔로워 (system_event_monitor와 유사하게 subprocess 사용 고려)
# 여기서는 간단하게 python 내장 함수로 구현 (파일 I/O 부하 주의)
def follow(filepath: str, queue: deque, stop_event: threading.Event):
    """파일의 새로운 라인을 지속적으로 읽어 deque에 추가합니다."""
    print(f"[*] '{os.path.basename(filepath)}' 로그 팔로잉 시작...")
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
            # 파일 끝으로 이동
            file.seek(0, os.SEEK_END)
            while not stop_event.is_set():
                line = file.readline()
                if not line:
                    # 파일 변경 감지를 위해 잠시 대기 (inode 변경 등 고급 처리 필요 시 watchdog 라이브러리 고려)
                    time.sleep(0.05)
                    # 파일이 재생성되었는지 간단히 확인 (더 견고한 방법 필요)
                    try:
                         if file.tell() > os.fstat(file.fileno()).st_size:
                              print(f"[!] 로그 파일 '{os.path.basename(filepath)}' 변경 감지됨. 다시 엽니다.")
                              file.seek(0, os.SEEK_END) # 파일 끝으로 다시 이동
                    except OSError: # 파일이 삭제된 경우 등
                         print(f"[!] 로그 파일 '{os.path.basename(filepath)}' 접근 오류. 팔로잉 중단.")
                         break # 해당 파일 팔로잉 중단
                    continue

                try:
                    # 빈 줄이나 공백만 있는 줄은 무시
                    if line.strip():
                        log_entry = json.loads(line)
                        # 'ts' 필드가 없으면 현재 시간 추가 (데이터 일관성)
                        if 'ts' not in log_entry:
                            log_entry['ts'] = time.time()
                        queue.append(log_entry)
                except json.JSONDecodeError:
                     # print(f"[!] JSON 파싱 오류 무시: {line[:100]}...") # 너무 많은 로그 방지
                     pass
                except Exception as read_err:
                     print(f"[!] 로그 라인 처리 중 오류 ({os.path.basename(filepath)}): {read_err}", file=sys.stderr)

    except FileNotFoundError:
        print(f"[!] 경고: 로그 파일을 찾을 수 없습니다: {filepath}. 해당 소스는 모니터링되지 않습니다.")
    except Exception as e:
        print(f"❌ '{os.path.basename(filepath)}' 팔로잉 중 예외 발생: {e}", file=sys.stderr)
    finally:
        print(f"[*] '{os.path.basename(filepath)}' 로그 팔로잉 종료.")


# ==============================================================================
# CTI 에이전트 메인 로직
# ==============================================================================
def main():
    print("🚀 [AI-CTI Agent v4.1] 지능형 위협 분류 에이전트 시작 (Feature Consistency)")
    stop_event = threading.Event() # 스레드 종료 플래그

    # 1. 모델 및 피처 목록 로드
    print(f"[*] AI 모델 및 피처 목록 로드 시도...")
    model = None
    training_features: List[str] = []
    # 파일이 생성될 때까지 주기적으로 확인 (최대 1분 대기)
    wait_start = time.time()
    while time.time() - wait_start < 60:
        if os.path.exists(MODEL_PATH) and os.path.exists(FEATURES_PATH):
            try:
                model = joblib.load(MODEL_PATH)
                with open(FEATURES_PATH, 'r') as f:
                    training_features = json.load(f)['features']
                print(f"✅ AI 모델 로드 완료: '{os.path.basename(MODEL_PATH)}'")
                print(f"✅ {len(training_features)}개 학습 피처 목록 로드 완료: '{os.path.basename(FEATURES_PATH)}'")
                break # 로드 성공 시 루프 탈출
            except Exception as e:
                print(f"❌ 오류: AI 모델/피처 파일 로드 실패 (파일은 존재하나 읽기 오류): {e}", file=sys.stderr)
                sys.exit(1) # 치명적 오류로 간주하고 종료
        else:
             print(f"   - 대기 중... (모델: {'OK' if os.path.exists(MODEL_PATH) else '없음'}, 피처: {'OK' if os.path.exists(FEATURES_PATH) else '없음'})")
             time.sleep(3)
    else: # while 루프가 break 없이 완료된 경우 (타임아웃)
         print(f"❌ 오류: AI 모델 또는 피처 파일을 지정된 시간 내에 찾을 수 없습니다.")
         print(f"   - 모델 경로: {MODEL_PATH}")
         print(f"   - 피처 경로: {FEATURES_PATH}")
         print("       먼저 train_classifier.py를 성공적으로 실행해야 합니다.")
         sys.exit(1)

    # 2. 실시간 로그 수집 스레드 시작
    log_queues: Dict[str, deque] = {name: deque(maxlen=5000) for name in LOG_SOURCES.keys()} # 각 소스별 큐
    log_threads: List[threading.Thread] = []

    for name, path in LOG_SOURCES.items():
        # 로그 파일 디렉토리 생성 (없으면)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 빈 파일 생성 (처음 실행 시 필요)
        if not os.path.exists(path):
             try: open(path, 'a').close()
             except Exception: pass # 생성 실패해도 일단 진행

        # 각 로그 파일에 대한 팔로워 스레드 생성 및 시작
        thread = threading.Thread(target=follow, args=(path, log_queues[name], stop_event), daemon=True)
        log_threads.append(thread)
        thread.start()

    print(f"[*] {len(log_threads)}개의 로그 소스 감시 시작...")

    time_window_data = deque() # 현재 시간 창에 포함된 모든 로그
    last_prediction_time = 0

    try:
        while not stop_event.is_set():
            now = time.time()
            new_data_count = 0

            # 3. 모든 큐에서 최신 로그를 시간 창(deque)으로 이동
            for queue in log_queues.values():
                while queue:
                    log = queue.popleft()
                    time_window_data.append(log)
                    new_data_count += 1

            # 4. 시간 창에서 오래된 데이터 제거 (TIME_WINDOW_SEC 기준)
            removed_count = 0
            while time_window_data and (now - time_window_data[0].get('ts', 0)) > TIME_WINDOW_SEC:
                time_window_data.popleft()
                removed_count += 1

            # if new_data_count > 0 or removed_count > 0:
            #     print(f"[DEBUG] Window Update: Added={new_data_count}, Removed={removed_count}, Current Size={len(time_window_data)}")

            if not time_window_data:
                # 처리할 데이터 없으면 잠시 대기
                time.sleep(0.1)
                continue

            # 5. 예측 주기마다 위협 분석 수행
            if (now - last_prediction_time) >= PREDICTION_INTERVAL_SEC:
                last_prediction_time = now

                # 현재 시간 창 데이터로 DataFrame 생성 (메모리 사용량 주의)
                # list()로 복사하여 반복 중 deque 변경 방지
                current_window_list = list(time_window_data)
                if not current_window_list: continue

                try:
                    df_raw_live = pd.json_normalize(current_window_list, sep='_')
                except Exception as norm_err:
                     print(f"❌ 오류: 실시간 데이터 정규화 실패: {norm_err}", file=sys.stderr)
                     continue # 이번 예측 건너뜀

                # 실시간 특징 벡터 생성
                live_features_series = create_features_from_window(df_raw_live)

                if live_features_series is None:
                    # print("[DEBUG] No features extracted from current window.")
                    continue

                # ⭐️ 학습 시 사용된 특징 순서에 맞춰 입력 벡터 준비
                X_live = pd.DataFrame(0.0, index=[0], columns=training_features)
                # live_features_series에 있는 값만 업데이트
                updatable_cols = X_live.columns.intersection(live_features_series.index)
                X_live.loc[0, updatable_cols] = live_features_series[updatable_cols].values

                # NaN/inf 값 최종 확인 및 0으로 대체 (안정성)
                X_live = X_live.replace([np.inf, -np.inf], np.nan).fillna(0)

                # 6. 예측 및 결과 분석/로깅
                try:
                    prediction = model.predict(X_live)[0]
                    probabilities = model.predict_proba(X_live)[0]
                    confidence = probabilities.max()
                    pred_class_index = probabilities.argmax()
                    pred_class_name = model.classes_[pred_class_index]

                    # 예측된 클래스가 저장된 이름과 다를 수 있으므로 확인
                    if pred_class_name != prediction:
                         print(f"[!] 경고: 예측 클래스 불일치 - predict()={prediction}, argmax()={pred_class_name}. argmax() 사용.")
                         prediction = pred_class_name


                    # 'normal'이 아니면서 신뢰도 임계값 이상일 때만 Alert
                    if prediction != 'normal' and confidence >= CONFIDENCE_THRESHOLD:

                        # 특징 중요도 기반 증거 추출 (모델이 지원하는 경우)
                        top_evidence = {}
                        if hasattr(model, 'feature_importances_'):
                             try:
                                 importances = model.feature_importances_
                                 # 현재 윈도우 특징 값 * 중요도
                                 weighted_features = importances * X_live.iloc[0].values
                                 feature_importance = sorted(zip(training_features, weighted_features),
                                                              key=lambda x: abs(x[1]), reverse=True) # 절대값 기준 정렬
                                 # 0이 아닌 상위 3개 특징만 증거로 포함
                                 top_evidence = {f: round(v, 4) for f, v in feature_importance[:3] if v != 0}
                             except Exception as fi_err:
                                  top_evidence = {"error": f"Failed to calculate feature importance: {fi_err}"}


                        alert_context = {
                            "detected_attack_category": prediction,
                            "confidence": f"{confidence:.2%}",
                            "probability_distribution": {label: f"{prob:.2%}" for label, prob in zip(model.classes_, probabilities)},
                            "evidence_features": top_evidence,
                            "model_used": os.path.basename(MODEL_PATH),
                            "window_duration_sec": TIME_WINDOW_SEC,
                            "log_count_in_window": len(current_window_list)
                        }

                        log_bus_event("ai_cti_alert", alert_context)
                        print(f"  🚨 \033[91m[AI-CTI] 위협 탐지! -> '{str(prediction).upper()}' (신뢰도: {alert_context['confidence']})\033[0m")
                        if top_evidence and "error" not in top_evidence :
                            print(f"      - 주요 근거 특징: {json.dumps(top_evidence)}")
                        elif top_evidence:
                             print(f"      - 근거 추출 오류: {top_evidence['error']}")

                    # else: # 정상 예측 또는 신뢰도 미달 시 디버깅 로그 (필요 시)
                    #     print(f"  - [AI-CTI] 예측: '{prediction}' (신뢰도: {confidence:.2%}) - 정상 또는 임계값 미만")

                except Exception as pred_err:
                    print(f"❌ 오류: 모델 예측 실패: {pred_err}", file=sys.stderr)
                    # 입력 데이터 확인 등 디버깅 정보 추가 가능
                    # print("    - Input Features:", X_live.iloc[0].to_dict())

            # 메인 루프 CPU 사용량 조절
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[AI-CTI Agent] 사용자 요청으로 종료합니다...")
    except Exception as main_err:
         print(f"❌ [AI-CTI Agent] 치명적 오류 발생: {main_err}", file=sys.stderr)
    finally:
        print("[AI-CTI Agent] 종료 절차 시작...")
        stop_event.set() # 모든 팔로워 스레드에 종료 신호 전송
        print("   - 로그 팔로워 스레드 종료 대기 중...")
        for thread in log_threads:
             if thread.is_alive():
                  thread.join(timeout=1.0) # 최대 1초 대기
        print("✅ [AI-CTI Agent] 모든 스레드 종료 완료. 에이전트를 종료합니다.")

if __name__ == "__main__":
    main()
