# nmap_emulator.py
import numpy as np
from typing import Optional
import config

class NmapEmulator:
    """
    실제 nmap 호출 없이 nmap 동작/오차/탐지확률을 에뮬레이트.
    """
    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng()

    def scan_ip(self, steps_since_ip_shuffle: np.ndarray, H_ip: np.ndarray):
        """
        일반 IP 스캔: 탐지됨(True), 정보이득 큼.
        """
        recent_w = np.clip(steps_since_ip_shuffle / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.SCAN_BASE_REDUCTION_IP * (
            config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w
        )
        prior = H_ip
        post = np.maximum(prior - reduction, 0.0)
        info_gain = prior - post
        detected = np.full(H_ip.shape, True)
        return post, info_gain, detected

    def scan_port(self, steps_since_port_shuffle: np.ndarray, H_port: np.ndarray):
        """
        일반 Port 스캔: 탐지됨(True), 정보이득 큼.
        """
        recent_w = np.clip(steps_since_port_shuffle / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.SCAN_BASE_REDUCTION_PT * (
            config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w
        )
        prior = H_port
        post = np.maximum(prior - reduction, 0.0)
        info_gain = prior - post
        detected = np.full(H_port.shape, True)
        return post, info_gain, detected

    def stealth_scan(self, steps_since_ip_shuffle: np.ndarray, H_ip: np.ndarray):
        """
        스텔스 스캔: 탐지확률 낮음, 정보이득은 일반 스캔보다 작음.
        """
        recent_w = np.clip(steps_since_ip_shuffle / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.STEALTH_REDUCTION * (
            config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w
        )
        prior = H_ip
        post = np.maximum(prior - reduction, 0.0)
        info_gain = prior - post
        detected = self.rng.random(H_ip.shape) < config.STEALTH_DET_FACTOR
        return post, info_gain, detected

    def decoy_probe(self, decoy_on: np.ndarray):
        """
        디코이 존재 여부를 추정.
        """
        base = config.DECOY_PROBE_P
        p_succ = np.where(decoy_on, base * (1.0 - config.DECOY_FN), config.DECOY_FP)
        return self.rng.random(decoy_on.shape[0]) < p_succ