#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, time, subprocess, shlex, itertools
try:
    import yaml
except Exception:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml"], check=True)
    import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

def run_bash(cmd: str, check=True, env_prefix:str=""):
    full = f"set -euo pipefail; cd '{BASE}'; source ./00_env_ext.sh; {env_prefix}{cmd}"
    print(f"    [exec] {cmd}")
    return subprocess.run(["bash","-lc", full], check=check)

def popen_bash(cmd: str, env_prefix:str=""):
    full = f"set -euo pipefail; cd '{BASE}'; source ./00_env_ext.sh; {env_prefix}{cmd}"
    print(f"    [spawn] {cmd}")
    return subprocess.Popen(["bash","-lc", full])

def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def df_free_bytes(path):
    try:
        st = os.statvfs(path); return st.f_bavail * st.f_frsize
    except Exception:
        return 0

def pick_artdir(store_cfg:dict):
    primary = os.path.join(BASE, "bus")
    fallback = store_cfg.get("artifacts_dir") or "/tmp/MTD_bus"
    need = int(store_cfg.get("reserve_bytes", 200*1024*1024))  # 200MB
    os.makedirs(primary, exist_ok=True)
    if df_free_bytes(primary) >= need:
        return primary, ""                     # 기본 경로 사용
    os.makedirs(fallback, exist_ok=True)
    return fallback, f"export OUT_DIR='{fallback}'; "  # 폴백

def expand_matrix(vars_dict:dict):
    keys = list(vars_dict.keys())
    vals = [vars_dict[k] for k in keys]
    for combo in itertools.product(*vals):
        yield dict(zip(keys, combo))

def tmpl_replace(obj, envmap):
    def rep(v):
        if isinstance(v,str):
            s=v
            for k,val in envmap.items(): s=s.replace("${%s}"%k, str(val))
            return s
        return v
    if isinstance(obj, dict):  return {k: tmpl_replace(v, envmap) for k,v in obj.items()}
    if isinstance(obj, list):  return [tmpl_replace(v, envmap) for v in obj]
    return rep(obj)

def main():
    if len(sys.argv) < 2:
        print("Usage: run_pipeline.py <pipeline.yml>", file=sys.stderr); sys.exit(2)
    data = load_yaml(sys.argv[1])
    scenario = str(data.get("scenario","scn"))
    desc = data.get("desc","")
    defaults = data.get("defaults",{}) or {}
    steps = data.get("steps",[]) or []
    store = data.get("store",{}) or {}

    role = defaults.get("role","gcs")
    svc  = defaults.get("svc","mavlink")
    sim_time = int(defaults.get("sim_time", 35))
    mtd_state = str(defaults.get("mtd","off"))
    udp_def = defaults.get("udp_probe",{}) or {}

    artdir, env_prefix = pick_artdir(store)
    os.makedirs(os.path.join(artdir,"captures","pcap"), exist_ok=True)

    scn_base = scenario
    scn = f"{scn_base}-{int(time.time())}"
    print(f"[SCENARIO] {scenario}  ({desc})  SCN={scn}  [ARTDIR={artdir}]")

    last_atk, last_lv = "unknown", "low"
    pcap_started = False

    def do_step(step):
        nonlocal scn, last_atk, last_lv, pcap_started, mtd_state, env_prefix
        if "pcap_start" in step:
            run_bash(f"bash modules/probe/probe_pcap.sh start '{scn}' {role} {svc}", env_prefix=env_prefix); pcap_started=True
        elif "pcap_stop" in step:
            run_bash(f"bash modules/probe/probe_pcap.sh stop '{scn}'", env_prefix=env_prefix); pcap_started=False
        elif "udp_probe" in step:
            pr = {**udp_def, **(step["udp_probe"] or {})}; cnt=int(pr.get("count",60)); itv=float(pr.get("interval",0.02))
            run_bash(f"bash modules/probe/probe_udp_fire.sh {role} {svc} --count={cnt} --interval={itv}", env_prefix=env_prefix)
        elif "attack" in step:
            a = step["attack"]; name=a.get("name"); level=a.get("level", defaults.get("atk_level","low"))
            mp=dict(duration_s=a.get("duration_s",12), pps=a.get("pps"), delay_ms=a.get("delay_ms"),
                    loss_pct=a.get("loss_pct"), dup_pct=a.get("dup_pct"))
            envs=[]
            for k,v in mp.items():
                if v is None: continue
                key=dict(duration_s="DURATION_S", delay_ms="DELAY_MS", loss_pct="LOSS_PCT", dup_pct="DUP_PCT").get(k,k.upper())
                envs.append(f"{key}={v}")
            sh=os.path.join(BASE,"modules","attacks",f"{name}.sh"); py=os.path.join(BASE,"modules","attacks",f"{name}.py")
            if os.path.exists(sh):
                cmd=" ".join(envs)+f" bash {sh}"
            elif os.path.exists(py):
                cmd=" ".join(envs)+f" python3 {py}"
            else:
                cmd=" ".join(envs)+f" python3 modules/attacks/lpc_runner.py {shlex.quote(name)} {shlex.quote(str(level))}"
            run_bash(cmd, env_prefix=env_prefix); last_atk, last_lv = name, level
        elif "mtd_apply" in step:
            m = step["mtd_apply"] or {}; args=[]
            for k in ("loss_pct","delay_ms","jitter_ms","dup_pct"):
                if str(m.get(k,""))!="": args.append(f"{dict(loss_pct='LOSS',delay_ms='DELAY',jitter_ms='JITTER',dup_pct='DUP')[k]}={m[k]}")
            run_bash(" ".join(args)+f" bash modules/mtd/mtd_tc_filter.sh apply {role} {svc}", env_prefix=env_prefix); mtd_state="on"
        elif "mtd_revert" in step:
            run_bash(f"bash modules/mtd/mtd_tc_filter.sh revert {role} {svc}", env_prefix=env_prefix); mtd_state="off"
        elif "sleep" in step:
            time.sleep(float(step["sleep"].get("sec",1)))
        elif "gen_effects" in step:
            run_bash(f"python3 tools/gen_effect_timestamp.py bus/bus.log --dvd bus/bus_dvd.log -o bus/effect_timeline_{scn}.csv || true", env_prefix=env_prefix)
            run_bash(f"python3 tools/gen_event_markers.py   bus/bus.log --dvd bus/bus_dvd.log -o bus/events_{scn}.csv          || true", env_prefix=env_prefix)
        elif "ns3_eval" in step:
            SIM_TIME = int(step["ns3_eval"].get("sim_time", sim_time))
            run_bash(f"SIM_TIME={SIM_TIME} bash scripts/ns3_eval.sh '{scn}' '{last_atk}' '{last_lv}' '{mtd_state}'", env_prefix=env_prefix)
        elif "set_env" in step:
            kv = step["set_env"] or {}
            prefix = "".join([f"export {k}='{v}'; " for k,v in kv.items()])
            env_prefix = prefix + env_prefix
        elif "new_scn" in step:
            nm = step["new_scn"].get("name") or scn_base
            scn = f"{nm}-{int(time.time())}"
            print(f"[NEW SCN] {scn}")
        else:
            print(f"[WARN] Unsupported step: {step}")

    for idx, step in enumerate(steps, start=1):
        print(f"[STEP {idx}/{len(steps)}] -> {step}")
        if "repeat" in step:
            rp = step["repeat"]; times=int(rp.get("times",1)); sub=rp.get("steps",[]) or []
            for i in range(times):
                print(f"  [repeat {i+1}/{times}]");  [do_step(s) for s in sub]
            continue
        if "matrix" in step:
            mx = step["matrix"]; vars_dict=mx.get("vars",{}); tmpl=mx.get("template",[]) or []
            for combo in expand_matrix(vars_dict):
                envmap = {k:str(v) for k,v in combo.items()}
                scn = scn_base + "-" + "-".join([f"{k}-{v}" for k,v in envmap.items()]) + f"-{int(time.time())}"
                print(f"  [matrix] {envmap}  -> SCN={scn}")
                for s in tmpl_replace(tmpl, envmap): do_step(s)
            continue
        do_step(step)

    if pcap_started:
        run_bash(f"bash modules/probe/probe_pcap.sh stop '{scn}' || true", env_prefix=env_prefix)

    print(f"\n[DONE] SCN: {scn}")
    print(" - NetAnim:", f"bus/dvd_netanim_{last_atk}_{last_lv}_{mtd_state}_{scn}.xml")
    print(" - Metrics:", f"bus/ns3_metrics_{last_atk}_{last_lv}_{mtd_state}_{scn}.csv")
