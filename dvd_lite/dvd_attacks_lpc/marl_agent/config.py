# config.py
import torch

# --- [v12] Full-GPU War Game 설정 ---
LEVEL = 2
N_ENVS = 2048
TOTAL_UPDATES = 15000
ROLLOUT_STEPS = 128
LOG_INTERVAL = 20
MAX_STEPS_PER_EPISODE = 200  # <<-- [수정 1] 누락된 에피소드 최대 스텝 변수 추가
TRAINING_TIME_LIMIT_MINUTES = 5 # <<-- [수정 2] 분 단위 학습 시간 제한 (0이면 무제한)

# --- PPO 하이퍼파라미터 ---
LEARNING_RATE = 3e-4
GAMMA = 0.99
GAE_LAMBDA = 0.95
EPSILON_CLIP = 0.2
PPO_EPOCHS = 10
MINIBATCH_SIZE = 4096 
ENTROPY_COEFF = 0.01
VALUE_COEFF = 0.5
MAX_GRAD_NORM = 0.5

# --- 신경망 및 가속 ---
HIDDEN_SIZE = 256
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP = True
TORCH_COMPILE = True

# --- [v12] 시나리오별 파라미터 ---
NUM_IPS = [64, 256, 1024][LEVEL]
NUM_PORTS = [8, 16, 32][LEVEL]
BUDGET = [100.0, 200.0, 300.0][LEVEL]
COST_IP_SHUFFLE = [-20.0, -15.0, -10.0][LEVEL]
COST_PT_SHUFFLE = [-15.0, -10.0, -8.0][LEVEL]
COST_DECOY = [-10.0, -8.0, -5.0][LEVEL]
COST_BL = [-5.0, -4.0, -2.0][LEVEL]

# 공격 표면(AS) 보상 가중치
W_EXP = [-2.0, -2.5, -3.0][LEVEL]
W_VAR = [1.5, 2.0, 2.5][LEVEL]

# 행동 정의
MTD_ACTIONS = {"대기": 0, "IP셔플": 1, "포트셔플": 2, "허니팟": 3, "블랙리스트": 4}
SEEKER_ACTIONS = {"정찰": 0, "스텔스정찰": 1, "디코이탐지": 2, "공격": 3, "회피": 4}

# --- PyTorch 성능 최적화 ---
torch.set_num_threads(4)
if DEVICE.type == "cuda":
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True