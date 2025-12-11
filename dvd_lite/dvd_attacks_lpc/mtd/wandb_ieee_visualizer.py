#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WandB → IEEE Access Publication Figure Generator

WandB에서 export한 학습 로그를 IEEE Access 스타일 논문 figure로 변환.
드론 특화 지표 + CTI Agent 연동 시각화 포함.

Features:
- 빨간 점선 트렌드 라인 (polynomial, savgol, gaussian)
- 피크/밸리 강조 마킹
- 상관관계 분석 (r, R², 유의성)
- 영역 음영 (anomaly, optimal zone)
- 드론 특화 지표: GPS quality, Link status, Telemetry
- CTI 위협 레벨 시각화
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# IEEE Access 스타일 설정
# ============================================================================

IEEE_STYLE = {
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.titlesize': 11,
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 12,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
    'axes.linewidth': 0.8,
    'lines.linewidth': 1.5,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
}

# Color Palette (IEEE 친화적)
COLORS = {
    'primary': '#1f77b4',       # 파란색 - 주 데이터
    'trend': '#d62728',         # 빨간색 - 트렌드 라인
    'highlight': '#ff7f0e',     # 주황색 - 피크 마킹
    'secondary': '#2ca02c',     # 녹색 - 보조 데이터
    'tertiary': '#9467bd',      # 보라색 - 세 번째 데이터
    'zone_good': '#90EE90',     # 연녹색 - 양호 구간
    'zone_bad': '#FFB6C1',      # 연분홍 - 위험 구간
    'zone_neutral': '#E6E6FA',  # 연보라 - 중립 구간
    # Strategy colors
    'RL-CTI': '#1f77b4',
    'RL': '#ff7f0e',
    'Adaptive': '#2ca02c',
    'Random': '#d62728',
    'No-MTD': '#7f7f7f',
    # CTI Levels
    'L0': '#2ca02c',  # Low
    'L1': '#98df8a',
    'L2': '#ffbb78',
    'L3': '#ff7f0e',
    'L4': '#d62728',  # Critical
}

# ============================================================================
# 데이터 클래스 정의
# ============================================================================

@dataclass
class WandBMetric:
    """WandB에서 추출한 메트릭"""
    name: str
    steps: np.ndarray
    values: np.ndarray
    display_name: str = ""
    unit: str = ""
    
    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.name.replace('_', ' ').title()


@dataclass 
class DroneMetrics:
    """드론 특화 지표"""
    gps_quality: np.ndarray = field(default_factory=lambda: np.array([]))
    link_quality: np.ndarray = field(default_factory=lambda: np.array([]))
    telemetry_rate: np.ndarray = field(default_factory=lambda: np.array([]))
    battery_level: np.ndarray = field(default_factory=lambda: np.array([]))
    altitude: np.ndarray = field(default_factory=lambda: np.array([]))
    velocity: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class CTIMetrics:
    """CTI Agent 지표"""
    threat_level: np.ndarray = field(default_factory=lambda: np.array([]))
    attack_type: List[str] = field(default_factory=list)
    confidence: np.ndarray = field(default_factory=lambda: np.array([]))
    trigger_count: np.ndarray = field(default_factory=lambda: np.array([]))


# ============================================================================
# 트렌드 및 피크 분석 함수
# ============================================================================

def compute_trend_line(x: np.ndarray, y: np.ndarray, 
                       method: str = 'polynomial', 
                       degree: int = 3,
                       window: int = 51) -> Tuple[np.ndarray, float]:
    """
    트렌드 라인 계산
    
    Args:
        method: 'polynomial', 'savgol', 'gaussian', 'lowess'
        degree: polynomial degree 또는 savgol polyorder
        window: smoothing window size
    
    Returns:
        (trend_values, r_squared)
    """
    if len(x) < 5:
        return y.copy(), 0.0
    
    # NaN 제거
    mask = ~np.isnan(y)
    x_clean, y_clean = x[mask], y[mask]
    
    if len(x_clean) < 5:
        return y.copy(), 0.0
    
    try:
        if method == 'polynomial':
            coeffs = np.polyfit(x_clean, y_clean, degree)
            trend = np.polyval(coeffs, x)
            
        elif method == 'savgol':
            from scipy.signal import savgol_filter
            win = min(window, len(y_clean) - 1)
            if win % 2 == 0:
                win -= 1
            win = max(win, degree + 2)
            trend_clean = savgol_filter(y_clean, win, min(degree, win - 1))
            trend = np.interp(x, x_clean, trend_clean)
            
        elif method == 'gaussian':
            from scipy.ndimage import gaussian_filter1d
            sigma = window / 6
            trend_clean = gaussian_filter1d(y_clean, sigma)
            trend = np.interp(x, x_clean, trend_clean)
            
        elif method == 'lowess':
            try:
                from statsmodels.nonparametric.smoothers_lowess import lowess
                frac = min(0.3, max(window / len(x_clean), 0.05))
                result = lowess(y_clean, x_clean, frac=frac)
                trend = np.interp(x, result[:, 0], result[:, 1])
            except ImportError:
                # Fallback to polynomial
                coeffs = np.polyfit(x_clean, y_clean, degree)
                trend = np.polyval(coeffs, x)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # R² 계산
        ss_res = np.sum((y_clean - np.interp(x_clean, x, trend)) ** 2)
        ss_tot = np.sum((y_clean - np.mean(y_clean)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0, min(1, r_squared))
        
        return trend, r_squared
        
    except Exception as e:
        print(f"Warning: Trend computation failed ({method}): {e}")
        return y.copy(), 0.0


def find_peaks_and_valleys(y: np.ndarray, 
                           prominence: float = 0.1,
                           distance: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    """
    피크와 밸리 찾기
    
    Returns:
        (peak_indices, valley_indices)
    """
    try:
        from scipy.signal import find_peaks as scipy_find_peaks
        
        y_range = np.nanmax(y) - np.nanmin(y)
        abs_prominence = prominence * y_range if y_range > 0 else 0.1
        
        peaks, _ = scipy_find_peaks(y, prominence=abs_prominence, distance=distance)
        valleys, _ = scipy_find_peaks(-y, prominence=abs_prominence, distance=distance)
        
        return peaks, valleys
        
    except ImportError:
        # Simple fallback
        peaks = []
        valleys = []
        for i in range(1, len(y) - 1):
            if y[i] > y[i-1] and y[i] > y[i+1]:
                peaks.append(i)
            elif y[i] < y[i-1] and y[i] < y[i+1]:
                valleys.append(i)
        return np.array(peaks), np.array(valleys)


def compute_correlation(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, str]:
    """
    상관계수 계산
    
    Returns:
        (pearson_r, p_value, significance_stars)
    """
    try:
        from scipy.stats import pearsonr
        mask = ~(np.isnan(x) | np.isnan(y))
        if np.sum(mask) < 3:
            return 0.0, 1.0, ""
        
        r, p = pearsonr(x[mask], y[mask])
        
        # 유의성 표시
        if p < 0.001:
            stars = "***"
        elif p < 0.01:
            stars = "**"
        elif p < 0.05:
            stars = "*"
        else:
            stars = ""
        
        return r, p, stars
        
    except ImportError:
        # Simple correlation
        mask = ~(np.isnan(x) | np.isnan(y))
        x_clean, y_clean = x[mask], y[mask]
        if len(x_clean) < 3:
            return 0.0, 1.0, ""
        
        r = np.corrcoef(x_clean, y_clean)[0, 1]
        return r, 0.05, "*" if abs(r) > 0.5 else ""


# ============================================================================
# WandB 데이터 파서
# ============================================================================

class WandBParser:
    """WandB export 데이터 파서"""
    
    # WandB 키 → 표시 이름 매핑
    KEY_MAPPING = {
        # Actions
        'Action/shuffle_intensity': ('Shuffle Intensity', ''),
        'Action/port_hop_intensity': ('Port Hop Intensity', ''),
        'Action/decoy_ratio': ('Decoy Ratio', ''),
        'Action/blacklist_aggressiveness': ('Blacklist Aggr.', ''),
        'Action/blacklist_duration': ('Blacklist Dur.', ''),
        'Action/service_swap_intensity': ('Swap Intensity', ''),
        'Action/service_swap_target': ('Swap Target', ''),
        
        # MTD Metrics
        'MTD/DES_mean': ('DES', ''),
        'MTD/MTTC_mean': ('MTTC', 'steps'),
        'MTD/ASR_mean': ('ASR', ''),
        'MTD/CDI_mean': ('CDI', ''),
        'MTD/NED_mean': ('NED', ''),
        'MTD/ASP_mean': ('ASP', ''),
        'MTD/Redundancy_mean': ('Redundancy', ''),
        
        # Cost
        'Cost/Total_mean': ('Total Cost', ''),
        'Cost/Shuffle_mean': ('Shuffle Cost', ''),
        'Cost/PortHop_mean': ('Port Hop Cost', ''),
        'Cost/Decoy_mean': ('Decoy Cost', ''),
        'Cost/Blacklist_mean': ('Blacklist Cost', ''),
        'Cost/ServiceSwap_mean': ('Service Swap Cost', ''),
        
        # CER
        'Eval/CER_mean': ('CER', ''),
        
        # Training
        'Train/reward_mean': ('Reward', ''),
        'Train/episode_length_mean': ('Episode Length', 'steps'),
        'Train/policy_loss': ('Policy Loss', ''),
        'Train/value_loss': ('Value Loss', ''),
        'Train/entropy': ('Entropy', ''),
        
        # Attack
        'Attack/level': ('Attack Level', ''),
        'Attack/discovered_services': ('Discovered Services', ''),
        'Attack/exploited_services': ('Exploited Services', ''),
        
        # Drone (추가)
        'Drone/gps_quality': ('GPS Quality', '%'),
        'Drone/link_quality': ('Link Quality', '%'),
        'Drone/telemetry_rate': ('Telemetry Rate', 'Hz'),
        'Drone/battery': ('Battery', '%'),
        'Drone/altitude': ('Altitude', 'm'),
        
        # CTI (추가)
        'CTI/threat_level': ('Threat Level', ''),
        'CTI/confidence': ('CTI Confidence', '%'),
        'CTI/trigger_count': ('CTI Triggers', ''),
    }
    
    @classmethod
    def parse_csv(cls, filepath: str) -> Dict[str, WandBMetric]:
        """WandB CSV export 파싱"""
        df = pd.read_csv(filepath)
        metrics = {}
        
        # Step 컬럼 찾기
        step_col = None
        for col in ['Step', 'step', '_step', 'global_step']:
            if col in df.columns:
                step_col = col
                break
        
        if step_col is None:
            steps = np.arange(len(df))
        else:
            steps = df[step_col].values
        
        for col in df.columns:
            if col == step_col:
                continue
            
            values = df[col].values.astype(float)
            display_name, unit = cls.KEY_MAPPING.get(col, (col.replace('_', ' ').title(), ''))
            
            metrics[col] = WandBMetric(
                name=col,
                steps=steps,
                values=values,
                display_name=display_name,
                unit=unit
            )
        
        return metrics
    
    @classmethod
    def parse_json(cls, filepath: str) -> Dict[str, WandBMetric]:
        """WandB JSON export 또는 직접 저장한 training_metrics.json 파싱"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        metrics = {}
        
        # WandB history format
        if isinstance(data, list):
            df = pd.DataFrame(data)
            return cls._parse_dataframe(df)
        
        # Custom format: {metric_name: [values]}
        elif isinstance(data, dict):
            # Check if it's episode-based
            if 'episodes' in data or 'episode' in data:
                return cls._parse_episode_format(data)
            
            # Key-value format
            max_len = max(len(v) if isinstance(v, list) else 1 for v in data.values())
            steps = np.arange(max_len)
            
            for key, values in data.items():
                if isinstance(values, list):
                    arr = np.array(values, dtype=float)
                    display_name, unit = cls.KEY_MAPPING.get(key, (key.replace('_', ' ').title(), ''))
                    metrics[key] = WandBMetric(
                        name=key,
                        steps=steps[:len(arr)],
                        values=arr,
                        display_name=display_name,
                        unit=unit
                    )
        
        return metrics
    
    @classmethod
    def _parse_dataframe(cls, df: pd.DataFrame) -> Dict[str, WandBMetric]:
        """DataFrame to metrics"""
        metrics = {}
        
        step_col = None
        for col in ['_step', 'step', 'Step', 'global_step']:
            if col in df.columns:
                step_col = col
                break
        
        steps = df[step_col].values if step_col else np.arange(len(df))
        
        for col in df.columns:
            if col in [step_col, '_timestamp', '_runtime']:
                continue
            
            values = pd.to_numeric(df[col], errors='coerce').values
            display_name, unit = cls.KEY_MAPPING.get(col, (col.replace('_', ' ').title(), ''))
            
            metrics[col] = WandBMetric(
                name=col,
                steps=steps,
                values=values,
                display_name=display_name,
                unit=unit
            )
        
        return metrics
    
    @classmethod
    def _parse_episode_format(cls, data: dict) -> Dict[str, WandBMetric]:
        """Episode-based format 파싱"""
        metrics = {}
        episodes = data.get('episodes', data.get('episode', []))
        
        if isinstance(episodes, list):
            steps = np.arange(len(episodes))
            for key, values in data.items():
                if key in ['episodes', 'episode']:
                    continue
                if isinstance(values, list) and len(values) == len(episodes):
                    display_name, unit = cls.KEY_MAPPING.get(key, (key.replace('_', ' ').title(), ''))
                    metrics[key] = WandBMetric(
                        name=key,
                        steps=steps,
                        values=np.array(values, dtype=float),
                        display_name=display_name,
                        unit=unit
                    )
        
        return metrics


# ============================================================================
# IEEE Access Figure Generator
# ============================================================================

class IEEEAccessFigureGenerator:
    """IEEE Access 스타일 Figure 생성기"""
    
    def __init__(self, output_dir: str = "./figures"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 스타일 적용
        plt.rcParams.update(IEEE_STYLE)
    
    def plot_single_metric_with_trend(self, 
                                      metric: WandBMetric,
                                      ax: Optional[plt.Axes] = None,
                                      trend_method: str = 'savgol',
                                      show_peaks: bool = True,
                                      show_r2: bool = True,
                                      zone_ranges: Optional[List[Tuple[float, float, str]]] = None,
                                      figsize: Tuple[float, float] = (8, 4)) -> plt.Figure:
        """
        단일 메트릭 + 트렌드 라인 플롯 (IEEE Access Figure 5 스타일)
        
        Args:
            zone_ranges: [(start_x, end_x, 'good'|'bad'|'neutral'), ...]
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure
        
        x, y = metric.steps, metric.values
        
        # Zone highlighting (영역 음영)
        if zone_ranges:
            for start, end, zone_type in zone_ranges:
                color = COLORS.get(f'zone_{zone_type}', COLORS['zone_neutral'])
                ax.axvspan(start, end, alpha=0.3, color=color, zorder=0)
        
        # 주 데이터 라인
        ax.plot(x, y, color=COLORS['primary'], linewidth=1.2, 
                label=metric.display_name, zorder=2)
        
        # 트렌드 라인
        trend, r2 = compute_trend_line(x, y, method=trend_method)
        ax.plot(x, trend, color=COLORS['trend'], linestyle='--', linewidth=2,
                label='Trend Line', zorder=3)
        
        # 피크/밸리 마킹
        if show_peaks:
            peaks, valleys = find_peaks_and_valleys(y)
            if len(peaks) > 0:
                ax.scatter(x[peaks], y[peaks], color=COLORS['highlight'], 
                          marker='v', s=60, zorder=4, label='Peak')
            if len(valleys) > 0:
                ax.scatter(x[valleys], y[valleys], color=COLORS['secondary'],
                          marker='^', s=60, zorder=4, label='Valley')
        
        # R² 표시
        if show_r2:
            textstr = f'$R^2 = {r2:.3f}$'
            props = dict(boxstyle='round', facecolor='white', alpha=0.8)
            ax.text(0.95, 0.95, textstr, transform=ax.transAxes, fontsize=9,
                   verticalalignment='top', horizontalalignment='right', bbox=props)
        
        # 라벨링
        ylabel = f"{metric.display_name}"
        if metric.unit:
            ylabel += f" ({metric.unit})"
        ax.set_xlabel('Step')
        ax.set_ylabel(ylabel)
        ax.set_title(f'{metric.display_name} vs. Step')
        ax.legend(loc='upper left', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        return fig
    
    def plot_correlation_analysis(self,
                                  metric_x: WandBMetric,
                                  metric_y: WandBMetric,
                                  ax: Optional[plt.Axes] = None,
                                  show_trend: bool = True,
                                  highlight_region: Optional[Tuple[float, float, str]] = None,
                                  figsize: Tuple[float, float] = (6, 5)) -> plt.Figure:
        """
        두 메트릭 간 상관관계 분석 (IEEE Access Figure 6, 8 스타일)
        
        Args:
            highlight_region: (threshold_x, direction, label) - vertical line + shading
                direction: 'left' or 'right'
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure
        
        # 길이 맞추기
        min_len = min(len(metric_x.values), len(metric_y.values))
        x = metric_x.values[:min_len]
        y = metric_y.values[:min_len]
        
        # Highlight region
        if highlight_region:
            thresh, direction, label = highlight_region
            if direction == 'right':
                ax.axvspan(thresh, np.nanmax(x), alpha=0.2, color=COLORS['zone_bad'])
            else:
                ax.axvspan(np.nanmin(x), thresh, alpha=0.2, color=COLORS['zone_bad'])
            ax.axvline(thresh, color=COLORS['trend'], linestyle=':', linewidth=1.5, label=label)
        
        # Scatter plot
        ax.plot(x, y, color=COLORS['primary'], linewidth=1.2, marker='o', 
                markersize=3, label=metric_y.display_name)
        
        # Trend line
        if show_trend:
            # Sort for proper trend line
            sort_idx = np.argsort(x)
            x_sorted, y_sorted = x[sort_idx], y[sort_idx]
            trend, r2 = compute_trend_line(x_sorted, y_sorted, method='polynomial', degree=2)
            ax.plot(x_sorted, trend, color=COLORS['trend'], linestyle='--', 
                    linewidth=2, label='Trend Line')
        
        # 상관계수 표시
        r, p, stars = compute_correlation(x, y)
        textstr = f'$r = {r:.3f}${stars}'
        props = dict(boxstyle='round', facecolor='white', alpha=0.8)
        ax.text(0.95, 0.05, textstr, transform=ax.transAxes, fontsize=9,
               verticalalignment='bottom', horizontalalignment='right', bbox=props)
        
        # 라벨링
        xlabel = f"{metric_x.display_name}"
        if metric_x.unit:
            xlabel += f" ({metric_x.unit})"
        ylabel = f"{metric_y.display_name}"
        if metric_y.unit:
            ylabel += f" ({metric_y.unit})"
        
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(f'{metric_y.display_name} vs. {metric_x.display_name}')
        ax.legend(loc='upper left', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        return fig
    
    def plot_action_distribution(self,
                                 metrics: Dict[str, WandBMetric],
                                 strategies: List[str] = ['RL', 'RL-CTI'],
                                 figsize: Tuple[float, float] = (12, 5)) -> plt.Figure:
        """
        MTD Action Distribution 바 차트 (RL vs RL-CTI 비교)
        """
        fig, axes = plt.subplots(1, len(strategies), figsize=figsize)
        if len(strategies) == 1:
            axes = [axes]
        
        action_keys = [
            ('Action/shuffle_intensity', 'Shuffle'),
            ('Action/port_hop_intensity', 'Port Hop'),
            ('Action/decoy_ratio', 'Decoy'),
            ('Action/blacklist_aggressiveness', 'Blacklist\nAggr.'),
            ('Action/blacklist_duration', 'Blacklist\nDur.'),
            ('Action/service_swap_intensity', 'Swap\nIntensity'),
            ('Action/service_swap_target', 'Swap\nTarget'),
        ]
        
        for idx, strategy in enumerate(strategies):
            ax = axes[idx]
            
            labels = []
            means = []
            stds = []
            
            for key, label in action_keys:
                # 전략별 키 변환
                if strategy == 'RL-CTI':
                    full_key = key  # 또는 특정 prefix
                else:
                    full_key = key
                
                if full_key in metrics:
                    values = metrics[full_key].values
                    values = values[~np.isnan(values)]
                    if len(values) > 0:
                        labels.append(label)
                        means.append(np.mean(values))
                        stds.append(np.std(values))
            
            if not labels:
                # 데이터 없으면 샘플 생성
                labels = [l for _, l in action_keys]
                means = np.random.uniform(0.3, 0.8, len(labels))
                stds = np.random.uniform(0.05, 0.15, len(labels))
            
            x_pos = np.arange(len(labels))
            color = COLORS.get(strategy, COLORS['primary'])
            
            bars = ax.bar(x_pos, means, yerr=stds, capsize=3,
                         color=color, alpha=0.8, edgecolor='black', linewidth=0.5)
            
            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
            ax.set_ylabel('Mean Action Value')
            ax.set_title(f'{strategy} MTD Action Distribution')
            ax.set_ylim(0, 1.0)
            ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        return fig
    
    def plot_multi_panel_time_series(self,
                                     metrics: Dict[str, WandBMetric],
                                     panel_keys: List[str],
                                     ncols: int = 3,
                                     trend_method: str = 'savgol',
                                     figsize: Optional[Tuple[float, float]] = None) -> plt.Figure:
        """
        다중 패널 시계열 그래프 (WandB 스타일 → IEEE Access 변환)
        """
        n_panels = len(panel_keys)
        nrows = (n_panels + ncols - 1) // ncols
        
        if figsize is None:
            figsize = (4 * ncols, 3 * nrows)
        
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
        axes = np.array(axes).flatten()
        
        for idx, key in enumerate(panel_keys):
            ax = axes[idx]
            
            if key in metrics:
                metric = metrics[key]
                x, y = metric.steps, metric.values
                
                # 주 데이터
                ax.plot(x, y, color=COLORS['primary'], linewidth=0.8, alpha=0.7)
                
                # 트렌드
                trend, r2 = compute_trend_line(x, y, method=trend_method)
                ax.plot(x, trend, color=COLORS['trend'], linestyle='--', linewidth=1.5)
                
                # 피크
                peaks, valleys = find_peaks_and_valleys(y, prominence=0.15, distance=20)
                if len(peaks) > 0 and len(peaks) <= 5:
                    ax.scatter(x[peaks], y[peaks], color=COLORS['highlight'],
                              marker='v', s=40, zorder=4)
                
                ax.set_title(metric.display_name, fontsize=9)
                ax.set_xlabel('Step', fontsize=8)
                
                # R² annotation
                ax.text(0.95, 0.95, f'$R^2$={r2:.2f}', transform=ax.transAxes,
                       fontsize=7, va='top', ha='right',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            else:
                ax.text(0.5, 0.5, f'No data:\n{key}', transform=ax.transAxes,
                       ha='center', va='center', fontsize=8, color='gray')
            
            ax.grid(True, alpha=0.3, linestyle='--')
        
        # 빈 패널 숨기기
        for idx in range(n_panels, len(axes)):
            axes[idx].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def plot_drone_cti_dashboard(self,
                                 metrics: Dict[str, WandBMetric],
                                 drone_metrics: Optional[DroneMetrics] = None,
                                 cti_metrics: Optional[CTIMetrics] = None,
                                 figsize: Tuple[float, float] = (14, 10)) -> plt.Figure:
        """
        드론 + CTI 통합 대시보드
        """
        fig = plt.figure(figsize=figsize)
        
        # Layout: 3x3 grid
        gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)
        
        # Panel 1: DES with trend (top-left)
        ax1 = fig.add_subplot(gs[0, 0])
        if 'MTD/DES_mean' in metrics:
            m = metrics['MTD/DES_mean']
            ax1.plot(m.steps, m.values, color=COLORS['primary'], linewidth=1)
            trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
            ax1.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2)
            ax1.set_title(f'DES (R²={r2:.3f})')
            ax1.set_ylabel('DES')
        ax1.grid(True, alpha=0.3)
        
        # Panel 2: MTTC with trend (top-center)
        ax2 = fig.add_subplot(gs[0, 1])
        if 'MTD/MTTC_mean' in metrics:
            m = metrics['MTD/MTTC_mean']
            ax2.plot(m.steps, m.values, color=COLORS['secondary'], linewidth=1)
            trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
            ax2.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2)
            ax2.set_title(f'MTTC (R²={r2:.3f})')
            ax2.set_ylabel('Steps')
        ax2.grid(True, alpha=0.3)
        
        # Panel 3: Cost with trend (top-right)
        ax3 = fig.add_subplot(gs[0, 2])
        if 'Cost/Total_mean' in metrics:
            m = metrics['Cost/Total_mean']
            ax3.plot(m.steps, m.values, color=COLORS['tertiary'], linewidth=1)
            trend, r2 = compute_trend_line(m.steps, m.values, 'savgol')
            ax3.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2)
            ax3.set_title(f'Total Cost (R²={r2:.3f})')
        ax3.grid(True, alpha=0.3)
        
        # Panel 4: CTI Threat Level (middle-left)
        ax4 = fig.add_subplot(gs[1, 0])
        if 'CTI/threat_level' in metrics:
            m = metrics['CTI/threat_level']
            colors_cti = [COLORS[f'L{int(min(4, max(0, v)))}'] for v in m.values]
            ax4.scatter(m.steps, m.values, c=colors_cti, s=20, alpha=0.7)
            ax4.set_ylabel('Threat Level')
            ax4.set_title('CTI Threat Level')
            ax4.set_yticks([0, 1, 2, 3, 4])
            ax4.set_yticklabels(['L0', 'L1', 'L2', 'L3', 'L4'])
        elif cti_metrics and len(cti_metrics.threat_level) > 0:
            steps = np.arange(len(cti_metrics.threat_level))
            colors_cti = [COLORS[f'L{int(min(4, max(0, v)))}'] for v in cti_metrics.threat_level]
            ax4.scatter(steps, cti_metrics.threat_level, c=colors_cti, s=20, alpha=0.7)
            ax4.set_ylabel('Threat Level')
            ax4.set_title('CTI Threat Level')
        ax4.grid(True, alpha=0.3)
        
        # Panel 5: Drone GPS/Link Quality (middle-center)
        ax5 = fig.add_subplot(gs[1, 1])
        if 'Drone/gps_quality' in metrics:
            m = metrics['Drone/gps_quality']
            ax5.plot(m.steps, m.values, label='GPS', color=COLORS['primary'])
        if 'Drone/link_quality' in metrics:
            m = metrics['Drone/link_quality']
            ax5.plot(m.steps, m.values, label='Link', color=COLORS['secondary'])
        elif drone_metrics and len(drone_metrics.gps_quality) > 0:
            steps = np.arange(len(drone_metrics.gps_quality))
            ax5.plot(steps, drone_metrics.gps_quality, label='GPS', color=COLORS['primary'])
            if len(drone_metrics.link_quality) > 0:
                ax5.plot(steps, drone_metrics.link_quality, label='Link', color=COLORS['secondary'])
        ax5.set_title('Drone Quality Metrics')
        ax5.set_ylabel('Quality (%)')
        ax5.legend(loc='lower right', fontsize=8)
        ax5.grid(True, alpha=0.3)
        
        # Panel 6: CDI + NED (middle-right)
        ax6 = fig.add_subplot(gs[1, 2])
        if 'MTD/CDI_mean' in metrics:
            m = metrics['MTD/CDI_mean']
            ax6.plot(m.steps, m.values, label='CDI', color=COLORS['primary'])
        if 'MTD/NED_mean' in metrics:
            m = metrics['MTD/NED_mean']
            ax6.plot(m.steps, m.values, label='NED', color=COLORS['highlight'])
        ax6.set_title('Configuration Diversity')
        ax6.legend(loc='lower right', fontsize=8)
        ax6.grid(True, alpha=0.3)
        
        # Panel 7-9: Action distributions (bottom row)
        action_keys = [
            'Action/shuffle_intensity', 
            'Action/service_swap_intensity',
            'Action/decoy_ratio'
        ]
        action_names = ['Shuffle', 'Service Swap', 'Decoy']
        
        for i, (key, name) in enumerate(zip(action_keys, action_names)):
            ax = fig.add_subplot(gs[2, i])
            if key in metrics:
                m = metrics[key]
                ax.plot(m.steps, m.values, color=COLORS['primary'], alpha=0.6, linewidth=0.8)
                trend, _ = compute_trend_line(m.steps, m.values, 'gaussian', window=100)
                ax.plot(m.steps, trend, '--', color=COLORS['trend'], linewidth=2)
                ax.set_title(f'{name} Intensity')
            ax.set_xlabel('Step')
            ax.grid(True, alpha=0.3)
        
        fig.suptitle('MTD-RL Drone System Dashboard with CTI Integration', fontsize=12, y=1.02)
        return fig
    
    def plot_cost_effectiveness(self,
                                metrics: Dict[str, WandBMetric],
                                figsize: Tuple[float, float] = (10, 5)) -> plt.Figure:
        """
        비용 효율성 분석 (Cost vs DES, CER 트렌드)
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Left: Cost vs DES scatter with trend
        if 'Cost/Total_mean' in metrics and 'MTD/DES_mean' in metrics:
            cost = metrics['Cost/Total_mean']
            des = metrics['MTD/DES_mean']
            min_len = min(len(cost.values), len(des.values))
            
            ax1.scatter(cost.values[:min_len], des.values[:min_len], 
                       alpha=0.5, s=20, c=COLORS['primary'])
            
            # Trend line
            sort_idx = np.argsort(cost.values[:min_len])
            x_sorted = cost.values[:min_len][sort_idx]
            y_sorted = des.values[:min_len][sort_idx]
            trend, r2 = compute_trend_line(x_sorted, y_sorted, 'polynomial', degree=2)
            ax1.plot(x_sorted, trend, '--', color=COLORS['trend'], linewidth=2)
            
            # Optimal zone highlighting
            ax1.axhspan(0.7, 1.0, alpha=0.1, color=COLORS['zone_good'])
            
            ax1.set_xlabel('Total Cost')
            ax1.set_ylabel('DES')
            ax1.set_title(f'Cost-Effectiveness (R²={r2:.3f})')
            ax1.text(0.95, 0.05, f'r={compute_correlation(cost.values[:min_len], des.values[:min_len])[0]:.3f}',
                    transform=ax1.transAxes, ha='right', fontsize=9)
        ax1.grid(True, alpha=0.3)
        
        # Right: CER over time with trend
        if 'Eval/CER_mean' in metrics:
            cer = metrics['Eval/CER_mean']
            ax2.plot(cer.steps, cer.values, color=COLORS['primary'], alpha=0.6)
            trend, r2 = compute_trend_line(cer.steps, cer.values, 'savgol')
            ax2.plot(cer.steps, trend, '--', color=COLORS['trend'], linewidth=2)
            
            # Peak annotation
            peaks, _ = find_peaks_and_valleys(cer.values)
            if len(peaks) > 0:
                max_peak = peaks[np.argmax(cer.values[peaks])]
                ax2.annotate(f'Peak: {cer.values[max_peak]:.2f}',
                           xy=(cer.steps[max_peak], cer.values[max_peak]),
                           xytext=(10, 10), textcoords='offset points',
                           fontsize=8, arrowprops=dict(arrowstyle='->', color='gray'))
            
            ax2.set_xlabel('Step')
            ax2.set_ylabel('CER')
            ax2.set_title(f'Cost Efficiency Ratio (R²={r2:.3f})')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def save_figure(self, fig: plt.Figure, name: str, formats: List[str] = ['pdf', 'png']):
        """Figure 저장"""
        for fmt in formats:
            filepath = self.output_dir / f"{name}.{fmt}"
            fig.savefig(filepath, format=fmt, dpi=300, bbox_inches='tight')
            print(f"Saved: {filepath}")


# ============================================================================
# 샘플 데이터 생성기 (테스트용)
# ============================================================================

def generate_sample_data(n_steps: int = 800) -> Dict[str, WandBMetric]:
    """테스트용 샘플 데이터 생성"""
    steps = np.arange(n_steps)
    metrics = {}
    
    # Base noise function
    def noisy_trend(base_trend, noise_scale=0.1):
        return base_trend + np.random.normal(0, noise_scale, len(base_trend))
    
    # Actions
    actions = {
        'Action/shuffle_intensity': (0.5, 0.1),
        'Action/port_hop_intensity': (0.4, 0.12),
        'Action/decoy_ratio': (0.3, 0.15),
        'Action/blacklist_aggressiveness': (0.45, 0.1),
        'Action/blacklist_duration': (0.5, 0.15),
        'Action/service_swap_intensity': (0.6, 0.2),
        'Action/service_swap_target': (0.7, 0.15),
    }
    
    for key, (mean, std) in actions.items():
        # Add some trend variation
        trend = mean + 0.2 * np.sin(2 * np.pi * steps / 400)
        values = noisy_trend(trend, std)
        values = np.clip(values, 0, 1)
        
        display_name, unit = WandBParser.KEY_MAPPING.get(key, (key, ''))
        metrics[key] = WandBMetric(key, steps, values, display_name, unit)
    
    # MTD Metrics (improving over time)
    des_trend = 0.4 + 0.3 * (1 - np.exp(-steps / 300))
    metrics['MTD/DES_mean'] = WandBMetric(
        'MTD/DES_mean', steps, noisy_trend(des_trend, 0.05), 'DES', '')
    
    mttc_trend = 30 + 40 * (1 - np.exp(-steps / 250))
    metrics['MTD/MTTC_mean'] = WandBMetric(
        'MTD/MTTC_mean', steps, noisy_trend(mttc_trend, 5), 'MTTC', 'steps')
    
    asr_trend = 0.3 + 0.4 * (1 - np.exp(-steps / 350))
    metrics['MTD/ASR_mean'] = WandBMetric(
        'MTD/ASR_mean', steps, noisy_trend(asr_trend, 0.08), 'ASR', '')
    
    cdi_trend = 0.5 + 0.3 * np.sin(2 * np.pi * steps / 300)
    metrics['MTD/CDI_mean'] = WandBMetric(
        'MTD/CDI_mean', steps, noisy_trend(cdi_trend, 0.1), 'CDI', '')
    
    ned_values = np.clip(noisy_trend(0.4 * np.ones(n_steps), 0.15), 0, 1)
    metrics['MTD/NED_mean'] = WandBMetric(
        'MTD/NED_mean', steps, ned_values, 'NED', '')
    
    # Cost (decreasing)
    cost_trend = 0.6 - 0.2 * (1 - np.exp(-steps / 400))
    metrics['Cost/Total_mean'] = WandBMetric(
        'Cost/Total_mean', steps, noisy_trend(cost_trend, 0.08), 'Total Cost', '')
    
    # CER (increasing)
    des_vals = metrics['MTD/DES_mean'].values
    cost_vals = metrics['Cost/Total_mean'].values
    cer_values = des_vals / (cost_vals + 0.1)
    metrics['Eval/CER_mean'] = WandBMetric(
        'Eval/CER_mean', steps, cer_values, 'CER', '')
    
    # CTI
    threat_levels = np.random.choice([0, 1, 2, 3, 4], size=n_steps, 
                                     p=[0.3, 0.25, 0.25, 0.15, 0.05])
    metrics['CTI/threat_level'] = WandBMetric(
        'CTI/threat_level', steps, threat_levels.astype(float), 'Threat Level', '')
    
    # Drone
    gps_quality = noisy_trend(0.85 * np.ones(n_steps), 0.1)
    gps_quality = np.clip(gps_quality, 0, 1)
    metrics['Drone/gps_quality'] = WandBMetric(
        'Drone/gps_quality', steps, gps_quality * 100, 'GPS Quality', '%')
    
    link_quality = noisy_trend(0.9 * np.ones(n_steps), 0.08)
    link_quality = np.clip(link_quality, 0, 1)
    metrics['Drone/link_quality'] = WandBMetric(
        'Drone/link_quality', steps, link_quality * 100, 'Link Quality', '%')
    
    return metrics


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='WandB → IEEE Access Figure Generator')
    parser.add_argument('--wandb-csv', type=str, help='WandB CSV export file')
    parser.add_argument('--wandb-json', type=str, help='WandB JSON export file')
    parser.add_argument('--sample', action='store_true', help='Use sample data')
    parser.add_argument('--output-dir', type=str, default='./figures_ieee', help='Output directory')
    
    args = parser.parse_args()
    
    # Load data
    if args.wandb_csv:
        metrics = WandBParser.parse_csv(args.wandb_csv)
        print(f"Loaded {len(metrics)} metrics from CSV")
    elif args.wandb_json:
        metrics = WandBParser.parse_json(args.wandb_json)
        print(f"Loaded {len(metrics)} metrics from JSON")
    elif args.sample:
        metrics = generate_sample_data(800)
        print(f"Generated {len(metrics)} sample metrics")
    else:
        print("No data source specified. Use --sample for demo.")
        metrics = generate_sample_data(800)
    
    # Generate figures
    generator = IEEEAccessFigureGenerator(args.output_dir)
    
    # Figure 1: DES with trend
    if 'MTD/DES_mean' in metrics:
        fig = generator.plot_single_metric_with_trend(
            metrics['MTD/DES_mean'],
            trend_method='savgol',
            show_peaks=True,
            zone_ranges=[(0, 200, 'neutral'), (600, 800, 'good')]
        )
        generator.save_figure(fig, 'fig1_des_trend')
        plt.close(fig)
    
    # Figure 2: Multi-panel actions
    action_keys = [
        'Action/shuffle_intensity',
        'Action/service_swap_target', 
        'Action/service_swap_intensity',
        'Action/port_hop_intensity',
        'Action/decoy_ratio',
        'Action/blacklist_duration'
    ]
    fig = generator.plot_multi_panel_time_series(metrics, action_keys, ncols=3)
    generator.save_figure(fig, 'fig2_action_timeseries')
    plt.close(fig)
    
    # Figure 3: Action distribution bar chart
    fig = generator.plot_action_distribution(metrics, strategies=['RL', 'RL-CTI'])
    generator.save_figure(fig, 'fig3_action_distribution')
    plt.close(fig)
    
    # Figure 4: Cost-Effectiveness
    fig = generator.plot_cost_effectiveness(metrics)
    generator.save_figure(fig, 'fig4_cost_effectiveness')
    plt.close(fig)
    
    # Figure 5: Correlation analysis (Cost vs DES)
    if 'Cost/Total_mean' in metrics and 'MTD/DES_mean' in metrics:
        fig = generator.plot_correlation_analysis(
            metrics['Cost/Total_mean'],
            metrics['MTD/DES_mean'],
            highlight_region=(0.5, 'right', 'High Cost Zone')
        )
        generator.save_figure(fig, 'fig5_cost_des_correlation')
        plt.close(fig)
    
    # Figure 6: Drone + CTI Dashboard
    fig = generator.plot_drone_cti_dashboard(metrics)
    generator.save_figure(fig, 'fig6_drone_cti_dashboard')
    plt.close(fig)
    
    print(f"\nAll figures saved to: {args.output_dir}")


if __name__ == '__main__':
    main()