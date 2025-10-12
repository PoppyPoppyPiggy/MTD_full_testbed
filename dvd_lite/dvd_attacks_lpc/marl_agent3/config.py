# config.py
# MTD–Seeker War Game configuration (paper-grounded)
# --------------------------------------------------
# 3080 Ti GPU 가속화 및 대규모 병렬 처리에 최적화된 파라미터 포함

import os, json, math, argparse, torch
from typing import Tuple

# -----------------------------
# 1) CLI & Scenario management
# -----------------------------
def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--level",   type=int,  default=int(os.environ.get("SCENARIO_LEVEL", 0)))
    p.add_argument("--n_envs",  type=int,  default=int(os.environ.get("N_ENVS", 2048)))
    p.add_argument("--updates", type=int,  default=int(os.environ.get("TOTAL_UPDATES", 2000)))
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
    for k in ["IP_SUBNET", "IP_RANGE", "COMMON_PORTS", "INITIAL_ASSETS"]:
        if k not in data:
            raise KeyError(f"Scenario missing key: {k}")
    return data

SCENARIO = load_scenario(ARGS.level)
IP_SUBNET      = SCENARIO["IP_SUBNET"]
IP_RANGE       = SCENARIO["IP_RANGE"]
COMMON_PORTS   = list(SCENARIO["COMMON_PORTS"])
INITIAL_ASSETS = int(SCENARIO["INITIAL_ASSETS"])

IP_SPACE    = list(range(IP_RANGE[0], IP_RANGE[1] + 1))
NUM_IPS     = len(IP_SPACE)
ALL_PORTS   = sorted(set(COMMON_PORTS))
NUM_PORTS   = len(ALL_PORTS)

LEVEL = int(ARGS.level)

# ----------------------------------
# 2) Difficulty scaling by scenario
# ----------------------------------
DIFF_SCAN_COST_SCALE   = 1.00 + 0.10 * LEVEL
DIFF_INFOGAIN_SCALE    = max(0.45, 1.00 - 0.10 * LEVEL)
DIFF_DETECT_SCALE      = 1.00 + 0.08 * LEVEL
DIFF_BASE_SUCCESS_SCL  = max(0.55, 0.85 - 0.08 * LEVEL)

# -------------------------
# 3) Device & performance
# -------------------------
DEVICE       = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP      = True  # Automatic Mixed Precision 활성화
USE_COMPILE  = hasattr(torch, 'compile') # PyTorch 2.x 이상에서 torch.compile 사용
ALLOW_TF32   = True
if DEVICE.type == "cuda":
    torch.backends.cuda.matmul.allow_tf32 = ALLOW_TF32
    torch.backends.cudnn.allow_tf32       = ALLOW_TF32
    torch.backends.cudnn.benchmark        = True
    if hasattr(torch, 'set_float32_matmul_precision'):
        torch.set_float32_matmul_precision("high")
torch.set_num_threads(1)

SEED = int(os.environ.get("SEED", "42"))

# -------------------------
# 4) PPO hyperparameters (GPU-Tuned)
# -------------------------
N_ENVS         = int(ARGS.n_envs)
ROLLOUT_STEPS  = int(os.environ.get("ROLLOUT_STEPS", 512))
TOTAL_UPDATES  = int(ARGS.updates)

LR            = float(os.environ.get("LR", "3e-4"))
GAMMA         = float(os.environ.get("GAMMA", "0.99"))
LAMBDA        = float(os.environ.get("LAMBDA", "0.95"))
EPS_CLIP      = float(os.environ.get("EPS_CLIP", "0.2"))
EPOCHS        = int(os.environ.get("EPOCHS", "4"))
MB_SIZE       = int(os.environ.get("MB_SIZE", "65536"))
ENT_COEF      = float(os.environ.get("ENT_COEF", "0.01"))
VAL_COEF      = float(os.environ.get("VAL_COEF", "0.5"))
MAX_GRAD_NORM = float(os.environ.get("MAX_GRAD_NORM", "0.5"))
HIDDEN        = int(os.environ.get("HIDDEN", "512"))
MAX_STEPS_PER_EP = int(os.environ.get("MAX_STEPS_PER_EP", "200"))

# ---------------------------------------
# 5) Rewards / Costs (game-theoretic tie)
# ---------------------------------------
REWARD_MTD_BLOCK     = 20.0  * DIFF_DETECT_SCALE
REWARD_MTD_DECOY     = 100.0
REWARD_MTD_BREACH    = -240.0
REWARD_MTD_SCAN_DET  = 5.0   * DIFF_DETECT_SCALE
COST_MTD_STEP        = -0.10

COST_MTD_IP          = -2.0
COST_MTD_PORT        = -2.0
COST_MTD_DECOY       = -5.0
COST_MTD_BL          = -1.0

REW_SEEKER_BREACH    = 240.0
COST_SEEKER_BLK      = -24.0
COST_SEEKER_SCAN_IP  = -1.0  * DIFF_SCAN_COST_SCALE
COST_SEEKER_SCAN_PT  = -1.0  * DIFF_SCAN_COST_SCALE
COST_SEEKER_STEALTH  = -2.5  * DIFF_SCAN_COST_SCALE
COST_SEEKER_PROBE    = -3.0
REW_SEEKER_DECOY_ID  = 4.0
COST_SEEKER_ATTACK   = -2.0
COST_SEEKER_EVADE    = -1.5

# ---------------------------------
# 6) Nmap-like scanning heuristics
# ---------------------------------
SCAN_BASE_REDUCTION_IP = 0.50 * DIFF_INFOGAIN_SCALE
SCAN_BASE_REDUCTION_PT = 0.50 * DIFF_INFOGAIN_SCALE
STEALTH_REDUCTION      = 0.35 * DIFF_INFOGAIN_SCALE
STEALTH_DET_FACTOR     = 0.20 / DIFF_DETECT_SCALE

DECOY_PROBE_P = 0.55
DECOY_FP      = 0.05
DECOY_FN      = 0.20

RECENT_WIN           = int(os.environ.get("RECENT_WIN", 6))
SCAN_REDUCTION_AT0   = 0.25

# ---------------------------------
# 7) MTD scheduling / budget model
# ---------------------------------
MTD_IP_CD   = 3
MTD_PT_CD   = 3

BUDGET_INIT   = 2000.0
BUDGET_FACTOR = 1.0
SWITCH_COST   = 1.0

# ----------------------------
# 8) Attack success baseline
# ----------------------------
ATTACK_BASE_P = DIFF_BASE_SUCCESS_SCL
BETA_UNC   = 0.7
LOG_N_IPS  = math.log(max(2, NUM_IPS))
LOG_N_PTS  = math.log(max(2, NUM_PORTS))
NORM_H     = LOG_N_IPS + LOG_N_PTS

EVADE_DUR    = 12
EVADE_EFFECT = 0.5

# ------------------------------
# 9) Metrics / plotting controls
# ------------------------------
LOG_INTERVAL     = int(os.environ.get("LOG_INTERVAL", 10))
PLOT_EVERY       = int(os.environ.get("PLOT_INTERVAL", 50))
METRIC_WIN_UPD   = int(os.environ.get("METRIC_WINDOW", 50))
SAVE_FORMATS     = os.environ.get("SAVE_FORMATS", "png,pdf").split(",")

AS_ALPHA         = 0.1
AS_DECOY_REDUCE  = 0.3
AS_BL_FACTOR     = 0.5