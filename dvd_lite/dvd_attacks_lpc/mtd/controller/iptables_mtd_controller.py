#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json, time, yaml, random, subprocess, pathlib, datetime as dt
from typing import Dict, Any, List, Tuple

BASE = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load(open(BASE / "configs" / "iptables_mtd.yaml"))
RL_JSON = BASE.parent / "ml" / "output" / "mtd_policy_params.json"  # 안전장치
RL_JSON = pathlib.Path(CFG.get("rl_output_path", RL_JSON))
STATE_FILE = pathlib.Path(CFG.get("state_file"))
BUS_SOURCE = CFG.get("bus_source", "iptables_mtd")
MODE = CFG.get("mode", "nodeport")
PROTO = CFG.get("protocol", "udp")
PUB_PORT = int(CFG.get("public_port", 14550))
BR_IF = CFG.get("bridge_if", "")

REAL_TARGETS: List[str] = list(CFG["real_targets"])
DECOY_TARGET: str = CFG["decoy_target"]
CONNTRACK_KICK = bool(CFG.get("conntrack_drop_on_switch", True))

# --- 버스 로깅 (없어도 stdout으로 fallback)
try:
    sys.path.insert(0, str(BASE.parent))
    from bus.logger import log_bus_event
except Exception:
    def log_bus_event(t, d, source_override=BUS_SOURCE):
        rec = {"ts": time.time(), "source": source_override, "type": t, "data": d}
        print(json.dumps(rec, ensure_ascii=False))

def sh(*args, **kw):
    kw.setdefault("check", True)
    return subprocess.run(args, **kw)

def _write_state(active: str):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"active": active, "ts": time.time()}, indent=2))

def _read_rl() -> Dict[str, float]:
    # RL이 주는 정책값 (없으면 기본)
    if RL_JSON.exists():
        try:
            d = json.loads(RL_JSON.read_text())
            return {
                "ip_cd": float(d.get("ip_cd_mean", 30.0)),
                "decoy_ratio": float(d.get("decoy_ratio_mean", 0.1)),
                "bl_level": float(d.get("bl_level_mean", 1.0)),
            }
        except Exception as e:
            log_bus_event("mtd_warning", {"msg":"RL JSON parse fail", "err": str(e)})
    return {"ip_cd": 30.0, "decoy_ratio": 0.1, "bl_level": 1.0}

def _pick_backend(prev: str) -> str:
    candidates = [t for t in REAL_TARGETS if t != prev] or REAL_TARGETS
    return random.choice(candidates)

def init_tables():
    env = os.environ.copy()
    env.update({
        "BACKEND": os.environ.get("BACKEND", ""),   # auto
        "MODE": MODE,
        "PROTO": PROTO,
        "PUB_PORT": str(PUB_PORT),
        "BR_IF": BR_IF,
    })
    sh(str(BASE / "scripts" / "mtd_nat.sh"), "init", env=env)
    log_bus_event("mtd_init", {"mode": MODE, "proto": PROTO, "port": PUB_PORT, "bridge": BR_IF})

def swap_to(new_ipport: str, old_ipport: str = ""):
    env = os.environ.copy()
    env.update({
        "CONNTRACK_KICK": "1" if CONNTRACK_KICK else "0",
        "PROTO": PROTO,
        "PUB_PORT": str(PUB_PORT),
    })
    args = [str(BASE / "scripts" / "mtd_nat.sh"), "swap", new_ipport]
    if old_ipport: args.append(old_ipport)
    sh(*args, env=env)
    _write_state(new_ipport)
    log_bus_event("mtd_switch", {
        "from": old_ipport or None, "to": new_ipport,
        "mode": MODE, "proto": PROTO, "port": PUB_PORT
    })

def main():
    init_tables()

    # 최초 활성 선정
    active = None
    if STATE_FILE.exists():
        try:
            active = json.loads(STATE_FILE.read_text()).get("active")
        except: pass
    if not active:
        active = _pick_backend(prev="")
        swap_to(active, "")

    last_switch = time.time()
    while True:
        try:
            pol = _read_rl()
            ip_cd = max(5.0, min(60.0, pol["ip_cd"]))
            decoy_ratio = max(0.0, min(0.5, pol["decoy_ratio"]))

            now = time.time()
            # 1) 주기적 스위치
            if now - last_switch >= ip_cd:
                old = active
                # decoy 전개(확률) vs 정상 백엔드 교체
                if random.random() < decoy_ratio:
                    # 디코이를 임시 활성으로 걸어 공격자 유도
                    new = DECOY_TARGET
                else:
                    new = _pick_backend(prev=old)
                swap_to(new, old)
                active = new
                last_switch = now

            # 2) (선택) 공격자 블랙리스트(bl_level)에 따라 추가 조치 가능 지점
            #    - 여기서는 예시로 로그만 남김. 실제로는 ipset:blocked_src + DOCKER-USER 체인에 DROP 등 수행.
            log_bus_event("mtd_policy_tick", {
                "ip_cd": ip_cd, "decoy_ratio": decoy_ratio, "bl_level": pol["bl_level"],
                "active": active
            })
            time.sleep(1.0)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log_bus_event("mtd_error", {"msg":"controller_loop", "err": str(e)})
            time.sleep(2.0)

if __name__ == "__main__":
    main()
