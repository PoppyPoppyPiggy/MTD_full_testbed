#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_mtd_from_json.py
- JSON(레벨×방법별 metrics) -> (a)~(d) 2×2 Figure 생성
- Matplotlib only (no seaborn)
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import matplotlib.pyplot as plt
import csv


# -----------------------------
# 설정: JSON 내부 metric 키들
# -----------------------------
DES_MEAN_KEY = "MTD/DES_mean"
DES_STD_KEY  = "MTD/DES_std"

MTTC_MEAN_KEY = "MTD/MTTC_mean"
MTTC_STD_KEY  = "MTD/MTTC_std"

COST_MEAN_KEY = "MTD/Cost_mean"
COST_STD_KEY  = "MTD/Cost_std"


@dataclass
class Point:
    level: int
    mode: str
    des_mean: float
    des_std: float
    mttc_mean: float
    mttc_std: float
    cost_mean: float
    cost_std: float


def _safe_get(d: dict, key: str, default: float = float("nan")) -> float:
    v = d.get(key, default)
    try:
        return float(v)
    except Exception:
        return float("nan")


def parse_level_mode(key: str) -> Optional[Tuple[int, str]]:
    """
    허용되는 키 예:
      - L0_No_MTD
      - L1_RL-CTI_MTD
      - L2-Static_MTD
    """
    m = re.match(r"^L(\d+)[_-](.+)$", key.strip())
    if not m:
        return None
    level = int(m.group(1))
    mode_raw = m.group(2).strip()

    # 관행적으로 _ 를 공백으로 보고, 연속 공백 정리
    mode = mode_raw.replace("__", "_").replace("_", " ")
    mode = re.sub(r"\s+", " ", mode).strip()
    return level, mode


def load_points(json_path: Path) -> List[Point]:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    # data가 최상위 dict가 아닐 경우(예: {"results": {...}})도 대비
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], dict):
        data = data["results"]

    if not isinstance(data, dict):
        raise ValueError("JSON 최상위가 dict 형태가 아닙니다. (예: { 'L0_No_MTD': {...}, ... } 형태 필요)")

    points: List[Point] = []
    for k, v in data.items():
        parsed = parse_level_mode(k)
        if not parsed:
            continue
        level, mode = parsed

        metrics = {}
        if isinstance(v, dict):
            # 보통 v["metrics"]에 들어있음
            if "metrics" in v and isinstance(v["metrics"], dict):
                metrics = v["metrics"]
            else:
                # 혹시 metric들이 바로 v 아래에 있을 수도 있음
                metrics = v

        p = Point(
            level=level,
            mode=mode,
            des_mean=_safe_get(metrics, DES_MEAN_KEY),
            des_std=_safe_get(metrics, DES_STD_KEY),
            mttc_mean=_safe_get(metrics, MTTC_MEAN_KEY),
            mttc_std=_safe_get(metrics, MTTC_STD_KEY),
            cost_mean=_safe_get(metrics, COST_MEAN_KEY),
            cost_std=_safe_get(metrics, COST_STD_KEY),
        )
        points.append(p)

    if not points:
        raise ValueError(
            "파싱된 데이터가 없습니다. 키가 'L0_No_MTD' 같은 패턴인지, metrics 키가 올바른지 확인하세요."
        )
    return points


def build_index(points: List[Point]) -> Tuple[List[int], List[str], Dict[Tuple[int, str], Point]]:
    levels = sorted({p.level for p in points})
    modes = sorted({p.mode for p in points})
    idx: Dict[Tuple[int, str], Point] = {(p.level, p.mode): p for p in points}
    return levels, modes, idx


def find_mode_name(modes: List[str], target: str) -> Optional[str]:
    """
    'No MTD'가 'NoMTD'/'No_MTD' 등으로 들어오는 경우를 위해 느슨하게 매칭
    """
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    t = norm(target)
    for m in modes:
        if norm(m) == t:
            return m

    # 부분 포함도 허용
    for m in modes:
        if t in norm(m):
            return m
    return None


def err_to_ci95(std: float, n: int) -> float:
    if not (n and n > 1 and math.isfinite(std)):
        return float("nan")
    return 1.96 * std / math.sqrt(n)


def export_summary_csv(out_csv: Path, levels: List[int], modes: List[str], idx: Dict[Tuple[int, str], Point]) -> None:
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["level", "mode", "des_mean", "des_std", "mttc_mean", "mttc_std", "cost_mean", "cost_std"])
        for L in levels:
            for M in modes:
                p = idx.get((L, M))
                if not p:
                    continue
                w.writerow([L, M, p.des_mean, p.des_std, p.mttc_mean, p.mttc_std, p.cost_mean, p.cost_std])


def plot_2x2(
    levels: List[int],
    modes: List[str],
    idx: Dict[Tuple[int, str], Point],
    out_png: Path,
    err_mode: str = "std",          # "std" or "ci95"
    episodes: int = 100,            # ci95 계산 시 사용
    delta_mode: bool = False,       # True면 No MTD 대비 Δ로 플롯
    ce_mode: str = "ratio",         # "ratio" or "delta_per_cost"
    title: str = "MTD Performance Evaluation Results"
) -> None:
    # baseline(No MTD) 찾기
    no_mtd = find_mode_name(modes, "No MTD")
    if no_mtd is None:
        # 그래도 delta_mode=False면 진행 가능
        if delta_mode:
            raise ValueError("delta_mode=True인데 'No MTD' 모드를 찾지 못했습니다. 모드 이름을 확인하세요.")

    def get_err(std: float) -> float:
        if err_mode == "ci95":
            return err_to_ci95(std, episodes)
        return std

    # -------------------------
    # (a) DES: grouped bar
    # -------------------------
    # bar 폭: 레벨 그룹마다 mode 개수만큼 나눔
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    ax_a, ax_b, ax_c, ax_d = axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]

    x = np.arange(len(levels), dtype=float)
    n_modes = len(modes)
    bar_w = 0.8 / max(n_modes, 1)

    for j, mode in enumerate(modes):
        y = []
        yerr = []
        for L in levels:
            p = idx.get((L, mode))
            if not p:
                y.append(np.nan); yerr.append(np.nan); continue

            val = p.des_mean
            if delta_mode and no_mtd:
                base = idx.get((L, no_mtd))
                if base:
                    val = val - base.des_mean
            y.append(val)
            yerr.append(get_err(p.des_std))

        ax_a.bar(x + (j - (n_modes - 1)/2)*bar_w, y, width=bar_w, yerr=yerr, capsize=3, label=mode)

    ax_a.set_title("(a) DES (Defense Effectiveness Score)")
    ax_a.set_xlabel("Attacker Level")
    ax_a.set_ylabel("DES" + (" (Δ vs No MTD)" if delta_mode else ""))
    ax_a.set_xticks(x)
    ax_a.set_xticklabels([f"L{L}" for L in levels])
    ax_a.grid(True, axis="y", alpha=0.3)
    ax_a.legend(fontsize=8, ncol=2)

    # -------------------------
    # (b) MTTC: line plot
    # -------------------------
    for mode in modes:
        y = []
        yerr = []
        for L in levels:
            p = idx.get((L, mode))
            if not p:
                y.append(np.nan); yerr.append(np.nan); continue

            val = p.mttc_mean
            if delta_mode and no_mtd:
                base = idx.get((L, no_mtd))
                if base:
                    val = val - base.mttc_mean
            y.append(val)
            yerr.append(get_err(p.mttc_std))

        ax_b.errorbar(x, y, yerr=yerr, capsize=3, marker="o", label=mode)

    ax_b.set_title("(b) MTTC (Mean Time To Compromise)")
    ax_b.set_xlabel("Attacker Level")
    ax_b.set_ylabel("MTTC" + (" (Δ vs No MTD)" if delta_mode else ""))
    ax_b.set_xticks(x)
    ax_b.set_xticklabels([f"L{L}" for L in levels])
    ax_b.grid(True, alpha=0.3)
    ax_b.legend(fontsize=8, ncol=2)

    # -------------------------
    # (c) Cost: line plot
    # -------------------------
    for mode in modes:
        y = []
        yerr = []
        for L in levels:
            p = idx.get((L, mode))
            if not p:
                y.append(np.nan); yerr.append(np.nan); continue

            val = p.cost_mean
            if delta_mode and no_mtd:
                base = idx.get((L, no_mtd))
                if base:
                    val = val - base.cost_mean
            y.append(val)
            yerr.append(get_err(p.cost_std))

        ax_c.errorbar(x, y, yerr=yerr, capsize=3, marker="o", label=mode)

    ax_c.set_title("(c) Defense Cost")
    ax_c.set_xlabel("Attacker Level")
    ax_c.set_ylabel("Cost" + (" (Δ vs No MTD)" if delta_mode else ""))
    ax_c.set_xticks(x)
    ax_c.set_xticklabels([f"L{L}" for L in levels])
    ax_c.grid(True, alpha=0.3)
    ax_c.legend(fontsize=8, ncol=2)

    # -------------------------
    # (d) Cost-Effectiveness
    # -------------------------
    # ce_mode:
    #   - ratio: DES / Cost
    #   - delta_per_cost: (DES - DES_no_mtd) / Cost
    for mode in modes:
        y = []
        for L in levels:
            p = idx.get((L, mode))
            if not p or not math.isfinite(p.cost_mean) or p.cost_mean == 0:
                y.append(np.nan); continue

            des = p.des_mean
            cost = p.cost_mean

            if ce_mode == "delta_per_cost":
                if not no_mtd:
                    y.append(np.nan); continue
                base = idx.get((L, no_mtd))
                if not base:
                    y.append(np.nan); continue
                des = des - base.des_mean  # ΔDES

            # delta_mode=True일 때 (c)처럼 cost도 Δ로 바뀌면 CE가 깨질 수 있어
            # CE는 보통 "원래 cost" 기준이 더 해석이 좋음 -> 여기서는 cost 그대로 사용
            ce = des / cost
            y.append(ce)

        ax_d.plot(x, y, marker="o", label=mode)

    ax_d.set_title("(d) Cost-Effectiveness")
    ax_d.set_xlabel("Attacker Level")
    ylabel = "DES/Cost" if ce_mode == "ratio" else "(DES- DES_NoMTD)/Cost"
    ax_d.set_ylabel(ylabel)
    ax_d.set_xticks(x)
    ax_d.set_xticklabels([f"L{L}" for L in levels])
    ax_d.grid(True, alpha=0.3)
    ax_d.legend(fontsize=8, ncol=2)

    fig.suptitle(title + (f"  [err={err_mode}" + (f", episodes={episodes}" if err_mode == "ci95" else "") +
                          (", Δ vs NoMTD" if delta_mode else "") + f", CE={ce_mode}]" ),
                 fontsize=12)

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="입력 JSON 경로 (예: results.json)")
    ap.add_argument("--out", default="mtd_eval_2x2.png", help="출력 PNG 경로")
    ap.add_argument("--csv", default="summary_metrics.csv", help="요약 CSV 경로")
    ap.add_argument("--err", choices=["std", "ci95"], default="std", help="에러바: std 또는 95% CI")
    ap.add_argument("--episodes", type=int, default=100, help="CI 계산용 반복 횟수(에피소드 수)")
    ap.add_argument("--delta", action="store_true", help="No MTD 대비 Δ로 플롯 (a)(b)(c) 기준)")
    ap.add_argument("--ce_mode", choices=["ratio", "delta_per_cost"], default="ratio",
                    help="Cost-Effectiveness 정의: ratio=DES/Cost, delta_per_cost=(DES-DES_NoMTD)/Cost")
    ap.add_argument("--title", default="MTD Performance Evaluation Results", help="Figure 타이틀")
    args = ap.parse_args()

    json_path = Path(args.json).expanduser().resolve()
    out_png = Path(args.out).expanduser().resolve()
    out_csv = Path(args.csv).expanduser().resolve()

    points = load_points(json_path)
    levels, modes, idx = build_index(points)

    # 요약 CSV
    export_summary_csv(out_csv, levels, modes, idx)

    # 2x2 figure
    plot_2x2(
        levels=levels,
        modes=modes,
        idx=idx,
        out_png=out_png,
        err_mode=args.err,
        episodes=args.episodes,
        delta_mode=args.delta,
        ce_mode=args.ce_mode,
        title=args.title
    )

    print(f"[OK] Saved figure: {out_png}")
    print(f"[OK] Saved summary: {out_csv}")
    print(f"[INFO] Levels: {levels}")
    print(f"[INFO] Modes: {modes}")


if __name__ == "__main__":
    main()
