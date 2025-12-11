#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD-RL Publication Quality Visualizer v08
==========================================

IEEE Access 스타일의 논문 품질 그래프 생성 모듈

특징:
1. 데이터 + 트렌드 라인 (빨간색 점선)
2. 피크/경향성/연관성 표시
3. 학술적 MTD 지표 시각화
4. 상관관계 분석

저자: MTD-RL Research Team
버전: 0.8.6
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator, FormatStrFormatter
import matplotlib

matplotlib.use('Agg')

# Scipy for trend analysis
try:
    from scipy import stats
    from scipy.signal import savgol_filter, find_peaks
    from scipy.ndimage import gaussian_filter1d
    from scipy.optimize import curve_fit
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("⚠️ scipy not installed. Install for trend analysis: pip install scipy")

# Seaborn for enhanced styling
try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


# =============================================================================
# MTD 지표 정의 및 계산식 설명
# =============================================================================
"""
MTD 학술적 지표 (Academic MTD Metrics)
======================================

1. MTTC (Mean Time To Compromise)
   - 정의: 공격자가 시스템을 침투하는 데 걸린 평균 시간 (스텝 수)
   - 계산식: MTTC = breach_step if breached else max_steps
   - 참조: Zhuang et al., IEEE TDSC 2014
   - 범위: [0, max_steps], 높을수록 좋음

2. ASR (Attack Surface Reduction)
   - 정의: MTD로 인해 감소된 공격 표면 비율
   - 계산식: ASR = 1 - (discovered + exploited*2) / (total_services * 3)
   - 참조: Jajodia et al., Springer 2011
   - 범위: [0, 1], 높을수록 좋음

3. CDI (Configuration Diversity Index)
   - 정의: Shannon Entropy 기반 설정 다양성
   - 계산식: CDI = H(configs) / H_max
            H = -Σ p(x) * log2(p(x))
            H_max = log2(N) where N = total configurations
   - 참조: Evans et al., ACSAC 2011
   - 범위: [0, 1], 높을수록 좋음

4. NED (Normalized Entropy of Defense)
   - 정의: 방어 액션의 예측 불가능성 (시간적 변동성)
   - 계산식: NED = std(diversity_changes) * 5 (normalized)
   - 참조: Cho et al., IEEE CNS 2020
   - 범위: [0, 1], 높을수록 좋음

5. ASP (Attack Success Probability)
   - 정의: 공격 성공 확률
   - 계산식: ASP = exploited_services / discovered_services
   - 참조: Connell et al., IEEE S&P 2017
   - 범위: [0, 1], 낮을수록 좋음

6. DES (Defense Effectiveness Score)
   - 정의: 종합 방어 효과성 점수
   - 계산식: DES = 0.25*MTTC_norm + 0.20*ASR + 0.20*CDI + 
                   0.15*NED + 0.10*(1-ASP) + 0.10*Redundancy
   - 참조: Composite (This work)
   - 범위: [0, 1], 높을수록 좋음

7. CER (Cost Efficiency Ratio)
   - 정의: 비용 대비 방어 효과
   - 계산식: CER = DES / (Cost + ε)
   - 참조: Hong & Kim, IEEE TIFS 2016
   - 범위: [0, ∞), 높을수록 좋음
"""

MTD_METRICS_INFO = {
    "MTTC": {
        "name": "Mean Time To Compromise",
        "formula": r"$MTTC = t_{breach}$ if breached else $t_{max}$",
        "reference": "Zhuang et al., IEEE TDSC 2014",
        "range": "[0, max_steps]",
        "higher_better": True,
        "unit": "steps",
    },
    "ASR": {
        "name": "Attack Surface Reduction",
        "formula": r"$ASR = 1 - \frac{|S_{disc}| + 2|S_{exp}|}{3|S_{total}|}$",
        "reference": "Jajodia et al., Springer 2011",
        "range": "[0, 1]",
        "higher_better": True,
        "unit": "ratio",
    },
    "CDI": {
        "name": "Configuration Diversity Index",
        "formula": r"$CDI = \frac{H(C)}{H_{max}} = \frac{-\sum p(c)\log_2 p(c)}{\log_2 N}$",
        "reference": "Evans et al., ACSAC 2011",
        "range": "[0, 1]",
        "higher_better": True,
        "unit": "ratio",
    },
    "NED": {
        "name": "Normalized Entropy of Defense",
        "formula": r"$NED = \min(1, 5 \cdot \sigma(\Delta CDI))$",
        "reference": "Cho et al., IEEE CNS 2020",
        "range": "[0, 1]",
        "higher_better": True,
        "unit": "ratio",
    },
    "ASP": {
        "name": "Attack Success Probability",
        "formula": r"$ASP = \frac{|S_{exploited}|}{|S_{discovered}|}$",
        "reference": "Connell et al., IEEE S&P 2017",
        "range": "[0, 1]",
        "higher_better": False,
        "unit": "probability",
    },
    "DES": {
        "name": "Defense Effectiveness Score",
        "formula": r"$DES = \sum_{i} w_i \cdot M_i$",
        "reference": "Composite (This work)",
        "range": "[0, 1]",
        "higher_better": True,
        "unit": "score",
    },
    "CER": {
        "name": "Cost Efficiency Ratio",
        "formula": r"$CER = \frac{DES}{Cost + \epsilon}$",
        "reference": "Hong & Kim, IEEE TIFS 2016",
        "range": "[0, ∞)",
        "higher_better": True,
        "unit": "ratio",
    },
}


# =============================================================================
# IEEE Access Style Configuration
# =============================================================================
def set_ieee_style():
    """IEEE Access 논문 스타일 설정"""
    plt.rcParams.update({
        # Font settings
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'serif'],
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 9,
        'figure.titlesize': 14,
        
        # Line settings
        'axes.linewidth': 0.8,
        'grid.linewidth': 0.5,
        'lines.linewidth': 1.5,
        'lines.markersize': 6,
        
        # Grid settings
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.linestyle': '--',
        
        # Figure settings
        'figure.dpi': 100,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,
        'figure.figsize': (8, 5),
        
        # Color cycle
        'axes.prop_cycle': plt.cycler(color=[
            '#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', 
            '#9467bd', '#8c564b', '#e377c2', '#7f7f7f'
        ]),
    })


# Color schemes
COLORS = {
    "primary_data": '#1f77b4',      # 파란색 (주 데이터)
    "trend_line": '#d62728',         # 빨간색 (트렌드 라인)
    "secondary_data": '#2ca02c',     # 녹색 (보조 데이터)
    "highlight": '#ff7f0e',          # 주황색 (강조)
    "annotation": '#9467bd',         # 보라색 (주석)
    "fill_positive": '#d4edda',      # 연녹색 (긍정 영역)
    "fill_negative": '#f8d7da',      # 연분홍 (부정 영역)
    "fill_neutral": '#e2e3e5',       # 회색 (중립 영역)
    
    # Strategy colors
    "No MTD": '#d62728',
    "Static MTD": '#ff7f0e',
    "Heuristic MTD": '#2ca02c',
    "RL MTD": '#1f77b4',
    "RL-CTI MTD": '#9467bd',
}

MARKERS = {
    "No MTD": 'o',
    "Static MTD": 's',
    "Heuristic MTD": '^',
    "RL MTD": 'D',
    "RL-CTI MTD": 'p',
}

HATCHES = ['', '///', '...', 'xxx', '\\\\\\']


# =============================================================================
# Trend Analysis Functions
# =============================================================================
def compute_trend_line(x: np.ndarray, y: np.ndarray, 
                       method: str = 'polynomial', 
                       degree: int = 3) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """
    트렌드 라인 계산
    
    Args:
        x: X축 데이터
        y: Y축 데이터
        method: 'polynomial', 'linear', 'lowess', 'savgol', 'exponential'
        degree: 다항식 차수
        
    Returns:
        x_trend, y_trend, statistics
    """
    x = np.array(x)
    y = np.array(y)
    
    # Remove NaN values
    mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[mask]
    y_clean = y[mask]
    
    if len(x_clean) < 3:
        return x, y, {}
    
    stats_dict = {}
    
    if method == 'linear':
        # 선형 회귀
        slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)
        y_trend = slope * x_clean + intercept
        stats_dict = {
            'slope': slope,
            'intercept': intercept,
            'r_squared': r_value**2,
            'p_value': p_value,
            'std_err': std_err,
        }
        
    elif method == 'polynomial':
        # 다항식 회귀
        coeffs = np.polyfit(x_clean, y_clean, degree)
        poly = np.poly1d(coeffs)
        y_trend = poly(x_clean)
        
        # R-squared 계산
        ss_res = np.sum((y_clean - y_trend)**2)
        ss_tot = np.sum((y_clean - np.mean(y_clean))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        stats_dict = {
            'coefficients': coeffs.tolist(),
            'r_squared': r_squared,
            'degree': degree,
        }
        
    elif method == 'savgol' and HAS_SCIPY:
        # Savitzky-Golay 필터
        window = min(len(y_clean) // 3 * 2 + 1, 51)
        if window < 5:
            window = 5
        if window % 2 == 0:
            window += 1
        polyorder = min(3, window - 1)
        y_trend = savgol_filter(y_clean, window, polyorder)
        stats_dict = {'window': window, 'polyorder': polyorder}
        
    elif method == 'gaussian' and HAS_SCIPY:
        # Gaussian 스무딩
        sigma = len(y_clean) // 10
        y_trend = gaussian_filter1d(y_clean, sigma=max(1, sigma))
        stats_dict = {'sigma': sigma}
        
    elif method == 'exponential' and HAS_SCIPY:
        # 지수 피팅
        def exp_func(x, a, b, c):
            return a * np.exp(-b * x) + c
        
        try:
            popt, pcov = curve_fit(exp_func, x_clean, y_clean, 
                                   p0=[1, 0.01, np.min(y_clean)],
                                   maxfev=5000)
            y_trend = exp_func(x_clean, *popt)
            stats_dict = {'params': popt.tolist()}
        except:
            # Fallback to polynomial
            coeffs = np.polyfit(x_clean, y_clean, 2)
            y_trend = np.poly1d(coeffs)(x_clean)
    else:
        # Default: polynomial
        coeffs = np.polyfit(x_clean, y_clean, min(degree, len(x_clean) - 1))
        y_trend = np.poly1d(coeffs)(x_clean)
        stats_dict = {'coefficients': coeffs.tolist()}
    
    return x_clean, y_trend, stats_dict


def find_peaks_and_valleys(y: np.ndarray, 
                           prominence: float = 0.1) -> Tuple[np.ndarray, np.ndarray]:
    """피크와 골 찾기"""
    if not HAS_SCIPY:
        return np.array([]), np.array([])
    
    y = np.array(y)
    if len(y) < 5:
        return np.array([]), np.array([])
    
    # 데이터 범위 기준 prominence
    y_range = np.max(y) - np.min(y)
    prom = y_range * prominence
    
    # 피크 찾기
    peaks, _ = find_peaks(y, prominence=prom, distance=len(y)//10)
    
    # 골 찾기 (데이터 반전 후 피크 찾기)
    valleys, _ = find_peaks(-y, prominence=prom, distance=len(y)//10)
    
    return peaks, valleys


def compute_correlation(x: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """상관관계 분석"""
    x = np.array(x)
    y = np.array(y)
    
    mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[mask]
    y_clean = y[mask]
    
    if len(x_clean) < 3:
        return {}
    
    # Pearson correlation
    pearson_r, pearson_p = stats.pearsonr(x_clean, y_clean) if HAS_SCIPY else (0, 1)
    
    # Spearman correlation
    spearman_r, spearman_p = stats.spearmanr(x_clean, y_clean) if HAS_SCIPY else (0, 1)
    
    return {
        'pearson_r': pearson_r,
        'pearson_p': pearson_p,
        'spearman_r': spearman_r,
        'spearman_p': spearman_p,
    }


# =============================================================================
# Publication Quality Plots
# =============================================================================
class IEEEAccessPlotter:
    """IEEE Access 스타일 플로터"""
    
    def __init__(self, output_dir: str = "figures"):
        set_ieee_style()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def plot_metric_with_trend(
        self,
        x: np.ndarray,
        y: np.ndarray,
        xlabel: str,
        ylabel: str,
        title: str,
        filename: str,
        trend_method: str = 'polynomial',
        trend_degree: int = 3,
        show_peaks: bool = True,
        show_correlation: bool = True,
        highlight_regions: Optional[List[Tuple[float, float, str]]] = None,
        y_optimal: Optional[float] = None,
        figsize: Tuple[float, float] = (8, 5),
    ) -> str:
        """
        IEEE Access 스타일의 메트릭 + 트렌드 라인 그래프
        
        Args:
            x: X축 데이터
            y: Y축 데이터  
            xlabel: X축 레이블
            ylabel: Y축 레이블
            title: 그래프 제목
            filename: 저장 파일명
            trend_method: 트렌드 계산 방법
            trend_degree: 다항식 차수
            show_peaks: 피크 표시 여부
            show_correlation: 상관계수 표시 여부
            highlight_regions: 강조 영역 [(start, end, color), ...]
            y_optimal: 최적값 수평선
            figsize: 그래프 크기
            
        Returns:
            저장된 파일 경로
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        x = np.array(x)
        y = np.array(y)
        
        # 강조 영역 그리기
        if highlight_regions:
            for start, end, color in highlight_regions:
                ax.axvspan(start, end, alpha=0.15, color=color, zorder=0)
        
        # 최적값 수평선
        if y_optimal is not None:
            ax.axhline(y=y_optimal, color='gray', linestyle=':', 
                       linewidth=1, alpha=0.7, label='Optimal', zorder=1)
        
        # 메인 데이터 플롯
        ax.plot(x, y, color=COLORS['primary_data'], linewidth=1.2,
                marker='', label=ylabel, zorder=2)
        
        # 트렌드 라인
        if HAS_SCIPY and len(x) > 5:
            x_trend, y_trend, trend_stats = compute_trend_line(
                x, y, method=trend_method, degree=trend_degree
            )
            ax.plot(x_trend, y_trend, color=COLORS['trend_line'], 
                    linestyle='--', linewidth=2,
                    label='Trend Line', zorder=3)
            
            # R² 표시
            if 'r_squared' in trend_stats:
                r2 = trend_stats['r_squared']
                ax.text(0.02, 0.98, f"$R^2$ = {r2:.3f}",
                        transform=ax.transAxes, fontsize=9,
                        verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # 피크와 골 표시
        if show_peaks and HAS_SCIPY:
            peaks, valleys = find_peaks_and_valleys(y)
            
            if len(peaks) > 0:
                ax.scatter(x[peaks], y[peaks], color=COLORS['highlight'],
                           marker='v', s=80, zorder=4, label='Peak')
                for p in peaks[:3]:  # 최대 3개 표시
                    ax.annotate(f'Peak\n{y[p]:.2f}', (x[p], y[p]),
                                textcoords="offset points", xytext=(0, 15),
                                ha='center', fontsize=8,
                                arrowprops=dict(arrowstyle='->', color='gray'))
            
            if len(valleys) > 0:
                ax.scatter(x[valleys], y[valleys], color=COLORS['secondary_data'],
                           marker='^', s=80, zorder=4, label='Valley')
        
        # 상관계수 표시
        if show_correlation and HAS_SCIPY:
            corr = compute_correlation(x, y)
            if corr:
                r = corr.get('pearson_r', 0)
                p = corr.get('pearson_p', 1)
                significance = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else ''
                ax.text(0.98, 0.02, f"r = {r:.3f}{significance}",
                        transform=ax.transAxes, fontsize=9,
                        verticalalignment='bottom', horizontalalignment='right',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # 축 설정
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight='bold')
        
        # 범례
        ax.legend(loc='upper right', framealpha=0.9, fontsize=9)
        
        # 격자
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # 저장
        plt.tight_layout()
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename}.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        
        return str(self.output_dir / f"{filename}.pdf")
    
    def plot_dual_axis_with_trend(
        self,
        x: np.ndarray,
        y1: np.ndarray,
        y2: np.ndarray,
        xlabel: str,
        y1_label: str,
        y2_label: str,
        title: str,
        filename: str,
        figsize: Tuple[float, float] = (10, 5),
    ) -> str:
        """
        두 개의 Y축을 가진 그래프 (IEEE Access 스타일)
        """
        fig, ax1 = plt.subplots(figsize=figsize)
        
        x = np.array(x)
        y1 = np.array(y1)
        y2 = np.array(y2)
        
        # 첫 번째 Y축
        color1 = COLORS['primary_data']
        ax1.set_xlabel(xlabel, fontsize=11)
        ax1.set_ylabel(y1_label, color=color1, fontsize=11)
        line1 = ax1.plot(x, y1, color=color1, linewidth=1.2, label=y1_label)
        ax1.tick_params(axis='y', labelcolor=color1)
        
        # 첫 번째 트렌드
        if HAS_SCIPY and len(x) > 5:
            _, y1_trend, _ = compute_trend_line(x, y1, method='polynomial', degree=3)
            ax1.plot(x, y1_trend, color=color1, linestyle='--', 
                     linewidth=2, alpha=0.7)
        
        # 두 번째 Y축
        ax2 = ax1.twinx()
        color2 = COLORS['trend_line']
        ax2.set_ylabel(y2_label, color=color2, fontsize=11)
        line2 = ax2.plot(x, y2, color=color2, linewidth=1.2, label=y2_label)
        ax2.tick_params(axis='y', labelcolor=color2)
        
        # 두 번째 트렌드
        if HAS_SCIPY and len(x) > 5:
            _, y2_trend, _ = compute_trend_line(x, y2, method='polynomial', degree=3)
            ax2.plot(x, y2_trend, color=color2, linestyle='--', 
                     linewidth=2, alpha=0.7)
        
        # 제목
        ax1.set_title(title, fontsize=12, fontweight='bold')
        
        # 범례
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax1.legend(lines, labels, loc='upper right', framealpha=0.9)
        
        ax1.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename}.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        
        return str(self.output_dir / f"{filename}.pdf")
    
    def plot_strategy_comparison_bar(
        self,
        data: Dict[str, Dict[int, float]],
        metric_name: str,
        ylabel: str,
        title: str,
        filename: str,
        level_names: Optional[List[str]] = None,
        show_error_bars: bool = True,
        errors: Optional[Dict[str, Dict[int, float]]] = None,
        figsize: Tuple[float, float] = (12, 6),
    ) -> str:
        """
        MTD 전략 비교 바 차트 (IEEE Access 스타일)
        
        Args:
            data: {strategy: {level: value}}
            metric_name: 메트릭 이름
            ylabel: Y축 레이블
            title: 제목
            filename: 파일명
            level_names: 레벨 이름 리스트
            show_error_bars: 에러바 표시
            errors: 에러 데이터
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        strategies = list(data.keys())
        levels = sorted(list(data[strategies[0]].keys()))
        n_levels = len(levels)
        n_strategies = len(strategies)
        
        if level_names is None:
            level_names = [f"L{l}" for l in levels]
        
        x = np.arange(n_levels)
        width = 0.8 / n_strategies
        
        for i, strategy in enumerate(strategies):
            values = [data[strategy].get(l, 0) for l in levels]
            offset = (i - n_strategies/2 + 0.5) * width
            
            error_vals = None
            if show_error_bars and errors and strategy in errors:
                error_vals = [errors[strategy].get(l, 0) for l in levels]
            
            bars = ax.bar(x + offset, values, width,
                          label=strategy,
                          color=COLORS.get(strategy, f'C{i}'),
                          edgecolor='black', linewidth=0.5,
                          hatch=HATCHES[i % len(HATCHES)],
                          yerr=error_vals, capsize=2 if error_vals else 0)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(level_names)
        ax.legend(loc='upper right', ncol=2, framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename}.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        
        return str(self.output_dir / f"{filename}.pdf")
    
    def plot_multi_metric_line(
        self,
        data: Dict[str, Dict[int, float]],
        xlabel: str,
        ylabel: str,
        title: str,
        filename: str,
        show_trend: bool = True,
        figsize: Tuple[float, float] = (10, 6),
    ) -> str:
        """
        다중 메트릭 라인 차트 (각 전략별 트렌드 포함)
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        for strategy, level_data in data.items():
            levels = sorted(level_data.keys())
            values = [level_data[l] for l in levels]
            
            color = COLORS.get(strategy, '#999')
            marker = MARKERS.get(strategy, 'o')
            
            # 데이터 포인트
            ax.plot(levels, values, 
                    marker=marker, color=color,
                    linewidth=1.5, markersize=8,
                    label=strategy)
            
            # 트렌드 라인
            if show_trend and HAS_SCIPY and len(levels) >= 3:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, 
                        color=color, linestyle='--',
                        linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename}.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        
        return str(self.output_dir / f"{filename}.pdf")
    
    def plot_cost_effectiveness_scatter(
        self,
        costs: Dict[str, Dict[int, float]],
        effectiveness: Dict[str, Dict[int, float]],
        xlabel: str = "Total MTD Cost",
        ylabel: str = "Defense Effectiveness Score (DES)",
        title: str = "Cost-Effectiveness Trade-off",
        filename: str = "cost_effectiveness",
        show_pareto: bool = True,
        figsize: Tuple[float, float] = (10, 7),
    ) -> str:
        """
        비용-효과 산점도 (Pareto front 포함)
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        all_points = []
        
        for strategy in costs.keys():
            levels = sorted(costs[strategy].keys())
            
            cost_vals = [costs[strategy][l] for l in levels]
            eff_vals = [effectiveness[strategy][l] for l in levels]
            
            color = COLORS.get(strategy, '#999')
            marker = MARKERS.get(strategy, 'o')
            
            ax.scatter(cost_vals, eff_vals,
                       label=strategy, color=color,
                       marker=marker, s=100, alpha=0.8,
                       edgecolors='black', linewidth=0.5)
            
            # 레벨 표시
            for j, level in enumerate(levels):
                ax.annotate(f"L{level}", (cost_vals[j], eff_vals[j]),
                            textcoords="offset points", xytext=(5, 5),
                            fontsize=8, alpha=0.7)
            
            # Pareto front용 데이터 수집
            for c, e in zip(cost_vals, eff_vals):
                all_points.append((c, e))
        
        # Pareto front 계산 및 표시
        if show_pareto and len(all_points) > 2:
            points = np.array(all_points)
            pareto_mask = self._compute_pareto_front(points)
            pareto_points = points[pareto_mask]
            
            # 정렬
            sorted_idx = np.argsort(pareto_points[:, 0])
            pareto_sorted = pareto_points[sorted_idx]
            
            ax.plot(pareto_sorted[:, 0], pareto_sorted[:, 1],
                    'k--', linewidth=1.5, alpha=0.5, label='Pareto Front')
            ax.fill_between(pareto_sorted[:, 0], pareto_sorted[:, 1],
                            np.max(pareto_sorted[:, 1]) * 1.1,
                            alpha=0.1, color='green')
        
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename}.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        
        return str(self.output_dir / f"{filename}.pdf")
    
    def _compute_pareto_front(self, points: np.ndarray) -> np.ndarray:
        """Pareto front 계산 (비용 최소화, 효과 최대화)"""
        n = len(points)
        is_pareto = np.ones(n, dtype=bool)
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    # j가 i를 dominate하는지 확인
                    # (비용이 낮고 효과가 높으면 dominate)
                    if (points[j, 0] <= points[i, 0] and 
                        points[j, 1] >= points[i, 1] and
                        (points[j, 0] < points[i, 0] or points[j, 1] > points[i, 1])):
                        is_pareto[i] = False
                        break
        
        return is_pareto
    
    def plot_heatmap(
        self,
        data: np.ndarray,
        row_labels: List[str],
        col_labels: List[str],
        title: str,
        filename: str,
        cmap: str = 'RdYlGn',
        vmin: float = 0,
        vmax: float = 1,
        figsize: Tuple[float, float] = (10, 6),
    ) -> str:
        """히트맵 (IEEE Access 스타일)"""
        fig, ax = plt.subplots(figsize=figsize)
        
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
        
        ax.set_xticks(np.arange(len(col_labels)))
        ax.set_yticks(np.arange(len(row_labels)))
        ax.set_xticklabels(col_labels)
        ax.set_yticklabels(row_labels)
        
        # 값 표시
        for i in range(len(row_labels)):
            for j in range(len(col_labels)):
                text_color = 'white' if data[i, j] < 0.5 else 'black'
                ax.text(j, i, f"{data[i, j]:.3f}",
                        ha="center", va="center", color=text_color,
                        fontsize=10, fontweight='bold')
        
        ax.set_title(title, fontsize=12, fontweight='bold')
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.ax.set_ylabel('Score', fontsize=10)
        
        plt.tight_layout()
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename}.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        
        return str(self.output_dir / f"{filename}.pdf")
    
    def plot_action_timeseries_with_trend(
        self,
        episode_data: List[Dict],
        action_keys: List[str],
        title: str,
        filename: str,
        figsize: Tuple[float, float] = (14, 10),
    ) -> str:
        """
        액션 시계열 그래프 (트렌드 포함)
        IEEE Access Figure 5 스타일
        """
        n_actions = len(action_keys)
        n_cols = 3
        n_rows = (n_actions + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        axes = axes.flatten() if n_actions > 1 else [axes]
        
        steps = np.arange(len(episode_data))
        
        for idx, action_key in enumerate(action_keys):
            ax = axes[idx]
            
            values = np.array([ep.get(f"Action/{action_key}", 0) for ep in episode_data])
            
            # 메인 데이터
            ax.plot(steps, values, color=COLORS['primary_data'],
                    linewidth=0.8, alpha=0.8, label=action_key)
            
            # 트렌드 라인
            if HAS_SCIPY and len(steps) > 10:
                _, y_trend, stats = compute_trend_line(
                    steps, values, method='savgol'
                )
                ax.plot(steps, y_trend, color=COLORS['trend_line'],
                        linestyle='--', linewidth=2,
                        label='Trend Line')
            
            ax.set_xlabel('Step', fontsize=10)
            ax.set_ylabel('Intensity', fontsize=10)
            ax.set_title(f'Action/{action_key}', fontsize=11)
            ax.legend(loc='upper right', fontsize=8)
            ax.grid(True, alpha=0.3, linestyle='--')
        
        # 빈 subplot 제거
        for idx in range(n_actions, len(axes)):
            fig.delaxes(axes[idx])
        
        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename}.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        
        return str(self.output_dir / f"{filename}.pdf")
    
    def plot_comprehensive_results(
        self,
        results: Dict[str, Any],
        filename_prefix: str = "fig_mtd",
    ) -> List[str]:
        """
        종합 결과 시각화 (IEEE Access 메인 Figure 스타일)
        
        Args:
            results: {strategy_level: ExperimentResult} 형태
            filename_prefix: 파일명 접두사
            
        Returns:
            생성된 파일 경로 리스트
        """
        generated_files = []
        
        # 데이터 추출
        levels = [0, 1, 2, 3, 4]
        level_names = ["Script\nKiddie", "Hobbyist", "Professional", "Expert", "APT"]
        
        strategies = list(set(
            key.split('_')[1] + (' ' if len(key.split('_')) > 2 else '') + 
            (key.split('_')[2] if len(key.split('_')) > 2 else '')
            for key in results.keys()
        ))
        
        mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
        strategies = [m for m in mode_order if any(m.replace(' ', '_').replace('-', '_') in k for k in results.keys())]
        
        # === Figure 1: Main Results (2x2 subplot) ===
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # (a) DES by Level - Bar Chart
        ax = axes[0, 0]
        des_data = {}
        des_errors = {}
        
        for strategy in strategies:
            des_data[strategy] = {}
            des_errors[strategy] = {}
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    des_data[strategy][level] = results[key].metrics.get("MTD/DES_mean", 0)
                    des_errors[strategy][level] = results[key].metrics.get("MTD/DES_std", 0)
        
        x = np.arange(len(levels))
        width = 0.8 / len(strategies)
        
        for i, strategy in enumerate(strategies):
            values = [des_data[strategy].get(l, 0) for l in levels]
            errors = [des_errors[strategy].get(l, 0) for l in levels]
            offset = (i - len(strategies)/2 + 0.5) * width
            
            ax.bar(x + offset, values, width,
                   label=strategy, color=COLORS.get(strategy, f'C{i}'),
                   yerr=errors, capsize=2,
                   hatch=HATCHES[i % len(HATCHES)],
                   edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=11)
        ax.set_ylabel('Defense Effectiveness Score (DES)', fontsize=11)
        ax.set_title('(a) Defense Effectiveness by Attacker Level', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(level_names)
        ax.set_ylim(0, 1.0)
        ax.legend(loc='upper right', ncol=2, framealpha=0.9, fontsize=8)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # (b) MTTC - Line Chart with Trend
        ax = axes[0, 1]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/MTTC_mean", 200))
                else:
                    values.append(200)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values, 
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=1.5, markersize=8)
            
            # 트렌드 라인
            if HAS_SCIPY:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=11)
        ax.set_ylabel('MTTC (steps)', fontsize=11)
        ax.set_title('(b) Mean Time To Compromise', fontsize=12)
        ax.set_xticks(levels)
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # (c) ASR - Line Chart with Trend
        ax = axes[1, 0]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/ASR_mean", 0))
                else:
                    values.append(0)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values,
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=1.5, markersize=8)
            
            # 트렌드 라인
            if HAS_SCIPY:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=11)
        ax.set_ylabel('Attack Surface Reduction (ASR)', fontsize=11)
        ax.set_title('(c) Attack Surface Reduction', fontsize=12)
        ax.set_xticks(levels)
        ax.set_ylim(0, 1.0)
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # (d) Cost-Effectiveness Scatter
        ax = axes[1, 1]
        for strategy in strategies:
            costs = []
            effectiveness = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    costs.append(results[key].metrics.get("Cost/Total_mean", 0))
                    effectiveness.append(results[key].metrics.get("MTD/DES_mean", 0))
            
            if costs and effectiveness:
                ax.scatter(costs, effectiveness,
                           label=strategy, color=COLORS.get(strategy, '#999'),
                           marker=MARKERS.get(strategy, 'o'), s=100, alpha=0.8,
                           edgecolors='black', linewidth=0.5)
                
                for j, level in enumerate(levels):
                    if j < len(costs):
                        ax.annotate(f"L{level}", (costs[j], effectiveness[j]),
                                    textcoords="offset points", xytext=(3, 3),
                                    fontsize=7, alpha=0.7)
        
        ax.set_xlabel('Total MTD Cost', fontsize=11)
        ax.set_ylabel('Defense Effectiveness Score (DES)', fontsize=11)
        ax.set_title('(d) Cost-Effectiveness Trade-off', fontsize=12)
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        for ext in ['pdf', 'png']:
            filepath = self.output_dir / f"{filename_prefix}_main_results.{ext}"
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        
        plt.close()
        generated_files.append(str(self.output_dir / f"{filename_prefix}_main_results.pdf"))
        
        return generated_files


# =============================================================================
# Example Usage and Test
# =============================================================================
def create_sample_data():
    """샘플 데이터 생성"""
    np.random.seed(42)
    
    # 에피소드 데이터
    n_episodes = 200
    steps = np.arange(n_episodes)
    
    # DES 시뮬레이션 (점진적 개선 + 노이즈)
    des_base = 0.4 + 0.4 * (1 - np.exp(-steps / 50))
    des_noise = np.random.normal(0, 0.05, n_episodes)
    des = np.clip(des_base + des_noise, 0, 1)
    
    # Cost 시뮬레이션
    cost_base = 5 + 10 * np.log1p(steps / 20)
    cost_noise = np.random.normal(0, 1, n_episodes)
    cost = np.clip(cost_base + cost_noise, 0, 50)
    
    # MTTC 시뮬레이션
    mttc_base = 120 + 60 * (1 - np.exp(-steps / 100))
    mttc_noise = np.random.normal(0, 10, n_episodes)
    mttc = np.clip(mttc_base + mttc_noise, 50, 200)
    
    return {
        'steps': steps,
        'des': des,
        'cost': cost,
        'mttc': mttc,
    }


def test_plotter():
    """플로터 테스트"""
    print("=== IEEE Access Style Plotter Test ===\n")
    
    plotter = IEEEAccessPlotter(output_dir="test_figures")
    data = create_sample_data()
    
    # 1. DES vs Episode with Trend
    print("1. Creating DES vs Episode plot...")
    path = plotter.plot_metric_with_trend(
        x=data['steps'],
        y=data['des'],
        xlabel='Training Episode',
        ylabel='Defense Effectiveness Score (DES)',
        title='Observation of DES during Training',
        filename='fig_des_vs_episode',
        trend_method='savgol',
        show_peaks=True,
        show_correlation=True,
        highlight_regions=[(0, 50, COLORS['fill_negative']), 
                           (150, 200, COLORS['fill_positive'])],
    )
    print(f"   Saved: {path}\n")
    
    # 2. Cost vs DES with Trend
    print("2. Creating Cost vs DES plot...")
    path = plotter.plot_metric_with_trend(
        x=data['cost'],
        y=data['des'],
        xlabel='Total MTD Cost',
        ylabel='Defense Effectiveness Score (DES)',
        title='Observation of DES and MTD Cost',
        filename='fig_des_vs_cost',
        trend_method='polynomial',
        trend_degree=2,
        show_peaks=False,
        show_correlation=True,
    )
    print(f"   Saved: {path}\n")
    
    # 3. Dual axis plot
    print("3. Creating Dual-axis plot...")
    path = plotter.plot_dual_axis_with_trend(
        x=data['steps'],
        y1=data['des'],
        y2=data['cost'],
        xlabel='Training Episode',
        y1_label='DES',
        y2_label='Cost',
        title='DES and Cost over Training',
        filename='fig_des_cost_dual',
    )
    print(f"   Saved: {path}\n")
    
    # 4. Strategy comparison
    print("4. Creating Strategy comparison bar chart...")
    strategy_data = {
        "No MTD": {0: 0.45, 1: 0.42, 2: 0.48, 3: 0.50, 4: 0.47},
        "Static MTD": {0: 0.55, 1: 0.52, 2: 0.58, 3: 0.62, 4: 0.58},
        "Heuristic MTD": {0: 0.75, 1: 0.72, 2: 0.68, 3: 0.65, 4: 0.62},
        "RL MTD": {0: 0.88, 1: 0.85, 2: 0.78, 3: 0.72, 4: 0.68},
        "RL-CTI MTD": {0: 0.92, 1: 0.90, 2: 0.85, 3: 0.80, 4: 0.78},
    }
    
    path = plotter.plot_strategy_comparison_bar(
        data=strategy_data,
        metric_name='DES',
        ylabel='Defense Effectiveness Score (DES)',
        title='Defense Effectiveness by MTD Strategy',
        filename='fig_strategy_comparison',
        level_names=["Script\nKiddie", "Hobbyist", "Professional", "Expert", "APT"],
    )
    print(f"   Saved: {path}\n")
    
    # 5. Multi-metric line
    print("5. Creating Multi-metric line chart...")
    path = plotter.plot_multi_metric_line(
        data=strategy_data,
        xlabel='Attacker Sophistication Level',
        ylabel='Defense Effectiveness Score (DES)',
        title='DES Trend by MTD Strategy and Attacker Level',
        filename='fig_des_by_level',
        show_trend=True,
    )
    print(f"   Saved: {path}\n")
    
    # 6. Cost-Effectiveness scatter
    print("6. Creating Cost-Effectiveness scatter plot...")
    cost_data = {
        "No MTD": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
        "Static MTD": {0: 15, 1: 18, 2: 20, 3: 22, 4: 25},
        "Heuristic MTD": {0: 25, 1: 28, 2: 32, 3: 35, 4: 38},
        "RL MTD": {0: 180, 1: 175, 2: 165, 3: 155, 4: 145},
        "RL-CTI MTD": {0: 185, 1: 180, 2: 170, 3: 160, 4: 150},
    }
    
    path = plotter.plot_cost_effectiveness_scatter(
        costs=cost_data,
        effectiveness=strategy_data,
        filename='fig_cost_effectiveness',
        show_pareto=True,
    )
    print(f"   Saved: {path}\n")
    
    # 7. Heatmap
    print("7. Creating Heatmap...")
    heatmap_data = np.array([
        [0.45, 0.42, 0.48, 0.50, 0.47],
        [0.55, 0.52, 0.58, 0.62, 0.58],
        [0.75, 0.72, 0.68, 0.65, 0.62],
        [0.88, 0.85, 0.78, 0.72, 0.68],
        [0.92, 0.90, 0.85, 0.80, 0.78],
    ])
    
    path = plotter.plot_heatmap(
        data=heatmap_data,
        row_labels=["No MTD", "Static", "Heuristic", "RL", "RL-CTI"],
        col_labels=["L0", "L1", "L2", "L3", "L4"],
        title='Defense Effectiveness Score (DES) Heatmap',
        filename='fig_des_heatmap',
    )
    print(f"   Saved: {path}\n")
    
    print("=== All tests completed! ===")
    print(f"Check output in: test_figures/")


if __name__ == "__main__":
    test_plotter()