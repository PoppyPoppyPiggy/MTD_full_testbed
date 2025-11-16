# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_train_v05.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 8/11] MTD-RL v05 PPO 학습 실행 스크립트 (Main)

- `rl_environment_v05`에서 시뮬레이션 환경을 가져옵니다.
- `rl_model_v05`에서 정책/가치 신경망을 정의합니다.
- `rl_config_v05`에서 상태/행동 공간 크기를 정의합니다.
- PPO 학습 루프를 실행하고 `wandb`에 로그를 기록합니다.
- 학습 완료 후 `rl_export_policy_v05`를 호출하여 모델을 저장합니다.

[옵션 B] TensorBoard 이벤트 파일 기반으로 wandb 연동
- wandb.tensorboard.patch(root_logdir=...) 를 SummaryWriter 생성 전에 호출
- wandb.init(..., sync_tensorboard=True) 도 SummaryWriter 보다 먼저 호출
"""

import os
import argparse
import time
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from torch.distributions.normal import Normal

# mtd 패키지 내의 모듈 임포트
from .rl_environment_v05 import NetworkEnv
from .rl_model_v05 import MTDPolicyNet, MTDValueNet
from .rl_config_v05 import OBS_DIM, ACTION_DIM
from .rl_export_policy_v05 import export_mtd_policy

# Wandb (Weights & Biases) 로거 임포트 시도
try:
    import wandb
except ImportError:
    wandb = None
    print("Warning: 'wandb' a-py (pip install wandb)가 설치되지 않았습니다. --disable-wandb 플래그가 강제 활성화됩니다.")


def parse_args():
    """ 스크립트 실행 인자 파싱 """
    parser = argparse.ArgumentParser(description="MTD-RL v05 PPO 학습 스크립트")
    
    # PPO 하이퍼파라미터
    parser.add_argument("--lr", type=float, default=3e-4, help="학습률 (기본값: 3e-4)")
    parser.add_argument("--gamma", type=float, default=0.99, help="할인 계수 (기본값: 0.99)")
    parser.add_argument("--gae-lambda", type=float, default=0.95, help="GAE 람다 (기본값: 0.95)")
    parser.add_argument("--clip-coef", type=float, default=0.2, help="PPO 클리핑 계수 (기본값: 0.2)")
    parser.add_argument("--ent-coef", type=float, default=0.01, help="엔트로피 계수 (기본값: 0.01)")
    parser.add_argument("--vf-coef", type=float, default=0.5, help="가치 함수 계수 (기본값: 0.5)")
    parser.add_argument("--max-grad-norm", type=float, default=0.5, help="그라디언트 클리핑 최대치 (기본값: 0.5)")
    
    # 학습 실행 설정
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드 (기본값: 42)")
    parser.add_argument("--updates", type=int, default=1500, help="총 학습 업데이트 횟수 (기본값: 1500)")
    parser.add_argument("--batch-size", type=int, default=2048, help="배치 크기 (롤아웃 버퍼 크기) (기본값: 2048)")
    parser.add_argument("--minibatch-size", type=int, default=64, help="미니배치 크기 (기본값: 64)")
    parser.add_argument("--n-epochs", type=int, default=10, help="한 배치의 업데이트 에포크 수 (기본값: 10)")
    parser.add_argument("--max-episode-steps", type=int, default=500, help="시뮬레이션 환경의 최대 스텝 (기본값: 500)")
    
    # 환경(Seeker) 설정
    parser.add_argument("--seeker-level", type=int, default=2, choices=[0, 1, 2, 3, 4], help="Seeker 난이도 (0~4) (기본값: 2)")
    
    # 로깅 및 저장 설정
    parser.add_argument("--wandb-project", type=str, default="MTD_RL_v05_Passive_CTI", help="Wandb 프로젝트 이름")
    parser.add_argument("--run-name", type=str, default=f"PPO_v05_vs_Seeker_L2_{int(time.time())}", help="Wandb 실행 이름")
    parser.add_argument("--disable-wandb", action="store_true", help="Wandb 로깅 비활성화")
    parser.add_argument("--export-dir", type=str, default="./mtd/rl_models/ver_05_L2", help="학습 완료 후 모델 저장 경로")

    args = parser.parse_args()
    args.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if wandb is None:
        # wandb 모듈이 없으면 강제 비활성화
        args.disable_wandb = True
        
    return args


class PPOAgent:
    """ PPO 에이전트 (신경망, 옵티마이저, 버퍼 포함) """
    def __init__(self, cfg):
        self.cfg = cfg
        self.obs_dim = OBS_DIM
        self.act_dim = ACTION_DIM
        
        # Actor/Critic 네트워크
        self.policy_net = MTDPolicyNet(self.obs_dim, self.act_dim).to(cfg.device)
        self.value_net = MTDValueNet(self.obs_dim).to(cfg.device)
        
        # 옵티마이저
        self.policy_optimizer = optim.Adam(self.policy_net.parameters(), lr=cfg.lr, eps=1e-5)
        self.value_optimizer = optim.Adam(self.value_net.parameters(), lr=cfg.lr, eps=1e-5)

        # 롤아웃 버퍼 초기화
        self.obs = torch.zeros((cfg.batch_size, self.obs_dim)).to(cfg.device)
        self.actions = torch.zeros((cfg.batch_size, self.act_dim)).to(cfg.device)
        self.logprobs = torch.zeros((cfg.batch_size,)).to(cfg.device)
        self.rewards = torch.zeros((cfg.batch_size,)).to(cfg.device)
        self.dones = torch.zeros((cfg.batch_size,)).to(cfg.device)
        self.values = torch.zeros((cfg.batch_size,)).to(cfg.device)

    def get_action_and_value(self, obs, done_mask):
        """ 현재 관찰(obs)로 행동, 로그확률, 가치(value) 계산 """
        self.policy_net.eval()
        self.value_net.eval()
        with torch.no_grad():
            # 이전 에피소드 종료 시 가치(value)를 0으로 마스킹 (GAE 계산 시 중요)
            last_values = self.value_net(obs) * done_mask
            
            # 행동 결정 (Stochastic)
            dist = self.policy_net(obs)
            action = dist.sample()
            logprob = dist.log_prob(action).sum(1)  # 다변수 -> 로그 확률 합
            
        self.policy_net.train()
        self.value_net.train()
        return action, logprob, last_values

    def update(self, advantages, returns, b_obs, b_logprobs, b_actions):
        """ PPO 정책 및 가치 네트워크 업데이트 """
        
        self.policy_net.train()
        self.value_net.train()
        
        b_inds = np.arange(self.cfg.batch_size)
        
        for epoch in range(self.cfg.n_epochs):
            np.random.shuffle(b_inds)  # 미니배치 셔플
            
            for start in range(0, self.cfg.batch_size, self.cfg.minibatch_size):
                end = start + self.cfg.minibatch_size
                mb_inds = b_inds[start:end]

                # 미니배치 데이터
                mb_obs = b_obs[mb_inds]
                mb_actions = b_actions[mb_inds]
                mb_logprobs = b_logprobs[mb_inds]
                mb_advantages = advantages[mb_inds]
                mb_returns = returns[mb_inds]

                # 새 확률 및 가치 계산
                dist = self.policy_net(mb_obs)
                new_logprob = dist.log_prob(mb_actions).sum(1)
                new_values = self.value_net(mb_obs).squeeze()
                entropy = dist.entropy().sum(1)

                # Policy Loss (PPO-Clip)
                logratio = new_logprob - mb_logprobs
                ratio = logratio.exp()

                clip_adv = torch.clamp(
                    ratio,
                    1 - self.cfg.clip_coef,
                    1 + self.cfg.clip_coef
                ) * mb_advantages
                policy_loss = -torch.min(ratio * mb_advantages, clip_adv).mean()

                # Value Loss (MSE)
                value_loss = 0.5 * ((new_values - mb_returns) ** 2).mean()

                # Entropy Loss (Regularization)
                entropy_loss = -entropy.mean()

                # 총 손실
                loss = policy_loss + self.cfg.vf_coef * value_loss + self.cfg.ent_coef * entropy_loss

                # 정책망 업데이트
                self.policy_optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy_net.parameters(), self.cfg.max_grad_norm)
                self.policy_optimizer.step()

                # 가치망 업데이트 (손실 재계산)
                new_values_v = self.value_net(mb_obs).squeeze()
                value_loss_v = 0.5 * ((new_values_v - mb_returns) ** 2).mean()
                
                self.value_optimizer.zero_grad()
                (self.cfg.vf_coef * value_loss_v).backward()
                nn.utils.clip_grad_norm_(self.value_net.parameters(), self.cfg.max_grad_norm)
                self.value_optimizer.step()


def main():
    """ 메인 학습 루프 """
    cfg = parse_args()
    
    # 시드 설정
    random.seed(cfg.seed)
    np.random.seed(cfg.seed)
    torch.manual_seed(cfg.seed)
    torch.backends.cudnn.deterministic = True

    # run 이름 / TensorBoard 로그 디렉토리
    run_name = cfg.run_name
    tb_logdir = os.path.join("runs", run_name)
    os.makedirs(tb_logdir, exist_ok=True)

    # --- [중요] wandb + TensorBoard 연동 (SummaryWriter보다 먼저) ---
    if (wandb is not None) and (not cfg.disable_wandb):
        # TensorBoard 이벤트 파일 위치를 wandb에 명시적으로 알려줌
        wandb.tensorboard.patch(root_logdir=tb_logdir, pytorch=True)
        wandb.init(
            project=cfg.wandb_project,
            name=run_name,
            config=vars(cfg),
            sync_tensorboard=True,
            monitor_gym=False,  # Gym 환경 아님
            save_code=False,
        )
        print(f"Wandb 로깅 활성화: {cfg.wandb_project} / {run_name}")
    else:
        print("Wandb 로깅 비활성화.")
    # -------------------------------------------------------------

    # 이제 SummaryWriter 생성 (wandb.patch / init 이후)
    writer = SummaryWriter(tb_logdir)
    writer.add_text(
        "hyperparameters",
        "|param|value|\n|-|-|\n%s"
        % ("\n".join([f"|{key}|{value}|" for key, value in vars(cfg).items()])),
    )
    
    # 환경 및 에이전트 초기화
    env = NetworkEnv(cfg)
    agent = PPOAgent(cfg)
    
    print(f"디바이스: {cfg.device}")
    print(f"Seeker 레벨: {cfg.seeker_level}")
    print(f"총 업데이트 횟수: {cfg.updates}")
    print(f"배치 크기: {cfg.batch_size}")

    start_time = time.time()
    
    # 환경 초기화
    obs = torch.tensor(env.reset(), dtype=torch.float32).to(cfg.device).unsqueeze(0)  # (1, OBS_DIM)
    done_mask = torch.ones((1, 1)).to(cfg.device)  # (1, 1)
    
    # 에피소드 보상/길이 추적
    ep_rewards = []
    ep_lengths = []
    current_ep_reward = 0.0
    current_ep_length = 0

    # 학습 루프
    for update in range(1, cfg.updates + 1):
        
        # 롤아웃 수집 (배치 크기만큼)
        for step in range(cfg.batch_size):
            action, logprob, value = agent.get_action_and_value(obs, done_mask)
            
            # (1, act_dim) -> (act_dim,)
            action_np = action.squeeze(0).cpu().numpy()
            
            # 환경 스텝 실행
            next_obs_np, reward, done, info = env.step(action_np)
            
            # 현재 에피소드 보상/길이 누적
            current_ep_reward += reward
            current_ep_length += 1
            
            # 버퍼에 저장
            agent.obs[step] = obs.squeeze(0)
            agent.actions[step] = action.squeeze(0)
            agent.logprobs[step] = logprob.squeeze(0)
            agent.rewards[step] = torch.tensor(reward).to(cfg.device)
            agent.dones[step] = torch.tensor(done, dtype=torch.float32).to(cfg.device)
            agent.values[step] = value.squeeze()  # (1, 1) -> 스칼라

            # 다음 상태 준비
            obs = torch.tensor(next_obs_np, dtype=torch.float32).to(cfg.device).unsqueeze(0)
            
            # 에피소드 종료 처리
            if done:
                # 1) 에피소드 통계 저장
                ep_rewards.append(current_ep_reward)
                ep_lengths.append(current_ep_length)
                
                # 2) 에피소드 단위 환경 메트릭 로깅 (선택)
                if info and (update % 10 == 0):
                    for key, val in info.items():
                        if "Metrics/" in key or "Params/" in key:
                            writer.add_scalar(f"EpisodeEnd/{key}", val, update)

                # 3) 환경 리셋
                obs = torch.tensor(env.reset(), dtype=torch.float32).to(cfg.device).unsqueeze(0)
                done_mask = torch.ones((1, 1)).to(cfg.device)
                current_ep_reward = 0.0
                current_ep_length = 0
            else:
                done_mask = torch.ones((1, 1)).to(cfg.device)

        # GAE (Generalized Advantage Estimation) 계산
        with torch.no_grad():
            # 마지막 스텝의 가치(value) 계산
            next_value = agent.value_net(obs).squeeze() * done_mask.squeeze()
            
            advantages = torch.zeros_like(agent.rewards).to(cfg.device)
            last_gae_lambda = 0
            
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
            
            returns = advantages + agent.values  # Return = GAE + V(s)

        # PPO 업데이트
        agent.update(advantages, returns, agent.obs, agent.logprobs, agent.actions)

        # 로깅
        if update % 10 == 0:
            avg_reward = np.mean(ep_rewards[-50:]) if ep_rewards else 0.0
            avg_length = np.mean(ep_lengths[-50:]) if ep_lengths else 0.0
            
            sps = int(cfg.batch_size * update / (time.time() - start_time))
            print(f"Update {update}/{cfg.updates}... Avg Reward: {avg_reward:.2f}")

            # TensorBoard 로깅
            writer.add_scalar("Rollout/mean_ep_reward", avg_reward, update)
            writer.add_scalar("Rollout/mean_ep_length", avg_length, update)
            writer.add_scalar("Debug/SPS", sps, update)

    # --- 학습 종료 ---
    print("\n학습 완료.")
    try:
        env.close()
    except AttributeError:
        pass
    writer.close()
    
    # 모델 저장
    if cfg.export_dir:
        print(f"학습된 정책을 '{cfg.export_dir}'에 저장합니다...")
        try:
            state_history = env.get_state_history()
            if len(state_history) == 0:
                print("Warning: state_history가 비어있습니다. 정규화 없이 저장합니다.")
                state_history = np.zeros((10, OBS_DIM), dtype=np.float32)
                
            export_mtd_policy(
                policy_net=agent.policy_net,
                state_history=state_history,
                save_dir=cfg.export_dir,
            )
        except Exception as e:
            print(f"오류: 모델 내보내기 실패. \n{e}")
            print("가중치만 별도 저장 시도: 'mtd_policy_backup.pth'")
            torch.save(agent.policy_net.state_dict(), "mtd_policy_backup.pth")


if __name__ == "__main__":
    main()
