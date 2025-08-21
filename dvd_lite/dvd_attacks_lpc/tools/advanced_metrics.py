#!/usr/bin/env python3
"""
고급 드론 공격 메트릭 분석기
- 시계열 분석
- 공격 효과 상관관계
- 탐지 가능성 계산
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

class DroneAttackAnalyzer:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.timeline_file = self.base_path / "attack_output" / "effect_timeline.csv"
        self.ns3_file = self.base_path / "attack_output" / "ns3_metrics.csv"
        self.output_dir = self.base_path / "attack_output"
        
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """공격 타임라인과 NS-3 메트릭 로드"""
        timeline_df = pd.read_csv(self.timeline_file)
        timeline_df['timestamp'] = pd.to_datetime(timeline_df['t'], unit='s')
        
        ns3_df = None
        if self.ns3_file.exists():
            ns3_df = pd.read_csv(self.ns3_file)
            
        return timeline_df, ns3_df
    
    def analyze_attack_patterns(self, timeline_df: pd.DataFrame) -> Dict:
        """공격 패턴 분석"""
        patterns = {}
        
        # 공격 모듈별 통계
        module_stats = timeline_df.groupby('module').agg({
            'loss_pct': ['mean', 'max', 'std'],
            'delay_ms': ['mean', 'max', 'std'],
            'jitter_ms': ['mean', 'max', 'std'],
            'level': lambda x: x.value_counts().to_dict()
        }).round(3)
        
        patterns['module_statistics'] = module_stats.to_dict()
        
        # 공격 강도별 분포
        intensity_dist = timeline_df['level'].value_counts().to_dict()
        patterns['intensity_distribution'] = intensity_dist
        
        # 시간대별 공격 밀도
        timeline_df['hour'] = timeline_df['timestamp'].dt.hour
        hourly_attacks = timeline_df.groupby('hour').size().to_dict()
        patterns['temporal_distribution'] = hourly_attacks
        
        # 공격 시퀀스 분석
        sequence_patterns = self._analyze_sequences(timeline_df)
        patterns['sequence_patterns'] = sequence_patterns
        
        return patterns
    
    def _analyze_sequences(self, df: pd.DataFrame) -> Dict:
        """공격 시퀀스 패턴 분석"""
        sequences = []
        current_seq = []
        
        for _, row in df.iterrows():
            if row['module'] != 'lpc_loop_completed':
                current_seq.append(row['module'])
            else:
                if current_seq:
                    sequences.append(' -> '.join(current_seq))
                    current_seq = []
        
        # 가장 빈번한 시퀀스
        from collections import Counter
        seq_counts = Counter(sequences)
        
        return {
            'total_sequences': len(sequences),
            'unique_sequences': len(seq_counts),
            'most_common': seq_counts.most_common(5)
        }
    
    def calculate_detection_probability(self, timeline_df: pd.DataFrame) -> Dict:
        """탐지 확률 계산"""
        detection_scores = []
        
        for _, row in timeline_df.iterrows():
            if row['module'] == 'lpc_loop_completed':
                continue
                
            # 탐지 점수 계산 (휴리스틱)
            base_score = {
                'low': 0.1,
                'medium': 0.3,
                'high': 0.7
            }.get(row['level'], 0.1)
            
            # 네트워크 효과에 따른 가중치
            network_weight = (
                row['loss_pct'] * 0.02 +
                row['delay_ms'] * 0.001 +
                row['jitter_ms'] * 0.002
            )
            
            total_score = min(1.0, base_score + network_weight)
            detection_scores.append(total_score)
        
        if detection_scores:
            return {
                'mean_detection_probability': np.mean(detection_scores),
                'max_detection_probability': np.max(detection_scores),
                'cumulative_detection_risk': 1 - np.prod([1 - score for score in detection_scores]),
                'stealth_score': 1 - np.mean(detection_scores)
            }
        
        return {'error': 'No attack events found'}
    
    def generate_mission_impact_report(self, timeline_df: pd.DataFrame, ns3_df: pd.DataFrame) -> Dict:
        """미션 영향도 보고서 생성"""
        impact = {}
        
        # 네트워크 성능 영향
        if ns3_df is not None and not ns3_df.empty:
            impact['network_impact'] = {
                'avg_throughput_mbps': ns3_df['throughput_bps'].mean() / 1e6,
                'packet_loss_rate': ns3_df['loss_rate'].mean(),
                'avg_delay_ms': ns3_df['mean_delay_ms'].mean(),
                'avg_jitter_ms': ns3_df['jitter_ms'].mean()
            }
        
        # 누적 효과 계산
        total_loss = timeline_df['loss_pct'].sum()
        total_delay = timeline_df['delay_ms'].sum()
        total_jitter = timeline_df['jitter_ms'].sum()
        
        impact['cumulative_effects'] = {
            'total_packet_loss_pct': total_loss,
            'total_delay_ms': total_delay,
            'total_jitter_ms': total_jitter,
            'attack_duration_minutes': (timeline_df['t'].max() - timeline_df['t'].min()) / 60
        }
        
        # 심각도 평가
        severity = 'LOW'
        if total_loss > 10 or total_delay > 1000:
            severity = 'MEDIUM'
        if total_loss > 25 or total_delay > 2000:
            severity = 'HIGH'
        if total_loss > 50 or total_delay > 5000:
            severity = 'CRITICAL'
            
        impact['severity_assessment'] = severity
        
        return impact
    
    def export_reports(self, patterns: Dict, detection: Dict, impact: Dict):
        """보고서 내보내기"""
        # JSON 상세 보고서
        full_report = {
            'attack_patterns': patterns,
            'detection_analysis': detection,
            'mission_impact': impact,
            'generated_at': pd.Timestamp.now().isoformat()
        }
        
        json_path = self.output_dir / "attack_analysis_report.json"
        with open(json_path, 'w') as f:
            json.dump(full_report, f, indent=2, default=str)
            
        # 요약 보고서 (텍스트)
        summary_path = self.output_dir / "attack_summary.txt"
        with open(summary_path, 'w') as f:
            f.write("=== 드론 공격 시뮬레이션 분석 보고서 ===\n\n")
            
            f.write(f"탐지 위험도: {detection.get('stealth_score', 0):.2%}\n")
            f.write(f"미션 영향도: {impact.get('severity_assessment', 'UNKNOWN')}\n")
            f.write(f"누적 패킷 손실: {impact.get('cumulative_effects', {}).get('total_packet_loss_pct', 0):.1f}%\n")
            f.write(f"총 공격 시간: {impact.get('cumulative_effects', {}).get('attack_duration_minutes', 0):.1f}분\n\n")
            
            f.write("주요 공격 모듈:\n")
            for module, count in patterns.get('intensity_distribution', {}).items():
                f.write(f"  - {module}: {count}회\n")
        
        print(f"보고서 생성 완료:")
        print(f"  - 상세: {json_path}")
        print(f"  - 요약: {summary_path}")

def main():
    parser = argparse.ArgumentParser(description='드론 공격 분석기')
    parser.add_argument('--base-path', default='.', help='베이스 경로')
    args = parser.parse_args()
    
    analyzer = DroneAttackAnalyzer(args.base_path)
    
    try:
        timeline_df, ns3_df = analyzer.load_data()
        print(f"데이터 로드 완료: {len(timeline_df)} 공격 이벤트")
        
        patterns = analyzer.analyze_attack_patterns(timeline_df)
        detection = analyzer.calculate_detection_probability(timeline_df)
        impact = analyzer.generate_mission_impact_report(timeline_df, ns3_df)
        
        analyzer.export_reports(patterns, detection, impact)
        
    except Exception as e:
        print(f"분석 오류: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
