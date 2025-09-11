import socket, time, json, sys
from pathlib import Path

def udp_check(ip: str, port: int, timeout=1.0) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(b"\xFE\x09\x00\x00", (ip, port))  # dummy
        return True
    except Exception:
        return False
    finally:
        try: s.close()
        except: pass

def write_bus_dvd(log_path: str, record: dict):
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def probe_all(gcs_ep: str, bus_dvd="results/bus_dvd.log") -> bool:
    ip, port = gcs_ep.split(":")
    ok = udp_check(ip, int(port))
    write_bus_dvd(bus_dvd, {"ts": time.time(), "type":"probe", "udp_check":ok, "target":gcs_ep})
    return ok

if __name__ == "__main__":
    ep = sys.argv[1] if len(sys.argv)>1 else "10.13.0.4:14550"
    print("OK" if probe_all(ep) else "FAIL")
