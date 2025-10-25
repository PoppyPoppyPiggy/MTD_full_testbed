import time
import json
import os
import logging
from datetime import datetime, timezone # timezone 추가
import platform
import threading
import glob # 로그 파일 패턴 매칭용

# Linux 시스템 로그 모니터링을 위한 라이브러리 (선택적)
try:
    import pygtail # 파일의 새로운 라인만 읽기 위함
except ImportError:
    pygtail = None
    logging.warning("pygtail 라이브러리가 설치되지 않았습니다. Linux 시스템 로그 모니터링 기능이 제한될 수 있습니다.")

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 또는 기본값 설정
BUS_LOG_PATH = os.environ.get('BUS_LOG_PATH', './bus.log')
MONITOR_INTERVAL = int(os.environ.get('SYSTEM_EVENT_MONITOR_INTERVAL', 5)) # 초 단위 모니터링 간격
# 모니터링할 로그 파일 경로 (쉼표 구분, 와일드카드(*) 지원)
DEFAULT_LOG_PATHS = '/var/log/syslog,/var/log/auth.log,/var/log/kern.log,/var/log/messages' # Linux 기본값 예시
SYSLOG_PATHS_PATTERN = os.environ.get('SYSTEM_EVENT_LOG_PATHS', DEFAULT_LOG_PATHS)
# 이벤트 감지를 위한 키워드 목록 (소문자로 비교)
EVENT_KEYWORDS = os.environ.get('SYSTEM_EVENT_KEYWORDS', 'error,failed,critical,warning,denied,refused,killed,attack,segfault,oom-killer,firewall,rule,login,authentication,unauthorized').lower().split(',')
MAX_EVENTS_PER_LOG = int(os.environ.get('SYSTEM_EVENT_MAX_EVENTS_PER_LOG', 50)) # 로그 한번에 기록할 최대 이벤트 수

# 운영체제 확인
SYSTEM_OS = platform.system()

# 스레드 종료 플래그
terminate_flag = threading.Event()

# 로그 파일별 마지막 읽은 위치 저장 (pygtail 사용 시 필요)
log_offsets = {}

def log_to_bus(event_type, event_data):
    """시스템 이벤트를 bus 로그 파일에 기록합니다."""
    log_entry = {
        # datetime.utcnow() -> datetime.now(timezone.utc)
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "source": "system_event_monitor",
        "type": f"system_{event_type.lower()}",
        "data": event_data
    }
    try:
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}")

def find_log_files(patterns):
    """쉼표로 구분된 경로 패턴 목록을 받아 실제 파일 경로 리스트를 반환합니다."""
    found_files = set()
    for pattern in patterns.split(','):
        pattern = pattern.strip()
        if not pattern:
            continue
        # glob을 사용하여 와일드카드 확장
        matched_files = glob.glob(pattern)
        if not matched_files:
             logger.debug(f"로그 파일 패턴 '{pattern}'과(와) 일치하는 파일을 찾을 수 없습니다.")
        for f in matched_files:
             # 실제 파일이고 읽기 가능한지 확인 (선택적)
             if os.path.isfile(f) and os.access(f, os.R_OK):
                 found_files.add(os.path.abspath(f))
             else:
                 logger.warning(f"로그 파일 '{f}'에 접근할 수 없거나 파일이 아닙니다.")
    logger.info(f"모니터링 대상 로그 파일: {list(found_files)}")
    return list(found_files)


def monitor_log_files_pygtail(log_files):
    """Linux 시스템 로그 파일에서 pygtail을 사용하여 새로운 라인을 읽어 이벤트를 감지합니다."""
    if not pygtail:
        logger.warning("pygtail이 없어 로그 파일 모니터링을 건너<0xEB><0x9B><0x81>니다.")
        return

    detected_events = []
    for log_path in log_files:
        try:
            logger.debug(f"로그 파일 '{log_path}'에서 새로운 라인 확인 중 (pygtail)...")
            # Pygtail 객체 생성 및 오프셋 파일 지정 (선택적)
            # offset_file = f"./.{os.path.basename(log_path)}.offset" # 예시
            # tailer = pygtail.Pygtail(log_path, read_from_end=True, offset_file=offset_file)

            # 간단하게 인메모리 오프셋 사용 (프로그램 재시작 시 처음부터 읽음)
            # 또는 log_offsets 딕셔너리 사용
            offset_key = log_path
            tailer = pygtail.Pygtail(log_path, read_from_end=not (offset_key in log_offsets), log_file_offset=log_offsets.get(offset_key))


            processed_lines = 0
            for line in tailer:
                processed_lines += 1
                line_lower = line.lower()
                # 정의된 키워드가 포함되어 있는지 확인
                if any(keyword in line_lower for keyword in EVENT_KEYWORDS):
                    event_info = {
                        'log_file': log_path,
                        'message': line.strip(),
                        'detected_keywords': [kw for kw in EVENT_KEYWORDS if kw in line_lower]
                    }
                    logger.info(f"'{log_path}'에서 이벤트 감지: {event_info['message']}")
                    detected_events.append(event_info)

                    # 너무 많은 이벤트를 한번에 기록하지 않도록 제한
                    if len(detected_events) >= MAX_EVENTS_PER_LOG * 5: # 임시 버퍼 크기
                        logger.warning("감지된 이벤트가 너무 많아 일부만 기록될 수 있습니다.")
                        break # 현재 파일 처리 중단하고 다음 파일로

            # 다음 실행을 위해 현재 오프셋 저장
            if hasattr(tailer, 'offset'):
                 log_offsets[offset_key] = tailer.offset
            # logger.debug(f"'{log_path}' 처리 완료 ({processed_lines} 라인 확인). 현재 오프셋: {log_offsets.get(offset_key)}")

        except PermissionError:
            logger.error(f"로그 파일 '{log_path}' 읽기 권한이 없습니다.")
            if log_path in log_offsets: del log_offsets[log_path] # 권한 없으면 오프셋 제거
        except FileNotFoundError:
             logger.warning(f"로그 파일 '{log_path}'가 사라졌습니다.")
             if log_path in log_offsets: del log_offsets[log_path] # 파일 없으면 오프셋 제거
        except Exception as e:
            logger.error(f"로그 파일 '{log_path}' 처리 중 오류 발생: {e}", exc_info=True)
            # 오류 발생 시 해당 파일 오프셋 유지 또는 초기화 고려
            # if log_path in log_offsets: del log_offsets[log_path]


    if detected_events:
        # 이벤트들을 분할하여 로그 기록 (MAX_EVENTS_PER_LOG 단위)
        for i in range(0, len(detected_events), MAX_EVENTS_PER_LOG):
             chunk = detected_events[i:i + MAX_EVENTS_PER_LOG]
             log_to_bus("log_event", chunk)


def monitor_events():
    """운영체제에 맞는 이벤트 모니터링 함수 호출"""
    if SYSTEM_OS == "Linux":
        log_files_to_monitor = find_log_files(SYSLOG_PATHS_PATTERN)
        if log_files_to_monitor:
            monitor_log_files_pygtail(log_files_to_monitor)
        else:
            logger.warning("모니터링할 Linux 로그 파일을 찾지 못했습니다.")
    elif SYSTEM_OS == "Windows":
        # TODO: Windows 이벤트 로그 모니터링 로직 추가 (예: WMI, pywin32, wevtx)
        logger.debug("Windows 이벤트 로그 모니터링은 현재 구현되지 않았습니다.")
        # 예시 (개념):
        # try:
        #    import win32evtlog
        #    # 이벤트 로그 읽기 로직...
        # except ImportError:
        #    logger.warning("Windows 이벤트 로그 모니터링을 위해 'pip install pywin32'가 필요합니다.")
        pass
    elif SYSTEM_OS == "Darwin": # macOS
        # TODO: macOS 시스템 로그 모니터링 로직 추가 (예: /var/log/system.log 파싱, Console API 접근 등)
         logger.debug("macOS 시스템 로그 모니터링은 현재 구현되지 않았습니다.")
         pass
    else:
        logger.warning(f"지원되지 않는 운영체제({SYSTEM_OS})입니다. 이벤트 모니터링이 제한됩니다.")


def main():
    """주기적으로 시스템 이벤트를 모니터링하고 로그를 기록합니다."""
    logger.info("시스템 이벤트 모니터 시작.")
    logger.info(f"모니터링 간격: {MONITOR_INTERVAL}초")
    logger.info(f"로그 파일 패턴: {SYSLOG_PATHS_PATTERN}")
    logger.info(f"감지 키워드: {EVENT_KEYWORDS}")

    while not terminate_flag.is_set():
        start_time = time.time()
        try:
            monitor_events()
        except Exception as e:
             logger.error(f"이벤트 모니터링 중 예외 발생: {e}", exc_info=True)

        # 다음 모니터링까지 대기
        elapsed_time = time.time() - start_time
        sleep_time = max(0, MONITOR_INTERVAL - elapsed_time)
        logger.debug(f"다음 이벤트 확인까지 {sleep_time:.2f}초 대기...")
        terminate_flag.wait(sleep_time) # sleep 대신 wait 사용

    logger.info("시스템 이벤트 모니터 종료.")

if __name__ == "__main__":
    if SYSTEM_OS == "Linux" and not pygtail:
        print("경고: Linux 로그 모니터링을 위해 'pip install pygtail' 명령으로 pygtail 라이브러리를 설치해주세요.")

    try:
        main()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링 중단 신호 수신...")
        terminate_flag.set()
    finally:
        logger.info("프로그램 종료 처리 완료.")


