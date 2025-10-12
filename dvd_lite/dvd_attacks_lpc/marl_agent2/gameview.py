# gameview.py
# 게임이론 요약(혼합전략, 경험적 페이오프 행렬, 기대효용, BR 갭) 생성 유틸

from __future__ import annotations
import math, json
from typing import Dict, List, Tuple
import numpy as np

# ---- Seeker 매크로 액션 정의 ----
SEEKER_MACROS = ["scan", "stealth", "probe", "evade", "atk_ip", "atk_pt"]  # 6종
MTD_MACROS    = ["wait", "ip_shuffle", "pt_shuffle", "decoy", "blacklist"] # 5종

def map_seeker_macro(a_idx: np.ndarray, num_ips: int, num_ports: int) -> np.ndarray:
    """
    Seeker 원 액션 인덱스 → 매크로 인덱스(0..5)
      0,1 -> scan(0), 2->stealth(1), 3->probe(2), 4->evade(3),
      5..(5+IPs-1)->atk_ip(4), (5+IPs)..(5+IPs+Ports-1)->atk_pt(5)
    """
    base_ip = 5
    base_pt = 5 + num_ips
    out = np.empty_like(a_idx)
    out[:] = -1
    out[a_idx == 0] = 0
    out[a_idx == 1] = 0
    out[a_idx == 2] = 1
    out[a_idx == 3] = 2
    out[a_idx == 4] = 3
    ip_mask = (a_idx >= base_ip) & (a_idx < base_ip + num_ips)
    pt_mask = (a_idx >= base_pt) & (a_idx < base_pt + num_ports)
    out[ip_mask] = 4
    out[pt_mask] = 5
    return out

def dist_from_counts(counts: np.ndarray, k: int) -> np.ndarray:
    """카운트 → 확률(혼합전략)"""
    v = np.zeros(k, dtype=np.float64)
    if counts.size == 0:
        return v
    for idx, c in counts:
        if 0 <= idx < k:
            v[idx] += c
    s = v.sum()
    return v / s if s > 0 else v

def payoff_matrix_from_samples(
    a_mtd_macro: np.ndarray, a_sk_macro: np.ndarray,
    r_mtd: np.ndarray, r_sk: np.ndarray,
    mtd_k: int = 5, sk_k: int = 6
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    (MTD매크로, SK매크로, 보상) 샘플들로부터
    - MTD 페이오프 행렬 A (mtd_k x sk_k)
    - SK  페이오프 행렬 B (mtd_k x sk_k)
    - 조합 빈도 행렬 N (mtd_k x sk_k)
    를 산출 (평균).
    """
    A = np.full((mtd_k, sk_k), np.nan, dtype=np.float64)
    B = np.full((mtd_k, sk_k), np.nan, dtype=np.float64)
    N = np.zeros((mtd_k, sk_k), dtype=np.int64)

    # (i,j)별 평균
    for i in range(mtd_k):
        mask_i = (a_mtd_macro == i)
        if not mask_i.any(): 
            continue
        for j in range(sk_k):
            mask = mask_i & (a_sk_macro == j)
            n = int(mask.sum())
            if n == 0: 
                continue
            N[i, j] = n
            A[i, j] = float(np.nanmean(r_mtd[mask]))
            B[i, j] = float(np.nanmean(r_sk[mask]))
    return A, B, N

def expected_payoff(A: np.ndarray, p: np.ndarray, q: np.ndarray) -> float:
    """E[MTD payoff] = p^T A q (Seeker는 동일형식으로 B 사용)"""
    if p.sum() == 0 or q.sum() == 0:
        return 0.0
    return float(p @ (A @ q))

def best_response_gap(A: np.ndarray, p: np.ndarray, q: np.ndarray, player: str) -> float:
    """
    BR 갭(근사 exploitability). 
    player='mtd' → row player BR: max_i (A[i]·q) - p^T A q
    player='sk'  → col player BR: max_j (p^T A[:,j]) - p^T A q
    *주의*: 비제로섬에서는 A/B를 각각 넣어 계산해야 함.
    """
    if p.sum() == 0 or q.sum() == 0 or np.all(np.isnan(A)):
        return 0.0
    cur = p @ (A @ q)
    if player == "mtd":
        # 각 row의 BR 값
        row_vals = (A @ q)
        max_row = float(np.nanmax(row_vals))
        return float(max_row - cur)
    else:
        # 각 column의 BR 값
        col_vals = (p @ A)
        max_col = float(np.nanmax(col_vals))
        return float(max_col - cur)

def summarize_round(
    upd_idx: int,
    elapsed_sec: float,
    ema_mtd: float,
    ema_sk: float,
    # 원시 기록(최근 라운드 전체 스텝):
    a_mtd: np.ndarray, a_sk: np.ndarray,
    r_mtd: np.ndarray, r_sk: np.ndarray,
    # env 메타(상태/자원/지표 스냅샷):
    meta: Dict[str, float],
    num_ips: int, num_ports: int
) -> Dict:
    """
    한 라운드(=1 업데이트 동안의 롤아웃) 요약 JSON 생성
    """
    # 혼합전략(행동 분포)
    mtd_counts = np.unique(a_mtd, return_counts=True)
    sk_macro = map_seeker_macro(a_sk, num_ips, num_ports)
    sk_counts = np.unique(sk_macro, return_counts=True)
    p = dist_from_counts(np.vstack(mtd_counts).T, 5)
    q = dist_from_counts(np.vstack(sk_counts).T, 6)

    # 페이오프 행렬(경험적)
    A_mtd, B_sk, N = payoff_matrix_from_samples(a_mtd, sk_macro, r_mtd, r_sk, 5, 6)

    # 기대효용 및 BR 갭
    exp_mtd = expected_payoff(np.nan_to_num(A_mtd, nan=0.0), p, q)
    exp_sk  = expected_payoff(np.nan_to_num(B_sk,  nan=0.0), p, q)
    br_gap_m = best_response_gap(np.nan_to_num(A_mtd, nan=0.0), p, q, "mtd")
    br_gap_s = best_response_gap(np.nan_to_num(B_sk,  nan=0.0), p, q, "sk")

    # 액션 조합 빈도(정규화)
    N_prob = N.astype(np.float64)
    tot = N_prob.sum()
    if tot > 0:
        N_prob /= tot

    # 라운드 JSON
    snap = {
        "update_idx": upd_idx,
        "time_sec": float(elapsed_sec),
        "time_min": float(elapsed_sec/60.0),
        "ema_mtd": float(ema_mtd),
        "ema_seeker": float(ema_sk),
        "meta": meta,  # env.last_stats + 힌트/자원 등
        "strategy": {
            "mtd_names": MTD_MACROS,
            "seeker_names": SEEKER_MACROS,
            "mtd_mix": p.round(6).tolist(),
            "seeker_mix": q.round(6).tolist()
        },
        "payoff": {
            "mtd_matrix": np.round(np.nan_to_num(A_mtd, nan=0.0), 6).tolist(),
            "seeker_matrix": np.round(np.nan_to_num(B_sk,  nan=0.0), 6).tolist(),
            "pair_freq": np.round(N_prob, 6).tolist()
        },
        "expected": {
            "mtd": round(float(exp_mtd), 6),
            "seeker": round(float(exp_sk), 6)
        },
        "br_gap": {
            "mtd": round(float(br_gap_m), 6),
            "seeker": round(float(br_gap_s), 6)
        }
    }
    return snap
