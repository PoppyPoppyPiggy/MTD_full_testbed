#!/usr/bin/env python3
import os, sys, json, subprocess, re, yaml

def sh(cmd): return subprocess.check_output(cmd, shell=True, text=True).strip()
def docker_inspect_ip(container):
    if not container: return ""
    try:
        out = sh(f"docker inspect -f '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {container}")
        return (out.split() or [""])[0]
    except Exception: return ""
def docker_network_subnet(net):
    if not net: return ""
    try:
        j = json.loads(sh(f"docker network inspect {net}"))[0]
        return j["IPAM"]["Config"][0]["Subnet"]
    except Exception: return ""
def first_network_of(container):
    try:
        nets = json.loads(sh(f"docker inspect -f '{{{{json .NetworkSettings.Networks}}}}' {container}"))
        return list(nets.keys())[0] if nets else ""
    except Exception: return ""
def guess_container(role):
    names = sh("docker ps --format '{{.Names}}'").lower().splitlines()
    patt = {
        "gcs":[r"ground[-]?control",r"\bgcs\b",r"ground-control-station",r"gcs.*lite",r"ground.*lite"],
        "companion":[r"companion",r"companion.*lite"],
        "flight":[r"flight[-_]?controller",r"\bfc\b",r"flight.*lite"],
        "sim":[r"simulator",r"\bsim\b",r"simulator.*lite"]
    }.get(role,[])
    for p in patt:
        for n in names:
            if re.search(p,n): return n
    return ""

# ${VAR:-default} 확장 + ${VAR} 확장
def expand_with_default(s: str) -> str:
    def repl(m):
        var, default = m.group(1), m.group(2)
        return os.environ.get(var, default or "")
    s = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)[:-]([^}]*)\}", repl, s)
    return os.path.expandvars(s)

def load_targets(yml_path):
    raw = open(yml_path, "r", encoding="utf-8").read()
    return yaml.safe_load(expand_with_default(raw))

def main():
    if len(sys.argv) < 3:
        print("usage: resolve_target.py <targets.yml> <role> [service]"); sys.exit(2)
    ypath, role = sys.argv[1], sys.argv[2]; service = sys.argv[3] if len(sys.argv)>3 else None
    cfg = load_targets(ypath)

    net = cfg.get("docker_network","")
    rolecfg = (cfg.get("roles") or {}).get(role, {})
    container = rolecfg.get("container","")

    # 컨테이너 자동 추정
    if not docker_inspect_ip(container):
        alt = guess_container(role)
        if alt: container = alt
    ip = docker_inspect_ip(container)

    # 네트워크/서브넷 보강
    if not net: net = first_network_of(container)
    subnet = cfg.get("subnet") or docker_network_subnet(net)

    res = {"role":role,"container":container,"ip":ip,"network":net,"subnet":subnet,"services":rolecfg.get("services",{})}
    if service:
        port = (rolecfg.get("services") or {}).get(service)
        if port is not None: res["port"] = int(str(port))
    print(json.dumps(res))

if __name__ == "__main__": main()
