#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_eval_v06.py

Evaluation script for PPO-based MTD policy.

- 학습된 정책(final_policy.pth)을 로드해서
  지정한 에피소드 수만큼 Seeker와 붙여보고
  에피소드별 / 전체 평균 성능 지표를 계산한다.
- W&B에는 에피소드별 metric + EvalSummary/* (전체 평균/합계)를 함께 로깅한다.

사용 예시:
    python3 -m mtd.rl_eval_v06 \
        --model ./runs/PPO_v06_vs_Seeker_20251130_045000/final_policy.pth \
        --episodes 200 \
        --seeker-level 3 \
        --max-steps 200 \
        --device cpu \
        --wandb-project mtd_rl_eval_v06 \
        --wandb-run-name "PPO_Adaptive_Defense_eval_L3"
"""

import argparse
import logging
import os
from collections import defaultdict
from datetime import datetime

import numpy as np
import torch
import wandb

from .rl_model_v05 import ActorCritic
from .rl_config_v06 import (
    RL_CONFIG,
    STATE_DIM,
    ACTION_DIM,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
)
from .rl_environment_v06 import MTDEnvironment

logger = logging.getLogger("RLEval")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _safe_mean(arr):
    return float(np.mean(arr)) if arr else 0.0


def _flatten_metrics(m):
    """
    env._get_current_metrics() or info dict를 받아서
    Metrics.Attack/Defense까지 평탄화해서 리턴.
    """
    flat = dict(m)
    nested = flat.pop("Metrics", {})

    defense = nested.get("Defense", {})
    attack = nested.get("Attack", {})

    # 공격 관련 카운트
    flat.setdefault("Attack/ExploitAttempts", float(attack.get("ExploitAttempts", 0)))
    flat.setdefault("Attack/BreachAttempts", float(attack.get("BreachAttempts", 0)))
    flat.setdefault("Attack/DecoyHits", float(attack.get("DecoyHits", 0)))

    # 방어 관련
    flat.setdefault("Defense/ShuffleCount", float(defense.get("ShuffleCount", 0)))
    flat.setdefault("Defense/TotalBlocks", float(defense.get("TotalBlocks", 0)))

    return flat


def load_policy(model_path: str, device: torch.device, hidden_size: int = 128) -> ActorCritic:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model path does not exist: {model_path}")

    policy = ActorCritic(STATE_DIM, ACTION_DIM, hidden_size=hidden_size).to(device)
    state_dict = torch.load(model_path, map_location=device)

    # 학습 스크립트에서 save_policy는 network.state_dict()를 저장하므로 그대로 로드
    policy.load_state_dict(state_dict)
    policy.eval()

    logger.info("Loaded plain state_dict from %s", model_path)
    return policy


def run_single_episode(env: MTDEnvironment, policy: ActorCritic, device: torch.device, max_steps: int):
    state, _ = env.reset()
    done = False
    ep_reward = 0.0
    steps = 0

    # 마지막 step의 info로부터 metrics 뽑기
    last_info = {}

    while not done and steps < max_steps:
        state_t = torch.as_tensor(state, dtype=torch.float32, device=device).unsqueeze(0)
        with torch.no_grad():
            # stochastic policy (훈련 시와 동일하게 샘플링)
            action, _, _, _ = policy.get_action_and_value(state_t)

        action_np = action.squeeze(0).cpu().numpy()
        next_state, reward, terminated, truncated, info = env.step(action_np)

        state = next_state
        ep_reward += float(reward)
        steps += 1
        done = terminated or truncated
        last_info = info

    # 에피소드 전체 기준 metric (env 내부 카운터 기반)
    metrics = env._get_current_metrics()
    metrics_flat = _flatten_metrics(metrics)

    return ep_reward, steps, metrics_flat


def evaluate(
    model_path: str,
    episodes: int,
    seeker_level: int,
    max_steps: int,
    device_str: str = "cpu",
    wandb_project: str | None = None,
    wandb_run_name: str | None = None,
    wandb_group: str | None = None,
):
    device = torch.device(device_str)
    policy = load_policy(model_path, device)

    env = MTDEnvironment(seeker_level=seeker_level)
    env.max_episode_steps = max_steps

    use_wandb = bool(wandb_project)
    if use_wandb:
        run_name = (
            wandb_run_name
            if wandb_run_name
            else f"PPO_Eval_v06_L{seeker_level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        wandb.init(
            project=wandb_project,
            name=run_name,
            group=wandb_group,
            config={
                "model_path": model_path,
                "episodes": episodes,
                "seeker_level": seeker_level,
                "max_steps": max_steps,
                "device": device_str,
            },
        )
        logger.info("Weights & Biases logging enabled for evaluation.")

    logger.info(
        "Starting evaluation: %d episodes vs Seeker Level %d (stochastic)",
        episodes,
        seeker_level,
    )

    # 에피소드별 로그 저장
    episode_rewards = []
    episode_lengths = []
    episode_metrics_list = []

    # 전체 합계/평균용 누적
    sum_metrics = defaultdict(float)

    for ep in range(1, episodes + 1):
        ep_reward, ep_len, metrics = run_single_episode(env, policy, device, max_steps)

        episode_rewards.append(ep_reward)
        episode_lengths.append(ep_len)
        episode_metrics_list.append(metrics)

        # 누적 합계
        for k, v in metrics.items():
            sum_metrics[k] += float(v)

        if use_wandb:
            log_data = {
                "Episode/TotalReward": ep_reward,
                "Episode/Length": ep_len,
                "Episode/SeekerLevel": seeker_level,
            }
            # 에피소드별 metric 그대로 넣기
            for k, v in metrics.items():
                log_data[k] = v
            wandb.log(log_data, step=ep)

        if ep % 10 == 0 or ep == episodes:
            logger.info("Episode %d/%d: Reward=%.2f", ep, episodes, ep_reward)

    # ---- 전체 평균/합계 계산 ----
    n = float(episodes)
    mean_reward = _safe_mean(episode_rewards)
    mean_length = _safe_mean(episode_lengths)

    mean_metrics = {}
    # 에피소드별 metric의 '평균' 계산 (카운트형도 평균 카운트로)
    all_keys = set().union(*(m.keys() for m in episode_metrics_list))
    for key in all_keys:
        vals = [m.get(key, 0.0) for m in episode_metrics_list]
        mean_metrics[key] = _safe_mean(vals)

    # 공격 관련 전역 카운트
    total_exploit_attempts = sum_metrics["Attack/ExploitAttempts"]
    total_breach_attempts = sum_metrics["Attack/BreachAttempts"]
    total_decoy_hits = sum_metrics["Attack/DecoyHits"]

    # 전역 비율 재계산 (논문/보고서에서 쓸 수 있는 값)
    global_decoy_lure_rate = (
        total_decoy_hits / total_exploit_attempts if total_exploit_attempts > 0 else 0.0
    )
    # BreachSuccessRate는 이미 env에서 0인 상태지만, 전역 기준으로 다시 계산
    # (여기서는 breach 성공 카운트가 없으므로 0)
    # 만약 향후 env에 breach_success 카운트를 추가하면 여기에 반영 가능
    global_breach_success_rate = mean_metrics.get("Attack/BreachSuccessRate", 0.0)

    summary = {
        "Episodes": episodes,
        "SeekerLevel": seeker_level,
        "MeanReward": mean_reward,
        "MeanLength": mean_length,
        "MeanMetrics": mean_metrics,
        "Total/ExploitAttempts": total_exploit_attempts,
        "Total/BreachAttempts": total_breach_attempts,
        "Total/DecoyHits": total_decoy_hits,
        "Global/DecoyLureRate": global_decoy_lure_rate,
        "Global/BreachSuccessRate": global_breach_success_rate,
    }

    # 콘솔 출력용 요약
    logger.info("=== Evaluation Summary (Level %d, %d episodes) ===", seeker_level, episodes)
    logger.info("Mean Reward          : %.2f", mean_reward)
    logger.info("Mean Episode Length  : %.2f", mean_length)
    logger.info("Mean Defense/R_succ  : %.4f", mean_metrics.get("Defense/R_succ", 0.0))
    logger.info("Mean S_MTD_overall   : %.4f", mean_metrics.get("Defense/S_MTD_overall", 0.0))
    logger.info("Mean Defense/CostMean: %.5f", mean_metrics.get("Defense/CostMean", 0.0))
    logger.info("Mean Attack/BreachSuccessRate: %.5f", mean_metrics.get("Attack/BreachSuccessRate", 0.0))
    logger.info("Mean Attack/DecoyLureRate    : %.5f", mean_metrics.get("Attack/DecoyLureRate", 0.0))
    logger.info("Total ExploitAttempts: %.0f", total_exploit_attempts)
    logger.info("Total BreachAttempts : %.0f", total_breach_attempts)
    logger.info("Total DecoyHits      : %.0f", total_decoy_hits)
    logger.info("Global DecoyLureRate : %.5f", global_decoy_lure_rate)
    logger.info("Global BreachSuccRate: %.5f", global_breach_success_rate)

    if use_wandb:
        # EvalSummary/* 로 한 번만 찍어서 summary에서 헷갈리지 않도록
        log_sum = {
            "EvalSummary/MeanReward": mean_reward,
            "EvalSummary/MeanEpisodeLength": mean_length,
            "EvalSummary/SeekerLevel": seeker_level,
            "EvalSummary/TotalExploitAttempts": total_exploit_attempts,
            "EvalSummary/TotalBreachAttempts": total_breach_attempts,
            "EvalSummary/TotalDecoyHits": total_decoy_hits,
            "EvalSummary/GlobalDecoyLureRate": global_decoy_lure_rate,
            "EvalSummary/GlobalBreachSuccessRate": global_breach_success_rate,
        }
        # 주요 defense metric 평균
        for key in [
            "Defense/R_succ",
            "Defense/S_MTD_overall",
            "Defense/CostMean",
            "Defense/Uptime",
            "Defense/MTD_Rate",
        ]:
            log_sum[f"EvalSummary/{key}"] = mean_metrics.get(key, 0.0)

        wandb.log(log_sum, step=episodes)
        wandb.finish()

    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate PPO MTD Policy (v06)")
    parser.add_argument("--model", type=str, required=True, help="Path to final_policy.pth")
    parser.add_argument("--episodes", type=int, default=200, help="Number of eval episodes")
    parser.add_argument("--seeker-level", type=int, default=3, help="Seeker level (0~4)")
    parser.add_argument("--max-steps", type=int, default=200, help="Max steps per episode")
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="Evaluation device",
    )
    parser.add_argument("--wandb-project", type=str, default="", help="W&B project name")
    parser.add_argument("--wandb-run-name", type=str, default="", help="W&B run name")
    parser.add_argument("--wandb-group", type=str, default="", help="W&B group name (optional)")

    args = parser.parse_args()

    try:
        evaluate(
            model_path=args.model,
            episodes=args.episodes,
            seeker_level=args.seeker_level,
            max_steps=args.max_steps,
            device_str=args.device,
            wandb_project=args.wandb_project if args.wandb_project else None,
            wandb_run_name=args.wandb_run_name if args.wandb_run_name else None,
            wandb_group=args.wandb_group if args.wandb_group else None,
        )
    except Exception as e:
        logger.error("Evaluation failed: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    main()
