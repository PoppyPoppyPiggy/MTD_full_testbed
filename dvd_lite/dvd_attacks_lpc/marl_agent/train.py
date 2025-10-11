# train.py
import torch
import numpy as np
import time  # <<-- [수정 1] 시간 측정을 위해 time 모듈 추가
import os    # <<-- [수정 2] 결과 저장을 위한 폴더 생성용 모듈 추가
import pandas as pd # <<-- [수정 3] CSV 저장을 위해 pandas 추가
import matplotlib.pyplot as plt # <<-- [수정 4] 그래프 생성을 위해 matplotlib 추가
import config
from environment_torch import MTDSeekerEnvTorch
from ppo_agent_torch import PPO, Buffer

def save_results(history, level, n_envs):
    """학습이 끝난 후 보상 기록을 CSV로 저장하고 그래프를 생성합니다."""
    if not history['updates']:
        print("기록된 데이터가 없어 결과를 저장하지 않습니다.")
        return

    # 결과 저장 폴더 생성
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    
    # 데이터프레임 생성 및 CSV 저장
    df = pd.DataFrame(history)
    csv_filename = os.path.join(results_dir, f"log_L{level}_E{n_envs}.csv")
    df.to_csv(csv_filename, index=False)
    print(f"\n학습 기록이 '{csv_filename}' 파일로 저장되었습니다.")

    # 학습 곡선 그래프 생성 및 저장
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))
    
    ax.plot(df['updates'], df['mtd_rewards'], label='MTD Reward (EMA)', color='royalblue')
    ax.plot(df['updates'], df['seeker_rewards'], label='Seeker Reward (EMA)', color='coral')
    
    ax.set_title(f'MARL Training Curve (Level: {level}, Envs: {n_envs})', fontsize=16, fontweight='bold')
    ax.set_xlabel('Updates', fontsize=12)
    ax.set_ylabel('EMA of Rewards', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    
    plt.tight_layout()
    img_filename = os.path.join(results_dir, f"learning_curve_L{level}_E{n_envs}.png")
    plt.savefig(img_filename, dpi=150)
    print(f"학습 곡선 그래프가 '{img_filename}' 파일로 저장되었습니다.")
    # plt.show() # 로컬에서 바로 확인하고 싶을 때 주석 해제

def train():
    dev = config.DEVICE
    env = MTDSeekerEnvTorch(config.N_ENVS, device=dev)
    S = env.reset()

    mtd = PPO(env.state_dim, env.mtd_n, dev)
    sk  = PPO(env.state_dim, env.seeker_n, dev)
    cap = config.ROLLOUT_STEPS * config.N_ENVS
    mbuf = Buffer(cap, env.state_dim, dev)
    sbuf = Buffer(cap, env.state_dim, dev)

    ema_m = 0.0; ema_s = 0.0; alpha = 0.02
    
    # <<-- [수정 5] 학습 기록 및 시간 측정을 위한 변수 초기화
    history = {'updates': [], 'mtd_rewards': [], 'seeker_rewards': []}
    start_time = time.time()

    print(f"####### [v12] MTD–Seeker Full-GPU War Game: device={dev.type}, n_envs={config.N_ENVS}, level={config.LEVEL} #######")
    print(f"State:{env.state_dim}, MTD actions:{env.mtd_n}, Seeker actions:{env.seeker_n} | IPs={config.NUM_IPS}, Ports={config.NUM_PORTS}")

    with torch.no_grad():
        for _ in range(5):
            am, lm = mtd.act(S); as_, ls = sk.act(S)
            vm = mtd.old.evaluate(S, am)[1]; vs = sk.old.evaluate(S, as_)[1]
            S, mr, sr, d = env.step(am, as_)

    for upd in range(1, config.TOTAL_UPDATES + 1):
        m_hist=[]; s_hist=[]
        mbuf.ptr = 0; sbuf.ptr = 0

        for _ in range(config.ROLLOUT_STEPS):
            with torch.no_grad():
                am, lm = mtd.act(S)
                as_, ls = sk.act(S)
                vm = mtd.old.evaluate(S, am)[1]
                vs = sk.old.evaluate(S, as_)[1]
            
            m_hist.append(am.cpu().numpy())
            s_hist.append(as_.cpu().numpy())
            
            S_next, mr, sr, d = env.step(am, as_)
            
            mbuf.add_batch(S,  am, lm, mr, vm, d)
            sbuf.add_batch(S,  as_, ls, sr, vs, d)
            S = S_next

        mtd.update(mbuf)
        sk.update(sbuf)
        
        ema_m = (1-alpha)*ema_m + alpha*float(mr.mean().item())
        ema_s = (1-alpha)*ema_s + alpha*float(sr.mean().item())

        if upd % config.LOG_INTERVAL == 0:
            # <<-- [수정 6] 로그 출력 시점에 history에 데이터 기록
            history['updates'].append(upd)
            history['mtd_rewards'].append(ema_m)
            history['seeker_rewards'].append(ema_s)
            
            m_dist = {name: 0 for name in config.MTD_ACTIONS.keys()}
            s_dist = {name: 0 for name in config.SEEKER_ACTIONS.keys()}
            m_flat = np.concatenate(m_hist)
            s_flat = np.concatenate(s_hist)
            
            for k, v in config.MTD_ACTIONS.items(): m_dist[k] = np.count_nonzero(m_flat == v)
            for k, v in config.SEEKER_ACTIONS.items(): s_dist[k] = np.count_nonzero(s_flat == v)
            
            m_tot = len(m_flat) or 1; s_tot = len(s_flat) or 1
            m_dist_str = {k: f"{100*v/m_tot:.1f}%" for k,v in m_dist.items()}
            s_dist_str = {k: f"{100*v/s_tot:.1f}%" for k,v in s_dist.items()}
            
            print(f"\n[Update {upd}/{config.TOTAL_UPDATES}] EMA → MTD: {ema_m:+.2f}, Seeker: {ema_s:+.2f}")
            print(f" · MTD 전략: {m_dist_str}")
            print(f" · Seeker 전략: {s_dist_str}")
            print(f" · 게임 국면: 예산: {env.budget.mean().item():.1f} | AS 노출: {env.as_exp.mean().item():.2f}, 변동성: {env.as_var.mean().item():.2f}")
        
        # <<-- [수정 7] 매 업데이트마다 시간 제한 체크
        if config.TRAINING_TIME_LIMIT_MINUTES > 0:
            elapsed_seconds = time.time() - start_time
            if elapsed_seconds > config.TRAINING_TIME_LIMIT_MINUTES * 60:
                print(f"\n시간 제한({config.TRAINING_TIME_LIMIT_MINUTES}분) 도달. 훈련을 조기 종료합니다.")
                break

    print("훈련 종료.")
    # <<-- [수정 8] 훈련 종료 후 결과 저장 함수 호출
    save_results(history, config.LEVEL, config.N_ENVS)

if __name__ == "__main__":
    train()