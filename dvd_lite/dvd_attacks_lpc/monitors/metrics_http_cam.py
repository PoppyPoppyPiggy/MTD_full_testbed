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

def http_probe(host, port, path="/", timeout=2.5):
    t0 = time.perf_counter()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(timeout)
    try:
        s.connect((host,int(port)))
        req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: lpc-probe\r\nConnection: close\r\n\r\n"
        s.sendall(req.encode("ascii"))
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk: break
            data += chunk
        t1 = time.perf_counter()
        s.close()
        code = 0
        try:
            first = data.split(b"\r\n",1)[0].decode("ascii","ignore")
            parts = first.split()
            if len(parts)>=2 and parts[1].isdigit(): code = int(parts[1])
        except: pass
        return {"ok": True, "status": code, "rtt_ms": int((t1-t0)*1000), "bytes": len(data)}
    except Exception as e:
        try: s.close()
        except: pass
        return {"ok": False, "err": str(e)}

def log(d): 
    with open(BUS_DVD,"a",encoding="utf-8") as f: f.write(json.dumps(d)+"\n")

def main():
    mode = sys.argv[1] if len(sys.argv)>1 else "once"
    # 우선순위: companion:8080(http_cam) → companion:3000(ui) → simulator:8000(ui)
    pri = [("companion","http_cam",8080), ("companion","ui",3000), ("sim","ui",8000)]
    for role,svc,defp in pri:
        try:
            r = resolve(role, svc)
            host = r.get("ip") or "127.0.0.1"
            port = r.get("port") or defp
            target = (role,svc,host,port)
            break
        except Exception:
            continue
    role,svc,host,port = target
    if mode == "once":
        res = http_probe(host, port, "/")
        log({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "evt":"http_probe", "role":role, "service":svc, "host":host, "port":port, **res})
    else:
        while True:
            res = http_probe(host, port, "/")
            log({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "evt":"http_probe", "role":role, "service":svc, "host":host, "port":port, **res})
            time.sleep(5)

if __name__ == "__main__":
    main()
