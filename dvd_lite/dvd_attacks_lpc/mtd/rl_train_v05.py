#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 v05] MTD-RL PPO Trainer (MTD 전용 학습 스크립트)

- rl_environment_v05 : 시뮬레이션 환경
- rl_model_v05       : 정책/가치 신경망
- rl_config_v05      : 상태/행동 공간 정의
- rl_export_policy_v05 : 학습된 정책 내보내기

[MTD 지표 통합 레이어]
- 에피소드 단위로 다음 지표 계산:
    - T_A: 공격이 활성화된 스텝 수 (Total attack steps)
    - T_D: 공격 중 디코이 노드에 머문 스텝 수 (Decoy steps while attacked)
    - N_A: 성공적인 공격(침투) 횟수
    - N_R: 재구성(Reconfiguration) 횟수
    - C_M: 에피소드 평균 MTD 비용

    - S_D = T_D / T_A (if T_A>0 else 0)
    - R_A = min(N_R, R_MAX) if N_A==0 else N_R / N_A
    - S_MTD = W_S_D * S_D + W_R_A * R_A - W_C_M * C_M

- TensorBoard / wandb 로깅 키:
    Episode/*
    Metric/*
"""

import os
import argparse
import time
import random
from typing import Any, Dict

import numpy as np
import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter

from .rl_environment_v05 import NetworkEnv
from .rl_model_v05 import MTDPolicyNet, MTDValueNet
from .rl_config_v05 import OBS_DIM, ACTION_DIM
from .rl_export_policy_v05 import export_mtd_policy

try:
    import wandb
except ImportError:
    wandb = None
    print("Warning: 'wandb' 패키지가 없습니다. (pip install wandb). --disable-wandb 플래그가 강제 활성화됩니다.")

# ----- [MTD 스코어 가중치] v02와 동일 -----
W_S_D = 0.5  # Deception success
W_R_A = 0.3  # Attack resilience
W_C_M = 0.2  # MTD cost
R_MAX = 10.0  # R_A 상한
# ----------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(description="MTD-RL v05 PPO 학습 스크립트")

    # PPO 하이퍼파라미터
    parser.add_argument("--lr", type=float, default=3e-4, help="학습률")
    parser.add_argument("--gamma", type=float, default=0.99, help="할인 계수")
    parser.add_argument("--gae-lambda", type=float, default=0.95, help="GAE 람다")
    parser.add_argument("--clip-coef", type=float, default=0.2, help="PPO 클리핑 계수")
    parser.add_argument("--ent-coef", type=float, default=0.01, help="엔트로피 계수")
    parser.add_argument("--vf-coef", type=float, default=0.5, help="가치 함수 계수")
    parser.add_argument("--max-grad-norm", type=float, default=0.5, help="그라디언트 클리핑 최대치")

    # 학습 실행 설정
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--updates", type=int, default=1500, help="총 학습 업데이트 횟수")
    parser.add_argument("--batch-size", type=int, default=2048, help="배치 크기 (롤아웃 버퍼 크기)")
    parser.add_argument("--minibatch-size", type=int, default=64, help="미니배치 크기")
    parser.add_argument("--n-epochs", type=int, default=10, help="한 배치의 업데이트 에포크 수")
    parser.add_argument("--max-episode-steps", type=int, default=500, help="환경 최대 스텝 수")

    # 환경(Seeker) 설정
    parser.add_argument(
        "--seeker-level",
        type=int,
        default=2,
        choices=[0, 1, 2, 3, 4],
        help="Seeker 난이도 (0~4)",
    )

    # 로깅 및 저장 설정
    parser.add_argument("--wandb-project", type=str, default="MTD_RL_v05_Passive_CTI", help="Wandb 프로젝트 이름")
    parser.add_argument(
        "--run-name",
        type=str,
        default="PPO_v05_vs_Seeker_L2",
        help="Wandb 실행 이름 (TensorBoard 로그 디렉토리 이름에도 사용)",
    )
    parser.add_argument("--disable-wandb", action="store_true", help="Wandb 로깅 비활성화")
    parser.add_argument(
        "--export-dir",
        type=str,
        default="./mtd/rl_models/ver_05_L2",
        help="학습 완료 후 모델 저장 기본 경로",
    )

    # 멀티 레벨 학습 옵션
    parser.add_argument(
        "--train-all-seeker-levels",
        action="store_true",
        help="L0~L4 모든 seeker 레벨을 순차적으로 학습",
    )

    args = parser.parse_args()
    args.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if wandb is None:
        args.disable_wandb = True
    return args


class PPOAgent:
    """ PPO 에이전트 (신경망, 옵티마이저, 버퍼 포함) """

    def __init__(self, cfg):
        self.cfg = cfg
        self.obs_dim = OBS_DIM
        self.act_dim = ACTION_DIM

        # Actor / Critic 네트워크
        self.policy_net = MTDPolicyNet(self.obs_dim, self.act_dim).to(cfg.device)
        self.value_net = MTDValueNet(self.obs_dim).to(cfg.device)

        # 옵티마이저
        self.policy_optimizer = torch.optim.Adam(self.policy_net.parameters(), lr=cfg.lr, eps=1e-5)
        self.value_optimizer = torch.optim.Adam(self.value_net.parameters(), lr=cfg.lr, eps=1e-5)

        # 롤아웃 버퍼
        self.obs = torch.zeros((cfg.batch_size, self.obs_dim), dtype=torch.float32, device=cfg.device)
        self.actions = torch.zeros((cfg.batch_size, self.act_dim), dtype=torch.float32, device=cfg.device)
        self.logprobs = torch.zeros((cfg.batch_size,), dtype=torch.float32, device=cfg.device)
        self.rewards = torch.zeros((cfg.batch_size,), dtype=torch.float32, device=cfg.device)
        self.dones = torch.zeros((cfg.batch_size,), dtype=torch.float32, device=cfg.device)
        self.values = torch.zeros((cfg.batch_size,), dtype=torch.float32, device=cfg.device)

    def get_action_and_value(self, obs: torch.Tensor, done_mask: torch.Tensor):
        """현재 관찰(obs)로 행동, 로그확률, 가치(value) 계산"""
        self.policy_net.eval()
        self.value_net.eval()
        with torch.no_grad():
            # done_mask는 향후 필요시 사용할 수 있도록 형태만 맞춰둠
            _ = self.value_net(obs) * done_mask

            dist = self.policy_net(obs)
            action = dist.sample()
            logprob = dist.log_prob(action).sum(1)
            value = self.value_net(obs)

        self.policy_net.train()
        self.value_net.train()
        return action, logprob, value

    def update(self, advantages, returns, b_obs, b_logprobs, b_actions):
        """ PPO 정책 및 가치 네트워크 업데이트 """
        cfg = self.cfg
        self.policy_net.train()
        self.value_net.train()

        b_inds = np.arange(cfg.batch_size)
        for _ in range(cfg.n_epochs):
            np.random.shuffle(b_inds)

            for start in range(0, cfg.batch_size, cfg.minibatch_size):
                end = start + cfg.minibatch_size
                mb_inds = b_inds[start:end]

                mb_obs = b_obs[mb_inds]
                mb_actions = b_actions[mb_inds]
                mb_logprobs = b_logprobs[mb_inds]
                mb_advantages = advantages[mb_inds]
                mb_returns = returns[mb_inds]

                # 새 확률 및 가치 계산
                dist = self.policy_net(mb_obs)
                new_logprob = dist.log_prob(mb_actions).sum(1)
                new_values = self.value_net(mb_obs).squeeze(-1)
                entropy = dist.entropy().sum(1)

                # Policy Loss (PPO-Clip)
                logratio = new_logprob - mb_logprobs
                ratio = torch.exp(logratio)

                clip_adv = torch.clamp(ratio, 1.0 - cfg.clip_coef, 1.0 + cfg.clip_coef) * mb_advantages
                policy_loss = -torch.min(ratio * mb_advantages, clip_adv).mean()

                # Value Loss (MSE)
                value_loss = 0.5 * ((new_values - mb_returns) ** 2).mean()

                # Entropy Loss
                entropy_loss = -entropy.mean()

                loss = policy_loss + cfg.vf_coef * value_loss + cfg.ent_coef * entropy_loss

                # 정책망 업데이트
                self.policy_optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy_net.parameters(), cfg.max_grad_norm)
                self.policy_optimizer.step()

                # 가치망 업데이트 (한 번 더 forward)
                new_values_v = self.value_net(mb_obs).squeeze(-1)
                value_loss_v = 0.5 * ((new_values_v - mb_returns) ** 2).mean()

                self.value_optimizer.zero_grad()
                (cfg.vf_coef * value_loss_v).backward()
                nn.utils.clip_grad_norm_(self.value_net.parameters(), cfg.max_grad_norm)
                self.value_optimizer.step()


def run_single_training(cfg):
    """ 한 개 Seeker 레벨에 대해 PPO 학습을 수행 """

    # 시드 설정
    random.seed(cfg.seed)
    np.random.seed(cfg.seed)
    torch.manual_seed(cfg.seed)
    torch.backends.cudnn.deterministic = True

    run_name = cfg.run_name
    tb_logdir = os.path.join("runs", run_name)
    os.makedirs(tb_logdir, exist_ok=True)

    # wandb + TensorBoard 연동
    if (wandb is not None) and (not cfg.disable_wandb):
        wandb.tensorboard.patch(root_logdir=tb_logdir, pytorch=True)
        wandb.init(
            project=cfg.wandb_project,
            name=run_name,
            config=vars(cfg),
            sync_tensorboard=True,
            monitor_gym=False,
            save_code=False,
        )
        print("[L{}] Wandb 로깅 활성화: {}/{}".format(cfg.seeker_level, cfg.wandb_project, run_name))
    else:
        print("[L{}] Wandb 로깅 비활성화.".format(cfg.seeker_level))

    writer = SummaryWriter(tb_logdir)
    hparam_lines = "\\n".join([f"|{key}|{value}|" for key, value in vars(cfg).items()])
    writer.add_text("hyperparameters", "|param|value|\\n|-|-|\\n" + hparam_lines)

    # 환경 및 에이전트 초기화
    env = NetworkEnv(cfg)
    agent = PPOAgent(cfg)

    print("[L{}] 디바이스: {}".format(cfg.seeker_level, cfg.device))
    print("[L{}] 총 업데이트 횟수: {}".format(cfg.seeker_level, cfg.updates))
    print("[L{}] 배치 크기: {}".format(cfg.seeker_level, cfg.batch_size))

    start_time = time.time()

    # 환경 초기화
    obs = torch.tensor(env.reset(), dtype=torch.float32, device=cfg.device).unsqueeze(0)
    done_mask = torch.ones((1, 1), dtype=torch.float32, device=cfg.device)

    # 에피소드 보상/길이 추적
    ep_rewards = []
    ep_lengths = []

    current_ep_reward = 0.0
    current_ep_length = 0

    # MTD 지표용 에피소드 누적 변수
    current_ep_total_attack_steps = 0
    current_ep_steps_on_decoy_while_attacked = 0
    current_ep_successful_attacks_N_A = 0
    current_ep_reconfigurations_N_R = 0
    current_ep_total_cost = 0.0

    # Episode/ 스텝용 인덱스
    global_episode = 0

    # Update/Metric 윈도우 누적 변수
    window_episodes = 0
    log_avg_S_MTD = 0.0
    log_avg_S_D = 0.0
    log_avg_R_A = 0.0
    log_avg_C_M = 0.0
    log_total_N_R = 0.0
    log_total_N_A = 0.0
    log_total_T_A = 0.0
    log_total_T_D = 0.0

    # ===================== 학습 루프 =====================
    for update in range(1, cfg.updates + 1):
        for step in range(cfg.batch_size):
            action, logprob, value = agent.get_action_and_value(obs, done_mask)

            action_np = action.squeeze(0).cpu().numpy()
            next_obs_np, reward, done, info = env.step(action_np)

            # 보상/길이 누적
            current_ep_reward += reward
            current_ep_length += 1

            # 버퍼 저장
            agent.obs[step] = obs.squeeze(0)
            agent.actions[step] = action.squeeze(0)
            agent.logprobs[step] = logprob.squeeze(0)
            agent.rewards[step] = torch.tensor(reward, dtype=torch.float32, device=cfg.device)
            agent.dones[step] = torch.tensor(float(done), dtype=torch.float32, device=cfg.device)
            agent.values[step] = value.squeeze()

            # --- MTD per-step 정보 추출 ---
            cost = 0.0
            is_attack = False
            is_decoy = False
            is_breach = False
            did_reconfig = False
            if info is not None:
                cost = float(info.get("cost", 0.0))
                is_attack = bool(info.get("is_attack_detected", info.get("is_attack", False)))
                is_decoy = bool(info.get("is_decoy_action", False))
                is_breach = bool(info.get("is_breach", False))
                did_reconfig = bool(info.get("did_reconfigure", info.get("is_reconfig", False)))

            current_ep_total_cost += cost
            if is_attack:
                current_ep_total_attack_steps += 1
            if is_attack and is_decoy:
                current_ep_steps_on_decoy_while_attacked += 1
            if is_breach:
                current_ep_successful_attacks_N_A += 1
            if did_reconfig:
                current_ep_reconfigurations_N_R += 1
            # ---------------------------------

            # 다음 상태
            obs = torch.tensor(next_obs_np, dtype=torch.float32, device=cfg.device).unsqueeze(0)

            if done:
                # ======== 에피소드 단위 MTD 지표 계산 =========
                T_A = current_ep_total_attack_steps
                T_D = current_ep_steps_on_decoy_while_attacked
                N_A = current_ep_successful_attacks_N_A
                N_R = current_ep_reconfigurations_N_R
                C_M = current_ep_total_cost / max(current_ep_length, 1)

                S_D = (T_D / T_A) if T_A > 0 else 0.0
                if N_A == 0:
                    R_A = min(float(N_R), R_MAX)
                else:
                    R_A = float(N_R) / float(max(N_A, 1))
                S_MTD = W_S_D * S_D + W_R_A * R_A - W_C_M * C_M
                # ============================================

                # Episode/ 단위 로깅
                global_episode += 1
                writer.add_scalar("Episode/MTD_Score_Overall", S_MTD, global_episode)
                writer.add_scalar("Episode/Deception_Success_S_D", S_D, global_episode)
                writer.add_scalar("Episode/Attack_Resilience_R_A", R_A, global_episode)
                writer.add_scalar("Episode/MTD_Cost_C_M", C_M, global_episode)
                writer.add_scalar("Episode/Detail_Reconfigurations_N_R", N_R, global_episode)
                writer.add_scalar("Episode/Detail_Successful_Attacks_N_A", N_A, global_episode)
                writer.add_scalar("Episode/Detail_Total_Attack_Steps_T_A", T_A, global_episode)
                writer.add_scalar("Episode/Detail_Total_Decoy_Steps_T_D", T_D, global_episode)

                # Update/Metric 윈도우 누적
                window_episodes += 1
                log_avg_S_MTD += S_MTD
                log_avg_S_D += S_D
                log_avg_R_A += R_A
                log_avg_C_M += C_M
                log_total_N_R += N_R
                log_total_N_A += N_A
                log_total_T_A += T_A
                log_total_T_D += T_D

                # 보상/길이 기록
                ep_rewards.append(current_ep_reward)
                ep_lengths.append(current_ep_length)

                # 선택적 EpisodeEnd 메트릭
                if info and (update % 10 == 0):
                    for key, val in info.items():
                        if "Metrics/" in key or "Params/" in key:
                            writer.add_scalar("EpisodeEnd/{}".format(key), val, update)

                # 에피소드 리셋
                obs = torch.tensor(env.reset(), dtype=torch.float32, device=cfg.device).unsqueeze(0)
                done_mask = torch.ones((1, 1), dtype=torch.float32, device=cfg.device)

                current_ep_reward = 0.0
                current_ep_length = 0
                current_ep_total_attack_steps = 0
                current_ep_steps_on_decoy_while_attacked = 0
                current_ep_successful_attacks_N_A = 0
                current_ep_reconfigurations_N_R = 0
                current_ep_total_cost = 0.0
            else:
                done_mask = torch.ones((1, 1), dtype=torch.float32, device=cfg.device)

        # ============== GAE & Returns 계산 ==============
        with torch.no_grad():
            next_value = agent.value_net(obs).squeeze(-1) * done_mask.squeeze()
            advantages = torch.zeros_like(agent.rewards, device=cfg.device)
            last_gae_lambda = 0.0

            for t in reversed(range(cfg.batch_size)):
                if t == cfg.batch_size - 1:
                    next_v = next_value
                else:
                    next_v = agent.values[t + 1]

                delta = (
                    agent.rewards[t]
                    + cfg.gamma * next_v * (1.0 - agent.dones[t])
                    - agent.values[t]
                )
                last_gae_lambda = (
                    delta
                    + cfg.gamma * cfg.gae_lambda * (1.0 - agent.dones[t]) * last_gae_lambda
                )
                advantages[t] = last_gae_lambda

            returns = advantages + agent.values
        # ==============================================

        # PPO 업데이트
        agent.update(advantages, returns, agent.obs, agent.logprobs, agent.actions)

        # ---------- Update/Metric 단위 집계 로그 ----------
        if update % 10 == 0:
            avg_reward = float(np.mean(ep_rewards[-50:])) if ep_rewards else 0.0
            avg_length = float(np.mean(ep_lengths[-50:])) if ep_lengths else 0.0
            sps = int(cfg.batch_size * update / (time.time() - start_time))

            if window_episodes > 0:
                avg_S_MTD = log_avg_S_MTD / window_episodes
                avg_S_D = log_avg_S_D / window_episodes
                avg_R_A = log_avg_R_A / window_episodes
                avg_C_M = log_avg_C_M / window_episodes
            else:
                avg_S_MTD = 0.0
                avg_S_D = 0.0
                avg_R_A = 0.0
                avg_C_M = 0.0

            print(
                "[L{}] Update {}/{}... Avg Reward: {:.2f} | S_MTD: {:.2f} (S_D={:.2f}, R_A={:.2f}, C_M={:.2f})".format(
                    cfg.seeker_level,
                    update,
                    cfg.updates,
                    avg_reward,
                    avg_S_MTD,
                    avg_S_D,
                    avg_R_A,
                    avg_C_M,
                )
            )

            writer.add_scalar("Rollout/mean_ep_reward", avg_reward, update)
            writer.add_scalar("Rollout/mean_ep_length", avg_length, update)
            writer.add_scalar("Debug/SPS", sps, update)

            writer.add_scalar("Metric/MTD_Score_Overall", avg_S_MTD, update)
            writer.add_scalar("Metric/Metric_Deception_Success (S_D)", avg_S_D, update)
            writer.add_scalar("Metric/Metric_Attack_Resilience (R_A)", avg_R_A, update)
            writer.add_scalar("Metric/Metric_MTD_Cost (C_M)", avg_C_M, update)
            writer.add_scalar("Metric/Detail_Reconfigurations (N_R)", log_total_N_R, update)
            writer.add_scalar("Metric/Detail_Successful_Attacks (N_A)", log_total_N_A, update)
            writer.add_scalar("Metric/Detail_Total_Attack_Steps (T_A)", log_total_T_A, update)
            writer.add_scalar("Metric/Detail_Total_Decoy_Steps (T_D)", log_total_T_D, update)

            # 윈도우 리셋
            window_episodes = 0
            log_avg_S_MTD = 0.0
            log_avg_S_D = 0.0
            log_avg_R_A = 0.0
            log_avg_C_M = 0.0
            log_total_N_R = 0.0
            log_total_N_A = 0.0
            log_total_T_A = 0.0
            log_total_T_D = 0.0
        # --------------------------------------------------

    # ================= 학습 종료 처리 =================
    print("[L{}] 학습 완료.".format(cfg.seeker_level))
    try:
        env.close()
    except AttributeError:
        pass
    writer.close()

    # export_dir 정리 (멀티 레벨이면 Lx 서브디렉토리)
    export_dir = cfg.export_dir
    if getattr(cfg, "train_all_seeker_levels", False):
        export_dir = os.path.join(cfg.export_dir, "L{}".format(cfg.seeker_level))

    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        print("[L{}] 학습된 정책을 '{}'에 저장합니다...".format(cfg.seeker_level, export_dir))
        try:
            state_history = env.get_state_history()
            if len(state_history) == 0:
                print("[경고] state_history가 비어있습니다. 정규화 없이 저장합니다.")
                state_history = np.zeros((10, OBS_DIM), dtype=np.float32)

            export_mtd_policy(
                policy_net=agent.policy_net,
                state_history=state_history,
                save_dir=export_dir,
            )
        except Exception as e:
            print("[L{}] 오류: 모델 내보내기 실패.".format(cfg.seeker_level))
            print(e)
            backup_path = os.path.join(export_dir, "mtd_policy_backup.pth")
            torch.save(agent.policy_net.state_dict(), backup_path)
            print("[L{}] 백업 가중치 저장: {}".format(cfg.seeker_level, backup_path))

    if (wandb is not None) and (not cfg.disable_wandb):
        wandb.finish()
    # ==================================================


def main():
    """
    진입점:
    - 기본: 단일 seeker-level 학습
    - --train-all-seeker-levels: L0~L4 순차 학습 (각 레벨별로 별도 run / export 디렉토리)
    """
    cfg = parse_args()
    base_run_name = cfg.run_name
    base_export_dir = cfg.export_dir
    base_seed = cfg.seed

    if getattr(cfg, "train_all_seeker-levels", False):
        # 오타 방지용: argparse dest는 train_all_seeker_levels 이므로 위 줄은 사용되지 않음
        pass

    if getattr(cfg, "train_all_seeker_levels", False):
        for lvl in [0, 1, 2, 3, 4]:
            print("=" * 70)
            print("[GLOBAL] Seeker Level {} 학습 시작".format(lvl))
            print("=" * 70)

            cfg.seeker_level = lvl
            cfg.run_name = "{}_L{}".format(base_run_name, lvl)
            cfg.export_dir = base_export_dir
            cfg.seed = base_seed + lvl

            run_single_training(cfg)
    else:
        run_single_training(cfg)


if __name__ == "__main__":
    main()
