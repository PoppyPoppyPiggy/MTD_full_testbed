#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD-RL Sweep Training Script v09
================================

W&B Sweep Agent에서 호출되는 학습 스크립트

저자: MTD-RL Research Team
버전: 0.9.0
"""
from __future__ import annotations

import os
import sys
import wandb
import torch
import numpy as np

from rl_config_v09 import (
    MTDConfig, get_default_config, 
    ActionThresholds, RewardWeights, CostConfig, CurriculumConfig, PPOConfig
)
from rl_train_v09 import PPOTrainer


def config_from_sweep() -> MTDConfig:
    """W&B Sweep 파라미터로 설정 생성"""
    config = get_default_config()
    
    # Reward weights
    if wandb.config.get("reward_survival_bonus"):
        config.rewards.survival_bonus = wandb.config.reward_survival_bonus
    if wandb.config.get("reward_breach_penalty"):
        config.rewards.breach_penalty = wandb.config.reward_breach_penalty
    if wandb.config.get("reward_cost_penalty"):
        config.rewards.cost_penalty = -abs(wandb.config.reward_cost_penalty)
    if wandb.config.get("reward_shuffle_usage_bonus"):
        config.rewards.shuffle_usage_bonus = wandb.config.reward_shuffle_usage_bonus
    if wandb.config.get("reward_action_diversity_bonus"):
        config.rewards.action_diversity_bonus = wandb.config.reward_action_diversity_bonus
    
    # Action thresholds
    if wandb.config.get("threshold_shuffle"):
        config.thresholds.shuffle = wandb.config.threshold_shuffle
    if wandb.config.get("threshold_port_hop"):
        config.thresholds.port_hop = wandb.config.threshold_port_hop
    if wandb.config.get("threshold_service_swap"):
        config.thresholds.service_swap = wandb.config.threshold_service_swap
    if wandb.config.get("threshold_decoy"):
        config.thresholds.decoy = wandb.config.threshold_decoy
    if wandb.config.get("threshold_blacklist"):
        config.thresholds.blacklist = wandb.config.threshold_blacklist
    
    # PPO hyperparameters
    if wandb.config.get("learning_rate"):
        config.ppo.learning_rate = wandb.config.learning_rate
    if wandb.config.get("entropy_coef_start"):
        config.ppo.entropy_coef_start = wandb.config.entropy_coef_start
    if wandb.config.get("entropy_coef_end"):
        config.ppo.entropy_coef_end = wandb.config.entropy_coef_end
    if wandb.config.get("clip_epsilon"):
        config.ppo.clip_epsilon = wandb.config.clip_epsilon
    if wandb.config.get("gae_lambda"):
        config.ppo.gae_lambda = wandb.config.gae_lambda
    if wandb.config.get("hidden_size"):
        config.ppo.hidden_size = wandb.config.hidden_size
    
    # Curriculum learning
    phase_episodes = []
    for i in range(5):
        key = f"phase{i}_episodes"
        if wandb.config.get(key):
            phase_episodes.append(wandb.config[key])
        else:
            phase_episodes.append(config.curriculum.phase_episodes[i])
    config.curriculum.phase_episodes = phase_episodes
    
    if wandb.config.get("review_ratio"):
        config.curriculum.review_ratio = wandb.config.review_ratio
    
    # Cost configuration
    if wandb.config.get("cost_shuffle"):
        config.cost.shuffle = wandb.config.cost_shuffle
    if wandb.config.get("cost_port_hop"):
        config.cost.port_hop = wandb.config.cost_port_hop
    if wandb.config.get("cost_service_swap"):
        config.cost.service_swap = wandb.config.cost_service_swap
    
    return config


def main():
    # W&B 초기화
    wandb.init()
    
    # Device 설정
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Sweep 파라미터로 설정 생성
    config = config_from_sweep()
    
    # 설정 출력
    print(f"\n{'='*60}")
    print("Sweep Configuration:")
    print(f"  Survival Bonus: {config.rewards.survival_bonus}")
    print(f"  Breach Penalty: {config.rewards.breach_penalty}")
    print(f"  Cost Penalty: {config.rewards.cost_penalty}")
    print(f"  Shuffle Threshold: {config.thresholds.shuffle}")
    print(f"  Learning Rate: {config.ppo.learning_rate}")
    print(f"  Total Episodes: {sum(config.curriculum.phase_episodes)}")
    print(f"{'='*60}\n")
    
    # 트레이너 생성 (W&B는 이미 초기화됨)
    trainer = PPOTrainer(
        config=config,
        device=device,
        use_wandb=False,  # 이미 sweep에서 초기화됨
    )
    
    # 학습 (수동 로깅)
    curriculum = config.curriculum
    total_phases = len(curriculum.phase_episodes)
    
    for phase in range(total_phases):
        trainer.current_phase = phase
        phase_eps = curriculum.phase_episodes[phase]
        
        for ep in range(phase_eps):
            result = trainer.train_episode()
            trainer.total_episodes += 1
            
            # W&B 로깅
            wandb.log({
                "train/episode": trainer.total_episodes,
                "train/phase": phase,
                "train/reward": result["reward"],
                "train/survival": 0 if result["breach"] else 1,
                "metrics/DES": result["des"],
                "metrics/MTTC": result["mttc"],
                "metrics/CDI": result["cdi"],
                "metrics/NED": result["ned"],
                "actions/shuffle_count": result["shuffle_count"],
                "actions/mean_shuffle_intensity": result["action_mean_shuffle"],
                "cost/total": result["total_cost"],
            }, step=trainer.total_episodes)
    
    # 최종 평가
    final_des = []
    final_survival = []
    
    for level in [0, 1, 2, 3, 4]:
        trainer.env.seeker_level = level
        
        for _ in range(10):
            trainer.agents = {"test": trainer}
            obs, info = trainer.env.reset()
            
            episode_reward = 0
            while True:
                state = torch.FloatTensor(obs).unsqueeze(0).to(device)
                with torch.no_grad():
                    action, _, _ = trainer.network.get_action(state, deterministic=True)
                action_np = action.cpu().numpy().flatten()
                
                obs, reward, term, trunc, info = trainer.env.step(action_np)
                episode_reward += reward
                
                if term or trunc:
                    break
            
            final_des.append(info.get("MTD/DES", 0))
            final_survival.append(0 if info.get("Episode/Breach", False) else 1)
    
    # 최종 메트릭 로깅
    wandb.log({
        "final/avg_des": np.mean(final_des),
        "final/avg_survival": np.mean(final_survival),
        "final/min_des": np.min(final_des),
    })
    
    print(f"\nFinal Results:")
    print(f"  Avg DES: {np.mean(final_des):.3f}")
    print(f"  Avg Survival: {np.mean(final_survival):.2%}")
    
    wandb.finish()


if __name__ == "__main__":
    main()