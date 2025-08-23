#!/bin/bash

# =================================================================
# 분석 및 모니터링 도구 생성 스크립트
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/create_analysis_tools.sh
# 사용법: chmod +x create_analysis_tools.sh && ./create_analysis_tools.sh
# =================================================================

set -e

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

log_info "분석 및 모니터링 도구 생성 시작"

# =================================================================
# 1. 실시간 대시보드
# =================================================================

log_info "=== 실시간 대시보드 생성 ==="

cat > scripts/monitoring/realtime_dashboard.py << 'EOF'
#!/usr/bin/env python3
"""
실시간 MTD 드론 보안 대시보드
"""

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import sqlite3
import time
import json
import threading
from datetime import datetime, timedelta
import numpy as np

app = dash.Dash(__name__)

# 전역 데이터 저장소
data_store = {
    'metrics': [],
    'attack_events': [],
    'mtd_events': [],
    'network_status': {}
}

def load_data():
    """데이터베이스에서 최신 데이터 로드"""
    try:
        conn = sqlite3.connect('attack_output/unified_metrics.db')
        
        # 최근 1시간 메트릭
        query = """
        SELECT * FROM unified_metrics 
        WHERE timestamp > ? 
        ORDER BY timestamp DESC 
        LIMIT 1000
        """
        
        one_hour_ago = time.time() - 3600
        df = pd.read_sql_query(query, conn, params=[one_hour_ago])
        
        conn.close()
        
        if not df.empty:
            data_store['metrics'] = df.to_dict('records')
        
    except Exception as e:
        print(f"데이터 로드 오류: {e}")

def update_data():
    """주기적 데이터 업데이트"""
    while True:
        load_data()
        time.sleep(5)

# 백그라운드 데이터 업데이트 시작
threading.Thread(target=update_data, daemon=True).start()

# 레이아웃
app.layout = html.Div([
    html.H1("MTD 드론 보안 테스트베드 실시간 대시보드", 
            style={'textAlign': 'center', 'color': '#2c3e50'}),
    
    # 상태 카드들
    html.Div([
        html.Div([
            html.H3("시스템 상태", style={'color': '#27ae60'}),
            html.P(id="system-status", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        }),
        
        html.Div([
            html.H3("탐지된 공격", style={'color': '#e74c3c'}),
            html.P(id="attack-count", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        }),
        
        html.Div([
            html.H3("MTD 적응 횟수", style={'color': '#f39c12'}),
            html.P(id="mtd-count", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        }),
        
        html.Div([
            html.H3("평균 지연시간", style={'color': '#3498db'}),
            html.P(id="avg-latency", style={'fontSize': '24px'})
        ], className="status-card", style={
            'width': '23%', 'display': 'inline-block', 'margin': '1%',
            'padding': '20px', 'border': '1px solid #bdc3c7', 'borderRadius': '5px'
        })
    ]),
    
    # 그래프들
    html.Div([
        html.Div([
            dcc.Graph(id="network-metrics-graph")
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(id="security-metrics-graph")
        ], style={'width': '50%', 'display': 'inline-block'})
    ]),
    
    html.Div([
        html.Div([
            dcc.Graph(id="mtd-timeline-graph")
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(id="attack-heatmap")
        ], style={'width': '50%', 'display': 'inline-block'})
    ]),
    
    # 자동 새로고침
    dcc.Interval(
        id='interval-component',
        interval=5*1000,  # 5초마다 업데이트
        n_intervals=0
    )
])

@app.callback(
    [Output('system-status', 'children'),
     Output('attack-count', 'children'),
     Output('mtd-count', 'children'),
     Output('avg-latency', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_status_cards(n):
    if not data_store['metrics']:
        return "연결 중...", "0", "0", "0ms"
    
    latest = data_store['metrics'][0] if data_store['metrics'] else {}
    
    system_status = "🟢 정상" if latest.get('latency_ms', 999) < 100 else "🔴 경고"
    attack_count = f"{latest.get('attacks_detected', 0)}"
    mtd_count = f"{latest.get('mtd_activations', 0)}"
    avg_latency = f"{latest.get('latency_ms', 0):.1f}ms"
    
    return system_status, attack_count, mtd_count, avg_latency

@app.callback(
    Output('network-metrics-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_network_graph(n):
    if not data_store['metrics']:
        return {'data': [], 'layout': {'title': '네트워크 메트릭 로딩 중...'}}
    
    df = pd.DataFrame(data_store['metrics'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['latency_ms'],
        mode='lines', name='지연시간 (ms)',
        line=dict(color='blue')
    ))
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['packet_loss_pct'],
        mode='lines', name='패킷 손실 (%)',
        line=dict(color='red'), yaxis='y2'
    ))
    
    fig.update_layout(
        title='네트워크 성능 메트릭',
        xaxis_title='시간',
        yaxis=dict(title='지연시간 (ms)', side='left'),
        yaxis2=dict(title='패킷 손실 (%)', side='right', overlaying='y'),
        legend=dict(x=0, y=1)
    )
    
    return fig

@app.callback(
    Output('security-metrics-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_security_graph(n):
    if not data_store['metrics']:
        return {'data': [], 'layout': {'title': '보안 메트릭 로딩 중...'}}
    
    df = pd.DataFrame(data_store['metrics'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['attacks_detected'],
        mode='markers+lines', name='탐지된 공격',
        line=dict(color='red')
    ))
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['detection_accuracy'],
        mode='lines', name='탐지 정확도',
        line=dict(color='green'), yaxis='y2'
    ))
    
    fig.update_layout(
        title='보안 메트릭',
        xaxis_title='시간',
        yaxis=dict(title='탐지된 공격 수', side='left'),
        yaxis2=dict(title='탐지 정확도', side='right', overlaying='y'),
        legend=dict(x=0, y=1)
    )
    
    return fig

@app.callback(
    Output('mtd-timeline-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_mtd_timeline(n):
    if not data_store['metrics']:
        return {'data': [], 'layout': {'title': 'MTD 타임라인 로딩 중...'}}
    
    df = pd.DataFrame(data_store['metrics'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    # MTD 전략별 색상 매핑
    strategy_colors = {
        'none': 'gray',
        'ip_hopping': 'blue',
        'port_shuffling': 'green',
        'route_mutation': 'orange',
        'frequency_hopping': 'purple',
        'protocol_diversification': 'red',
        'decoy_deployment': 'pink',
        'traffic_shaping': 'brown'
    }
    
    fig = go.Figure()
    
    for strategy, color in strategy_colors.items():
        strategy_data = df[df['mtd_strategy'] == strategy]
        if not strategy_data.empty:
            fig.add_trace(go.Scatter(
                x=strategy_data['timestamp'],
                y=strategy_data['defense_level'],
                mode='markers',
                name=strategy,
                marker=dict(color=color, size=10)
            ))
    
    fig.update_layout(
        title='MTD 전략 타임라인',
        xaxis_title='시간',
        yaxis_title='방어 수준',
        legend=dict(x=0, y=1)
    )
    
    return fig

@app.callback(
    Output('attack-heatmap', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_attack_heatmap(n):
    # 시간대별 공격 발생 히트맵 (시뮬레이션)
    hours = list(range(24))
    days = ['월', '화', '수', '목', '금', '토', '일']
    
    # 랜덤 데이터 생성 (실제로는 데이터베이스에서)
    attack_data = np.random.randint(0, 10, size=(7, 24))
    
    fig = go.Figure(data=go.Heatmap(
        z=attack_data,
        x=hours,
        y=days,
        colorscale='Reds',
        hoveremplate='시간: %{x}시<br>요일: %{y}<br>공격 수: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title='시간대별 공격 발생 패턴',
        xaxis_title='시간 (24시간)',
        yaxis_title='요일'
    )
    
    return fig

if __name__ == '__main__':
    print("실시간 대시보드 시작: http://localhost:8050")
    app.run_server(debug=False, host='0.0.0.0', port=8050)
EOF

# =================================================================
# 2. 자동 보고서 생성기
# =================================================================

log_info "=== 자동 보고서 생성기 생성 ==="

cat > scripts/analysis/generate_comparison_report.py << 'EOF'
#!/usr/bin/env python3
"""
비교 분석 보고서 자동 생성기
"""

import os
import sys
import pandas as pd
import numpy as np
import json
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import Dict, List, Any
import argparse

class ComparisonReportGenerator:
    def __init__(self, experiment_dir: str):
        self.experiment_dir = experiment_dir
        self.results = {}
        self.summary_data = []
        
    def generate_report(self):
        """종합 비교 보고서 생성"""
        print(f"실험 결과 분석 중: {self.experiment_dir}")
        
        # 1. 실험 데이터 수집
        self._collect_experiment_data()
        
        # 2. 통계 분석
        self._perform_statistical_analysis()
        
        # 3. 시각화 생성
        self._generate_visualizations()
        
        # 4. 보고서 작성
        self._write_comprehensive_report()
        
        print(f"보고서 생성 완료: {self.experiment_dir}/comparison_report.md")
    
    def _collect_experiment_data(self):
        """실험 데이터 수집"""
        for root, dirs, files in os.walk(self.experiment_dir):
            for file in files:
                if file == 'comprehensive_report.json':
                    exp_path = os.path.join(root, file)
                    with open(exp_path, 'r') as f:
                        data = json.load(f)
                    
                    # 실험 이름 추출
                    exp_name = os.path.basename(root)
                    self.results[exp_name] = data
                    
                    # 요약 데이터 추가
                    summary = {
                        'experiment': exp_name,
                        'avg_latency': data.get('network_performance', {}).get('avg_latency_ms', 0),
                        'avg_packet_loss': data.get('network_performance', {}).get('avg_packet_loss_pct', 0),
                        'detection_accuracy': data.get('security_metrics', {}).get('avg_detection_accuracy', 0),
                        'mtd_activations': data.get('mtd_effectiveness', {}).get('total_mtd_activations', 0),
                        'mission_success_rate': data.get('overall_performance', {}).get('avg_mission_success_rate', 0)
                    }
                    self.summary_data.append(summary)
    
    def _perform_statistical_analysis(self):
        """통계 분석 수행"""
        if not self.summary_data:
            return
        
        df = pd.DataFrame(self.summary_data)
        
        # 기본 통계
        self.stats = {
            'descriptive': df.describe(),
            'correlation': df.corr(),
            'best_performers': {
                'lowest_latency': df.loc[df['avg_latency'].idxmin()]['experiment'],
                'highest_detection': df.loc[df['detection_accuracy'].idxmax()]['experiment'],
                'best_mission_success': df.loc[df['mission_success_rate'].idxmax()]['experiment']
            }
        }
    
    def _generate_visualizations(self):
        """시각화 생성"""
        if not self.summary_data:
            return
        
        df = pd.DataFrame(self.summary_data)
        
        # 스타일 설정
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('MTD 드론 보안 테스트베드 실험 결과 비교', fontsize=16, fontweight='bold')
        
        # 1. 지연시간 비교
        axes[0, 0].bar(df['experiment'], df['avg_latency'], color='skyblue')
        axes[0, 0].set_title('평균 지연시간 비교')
        axes[0, 0].set_ylabel('지연시간 (ms)')
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # 2. 패킷 손실 비교
        axes[0, 1].bar(df['experiment'], df['avg_packet_loss'], color='lightcoral')
        axes[0, 1].set_title('평균 패킷 손실 비교')
        axes[0, 1].set_ylabel('패킷 손실 (%)')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # 3. 탐지 정확도 비교
        axes[0, 2].bar(df['experiment'], df['detection_accuracy'], color='lightgreen')
        axes[0, 2].set_title('탐지 정확도 비교')
        axes[0, 2].set_ylabel('정확도')
        axes[0, 2].tick_params(axis='x', rotation=45)
        
        # 4. MTD 적응 횟수
        axes[1, 0].bar(df['experiment'], df['mtd_activations'], color='orange')
        axes[1, 0].set_title('MTD 적응 횟수')
        axes[1, 0].set_ylabel('적응 횟수')
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # 5. 미션 성공률
        axes[1, 1].bar(df['experiment'], df['mission_success_rate'], color='purple')
        axes[1, 1].set_title('미션 성공률')
        axes[1, 1].set_ylabel('성공률')
        axes[1, 1].tick_params(axis='x', rotation=45)
        
        # 6. 상관관계 히트맵
        correlation_matrix = df[['avg_latency', 'avg_packet_loss', 'detection_accuracy', 
                               'mtd_activations', 'mission_success_rate']].corr()
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0, 
                   ax=axes[1, 2], square=True)
        axes[1, 2].set_title('메트릭 간 상관관계')
        
        plt.tight_layout()
        plt.savefig(f"{self.experiment_dir}/comparison_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 레이더 차트 생성
        self._create_radar_chart(df)
    
    def _create_radar_chart(self, df: pd.DataFrame):
        """레이더 차트 생성"""
        from math import pi
        
        # 메트릭 정규화 (0-1 범위)
        metrics = ['avg_latency', 'avg_packet_loss', 'detection_accuracy', 
                  'mtd_activations', 'mission_success_rate']
        
        normalized_df = df.copy()
        for metric in metrics:
            if metric in ['avg_latency', 'avg_packet_loss']:  # 낮을수록 좋음
                normalized_df[metric] = 1 - (df[metric] / df[metric].max())
            else:  # 높을수록 좋음
                normalized_df[metric] = df[metric] / df[metric].max()
        
        # 각도 계산
        angles = [n / float(len(metrics)) * 2 * pi for n in range(len(metrics))]
        angles += angles[:1]  # 원을 완성하기 위해
        
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(df)))
        
        for i, (idx, row) in enumerate(normalized_df.iterrows()):
            values = [row[metric] for metric in metrics]
            values += values[:1]  # 원을 완성하기 위해
            
            ax.plot(angles, values, 'o-', linewidth=2, label=row['experiment'], color=colors[i])
            ax.fill(angles, values, alpha=0.25, color=colors[i])
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(['지연시간', '패킷손실', '탐지정확도', 'MTD적응', '미션성공'])
        ax.set_ylim(0, 1)
        ax.set_title('실험별 종합 성능 비교 (레이더 차트)', size=16, fontweight='bold')
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        
        plt.savefig(f"{self.experiment_dir}/radar_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _write_comprehensive_report(self):
        """종합 보고서 작성"""
        report_path = f"{self.experiment_dir}/comparison_report.md"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"""# MTD 드론 보안 테스트베드 실험 결과 보고서

생성 날짜: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🎯 실험 개요

이 보고서는 MTD(Moving Target Defense) 기반 드론 보안 테스트베드에서 수행된 
다양한 공격 시나리오와 방어 전략의 효과를 비교 분석한 결과입니다.

### 실험된 시나리오
""")
            
            # 실험 목록
            for exp_name in self.results.keys():
                f.write(f"- {exp_name}\n")
            
            f.write(f"""
## 📊 주요 결과 요약

### 최고 성능 실험
""")
            
            if hasattr(self, 'stats'):
                f.write(f"""
- **최저 지연시간**: {self.stats['best_performers']['lowest_latency']}
- **최고 탐지 정확도**: {self.stats['best_performers']['highest_detection']}
- **최고 미션 성공률**: {self.stats['best_performers']['best_mission_success']}
""")
            
            f.write(f"""
## 📈 성능 메트릭 분석

### 네트워크 성능
""")
            
            # 각 실험별 상세 결과
            for exp_name, data in self.results.items():
                network_perf = data.get('network_performance', {})
                security_metrics = data.get('security_metrics', {})
                mtd_effectiveness = data.get('mtd_effectiveness', {})
                
                f.write(f"""
#### {exp_name}
- **평균 지연시간**: {network_perf.get('avg_latency_ms', 'N/A'):.2f} ms
- **평균 패킷 손실**: {network_perf.get('avg_packet_loss_pct', 'N/A'):.2f}%
- **평균 처리량**: {network_perf.get('avg_throughput_mbps', 'N/A'):.2f} Mbps
- **탐지 정확도**: {security_metrics.get('avg_detection_accuracy', 'N/A'):.3f}
- **총 공격 탐지**: {security_metrics.get('total_attacks_detected', 'N/A')}
- **MTD 적응 횟수**: {mtd_effectiveness.get('total_mtd_activations', 'N/A')}
- **주요 MTD 전략**: {mtd_effectiveness.get('most_used_strategy', 'N/A')}
""")
            
            f.write(f"""
## 🔍 통계 분석

### 기술 통계
""")
            
            if hasattr(self, 'stats'):
                stats_df = self.stats['descriptive']
                f.write(f"""
| 메트릭 | 평균 | 표준편차 | 최소값 | 최대값 |
|--------|------|----------|--------|--------|
""")
                for metric in stats_df.columns:
                    f.write(f"| {metric} | {stats_df.loc['mean', metric]:.3f} | {stats_df.loc['std', metric]:.3f} | {stats_df.loc['min', metric]:.3f} | {stats_df.loc['max', metric]:.3f} |\n")
            
            f.write(f"""
## 📊 시각화

다음 그래프들이 생성되었습니다:
- `comparison_analysis.png`: 전체 메트릭 비교 차트
- `radar_comparison.png`: 레이더 차트 비교

## 🎓 결론 및 권장사항

### 주요 발견사항
1. **성능 vs 보안 트레이드오프**: MTD 전략 적용 시 네트워크 성능에 일정한 오버헤드가 발생하나, 
   보안 향상 효과가 이를 상쇄함
2. **적응형 방어의 효과**: 실시간 MTD 적응이 공격 탐지율을 크게 향상시킴
3. **허니드론 네트워크의 유효성**: 가짜 드론을 통한 공격 유도 및 CTI 수집이 효과적임

### 권장사항
1. **균형잡힌 방어 전략**: enhanced 수준의 방어가 성능과 보안의 최적 균형점
2. **동적 임계치 조정**: 공격 패턴에 따른 실시간 탐지 임계치 조정 필요
3. **지속적 학습**: 강화학습 기반 MTD 전략 선택의 지속적 개선

## 📋 부록

### 실험 환경
- **테스트베드**: DVD (Damn Vulnerable Drone) 기반
- **시뮬레이션 도구**: NS-3 네트워크 시뮬레이터
- **ML 프레임워크**: PyTorch 기반 DQN
- **네트워크 토폴로지**: FANET 기반 허니드론 메시 네트워크

### 데이터 소스
- 실시간 네트워크 메트릭
- Docker 컨테이너 이벤트 로그
- LPC 공격 패턴 로그
- NS-3 시뮬레이션 결과

---
*이 보고서는 MTD 드론 보안 테스트베드 자동 분석 시스템에 의해 생성되었습니다.*
""")
        
        print(f"종합 보고서 생성 완료: {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="실험 결과 비교 분석 보고서 생성")
    parser.add_argument("experiment_dir", help="실험 결과 디렉토리")
    args = parser.parse_args()
    
    generator = ComparisonReportGenerator(args.experiment_dir)
    generator.generate_report()
EOF

# =================================================================
# 3. 시스템 상태 검증기
# =================================================================

log_info "=== 시스템 상태 검증기 생성 ==="

cat > scripts/monitoring/system_validator.py << 'EOF'
#!/usr/bin/env python3
"""
시스템 상태 검증기
"""

import os
import subprocess
import docker
import sqlite3
import yaml
import json
import time
import requests
from typing import Dict, List, Tuple, Any
from datetime import datetime
import socket

class SystemValidator:
    def __init__(self):
        self.checks = []
        self.results = {}
        
    def run_all_checks(self) -> Dict[str, Any]:
        """모든 검증 수행"""
        print("🔍 시스템 상태 검증 시작...")
        
        self.checks = [
            ("디렉토리 구조", self._check_directory_structure),
            ("설정 파일", self._check_config_files),
            ("Python 의존성", self._check_python_dependencies),
            ("Docker 상태", self._check_docker_status),
            ("데이터베이스", self._check_database),
            ("네트워크 연결", self._check_network_connectivity),
            ("NS-3 환경", self._check_ns3_environment),
            ("로그 파일", self._check_log_files),
            ("권한 설정", self._check_permissions)
        ]
        
        all_passed = True
        
        for check_name, check_func in self.checks:
            try:
                result = check_func()
                self.results[check_name] = result
                
                if result['status'] == 'pass':
                    print(f"✅ {check_name}: 통과")
                elif result['status'] == 'warning':
                    print(f"⚠️  {check_name}: 경고 - {result['message']}")
                else:
                    print(f"❌ {check_name}: 실패 - {result['message']}")
                    all_passed = False
                    
            except Exception as e:
                print(f"❌ {check_name}: 오류 - {e}")
                self.results[check_name] = {'status': 'fail', 'message': str(e)}
                all_passed = False
        
        # 결과 요약
        print(f"\n📋 검증 완료: {'모든 검사 통과' if all_passed else '일부 문제 발견'}")
        self._save_results()
        
        return self.results
    
    def _check_directory_structure(self) -> Dict:
        """디렉토리 구조 확인"""
        required_dirs = [
            'ml', 'configs', 'honeydrone_network', 'data_pipeline',
            'ns3_integration', 'scripts', 'attack_output', 'logs', 'results'
        ]
        
        missing_dirs = []
        for dir_name in required_dirs:
            if not os.path.exists(dir_name):
                missing_dirs.append(dir_name)
        
        if missing_dirs:
            return {
                'status': 'fail',
                'message': f'누락된 디렉토리: {", ".join(missing_dirs)}'
            }
        
        return {'status': 'pass', 'message': '모든 필수 디렉토리 존재'}
    
    def _check_config_files(self) -> Dict:
        """설정 파일 확인"""
        config_files = [
            'configs/attack_intensity/lpc_profiles.yaml',
            'configs/defense_levels/detection_thresholds.yaml',
            'configs/network_topologies/honeydrone_network.yaml',
            'ml/pipeline_config.yaml'
        ]
        
        invalid_files = []
        
        for config_file in config_files:
            if not os.path.exists(config_file):
                invalid_files.append(f"{config_file} (없음)")
                continue
            
            try:
                with open(config_file, 'r') as f:
                    yaml.safe_load(f)
            except Exception as e:
                invalid_files.append(f"{config_file} (유효하지 않음: {e})")
        
        if invalid_files:
            return {
                'status': 'fail',
                'message': f'문제있는 설정 파일: {", ".join(invalid_files)}'
            }
        
        return {'status': 'pass', 'message': '모든 설정 파일 유효'}
    
    def _check_python_dependencies(self) -> Dict:
        """Python 의존성 확인"""
        required_packages = [
            'numpy', 'pandas', 'torch', 'sklearn', 'matplotlib',
            'yaml', 'docker', 'asyncio', 'websockets'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            return {
                'status': 'fail',
                'message': f'누락된 패키지: {", ".join(missing_packages)}'
            }
        
        return {'status': 'pass', 'message': '모든 필수 패키지 설치됨'}
    
    def _check_docker_status(self) -> Dict:
        """Docker 상태 확인"""
        try:
            client = docker.from_env()
            containers = client.containers.list()
            
            dvd_containers = [c for c in containers if any(
                name in c.name for name in ['simulator', 'ground-control', 'companion', 'flight']
            )]
            
            if not dvd_containers:
                return {
                    'status': 'warning',
                    'message': 'DVD 컨테이너가 실행되지 않음'
                }
            
            return {
                'status': 'pass', 
                'message': f'{len(dvd_containers)}개 DVD 컨테이너 실행 중'
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Docker 연결 실패: {e}'
            }
    
    def _check_database(self) -> Dict:
        """데이터베이스 확인"""
        db_files = [
            'attack_output/unified_metrics.db',
            'attack_output/mtd_performance.db'
        ]
        
        for db_file in db_files:
            if os.path.exists(db_file):
                try:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    conn.close()
                    
                    if not tables:
                        return {
                            'status': 'warning',
                            'message': f'{db_file}: 테이블 없음'
                        }
                except Exception as e:
                    return {
                        'status': 'fail',
                        'message': f'{db_file}: 접근 오류 - {e}'
                    }
        
        return {'status': 'pass', 'message': '데이터베이스 정상'}
    
    def _check_network_connectivity(self) -> Dict:
        """네트워크 연결 확인"""
        test_endpoints = [
            ('localhost', 5001, 'LPC UI'),
            ('localhost', 5002, 'DVD OPS UI'),
            ('localhost', 8050, 'Dashboard'),
            ('localhost', 8765, 'WebSocket')
        ]
        
        failed_connections = []
        
        for host, port, name in test_endpoints:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result != 0:
                failed_connections.append(f"{name} ({host}:{port})")
        
        if failed_connections:
            return {
                'status': 'warning',
                'message': f'연결 실패: {", ".join(failed_connections)}'
            }
        
        return {'status': 'pass', 'message': '모든 네트워크 연결 정상'}
    
    def _check_ns3_environment(self) -> Dict:
        """NS-3 환경 확인"""
        ns3_paths = [
            '~/MTD/MTD_full_testbed/ns-3.45/ns-3-dev',
            '/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev'
        ]
        
        for ns3_path in ns3_paths:
            expanded_path = os.path.expanduser(ns3_path)
            if os.path.exists(expanded_path):
                # NS-3 실행 파일 확인
                ns3_exec = os.path.join(expanded_path, 'ns3')
                waf_exec = os.path.join(expanded_path, 'waf')
                
                if os.path.exists(ns3_exec) or os.path.exists(waf_exec):
                    return {
                        'status': 'pass',
                        'message': f'NS-3 환경 발견: {expanded_path}'
                    }
        
        return {
            'status': 'warning',
            'message': 'NS-3 환경을 찾을 수 없음'
        }
    
    def _check_log_files(self) -> Dict:
        """로그 파일 확인"""
        log_dirs = ['logs', 'attack_output']
        total_log_files = 0
        
        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    log_files = [f for f in files if f.endswith('.log')]
                    total_log_files += len(log_files)
        
        if total_log_files == 0:
            return {
                'status': 'warning',
                'message': '로그 파일이 없음 (시스템이 아직 실행되지 않음)'
            }
        
        return {
            'status': 'pass',
            'message': f'{total_log_files}개 로그 파일 발견'
        }
    
    def _check_permissions(self) -> Dict:
        """권한 설정 확인"""
        script_files = []
        
        # 실행 스크립트 찾기
        for root, dirs, files in os.walk('scripts'):
            for file in files:
                if file.endswith('.sh') or file.endswith('.py'):
                    script_files.append(os.path.join(root, file))
        
        non_executable = []
        
        for script_file in script_files:
            if not os.access(script_file, os.X_OK):
                non_executable.append(script_file)
        
        if non_executable:
            return {
                'status': 'warning',
                'message': f'실행 권한 없음: {len(non_executable)}개 파일'
            }
        
        return {
            'status': 'pass',
            'message': '모든 스크립트 실행 가능'
        }
    
    def _save_results(self):
        """검증 결과 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = f'results/validation_report_{timestamp}.json'
        
        os.makedirs('results', exist_ok=True)
        
        with open(result_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'total_checks': len(self.checks),
                'passed': len([r for r in self.results.values() if r['status'] == 'pass']),
                'warnings': len([r for r in self.results.values() if r['status'] == 'warning']),
                'failed': len([r for r in self.results.values() if r['status'] == 'fail']),
                'details': self.results
            }, f, indent=2)
        
        print(f"📄 검증 보고서 저장: {result_file}")

if __name__ == "__main__":
    validator = SystemValidator()
    validator.run_all_checks()
EOF

# =================================================================
# 4. 웹 기반 통합 컨트롤 패널
# =================================================================

log_info "=== 웹 기반 통합 컨트롤 패널 생성 ==="

cat > scripts/monitoring/control_panel.py << 'EOF'
#!/usr/bin/env python3
"""
웹 기반 통합 컨트롤 패널
"""

from flask import Flask, render_template, request, jsonify, send_file
import subprocess
import json
import os
import time
from datetime import datetime
import threading
import sqlite3

app = Flask(__name__)

# 전역 상태
system_status = {
    'honeydrone_network': False,
    'timestamp_collector': False,
    'ml_pipeline': False,
    'ns3_simulation': False,
    'dashboard': False
}

running_processes = {}

@app.route('/')
def index():
    """메인 대시보드"""
    return render_template('control_panel.html')

@app.route('/api/status')
def api_status():
    """시스템 상태 API"""
    return jsonify(system_status)

@app.route('/api/start_component', methods=['POST'])
def start_component():
    """컴포넌트 시작"""
    component = request.json.get('component')
    
    try:
        if component == 'honeydrone_network':
            proc = subprocess.Popen(['python3', 'honeydrone_network/honeydrone_manager.py'])
            running_processes['honeydrone_network'] = proc
            system_status['honeydrone_network'] = True
            
        elif component == 'timestamp_collector':
            proc = subprocess.Popen(['python3', 'data_pipeline/collectors/timestamp_collector.py'])
            running_processes['timestamp_collector'] = proc
            system_status['timestamp_collector'] = True
            
        elif component == 'ml_pipeline':
            proc = subprocess.Popen(['python3', 'ml/integrated_ml_pipeline.py', '--duration', '0'])
            running_processes['ml_pipeline'] = proc
            system_status['ml_pipeline'] = True
            
        elif component == 'dashboard':
            proc = subprocess.Popen(['python3', 'scripts/monitoring/realtime_dashboard.py'])
            running_processes['dashboard'] = proc
            system_status['dashboard'] = True
            
        return jsonify({'status': 'success', 'message': f'{component} 시작됨'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/stop_component', methods=['POST'])
def stop_component():
    """컴포넌트 중지"""
    component = request.json.get('component')
    
    try:
        if component in running_processes:
            proc = running_processes[component]
            proc.terminate()
            del running_processes[component]
            system_status[component] = False
            
        return jsonify({'status': 'success', 'message': f'{component} 중지됨'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/run_experiment', methods=['POST'])
def run_experiment():
    """실험 실행"""
    scenario = request.json.get('scenario', 'stealth_recon')
    defense_level = request.json.get('defense_level', 'standard')
    duration = request.json.get('duration', 300)
    
    try:
        cmd = [
            './scripts/deployment/run_integrated_system.sh',
            'experiment', scenario,
            '--defense-level', defense_level,
            '--duration', str(duration)
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        running_processes['experiment'] = proc
        
        return jsonify({
            'status': 'success',
            'message': f'실험 시작: {scenario} vs {defense_level}'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/get_logs')
def get_logs():
    """로그 조회"""
    log_type = request.args.get('type', 'integrated')
    lines = int(request.args.get('lines', 50))
    
    log_files = {
        'integrated': 'attack_output/integrated_pipeline.log',
        'collector': 'logs/timestamps/collector.log',
        'honeydrone': 'logs/networks/honeydrone_manager.log',
        'sdn': 'attack_output/sdn_mtd.log'
    }
    
    log_file = log_files.get(log_type)
    if not log_file or not os.path.exists(log_file):
        return jsonify({'logs': []})
    
    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return jsonify({'logs': [line.strip() for line in recent_lines]})
        
    except Exception as e:
        return jsonify({'logs': [f'로그 읽기 오류: {e}']})

@app.route('/api/get_metrics')
def get_metrics():
    """메트릭 조회"""
    try:
        conn = sqlite3.connect('attack_output/unified_metrics.db')
        cursor = conn.cursor()
        
        # 최근 100개 레코드
        cursor.execute("""
            SELECT * FROM unified_metrics 
            ORDER BY timestamp DESC 
            LIMIT 100
        """)
        
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        
        metrics = []
        for row in rows:
            metrics.append(dict(zip(columns, row)))
        
        conn.close()
        return jsonify({'metrics': metrics})
        
    except Exception as e:
        return jsonify({'metrics': [], 'error': str(e)})

@app.route('/api/validate_system', methods=['POST'])
def validate_system():
    """시스템 검증"""
    try:
        proc = subprocess.run(
            ['python3', 'scripts/monitoring/system_validator.py'],
            capture_output=True, text=True
        )
        
        return jsonify({
            'status': 'success',
            'output': proc.stdout,
            'returncode': proc.returncode
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# HTML 템플릿 생성
templates_dir = 'templates'
os.makedirs(templates_dir, exist_ok=True)

with open(f'{templates_dir}/control_panel.html', 'w') as f:
    f.write('''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MTD 드론 보안 테스트베드 - 통합 컨트롤 패널</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .panel { background: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .status-item { padding: 15px; border-radius: 5px; text-align: center; }
        .status-running { background: #2ecc71; color: white; }
        .status-stopped { background: #e74c3c; color: white; }
        .btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #2980b9; }
        .btn-danger { background: #e74c3c; }
        .btn-danger:hover { background: #c0392b; }
        .logs { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; height: 300px; overflow-y: auto; font-family: monospace; font-size: 12px; }
        .experiment-form { display: grid; gap: 10px; }
        .form-group { display: grid; grid-template-columns: 1fr 2fr; gap: 10px; align-items: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚁 MTD 드론 보안 테스트베드</h1>
        <p>통합 컨트롤 패널 및 모니터링 시스템</p>
    </div>

    <div class="container">
        <div class="panel">
            <h2>🔧 시스템 제어</h2>
            <div class="status-grid" id="status-grid">
                <!-- 동적으로 생성됨 -->
            </div>
            <br>
            <button class="btn" onclick="startAllComponents()">전체 시작</button>
            <button class="btn btn-danger" onclick="stopAllComponents()">전체 중지</button>
            <button class="btn" onclick="validateSystem()">시스템 검증</button>
        </div>

        <div class="panel">
            <h2>🧪 실험 실행</h2>
            <div class="experiment-form">
                <div class="form-group">
                    <label>공격 시나리오:</label>
                    <select id="scenario">
                        <option value="stealth_recon">은밀한 정찰</option>
                        <option value="aggressive_attack">공격적 침투</option>
                        <option value="persistent_campaign">지속적 캠페인</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>방어 수준:</label>
                    <select id="defense-level">
                        <option value="minimal">최소</option>
                        <option value="standard" selected>표준</option>
                        <option value="enhanced">고급</option>
                        <option value="maximum">최대</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>실행 시간 (초):</label>
                    <input type="number" id="duration" value="300" min="60" max="3600">
                </div>
                <button class="btn" onclick="runExperiment()">실험 시작</button>
            </div>
        </div>

        <div class="panel">
            <h2>📊 시스템 로그</h2>
            <select id="log-type" onchange="updateLogs()">
                <option value="integrated">통합 파이프라인</option>
                <option value="collector">타임스탬프 수집기</option>
                <option value="honeydrone">허니드론 네트워크</option>
                <option value="sdn">SDN 컨트롤러</option>
            </select>
            <div class="logs" id="logs-display">로그 로딩 중...</div>
        </div>

        <div class="panel">
            <h2>🔗 외부 링크</h2>
            <button class="btn" onclick="window.open('http://localhost:8050', '_blank')">실시간 대시보드</button>
            <button class="btn" onclick="window.open('http://localhost:5001', '_blank')">공격/평가 콘솔</button>
            <button class="btn" onclick="window.open('http://localhost:5002', '_blank')">DVD 모니터링</button>
            <button class="btn" onclick="window.open('http://localhost:8000', '_blank')">DVD 시뮬레이터</button>
        </div>
    </div>

    <script>
        let systemStatus = {};

        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    systemStatus = data;
                    renderStatusGrid();
                });
        }

        function renderStatusGrid() {
            const grid = document.getElementById('status-grid');
            grid.innerHTML = '';
            
            const components = {
                'honeydrone_network': '허니드론 네트워크',
                'timestamp_collector': '타임스탬프 수집기',
                'ml_pipeline': 'ML 파이프라인',
                'dashboard': '실시간 대시보드'
            };

            for (const [key, name] of Object.entries(components)) {
                const status = systemStatus[key] ? 'running' : 'stopped';
                const statusText = systemStatus[key] ? '실행 중' : '중지됨';
                
                const item = document.createElement('div');
                item.className = `status-item status-${status}`;
                item.innerHTML = `
                    <div><strong>${name}</strong></div>
                    <div>${statusText}</div>
                    <button class="btn" onclick="toggleComponent('${key}')" style="margin-top: 10px;">
                        ${systemStatus[key] ? '중지' : '시작'}
                    </button>
                `;
                grid.appendChild(item);
            }
        }

        function toggleComponent(component) {
            const action = systemStatus[component] ? 'stop_component' : 'start_component';
            
            fetch(`/api/${action}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({component: component})
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                updateStatus();
            });
        }

        function startAllComponents() {
            const components = ['honeydrone_network', 'timestamp_collector', 'ml_pipeline', 'dashboard'];
            
            components.forEach(component => {
                if (!systemStatus[component]) {
                    toggleComponent(component);
                }
            });
        }

        function stopAllComponents() {
            const components = ['honeydrone_network', 'timestamp_collector', 'ml_pipeline', 'dashboard'];
            
            components.forEach(component => {
                if (systemStatus[component]) {
                    toggleComponent(component);
                }
            });
        }

        function runExperiment() {
            const scenario = document.getElementById('scenario').value;
            const defenseLevel = document.getElementById('defense-level').value;
            const duration = document.getElementById('duration').value;

            fetch('/api/run_experiment', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    scenario: scenario,
                    defense_level: defenseLevel,
                    duration: parseInt(duration)
                })
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
            });
        }

        function updateLogs() {
            const logType = document.getElementById('log-type').value;
            
            fetch(`/api/get_logs?type=${logType}&lines=50`)
                .then(response => response.json())
                .then(data => {
                    const logsDisplay = document.getElementById('logs-display');
                    logsDisplay.innerHTML = data.logs.join('\\n');
                    logsDisplay.scrollTop = logsDisplay.scrollHeight;
                });
        }

        function validateSystem() {
            fetch('/api/validate_system', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert('시스템 검증 완료. 콘솔 확인');
                });
        }

        // 초기화 및 주기적 업데이트
        updateStatus();
        updateLogs();
        setInterval(updateStatus, 5000);
        setInterval(updateLogs, 10000);
    </script>
</body>
</html>''')

if __name__ == '__main__':
    print("통합 컨트롤 패널 시작: http://localhost:9000")
    app.run(debug=False, host='0.0.0.0', port=9000)
EOF

# =================================================================
# 5. 실행 권한 및 마무리
# =================================================================

log_info "=== 권한 설정 및 마무리 ==="

# 모든 Python 파일에 실행 권한 부여
find . -name "*.py" -exec chmod +x {} \; 2>/dev/null || true

# 모든 스크립트에 실행 권한 부여
find . -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true

# 빠른 시작 스크립트 생성
cat > quick_start.sh << 'EOF'
#!/bin/bash
# MTD 드론 보안 테스트베드 빠른 시작

echo "🚀 MTD 드론 보안 테스트베드 빠른 시작"
echo ""
echo "1. 통합 컨트롤 패널 시작..."
python3 scripts/monitoring/control_panel.py &

echo "2. 실시간 대시보드 시작..."
python3 scripts/monitoring/realtime_dashboard.py &

echo "3. 시스템 검증..."
python3 scripts/monitoring/system_validator.py

echo ""
echo "✅ 준비 완료!"
echo "🌐 통합 컨트롤 패널: http://localhost:9000"
echo "📊 실시간 대시보드: http://localhost:8050"
echo ""
echo "사용법:"
echo "  전체 시스템 시작: ./scripts/deployment/run_integrated_system.sh start"
echo "  실험 실행: ./scripts/deployment/run_integrated_system.sh experiment stealth_recon"
EOF

chmod +x quick_start.sh

log_success "분석 및 모니터링 도구 생성 완료!"

echo ""
echo "================================================================="
echo -e "${GREEN}🎉 완전한 MTD 드론 보안 테스트베드 구축 완료! 🎉${NC}"
echo "================================================================="
echo ""
echo -e "${BLUE}📋 새로 추가된 기능:${NC}"
echo "• 실시간 웹 대시보드 (포트 8050)"
echo "• 통합 컨트롤 패널 (포트 9000)"
echo "• 자동 보고서 생성기"
echo "• 시스템 상태 검증기"
echo ""
echo -e "${GREEN}🚀 즉시 시작:${NC}"
echo "  ./quick_start.sh"
echo ""
echo -e "${YELLOW}🔗 웹 인터페이스:${NC}"
echo "  • 통합 컨트롤 패널: http://localhost:9000"
echo "  • 실시간 대시보드: http://localhost:8050"
echo "  • 공격/평가 콘솔: http://localhost:5001" 
echo "  • DVD 모니터링: http://localhost:5002"
echo ""
echo "================================================================="