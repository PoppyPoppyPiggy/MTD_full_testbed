#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/mtd_scoring_calculator.py - MTD 성능 지표 스코링 계산 툴 (numpy 의존 제거 버전)
- 기본 설정 경로: ${ATK_DIR}/config/mtd_scoring_config.json
- 출력을 attack_output/ 하위에 저장하도록 상위에서 경로 지정 권장
"""
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Any, Optional

# ----------------------------- 데이터 모델 -----------------------------
@dataclass
class MTDMetrics:
    timestamp: datetime
    # DIVERSITY
    ip_changes: int = 0
    port_changes: int = 0
    route_changes: int = 0
    endpoint_diversity: float = 0.0
    # SHUFFLE
    shuffle_frequency: float = 0.0
    recovery_time: float = 0.0
    shuffle_cost: float = 0.0
    # REDUNDANCY
    backup_routes_used: int = 0
    redundancy_ratio: float = 0.0
    failover_success_rate: float = 0.0
    # SURVIVABILITY
    service_uptime: float = 0.0
    mission_continuity: float = 0.0
    attack_resistance: float = 0.0
    # ENERGY
    cpu_cost: float = 0.0
    network_overhead: float = 0.0
    battery_consumption: float = 0.0
    total_energy_cost: float = 0.0

@dataclass
class MTDScore:
    timestamp: datetime
    diversity_score: float = 0.0
    shuffle_score: float = 0.0
    redundancy_score: float = 0.0
    survivability_score: float = 0.0
    energy_score: float = 0.0
    weighted_total: float = 0.0
    performance_grade: str = "F"
    recommendations: List[str] = None
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []

# ----------------------------- 스코어 엔진 -----------------------------
class MTDScoringCalculator:
    def __init__(self, config_path: str):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.weights = self.config.get('weights', {
            'diversity': 0.25, 'shuffle': 0.20,
            'redundancy': 0.20, 'survivability': 0.25, 'energy': 0.10
        })
        self.thresholds = self.config.get('thresholds', {
            'diversity': {'excellent': 80, 'good': 60, 'fair': 40, 'poor': 20},
            'shuffle': {'excellent': 85, 'good': 70, 'fair': 50, 'poor': 30},
            'redundancy': {'excellent': 90, 'good': 75, 'fair': 55, 'poor': 35},
            'survivability': {'excellent': 95, 'good': 85, 'fair': 70, 'poor': 50},
            'energy': {'excellent': 20, 'good': 40, 'fair': 60, 'poor': 80}
        })
        self.baseline_metrics = self.config.get('baseline', {
            'max_ip_changes_per_min': 10,
            'max_port_changes_per_min': 15,
            'max_route_changes_per_min': 5,
            'target_shuffle_frequency': 2.0,
            'max_recovery_time': 30.0,
            'max_shuffle_cost': 100.0,
            'target_redundancy_ratio': 0.8,
            'target_survivability': 0.95,
            'max_cpu_cost_percent': 20.0,
            'max_network_overhead_percent': 15.0,
            'max_battery_cost_percent': 10.0
        })
        self.metrics_history: List[MTDMetrics] = []
        self.scores_history: List[MTDScore] = []
        self._last_effectiveness: float = 0.0  # 효율 보너스 계산용

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            p = Path(config_path)
            if p.exists():
                return json.loads(p.read_text(encoding='utf-8'))
            logging.getLogger(__name__).warning(f"설정 파일 {p} 없음. 기본값 사용.")
            return {}
        except Exception as e:
            logging.getLogger(__name__).error(f"설정 파일 로드 실패: {e}")
            return {}

    # -------- component scores --------
    def calculate_diversity_score(self, metrics: MTDMetrics, time_window_minutes: float = 5.0) -> float:
        base = self.baseline_metrics
        ip_per_min    = metrics.ip_changes    / max(1e-9, time_window_minutes)
        port_per_min  = metrics.port_changes  / max(1e-9, time_window_minutes)
        route_per_min = metrics.route_changes / max(1e-9, time_window_minutes)

        ip_score    = min(100.0, ip_per_min    / base['max_ip_changes_per_min']   * 100.0)
        port_score  = min(100.0, port_per_min  / base['max_port_changes_per_min'] * 100.0)
        route_score = min(100.0, route_per_min / base['max_route_changes_per_min']* 100.0)
        endp_score  = min(100.0, metrics.endpoint_diversity * 100.0)
        return ip_score*0.4 + port_score*0.3 + route_score*0.2 + endp_score*0.1

    def calculate_shuffle_score(self, metrics: MTDMetrics) -> float:
        base = self.baseline_metrics
        target = base['target_shuffle_frequency']
        freq_score = max(0.0, 100.0 - abs(metrics.shuffle_frequency - target)/max(1e-9, target) * 100.0)
        rec_score  = max(0.0, 100.0 - metrics.recovery_time/max(1e-9, base['max_recovery_time'])*100.0)
        cost_score = max(0.0, 100.0 - metrics.shuffle_cost/max(1e-9, base['max_shuffle_cost'])*100.0)
        eff_score  = min(100.0, (metrics.shuffle_frequency/max(1e-9, metrics.shuffle_cost))*50.0) if metrics.shuffle_cost>0 else 100.0
        return freq_score*0.30 + rec_score*0.35 + cost_score*0.25 + eff_score*0.10

    def calculate_redundancy_score(self, metrics: MTDMetrics) -> float:
        red = min(100.0, metrics.redundancy_ratio*100.0)
        fail= min(100.0, metrics.failover_success_rate*100.0)
        use = min(100.0, metrics.backup_routes_used*20.0) if metrics.backup_routes_used>0 else 0.0
        return red*0.50 + fail*0.40 + use*0.10

    def calculate_survivability_score(self, metrics: MTDMetrics, total_time_seconds: float = 300.0) -> float:
        up_ratio = min(1.0, metrics.service_uptime/max(1e-9, total_time_seconds))
        up_score = up_ratio*100.0
        cont_score = min(100.0, metrics.mission_continuity*100.0)
        res_score  = min(100.0, metrics.attack_resistance*100.0)
        if up_ratio>=0.99: q=100.0
        elif up_ratio>=0.90: q=50.0 + (up_ratio-0.90)/0.09*50.0
        else: q=max(0.0, up_ratio/0.90*50.0)
        return up_score*0.40 + cont_score*0.30 + res_score*0.20 + q*0.10

    def calculate_energy_score(self, metrics: MTDMetrics) -> float:
        base = self.baseline_metrics
        cpu = max(0.0, 100.0 - metrics.cpu_cost / max(1e-9, base['max_cpu_cost_percent']) * 100.0)
        net = max(0.0, 100.0 - metrics.network_overhead / max(1e-9, base['max_network_overhead_percent']) * 100.0)
        bat = max(0.0, 100.0 - metrics.battery_consumption / max(1e-9, base['max_battery_cost_percent']) * 100.0)
        tot = max(0.0, 100.0 - (metrics.cpu_cost + metrics.network_overhead + metrics.battery_consumption)/3.0)
        bonus = 0.0
        if metrics.total_energy_cost>0 and self._last_effectiveness>0:
            bonus = min(20.0, (self._last_effectiveness/metrics.total_energy_cost)*10.0)
        return min(100.0, cpu*0.35 + net*0.25 + bat*0.25 + tot*0.15 + bonus)

    def calculate_comprehensive_score(self, metrics: MTDMetrics,
                                      time_window_minutes: float = 5.0,
                                      total_time_seconds: float = 300.0) -> MTDScore:
        d = self.calculate_diversity_score(metrics, time_window_minutes)
        s = self.calculate_shuffle_score(metrics)
        r = self.calculate_redundancy_score(metrics)
        v = self.calculate_survivability_score(metrics, total_time_seconds)
        e = self.calculate_energy_score(metrics)
        weighted = d*self.weights['diversity'] + s*self.weights['shuffle'] + \
                   r*self.weights['redundancy'] + v*self.weights['survivability'] + \
                   e*self.weights['energy']
        if   weighted >= 90: grade="A"
        elif weighted >= 80: grade="B"
        elif weighted >= 70: grade="C"
        elif weighted >= 60: grade="D"
        else: grade="F"

        recs = self._generate_recommendations(d,s,r,v,e)
        score = MTDScore(timestamp=metrics.timestamp, diversity_score=d, shuffle_score=s,
                         redundancy_score=r, survivability_score=v, energy_score=e,
                         weighted_total=weighted, performance_grade=grade,
                         recommendations=recs)
        self.metrics_history.append(metrics)
        self.scores_history.append(score)
        if len(self.metrics_history)>100:
            self.metrics_history=self.metrics_history[-100:]
            self.scores_history=self.scores_history[-100:]
        return score

    def _generate_recommendations(self, d,s,r,v,e)->List[str]:
        rec=[]
        if d<70: rec+=["IP/Port 변경 빈도 상향","엔드포인트/라우팅 다양화"]
        if s<70: rec+=["MTD 변경 빈도 최적화","복구 시간 단축","변경 비용 경감"]
        if r<70: rec+=["백업 경로 활용 증대","Failover 메커니즘 강화"]
        if v<70: rec+=["가용성 모니터링 강화","연속성 정책 보완","저항성 강화"]
        if e<70: rec+=["CPU/네트워크/배터리 비용 최적화"]
        if (d+s+r+v+e)/5 < 60:
            rec+=["MTD 정책 전면 재검토","토폴로지/보안 요구 재분석"]
        return rec

    def get_trend_analysis(self, hours:int=1)->Dict[str,Any]:
        if len(self.scores_history)<2:
            return {"error":"데이터 부족"}
        cutoff=datetime.now()-timedelta(hours=hours)
        recent=[s for s in self.scores_history if s.timestamp>=cutoff]
        if len(recent)<2: return {"error":"시간 범위 내 데이터 부족"}
        scores=[s.weighted_total for s in recent]
        trend="증가" if scores[-1]>scores[0] else "감소"
        return {
            "time_window_hours":hours,
            "data_points":len(recent),
            "overall_trend":{
                "current":scores[-1],"average":mean(scores),
                "trend":trend,"change_rate":(scores[-1]-scores[0])/len(scores)
            },
            "performance_stability":pstdev(scores) if len(scores)>1 else 0.0
        }

    def export_scores(self, output_path:str, fmt:str="json")->bool:
        try:
            p=Path(output_path); p.parent.mkdir(parents=True, exist_ok=True)
            if fmt=="json":
                data={"export_time":datetime.now().isoformat(),
                      "total_entries":len(self.scores_history),
                      "config":{"weights":self.weights,"thresholds":self.thresholds},
                      "scores":[asdict(s) for s in self.scores_history]}
                p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            elif fmt=="csv":
                import csv
                if not self.scores_history: return False
                with p.open("w",newline='',encoding='utf-8') as f:
                    fn=['timestamp','diversity_score','shuffle_score','redundancy_score',
                        'survivability_score','energy_score','weighted_total','performance_grade']
                    w=csv.DictWriter(f, fieldnames=fn); w.writeheader()
                    for s in self.scores_history:
                        row=asdict(s); row.pop('recommendations',None); w.writerow(row)
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"점수 내보내기 실패: {e}")
            return False

# CLI
if __name__=="__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # ATK_DIR 기본 경로 추정
    ATK_DIR = Path(__file__).resolve().parents[1]
    default_cfg = ATK_DIR / "config" / "mtd_scoring_config.json"

    ap=argparse.ArgumentParser(description="MTD 성능 스코링 계산")
    ap.add_argument("--config", default=str(default_cfg))
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--export")
    ap.add_argument("--format", choices=["json","csv"], default="json")
    args=ap.parse_args()

    calc=MTDScoringCalculator(args.config)
    if args.test:
        m=MTDMetrics(timestamp=datetime.now(),
                     ip_changes=8, port_changes=12, route_changes=3, endpoint_diversity=0.75,
                     shuffle_frequency=2.5, recovery_time=15.0, shuffle_cost=45.0,
                     backup_routes_used=2, redundancy_ratio=0.8, failover_success_rate=0.95,
                     service_uptime=285.0, mission_continuity=0.92, attack_resistance=0.88,
                     cpu_cost=12.0, network_overhead=8.5, battery_consumption=6.2, total_energy_cost=26.7)
        s=calc.calculate_comprehensive_score(m)
        print(json.dumps(asdict(s), ensure_ascii=False, indent=2, default=str))
        if args.export: calc.export_scores(args.export, args.format)
    else:
        print("실제 메트릭 입력 또는 --test 사용")
