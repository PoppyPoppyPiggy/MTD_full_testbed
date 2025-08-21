#!/usr/bin/env python3
"""
ns3_window_fallback.py - 안전한 버전 (빈 데이터 처리)
"""
import sys, csv, argparse
import numpy as np

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline_csv", help="타임라인 CSV 파일")
    ap.add_argument("-o", "--out", required=True, help="출력 NS-3 메트릭스 파일")
    ap.add_argument("--simTime", type=int, default=60, help="시뮬레이션 시간")
    args = ap.parse_args()

    # 타임라인 로드
    t = []
    try:
        with open(args.timeline_csv, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    t.append(float(row.get('t', 0)))
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        print(f"타임라인 로드 오류: {e}", file=sys.stderr)

    # 빈 배열 처리
    if not t:
        print("타임라인이 비어있음, 기본 시간 범위 사용", file=sys.stderr)
        import time
        current_time = int(time.time())
        t0, t1 = current_time, current_time + args.simTime
    else:
        t = np.array(t)
        t0, t1 = float(np.min(t)), float(np.max(t))
    
    # 시뮬레이션 시간 조정
    duration = max(args.simTime, int(t1 - t0) + 5)
    
    # 합성 NS-3 메트릭스 생성
    with open(args.out, 'w') as f:
        f.write("t,rxPackets,throughput_mbps\n")
        
        # per-bin 데이터 (1초 간격)
        for i in range(1, duration + 1):
            # 간단한 시뮬레이션: 시간에 따른 변화
            base_throughput = 45.0 + 5.0 * np.sin(i * 0.1)  # 40-50 Mbps 범위
            noise = np.random.normal(0, 2)  # 노이즈 추가
            throughput = max(0, base_throughput + noise)
            
            packets = int(throughput * 1000 / 8 / 512)  # 대략적인 패킷 수
            
            f.write(f"{i},{packets},{throughput:.2f}\n")
    
    print(f"합성 NS-3 메트릭스 생성: {args.out} ({duration} lines)")

if __name__ == "__main__":
    main()