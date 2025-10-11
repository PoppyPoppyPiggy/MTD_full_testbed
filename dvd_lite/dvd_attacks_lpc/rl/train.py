# train.py
import torch
import numpy as np
from collections import deque
import config
from environment import MTDEnvironment
from ppo_agent import PPOAgent

def train():
    """
    MTD 에이전트와 Seeker 에이전트를 동시에 훈련시키는 메인 루프.
    """
    print(f"훈련 장치: {config.DEVICE}")

    env = MTDEnvironment()
    # [수정] 환경 객체로부터 정확한 상태 차원을 가져옴
    state_dim = env.state_dim 

    # 두 명의 독립적인 PPO 에이전트 생성
    mtd_agent = PPOAgent(state_dim, env.mtd_action_space_n)
    seeker_agent = PPOAgent(state_dim, env.seeker_action_space_n)

    time_step = 0
    mtd_rewards_log = deque(maxlen=100)
    seeker_rewards_log = deque(maxlen=100)

    for i_episode in range(1, config.TOTAL_EPISODES + 1):
        state = env.reset()
        current_mtd_reward = 0
        current_seeker_reward = 0

        for t in range(config.MAX_STEPS_PER_EPISODE):
            time_step += 1

            mtd_action = mtd_agent.select_action(state)
            seeker_action = seeker_agent.select_action(state)

            state, mtd_reward, seeker_reward, done = env.step(mtd_action, seeker_action)

            mtd_agent.buffer.rewards.append(mtd_reward)
            mtd_agent.buffer.is_terminals.append(done)
            
            seeker_agent.buffer.rewards.append(seeker_reward)
            seeker_agent.buffer.is_terminals.append(done)

            current_mtd_reward += mtd_reward
            current_seeker_reward += seeker_reward

            if time_step % config.UPDATE_TIMESTEP == 0:
                print(f"--- 타임스텝 {time_step}에서 정책 업데이트 ---") # [개선] 로그 추가
                mtd_agent.update()
                seeker_agent.update()

            if done:
                break
        
        mtd_rewards_log.append(current_mtd_reward)
        seeker_rewards_log.append(current_seeker_reward)

        if i_episode % 100 == 0:
            avg_mtd_reward = np.mean(mtd_rewards_log)
            avg_seeker_reward = np.mean(seeker_rewards_log)
            print(f"에피소드: {i_episode}/{config.TOTAL_EPISODES} | MTD 평균 보상: {avg_mtd_reward:.2f} | Seeker 평균 보상: {avg_seeker_reward:.2f}")

    print("--- 훈련 완료 ---")

    torch.save(mtd_agent.policy_old.state_dict(), './mtd_agent_policy.pth')
    torch.save(seeker_agent.policy_old.state_dict(), './seeker_agent_policy.pth')
    print("훈련된 모델이 저장되었습니다.")

if __name__ == '__main__':
    train()