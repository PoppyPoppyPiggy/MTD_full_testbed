#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Runner (DVD ⇨ bus.log ⇨ effect_timeline.csv ⇨ NS-3 ⇨ ns3_metrics.csv ⇨ score.json ⇨ dataset.csv ⇨ train)
"""
import os, sys, time, json, random, subprocess, shlex, signal, argparse
from pathlib import Path
try:
  import yaml  # pip install PyYAML
except Exception:
  yaml=None

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "attack_output"
BUS  = OUT / "bus.log"
RULES_DEFAULT = ROOT / "tools" / "effects_rules.json"

def run_cmd(cmd, cwd=ROOT, env=None):
  print("[RUN]", cmd, flush=True)
  return subprocess.run(cmd, cwd=str(cwd), shell=True, env=env or os.environ.copy())

def load_scn(p:Path):
  txt=p.read_text(encoding="utf-8")
  if yaml:
    try: return yaml.safe_load(txt)
    except Exception: pass
  try: return json.loads(txt)
  except: return {}

def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--file","-f", required=True)
  ap.add_argument("--runs", type=int)
  ap.add_argument("--run-ns3", type=int)
  ap.add_argument("--ns3root", default=os.path.expanduser("~/MTD/MTD_full_testbed/ns-3.45/ns-3-dev"))
  args=ap.parse_args()

  scn = load_scn(Path(args.file))
  meta = scn.get("meta",{})
  runs = args.runs if args.runs is not None else int(meta.get("runs", 50))
  run_ns3 = args.run_ns3 if args.run_ns3 is not None else int(meta.get("run_ns3",1))
  sim_time = float(meta.get("sim_time",60))
  atk_rate = float(meta.get("atk_rate_mbps",30))
  cooldown = float(meta.get("cooldown_s",0.2))
  cti_wait = float(meta.get("cti_wait_s",0.5))
  port_prob= int(meta.get("port_hop_prob",50))
  flood_pr = int(meta.get("follow_flood_prob",50))
  rules = str(meta.get("rules", str(RULES_DEFAULT)))

  OUT.mkdir(parents=True, exist_ok=True)
  if not BUS.exists(): BUS.write_text("")

  # kill old watchers
  for pf in (Path("/tmp/cti_ip.pid"), Path("/tmp/cti_sniff.pid")):
    try: os.kill(int(pf.read_text().strip()), 15)
    except: pass
    try: pf.unlink()
    except: pass

  # start watchers
  subprocess.Popen(["bash","-lc","bash cti/cti_watch_ip.sh > attack_output/cti_watch_ip.out 2>&1 & echo $! > /tmp/cti_ip.pid"], cwd=str(ROOT))
  subprocess.Popen(["bash","-lc","sudo -n -E python3 cti/cti_sniff_mavlink.py > attack_output/cti_sniff_port.out 2>&1 & echo $! > /tmp/cti_sniff.pid"], cwd=str(ROOT))

  print(f"[*] runs={runs}", flush=True)
  for i in range(1, runs+1):
    print(f"[*] run {i}/{runs}", flush=True)
    # MTD: IP shuffle
    new_last = 100 + random.randint(0,99)
    run_cmd(f"bash modules/mtd_ip_shuffle.sh CIDR=24 NEW_LAST={new_last} ANNOUNCE_MS=600 DROP_OLD={random.randint(0,1)}")
    time.sleep(cti_wait)

    # port hop
    if random.randint(0,99) < port_prob:
      newp = 20000 + random.randint(0,4999)
      env=os.environ.copy()
      env.update({"OLD_PORT":"14550","NEW_PORT":str(newp),"GRACE":"5","DROP_OLD":"1"})
      if subprocess.call("command -v iptables >/dev/null 2>&1", shell=True)==0:
        run_cmd("bash modules/mtd_port_hop_mavlink.sh", env=env)
      else:
        run_cmd(f"docker exec -d ground-control-station bash -lc 'nohup socat -T0 -u UDP-RECVFROM:{newp},fork,reuseaddr UDP-SENDTO:127.0.0.1:14550 >/dev/null 2>&1 & echo $! > /tmp/mtd_socat_{newp}.pid'")
        with (OUT/"cti_targets.env").open("a") as f: f.write(f"MAVLINK_PORT={newp}\n")
        with BUS.open("a") as f: f.write(f"{int(time.time()*1000)}\tmtd\tmode=REAL actor=defender action=port_hop_socat new={newp} old=14550 target=ground-control-station\n")
      time.sleep(0.01)

    # attack
    if random.randint(0,99) < flood_pr:
      env=os.environ.copy()
      env.update({"DUR":str(4 + random.randint(0,5)),"PKT_SIZE":"250","RATE_PPS":str(800 + random.randint(0,799))})
      run_cmd("bash modules/atk_follow_flood.sh", env=env)
    else:
      env=os.environ.copy()
      env.update({"COUNT":str(100 + random.randint(0,199)),"SLEEP_MS":"5"})
      run_cmd("bash modules/atk_follow_mavlink.sh", env=env)

    time.sleep(cooldown)

  # timeline
  run_cmd(f"python3 tools/gen_effects_timeline.py attack_output/bus.log -o attack_output/effect_timeline.csv --rules {shlex.quote(rules)} --mode hold")

  # ns-3
  if run_ns3:
    ns3cmd = f'./ns3 run "scratch/drone_lpc_eval --timeline=../../dvd_lite/dvd_attacks_lpc/attack_output/effect_timeline.csv --simTime={sim_time} --animMaxPkts=8000000 --atkRateMbps={atk_rate}"'
    run_cmd(ns3cmd, cwd=Path(args.ns3root))

  # score/dataset/train
  run_cmd("python3 tools/score_cti_mtd.py attack_output/bus.log attack_output/effect_timeline.csv --ns3 attack_output/ns3_metrics.csv -o attack_output/score.json")
  run_cmd("python3 tools/make_ml_dataset.py attack_output/bus.log attack_output/effect_timeline.csv --ns3 attack_output/ns3_metrics.csv -o attack_output/dataset.csv")
  run_cmd("python3 tools/train_mtd_policy.py attack_output/dataset.csv")

if __name__=="__main__":
  main()
