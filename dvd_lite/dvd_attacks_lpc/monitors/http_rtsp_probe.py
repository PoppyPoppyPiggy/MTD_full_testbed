#!/usr/bin/env python3
import socket, sys, time, json, os
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("BUS_DVD_LOG", str(BASE/"bus"/"bus_dvd.log")))

def log(j): OUT.parent.mkdir(parents=True, exist_ok=True); OUT.open("a").write(json.dumps(j)+"\n")

def tcp_probe(host, port, payload=b"", timeout=2.0):
    s=socket.socket(); s.settimeout(timeout)
    t0=time.time()
    try:
        s.connect((host,port))
        if payload: s.sendall(payload)
        s.recv(64)
        ok=True; err=""
    except Exception as e:
        ok=False; err=str(e)
    finally:
        rtt=int((time.time()-t0)*1000)
        try: s.close()
        except: pass
    return ok,err,rtt

def main():
    role=sys.argv[1]; host=sys.argv[2]; port=int(sys.argv[3]); kind=sys.argv[4]
    ok, err, rtt = tcp_probe(host, port, b"OPTIONS * HTTP/1.0\r\n\r\n" if kind=="http" else b"OPTIONS rtsp://*/ RTSP/1.0\r\nCSeq: 1\r\n\r\n")
    log({"ts":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "evt":f"{kind}_probe", "role":role, "host":host, "port":port, "ok":ok, "rtt_ms":rtt, "err":err})
if __name__=="__main__": main()
