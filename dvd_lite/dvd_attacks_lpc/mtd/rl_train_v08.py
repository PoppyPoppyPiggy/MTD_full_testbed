#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Training Script v08 - Complete Training Pipeline

핵심 개선사항:
1. Actor-Critic 역할 명확화
   - Actor: MTD 전략 결정 (언제, 어떤 강도로 셔플/디코이/블랙리스트)
   - Critic: 현재 상태의 가치 추정 (방어 성공 가능성)
2. Curriculum Learning: 점진적 난이도 증가
3. 상세 로깅 및 체크포인트
4. 학습 안정성 개선

저자: MTD-RL Research Team
버전: 0.8.0
"""
from __future__ import annotations

import argparse
import datetime
import json
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

from rl_config_v08 import (
    ACTION_DIM,
    ACTION_PARAM_KEYS,
    SEEKER_PROFILES,
    FEATURE_KEYS,
    STATE_DIM,
    EpisodeStats,
    MTDConfig,
    PPOConfig,
)
from rl_environment_v08 import MTDEnvironment

def to_serializable(obj):
    # numpy float → Python float
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    # numpy int → Python int
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    # numpy 배열 → list
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    # torch 텐서 → list
    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu().tolist()
    # 그 외는 문자열로라도 떨어지게
    return str(obj)
# =============================================================================
# Actor-Critic Network
# =============================================================================
class ActorCritic(nn.Module):
    """
    Actor-Critic 네트워크
    
    Actor의 역할:
    - 입력: 현재 상태 (공격 상황, 방어 상태, 시간 컨텍스트)
    - 출력: MTD 액션 분포 (셔플 강도, 디코이 비율, 블랙리스트 공격성 등)
    - 목표: 장기 보상을 최대화하는 방어 전략 학습
    
    Critic의 역할:
    - 입력: 현재 상태
    - 출력: 상태 가치 V(s) 추정
    - 목표: 현재 상태에서 기대되는 미래 보상 예측
    - 용도: Actor 업데이트를 위한 베이스라인 (분산 감소)
    """
    
    def __init__(
        self, 
        state_dim: int, 
        action_dim: int, 
        hidden_size: int = 256,
        num_layers: int = 2,
    ):
        super().__init__()
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # === Shared Feature Extractor ===
        # 상태에서 공통 특징 추출 (Actor와 Critic이 공유)
        layers = []
        input_dim = state_dim
        for i in range(num_layers):
            layers.extend([
                nn.Linear(input_dim, hidden_size),
                nn.LayerNorm(hidden_size),
                nn.ReLU(),
            ])
            input_dim = hidden_size
        self.shared = nn.Sequential(*layers)
        
        # === Actor Head ===
        # MTD 액션 결정 (연속 액션 공간)
        self.actor = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, action_dim),
            nn.Tanh(),  # 출력을 [-1, 1]로 제한
        )
        
        # 액션 분산 (학습 가능한 파라미터)
        # 초기값 -0.5 → std ≈ 0.6 (적절한 탐색)
        self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)
        
        # === Critic Head ===
        # 상태 가치 추정
        self.critic = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
        )
        
        # 가중치 초기화
        self._init_weights()
    
    def _init_weights(self):
        """Orthogonal 초기화 (PPO 권장)"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
                nn.init.zeros_(m.bias)
        
        # Actor 출력층은 작은 값으로 초기화 (초기 행동 안정화)
        nn.init.orthogonal_(self.actor[-2].weight, gain=0.01)
    
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        순전파
        
        Args:
            state: 상태 텐서 [batch, state_dim]
        
        Returns:
            action_mean: 액션 평균 [batch, action_dim]
            value: 상태 가치 [batch, 1]
        """
        features = self.shared(state)
        action_mean = self.actor(features)
        value = self.critic(features)
        return action_mean, value
    
    def act(
        self, 
        state: torch.Tensor, 
        deterministic: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        액션 샘플링
        
        Args:
            state: 상태 텐서
            deterministic: True면 평균값 반환, False면 분포에서 샘플링
        
        Returns:
            action: 선택된 액션
            log_prob: 액션의 로그 확률
            value: 상태 가치
        """
        action_mean, value = self.forward(state)
        
        if deterministic:
            return action_mean, torch.zeros(1), value
        
        # 액션 분포 생성
        std = torch.exp(self.log_std)
        dist = Normal(action_mean, std)
        
        # 샘플링 및 클리핑
        action = dist.sample()
        action = torch.clamp(action, -1, 1)
        
        # 로그 확률 계산
        log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)
        
        return action, log_prob, value
    
    def evaluate(
        self, 
        states: torch.Tensor, 
        actions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        액션 평가 (PPO 업데이트용)
        
        Args:
            states: 상태 배치 [batch, state_dim]
            actions: 액션 배치 [batch, action_dim]
        
        Returns:
            log_probs: 액션 로그 확률 [batch, 1]
            values: 상태 가치 [batch, 1]
            entropy: 엔트로피 [batch, 1]
        """
        action_mean, values = self.forward(states)
        
        std = torch.exp(self.log_std)
        dist = Normal(action_mean, std)
        
        log_probs = dist.log_prob(actions).sum(dim=-1, keepdim=True)
        entropy = dist.entropy().sum(dim=-1, keepdim=True)
        
        return log_probs, values, entropy
    
    def get_action_distribution(self, state: torch.Tensor) -> Normal:
        """액션 분포 반환 (분석용)"""
        action_mean, _ = self.forward(state)
        std = torch.exp(self.log_std)
        return Normal(action_mean, std)


# =============================================================================
# Rollout Buffer
# =============================================================================
class RolloutBuffer:
    """
    경험 저장 버퍼
    
    PPO는 on-policy 알고리즘이므로 매 업데이트 후 버퍼를 비움
    """
    
    def __init__(self):
        self.clear()
    
    def add(
        self, 
        state: np.ndarray, 
        action: np.ndarray, 
        reward: float,
        value: float, 
        log_prob: float, 
        done: bool
    ):
        """경험 추가"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)
    
    def clear(self):
        """버퍼 초기화"""
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []
    
    def compute_gae(
        self, 
        last_value: float, 
        gamma: float, 
        gae_lambda: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generalized Advantage Estimation (GAE) 계산
        
        GAE는 bias-variance tradeoff를 조절:
        - lambda=0: TD(0), 높은 bias, 낮은 variance
        - lambda=1: Monte Carlo, 낮은 bias, 높은 variance
        - 일반적으로 lambda=0.95 사용
        
        Args:
            last_value: 마지막 상태의 가치 추정
            gamma: 할인율
            gae_lambda: GAE 파라미터
        
        Returns:
            returns: 리턴 값
            advantages: 어드밴티지 값
        """
        rewards = np.array(self.rewards)
        values = np.array(self.values + [last_value])
        dones = np.array(self.dones)
        
        advantages = np.zeros_like(rewards)
        gae = 0.0
        
        # 역순으로 계산
        for t in reversed(range(len(rewards))):
            mask = 1.0 - dones[t]
            delta = rewards[t] + gamma * values[t + 1] * mask - values[t]
            gae = delta + gamma * gae_lambda * mask * gae
            advantages[t] = gae
        
        returns = advantages + values[:-1]
        
        # 어드밴티지 정규화 (학습 안정성)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        return returns, advantages
    
    def iter_batches(
        self, 
        batch_size: int, 
        returns: np.ndarray, 
        advantages: np.ndarray
    ):
        """미니배치 이터레이터"""
        n = len(self.states)
        indices = np.random.permutation(n)
        
        for start in range(0, n, batch_size):
            batch_idx = indices[start:start + batch_size]
            
            yield (
                torch.FloatTensor(np.array(self.states)[batch_idx]),
                torch.FloatTensor(np.array(self.actions)[batch_idx]),
                torch.FloatTensor(np.array(self.log_probs)[batch_idx]).unsqueeze(1),
                torch.FloatTensor(returns[batch_idx]).unsqueeze(1),
                torch.FloatTensor(advantages[batch_idx]).unsqueeze(1),
            )
    
    def __len__(self):
        return len(self.states)


# =============================================================================
# PPO Agent
# =============================================================================
class PPOAgent:
    """
    PPO 에이전트
    
    핵심 알고리즘:
    1. 현재 정책으로 경험 수집
    2. GAE로 어드밴티지 계산
    3. Clipped objective로 정책 업데이트
    4. 가치 함수 업데이트
    """
    
    def __init__(
        self, 
        config: PPOConfig, 
        device: str = "cpu",
        hidden_size: int = 256,
    ):
        self.cfg = config
        self.device = device
        
        # 네트워크 초기화
        self.policy = ActorCritic(
            state_dim=STATE_DIM,
            action_dim=ACTION_DIM,
            hidden_size=hidden_size,
        ).to(device)
        
        # 옵티마이저
        self.optimizer = optim.Adam(
            self.policy.parameters(), 
            lr=config.learning_rate,
            eps=1e-5
        )
        
        # 엔트로피 계수 (탐색 조절)
        self.entropy_coef = config.entropy_coef_start
        
        # 학습 통계
        self.update_count = 0
    
    def select_action(
        self, 
        state: np.ndarray, 
        deterministic: bool = False
    ) -> Tuple[np.ndarray, float, float]:
        """
        액션 선택
        
        Args:
            state: 현재 상태
            deterministic: 결정론적 선택 여부
        
        Returns:
            action: 선택된 액션
            log_prob: 로그 확률
            value: 상태 가치
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            action, log_prob, value = self.policy.act(state_tensor, deterministic)
        
        return (
            action.cpu().numpy().squeeze(),
            log_prob.item(),
            value.item()
        )
    
    def update(
        self, 
        buffer: RolloutBuffer, 
        last_value: float
    ) -> Dict[str, float]:
        """
        PPO 업데이트
        
        Args:
            buffer: 경험 버퍼
            last_value: 마지막 상태의 가치
        
        Returns:
            손실 정보 딕셔너리
        """
        # GAE 계산
        returns, advantages = buffer.compute_gae(
            last_value, 
            self.cfg.gamma, 
            self.cfg.gae_lambda
        )
        
        # 손실 누적
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        n_updates = 0
        
        # 여러 에폭에 걸쳐 업데이트
        for _ in range(self.cfg.update_epochs):
            for (states, actions, old_log_probs, 
                 batch_returns, batch_advs) in buffer.iter_batches(
                     self.cfg.batch_size, returns, advantages
                 ):
                
                # GPU로 이동
                states = states.to(self.device)
                actions = actions.to(self.device)
                old_log_probs = old_log_probs.to(self.device)
                batch_returns = batch_returns.to(self.device)
                batch_advs = batch_advs.to(self.device)
                
                # 현재 정책으로 평가
                log_probs, values, entropy = self.policy.evaluate(states, actions)
                
                # === Policy Loss (Clipped Surrogate) ===
                ratio = torch.exp(log_probs - old_log_probs)
                surr1 = ratio * batch_advs
                surr2 = torch.clamp(
                    ratio, 
                    1 - self.cfg.clip_epsilon, 
                    1 + self.cfg.clip_epsilon
                ) * batch_advs
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # === Value Loss ===
                value_loss = nn.functional.mse_loss(values, batch_returns)
                
                # === Entropy Loss (탐색 촉진) ===
                entropy_loss = -entropy.mean()
                
                # === Total Loss ===
                loss = (
                    policy_loss 
                    + self.cfg.value_loss_coef * value_loss 
                    + self.entropy_coef * entropy_loss
                )
                
                # 역전파
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(
                    self.policy.parameters(), 
                    self.cfg.max_grad_norm
                )
                self.optimizer.step()
                
                # 통계 누적
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += -entropy_loss.item()
                n_updates += 1
        
        self.update_count += 1
        
        return {
            "policy_loss": total_policy_loss / n_updates,
            "value_loss": total_value_loss / n_updates,
            "entropy": total_entropy / n_updates,
            "update_count": self.update_count,
        }
    
    def update_entropy_coef(self, episode: int, total_episodes: int):
        """엔트로피 계수 스케줄링"""
        progress = min(1.0, episode / self.cfg.entropy_decay_episodes)
        self.entropy_coef = (
            self.cfg.entropy_coef_start + 
            (self.cfg.entropy_coef_final - self.cfg.entropy_coef_start) * progress
        )
    
    def save(self, path: str):
        """모델 저장"""
        torch.save({
            "policy": self.policy.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "entropy_coef": self.entropy_coef,
            "update_count": self.update_count,
        }, path)
        print(f"✅ Model saved: {path}")
    
    def load(self, path: str):
        """모델 로드"""
        checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        self.policy.load_state_dict(checkpoint["policy"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.entropy_coef = checkpoint.get("entropy_coef", self.cfg.entropy_coef_start)
        self.update_count = checkpoint.get("update_count", 0)
        print(f"✅ Model loaded: {path}")
    
    def export_policy(self, path: str):
        """배포용 정책 저장 (정책 네트워크만)"""
        torch.save(self.policy.state_dict(), path)
        print(f"✅ Policy exported: {path}")


# =============================================================================
# Training Function
# =============================================================================
def train(args):
    """메인 학습 함수"""
    
    # 디바이스 설정
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    print(f"🖥️ Device: {device}")
    
    # 설정 로드
    cfg = MTDConfig()
    cfg.ppo.total_episodes = args.episodes
    cfg.ppo.max_steps = args.max_steps
    
    # 체크포인트 디렉토리
    ckpt_dir = Path(args.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    
    # WandB 초기화
    if args.wandb:
        import wandb
        run_name = args.wandb_name or f"mtd-v08-{datetime.datetime.now():%m%d-%H%M}"
        wandb.init(
            project=args.wandb_project, 
            name=run_name, 
            config=vars(args)
        )
    
    # 에이전트 초기화
    agent = PPOAgent(cfg.ppo, device, hidden_size=args.hidden_size)
    
    if args.resume:
        agent.load(args.resume)
    
    # Curriculum 설정
    if args.curriculum:
        phases = cfg.curriculum.phases
        phase_episodes = cfg.curriculum.phase_episodes
        entropy_schedule = cfg.curriculum.entropy_schedule
    else:
        # 단일 레벨 또는 전체 레벨
        levels = args.seeker_levels if args.train_all_levels else [args.seeker_level]
        phases = [tuple(levels)] * 5
        phase_episodes = [args.episodes // 5] * 5
        entropy_schedule = [0.02, 0.015, 0.01, 0.005, 0.002]
    
    # 학습 통계
    rewards_history = deque(maxlen=100)
    best_reward = float("-inf")
    all_metrics: List[Dict] = []
    start_time = time.time()
    global_episode = 0
    
    # 학습 정보 출력
    print(f"\n{'='*70}")
    print("MTD RL Training v08")
    print(f"{'='*70}")
    print(f"Search Space: {cfg.search_space.total_search_space:,}")
    print(f"State Dim: {STATE_DIM}, Action Dim: {ACTION_DIM}")
    print(f"Total Episodes: {args.episodes}")
    print(f"Curriculum: {args.curriculum}")
    print(f"{'='*70}\n")
    
    # === 메인 학습 루프 ===
    for phase_idx, (phase_levels, n_episodes, ent_coef) in enumerate(
        zip(phases, phase_episodes, entropy_schedule)
    ):
        print(f"\n{'='*50}")
        print(f"Phase {phase_idx}: Levels {phase_levels}")
        print(f"Episodes: {n_episodes}, Entropy: {ent_coef}")
        print(f"{'='*50}")
        
        # 엔트로피 계수 설정
        agent.entropy_coef = ent_coef
        
        # 보상 프로파일 (초반: 탐색, 후반: 활용)
        reward_profile = "explore" if phase_idx < 2 else "exploit"
        
        for ep_in_phase in range(n_episodes):
            global_episode += 1
            
            # 레벨 선택
            level = int(np.random.choice(phase_levels))
            
            # 환경 생성
            env = MTDEnvironment(
                seed=args.seed + global_episode,
                seeker_level=level,
                config=cfg,
            )
            env.set_reward_profile(reward_profile)
            
            # 버퍼 초기화
            buffer = RolloutBuffer()
            
            # 에피소드 실행
            state, info = env.reset()
            episode_reward = 0.0
            episode_actions = []
            
            for step in range(args.max_steps):
                # 액션 선택
                action, log_prob, value = agent.select_action(state)
                
                # 환경 스텝
                next_state, reward, terminated, truncated, info = env.step(action)
                
                # 버퍼에 저장
                buffer.add(state, action, reward, value, log_prob, terminated or truncated)
                
                # 통계 업데이트
                episode_reward += reward
                episode_actions.append((action + 1) / 2)  # [0, 1]로 스케일
                
                state = next_state
                
                if terminated or truncated:
                    break
            
            # PPO 업데이트
            _, _, last_value = agent.select_action(state)
            losses = agent.update(buffer, last_value)
            
            # 엔트로피 스케줄링
            agent.update_entropy_coef(global_episode, args.episodes)
            
            # 통계 저장
            rewards_history.append(episode_reward)
            avg_reward = np.mean(rewards_history)
            
            # 액션 통계
            episode_actions = np.array(episode_actions)
            action_means = (
                episode_actions.mean(axis=0) 
                if len(episode_actions) > 0 
                else np.zeros(ACTION_DIM)
            )
            
            # 메트릭 수집
            episode_metrics = {
                "episode": global_episode,
                "phase": phase_idx,
                "seeker_level": level,
                "reward": episode_reward,
                "avg_reward": avg_reward,
                "steps": step + 1,
                **info,
                **losses,
                "entropy_coef": agent.entropy_coef,
            }
            
            # 액션별 평균 추가
            for i, key in enumerate(ACTION_PARAM_KEYS):
                episode_metrics[f"Action/{key}"] = float(action_means[i])
            
            all_metrics.append(episode_metrics)
            
            # 로깅
            if global_episode % args.log_interval == 0:
                elapsed = time.time() - start_time
                s_mtd = info.get("Defense/S_MTD", 0)
                svc_found = info.get("Attack/ServicesFound", 0)
                breach_prevented = info.get("Defense/BreachPrevented", 1)
                
                print(
                    f"Ep {global_episode:4d} | "
                    f"P{phase_idx} L{level} | "
                    f"R: {episode_reward:7.1f} | "
                    f"Avg: {avg_reward:7.1f} | "
                    f"S_MTD: {s_mtd:.3f} | "
                    f"Found: {svc_found:.0f} | "
                    f"Survive: {breach_prevented:.0f} | "
                    f"{elapsed/60:.1f}m"
                )
            
            # WandB 로깅
            if args.wandb:
                import wandb
                wandb.log(episode_metrics)
            
            # 체크포인트 저장
            if global_episode % args.save_interval == 0:
                agent.save(str(ckpt_dir / f"model_ep{global_episode}.pt"))
            
            # Best 모델 저장
            if avg_reward > best_reward:
                best_reward = avg_reward
                agent.save(str(ckpt_dir / "best.pt"))
    
    # === 최종 저장 ===
    agent.save(str(ckpt_dir / "final.pt"))
    agent.export_policy(str(ckpt_dir / "policy_deploy.pt"))
    
    # 학습 설정 저장
    training_config = {
        "args": vars(args),
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "feature_keys": FEATURE_KEYS,
        "action_keys": ACTION_PARAM_KEYS,
        "search_space": cfg.search_space.total_search_space,
        "best_reward": best_reward,
        "total_episodes": global_episode,
    }
    
    with open(ckpt_dir / "training_config.json", "w") as f:
        json.dump(training_config, f, indent=2,default=to_serializable)
    
    # 메트릭 저장
    def convert_to_serializable(obj):
        if isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_serializable(i) for i in obj]
        return obj
    
    with open(ckpt_dir / "training_metrics.json", "w") as f:
        json.dump(convert_to_serializable(all_metrics), f)
    
    print(f"\n{'='*70}")
    print("✅ Training Complete!")
    print(f"Best avg reward: {best_reward:.1f}")
    print(f"Checkpoints saved to: {ckpt_dir}")
    print(f"{'='*70}\n")
    
    if args.wandb:
        import wandb
        wandb.finish()
    
    return best_reward


# =============================================================================
# Evaluation Function
# =============================================================================
def evaluate(args):
    """모델 평가"""
    
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    cfg = MTDConfig()
    
    # 에이전트 로드
    agent = PPOAgent(cfg.ppo, device)
    if args.model:
        agent.load(args.model)
    
    # 평가할 레벨
    test_levels = args.seeker_levels if args.eval_all_levels else [args.seeker_level]
    
    print(f"\n{'='*80}")
    print("MTD RL Evaluation - Robustness Matrix")
    print(f"{'='*80}")
    print(f"{'Level':<18} {'R_succ':>8} {'S_MTD':>8} {'Decoy':>8} "
          f"{'Found':>8} {'Cost':>8} {'Survival':>8}")
    print("-" * 80)
    
    results = {}
    
    for level in test_levels:
        metrics_list = []
        
        for ep in range(args.eval_episodes):
            env = MTDEnvironment(
                seed=args.seed + ep * 100 + level,
                seeker_level=level,
                config=cfg,
            )
            
            state, _ = env.reset()
            
            for _ in range(args.max_steps):
                action, _, _ = agent.select_action(state, deterministic=True)
                state, _, terminated, truncated, info = env.step(action)
                
                if terminated or truncated:
                    break
            
            metrics_list.append(info)
        
        # 집계
        agg = {
            k: np.mean([m.get(k, 0) for m in metrics_list])
            for k in metrics_list[0].keys()
        }
        results[level] = agg
        
        name = SEEKER_PROFILES[level]["name"]
        print(
            f"L{level} {name:<12} "
            f"{agg.get('Defense/Success', 0):>8.3f} "
            f"{agg.get('Defense/S_MTD', 0):>8.3f} "
            f"{agg.get('Decoy/Hits', 0):>8.1f} "
            f"{agg.get('Attack/ServicesFound', 0):>8.1f} "
            f"{agg.get('Cost/Total', 0):>8.2f} "
            f"{agg.get('Defense/BreachPrevented', 0):>8.1%}"
        )
    
    print(f"{'='*80}\n")
    
    # 결과 저장
    with open("eval_results.json", "w") as f:
        json.dump({str(k): v for k, v in results.items()}, f, indent=2, default=float)
    
    return results


# =============================================================================
# CLI
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(description="MTD RL Training v08")
    
    # 모드
    parser.add_argument("--test", action="store_true", help="평가 모드")
    
    # 학습 파라미터
    parser.add_argument("--episodes", type=int, default=500, help="총 에피소드 수")
    parser.add_argument("--max-steps", type=int, default=200, help="에피소드당 최대 스텝")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--cpu", action="store_true", help="CPU 강제 사용")
    parser.add_argument("--hidden-size", type=int, default=256, help="은닉층 크기")
    
    # 공격자 레벨
    parser.add_argument("--seeker-level", type=int, default=1, choices=[0, 1, 2, 3, 4])
    parser.add_argument("--seeker-levels", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--train-all-levels", action="store_true", dest="train_all_levels")
    
    # Curriculum
    parser.add_argument("--curriculum", action="store_true", help="Curriculum Learning 사용")
    
    # 모델 경로
    parser.add_argument("--model", type=str, help="평가할 모델 경로")
    parser.add_argument("--resume", type=str, help="이어서 학습할 모델 경로")
    
    # 체크포인트
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints_v08")
    parser.add_argument("--save-interval", type=int, default=100)
    parser.add_argument("--log-interval", type=int, default=10)
    
    # 평가
    parser.add_argument("--eval-episodes", type=int, default=50)
    parser.add_argument("--eval-all-levels", action="store_true")
    
    # WandB
    parser.add_argument("--wandb", action="store_true")
    parser.add_argument("--wandb-project", type=str, default="mtd-rl-v08")
    parser.add_argument("--wandb-name", type=str, dest="wandb_name")
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # 시드 설정
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    
    if args.test:
        evaluate(args)
    else:
        train(args)