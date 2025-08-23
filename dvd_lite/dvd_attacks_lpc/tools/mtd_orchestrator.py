#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E 오케스트레이터: DVD → LPC 타임라인 → ns-3 → (옵션) 집계
환경변수:
  MTD_ROOT=/home/kali/MTD/MTD_full_testbed
  MTD_OUT=$MTD_ROOT/dvd_lite/dvd_attacks_lpc/attack_output
  MTD_NS3=$MTD_ROOT/ns-3.45/ns-3-dev
"""
import os, subprocess, pathlib, time, sys, json
from datetime import datetime
import typer

app = typer.Typer(add_completion=False)

def sh(cmd, cwd=None):
    print(f">> {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd)
    if res.returncode != 0:
        raise SystemExit(res.returncode)

def env_paths():
    root = os.environ.get("MTD_ROOT", str(pathlib.Path(__file__).resolve().parents[1]))
    out  = os.environ.get("MTD_OUT", f"{root}/dvd_lite/dvd_attacks_lpc/attack_output")
    ns3  = os.environ.get("MTD_NS3", f"{root}/ns-3.45/ns-3-dev")
    return root, out, ns3

@app.command()
def e2e(profile: str = "lpc_multi",
        rules: str = "tools/effects_rules.json",
        sim_time: int = 60,
        pkt_size: int = 512,
        run_id: str = ""):
    """
    한방 실행:
    1) DVD 공격→bus.log
    2) bus.log→effect_timeline.csv
    3) ns-3 실행→ns3_metrics.csv, netanim.xml
    4) (옵션) 집계 실행
    """
    root, out, ns3 = env_paths()
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 결과 버전 폴더
    run_dir = os.path.join(out, run_id)
    os.makedirs(run_dir, exist_ok=True)
    bus_log = os.path.join(run_dir, "bus.log")
    timeline = os.path.join(run_dir, "effect_timeline.csv")

    dvd_dir = f"{root}/Damn-Vulnerable-Drone/dvd_lite/dvd_attacks_lpc"
    # 1) DVD (파이썬 런처 우선, 실패 시 bash 시나리오)
    try:
        sh(f"python3 interface/lpc_state_engine.py --profile {profile} --out {bus_log}", cwd=dvd_dir)
    except SystemExit:
        sh(f"bash scripts/scenario_lpc_multi.sh", cwd=dvd_dir)
        # 기본 시나리오가 attack_output/bus.log에 쌓는다면 복사
        default_bus = os.path.join(out, "bus.log")
        if os.path.exists(default_bus):
            sh(f"cp -f {default_bus} {bus_log}")

    # 2) 로그→타임라인
    sh(f"python3 tools/gen_effects_timeline.py {bus_log} -o {timeline} --rules {rules}", cwd=dvd_dir)

    # 3) ns-3
    # ns-3 출력(ns3_metrics.csv, netanim.xml)을 run_dir로 내보내도록 환경변수 전달
    env = os.environ.copy()
    env["NS3_OUT_DIR"] = run_dir
    cmd = f'./ns3 run "scratch/drone_lpc_eval --timeline={timeline} --simTime={sim_time} --pktSize={pkt_size}"'
    print(f">> {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=ns3, env=env)
    if res.returncode != 0:
        raise SystemExit(res.returncode)

    # 4) 집계(옵션) - run_dir 하나만
    agg = f"{root}/tools/mtd_eval_aggregate.py"
    if os.path.exists(agg):
        sh(f"python3 {agg} --inputs {run_dir} --out {os.path.join(run_dir, 'eval_summary.csv')}")

    print(f"[OK] E2E done: {run_dir}")

if __name__ == "__main__":
    app()
