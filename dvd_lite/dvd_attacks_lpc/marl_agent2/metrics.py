# metrics.py
from collections import deque
import numpy as np
import math
import config

EPS = 1e-9

def shannon_entropy(p):
    p = np.clip(p, EPS, 1.0)
    return float(-(p*np.log2(p)).sum())

class MetricsTracker:
    """
    업데이트 창(최근 METRIC_WIN_UPD) 기준으로 논문형 지표를 계산.
    roll_step()에 스텝 단위 원천 카운트/마스크를 밀어넣고,
    snapshot()에서 창 평균/분포로 통계량 산출.
    """
    def __init__(self, mtd_n: int, seeker_n: int, num_ips: int, num_ports: int):
        self.mtd_n = mtd_n
        self.seeker_n = seeker_n
        self.num_ips = num_ips
        self.num_ports = num_ports

        self.win = config.METRIC_WIN_UPD
        self.snap_every = config.SNAPSHOT_EVERY

        # 업데이트 윈도우 단위 집계 버퍼
        self.buf = {
            "breach": deque(maxlen=self.win),
            "block": deque(maxlen=self.win),
            "decoy": deque(maxlen=self.win),
            "scan": deque(maxlen=self.win),
            "stealth": deque(maxlen=self.win),
            "probe": deque(maxlen=self.win),
            "attack": deque(maxlen=self.win),
            "ip_move": deque(maxlen=self.win),
            "pt_move": deque(maxlen=self.win),
            "as_exp": deque(maxlen=self.win),
            "as_var": deque(maxlen=self.win),
            "cost_total": deque(maxlen=self.win),
            "cost_ip": deque(maxlen=self.win),
            "cost_pt": deque(maxlen=self.win),
            "cost_decoy": deque(maxlen=self.win),
            "cost_bl": deque(maxlen=self.win),
            "bl_density": deque(maxlen=self.win),
            "mtd_hist": deque(maxlen=self.win),   # np.array shape [mtd_n]
        }

        # MTTC 추정: 각 env의 누적 스텝(롤아웃 스텝 기준)
        self._survival_steps = None
        self.mttc_samples = []

        # 출력 타임시리즈
        self.hist = {"t":[], "upd":[],
                     "ema_m":[], "ema_s":[],
                     "breach":[], "block":[], "decoy":[], "scan":[], "stealth":[], "probe":[], "attack":[],
                     "ip_move":[], "pt_move":[], "avg_budget":[], "as_exp":[], "as_var":[],
                     "D_entropy":[], "S_score":[], "R_score":[], "eta_dec":[], "C_def":[], "R_succ":[],
                     "score_mtd":[], "score_seeker":[]}

        # EMA 보상 (학습 루프에서 받아옴)
        self._last_ema_m = 0.0
        self._last_ema_s = 0.0

    def ensure_survival(self, n_envs:int):
        if self._survival_steps is None or len(self._survival_steps)!=n_envs:
            self._survival_steps = np.zeros(n_envs, dtype=np.int64)

    def roll_step(self, n_envs:int, a_mtd_np:np.ndarray, S_np:np.ndarray, last_stats:dict, last_masks:dict):
        """
        한 스텝 처리 후 호출. a_mtd_np: (N,), S_np: (N, state_dim)
        """
        self.ensure_survival(n_envs)

        # 블랙리스트 밀도: state 마지막 NUM_IPS 칼럼 사용
        bl = S_np[:, -self.num_ips:]
        bl_density = float((bl > 0.5).mean())

        # MTD 액션 히스토그램
        hist = np.bincount(a_mtd_np, minlength=self.mtd_n).astype(np.float64)
        self._step_mtd_hist = hist  # 임시 저장 (업데이트 끝에서 평균)

        # MTTC: breach 발생 env들의 생존시간 기록
        breach_mask = last_masks.get("breach", None)
        if breach_mask is not None:
            b = breach_mask.detach().cpu().numpy().astype(bool)
            self._survival_steps += 1
            if b.any():
                self.mttc_samples.extend(list(self._survival_steps[b]))
                self._survival_steps[b] = 0

        # 누적(업데이트 단위 평균을 위해 즉시 값을 저장하지 않고 train에서 업데이트 끝에 add_update로 집계)
        self._last_step = {
            "bl_density": bl_density,
            "last_stats": last_stats,
        }

    def add_update(self, avg_budget:float):
        """
        한 업데이트(ROLLOUT_STEPS) 종료 시점에 창 버퍼에 평균치/합계를 넣음.
        train 루프에서 스텝 누적 평균을 넘겨줄 수도 있지만,
        여기서는 env.last_stats의 최종 값(업데이트 마지막 스텝)을 사용 + mtd_hist 평균(스텝당)을 사용.
        """
        ls = self._last_step["last_stats"]
        self.buf["breach"].append(ls.get("breach_rate",0.0))
        self.buf["block"].append(ls.get("block_rate",0.0))
        self.buf["decoy"].append(ls.get("decoy_rate",0.0))
        self.buf["scan"].append(ls.get("scan_rate",0.0))
        self.buf["stealth"].append(ls.get("stealth_rate",0.0))
        self.buf["probe"].append(ls.get("probe_rate",0.0))
        self.buf["attack"].append(ls.get("attack_rate",0.0))
        self.buf["ip_move"].append(ls.get("ip_move_rate",0.0))
        self.buf["pt_move"].append(ls.get("pt_move_rate",0.0))
        self.buf["as_exp"].append(ls.get("as_exp",0.0))
        self.buf["as_var"].append(ls.get("as_var",0.0))
        self.buf["cost_total"].append(ls.get("cost_total",0.0))
        self.buf["cost_ip"].append(ls.get("cost_ip",0.0))
        self.buf["cost_pt"].append(ls.get("cost_pt",0.0))
        self.buf["cost_decoy"].append(ls.get("cost_decoy",0.0))
        self.buf["cost_bl"].append(ls.get("cost_bl",0.0))
        self.buf["bl_density"].append(self._last_step["bl_density"])
        self.buf["mtd_hist"].append(self._step_mtd_hist)

        self._last_avg_budget = avg_budget

    def _window_mean(self, key):
        if len(self.buf[key])==0: return 0.0
        return float(np.mean(self.buf[key]))

    def _window_mtd_hist(self):
        if len(self.buf["mtd_hist"])==0:
            return np.zeros(self.mtd_n, dtype=np.float64)
        H = np.stack(list(self.buf["mtd_hist"]), axis=0)
        return H.mean(axis=0)

    def compute_metrics(self):
        # 이벤트 레이트 창 평균
        breach = self._window_mean("breach")
        block  = self._window_mean("block")
        decoy  = self._window_mean("decoy")
        scan   = self._window_mean("scan")
        stealth= self._window_mean("stealth")
        probe  = self._window_mean("probe")
        attack = self._window_mean("attack")
        ipm    = self._window_mean("ip_move")
        ptm    = self._window_mean("pt_move")
        as_exp = self._window_mean("as_exp")
        as_var = self._window_mean("as_var")

        # D: MTD 행동 다양성 (대기(0) 제외한 분포 기준, 모두 0이면 0)
        hist = self._window_mtd_hist().copy()
        if hist.sum() > 0:
            # exclude wait(0)
            h = hist[1:].copy()
            if h.sum() > 0: h = h / h.sum()
            D_entropy = shannon_entropy(h)
        else:
            D_entropy = 0.0

        # S: shuffle 빈도 × log2(|공간|)
        f_shuffle = 0.5*(ipm + ptm)
        S_score = f_shuffle * config.LOG2_SPACE

        # R: 블랙리스트 밀도를 Redundancy proxy로 사용 (0~1)
        R_score = self._window_mean("bl_density")

        # η_dec: decoy / (decoy + breach)
        eta_dec = float(decoy / max(EPS, (decoy + breach)))

        # C_def: 평균 방어 비용의 정규화 프록시 (절댓값/정규화상수)
        COST_NORM = abs(config.COST_MTD_IP) + abs(config.COST_MTD_PORT) + abs(config.COST_MTD_DECOY) + abs(config.COST_MTD_BL) + abs(config.COST_MTD_STEP)
        ctot = self._window_mean("cost_total")  # < 0 (비용)
        C_def = min(1.0, max(0.0, (-ctot)/max(EPS, COST_NORM)))

        # R_succ: 1 - breach
        R_succ = float(1.0 - breach)

        # 간단 합성 점수(논문 그림용): 방어는 "성공↑, 비용↓, 기만↑, 다양성↑, 셔플↑"
        score_mtd = 0.25*R_succ + 0.20*eta_dec + 0.20*min(1.0, D_entropy/2.0) + 0.20*min(1.0, S_score/config.LOG2_SPACE) + 0.15*(1.0 - C_def)
        # 공격은 "침투↑, 탐지↓"를 가볍게 표현 (그림용)
        score_seeker = 0.7*breach + 0.3*max(0.0, 1.0 - block)

        return dict(
            breach=breach, block=block, decoy=decoy, scan=scan, stealth=stealth, probe=probe, attack=attack,
            ip_move=ipm, pt_move=ptm, as_exp=as_exp, as_var=as_var,
            D_entropy=D_entropy, S_score=S_score, R_score=R_score, eta_dec=eta_dec, C_def=C_def, R_succ=R_succ,
            score_mtd=score_mtd, score_seeker=score_seeker
        )

    def snapshot(self, t_sec:float, upd_idx:int, ema_m:float, ema_s:float):
        self._last_ema_m = ema_m; self._last_ema_s = ema_s
        if upd_idx % self.snap_every != 0:  # 너무 자주 기록하지 않도록
            return None
        m = self.compute_metrics()
        self.hist["t"].append(t_sec); self.hist["upd"].append(upd_idx)
        self.hist["ema_m"].append(ema_m); self.hist["ema_s"].append(ema_s)
        for k,v in m.items():
            self.hist.setdefault(k, []).append(v)
        return m  # 필요하면 로그에 쓰기

    # 도식화를 위한 파생 데이터
    def pareto_points(self):
        """(C_def, R_succ) 시퀀스와 파레토 프런티어 계산"""
        C = np.array(self.hist.get("C_def", []), dtype=float)
        R = np.array(self.hist.get("R_succ", []), dtype=float)
        if len(C)==0: return C, R, (C, R)
        order = np.argsort(C)
        C, R = C[order], R[order]
        frontier = np.maximum.accumulate(R)  # 최소 C에서 R_succ 최대
        return C, R, (C, frontier)

    def mttc_ecdf(self):
        if len(self.mttc_samples)==0:
            return np.array([0.0,1.0]), np.array([0.0,1.0])
        x = np.sort(np.array(self.mttc_samples, dtype=float))
        y = np.arange(1, len(x)+1)/len(x)
        return x, y
