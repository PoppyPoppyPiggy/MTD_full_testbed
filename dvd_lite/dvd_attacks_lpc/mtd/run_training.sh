#!/bin/bash
# run_training.sh
# MTD RL Level별 상세 학습 스크립트

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 기본 설정
PROJECT="mtd-rl-v07"
CHECKPOINT_DIR="checkpoints"
LOG_DIR="logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 디렉토리 생성
mkdir -p $CHECKPOINT_DIR
mkdir -p $LOG_DIR

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   MTD RL Training Suite (v07)${NC}"
echo -e "${BLUE}============================================${NC}"

# ============================================
# 옵션 1: 커리큘럼 학습 (권장)
# ============================================
curriculum_training() {
    echo -e "\n${GREEN}[1] Curriculum Learning (Level 0 → 2 → 4)${NC}"
    
    python3 rl_train_v07.py \
        --curriculum \
        --episodes 2000 \
        --max-steps 200 \
        --seed 42 \
        --wandb \
        --project ${PROJECT} \
        --run-name "curriculum-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/curriculum" \
        --save-interval 200 \
        --log-interval 50 \
        2>&1 | tee "${LOG_DIR}/curriculum_${TIMESTAMP}.log"
}

# ============================================
# 옵션 2: 개별 Level 순차 학습
# ============================================
sequential_training() {
    echo -e "\n${GREEN}[2] Sequential Level Training${NC}"
    
    EPISODES_PER_LEVEL=500
    
    # Level 0: Script Kiddie
    echo -e "\n${YELLOW}>>> Training Level 0 (Script Kiddie)${NC}"
    python3 rl_train_v07.py \
        --seeker-level 0 \
        --episodes ${EPISODES_PER_LEVEL} \
        --max-steps 200 \
        --seed 42 \
        --wandb \
        --project ${PROJECT} \
        --run-name "level0-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/level0" \
        --save-interval 100 \
        --log-interval 20 \
        2>&1 | tee "${LOG_DIR}/level0_${TIMESTAMP}.log"
    
    # Level 1: Mainstream Hacker (이전 모델에서 이어서)
    echo -e "\n${YELLOW}>>> Training Level 1 (Mainstream Hacker)${NC}"
    python3 rl_train_v07.py \
        --seeker-level 1 \
        --episodes ${EPISODES_PER_LEVEL} \
        --resume "${CHECKPOINT_DIR}/level0/best_model.pt" \
        --max-steps 200 \
        --seed 43 \
        --wandb \
        --project ${PROJECT} \
        --run-name "level1-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/level1" \
        --save-interval 100 \
        --log-interval 20 \
        2>&1 | tee "${LOG_DIR}/level1_${TIMESTAMP}.log"
    
    # Level 2: Time-Aware
    echo -e "\n${YELLOW}>>> Training Level 2 (Time-Aware)${NC}"
    python3 rl_train_v07.py \
        --seeker-level 2 \
        --episodes ${EPISODES_PER_LEVEL} \
        --resume "${CHECKPOINT_DIR}/level1/best_model.pt" \
        --max-steps 200 \
        --seed 44 \
        --wandb \
        --project ${PROJECT} \
        --run-name "level2-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/level2" \
        --save-interval 100 \
        --log-interval 20 \
        2>&1 | tee "${LOG_DIR}/level2_${TIMESTAMP}.log"
    
    # Level 3: Adaptive APT
    echo -e "\n${YELLOW}>>> Training Level 3 (Adaptive APT)${NC}"
    python3 rl_train_v07.py \
        --seeker-level 3 \
        --episodes ${EPISODES_PER_LEVEL} \
        --resume "${CHECKPOINT_DIR}/level2/best_model.pt" \
        --max-steps 200 \
        --seed 45 \
        --wandb \
        --project ${PROJECT} \
        --run-name "level3-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/level3" \
        --save-interval 100 \
        --log-interval 20 \
        2>&1 | tee "${LOG_DIR}/level3_${TIMESTAMP}.log"
    
    # Level 4: Expert APT
    echo -e "\n${YELLOW}>>> Training Level 4 (Expert APT)${NC}"
    python3 rl_train_v07.py \
        --seeker-level 4 \
        --episodes ${EPISODES_PER_LEVEL} \
        --resume "${CHECKPOINT_DIR}/level3/best_model.pt" \
        --max-steps 200 \
        --seed 46 \
        --wandb \
        --project ${PROJECT} \
        --run-name "level4-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/level4" \
        --save-interval 100 \
        --log-interval 20 \
        2>&1 | tee "${LOG_DIR}/level4_${TIMESTAMP}.log"
    
    echo -e "\n${GREEN}✅ All levels trained!${NC}"
}

# ============================================
# 옵션 3: 단일 레벨 집중 학습
# ============================================
single_level_training() {
    LEVEL=$1
    EPISODES=$2
    
    echo -e "\n${GREEN}[3] Single Level Training: Level ${LEVEL}${NC}"
    
    python3 rl_train_v07.py \
        --seeker-level ${LEVEL} \
        --episodes ${EPISODES} \
        --max-steps 200 \
        --seed 42 \
        --wandb \
        --project ${PROJECT} \
        --run-name "single-L${LEVEL}-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/single_L${LEVEL}" \
        --save-interval 100 \
        --log-interval 20 \
        2>&1 | tee "${LOG_DIR}/single_L${LEVEL}_${TIMESTAMP}.log"
}

# ============================================
# 옵션 4: 빠른 테스트 (디버깅용)
# ============================================
quick_test() {
    echo -e "\n${GREEN}[4] Quick Test (50 episodes)${NC}"
    
    python3 rl_train_v07.py \
        --seeker-level 2 \
        --episodes 50 \
        --max-steps 100 \
        --seed 42 \
        --wandb \
        --project "${PROJECT}-test" \
        --run-name "quick-test-${TIMESTAMP}" \
        --checkpoint-dir "${CHECKPOINT_DIR}/test" \
        --save-interval 50 \
        --log-interval 10
}

# ============================================
# 메인 메뉴
# ============================================
show_menu() {
    echo -e "\n${BLUE}Select Training Mode:${NC}"
    echo "  1) Curriculum Learning (권장, 2000 episodes)"
    echo "  2) Sequential Level Training (각 500 episodes)"
    echo "  3) Single Level Training"
    echo "  4) Quick Test (50 episodes)"
    echo "  5) Exit"
    echo ""
    read -p "Enter choice [1-5]: " choice
    
    case $choice in
        1) curriculum_training ;;
        2) sequential_training ;;
        3) 
            read -p "Enter Level [0-4]: " level
            read -p "Enter Episodes: " eps
            single_level_training $level $eps
            ;;
        4) quick_test ;;
        5) exit 0 ;;
        *) echo -e "${RED}Invalid choice${NC}" ;;
    esac
}

# 인자가 있으면 직접 실행, 없으면 메뉴 표시
if [ $# -eq 0 ]; then
    show_menu
else
    case $1 in
        "curriculum") curriculum_training ;;
        "sequential") sequential_training ;;
        "single") single_level_training $2 $3 ;;
        "quick") quick_test ;;
        *) 
            echo "Usage: $0 [curriculum|sequential|single <level> <episodes>|quick]"
            exit 1
            ;;
    esac
fi