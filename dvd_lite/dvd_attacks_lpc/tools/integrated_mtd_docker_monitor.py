#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/integrated_mtd_docker_monitor.py
- Docker 상태를 주기采집하여 ENRICH 라인을 bus.log/bus_mtd.log에 기록
- 주기적으로 MTD 스코어를 계산하여 [MTD_SCORING] 라인을 기록하고 JSON/CSV를 export
- 외부 라이브러리 의존 없음(표준 라이브러리+docker CLI)
"""
import argparse, json, logging, shlex, subprocess, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 로컬
from mtd_scoring_calculator import MTDScoringCalculator, MTDMetrics

# ----------------------------- 유틸 -----------------------------
def run(cmd: str) -> str:
    return subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout

def parse_bytes(s: str) -> int:
    # "12.3kB", "45.6MB", "1.2GB", "987B"
    s=s.strip().replace(",","")
    if not s: return 0
    import re
    m=re.match(r"([0-9.]+)\s*([a-zA-Z]*)", s)
    if not m: return 0
    val=float(m.group(1)); unit=m.group(2)
    if unit in ["B",""]: mul=1
    elif unit in ["kB","KB","KiB"]: mul=1024
    elif unit in ["MB","MiB"]: mul=1024**2
    elif unit in ["GB","GiB"]: mul=1024**3
    else: mul=1
    return int(val*mul)

def now_ts_str()->str:
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

# ----------------------------- 모니터 -----------------------------
class DockerSampler:
    def __init__(self, container_filter: List[str]):
        self.filter=container_filter
        self.prev_net: Dict[str, Tuple[int,int]]={}
        self.prev_ip:  Dict[str, str]={}
        self.prev_ports: Dict[str, str]={}
        self.prev_restart: Dict[str, int]={}

    def list_containers(self)->List[str]:
        out=run("docker ps --format {{.Names}}")
        names=[x.strip() for x in out.splitlines() if x.strip()]
        if self.filter:
            names=[n for n in names if n in self.filter]
        return names

    def sample_stats(self, names: List[str]) -> Dict[str, Dict[str,str]]:
        # Name,CPUPerc,MemUsage,NetIO
        out=run("docker stats --no-stream --format {{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}")
        stats={}
        for line in out.splitlines():
            if not line.strip(): continue
            name,cpu,mem,net = [x.strip() for x in line.split(",",3)]
            if names and name not in names: continue
            stats[name]={"cpu":cpu,"mem":mem,"net":net}
        return stats

    def sample_ips(self, names: List[str]) -> Dict[str,str]:
        ips={}
        for n in names:
            ip=run(f"bash -lc \"docker inspect -f '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}} {{{{end}}}}' {shlex.quote(n)}\"").strip()
            ips[n]=ip
        return ips

    def sample_ports(self, names: List[str]) -> Dict[str,str]:
        ports={}
        for n in names:
            p=run(f"docker port {shlex.quote(n)}").strip()
            ports[n]=p
        return ports

    def sample_restarts(self, names: List[str]) -> Dict[str,int]:
        res={}
        for n in names:
            c=run(f"bash -lc \"docker inspect -f '{{{{.RestartCount}}}}' {shlex.quote(n)}\"").strip()
            try: res[n]=int(c)
            except: res[n]=0
        return res

# ----------------------------- 메인 로직 -----------------------------
def main():
    # ATK_DIR 추정
    THIS=Path(__file__).resolve()
    ATK_DIR=THIS.parents[1]
    default_cfg = ATK_DIR / "config" / "integrated_monitor_config.json"
    default_bus = ATK_DIR / "attack_output" / "bus.log"
    out_dir     = ATK_DIR / "attack_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    ap=argparse.ArgumentParser(description="통합 MTD-Docker 모니터")
    ap.add_argument("--config", default=str(default_cfg))
    ap.add_argument("--mode", choices=["no_mtd","mtd"], required=True, help="수집 모드 (버스 로그 분리)")
    ap.add_argument("--duration", type=int, default=60, help="초 단위 총 실행 시간")
    ap.add_argument("--dt", type=float, default=0.5, help="샘플링 간격(sec)")
    ap.add_argument("--score-interval", type=float, default=30.0, help="스코어 계산 주기(sec)")
    ap.add_argument("--bus", default=str(default_bus), help="bus.log 경로(모드별 자동 대체)")
    args=ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger=logging.getLogger("integrated_mtd")

    # 버스 로그 경로 결정
    bus_path=Path(args.bus)
    if args.mode=="mtd":
        bus_path = ATK_DIR / "attack_output" / "bus_mtd.log"
    bus_path.parent.mkdir(parents=True, exist_ok=True)

    # 설정 로드
    cfg={}
    if Path(args.config).exists():
        try:
            cfg=json.loads(Path(args.config).read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f"설정 로드 실패, 기본값 사용: {e}")
    mon_containers = cfg.get("docker_monitoring",{}).get("monitored_containers", [])
    thresholds = cfg.get("docker_monitoring",{}).get("thresholds", {
        "cpu_percent": {"medium": 50.0, "high": 75.0, "critical": 90.0},
        "memory_percent": {"medium": 60.0, "high": 80.0, "critical": 95.0}
    })
    score_export_json = out_dir / f"mtd_scores_{args.mode}.json"
    dashboard_json    = out_dir / f"realtime_dashboard_{args.mode}.json"
    metrics_csv       = out_dir / f"integrated_metrics_{args.mode}.csv"

    # 스코어 엔진 초기화(ATK_DIR 하위 기본 설정)
    scoring_cfg = ATK_DIR / "config" / "mtd_scoring_config.json"
    scorer = MTDScoringCalculator(str(scoring_cfg))

    sampler=DockerSampler(mon_containers)

    # 메트릭 카운터/상태
    counters={
        'ip_changes':0,'port_changes':0,'route_changes':0,
        'network_reconfigs':0,'container_restarts':0,'resource_alerts':0,'filesystem_changes':0
    }
    last_score_time=time.time()
    start=time.time()

    # CSV 헤더 준비
    if not metrics_csv.exists():
        metrics_csv.write_text("timestamp,total_score,grade,diversity,shuffle,redundancy,survivability,energy,ip,port,route,restarts,alerts\n", encoding='utf-8')

    # 루프
    while True:
        now=time.time()
        if now-start > args.duration:
            break
        names=sampler.list_containers()
        stats=sampler.sample_stats(names)

        # 합산 지표
        cpu_sum=0.0; mem_mb_sum=0.0; rx_step=0; tx_step=0
        for n,st in stats.items():
            # CPU
            try: cpu_sum += float(st["cpu"].strip().rstrip("%") or "0")
            except: pass
            # MEM "123.4MiB / 8.0GiB" -> 첫 토큰
            try:
                mem_first=st["mem"].split()[0]
                # GiB/MiB → MB 근사
                if mem_first.endswith("GiB"):
                    val=float(mem_first[:-3]); mem_mb_sum += val*1024
                elif mem_first.endswith("MiB"):
                    val=float(mem_first[:-3]); mem_mb_sum += val
                elif mem_first.endswith("MB"):
                    val=float(mem_first[:-2]); mem_mb_sum += val
                elif mem_first.endswith("kB"):
                    val=float(mem_first[:-2]); mem_mb_sum += val/1024.0
                else:
                    mem_mb_sum += float(mem_first)
            except: pass
            # NET "12.3kB / 45.6kB"
            try:
                parts=st["net"].split("/")
                rx=parse_bytes(parts[0].strip())
                tx=parse_bytes(parts[1].strip())
                prx,ptx = sampler.prev_net.get(n, (rx,tx))
                drx=max(0, rx-prx); dtx=max(0, tx-ptx)
                rx_step += drx; tx_step += dtx
                sampler.prev_net[n]=(rx,tx)
            except: pass

        # IP/포트/네트워크 변화
        ips = sampler.sample_ips(names)
        ports = sampler.sample_ports(names)
        restarts = sampler.sample_restarts(names)

        # 변화 감지
        for n in names:
            # ip change
            prev_ip=sampler.prev_ip.get(n,"")
            if prev_ip and ips.get(n,"") != prev_ip:
                counters['ip_changes'] += 1
                counters['network_reconfigs'] += 1
            sampler.prev_ip[n]=ips.get(n,"")
            # port change (문자열 비교)
            prev_p=sampler.prev_ports.get(n,"")
            if prev_p and ports.get(n,"") != prev_p:
                counters['port_changes'] += 1
            sampler.prev_ports[n]=ports.get(n,"")
            # restart
            prev_r=sampler.prev_restart.get(n,0)
            r=restarts.get(n,0)
            if r>prev_r:
                counters['container_restarts'] += (r-prev_r)
            sampler.prev_restart[n]=r

        # 리소스 경보(간단): 평균 CPU>75% or Mem 합> 특정 MB 등
        if cpu_sum/ max(1,len(stats)) > thresholds["cpu_percent"]["high"]:
            counters['resource_alerts'] += 1

        # ENRICH 라인 기록
        line = f"ENRICH ts={time.time()} mode={args.mode} module=unknown level=unknown cpu_sum={cpu_sum:.3f} mem_mb={mem_mb_sum:.3f} rx_step_b={rx_step} tx_step_b={tx_step} containers={len(stats)}\n"
        with open(bus_path, "a", encoding="utf-8") as f:
            f.write(line)

        # 스코어 계산 주기
        if now - last_score_time >= args.score_interval:
            # 다양성 지표
            total_changes = counters['ip_changes'] + counters['port_changes'] + counters['route_changes']
            # 간이 추정: route_changes = ip/network 변경으로 근사
            counters['route_changes'] = counters['network_reconfigs']

            window_min = max(1.0, args.score_interval/60.0)
            total_containers = max(1, len(names))
            endpoint_diversity = min(1.0, (counters['ip_changes'] + counters['port_changes'] + counters['route_changes']) / (total_containers*3.0))

            # 에너지 비용 근사
            cpu_cost = min(100.0, (cpu_sum/max(1,len(stats))) / 100.0 * 100.0)  # 평균 CPU(%)
            network_overhead = min(100.0, (counters['ip_changes'] + counters['port_changes']) * 2.0)
            battery_consumption = min(100.0, counters['resource_alerts'] * 3.0)
            total_energy_cost = (cpu_cost + network_overhead + battery_consumption)/3.0

            m = MTDMetrics(
                timestamp=datetime.now(),
                ip_changes=counters['ip_changes'],
                port_changes=counters['port_changes'],
                route_changes=counters['route_changes'],
                endpoint_diversity=endpoint_diversity,
                shuffle_frequency= total_changes / window_min,  # 분당
                recovery_time= 10.0 + counters['container_restarts']*5.0,
                shuffle_cost= min(100.0, counters['resource_alerts']*10.0 + total_changes*1.5),
                backup_routes_used= min(10, counters['network_reconfigs']),
                redundancy_ratio= min(1.0, counters['network_reconfigs']/5.0) if counters['network_reconfigs']>0 else 0.5,
                failover_success_rate= 0.9 if counters['network_reconfigs']>0 else 0.8,
                service_uptime= args.score_interval - counters['container_restarts']*3.0,
                mission_continuity= max(0.0, min(1.0, 1.0 - counters['container_restarts']*0.05)),
                attack_resistance= max(0.3, 1.0 - (0.05 * counters['filesystem_changes'])),
                cpu_cost= cpu_cost,
                network_overhead= network_overhead,
                battery_consumption= battery_consumption,
                total_energy_cost= total_energy_cost
            )
            s = scorer.calculate_comprehensive_score(m, time_window_minutes=window_min, total_time_seconds=args.score_interval)

            # 버스 로그 기록
            score_line = (f"{now_ts_str()} [MTD_SCORING] total_score={s.weighted_total:.1f} grade={s.performance_grade} "
                          f"diversity={s.diversity_score:.1f} shuffle={s.shuffle_score:.1f} redundancy={s.redundancy_score:.1f} "
                          f"survivability={s.survivability_score:.1f} energy={s.energy_score:.1f} recommendations_count={len(s.recommendations)}\n")
            with open(bus_path, "a", encoding="utf-8") as f:
                f.write(score_line)

            # 대시보드 JSON
            dash={
                "timestamp": s.timestamp.isoformat(),
                "total": s.weighted_total, "grade": s.performance_grade,
                "components": {"diversity":s.diversity_score,"shuffle":s.shuffle_score,"redundancy":s.redundancy_score,
                               "survivability":s.survivability_score,"energy":s.energy_score},
                "counters": counters, "containers": names
            }
            Path(dashboard_json).write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding='utf-8')

            # 누수 방지: 절반 감쇠
            for k in list(counters.keys()):
                counters[k] = int(counters[k]*0.5)

            last_score_time=now

            # CSV 추적
            with open(metrics_csv, "a", encoding="utf-8") as f:
                f.write(f"{s.timestamp.isoformat()},{s.weighted_total:.2f},{s.performance_grade},"
                        f"{s.diversity_score:.2f},{s.shuffle_score:.2f},{s.redundancy_score:.2f},"
                        f"{s.survivability_score:.2f},{s.energy_score:.2f},"
                        f"{m.ip_changes},{m.port_changes},{m.route_changes},{counters['container_restarts']},{counters['resource_alerts']}\n")

        time.sleep(args.dt)

    # 종료: 점수 JSON 내보내기
    scorer.export_scores(str(score_export_json), "json")
    print(f"[DONE] bus={bus_path} scores_json={score_export_json}")

if __name__=="__main__":
    main()
