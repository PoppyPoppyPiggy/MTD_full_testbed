#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, time, signal, subprocess, argparse
from datetime import datetime
from pathlib import Path

MON_DIR = Path(__file__).parent.resolve()
LOG_DIR = MON_DIR / "logs" / datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 필요에 따라 인자/환경변수 넘겨주고 싶으면 아래에서 조정
def build_scripts():
    scripts = [
        ("dvd_container_monitor.py", []),
        ("network_traffic_monitor.py",  (["--iface", os.environ["NET_IFACE"]] if os.environ.get("NET_IFACE") else [])),
        ("dvd_telemetry_monitor.py", []),
        ("qos_monitor.py", []),
        ("system_event_monitor.py", []),
    ]
    # 파일이 실제 존재하는 것만 실행 대상에 포함
    return [(n, a) for (n, a) in scripts if (MON_DIR / n).exists()]

def start_proc(name, args):
    out = open(LOG_DIR / f"{name}.out.log", "a", buffering=1)
    err = open(LOG_DIR / f"{name}.err.log", "a", buffering=1)
    cmd = [sys.executable, str(MON_DIR / name)] + args
    env = os.environ.copy()
    p = subprocess.Popen(cmd, cwd=str(MON_DIR), stdout=out, stderr=err, env=env)
    (LOG_DIR / f"{name}.pid").write_text(str(p.pid))
    print(f"[run] {name} (pid={p.pid})  args={args}")
    return p, out, err

def kill_proc(p, name, timeout=5):
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"[force-kill] {name} (pid={p.pid})")
            p.kill()

def main():
    parser = argparse.ArgumentParser(description="Run all monitors concurrently")
    parser.add_argument("--no-restart", action="store_true", help="프로세스 종료 시 재시작하지 않음")
    parser.add_argument("--sleep", type=float, default=2.0, help="헬스체크 주기(초)")
    args = parser.parse_args()

    targets = build_scripts()
    if not targets:
        print("실행할 모니터 스크립트를 찾지 못했습니다.")
        sys.exit(1)

    procs = {}  # name -> (Popen, out_f, err_f)
    stopping = False

    def handle_sig(sig, frame):
        nonlocal stopping
        if not stopping:
            print("\n[shutdown] stopping all monitors...")
            stopping = True

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    # 최초 기동
    for name, a in targets:
        procs[name] = start_proc(name, a)

    # 감시 루프
    while not stopping:
        time.sleep(args.sleep)
        for name in list(procs.keys()):
            p, out_f, err_f = procs[name]
            rc = p.poll()
            if rc is not None:
                out_f.flush(); err_f.flush()
                out_f.close(); err_f.close()
                print(f"[exit] {name} rc={rc}")
                if args.no_restart:
                    del procs[name]
                else:
                    # 재시작
                    procs[name] = start_proc(name, dict(targets)[name])

        if not procs:  # 모두 종료된 경우
            break

    # 종료 시그널 수신 → 모두 정리
    for name, (p, out_f, err_f) in procs.items():
        kill_proc(p, name)
        out_f.close(); err_f.close()
    print("[done] all monitors stopped.")

if __name__ == "__main__":
    main()
