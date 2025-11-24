import argparse
import random
import time
import os
import json
import logging
from collections import deque
from datetime import datetime

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter
import wandb

from .rl_model_v05 import PPOAgent
# [FIX] Import module-level constants from rl_config_v05
from .rl_config_v05 import (
    RL_CONFIG,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    STATE_DIM,
    ACTION_DIM,
    LOG_METRICS_DEFENSE,
    LOG_METRICS_ATTACK,
    LOG_METRICS_TIME_TO_EVENT,
    LOG_METRICS_DRS,
)
from .rl_environment_v05 import MTDEnvironment

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _safe_mean(arr):
    return float(np.mean(arr)) if arr else 0.0


def calculate_metrics_from_infos(ep_infos):
    """
    Extract Metrics from the list of info collected in an episode
    and create a flat dict for wandb/TensorBoard.
    """
    if not ep_infos:
        return {}

    # Simple aggregation
    mtd_count = sum([1 for info in ep_infos if info.get("applied_mtd", False)])
    
    metrics = {
        "Defense/MTD_Count": mtd_count,
        "Defense/MTD_Rate": mtd_count / len(ep_infos) if ep_infos else 0.0
    }

    # Process nested metrics dict from environment
    last_info = ep_infos[-1]
    if "Metrics" in last_info:
        final_m = last_info["Metrics"]
        for k, v in final_m.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    metrics[f"{k}/{sub_k}"] = float(sub_v)
            else:
                try:
                    metrics[k] = float(v)
                except (ValueError, TypeError):
                    pass

    # Policy parameter means (Episode average)
    if ep_infos and "Params/bl_level" in ep_infos[0]:
        metrics["Policy/bl_level_mean"] = _safe_mean([i.get("Params/bl_level", 0.0) for i in ep_infos])
    if ep_infos and "Params/decoy_ratio" in ep_infos[0]:
        metrics["Policy/decoy_ratio_mean"] = _safe_mean([i.get("Params/decoy_ratio", 0.0) for i in ep_infos])
    if ep_infos and "Params/shuffle_intensity" in ep_infos[0]:
        metrics["Policy/shuffle_intensity_mean"] = _safe_mean([i.get("Params/shuffle_intensity", 0.0) for i in ep_infos])

    return metrics


def train_ppo(args):
    # ---------------------------
    # Seed & Device
    # ---------------------------
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = args.torch_deterministic

    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")

    # ---------------------------
    # Env Setup
    # ---------------------------
    # MTDEnvironment class is defined in rl_environment_v05.py
    env = MTDEnvironment(seeker_level=args.seeker_level)
    env.max_episode_steps = args.max_steps_per_episode 

    # ---------------------------
    # Logging (TensorBoard + wandb)
    # ---------------------------
    run_name = (
        args.run_name
        if args.run_name
        else f"PPO_v06_vs_Seeker_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    log_path = os.path.join(args.log_dir, run_name)
    os.makedirs(log_path, exist_ok=True)

    writer = SummaryWriter(log_path)

    use_wandb = args.wandb_project is not None and args.wandb_project != ""
    if use_wandb:
        wandb.init(
            project=args.wandb_project,
            entity=args.wandb_entity,
            sync_tensorboard=False,
            config=vars(args),
            name=run_name,
            dir=args.log_dir,
            reinit=True,
        )
        logger.info("Weights & Biases initialized.")

    # ---------------------------
    # PPO Agent
    # ---------------------------
    MAX_GRAD_NORM = getattr(args, "max_grad_norm", 0.5)

    # Use constants imported from config
    state_dim = STATE_DIM
    action_dim = ACTION_DIM

    logger.info(f"State Dim: {state_dim}, Action Dim: {action_dim}")

    agent = PPOAgent(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_size=args.hidden_size,
        lr=args.learning_rate,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_coef=args.clip_coef,
        max_grad_norm=MAX_GRAD_NORM,
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

    logger.info("=== Start MTD PPO Training ===")

    for episode in range(1, total_episodes + 1):
        try:
            # Sample Seeker Level
            if args.train_all_seeker_levels:
                env.seeker_level = random.choice(args.seeker_levels)
            else:
                env.seeker_level = args.seeker_level

            state, _ = env.reset(seed=args.seed + episode) # reset returns (obs, info)
            done = False
            ep_reward = 0.0
            ep_steps = 0
            ep_infos = []

            while not done:
                state_tensor = (
                    torch.as_tensor(state, dtype=torch.float32)
                    .to(device)
                    .unsqueeze(0)
                )

                action, log_prob, value = agent.get_action_and_value(state_tensor)
                
                # gym env step: obs, reward, terminated, truncated, info
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

            # PPO Update
            if agent.ready_for_update():
                logger.info(
                    f"[Update] Global Step {global_step}: Starting PPO update."
                )
                (
                    policy_loss,
                    value_loss,
                    entropy_loss,
                    approx_kl,
                    var_explained,
                ) = agent.update_policy()

                writer.add_scalar("Loss/Policy_Loss", policy_loss, global_step)
                writer.add_scalar("Loss/Value_Loss", value_loss, global_step)
                writer.add_scalar("Loss/Entropy_Loss", entropy_loss, global_step)
                writer.add_scalar("Stats/Approx_KL", approx_kl, global_step)
                writer.add_scalar(
                    "Stats/Frac_Variance_Explained", var_explained, global_step
                )

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

                logger.info(
                    f"[Update] PPO finished. PolicyLoss={policy_loss:.4f}"
                )
                agent.clear_buffer()

            # Aggregate Episode Metrics
            reward_window.append(ep_reward)
            current_metrics = calculate_metrics_from_infos(ep_infos)
            metrics_window.append(current_metrics)

            avg_reward = _safe_mean(reward_window)

            # Calculate Window Averaged Metrics
            window_metrics = {}
            all_keys = set().union(*(m.keys() for m in metrics_window)) if metrics_window else set()
            for key in all_keys:
                window_metrics[key] = _safe_mean(
                    [m.get(key, 0.0) for m in metrics_window]
                )

            # Log Basic Episode Metrics
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

            # Log Detailed Metrics
            for key, value in current_metrics.items():
                writer.add_scalar(key, value, episode)
                log_data[key] = value

                window_key = key.replace("/", "Window/", 1)
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
                wandb.log(
                    {
                        "error": f"Episode {episode} failed with error: {e}",
                        "global_step": global_step,
                    }
                )
            try:
                ckpt_path = os.path.join(log_path, f"checkpoint_ep{episode}_error.pth")
                agent.save_policy(ckpt_path)
            except Exception:
                pass
            break

    logger.info("Training finished. Closing writers.")
    writer.close()
    if use_wandb:
        wandb.finish()

    final_model_path = os.path.join(log_path, "final_policy.pth")
    agent.save_policy(final_model_path)

    # Save Normalization Metadata
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

    # Env
    parser.add_argument("--seeker-level", type=int, default=0, help="Base Seeker Level (0~3)")
    parser.add_argument(
        "--train-all-seeker-levels",
        action="store_true",
        help="Train by randomly sampling from all seeker levels 0~3",
    )
    parser.add_argument(
        "--seeker-levels",
        type=int,
        nargs="+",
        default=[0, 1, 2, 3],
        help="List of levels to use with train-all-seeker-levels option",
    )
    parser.add_argument("--total-episodes", type=int, default=100)
    parser.add_argument("--max-steps-per-episode", type=int, default=200)

    # PPO
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

    # Logging
    parser.add_argument("--log-dir", type=str, default="./runs")
    parser.add_argument("--run-name", type=str, default=None)

    parser.add_argument(
        "--wandb-project",
        type=str,
        default="mtd_rl_v06_comparison",
        help="WANDB_PROJECT",
    )
    parser.add_argument(
        "--wandb-entity",
        type=str,
        default="emforhsqhf29-",
        help="WANDB_ENTITY",
    )
    parser.add_argument(
        "--metric-window-size",
        type=int,
        default=50,
        help="Rolling mean window (in episodes)",
    )

    args = parser.parse_args()
    train_ppo(args)