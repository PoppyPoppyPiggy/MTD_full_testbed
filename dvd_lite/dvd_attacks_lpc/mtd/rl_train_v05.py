# 파일 경로: dvd_lite/dvd_attacks_lpc/mtd/rl_train_v05.py
import argparse
import random
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
from .rl_environment_v05 import NetworkEnv, ACTION_PARAM_KEYS, FEATURE_KEYS
from .rl_config_v05 import (
    LOG_METRICS_DEFENSE,
    LOG_METRICS_ATTACK,
    LOG_METRICS_TIME_TO_EVENT,
    LOG_METRICS_DRS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ----------------------------
# 유틸 함수
# ----------------------------
def _safe_mean(arr):
    return float(np.mean(arr)) if arr else 0.0


def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator != 0 else 0.0


def calculate_metrics_from_infos(ep_infos):
    """
    한 에피소드 동안 env.step()에서 모은 info 리스트(ep_infos)를 받아
    마지막 스텝에 들어있는 Metrics(Defense/Attack/Time/DRS) + 정책 파라미터 평균을 합친 dict 반환
    """
    if not ep_infos:
        return {}

    final_info = ep_infos[-1]
    final_metrics = final_info.get("Metrics", {})

    bl_level_mean = _safe_mean([info.get("Params/bl_level", 0.0) for info in ep_infos])
    decoy_ratio_mean = _safe_mean([info.get("Params/decoy_ratio", 0.0) for info in ep_infos])
    shuffle_intensity_mean = _safe_mean(
        [info.get("Params/shuffle_intensity", 0.0) for info in ep_infos]
    )

    metrics = {}
    metrics.update(final_metrics.get("Defense", {}))
    metrics.update(final_metrics.get("Attack", {}))
    metrics.update(final_metrics.get("Time", {}))
    metrics.update(final_metrics.get("DRS", {}))

    metrics["Policy/bl_level_mean"] = bl_level_mean
    metrics["Policy/decoy_ratio_mean"] = decoy_ratio_mean
    metrics["Policy/shuffle_intensity_mean"] = shuffle_intensity_mean

    return metrics


# ----------------------------
# 학습 메인 함수
# ----------------------------
def train_ppo(args):
    # 시드 & 디바이스
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = args.torch_deterministic
    torch.backends.cudnn.benchmark = not args.torch_deterministic

    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")
    logger.info(f"Using device: {device}")

    # 환경 설정
    NetworkEnv.max_episode_steps = args.max_steps_per_episode
    env = NetworkEnv(seed=args.seed, seeker_level=args.seeker_level)

    # 로그 디렉토리 준비
    os.makedirs(args.log_dir, exist_ok=True)

    # run 이름 구성 (Seeker 단일 vs 전체 레벨)
    if args.train_all_seeker_levels:
        seeker_tag = f"Lmix_{'-'.join(str(l) for l in args.seeker_levels)}"
    else:
        seeker_tag = f"L{args.seeker_level}"

    if args.run_name:
        run_name = args.run_name
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"PPO_v06_vs_Seeker_{seeker_tag}_{ts}"

    log_path = os.path.join(args.log_dir, run_name)
    os.makedirs(log_path, exist_ok=True)

    writer = SummaryWriter(log_path)

    # wandb 사용 여부 (project가 빈 문자열이면 비활성)
    use_wandb = bool(args.wandb_project)
    if use_wandb:
        wandb.init(
            project=args.wandb_project,
            entity=args.wandb_entity,
            config=vars(args),
            name=run_name,
            dir=args.log_dir,
            sync_tensorboard=False,  # 수동 로그
            reinit=True,
        )
        logger.info(
            f"WandB initialized (project={args.wandb_project}, entity={args.wandb_entity}, run={run_name})"
        )
    else:
        logger.info("WandB disabled (wandb_project is empty).")

    # PPO Agent 초기화
    max_grad_norm = getattr(args, "max_grad_norm", 0.5)

    agent = PPOAgent(
        state_dim=env.observation_space.shape[0],
        action_dim=env.action_space.shape[0],
        hidden_size=args.hidden_size,
        lr=args.learning_rate,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_coef=args.clip_coef,
        max_grad_norm=max_grad_norm,
        ent_coef=args.ent_coef,
        vf_coef=args.vf_coef,
        ppo_epochs=args.ppo_epochs,
        minibatch_size=args.minibatch_size,
        target_kl=args.target_kl,
        device=device,
    )

    total_episodes = args.total_episodes
    global_step = 0

    episode_reward_window = deque(maxlen=args.metric_window_size)
    episode_metrics_window = deque(maxlen=args.metric_window_size)

    logger.info("Starting MTD PPO training loop.")

    # ----------------------------
    # 에피소드 루프
    # ----------------------------
    for episode in range(1, total_episodes + 1):
        try:
            # Seeker 레벨 선택 (고정 vs 랜덤)
            if args.train_all_seeker_levels:
                current_seeker_level = random.choice(args.seeker_levels)
                env.seeker_level = current_seeker_level
            else:
                current_seeker_level = args.seeker_level
                env.seeker_level = current_seeker_level

            # 에피소드별 seed 조금씩 바꿔주기
            state, info = env.reset(seed=args.seed + episode)
            done = False
            ep_reward = 0.0
            ep_steps = 0
            ep_infos = []

            # -------- Rollout --------
            while not done:
                state_tensor = torch.as_tensor(state, dtype=torch.float32).to(device).unsqueeze(0)
                action, log_prob, value = agent.get_action_and_value(state_tensor)

                next_state, reward, terminated, truncated, info = env.step(
                    action.cpu().numpy().squeeze(0)
                )
                done = terminated or truncated

                agent.store_transition(
                    state,
                    action.squeeze(0).cpu().numpy(),
                    log_prob.item(),
                    reward,
                    value.item(),
                    done,
                )

                state = next_state
                ep_reward += reward
                ep_steps += 1
                global_step += 1

                ep_infos.append(info.copy())

                if done:
                    break

            # -------- PPO 업데이트 --------
            if agent.ready_for_update():
                logger.info(f"[Update] Global Step {global_step}: Starting PPO update.")
                policy_loss, value_loss, entropy_loss, approx_kl, frac_var_explained = (
                    agent.update_policy()
                )

                writer.add_scalar("Loss/Policy_Loss", policy_loss, global_step)
                writer.add_scalar("Loss/Value_Loss", value_loss, global_step)
                writer.add_scalar("Loss/Entropy_Loss", entropy_loss, global_step)
                writer.add_scalar("Stats/Approx_KL", approx_kl, global_step)
                writer.add_scalar("Stats/Frac_Variance_Explained", frac_var_explained, global_step)

                if use_wandb:
                    wandb.log(
                        {
                            "Loss/Policy_Loss": policy_loss,
                            "Loss/Value_Loss": value_loss,
                            "Loss/Entropy_Loss": entropy_loss,
                            "Stats/Approx_KL": approx_kl,
                            "Stats/Frac_Variance_Explained": frac_var_explained,
                            "global_step": global_step,
                        }
                    )

                logger.info(f"[Update] PPO finished. PolicyLoss={policy_loss:.4f}")
                agent.clear_buffer()

            # -------- 에피소드 메트릭 집계 --------
            episode_reward_window.append(ep_reward)
            current_metrics = calculate_metrics_from_infos(ep_infos)
            episode_metrics_window.append(current_metrics)

            avg_reward = _safe_mean(episode_reward_window)

            # window 평균 메트릭
            window_metrics = {}
            all_keys = set().union(*(m.keys() for m in episode_metrics_window))
            for key in all_keys:
                window_metrics[key] = _safe_mean([m.get(key, 0.0) for m in episode_metrics_window])

            # 기본 Episode 정보
            writer.add_scalar("Episode/Reward_Total", ep_reward, episode)
            writer.add_scalar("Episode/Reward_Mean_Window", avg_reward, episode)
            writer.add_scalar("Episode/Length", ep_steps, episode)
            writer.add_scalar("Episode/Seeker_Level", current_seeker_level, episode)

            log_data = {
                "Episode/Reward_Total": ep_reward,
                "Episode/Reward_Mean_Window": avg_reward,
                "Episode/Length": ep_steps,
                "Episode/Seeker_Level": current_seeker_level,
                "global_step": global_step,
            }

            # 상세 Defense/Attack/Time/DRS 메트릭
            for key, value in current_metrics.items():
                writer.add_scalar(key, value, episode)
                log_data[key] = value

                window_key = key.replace("/", "Window/")
                writer.add_scalar(window_key, window_metrics[key], episode)
                log_data[window_key] = window_metrics[key]

            if use_wandb:
                wandb.log(log_data)

            logger.info(
                f"Episode {episode}/{total_episodes} "
                f"[Seeker L{current_seeker_level}] "
                f"Reward={ep_reward:.2f} "
                f"S_MTD={current_metrics.get('Defense/S_MTD_overall', 0.0):.3f} "
                f"R_succ={current_metrics.get('Defense/R_succ', 0.0):.3f}"
            )

        except Exception as e:
            logger.error(f"An error occurred during episode {episode}: {e}")
            if use_wandb:
                wandb.log(
                    {
                        "error": f"Episode {episode} failed with error: {e}",
                        "global_step": global_step,
                    }
                )
            # 체크포인트 한번은 시도
            try:
                ckpt_path = os.path.join(log_path, f"checkpoint_ep{episode}.pth")
                torch.save(agent.network.state_dict(), ckpt_path)
                logger.info(f"Checkpoint saved to {ckpt_path}")
            except Exception as ee:
                logger.error(f"Failed to save checkpoint: {ee}")
            break

    # ----------------------------
    # 종료 처리
    # ----------------------------
    logger.info("Training finished. Closing writers.")
    writer.close()
    if use_wandb:
        wandb.finish()

    final_model_path = os.path.join(log_path, "final_policy.pth")
    agent.save_policy(final_model_path)

    norm_metadata = {
        "FEATURE_KEYS": FEATURE_KEYS,
        "ACTION_PARAM_KEYS": ACTION_PARAM_KEYS,
        "FEATURE_NORM_METADATA": {
            "means": [0.0] * len(FEATURE_KEYS),
            "stds": [1.0] * len(FEATURE_KEYS),
        },
    }
    with open(os.path.join(log_path, "norm_metadata.json"), "w") as f:
        json.dump(norm_metadata, f, indent=4)

    logger.info(f"Final policy saved to {final_model_path}")
    logger.info(f"Training log data saved to {log_path}")


# ----------------------------
# CLI 인자 정의
# ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MTD PPO Reinforcement Learning Trainer (v06)")

    # Seed / Device
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--cuda", action="store_true", default=False, help="Enable CUDA training")
    parser.add_argument(
        "--torch-deterministic",
        action="store_true",
        default=True,
        help="Make torch operations deterministic",
    )

    # Environment Params
    parser.add_argument("--seeker-level", type=int, default=2, help="Single seeker level (0-3)")
    parser.add_argument(
        "--train-all-seeker-levels",
        action="store_true",
        help="If set, randomly samples seeker level from --seeker-levels per episode",
    )
    parser.add_argument(
        "--seeker-levels",
        type=int,
        nargs="+",
        default=[0, 1, 2, 3],
        help="Candidate seeker levels when --train-all-seeker-levels is enabled",
    )
    parser.add_argument("--total-episodes", type=int, default=1000, help="Total episodes to train")
    parser.add_argument(
        "--max-steps-per-episode",
        type=int,
        default=1000,
        help="Maximum env steps per episode",
    )

    # PPO Hyperparameters
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--hidden-size", type=int, default=128, help="Hidden layer size")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    parser.add_argument("--gae-lambda", type=float, default=0.95, help="GAE lambda")
    parser.add_argument("--clip-coef", type=float, default=0.2, help="PPO clip coefficient")
    parser.add_argument(
        "--max-grad-norm", type=float, default=0.5, help="Max gradient norm for clipping"
    )
    parser.add_argument("--ent-coef", type=float, default=0.01, help="Entropy coefficient")
    parser.add_argument("--vf-coef", type=float, default=0.5, help="Value function coefficient")
    parser.add_argument("--ppo-epochs", type=int, default=10, help="PPO epochs per update")
    parser.add_argument("--minibatch-size", type=int, default=64, help="Minibatch size")
    parser.add_argument("--target-kl", type=float, default=0.015, help="Target KL threshold")

    # Logging / W&B (여기서 인자로 받음)
    parser.add_argument(
        "--log-dir",
        type=str,
        default="./runs",
        help="Directory for TensorBoard/Model logs",
    )
    parser.add_argument("--run-name", type=str, default=None, help="Custom run name")

    parser.add_argument(
        "--wandb-project",
        type=str,
        default="mtd_rl_v06_comparison",
        help="WandB project name (''이면 W&B 미사용)",
    )
    parser.add_argument(
        "--wandb-entity",
        type=str,
        default="emforhsqhf29-",
        help="WandB entity/user name",
    )
    parser.add_argument(
        "--metric-window-size",
        type=int,
        default=50,
        help="Window size for averaging episode metrics",
    )

    args = parser.parse_args()
    NetworkEnv.max_episode_steps = args.max_steps_per_episode
    train_ppo(args)
