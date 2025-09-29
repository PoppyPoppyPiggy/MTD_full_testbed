from stable_baselines3.common.vec_env import DummyVecEnv
from rl.enviornment import AdversarialDroneEnv
from mtd.mtd_engine import MTDEngine
from rl.seeker import Seeker

def main():
    # 1. 임시 더미 에이전트 생성 (상대방으로 사용하기 위함)
    # 실제 환경은 아래에서 생성되므로 여기서는 None으로 임시 설정
    dummy_mtd_agent = MTDEngine(env=None)
    dummy_seeker_agent = Seeker(env=None)

    # 2. 각 에이전트의 학습 환경과 모델 생성
    mtd_env = DummyVecEnv([lambda: AdversarialDroneEnv(opponent_agent=dummy_seeker_agent, training_mtd=True)])
    mtd_agent = MTDEngine(mtd_env)

    seeker_env = DummyVecEnv([lambda: AdversarialDroneEnv(opponent_agent=dummy_mtd_agent, training_mtd=False)])
    seeker_agent = Seeker(seeker_env)
    
    # 3. 실제 에이전트를 서로의 상대로 설정
    mtd_env.envs[0].opponent_agent = seeker_agent
    seeker_env.envs[0].opponent_agent = mtd_agent
    
    # 4. 적대적 학습 루프
    training_rounds = 10
    timesteps_per_round = 5000

    print("--- 적대적 강화학습 시작 ---")
    for round_num in range(training_rounds):
        print(f"\n--- [ 라운드 {round_num + 1}/{training_rounds} ] ---")
        
        # MTD 에이전트 학습 (Seeker 정책은 고정)
        print(f"-> MTD 에이전트 학습 시작...")
        mtd_agent.learn(total_timesteps=timesteps_per_round)
        
        # Seeker 에이전트 학습 (MTD 정책은 고정)
        print(f"-> Seeker 에이전트 학습 시작...")
        seeker_agent.learn(total_timesteps=timesteps_per_round)
        
        print(f"-> 라운드 {round_num + 1} 학습 완료")

    # 5. 모델 저장
    mtd_agent.save("mtd_agent_adversarial.zip")
    seeker_agent.save("seeker_agent_adversarial.zip")
    print("\n--- 학습 완료! 모델이 성공적으로 저장되었습니다. ---")


if __name__ == "__main__":
    main()