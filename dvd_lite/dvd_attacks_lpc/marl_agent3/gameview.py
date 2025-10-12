# gameview.py
import numpy as np

def map_seeker_macro(a_sk, num_ips, num_ports):
    macro = np.zeros_like(a_sk)
    
    base_pt = 2 + num_ips
    stealth = base_pt + num_ports
    probe = stealth + 1
    evade = probe + 1

    macro[a_sk == 0] = 0
    macro[a_sk == 1] = 0
    macro[a_sk == stealth] = 1
    macro[a_sk == probe] = 2
    macro[a_sk == evade] = 3
    macro[(a_sk >= 2) & (a_sk < base_pt)] = 4
    macro[(a_sk >= base_pt) & (a_sk < stealth)] = 5
    return macro

def summarize_round(upd_idx, elapsed_sec, ema_mtd, ema_sk, a_mtd, a_sk, r_mtd, r_sk, meta, num_ips, num_ports):
    mtd_actions = {
        "wait": float((a_mtd == 0).mean()),
        "ip_shuffle": float((a_mtd == 1).mean()),
        "port_shuffle": float((a_mtd == 2).mean()),
        "decoy": float((a_mtd == 3).mean()),
        "blacklist": float((a_mtd == 4).mean()),
    }
    
    sk_macro = map_seeker_macro(a_sk, num_ips, num_ports)
    seeker_actions = {
        "scan": float((sk_macro == 0).mean()),
        "stealth": float((sk_macro == 1).mean()),
        "probe": float((sk_macro == 2).mean()),
        "evade": float((sk_macro == 3).mean()),
        "attack_ip": float((sk_macro == 4).mean()),
        "attack_port": float((sk_macro == 5).mean()),
    }

    summary = {
        "update": upd_idx,
        "time_sec": elapsed_sec,
        "ema_reward_mtd": ema_mtd,
        "ema_reward_seeker": ema_sk,
        "avg_reward_mtd": float(np.mean(r_mtd)),
        "avg_reward_seeker": float(np.mean(r_sk)),
        "action_dist_mtd": mtd_actions,
        "action_dist_seeker": seeker_actions,
        "metrics": meta
    }
    return summary