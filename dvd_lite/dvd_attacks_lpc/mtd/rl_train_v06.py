#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL training script (v06) for continuous PPO agent.

- Heuristic Seeker (SimulatedHeuristicSeeker) 와 대결하면서 MTD 정책을 학습
- rl_environment_v06.MTDEnvironment + rl_config_v06.RL_CONFIG 기반
- seeker_levels.json으로 레벨별 공격자 프로파일을 정의하고,
  --train-all-seeker-levels 옵션으로 여러 레벨을 랜덤 샘플링하며 robust policy 학습

실행 예시:

    cd dvd_lite/dvd_attacks_lpc/mtd

    python3 -m mtd.rl_train_v06 \
        --total-episodes 500 \
        --train-all-seeker-levels \
        --seeker-levels 0 1 2 3 4 \
        --seeker-profiles-path ./config/seeker_levels.json \
        --wandb-project mtd_rl_v06
"""

import argparse
import random
import os
import json
import logging
from collections import deque
from datetime import datetime
from typing import Dict

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter
import wandb

from .rl_model_v05 import PPOAgent
from .rl_config_v06 import (
    RL_CONFIG,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    STATE_DIM,
    ACTION_DIM,
)
from .rl_environment_v06 import MTDEnvironment

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _safe_mean(arr):
    """Return the mean of an array or 0.0 if empty."""
    return float(np.mean(arr)) if arr else 0.0


def calculate_metrics_from_infos(ep_infos):
    """
    Extract metrics from a list of ``info`` dictionaries and return a
    flattened dict for logging.

    각 step의 info 예시:
      - applied_mtd: 셔플(MTD) 액션이 적용되었는지 여부
      - cost: 이 step에서의 MTD 비용
      - raw_reward: 환경이 계산한 reward
      - Params/<param>: RL 액션 파라미터 (dnat_target_focus, shuffle_intensity 등)
      - Metrics: 환경에서 제공하는 R_succ, S_MTD_overall 등 고수준 방어/공격 지표

    이를 episode 단위로 aggregate 해서 TensorBoard / wandb에 로깅한다.
    """
    if not ep_infos:
        return {}

    mtd_count = sum(1 for info in ep_infos if info.get("applied_mtd", False))
    metrics: Dict[str, float] = {
        "Defense/MTD_Count": mtd_count,
        "Defense/MTD_Rate": mtd_count / len(ep_infos) if ep_infos else 0.0,
    }

    # 마지막 step의 Metrics를 episode 대표값으로 사용
    last_info = ep_infos[-1]
    if "Metrics" in last_info:
        final_m = last_info["Metrics"]
        for k, v in final_m.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    try:
                        metrics[f"{k}/{sub_k}"] = float(sub_v)
                    except (ValueError, TypeError):
                        continue
            else:
                try:
                    metrics[k] = float(v)
                except (ValueError, TypeError):
                    continue

    # RL 정책 파라미터 평균 (episode 동안의 mean)
    for param in ACTION_PARAM_KEYS:
        key = f"Params/{param}"
        if ep_infos and key in ep_infos[0]:
            metrics[f"Policy/{param}_mean"] = _safe_mean([info.get(key, 0.0) for info in ep_infos])

    # 방어 비용, reward 평균/합
    if ep_infos and "cost" in ep_infos[0]:
        metrics["Episode/avg_cost"] = _safe_mean([info.get("cost", 0.0) for info in ep_infos])
        metrics["Episode/total_cost"] = float(sum(info.get("cost", 0.0) for info in ep_infos))
    if ep_infos and "raw_reward" in ep_infos[0]:
        metrics["Episode/avg_raw_reward"] = _safe_mean([info.get("raw_reward", 0.0) for info in ep_infos])

    return metrics


def train_ppo(args):
    """
    Train a PPO agent on the MTD environment using the provided arguments.

    - 환경: MTDEnvironment(seeker_level, seeker_profiles_path)
    - 공격자: SimulatedHeuristicSeeker (seeker_agent.py)
    - PPOAgent: rl_model_v05.PPOAgent
    """
    # Seed 고정
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = args.torch_deterministic

    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")

    # -------- 환경 생성 --------
    env = MTDEnvironment(
        seeker_level=args.seeker_level,
        seeker_profiles_path=args.seeker_profiles_path,
    )
    env.max_episode_steps = args.max_steps_per_episode

    # -------- 로그 디렉토리 / TensorBoard --------
    run_name = args.run_name if args.run_name else f"PPO_v06_vs_Seeker_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log_path = os.path.join(args.log_dir, run_name)
    os.makedirs(log_path, exist_ok=True)
    writer = SummaryWriter(log_path)

    # -------- Weights & Biases --------
    use_wandb = args.wandb_project is not None and args.wandb_project != ""
    if use_wandb:
        wandb.init(
            project=args.wandb_project,
            entity=args.wandb_entity if args.wandb_entity else None,
            sync_tensorboard=False,
            config=vars(args),
            name=run_name,
            dir=args.log_dir,
            reinit=True,
        )
        logger.info("Weights & Biases initialised.")

    # -------- PPO Agent 초기화 --------
    agent = PPOAgent(
        state_dim=STATE_DIM,
        action_dim=ACTION_DIM,
        hidden_size=args.hidden_size,
        lr=args.learning_rate,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_coef=args.clip_coef,
        max_grad_norm=args.max_grad_norm,
        ent_coef=args.ent_coef,
        vf_coef=args.vf_coef,
        ppo_epochs=args.ppo_epochs,
        minibatch_size=args.minibatch_size,
        target_kl=args.target_kl,
        device=device,
    )

    total_episodes = args.total_episodes
    global_step = 0
    reward_window = deque(maxlen=args.metric_window_size)
    metrics_window = deque(maxlen=args.metric_window_size)

    logger.info("=== Starting MTD PPO Training (v06) ===")
    logger.info(f"Seeker profiles: {args.seeker_profiles_path}")

    for episode in range(1, total_episodes + 1):
        try:
            # --- 에피소드마다 Seeker Level 결정 (단일 / 랜덤) ---
            if args.train_all_seeker_levels:
                env.seeker_level = random.choice(args.seeker_levels)
            else:
                env.seeker_level = args.seeker_level

            state, _ = env.reset(seed=args.seed + episode)
            done = False
            ep_reward = 0.0
            ep_steps = 0
            ep_infos = []

            # -------- Episode Rollout --------
            while not done:
                state_tensor = torch.as_tensor(state, dtype=torch.float32).to(device).unsqueeze(0)
                action, log_prob, value = agent.get_action_and_value(state_tensor)
                next_state, reward, terminated, truncated, step_info = env.step(
                    action.cpu().numpy().squeeze(0)
                )

                done = terminated or truncated
                agent.store_transition(
                    state,
                    action.squeeze(0).cpu().numpy(),
                    log_prob.item(),
                    float(reward),
                    float(value.item()),
                    done,
                )
                state = next_state
                ep_reward += float(reward)
                ep_steps += 1
                global_step += 1
                ep_infos.append(step_info.copy())

                if done:
                    break

            # -------- PPO 업데이트 --------
            if agent.ready_for_update():
                logger.info(f"[Update] Global Step {global_step}: Starting PPO update.")
                policy_loss, value_loss, entropy_loss, approx_kl, var_explained = agent.update_policy()

                writer.add_scalar("Loss/Policy_Loss", policy_loss, global_step)
                writer.add_scalar("Loss/Value_Loss", value_loss, global_step)
                writer.add_scalar("Loss/Entropy_Loss", entropy_loss, global_step)
                writer.add_scalar("Stats/Approx_KL", approx_kl, global_step)
                writer.add_scalar("Stats/Frac_Variance_Explained", var_explained, global_step)

                if use_wandb:
                    wandb.log(
                        {
                            "Loss/Policy_Loss": policy_loss,
                            "Loss/Value_Loss": value_loss,
                            "Loss/Entropy_Loss": entropy_loss,
                            "Stats/Approx_KL": approx_kl,
                            "Stats/Frac_Variance_Explained": var_explained,
                            "global_step": global_step,
                        }
                    )

                logger.info(f"[Update] PPO finished. PolicyLoss={policy_loss:.4f}")
                agent.clear_buffer()

            # -------- Episode 메트릭 집계 --------
            reward_window.append(ep_reward)
            current_metrics = calculate_metrics_from_infos(ep_infos)
            metrics_window.append(current_metrics)

            avg_reward = _safe_mean(reward_window)

            # sliding window 평균
            window_metrics = {}
            all_keys = set().union(*(m.keys() for m in metrics_window)) if metrics_window else set()
            for key in all_keys:
                window_metrics[key] = _safe_mean([m.get(key, 0.0) for m in metrics_window])

            # TensorBoard / wandb 로그
            writer.add_scalar("Episode/Reward_Total", ep_reward, episode)
            writer.add_scalar("Episode/Reward_Mean_Window", avg_reward, episode)
            writer.add_scalar("Episode/Length", ep_steps, episode)

            log_data = {
                "Episode/Reward_Total": ep_reward,
                "Episode/Reward_Mean_Window": avg_reward,
                "Episode/Length": ep_steps,
                "Episode/Seeker_Level": env.seeker_level,
                "global_step": global_step,
            }

            for key, value in current_metrics.items():
                writer.add_scalar(key, value, episode)
                log_data[key] = value

                window_key = key.replace("/", "/Window_", 1)
                writer.add_scalar(window_key, window_metrics.get(key, 0.0), episode)
                log_data[window_key] = window_metrics.get(key, 0.0)

            if use_wandb:
                wandb.log(log_data)

            logger.info(
                f"Episode {episode}/{total_episodes} [Seeker L{env.seeker_level}] "
                f"Reward={ep_reward:.2f} "
                f"S_MTD={current_metrics.get('Defense/S_MTD_overall', 0.0):.3f} "
                f"R_succ={current_metrics.get('Defense/R_succ', 0.0):.3f}"
            )

        except KeyboardInterrupt:
            logger.warning("KeyboardInterrupt detected. Saving checkpoint before exit.")
            ckpt_path = os.path.join(log_path, f"checkpoint_ep{episode}.pth")
            agent.save_policy(ckpt_path)
            break
        except Exception as e:
            logger.error(f"Error in episode {episode}: {e}", exc_info=True)
            if use_wandb:
                wandb.log({"error": f"Episode {episode} failed with error: {e}", "global_step": global_step})
            try:
                ckpt_path = os.path.join(log_path, f"checkpoint_ep{episode}_error.pth")
                agent.save_policy(ckpt_path)
            except Exception:
                pass
            break

    # -------- 종료 처리 / 최종 정책 저장 --------
    logger.info("Training finished. Closing writers.")
    writer.close()
    if use_wandb:
        wandb.finish()

    final_model_path = os.path.join(log_path, "final_policy.pth")
    agent.save_policy(final_model_path)

    # 정규화 메타데이터 저장
    norm_meta = {
        "FEATURE_KEYS": FEATURE_KEYS,
        "ACTION_PARAM_KEYS": ACTION_PARAM_KEYS,
        "FEATURE_NORM_METADATA": RL_CONFIG.FEATURE_NORM_METADATA,
    }
    with open(os.path.join(log_path, "norm_metadata.json"), "w") as f:
        json.dump(norm_meta, f, indent=4)

    logger.info(f"Final policy saved to {final_model_path}")
    logger.info(f"Log dir: {log_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MTD PPO Trainer v06 (vs Heuristic Seeker)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cuda", action="store_true", default=False)
    parser.add_argument("--torch-deterministic", action="store_true", default=True)

    # ---- Environment parameters ----
    parser.add_argument("--seeker-level", type=int, default=0, help="Base Seeker Level (0~4)")
    parser.add_argument(
        "--train-all-seeker-levels",
        action="store_true",
        help="Randomly sample seeker levels from the list",
    )
    parser.add_argument(
        "--seeker-levels",
        type=int,
        nargs="+",
        default=[0, 1, 2, 3, 4],
        help="List of seeker levels to use when sampling",
    )
    parser.add_argument(
        "--seeker-profiles-path",
        type=str,
        default="./config/seeker_levels.json",
        help="Path to seeker level profiles JSON",
    )
    parser.add_argument("--total-episodes", type=int, default=100)
    parser.add_argument("--max-steps-per-episode", type=int, default=200)

    # ---- PPO hyperparameters ----
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-coef", type=float, default=0.2)
    parser.add_argument("--max-grad-norm", type=float, default=0.5)
    parser.add_argument("--ent-coef", type=float, default=0.01)
    parser.add_argument("--vf-coef", type=float, default=0.5)
    parser.add_argument("--ppo-epochs", type=int, default=10)
    parser.add_argument("--minibatch-size", type=int, default=64)
    parser.add_argument("--target-kl", type=float, default=0.015)

    # ---- Logging ----
    parser.add_argument("--log-dir", type=str, default="./runs")
    parser.add_argument("--run-name", type=str, default=None)
    parser.add_argument(
        "--wandb-project",
        type=str,
        default="mtd_rl_v06",
        help="Weights & Biases project name",
    )
    parser.add_argument("--wandb-entity", type=str, default="", help="Weights & Biases entity (user or team)")
    parser.add_argument(
        "--metric-window-size",
        type=int,
        default=50,
        help="Number of episodes over which to compute running averages",
    )

    args = parser.parse_args()
    train_ppo(args)
