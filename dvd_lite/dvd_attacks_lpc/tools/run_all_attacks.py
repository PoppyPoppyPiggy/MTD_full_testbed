#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
모듈: dvd_lite/dvd_attacks_lpc/tools/run_all_attacks.py
기능: modules/attacks_wiki 하위의 *.sh 공격 스크립트를 순차 실행하여 동작 검증.
- 각 공격을 지정 시간(duration)만 실행 후 정상 종료 시도(SIGINT), 필요 시 강제 종료.
- 실행 로그를 attack_output/attacks/ 아래에 개별 파일로 저장하고, 요약을 JSONL로 남김.
- BASE/TARGET_EP 환경 변수를 주입 (BASE은 dvd_attacks_lpc, TARGET_EP은 GCS:14550 자동 탐색).
사용:
  sudo -E python3 dvd_lite/dvd_attacks_lpc/tools/run_all_attacks.py --duration 30
옵션:
  --duration SECONDS   각 공격 실행 시간(기본 20초)
  --include "regex"    파일명 포함 필터(여러 번 지정 가능)
  --exclude "regex"    파일명 제외 필터(여러 번 지정 가능)
  --dry-run            실제 실행하지 않고 목록/환경만 출력
"""
import argparse, os, re, shlex, subprocess, sys, threading, time
from pathlib import Path
from datetime import datetime

def detect_base() -> Path:
    # tools/ 의 부모가 dvd_attacks_lpc
    here = Path(__file__).resolve()
    base = here.parents[1]
    return base

def detect_gcs_ip() -> str | None:
    # 1) 컨테이너 이름 직접 조회
    try:
        out = subprocess.run(
            ["docker","inspect","-f","{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}","ground-control-station-lite"],
            text=True, capture_output=True, check=True, timeout=5
        ).stdout.strip()
        if out and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", out): return out
    except Exception:
        pass
    # 2) simulator 네트워크 검사
    try:
        p = subprocess.run(["docker","network","inspect","simulator"], text=True, capture_output=True, check=True, timeout=5)
        import json
        net = json.loads(p.stdout)[0]
        cons = (net.get("Containers") or {}).values()
        for v in cons:
            if (v.get("Name") or "").strip() == "ground-control-station-lite":
                ip = (v.get("IPv4Address") or "").split("/")[0]
                return ip or None
    except Exception:
        pass
    return None

def list_attack_scripts(attack_dir: Path, include, exclude):
    files = sorted([p for p in attack_dir.glob("*.sh") if p.is_file()])
    def ok(name: str):
        for rx in include:
            if not re.search(rx, name): 
                return False
        for rx in exclude:
            if re.search(rx, name):
                return False
        return True
    return [p for p in files if ok(p.name)]

def tee_stream(stream, fp, prefix):
    for line in iter(stream.readline, b""):
        try:
            txt = line.decode(errors="replace")
        except Exception:
            txt = str(line)
        fp.write(f"{prefix}{txt}")
        fp.flush()
        # 콘솔에도 뿌리기
        sys.stdout.write(f"{prefix}{txt}")
        sys.stdout.flush()

def run_one(script: Path, env: dict, out_dir: Path, duration: int) -> dict:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = out_dir / f"{script.stem}.{ts}.log"
    summary = {
        "script": str(script),
        "start": time.time(),
        "duration_sec": duration,
        "env": {"BASE": env.get("BASE"), "TARGET_EP": env.get("TARGET_EP")},
        "status": None,
        "timeout": False,
        "returncode": None,
        "log": str(log_path)
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as fp:
        fp.write(f"# RUN {script.name} at {ts}\n# ENV BASE={env.get('BASE')} TARGET_EP={env.get('TARGET_EP')}\n\n")
        # bash 에서 실행 (실행비트 없어도 됨)
        cmd = ["bash", str(script)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        t = threading.Thread(target=tee_stream, args=(proc.stdout, fp, ""))
        t.daemon = True; t.start()

        # 타임박스
        deadline = time.time() + duration
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.5)
        if proc.poll() is None:
            # 먼저 SIGINT로 정상 종료 유도
            try:
                proc.send_signal(subprocess.signal.SIGINT)
            except Exception:
                pass
            # 3초 기다렸다가 살아있으면 SIGTERM
            for _ in range(6):
                if proc.poll() is not None: break
                time.sleep(0.5)
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            # 그래도 살아있으면 SIGKILL
            for _ in range(6):
                if proc.poll() is not None: break
                time.sleep(0.5)
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            summary["timeout"] = True

        rc = proc.wait()
        try:
            t.join(timeout=1.0)
        except Exception:
            pass
        summary["returncode"] = rc
        summary["status"] = "ok" if (rc == 0 or summary["timeout"]) else "error"
        summary["end"] = time.time()
    return summary

def write_jsonl(path: Path, rec: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=20, help="각 공격 실행 시간(초)")
    ap.add_argument("--include", action="append", default=[], help="파일명 포함 정규식(AND)")
    ap.add_argument("--exclude", action="append", default=[], help="파일명 제외 정규식(OR)")
    ap.add_argument("--dry-run", action="store_true", help="실행하지 않고 목록/환경만 출력")
    args = ap.parse_args()

    base = detect_base()
    attack_dir = base / "modules" / "attacks_wiki"
    out_dir = base / "attack_output" / "attacks"
    sum_path = base / "attack_output" / "attack_runner.jsonl"

    gcs_ip = detect_gcs_ip()
    target_ep = f"{gcs_ip}:14550" if gcs_ip else os.environ.get("TARGET_EP","10.13.0.4:14550")

    scripts = list_attack_scripts(attack_dir, include=args.include or [".*"], exclude=args.exclude or [])
    if not scripts:
        print(f"[!] 실행 대상 없음: {attack_dir}")
        sys.exit(1)

    env = os.environ.copy()
    env["BASE"] = env.get("BASE", str(base))
    env["TARGET_EP"] = target_ep
    env["PYTHONUNBUFFERED"] = "1"

    print(f"[i] BASE={env['BASE']}")
    print(f"[i] TARGET_EP={env['TARGET_EP']}")
    print(f"[i] 대상 스크립트({len(scripts)}):")
    for s in scripts:
        print("   -", s.name)

    if args.dry_run:
        return

    # 루트 권고
    if os.geteuid() != 0:
        print("[!] 권한 주의: 일부 공격/네트워크 조작은 root 권한이 필요할 수 있습니다.", file=sys.stderr)

    for idx, script in enumerate(scripts, 1):
        print(f"\n=== [{idx}/{len(scripts)}] {script.name} 실행({args.duration}s) ===")
        summary = run_one(script, env, out_dir, args.duration)
        write_jsonl(sum_path, summary)
        print(f" -> status={summary['status']} timeout={summary['timeout']} rc={summary['returncode']}")
        print(f" -> log: {summary['log']}")

    print(f"\n[✓] 요약(JSONL): {sum_path}")

if __name__ == "__main__":
    main()
