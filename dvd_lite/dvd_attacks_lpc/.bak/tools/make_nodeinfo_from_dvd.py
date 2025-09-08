#!/usr/bin/env python3
import json, subprocess, sys, os

# 기대 컨테이너명과 역할(표시 순서 고정: GCS, CC, FC, SIM, ATTACKER)
ROLES = [
  ("ground-control-station-lite","GCS"),
  ("companion-computer-lite","CC"),
  ("flight-controller-lite","FC"),
  ("simulator-lite","SIM"),
  # 공격자는 실제 도커 컨테이너일 수도/아닐 수도 있으므로 자리만 둠
]

NETWORK = os.environ.get("DVD_DOCKER_NET","simulator")

def docker_out(args):
  try: return subprocess.check_output(args, text=True).strip()
  except Exception: return ""

def ip_of(name):
  j = docker_out(["bash","-lc", f"docker inspect {name} --format '{{{{json .NetworkSettings.Networks}}}}'"])
  if not j: return ""
  try:
    nets = json.loads(j)
    if NETWORK in nets: return nets[NETWORK].get("IPAddress","")
    # 네트워크 이름이 다르면 첫 항목 임의 선택
    for k,v in nets.items():
      if v.get("IPAddress"): return v["IPAddress"]
  except Exception:
    pass
  return ""

nodes=[]
for idx,(cname,role) in enumerate(ROLES):
  ip = ip_of(cname)
  nodes.append({"order":idx,"role":role,"container":cname,"ip":ip})

# ATTACKER는 가상 노드로 추가
nodes.append({"order":4,"role":"ATTACKER","container":None,"ip":""})

# 기본 좌표(원하시면 여기 바꾸면 됨)
pos = {
  "GCS":[20.0,20.0], "CC":[60.0,40.0], "FC":[60.0,0.0],
  "SIM":[100.0,20.0], "ATTACKER":[0.0,60.0]
}

# labels / posCSV 생성
labels = ",".join([n["role"] for n in sorted(nodes,key=lambda x:x["order"])])
posCSV = ";".join([f"{pos[n['role']][0]}:{pos[n['role']][1]}" for n in sorted(nodes,key=lambda x:x["order"])])

nodeinfo = {
  "network": NETWORK,
  "nodes": nodes,
  "labels": labels,
  "posCSV": posCSV,
  "links":[
    {"from":"FC","to":"GCS","label":"MAVLink/UDP:14550"},
    {"from":"ATTACKER","to":"GCS","label":"ATTACK"}
  ]
}

os.makedirs("bus", exist_ok=True)
with open("bus/nodeinfo.json","w") as f: json.dump(nodeinfo,f,indent=2)
print("Wrote bus/nodeinfo.json")
