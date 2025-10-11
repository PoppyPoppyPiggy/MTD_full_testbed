# nmap_emulator.py  (Python 3.9 호환 버전)
import numpy as np
from typing import Optional
import config

class NmapEmulator:
    """
    실제 nmap 호출 없이 nmap 동작/오차/탐지확률을 에뮬레이트.
    - 일반 IP/Port 스캔: 탐지됨, 정보이득 큼(난이도에 비례 감소), 셔플 직후 정보이득 감소
    - 스텔스 스캔: 탐지확률 낮음, 정보이득 작음
    - 디코이 프로브: 디코이 존재시 높은 성공 확률, FP/FN 포함
    반환 형식은 환경에서 직접 보상 계산에 사용.
    """

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng()

    def _noise(self, size, p_false_pos: float = 0.02, p_false_neg: float = 0.05):
        # 필요시 스캔 결과에 FP/FN 섞을 때 사용 (현재는 정보량 추정 중심)
        fp = self.rng.random(size) < p_false_pos
        fn = self.rng.random(size) < p_false_neg
        return fp, fn

    def scan_ip(self, steps_since_ip_shuffle: np.ndarray, H_ip: np.ndarray):
        """
        일반 IP 스캔: 탐지됨(True), 정보이득 큼.
        셔플 직후(steps_since_ip_shuffle 작음)에는 정보이득이 줄어듦.
        """
        recent_w = np.clip(steps_since_ip_shuffle / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.SCAN_BASE_REDUCTION_IP * (
            config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w
        )
        prior = H_ip
        post = np.maximum(prior - reduction, 0.0)
        info_gain = prior - post
        detected = True  # 일반 스캔은 탐지됨
        return post, info_gain, detected

    def scan_port(self, steps_since_port_shuffle: np.ndarray, H_port: np.ndarray):
        """
        일반 Port 스캔: 탐지됨(True), 정보이득 큼.
        셔플 직후에는 정보이득이 줄어듦.
        """
        recent_w = np.clip(steps_since_port_shuffle / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.SCAN_BASE_REDUCTION_PT * (
            config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w
        )
        prior = H_port
        post = np.maximum(prior - reduction, 0.0)
        info_gain = prior - post
        detected = True
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
        detected = (self.rng.random() < config.STEALTH_DET_FACTOR)  # 낮은 탐지 확률
        return post, info_gain, detected

    def decoy_probe(self, decoy_on: np.ndarray):
        """
        디코이 존재 여부를 추정. 존재 시 높은 성공확률(하지만 FN 존재),
        없을 때는 낮은 FP 확률로 오탐 가능.
        """
        base = config.DECOY_PROBE_P
        p_succ = np.where(decoy_on, base * (1.0 - config.DECOY_FN), config.DECOY_FP)
        return self.rng.random(decoy_on.shape[0]) < p_succ
