#!/usr/bin/env python3
import argparse, os, sys, time, json, subprocess, threading, uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ENV_MAIN = BASE / "00_env.sh"
ENV_EXT  = BASE / "00_env_ext.sh"
OUT_DIR  = Path(os.environ.get("OUT_DIR", str(BASE / "attack_output")))
BUS_LOG  = Path(os.environ.get("BUS_LOG", str(OUT_DIR / "bus.log")))
BUS_DVD  = Path(os.environ.get("BUS_DVD_LOG", str(OUT_DIR / "bus_dvd.log")))

def sh(cmd, env=None, check=True):
    return subprocess.run(cmd, shell=True, env=env, check=check)

def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def epoch():
    return time.time()

def log_bus(obj):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with BUS_LOG.open("a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def call_attack(module, level, params=None, scenario_id=None, step_id=None, group_id=None, mitre=None, duration_s=None):
    # 시작 로그
    ev_base = dict(ts=now_iso(), t=epoch(), src="attack", evt="attack_start",
                   scenario_id=scenario_id, step_id=step_id, group_id=group_id,
                   attack={"module":module, "level":level, "params":params or {}, "duration_s": duration_s or 0},
                   mitre=mitre or {})
    # 영향 추정(간단 룰: level 스케일)
    scale = {"low":0.5, "med":1.0, "medium":1.0, "high":1.6}.get(level, 1.0)
    impair = {
        "loss_pct": 0.8*scale, "delay_ms": 1.5*scale, "jitter_ms": 1.0*scale,
        "dup_pct": 0.05*scale, "rate_limit_mbps": 0.0,
        "t_apply_s": ev_base["t"], "t_duration_s": duration_s or 5.0
    }
    ev_base["impair"] = impair
    log_bus(ev_base)

    # 실제 공격 모듈 호출(있으면)
    attack_sh = BASE / "modules" / "attacks" / f"{module}.sh"
    if attack_sh.exists():
        env = os.environ.copy()
        env["LEVEL"] = level
        if params: env["ATTACK_PARAMS_JSON"] = json.dumps(params)
        try:
            sh(f"bash '{attack_sh}' '{level}'", env=env, check=False)
        except Exception:
            pass

    # 종료 로그
    log_bus(dict(ts=now_iso(), t=epoch(), src="attack", evt="attack_end",
                 scenario_id=scenario_id, step_id=step_id, group_id=group_id,
                 attack={"module":module, "level":level, "params":params or {}},
                 mitre=mitre or {}))

def call_mtd(action, params=None, scenario_id=None, step_id=None, group_id=None):
    ev = dict(ts=now_iso(), t=epoch(), src="mtd", evt="mtd_action",
              scenario_id=scenario_id, step_id=step_id, group_id=group_id,
              mtd={"action":action, "params":params or {}})
    # MTD 포트 셔플면 impair는 없음(연결 재설정 간헐지연만)
    log_bus(ev)
    # 실제 모듈
    mtd_sh = BASE / "modules" / "mtd" / f"{action}.sh"
    if mtd_sh.exists():
        env = os.environ.copy()
        if params: env["MTD_PARAMS_JSON"] = json.dumps(params)
        try:
            sh(f"bash '{mtd_sh}'", env=env, check=False)
        except Exception:
            pass

def call_probe(kind="dvd_status", scenario_id=None, step_id=None, group_id=None):
    log_bus(dict(ts=now_iso(), t=epoch(), src="probe", evt="probe",
                 scenario_id=scenario_id, step_id=step_id, group_id=group_id))
    probe_sh = BASE / "modules" / "probe" / f"probe_{kind}.sh"
    if probe_sh.exists():
        try:
            sh(f"bash '{probe_sh}'", check=False)
        except Exception:
            pass

def run_wait(seconds):
    time.sleep(float(seconds))

def run_step(step, scenario_id, step_idx, group_id=None):
    stype = step.get("type","attack")
    step_id = step.get("id") or f"step-{step_idx}"
    if stype == "attack":
        call_attack(
            module=step["module"],
            level=step.get("level","med"),
            params=step.get("params"),
            scenario_id=scenario_id, step_id=step_id, group_id=group_id,
            mitre=step.get("mitre"),
            duration_s=step.get("duration_s", 5.0)
        )
    elif stype == "mtd":
        call_mtd(
            action=step["action"],
            params=step.get("params"),
            scenario_id=scenario_id, step_id=step_id, group_id=group_id
        )
    elif stype == "probe":
        call_probe(kind=step.get("kind","dvd_status"),
                   scenario_id=scenario_id, step_id=step_id, group_id=group_id)
    elif stype == "wait":
        run_wait(step.get("seconds", 1.0))
    else:
        log_bus(dict(ts=now_iso(), t=epoch(), src="system", evt="note",
                     scenario_id=scenario_id, step_id=step_id,
                     note=f"unknown step type: {stype}"))

def run_parallel(steps, scenario_id):
    threads = []
    gid = f"grp-{uuid.uuid4().hex[:8]}"
    for i, st in enumerate(steps):
        th = threading.Thread(target=run_step, args=(st, scenario_id, i, gid))
        th.start()
        threads.append(th)
    for th in threads:
        th.join()

def load_yaml(path):
    import yaml
    with open(path,"r",encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pipeline", help="YAML pipeline file")
    args = ap.parse_args()

    pipe = load_yaml(args.pipeline)
    scenario_id = pipe.get("scenario_id") or f"scn-{uuid.uuid4().hex[:8]}"
    stages = pipe.get("stages", [])

    # dvd 내부 감시 데몬이 없으면 기동
    watch = BASE / "monitors" / "dvd_watch.sh"
    if watch.exists():
        try:
            subprocess.run(f"pgrep -f 'monitors/dvd_watch.sh' || (nohup bash '{watch}' >/dev/null 2>&1 &)",
                           shell=True, check=False)
        except Exception:
            pass

    # 실행
    for idx, stage in enumerate(stages):
        mode = stage.get("mode","seq")  # seq | parallel
        steps = stage.get("steps", [])
        if mode == "parallel":
            run_parallel(steps, scenario_id)
        else:
            for i, st in enumerate(steps):
                run_step(st, scenario_id, i)

    print(f"[pipeline] done. scenario_id={scenario_id}  bus={BUS_LOG}  bus_dvd={BUS_DVD}")

if __name__ == "__main__":
    main()
