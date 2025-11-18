# 파일 경로: dvd_lite/dvd_attacks_lpc/mtd/rl_train_v05.py
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
# Assuming existing rl_model_v05.py implements PPOAgent and ActorCritic
from .rl_model_v05 import PPOAgent # Import PPOAgent
from .rl_environment_v05 import NetworkEnv, ACTION_PARAM_KEYS, FEATURE_KEYS
from .rl_config_v05 import LOG_METRICS_DEFENSE, LOG_METRICS_ATTACK, LOG_METRICS_TIME_TO_EVENT, LOG_METRICS_DRS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Utility Functions for Training Loop ---

def _safe_mean(arr):
    """Calculates mean safely, returning 0.0 for empty arrays."""
    return np.mean(arr) if arr else 0.0

def _safe_divide(numerator, denominator):
    """Divides safely, returning 0.0 for empty arrays."""
    return numerator / denominator if denominator != 0 else 0.0

def calculate_metrics_from_infos(ep_infos):
    """
    Calculates detailed episode-level metrics from collected info dictionaries.
    Note: The environment's _get_current_metrics already calculates DRS/TTF 
    based on internal state at the last step. We aggregate and average other metrics here.
    
    Args:
        ep_infos (list): A list of dictionaries, one per episode step.
    
    Returns:
        dict: A dictionary of aggregated metrics for logging.
    """
    
    if not ep_infos:
        return {}

    # The last step's info dictionary contains the final episode-wide metrics (DRS, TTF, etc.)
    final_metrics = ep_infos[-1].get("Metrics", {})
    
    # 1. Collect policy parameter time-averages
    bl_level_mean = _safe_mean([info.get("Params/bl_level", 0.0) for info in ep_infos])
    decoy_ratio_mean = _safe_mean([info.get("Params/decoy_ratio", 0.0) for info in ep_infos])
    shuffle_intensity_mean = _safe_mean([info.get("Params/shuffle_intensity", 0.0) for info in ep_infos])
    
    # 2. Combine and re-group metrics for consistent logging structure
    metrics = {}
    
    # Core Metrics (from final step's comprehensive calculation)
    metrics.update(final_metrics.get("Defense", {}))
    metrics.update(final_metrics.get("Attack", {}))
    metrics.update(final_metrics.get("Time", {}))
    metrics.update(final_metrics.get("DRS", {}))
    
    # Policy Parameters (time-average)
    metrics["Policy/bl_level_mean"] = bl_level_mean
    metrics["Policy/decoy_ratio_mean"] = decoy_ratio_mean
    metrics["Policy/shuffle_intensity_mean"] = shuffle_intensity_mean

    return metrics

def train_ppo(args):
    # --- Setup and Initialization ---
    
    # Seed for reproducibility
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = args.torch_deterministic

    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")

    # Environment Setup
    # Max steps per episode is set via args before env initialization for consistency
    NetworkEnv.max_episode_steps = args.max_steps_per_episode
    env = NetworkEnv(seed=args.seed, seeker_level=args.seeker_level)
    
    # Logging Setup
    run_name = args.run_name if args.run_name else f"PPO_v06_vs_Seeker_L{args.seeker_level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log_path = os.path.join(args.log_dir, run_name)
    os.makedirs(log_path, exist_ok=True)
    
    writer = SummaryWriter(log_path)
    if args.wandb_project:
        wandb.init(
            project=args.wandb_project,
            entity=args.wandb_entity,
            sync_tensorboard=False, # Manual logging
            config=vars(args),
            name=run_name,
            dir=args.log_dir,
            reinit=True # Handle possible re-initialization cleanly
        )
        logger.info("WandB initialized.")
    
    # Agent Setup
    agent = PPOAgent(
        state_dim=env.observation_space.shape[0],
        action_dim=env.action_space.shape[0],
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
        device=device
    )

    # Total training steps and episodes
    total_episodes = args.total_episodes
    global_step = 0
    
    # For rolling window metrics (addressing the user's calculation error)
    episode_reward_window = deque(maxlen=args.metric_window_size)
    episode_metrics_window = deque(maxlen=args.metric_window_size)
    
    # --- Main Training Loop ---
    logger.info("Starting MTD PPO training loop. ")
    
    for episode in range(1, total_episodes + 1):
        try:
            state, info = env.reset(seed=args.seed + episode) # Reseed per episode
            done = False
            ep_reward = 0
            ep_steps = 0
            ep_infos = [] # Collect info for detailed end-of-episode metrics

            # --- Rollout Collection Phase ---
            while not done:
                # 1. Agent acts
                action, log_prob, value = agent.get_action_and_value(torch.as_tensor(state, dtype=torch.float32).to(device))
                
                # 2. Step environment
                # The environment returns next_state, reward, terminated, truncated, info
                next_state, reward, terminated, truncated, info = env.step(action.cpu().numpy())
                done = terminated or truncated

                # 3. Store transition
                agent.store_transition(
                    state, action.cpu().numpy(), log_prob.item(), reward, value.item(), done
                )
                
                state = next_state
                ep_reward += reward
                ep_steps += 1
                global_step += 1
                
                # We store a copy of the info dictionary for later metric calculation
                # Deep copy is important if info contains mutable objects, but here we assume it's flat/safe.
                ep_infos.append(info.copy()) 

                # Early stop on terminal condition if necessary
                if done:
                    break

            # --- Policy Update Phase ---
            if agent.ready_for_update():
                logger.info(f"Global Step {global_step}: Starting PPO update.")
                policy_loss, value_loss, entropy_loss, approx_kl, frac_var_explained = agent.update_policy()
                
                # Log PPO Update Stats
                writer.add_scalar("Loss/Policy_Loss", policy_loss, global_step)
                writer.add_scalar("Loss/Value_Loss", value_loss, global_step)
                writer.add_scalar("Loss/Entropy_Loss", entropy_loss, global_step)
                writer.add_scalar("Stats/Approx_KL", approx_kl, global_step)
                writer.add_scalar("Stats/Frac_Variance_Explained", frac_var_explained, global_step)
                
                if args.wandb_project:
                     wandb.log({
                        "Loss/Policy_Loss": policy_loss,
                        "Loss/Value_Loss": value_loss,
                        "Loss/Entropy_Loss": entropy_loss,
                        "Stats/Approx_KL": approx_kl,
                        "Stats/Frac_Variance_Explained": frac_var_explained,
                        "global_step": global_step,
                    })
                
                logger.info(f"PPO Update finished. Loss: {policy_loss:.4f}")
                agent.clear_buffer() # Clear buffer after update

            # --- Episode Logging and Metrics Aggregation ---
            
            # 1. Update rolling reward/metric windows
            episode_reward_window.append(ep_reward)
            current_metrics = calculate_metrics_from_infos(ep_infos)
            episode_metrics_window.append(current_metrics)
            
            # 2. Calculate windowed average metrics
            avg_reward = _safe_mean(episode_reward_window)
            
            # Calculate rolling averages for all collected metric keys
            window_metrics = {}
            # Get a superset of all keys present in the window
            all_keys = set().union(*(m.keys() for m in episode_metrics_window)) 
            for key in all_keys:
                window_metrics[key] = _safe_mean([m.get(key, 0.0) for m in episode_metrics_window])
            
            # 3. Log Episode Totals
            writer.add_scalar("Episode/Reward_Total", ep_reward, episode)
            writer.add_scalar("Episode/Reward_Mean_Window", avg_reward, episode)
            writer.add_scalar("Episode/Length", ep_steps, episode)
            
            log_data = {
                "Episode/Reward_Total": ep_reward,
                "Episode/Reward_Mean_Window": avg_reward,
                "Episode/Length": ep_steps,
                "global_step": global_step,
            }
            
            # 4. Log Detailed Metrics (Ep-level & Window Avg)
            for key, value in current_metrics.items():
                # Log current episode metric
                writer.add_scalar(key, value, episode)
                log_data[key] = value
                
                # Log windowed average metric (using consistent grouping)
                window_key = key.replace("/", "Window/") # e.g. Defense/R_succ -> DefenseWindow/R_succ
                writer.add_scalar(window_key, window_metrics[key], episode)
                log_data[window_key] = window_metrics[key]
                
            if args.wandb_project:
                wandb.log(log_data)
                
            logger.info(f"Episode {episode}/{total_episodes}: Reward={ep_reward:.2f} | S_MTD={current_metrics.get('Defense/S_MTD_overall', 0.0):.3f} | R_succ={current_metrics.get('Defense/R_succ', 0.0):.3f}")

        except Exception as e:
            logger.error(f"An error occurred during episode {episode}: {e}")
            if args.wandb_project:
                wandb.log({"error": f"Episode {episode} failed with error: {e}", "global_step": global_step})
            # Attempt to save model before exiting (simple save)
            if agent.network is not None:
                 torch.save(agent.network.state_dict(), os.path.join(log_path, f"checkpoint_ep{episode}.pth"))
            break


    # --- Finalization ---
    logger.info("Training finished. Closing writers.")
    writer.close()
    if args.wandb_project:
        wandb.finish()
        
    # Save final model and normalization data (Simplified export via PPOAgent)
    final_model_path = os.path.join(log_path, "final_policy.pth")
    agent.save_policy(final_model_path)
    
    # Save dummy normalization data (to be consistent with export script requirement)
    norm_metadata = {
        "FEATURE_KEYS": FEATURE_KEYS,
        "ACTION_PARAM_KEYS": ACTION_PARAM_KEYS,
        "FEATURE_NORM_METADATA": {"means": [0.0]*len(FEATURE_KEYS), "stds": [1.0]*len(FEATURE_KEYS)}
    }
    with open(os.path.join(log_path, "norm_metadata.json"), 'w') as f:
        json.dump(norm_metadata, f, indent=4)
        
    logger.info(f"Final policy saved to {final_model_path}")
    logger.info(f"Training log data saved to {log_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="MTD PPO Reinforcement Learning Trainer")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--cuda", action="store_true", default=False, help="Enable CUDA training")
    parser.add_argument("--torch-deterministic", action="store_true", default=True, help="Make torch operations deterministic")
    
    # Environment Params
    parser.add_argument("--seeker-level", type=int, default=2, help="Seeker difficulty level (0-3)")
    parser.add_argument("--total-episodes", type=int, default=1000, help="Total number of episodes to train")
    parser.add_argument("--max-steps-per-episode", type=int, default=1000, help="Maximum steps per episode")
    
    # PPO Hyperparameters
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="Learning rate for policy and value networks")
    parser.add_argument("--hidden-size", type=int, default=128, help="Hidden layer size for networks")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor (gamma)")
    parser.add_argument("--gae-lambda", type=float, default=0.95, help="GAE lambda parameter")
    parser.add_argument("--clip-coef", type=float, default=0.2, help="PPO clipping coefficient")
    parser.add_argument("--ent-coef", type=float, default=0.01, help="Entropy coefficient")
    parser.add_argument("--vf-coef", type=float, default=0.5, help="Value function coefficient")
    parser.add_argument("--ppo-epochs", type=int, default=10, help="Number of epochs to run PPO update per batch")
    parser.add_argument("--minibatch-size", type=int, default=64, help="Minibatch size for optimization")
    parser.add_argument("--target-kl", type=float, default=0.015, help="Target KL divergence threshold")

    # Logging/Reporting
    parser.add_argument("--log-dir", type=str, default="runs", help="Directory for TensorBoard/Model logs")
    parser.add_argument("--wandb-project", type=str, default="mtd_rl_v06", help="WandB project name")
    parser.add_argument("--wandb-entity", type=str, default=None, help="WandB entity/user name")
    parser.add_argument("--metric-window-size", type=int, default=50, help="Window size for calculating mean episode metrics")

    args = parser.parse_args()
    
    # Set max episode steps in environment configuration
    NetworkEnv.max_episode_steps = args.max_steps_per_episode

    train_ppo(args)