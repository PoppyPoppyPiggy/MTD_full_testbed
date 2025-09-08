import csv, json, glob, os, math
# 보상: throughput_mbps - alpha*(delay_ms_avg) - beta*loss_pct  (ns3에 delay/jitter 없음 -> penalty는 적용된 MTD 파라미터로 근사)
alpha=float(os.environ.get("ALPHA",0.0)); beta=float(os.environ.get("BETA",0.1))
# 후보 액션(프로파일)
ACTIONS=[
  {"name":"none", "mtd":"off", "netem":{"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0}},
  {"name":"tc_soft", "mtd":"on", "netem":{"loss_pct":1.0,"delay_ms":2,"jitter_ms":1,"dup_pct":0}},
  {"name":"tc_med",  "mtd":"on", "netem":{"loss_pct":2.5,"delay_ms":5,"jitter_ms":2,"dup_pct":0.5}},
  {"name":"tc_hard", "mtd":"on", "netem":{"loss_pct":5.0,"delay_ms":8,"jitter_ms":3,"dup_pct":1.0}},
]
# impact_report에서 (scn, atk, mtd)별 성능 수집
imp="bus/impact_report.csv"; assert os.path.exists(imp), imp
stats={}
with open(imp) as f:
  R=csv.DictReader(f)
  for r in R:
    atk=r["atk"]; mtd=r["mtd"]; thr=float(r.get("throughput_mbps",0) or 0)
    key=(atk,mtd); stats.setdefault(key,[]).append(thr)
# 각 공격별로 평균 스코어 최대인 액션 선정
policy={}
for atk in {k[0] for k in stats.keys()}:
  best=None; best_score=-1e9
  for a in ACTIONS:
    mtd=a["mtd"]
    thr=sum(stats.get((atk,mtd),[0]))/max(1,len(stats.get((atk,mtd),[0])))
    # penalty 근사(프로파일 자체 비용)
    p = alpha*a["netem"]["delay_ms"] + beta*a["netem"]["loss_pct"]
    score = thr - p/100.0
    if score>best_score:
      best_score=score; best=a
  policy[atk]=best
os.makedirs("bus/models",exist_ok=True)
with open("bus/models/mtd_policy.json","w") as f: json.dump({"policy":policy}, f, indent=2)
print("WROTE bus/models/mtd_policy.json with", len(policy), "attack entries")
