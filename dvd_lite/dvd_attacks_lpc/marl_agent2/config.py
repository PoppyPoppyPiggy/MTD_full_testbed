# config.py
# MTD–Seeker War Game configuration (paper-grounded)
# --------------------------------------------------
# 이 설정은 MTD 리프레시 주기, 스캔 정보획득/탐지 확률, 비용/보상, 예산, PPO 하이퍼파라미터를
# 문헌의 정성/정량적 권고를 반영해 합리적인 기본값으로 잡았다.
# (아래 “참고문헌 근거 요약” 참고)

import os, json, math, argparse, torch
from typing import Tuple

# -----------------------------
# 1) CLI & Scenario management
# -----------------------------
def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--level",   type=int,  default=int(os.environ.get("SCENARIO_LEVEL", 0)))
    p.add_argument("--n_envs",  type=int,  default=int(os.environ.get("N_ENVS", 256)))
    p.add_argument("--updates", type=int,  default=int(os.environ.get("TOTAL_UPDATES", 1200)))
    return p.parse_known_args()[0]

ARGS = _parse_args()

BASE_DIR = os.path.dirname(__file__)
SCEN_DIR = os.path.join(BASE_DIR, "scenarios")

def load_scenario(level: int) -> dict:
    path = os.path.join(SCEN_DIR, f"level{level}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Scenario file not found: {path}")
    with open(path, "r") as f:
        data = json.load(f)
    # required keys
    for k in ["IP_SUBNET", "IP_RANGE", "COMMON_PORTS", "INITIAL_ASSETS"]:
        if k not in data:
            raise KeyError(f"Scenario missing key: {k}")
    return data

SCENARIO = load_scenario(ARGS.level)
IP_SUBNET      = SCENARIO["IP_SUBNET"]
IP_RANGE       = SCENARIO["IP_RANGE"]          # [lo, hi]
COMMON_PORTS   = list(SCENARIO["COMMON_PORTS"])
INITIAL_ASSETS = int(SCENARIO["INITIAL_ASSETS"])

# Derived space sizes
IP_SPACE    = list(range(IP_RANGE[0], IP_RANGE[1] + 1))
NUM_IPS     = len(IP_SPACE)
ALL_PORTS   = sorted(set(COMMON_PORTS))
NUM_PORTS   = len(ALL_PORTS)

LEVEL = int(ARGS.level)

# ----------------------------------
# 2) Difficulty scaling by scenario
# ----------------------------------
# 난이도(Level)가 높을수록: 스캔은 비싸지고(info gain↓), 탐지 난이도↑, 공격 기본성공률↓.
DIFF_SCAN_COST_SCALE   = 1.00 + 0.10 * LEVEL                 # ↑ 비용 (스캔·스텔스)
DIFF_INFOGAIN_SCALE    = max(0.45, 1.00 - 0.10 * LEVEL)      # ↓ 정보획득량 (스캔 1회 당)
DIFF_DETECT_SCALE      = 1.00 + 0.08 * LEVEL                 # ↑ 탐지 관련 보상/가중
DIFF_BASE_SUCCESS_SCL  = max(0.55, 0.85 - 0.08 * LEVEL)      # ↓ 공격 base 성공률

# -------------------------
# 3) Device & performance
# -------------------------
DEVICE       = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP      = True                       # mixed precision on GPU
USE_COMPILE  = True                       # torch.compile (PyTorch 2.x)
ALLOW_TF32   = True
if DEVICE.type == "cuda":
    torch.backends.cuda.matmul.allow_tf32 = ALLOW_TF32
    torch.backends.cudnn.allow_tf32       = ALLOW_TF32
    torch.backends.cudnn.benchmark        = True
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass
torch.set_num_threads(1)

# 재현성(완전 결정성은 아님: 병렬/AMP 영향)
SEED = int(os.environ.get("SEED", "42"))

# -------------------------
# 4) PPO hyperparameters
# -------------------------
N_ENVS         = int(ARGS.n_envs)
ROLLOUT_STEPS  = int(os.environ.get("ROLLOUT_STEPS", 256))   # 크면 GPU 활용↑ (메모리 주의)
TOTAL_UPDATES  = int(ARGS.updates)

LR            = float(os.environ.get("LR", "3e-4"))
GAMMA         = float(os.environ.get("GAMMA", "0.99"))
LAMBDA        = float(os.environ.get("LAMBDA", "0.95"))
EPS_CLIP      = float(os.environ.get("EPS_CLIP", "0.2"))
EPOCHS        = int(os.environ.get("EPOCHS", "3"))
MB_SIZE       = int(os.environ.get("MB_SIZE", "32768"))
ENT_COEF      = float(os.environ.get("ENT_COEF", "0.012"))
VAL_COEF      = float(os.environ.get("VAL_COEF", "0.5"))
MAX_GRAD_NORM = float(os.environ.get("MAX_GRAD_NORM", "0.5"))
HIDDEN        = int(os.environ.get("HIDDEN", "256"))
MAX_STEPS_PER_EP = int(os.environ.get("MAX_STEPS_PER_EP", "200"))

# ---------------------------------------
# 5) Rewards / Costs (game-theoretic tie)
# ---------------------------------------
# Defender (MTD)
REWARD_MTD_BLOCK     = 20.0  * DIFF_DETECT_SCALE  # 차단 성공
REWARD_MTD_DECOY     = 100.0                      # 디코이 유인 성공
REWARD_MTD_BREACH    = -240.0                     # 침투 허용 패널티
REWARD_MTD_SCAN_DET  = 5.0   * DIFF_DETECT_SCALE  # 정찰 탐지(간접 보상)
COST_MTD_STEP        = -0.10                      # 운영시간 비용

# 리프레시/기만/블랙리스트 비용(“유용성 vs 보안” 트레이드오프 반영)
COST_MTD_IP          = -2.0                       # IP 셔플
COST_MTD_PORT        = -2.0                       # Port 셔플
COST_MTD_DECOY       = -5.0                       # 디코이 가동
COST_MTD_BL          = -1.0                       # 블랙리스트(저렴)

# Attacker (Seeker)
REW_SEEKER_BREACH    = 240.0                      # 침투 보상(일반적으로 대칭)
COST_SEEKER_BLK      = -24.0                      # 차단당함
COST_SEEKER_SCAN_IP  = -1.0  * DIFF_SCAN_COST_SCALE
COST_SEEKER_SCAN_PT  = -1.0  * DIFF_SCAN_COST_SCALE
COST_SEEKER_STEALTH  = -2.5  * DIFF_SCAN_COST_SCALE
COST_SEEKER_PROBE    = -3.0
REW_SEEKER_DECOY_ID  = 4.0                        # 디코이 식별에 대한 소보상
COST_SEEKER_ATTACK   = -2.0
COST_SEEKER_EVADE    = -1.5

# ---------------------------------
# 6) Nmap-like scanning heuristics
# ---------------------------------
# 한 스텝 스캔 시 힌트(H_ip/H_pt) 감소(정보획득량)
SCAN_BASE_REDUCTION_IP = 0.50 * DIFF_INFOGAIN_SCALE
SCAN_BASE_REDUCTION_PT = 0.50 * DIFF_INFOGAIN_SCALE
STEALTH_REDUCTION      = 0.35 * DIFF_INFOGAIN_SCALE       # 스텔스 스캔은 조심스러워 info↓
# 스텔스 탐지 확률 인자(낮을수록 탐지 어렵다)
STEALTH_DET_FACTOR     = 0.20 / DIFF_DETECT_SCALE

# 디코이(허니포트/허니서비스) 프로빙 성능
DECOY_PROBE_P = 0.55   # 디코이가 있을 때 성공확률의 기준
DECOY_FP      = 0.05   # 디코이 없음에도 있다고 착각(False Positive)
DECOY_FN      = 0.20   # 디코이 있는데 못찾음(False Negative)

# 최근성 가중(리프레시 직후엔 힌트가 더 빨리 감소)
RECENT_WIN           = int(os.environ.get("RECENT_WIN", 6))
SCAN_REDUCTION_AT0   = 0.25   # t=0 부근 가중

# ---------------------------------
# 7) MTD scheduling / budget model
# ---------------------------------
# 리프레시 쿨다운(episode 로컬 시간 단위)
MTD_IP_CD   = 3
MTD_PT_CD   = 3

# 방어자 예산: 고비용 전략 남용 방지(게임이론적 자원 제약)
BUDGET_INIT   = 2000.0
BUDGET_FACTOR = 1.0
SWITCH_COST   = 1.0        # 전략 전환 시 추가 비용(과도한 스위칭 억제)

# ----------------------------
# 8) Attack success baseline
# ----------------------------
# 기본 공격성공 확률(힌트 높을수록↑, 디코이/블랙리스트/쿨다운 영향↓)
ATTACK_BASE_P = DIFF_BASE_SUCCESS_SCL

# 불확실성/공격면 정규화(지표용)
BETA_UNC   = 0.7
LOG_N_IPS  = math.log(max(2, NUM_IPS))
LOG_N_PTS  = math.log(max(2, NUM_PORTS))
NORM_H     = LOG_N_IPS + LOG_N_PTS

# 회피(Evade) 지속시간/효과(일시적으로 블랙리스트 영향 경감 등)
EVADE_DUR    = 12
EVADE_EFFECT = 0.5

# ------------------------------
# 9) Metrics / plotting controls
# ------------------------------
# 콘솔 로그 주기(업데이트 단위)
LOG_INTERVAL     = int(os.environ.get("LOG_INTERVAL", 20))

# 스냅샷/플롯 주기
SNAPSHOT_EVERY   = int(os.environ.get("SNAPSHOT_EVERY", 10))
PLOT_EVERY       = int(os.environ.get("PLOT_INTERVAL", 100))  # 0이면 비활성
METRIC_WIN_UPD   = int(os.environ.get("METRIC_WINDOW", 50))
SAVE_FORMATS     = os.environ.get("SAVE_FORMATS", "png,pdf").split(",")

# 학술용 보조 상수
LOG2_SPACE       = math.log2(max(2, NUM_IPS * NUM_PORTS))
AS_ALPHA         = 0.1   # Attack-Surface EMA 기본 알파
AS_DECOY_REDUCE  = 0.3   # 디코이 검출 시 노출도 감소량 가중
AS_BL_FACTOR     = 0.5   # 블랙리스트가 노출도에 주는 상대 영향
