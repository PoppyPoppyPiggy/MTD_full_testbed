#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일명: dvd_lite/dvd_attacks_lpc/monitors/qos_monitor.py
# 설명: MTD 타겟 IP를 추적하여 네트워크 품질(RTT, Loss, Jitter) 측정 (v1.1 - 안정성 강화)

import os
import sys
import time
import json
import datetime
import subprocess
import re
from typing import Tuple # typing.Tuple 대신 사용

# --- 경로 설정 및 유틸리티 임포트 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.dirname(MONITORS_DIR)
BUS_DIR = os.path.join(LPC_DIR, 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_qos.log') # QoS 전용 로그
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')
SOURCE_IP = os.environ.get('MY_IP_ADDRESS', "10.13.0.200") # 공격자 컨테이너 IP
PING_INTERVAL_SEC = 5
PING_COUNT = 5 # 핑 횟수 줄이기 (테스트 환경 고려)
PING_TIMEOUT_SEC = 3 # 전체 핑 타임아웃

# utils 디렉토리를 PYTHONPATH에 추가 (가정)
UTILS_DIR_PATH = os.path.join(LPC_DIR, 'utils')
if UTILS_DIR_PATH not in sys.path:
    sys.path.insert(0, UTILS_DIR_PATH)

# MTD 상태 리더 임포트 시도 및 Fallback
try:
    from utils import mtd_state_reader
    print("[QoS Monitor] MTD 상태 리더 로드 성공.")
except ImportError:
    try:
        from mtd import mtd_state_reader
        print("[QoS Monitor] MTD 상태 리더(mtd) 로드 성공.")
    except ImportError:
        class mtd_state_reader:
            @staticmethod
            def get_current_target(): return None, None
            @staticmethod
            def stop_monitor(): pass
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
        print("!!! 경고: MTD 상태 리더(mtd_state_reader)를 찾을 수 없습니다. !!!", file=sys.stderr)
        print("!!! MTD 타겟 추적 없이 기본 IP(10.13.0.3)로 QoS 측정 시도   !!!", file=sys.stderr)
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)


def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"❌ [QoS Monitor] 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def get_ping_stats(target_ip: str) -> Tuple[float, float, float]:
    """지정된 IP로 ping을 보내 RTT(평균), 패킷 손실, Jitter(mdev)를 반환합니다."""
    # -c: 핑 횟수, -i: 간격(초), -W: 타임아웃(초), -I: 출발지 인터페이스/IP
    # ⭐️ 언어 독립적인 파싱을 위해 노력 (하지만 완벽하진 않음)
    ping_cmd = ["ping", "-c", str(PING_COUNT), "-i", "0.2", "-W", "1", "-I", SOURCE_IP, target_ip]
    try:
        # 언어 설정을 C (POSIX/영어)로 고정하여 출력 형식 일관성 유지 시도
        env = os.environ.copy()
        env['LANG'] = 'C'
        result = subprocess.run(
            ping_cmd,
            capture_output=True, text=True, timeout=PING_TIMEOUT_SEC, env=env,
            errors='ignore' # UTF-8 디코딩 오류 발생 시 무시
        )
        output = result.stdout
        # print(f"--- PING OUTPUT for {target_ip} ---\n{output}\n--------------------------") # 디버깅용

        avg_rtt, mdev_rtt, packet_loss = -1.0, -1.0, 100.0

        # RTT 파싱 (min/avg/max/mdev 또는 round-trip min/avg/max/stddev)
        rtt_match = re.search(r"(?:rtt|round-trip)\s*(?:min/avg/max/(?:mdev|stddev)|avg)\s*=\s*[\d.]+/([\d.]+)/?[\d.]*/?([\d.]+)?", output)
        if rtt_match:
            try:
                avg_rtt = float(rtt_match.group(1))
                # mdev/stddev 값이 있을 경우 jitter로 사용
                if rtt_match.group(2):
                    mdev_rtt = float(rtt_match.group(2))
                else:
                    mdev_rtt = 0.0 # mdev 없으면 0으로 처리 (일부 ping 버전)
            except (ValueError, IndexError):
                print(f"[QoS Monitor] 경고: RTT 파싱 실패 (출력: ...{output[-100:]})")
                avg_rtt, mdev_rtt = -1.0, -1.0

        # 패킷 손실 파싱 (packet loss 또는 Verluste)
        loss_match = re.search(r"(\d+(?:[.,]\d+)?)%\s*(?:packet loss|Paketverlust)", output)
        if loss_match:
            try:
                # 쉼표를 점으로 변환 후 float으로 변환
                packet_loss = float(loss_match.group(1).replace(',', '.'))
            except ValueError:
                 print(f"[QoS Monitor] 경고: 패킷 손실 파싱 실패 (값: {loss_match.group(1)})")
                 packet_loss = 100.0
        elif "100% packet loss" in output or f"{PING_COUNT} packets transmitted, 0 received" in output:
             packet_loss = 100.0
        elif avg_rtt != -1.0: # RTT 정보가 있는데 손실 정보가 없으면 0%로 간주
             packet_loss = 0.0


        # 가끔 mdev가 0인데 avg_rtt가 있는 경우 처리
        if avg_rtt > 0 and mdev_rtt == -1.0:
            mdev_rtt = 0.0

        return avg_rtt, packet_loss, mdev_rtt

    except subprocess.TimeoutExpired:
        print(f"[QoS Monitor] 경고: Ping 타임아웃 ({target_ip})")
        return -1.0, 100.0, -1.0
    except FileNotFoundError:
        print(f"❌ [QoS Monitor] 오류: 'ping' 명령어를 찾을 수 없습니다. iputils-ping 패키지가 설치되었는지 확인하세요.", file=sys.stderr)
        # 이 경우 반복적인 오류를 막기 위해 종료 또는 다른 처리 필요
        sys.exit(1) # 심각한 오류로 간주하고 종료
    except Exception as e:
        print(f"❌ [QoS Monitor] Ping 실행 중 예외 발생 ({target_ip}): {e}", file=sys.stderr)
        return -1.0, 100.0, -1.0

def main():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    print(f"[QoS Monitor] 네트워크 품질 측정 시작 (Source: {SOURCE_IP}) -> {LOG_FILE_PATH}")
    print(f"✅ [QoS Monitor] 현재 공격 라벨: {CURRENT_ATTACK_LABEL}")

    # Fallback IP (mtd_state_reader 실패 시 사용)
    fallback_target_ip = "10.13.0.3"

    while True:
        try:
            target_ip, _ = mtd_state_reader.get_current_target()

            if not target_ip:
                # MTD 리더가 활성화되지 않았거나 타겟 정보가 없는 경우 Fallback IP 사용
                if 'get_current_target' in dir(mtd_state_reader): # mtd_state_reader가 임포트되었는지 확인
                     print("[QoS Monitor] 대기 중: MTD 타겟 정보를 찾을 수 없습니다...")
                     target_ip = None # 명시적으로 None 설정
                else: # Fallback 클래스가 사용 중인 경우
                     print(f"[QoS Monitor] 경고: MTD 리더 비활성. Fallback 타겟({fallback_target_ip})으로 측정 시도.")
                     target_ip = fallback_target_ip

            if target_ip: # 유효한 타겟 IP가 있을 때만 ping 실행
                avg_rtt, packet_loss, jitter = get_ping_stats(target_ip)

                record = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "ts": time.time(),
                    "source": "qos_monitor",
                    "type": "network_qos",
                    "data": {
                        "target_ip": target_ip,
                        "source_ip": SOURCE_IP,
                        "avg_rtt_ms": avg_rtt if avg_rtt != -1.0 else None, # -1은 Null로 기록
                        "packet_loss_pct": packet_loss,
                        "jitter_ms": jitter if jitter != -1.0 else None # -1은 Null로 기록
                    }
                }
                write_jsonl(record)
                status = "OK" if packet_loss < 100 else "FAIL"
                print(f"[QoS Monitor] Target: {target_ip:<15} | RTT: {avg_rtt:6.2f} ms | Loss: {packet_loss:5.1f}% | Jitter: {jitter:6.2f} ms | Status: {status}")
            else:
                 # 타겟 IP가 없는 경우 (MTD 리더는 있지만 정보 못 읽음) 로그 스킵
                 pass

            # 다음 측정까지 대기
            time.sleep(PING_INTERVAL_SEC)

        except KeyboardInterrupt:
            print("\n[QoS Monitor] 사용자 요청으로 모니터링 중지.")
            break
        except Exception as e:
            print(f"❌ [QoS Monitor] 메인 루프 처리 중 예외 발생: {e}", file=sys.stderr)
            time.sleep(5) # 예외 발생 시 잠시 대기 후 재시도

    mtd_state_reader.stop_monitor() # 종료 시 MTD 리더 스레드 정리 요청
    print("[*] QoS 모니터링 종료.")

if __name__ == "__main__":
    main()
