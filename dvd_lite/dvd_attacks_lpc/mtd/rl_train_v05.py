#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_train_v05.py

MTD PPO 학습 스크립트 (v0.5, 테스트베드 정합성 강화판)

- NetworkEnv (rl_environment_v05)
- MTDPolicyNet / MTDValueNet (rl_model_v05)
- PPO 업데이트
- 에피소드 단위 MTD 지표(S_D, R_A, C_M, S_MTD) 계산 및 로깅
- 모든 Seeker 레벨(L0~L4)에서 파생 학습 가능 (--train-all-seeker-levels)
"""

import argparse
import time
from dataclasses import asdict
from typing import Dict, Any, List

import numpy as np
import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter

from rl_config_v05 import RLConfigV05, OBS_DIM, ACTION_DIM
from rl_environment_v05 import NetworkEnv
from rl_model_v05 import MTDPolicyNet, MTDValueNet

try:
    import wandb  # type: ignore
    WANDB_AVAILABLE = True
except Exception:
    wandb = None  # type: ignore
    WANDB_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MTD PPO Trainer v0.5 (testbed-aligned)")

    # 학습 스텝 관련
    parser.add_argument("--total-timesteps", type=int, default=200_000,
                        help="총 time step 수 (updates 미사용 시)")
    parser.add_argument("--updates", type=int, default=None,
                        help="(선택) update 횟수. 지정 시 total_timesteps = updates * batch_size")
    parser.add_argument("--batch-size", type=int, default=2048,
                        help="한 번의 rollout에서 수집할 step 수 (PPO batch size)")
    parser.add_argument("--minibatch-size", type=int, default=64,
                        help="PPO 업데이트 시 사용하는 mini-batch 크기")

    # PPO 하이퍼파라미터
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-coef", type=float, default=0.2)

    parser.add_argument("--update-epochs", "--n-epochs", dest="update_epochs",
                        type=int, default=10,
                        help="한 batch에 대해 PPO 업데이트 반복 횟수")
    parser.add_argument("--ent-coef", type=float, default=0.01)
    parser.add_argument("--vf-coef", type=float, default=0.5)
    parser.add_argument("--max-grad-norm", type=float, default=0.5)

    parser.add_argument("--learning-rate", "--lr", dest="learning_rate",
                        type=float, default=3e-4,
                        help="optimizer learning rate")

    # Seeker 관련
    parser.add_argument("--seeker-level", type=int, default=2,
                        help="단일 level 학습 시 사용할 seeker level")
    parser.add_argument("--train-all-seeker-levels", action="store_true", default=False,
                        help="에피소드마다 seeker 레벨을 seeker-levels 중 하나로 랜덤 선택")
    parser.add_argument("--seeker-levels", type=int, nargs="+",
                        default=[0, 1, 2, 3, 4],
                        help="--train-all-seeker-levels 사용 시 사용할 seeker 레벨 리스트")

    # 기타 설정
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", type=str, default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--max-episode-steps", type=int, default=512)

    # 로깅 / export
    parser.add_argument("--log-dir", type=str, default="./runs/mtd_v05")
    parser.add_argument("--run-name", type=str, default="mtd_rl_v05")
    parser.add_argument("--wandb-project", type=str, default="MTD_RL_v05",
                        help="wandb 프로젝트 이름")
    parser.add_argument("--disable-wandb", action="store_true", default=False)

    parser.add_argument("--export-dir", type=str, default="./mtd/rl_models/ver_05",
                        help="정책 export 경로")
    parser.add_argument("--no-export", action="store_true", default=False,
                        help="학습 후 정책 export 하지 않음")

    return parser.parse_args()


# --------------------------------------------------------------------------- #
# PPO Agent
# --------------------------------------------------------------------------- #

class PPOAgent:
    def __init__(self, cfg: RLConfigV05, device: torch.device, minibatch_size: int = 64) -> None:
        self.cfg = cfg
        self.device = device
        self.minibatch_size = minibatch_size

        self.actor = MTDPolicyNet().to(device)
        self.critic = MTDValueNet().to(device)

        self.optimizer = torch.optim.Adam(
            list(self.actor.parameters()) + list(self.critic.parameters()),
            lr=cfg.learning_rate,
        )

        bsz = cfg.batch_size
        self.obs_buf = torch.zeros((bsz, OBS_DIM), dtype=torch.float32, device=device)
        self.action_buf = torch.zeros((bsz, ACTION_DIM), dtype=torch.float32, device=device)
        self.logprob_buf = torch.zeros((bsz,), dtype=torch.float32, device=device)
        self.reward_buf = torch.zeros((bsz,), dtype=torch.float32, device=device)
        self.done_buf = torch.zeros((bsz,), dtype=torch.float32, device=device)
        self.value_buf = torch.zeros((bsz,), dtype=torch.float32, device=device)

    @torch.no_grad()
    def get_action_and_value(
        self,
        obs: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        obs = obs.to(self.device)
        dist = self.actor.get_dist(obs)
        action = dist.sample()
        log_prob = dist.log_prob(action).sum(-1)
        value = self.critic(obs)
        return action, log_prob, value

    def update(
        self,
        advantages: torch.Tensor,
        returns: torch.Tensor,
        b_obs: torch.Tensor,
        b_actions: torch.Tensor,
        b_logprobs: torch.Tensor,
    ) -> Dict[str, float]:
        cfg = self.cfg
        bsz = cfg.batch_size

        advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)

        batch_inds = np.arange(bsz)
        metrics: Dict[str, float] = {}

        for _ in range(cfg.update_epochs):
            np.random.shuffle(batch_inds)
            for start in range(0, bsz, self.minibatch_size):
                end = start + self.minibatch_size
                mb_inds = batch_inds[start:end]
                mb_obs = b_obs[mb_inds]
                mb_actions = b_actions[mb_inds]
                mb_logprobs = b_logprobs[mb_inds]
                mb_advantages = advantages[mb_inds]
                mb_returns = returns[mb_inds]

                dist = self.actor.get_dist(mb_obs)
                new_logprobs = dist.log_prob(mb_actions).sum(-1)
                entropy = dist.entropy().sum(-1).mean()

                ratio = (new_logprobs - mb_logprobs).exp()
                pg_loss1 = -mb_advantages * ratio
                pg_loss2 = -mb_advantages * torch.clamp(
                    ratio,
                    1.0 - cfg.clip_coef,
                    1.0 + cfg.clip_coef,
                )
                pg_loss = torch.max(pg_loss1, pg_loss2).mean()

                value = self.critic(mb_obs)
                v_loss = 0.5 * (mb_returns - value).pow(2).mean()

                loss = pg_loss + cfg.vf_coef * v_loss - cfg.ent_coef * entropy

                self.optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(
                    list(self.actor.parameters()) + list(self.critic.parameters()),
                    cfg.max_grad_norm,
                )
                self.optimizer.step()

                metrics["train/policy_loss"] = float(pg_loss.item())
                metrics["train/value_loss"] = float(v_loss.item())
                metrics["train/entropy"] = float(entropy.item())

        return metrics


# --------------------------------------------------------------------------- #
# Training Loop
# --------------------------------------------------------------------------- #

def run_training(args: argparse.Namespace) -> None:
    # RLConfigV05 구성
    cfg = RLConfigV05(
        seed=args.seed,
        seeker_level=args.seeker_level,
        total_timesteps=args.total_timesteps,
        batch_size=args.batch_size,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_coef=args.clip_coef,
        update_epochs=args.update_epochs,
        ent_coef=args.ent_coef,
        vf_coef=args.vf_coef,
        max_grad_norm=args.max_grad_norm,
        learning_rate=args.learning_rate,
    )

    # updates 옵션이 있으면 total_timesteps 재계산
    if args.updates is not None:
        cfg.total_timesteps = args.updates * cfg.batch_size

    device = torch.device(args.device if torch.cuda.is_available() and args.device == "cuda" else "cpu")

    # 시드 고정
    np.random.seed(cfg.seed)
    torch.manual_seed(cfg.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(cfg.seed)

    # 환경 / 에이전트
    env = NetworkEnv(
        seeker_level=cfg.seeker_level,
        seed=cfg.seed,
        max_episode_steps=args.max_episode_steps,
    )
    agent = PPOAgent(cfg, device=device, minibatch_size=args.minibatch_size)

    # 로깅
    writer = SummaryWriter(log_dir=args.log_dir + "/" + args.run_name)
    use_wandb = WANDB_AVAILABLE and not args.disable_wandb

    if use_wandb:
        wandb.init(
            project=args.wandb_project,
            name=args.run_name,
            config=asdict(cfg),
        )

    obs = env.reset()
    obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)

    global_step = 0
    if args.updates is not None:
        num_updates = args.updates
    else:
        num_updates = cfg.total_timesteps // cfg.batch_size

    # 최근 에피소드 윈도우 (MTD 지표 moving average 용)
    window_size = 50
    recent_eps_scores: List[Dict[str, float]] = []

    start_time = time.time()

    for update in range(num_updates):
        # Rollout 수집
        for step in range(cfg.batch_size):
            with torch.no_grad():
                action_t, logprob_t, value_t = agent.get_action_and_value(obs_t.unsqueeze(0))
            action = action_t.squeeze(0).cpu().numpy()

            next_obs, reward, done, info = env.step(action)

            agent.obs_buf[step] = obs_t
            agent.action_buf[step] = torch.as_tensor(action, dtype=torch.float32, device=device)
            agent.logprob_buf[step] = logprob_t.squeeze(0)
            agent.reward_buf[step] = float(reward)
            agent.done_buf[step] = float(done)
            agent.value_buf[step] = value_t.squeeze(0)

            global_step += 1
            obs = next_obs
            obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)

            # episode 종료 시 MTD 지표 계산
            if done:
                ep_len = env.episode_step
                ep_ret = env.ep_return
                attack_steps = max(env.ep_attack_steps, 1)
                decoy_steps = env.ep_decoy_attack_steps
                breach_events = env.ep_breach_events
                ep_cost = env.ep_mtd_cost

                # S_D, R_A, C_M, S_MTD
                s_d = float(decoy_steps / attack_steps)
                r_a = float(1.0 - (breach_events / attack_steps))
                c_m = float(ep_cost / max(ep_len, 1))
                s_mtd = 0.5 * s_d + 0.5 * r_a - 0.1 * c_m

                ep_metrics = {
                    "Episode/return": ep_ret,
                    "Episode/length": ep_len,
                    "Episode/S_D_decoy_success": s_d,
                    "Episode/R_A_resilience": r_a,
                    "Episode/C_M_cost": c_m,
                    "Episode/S_MTD_overall": s_mtd,
                    "Episode/attack_steps": env.ep_attack_steps,
                    "Episode/detected_attack_steps": env.ep_detected_attack_steps,
                    "Episode/decoy_attack_steps": env.ep_decoy_attack_steps,
                    "Episode/breach_events": env.ep_breach_events,
                    "Episode/mtd_cost": env.ep_mtd_cost,
                    "Episode/reconfig_steps": env.ep_reconfig_steps,
                }

                # TensorBoard 기록
                for k, v in ep_metrics.items():
                    writer.add_scalar(k, v, global_step)

                # 최근 윈도우에 추가
                recent_eps_scores.append(ep_metrics)
                if len(recent_eps_scores) > window_size:
                    recent_eps_scores.pop(0)

                # 최근 윈도우 평균 기록
                if len(recent_eps_scores) >= 5:
                    avg = {}
                    for k in recent_eps_scores[0].keys():
                        avg[k] = float(
                            sum(e[k] for e in recent_eps_scores) / len(recent_eps_scores)
                        )
                    writer.add_scalar("EpisodeWindow/S_MTD_overall", avg["Episode/S_MTD_overall"], global_step)
                    writer.add_scalar("EpisodeWindow/S_D_decoy_success", avg["Episode/S_D_decoy_success"], global_step)
                    writer.add_scalar("EpisodeWindow/R_A_resilience", avg["Episode/R_A_resilience"], global_step)
                    writer.add_scalar("EpisodeWindow/C_M_cost", avg["Episode/C_M_cost"], global_step)

                    if use_wandb:
                        wandb.log(
                            {
                                "EpisodeWindow/S_MTD_overall": avg["Episode/S_MTD_overall"],
                                "EpisodeWindow/S_D_decoy_success": avg["Episode/S_D_decoy_success"],
                                "EpisodeWindow/R_A_resilience": avg["Episode/R_A_resilience"],
                                "EpisodeWindow/C_M_cost": avg["Episode/C_M_cost"],
                                "global_step": global_step,
                            }
                        )

                if use_wandb:
                    wandb.log({**ep_metrics, "global_step": global_step})

                # --- 모든 seeker 레벨 학습 모드일 때 레벨 랜덤 스위칭 ---
                if args.train_all_seeker_levels:
                    new_level = int(np.random.choice(args.seeker_levels))
                    env.seeker_level = new_level
                    writer.add_scalar("Seeker/level", new_level, global_step)
                    if use_wandb:
                        wandb.log({"Seeker/level": new_level, "global_step": global_step})

                # 에피소드 리셋
                obs = env.reset()
                obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)

        # GAE 계산
        with torch.no_grad():
            _, _, last_val = agent.get_action_and_value(obs_t.unsqueeze(0))
            last_val = last_val.squeeze(0)

        advantages = torch.zeros_like(agent.reward_buf, device=device)
        last_gae_lam = 0.0
        for t in reversed(range(cfg.batch_size)):
            if t == cfg.batch_size - 1:
                next_non_terminal = 1.0 - agent.done_buf[t]
                next_value = last_val
            else:
                next_non_terminal = 1.0 - agent.done_buf[t + 1]
                next_value = agent.value_buf[t + 1]

            delta = (
                agent.reward_buf[t]
                + cfg.gamma * next_value * next_non_terminal
                - agent.value_buf[t]
            )
            last_gae_lam = (
                delta
                + cfg.gamma * cfg.gae_lambda * next_non_terminal * last_gae_lam
            )
            advantages[t] = last_gae_lam

        returns = advantages + agent.value_buf

        # PPO 업데이트
        metrics = agent.update(
            advantages,
            returns,
            agent.obs_buf,
            agent.action_buf,
            agent.logprob_buf,
        )

        for k, v in metrics.items():
            writer.add_scalar(k, v, global_step)

        if use_wandb:
            wandb.log({**metrics, "global_step": global_step})

        if (update + 1) % 10 == 0:
            fps = int(global_step / (time.time() - start_time))
            print(
                f"[Update {update+1}/{num_updates}] "
                f"global_step={global_step}, fps={fps}, "
                f"policy_loss={metrics.get('train/policy_loss', 0.0):.3f}, "
                f"value_loss={metrics.get('train/value_loss', 0.0):.3f}"
            )

    # 종료 처리
    writer.flush()
    writer.close()
    if use_wandb:
        wandb.finish()

    # 정책 export (선택)
    if not args.no_export:
        try:
            from rl_export_policy_v05 import export_mtd_policy
            import os

            os.makedirs(args.export_dir, exist_ok=True)
            # TODO: 원하면 state_history 수집해서 feature_norm 진짜로 계산할 수 있음
            state_history: List[np.ndarray] = []
            export_mtd_policy(
                policy_net=agent.actor.to("cpu"),
                state_history=state_history,
                save_dir=args.export_dir,
                version="ver_05_all" if args.train_all_seeker_levels else "ver_05",
            )
            print(f"[+] Exported policy to {args.export_dir}")
        except Exception as e:
            print(f"[!] Failed to export policy: {e}")


if __name__ == "__main__":
    run_training(parse_args())
