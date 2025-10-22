# 파일 경로: dvd_lite/dvd_attacks_lpc/utils/mtd_state_reader.py
# 설명: 모든 모니터가 MTD 상태 파일의 변경을 실시간으로 감지하고 공유하기 위한 중앙 집중식 유틸리티입니다.

import json
import os
import threading
import time
import sys
from typing import Dict, Optional, Tuple

# --- 경로 설정 ---
# 이 파일은 utils 폴더 안에 위치한다고 가정합니다.
UTILS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.dirname(UTILS_DIR)
SHARED_STATE_FILE = os.path.join(LPC_DIR, 'mtd', 'shared_state', 'mtd_state.json')

# --- 전역 변수 및 Lock ---
# 최신 MTD 상태를 메모리에 캐싱하여 파일 I/O를 최소화합니다.
_current_state: Dict[str, any] = {}
_state_lock = threading.Lock()
_stop_event = threading.Event()

def _read_state_from_file() -> Dict:
    """파일에서 직접 MTD 상태를 읽습니다."""
    try:
        with open(SHARED_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 파일이 없거나 비어있는 경우, 빈 딕셔너리 반환
        return {}

def _state_monitor_thread():
    """백그라운드에서 mtd_state.json 파일의 변경을 주기적으로 감지하고 캐시를 업데이트합니다."""
    global _current_state
    print("[MTD State Reader] MTD 상태 파일 모니터링 시작...")
    
    last_mod_time = 0
    while not _stop_event.is_set():
        try:
            # 파일 존재 여부 먼저 확인
            if not os.path.exists(SHARED_STATE_FILE):
                time.sleep(1)
                continue

            current_mod_time = os.path.getmtime(SHARED_STATE_FILE)
            if current_mod_time > last_mod_time:
                new_state = _read_state_from_file()
                with _state_lock:
                    # 상태가 실제로 변경되었을 때만 로그 출력
                    if _current_state.get("current_target") != new_state.get("current_target"):
                        print(f"[MTD State Reader] ⭐️ 상태 변경 감지! 새 타겟: {new_state.get('current_target', 'N/A')}")
                    _current_state = new_state
                last_mod_time = current_mod_time
        except FileNotFoundError:
            # 파일이 검사 도중 삭제될 경우를 대비
            pass
        except Exception as e:
            print(f"[MTD State Reader] 오류 발생: {e}", file=sys.stderr)
            
        time.sleep(1) # 1초마다 변경 확인

def get_current_target() -> Optional[Tuple[str, int]]:
    """캐시된 MTD 상태에서 현재 타겟 IP와 포트를 반환합니다."""
    with _state_lock:
        target_str = _current_state.get("current_target")
    
    if target_str and ":" in target_str:
        try:
            ip, port_str = target_str.split(":", 1)
            return ip, int(port_str)
        except (ValueError, IndexError):
            return None, None
    return None, None

def get_full_state() -> Dict:
    """캐시된 전체 MTD 상태 정보를 반환합니다."""
    with _state_lock:
        return _current_state.copy()

# --- 스레드 초기화 ---
# 이 모듈이 임포트될 때 백그라운드 스레드가 자동으로 시작됩니다.
_monitor_thread = threading.Thread(target=_state_monitor_thread, daemon=True)
_monitor_thread.start()

# 애플리케이션 종료 시 스레드를 정리하기 위한 함수
def stop_monitor():
    """모니터링 스레드를 안전하게 종료합니다."""
    print("[MTD State Reader] 모니터링 스레드 종료 요청...")
    _stop_event.set()

