# environment.py
import numpy as np
import config

class MTDEnvironment:
    """
    MTD vs Seeker 사이의 상호작용을 모델링하는 확률적 게임(Stochastic Game) 환경.
    상태는 '공격 표면'으로 정의되며, 두 에이전트의 공동 행동에 따라 상태 전이와 보상이 결정됨.
    """
    def __init__(self):
        # --- 상태 공간 (State Space) 정의: 공격 표면 ---
        self.active_ip = np.random.randint(0, config.NUM_IPS)
        self.active_port = np.random.randint(0, config.NUM_PORTS)
        self.decoy_active = False
        self.decoy_ip = -1
        self.decoy_port = -1
        self.blacklisted_ip = -1

        # --- 행동 공간 (Action Space) 정의 ---
        self.mtd_action_space_n = 5
        self.seeker_action_space_n = 2
        
        self.current_step = 0
        
        # [개선] 상태 벡터의 차원을 미리 계산
        self.state_dim = 6 

    def get_state(self):
        """[수정] 현재 환경의 상태(공격 표면)를 정규화된 벡터로 반환."""
        # 상태 벡터: [활성IP, 활성포트, 미끼활성여부, 미끼IP, 미끼포트, 블랙리스트IP]
        # 신경망의 안정적인 학습을 위해 각 요소를 0과 1 사이로 정규화합니다.
        state = np.array([
            self.active_ip / config.NUM_IPS,
            self.active_port / config.NUM_PORTS,
            1.0 if self.decoy_active else 0.0,
            self.decoy_ip / config.NUM_IPS if self.decoy_active else -1.0,
            self.decoy_port / config.NUM_PORTS if self.decoy_active else -1.0,
            self.blacklisted_ip / config.NUM_IPS if self.blacklisted_ip != -1 else -1.0
        ], dtype=np.float32)
        return state

    def reset(self):
        """환경을 초기 상태로 리셋."""
        self.active_ip = np.random.randint(0, config.NUM_IPS)
        self.active_port = np.random.randint(0, config.NUM_PORTS)
        self.decoy_active = False
        self.decoy_ip = -1
        self.decoy_port = -1
        self.blacklisted_ip = -1
        self.current_step = 0
        return self.get_state()

    def step(self, mtd_action, seeker_action):
        """
        두 에이전트의 행동을 받아 환경을 한 스텝 진행.
        다음 상태, 각 에이전트의 보상, 종료 여부를 반환.
        """
        self.current_step += 1
        
        mtd_reward = config.COST_MTD_TIME_STEP
        seeker_reward = 0
        done = False

        # 1. MTD 에이전트 행동 처리
        mtd_reward += self._execute_mtd_action(mtd_action)

        # 2. Seeker 에이전트 행동 처리
        breach, decoy_hit, blocked = self._execute_seeker_action(seeker_action)

        # 3. 보상 계산
        if blocked:
            mtd_reward += config.REWARD_MTD_SUCCESSFUL_DEFENSE
            seeker_reward += config.COST_SEEKER_BLOCKED
        elif decoy_hit:
            mtd_reward += config.REWARD_MTD_DECOY_ENGAGED
            seeker_reward += config.COST_SEEKER_DECOY_ENGAGED
        elif breach:
            mtd_reward += config.REWARD_MTD_BREACH
            seeker_reward += config.REWARD_SEEKER_BREACH
            done = True
        
        # [개선] 스캔 행동에 대한 보상을 명확히 분리
        if seeker_action == 0: # 스캔 행동
             mtd_reward += config.REWARD_MTD_SCAN_DETECTED
             seeker_reward += config.COST_SEEKER_SCAN
        
        # 4. 에피소드 종료 조건 확인
        if self.current_step >= config.MAX_STEPS_PER_EPISODE:
            done = True

        return self.get_state(), mtd_reward, seeker_reward, done

    def _execute_mtd_action(self, action):
        """MTD 행동을 실행하고 그에 따른 비용을 반환."""
        action_cost = 0
        
        # [개선] 블랙리스트는 한 스텝 후에 자동으로 해제되도록 로직 수정
        if self.blacklisted_ip != -1:
            self.blacklisted_ip = -1

        if action == 1: # IP 셔플링
            self.active_ip = np.random.randint(0, config.NUM_IPS)
            action_cost = config.COST_MTD_ACTION
        elif action == 2: # 포트 셔플링
            self.active_port = np.random.randint(0, config.NUM_PORTS)
            action_cost = config.COST_MTD_ACTION
        elif action == 3: # 미끼 배포
            if not self.decoy_active:
                self.decoy_active = True
                self.decoy_ip = (self.active_ip + np.random.randint(1, config.NUM_IPS)) % config.NUM_IPS
                self.decoy_port = (self.active_port + np.random.randint(1, config.NUM_PORTS)) % config.NUM_PORTS
                action_cost = config.COST_MTD_ACTION
        elif action == 4: # 블랙리스트
            self.blacklisted_ip = self.active_ip
            action_cost = config.COST_MTD_BLACKLIST
            
        return action_cost

    def _execute_seeker_action(self, action):
        """Seeker 행동을 실행하고 결과를 반환."""
        breach, decoy_hit, blocked = False, False, False
        
        if action == 1: # 공격
            # 블랙리스트 확인
            if self.active_ip == self.blacklisted_ip:
                blocked = True
            # 미끼 공격 확인
            elif self.decoy_active and np.random.rand() < 0.5: 
                decoy_hit = True
            # 실제 시스템 공격
            else:
                if np.random.rand() < 0.7:
                    breach = True
        
        return breach, decoy_hit, blocked