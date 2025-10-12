# nmap_emulator.py
import numpy as np
import config

class NmapEmulator:
    def __init__(self, rng: np.random.Generator):
        self.rng = rng

    def _get_reduction(self, steps_since, base_reduction):
        w = np.exp(-steps_since / config.RECENT_WIN)
        return base_reduction + w * config.SCAN_REDUCTION_AT0

    def scan_ip(self, steps_since_ip, current_h_ip):
        reduction = self._get_reduction(steps_since_ip, config.SCAN_BASE_REDUCTION_IP)
        info_gain = np.minimum(current_h_ip, reduction)
        post_h_ip = np.maximum(0.0, current_h_ip - info_gain)
        detected = self.rng.random(current_h_ip.shape) < (0.15 + 0.05 * config.LEVEL)
        return post_h_ip, info_gain, detected

    def scan_port(self, steps_since_pt, current_h_pt):
        reduction = self._get_reduction(steps_since_pt, config.SCAN_BASE_REDUCTION_PT)
        info_gain = np.minimum(current_h_pt, reduction)
        post_h_pt = np.maximum(0.0, current_h_pt - info_gain)
        detected = self.rng.random(current_h_pt.shape) < (0.15 + 0.05 * config.LEVEL)
        return post_h_pt, info_gain, detected

    def stealth_scan(self, steps_since_ip, current_h_ip):
        reduction = self._get_reduction(steps_since_ip, config.STEALTH_REDUCTION)
        info_gain = np.minimum(current_h_ip, reduction)
        post_h_ip = np.maximum(0.0, current_h_ip - info_gain)
        detected = self.rng.random(current_h_ip.shape) < (0.05 * config.STEALTH_DET_FACTOR)
        return post_h_ip, info_gain, detected

    def decoy_probe(self, decoy_active_mask):
        p = np.full(decoy_active_mask.shape, config.DECOY_FP, dtype=np.float32)
        p[decoy_active_mask] = config.DECOY_PROBE_P
        
        fn_mask = decoy_active_mask & (self.rng.random(p.shape) < config.DECOY_FN)
        
        success = self.rng.random(p.shape) < p
        success[fn_mask] = False
        return success