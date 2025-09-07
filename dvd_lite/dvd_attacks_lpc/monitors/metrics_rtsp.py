#!/usr/bin/env python3
import os, sys, time, socket, json, subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("OUT_DIR", str(BASE/"bus")))
BUS_DVD = Path(os.environ.get("BUS_DVD_LOG", str(OUT/"bus_dvd.log")))

def sh(cmd): return subprocess.check_output(cmd, shell=True, text=True).strip()

def resolve(role, service):
    r = sh(f"python3 {BASE}/modules/attacks/resolve_target.py {BASE}/modules/attacks/targets/targets.yml {role} {service}")
    return json.loads(r)

def probe_once(host, port, timeout=2.5, read_ms=800):
    t0 = time.perf_counter()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(timeout)
    try:
        s.connect((host, int(port)))
        req = f"DESCRIBE rtsp://{host}:{port}/stream RTSP/1.0\r\nCSeq: 1\r\nAccept: application/sdp\r\n\r\n"
        s.sendall(req.encode("ascii"))
        data = b""
        t1 = time.perf_counter()
        s.settimeout(read_ms/1000.0)
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk: break
                data += chunk
        except Exception:
            pass
        s.close()
        rtt_ms = int((t1 - t0)*1000)
        sdp_len = data.count(b"\r\n") + (len(data))
        return {"ok": True, "rtt_ms": rtt_ms, "bytes": len(data), "sdp_len": sdp_len}
    except Exception as e:
        try: s.close()
        except: pass
        return {"ok": False, "err": str(e)}

def log(line):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(BUS_DVD,"a",encoding="utf-8") as f: f.write(line+"\n")

def main():
    mode = sys.argv[1] if len(sys.argv)>1 else "once"
    tgt = resolve("companion","rtsp")
    host, port = tgt.get("ip") or "127.0.0.1", (tgt.get("port") or 8554)
    if mode == "once":
        r = probe_once(host, port)
        log(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "evt":"rtsp_probe", "target": f"rtsp://{host}:{port}/stream", **r}))
    else:
        while True:
            r = probe_once(host, port)
            log(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "evt":"rtsp_probe", "target": f"rtsp://{host}:{port}/stream", **r}))
            time.sleep(5)

if __name__ == "__main__":
    main()
