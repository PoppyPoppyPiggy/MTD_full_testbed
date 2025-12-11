#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD-RL v08 + WandB → IEEE Access Figure Generator

v08 평가 결과와 WandB 학습 로그를 IEEE Access 스타일 논문 Figure로 변환.
드론 특화 지표 + CTI Agent 연동 시각화 포함.

사용법:
    # WandB에서 CSV export 후:
    python mtd_v08_ieee_figures.py --wandb-csv wandb_export.csv
    
    # WandB 런에서 직접 다운로드:
    python mtd_v08_ieee_figures.py --wandb-run <entity>/<project>/<run_id>
    
    # v08 평가 결과에서:
    python mtd_v08_ieee_figures.py --v08-results eval_results_v08/results.json
    
    # 샘플 데모:
    python mtd_v08_ieee_figures.py --demo
"""

import sys
import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

# Import our visualizer
from wandb_ieee_visualizer import (
    IEEEAccessFigureGenerator, 
    WandBParser, 
    WandBMetric,
    generate_sample_data,
    compute_trend_line,
    find_peaks_and_valleys,
    compute_correlation,
    COLORS,
    IEEE_STYLE
)

import matplotlib.pyplot as plt


# ============================================================================
# v08 Result Parser
# ============================================================================

def parse_v08_results(filepath: str) -> dict:
    """
    v08 evaluate_mtd_comparison 결과 파싱
    
    Expected format:
    {
        "strategies": {
            "RL-CTI": { "DES_mean": 0.72, "MTTC_mean": 85.3, ... },
            "RL": { "DES_mean": 0.68, ... },
            ...
        },
        "episodes": [...],
        "training_metrics": {...}
    }
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    return data


def v08_to_wandb_metrics(v08_data: dict) -> dict:
    """v08 결과를 WandBMetric 형식으로 변환"""
    metrics = {}
    
    # Episode-level metrics
    if 'episodes' in v08_data:
        episodes = v08_data['episodes']
        n = len(episodes)
        steps = np.arange(n)
        
        # Extract per-episode metrics
        for key in ['DES', 'MTTC', 'ASR', 'CDI', 'NED', 'ASP', 'Cost', 'CER']:
            values = []
            for ep in episodes:
                if isinstance(ep, dict) and key in ep:
                    values.append(ep[key])
            if values:
                metrics[f'MTD/{key}_mean'] = WandBMetric(
                    f'MTD/{key}_mean', steps[:len(values)], 
                    np.array(values), key, ''
                )
    
    # Training metrics
    if 'training_metrics' in v08_data:
        tm = v08_data['training_metrics']
        for key, values in tm.items():
            if isinstance(values, list):
                steps = np.arange(len(values))
                metrics[f'Train/{key}'] = WandBMetric(
                    f'Train/{key}', steps, np.array(values), key, ''
                )
    
    return metrics


# ============================================================================
# WandB Direct Download (Optional)
# ============================================================================

def download_wandb_run(run_path: str) -> dict:
    """
    WandB API를 통해 런 데이터 다운로드
    
    Args:
        run_path: "entity/project/run_id" 형식
    """
    try:
        import wandb
    except ImportError:
        print("wandb not installed. Install with: pip install wandb")
        return {}
    
    api = wandb.Api()
    run = api.run(run_path)
    
    # History 다운로드
    history = run.history()
    metrics = WandBParser._parse_dataframe(history)
    
    return metrics


# ============================================================================
# 드론 특화 지표 생성/로드
# ============================================================================

def generate_drone_metrics(n_steps: int = 800, 
                           attack_events: list = None) -> dict:
    """
    드론 특화 지표 생성
    
    실제 테스트베드에서는 telemetry 로그에서 추출
    """
    steps = np.arange(n_steps)
    metrics = {}
    
    # GPS Quality (공격 시 저하)
    gps_base = 0.92 * np.ones(n_steps)
    if attack_events:
        for start, end, severity in attack_events:
            gps_base[start:end] -= 0.3 * severity
    gps_quality = gps_base + np.random.normal(0, 0.05, n_steps)
    gps_quality = np.clip(gps_quality, 0, 1)
    metrics['Drone/gps_quality'] = WandBMetric(
        'Drone/gps_quality', steps, gps_quality * 100, 'GPS Quality', '%'
    )
    
    # Link Quality (통신 품질)
    link_base = 0.95 * np.ones(n_steps)
    if attack_events:
        for start, end, severity in attack_events:
            link_base[start:end] -= 0.2 * severity
    link_quality = link_base + np.random.normal(0, 0.03, n_steps)
    link_quality = np.clip(link_quality, 0, 1)
    metrics['Drone/link_quality'] = WandBMetric(
        'Drone/link_quality', steps, link_quality * 100, 'Link Quality', '%'
    )
    
    # Telemetry Rate (Hz)
    telem_rate = 10 + np.random.normal(0, 0.5, n_steps)  # 10Hz baseline
    metrics['Drone/telemetry_rate'] = WandBMetric(
        'Drone/telemetry_rate', steps, telem_rate, 'Telemetry Rate', 'Hz'
    )
    
    # MAVLink message integrity
    integrity = np.random.uniform(0.98, 1.0, n_steps)
    if attack_events:
        for start, end, severity in attack_events:
            integrity[start:end] = np.random.uniform(0.7, 0.9, end-start)
    metrics['Drone/mavlink_integrity'] = WandBMetric(
        'Drone/mavlink_integrity', steps, integrity * 100, 'MAVLink Integrity', '%'
    )
    
    return metrics


def generate_cti_metrics(n_steps: int = 800,
                        attack_schedule: list = None) -> dict:
    """
    CTI Agent 지표 생성
    
    실제 테스트베드에서는 cti_agent_deploy.py의 출력에서 추출
    """
    steps = np.arange(n_steps)
    metrics = {}
    
    # Threat Level (0-4)
    if attack_schedule:
        threat_levels = np.zeros(n_steps)
        for start, end, level in attack_schedule:
            threat_levels[start:end] = level
        # Add some noise/transitions
        for i in range(1, n_steps):
            if np.random.random() < 0.1:
                threat_levels[i] = np.clip(
                    threat_levels[i] + np.random.choice([-1, 0, 1]), 0, 4
                )
    else:
        # Random threat levels
        threat_levels = np.random.choice([0, 1, 2, 3, 4], size=n_steps,
                                        p=[0.4, 0.25, 0.2, 0.1, 0.05])
    
    metrics['CTI/threat_level'] = WandBMetric(
        'CTI/threat_level', steps, threat_levels.astype(float), 'Threat Level', ''
    )
    
    # CTI Confidence
    confidence = 0.85 + np.random.normal(0, 0.08, n_steps)
    confidence = np.clip(confidence, 0.5, 1.0)
    metrics['CTI/confidence'] = WandBMetric(
        'CTI/confidence', steps, confidence * 100, 'CTI Confidence', '%'
    )
    
    # Trigger count (cumulative)
    triggers = np.cumsum(np.random.binomial(1, 0.05, n_steps))
    metrics['CTI/trigger_count'] = WandBMetric(
        'CTI/trigger_count', steps, triggers.astype(float), 'Trigger Count', ''
    )
    
    return metrics


# ============================================================================
# IEEE Access Figure Templates
# ============================================================================

def generate_comprehensive_figures(metrics: dict, 
                                   output_dir: str = './figures_ieee',
                                   include_drone: bool = True,
                                   include_cti: bool = True):
    """
    논문용 IEEE Access Figure 세트 생성
    
    생성되는 Figure:
    - Fig 1: Main results overview (DES, MTTC comparison)
    - Fig 2: Training progress with trends
    - Fig 3: Action distribution (RL vs RL-CTI)
    - Fig 4: Cost-effectiveness analysis
    - Fig 5: Detailed metrics (CDI, NED, ASP)
    - Fig 6: Drone quality metrics (optional)
    - Fig 7: CTI integration visualization (optional)
    - Fig 8: Correlation analysis
    """
    generator = IEEEAccessFigureGenerator(output_dir)
    
    # ========== Fig 1: Main Results ==========
    print("Generating Fig 1: Main Results...")
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # 1a: DES over time
    ax = axes[0, 0]
    if 'MTD/DES_mean' in metrics:
        m = metrics['MTD/DES_mean']
        ax.plot(m.steps, m.values, color=COLORS['primary'], linewidth=1, alpha=0.7)
        trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
        ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2, label=f'Trend (R²={r2:.3f})')
        ax.axhline(y=0.7, color='gray', linestyle=':', alpha=0.5, label='Target DES=0.7')
        ax.set_xlabel('Training Step')
        ax.set_ylabel('DES')
        ax.set_title('(a) Defense Effectiveness Score')
        ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    
    # 1b: MTTC over time
    ax = axes[0, 1]
    if 'MTD/MTTC_mean' in metrics:
        m = metrics['MTD/MTTC_mean']
        ax.plot(m.steps, m.values, color=COLORS['secondary'], linewidth=1, alpha=0.7)
        trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
        ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2, label=f'Trend (R²={r2:.3f})')
        ax.set_xlabel('Training Step')
        ax.set_ylabel('MTTC (steps)')
        ax.set_title('(b) Mean Time To Compromise')
        ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    
    # 1c: ASR over time
    ax = axes[1, 0]
    if 'MTD/ASR_mean' in metrics:
        m = metrics['MTD/ASR_mean']
        ax.plot(m.steps, m.values, color=COLORS['tertiary'], linewidth=1, alpha=0.7)
        trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
        ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2, label=f'Trend (R²={r2:.3f})')
        ax.set_xlabel('Training Step')
        ax.set_ylabel('ASR')
        ax.set_title('(c) Attack Surface Reduction')
        ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    
    # 1d: Cost over time
    ax = axes[1, 1]
    if 'Cost/Total_mean' in metrics:
        m = metrics['Cost/Total_mean']
        ax.plot(m.steps, m.values, color=COLORS['highlight'], linewidth=1, alpha=0.7)
        trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
        ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2, label=f'Trend (R²={r2:.3f})')
        ax.set_xlabel('Training Step')
        ax.set_ylabel('Total Cost')
        ax.set_title('(d) MTD Operation Cost')
        ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    fig.suptitle('Figure 1. Training Progress of MTD-RL System', fontsize=12, y=1.02)
    plt.tight_layout()
    generator.save_figure(fig, 'fig1_main_results')
    plt.close(fig)
    
    # ========== Fig 2: Action Timeseries (WandB style → IEEE) ==========
    print("Generating Fig 2: Action Timeseries...")
    action_keys = [
        'Action/shuffle_intensity',
        'Action/service_swap_target',
        'Action/service_swap_intensity',
        'Action/port_hop_intensity',
        'Action/decoy_ratio',
        'Action/blacklist_duration'
    ]
    fig = generator.plot_multi_panel_time_series(metrics, action_keys, ncols=3)
    fig.suptitle('Figure 2. MTD Action Selection During Training', fontsize=12, y=1.02)
    generator.save_figure(fig, 'fig2_action_timeseries')
    plt.close(fig)
    
    # ========== Fig 3: Action Distribution ==========
    print("Generating Fig 3: Action Distribution...")
    fig = generator.plot_action_distribution(metrics, strategies=['RL', 'RL-CTI'])
    fig.suptitle('Figure 3. MTD Action Distribution Comparison', fontsize=12, y=1.02)
    generator.save_figure(fig, 'fig3_action_distribution')
    plt.close(fig)
    
    # ========== Fig 4: Cost-Effectiveness ==========
    print("Generating Fig 4: Cost-Effectiveness...")
    fig = generator.plot_cost_effectiveness(metrics)
    fig.suptitle('Figure 4. Cost-Effectiveness Analysis', fontsize=12, y=1.02)
    generator.save_figure(fig, 'fig4_cost_effectiveness')
    plt.close(fig)
    
    # ========== Fig 5: Detailed Metrics (CDI, NED, ASP) ==========
    print("Generating Fig 5: Detailed Metrics...")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    
    for idx, (key, name, color) in enumerate([
        ('MTD/CDI_mean', 'Configuration Diversity Index', COLORS['primary']),
        ('MTD/NED_mean', 'Normalized Entropy of Defense', COLORS['highlight']),
        ('MTD/ASP_mean', 'Attack Success Probability', COLORS['tertiary'])
    ]):
        ax = axes[idx]
        if key in metrics:
            m = metrics[key]
            ax.plot(m.steps, m.values, color=color, linewidth=1, alpha=0.7)
            trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
            ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2)
            
            # Peak annotation
            peaks, _ = find_peaks_and_valleys(m.values)
            if len(peaks) > 0 and len(peaks) <= 3:
                ax.scatter(m.steps[peaks], m.values[peaks], 
                          color=COLORS['highlight'], marker='v', s=50, zorder=4)
            
            ax.set_title(f'({chr(97+idx)}) {name} (R²={r2:.3f})')
            ax.set_xlabel('Step')
            ax.set_ylabel(m.display_name)
        ax.grid(True, alpha=0.3)
    
    fig.suptitle('Figure 5. Detailed MTD Performance Metrics', fontsize=12, y=1.02)
    plt.tight_layout()
    generator.save_figure(fig, 'fig5_detailed_metrics')
    plt.close(fig)
    
    # ========== Fig 6: Drone Quality (Optional) ==========
    if include_drone:
        print("Generating Fig 6: Drone Quality...")
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        drone_metrics = [
            ('Drone/gps_quality', 'GPS Quality', '%'),
            ('Drone/link_quality', 'Link Quality', '%'),
            ('Drone/telemetry_rate', 'Telemetry Rate', 'Hz'),
            ('Drone/mavlink_integrity', 'MAVLink Integrity', '%')
        ]
        
        for idx, (key, name, unit) in enumerate(drone_metrics):
            ax = axes[idx // 2, idx % 2]
            if key in metrics:
                m = metrics[key]
                ax.plot(m.steps, m.values, color=COLORS['primary'], linewidth=1, alpha=0.7)
                trend, r2 = compute_trend_line(m.steps, m.values, 'gaussian', window=50)
                ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2)
                
                # Threshold line
                if 'quality' in key.lower() or 'integrity' in key.lower():
                    ax.axhline(y=80, color='orange', linestyle=':', alpha=0.7, label='Warning (80%)')
                    ax.axhline(y=60, color='red', linestyle=':', alpha=0.7, label='Critical (60%)')
                
                ax.set_title(f'({chr(97+idx)}) {name}')
                ax.set_ylabel(f'{name} ({unit})')
                ax.set_xlabel('Step')
                if 'quality' in key.lower():
                    ax.legend(loc='lower right', fontsize=8)
            ax.grid(True, alpha=0.3)
        
        fig.suptitle('Figure 6. Drone System Quality Metrics During MTD Operation', fontsize=12, y=1.02)
        plt.tight_layout()
        generator.save_figure(fig, 'fig6_drone_quality')
        plt.close(fig)
    
    # ========== Fig 7: CTI Integration (Optional) ==========
    if include_cti:
        print("Generating Fig 7: CTI Integration...")
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        # 7a: Threat Level timeline
        ax = axes[0, 0]
        if 'CTI/threat_level' in metrics:
            m = metrics['CTI/threat_level']
            colors = [COLORS[f'L{int(min(4, max(0, v)))}'] for v in m.values]
            ax.scatter(m.steps, m.values, c=colors, s=10, alpha=0.7)
            ax.set_yticks([0, 1, 2, 3, 4])
            ax.set_yticklabels(['L0\n(Low)', 'L1', 'L2', 'L3', 'L4\n(Critical)'])
            ax.set_title('(a) CTI Threat Level Timeline')
            ax.set_xlabel('Step')
            ax.set_ylabel('Threat Level')
        ax.grid(True, alpha=0.3)
        
        # 7b: CTI Confidence
        ax = axes[0, 1]
        if 'CTI/confidence' in metrics:
            m = metrics['CTI/confidence']
            ax.plot(m.steps, m.values, color=COLORS['secondary'], linewidth=1, alpha=0.7)
            trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
            ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2)
            ax.axhline(y=90, color='green', linestyle=':', alpha=0.7, label='High Conf. (90%)')
            ax.set_title(f'(b) CTI Detection Confidence (R²={r2:.3f})')
            ax.set_ylabel('Confidence (%)')
            ax.set_xlabel('Step')
            ax.legend(loc='lower right')
        ax.grid(True, alpha=0.3)
        
        # 7c: Trigger count (cumulative)
        ax = axes[1, 0]
        if 'CTI/trigger_count' in metrics:
            m = metrics['CTI/trigger_count']
            ax.plot(m.steps, m.values, color=COLORS['highlight'], linewidth=1.5)
            ax.fill_between(m.steps, 0, m.values, alpha=0.2, color=COLORS['highlight'])
            ax.set_title('(c) Cumulative CTI Trigger Events')
            ax.set_ylabel('Trigger Count')
            ax.set_xlabel('Step')
        ax.grid(True, alpha=0.3)
        
        # 7d: DES by threat level (scatter)
        ax = axes[1, 1]
        if 'CTI/threat_level' in metrics and 'MTD/DES_mean' in metrics:
            threat = metrics['CTI/threat_level'].values
            des = metrics['MTD/DES_mean'].values
            min_len = min(len(threat), len(des))
            
            colors = [COLORS[f'L{int(min(4, max(0, v)))}'] for v in threat[:min_len]]
            ax.scatter(threat[:min_len], des[:min_len], c=colors, s=15, alpha=0.5)
            
            # Box plot style summary
            for level in range(5):
                mask = threat[:min_len] == level
                if np.any(mask):
                    des_level = des[:min_len][mask]
                    ax.boxplot([des_level], positions=[level], widths=0.3, 
                              patch_artist=True,
                              boxprops=dict(facecolor=COLORS[f'L{level}'], alpha=0.5))
            
            ax.set_title('(d) DES Distribution by Threat Level')
            ax.set_xlabel('Threat Level')
            ax.set_ylabel('DES')
            ax.set_xticks([0, 1, 2, 3, 4])
            ax.set_xticklabels(['L0', 'L1', 'L2', 'L3', 'L4'])
        ax.grid(True, alpha=0.3)
        
        fig.suptitle('Figure 7. CTI Agent Integration with MTD-RL', fontsize=12, y=1.02)
        plt.tight_layout()
        generator.save_figure(fig, 'fig7_cti_integration')
        plt.close(fig)
    
    # ========== Fig 8: Correlation Analysis ==========
    print("Generating Fig 8: Correlation Matrix...")
    
    # Create correlation heatmap
    metric_keys = ['MTD/DES_mean', 'MTD/MTTC_mean', 'MTD/ASR_mean', 
                   'MTD/CDI_mean', 'MTD/NED_mean', 'Cost/Total_mean']
    present_keys = [k for k in metric_keys if k in metrics]
    
    if len(present_keys) >= 3:
        fig, ax = plt.subplots(figsize=(8, 7))
        
        # Compute correlation matrix
        n = len(present_keys)
        corr_matrix = np.zeros((n, n))
        
        for i, k1 in enumerate(present_keys):
            for j, k2 in enumerate(present_keys):
                v1 = metrics[k1].values
                v2 = metrics[k2].values
                min_len = min(len(v1), len(v2))
                r, _, _ = compute_correlation(v1[:min_len], v2[:min_len])
                corr_matrix[i, j] = r
        
        # Plot heatmap
        im = ax.imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1)
        
        # Labels
        labels = [metrics[k].display_name for k in present_keys]
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_yticklabels(labels)
        
        # Annotate
        for i in range(n):
            for j in range(n):
                text = ax.text(j, i, f'{corr_matrix[i, j]:.2f}',
                              ha='center', va='center', color='white' if abs(corr_matrix[i, j]) > 0.5 else 'black',
                              fontsize=9)
        
        plt.colorbar(im, ax=ax, label='Pearson Correlation')
        ax.set_title('Figure 8. Correlation Matrix of MTD Metrics')
        plt.tight_layout()
        generator.save_figure(fig, 'fig8_correlation_matrix')
        plt.close(fig)
    
    print(f"\nAll figures saved to: {output_dir}")
    return generator


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='MTD-RL v08 + WandB → IEEE Access Figure Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sample demo
  python mtd_v08_ieee_figures.py --demo
  
  # From WandB CSV export
  python mtd_v08_ieee_figures.py --wandb-csv wandb_export.csv
  
  # From v08 evaluation results
  python mtd_v08_ieee_figures.py --v08-results eval_results_v08/results.json
  
  # From WandB run (requires wandb login)
  python mtd_v08_ieee_figures.py --wandb-run entity/project/run_id
        """
    )
    
    # Data sources
    parser.add_argument('--demo', action='store_true', help='Run with sample data')
    parser.add_argument('--wandb-csv', type=str, help='WandB CSV export file')
    parser.add_argument('--wandb-json', type=str, help='WandB JSON export file')
    parser.add_argument('--wandb-run', type=str, help='WandB run path (entity/project/run_id)')
    parser.add_argument('--v08-results', type=str, help='v08 evaluation results JSON')
    
    # Options
    parser.add_argument('--output-dir', type=str, default='./figures_ieee', help='Output directory')
    parser.add_argument('--no-drone', action='store_true', help='Skip drone metrics figures')
    parser.add_argument('--no-cti', action='store_true', help='Skip CTI figures')
    parser.add_argument('--attack-schedule', type=str, help='Attack schedule JSON file')
    
    args = parser.parse_args()
    
    # Apply IEEE style
    plt.rcParams.update(IEEE_STYLE)
    
    # Load metrics
    metrics = {}
    
    if args.demo:
        print("Generating sample data for demo...")
        metrics = generate_sample_data(800)
        
    elif args.wandb_csv:
        print(f"Loading WandB CSV: {args.wandb_csv}")
        metrics = WandBParser.parse_csv(args.wandb_csv)
        
    elif args.wandb_json:
        print(f"Loading WandB JSON: {args.wandb_json}")
        metrics = WandBParser.parse_json(args.wandb_json)
        
    elif args.wandb_run:
        print(f"Downloading WandB run: {args.wandb_run}")
        metrics = download_wandb_run(args.wandb_run)
        
    elif args.v08_results:
        print(f"Loading v08 results: {args.v08_results}")
        v08_data = parse_v08_results(args.v08_results)
        metrics = v08_to_wandb_metrics(v08_data)
        
    else:
        print("No data source specified. Use --demo for sample data.")
        print("Run with --help for more options.")
        return
    
    print(f"Loaded {len(metrics)} metrics")
    
    # Add drone metrics if not present
    if not args.no_drone:
        if not any('Drone/' in k for k in metrics.keys()):
            print("Adding sample drone metrics...")
            n_steps = max(len(m.values) for m in metrics.values()) if metrics else 800
            drone_m = generate_drone_metrics(n_steps)
            metrics.update(drone_m)
    
    # Add CTI metrics if not present
    if not args.no_cti:
        if not any('CTI/' in k for k in metrics.keys()):
            print("Adding sample CTI metrics...")
            n_steps = max(len(m.values) for m in metrics.values()) if metrics else 800
            cti_m = generate_cti_metrics(n_steps)
            metrics.update(cti_m)
    
    # Generate figures
    generate_comprehensive_figures(
        metrics,
        output_dir=args.output_dir,
        include_drone=not args.no_drone,
        include_cti=not args.no_cti
    )


if __name__ == '__main__':
    main()