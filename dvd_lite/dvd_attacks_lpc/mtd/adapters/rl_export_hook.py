import json, pathlib

def export_rl_policy_means(out_path: str, metrics: dict):
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ip_cd_mean": float(metrics.get("ip_cd_mean", 30.0)),
        "decoy_ratio_mean": float(metrics.get("decoy_ratio_mean", 0.1)),
        "bl_level_mean": float(metrics.get("bl_level_mean", 1.0))
    }
    p.write_text(json.dumps(data, indent=2))
