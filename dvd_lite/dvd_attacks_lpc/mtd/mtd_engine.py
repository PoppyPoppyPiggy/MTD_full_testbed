from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
import gymnasium as gym

class MTDEngine:
    def __init__(self, env):
        self.env = env
        self.model = PPO(
            "MultiInputPolicy",
            self.env,
            verbose=0,
            tensorboard_log="./mtd_tensorboard/"
        )

    def learn(self, total_timesteps=10000):
        self.model.learn(total_timesteps=total_timesteps)

    def predict(self, obs):
        action, _states = self.model.predict(obs, deterministic=True)
        return action

    def save(self, path):
        self.model.save(path)

    def load(self, path):
        self.model = PPO.load(path, env=self.env)