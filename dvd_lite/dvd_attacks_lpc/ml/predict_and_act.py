import json, joblib, pandas as pd, subprocess, time, os
MODEL="bus/models/attack_clf.joblib"; LAB="bus/models/attack_labels.joblib"; POL="bus/models/mtd_policy.json"
clf=joblib.load(MODEL); lab=joblib.load(LAB)
policy=json.load(open(POL))["policy"]
def predict_last(df):
    X=df[["pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"]].fillna(0.0)
    y=lab.inverse_transform(clf.predict(X))
    return list(zip(df["scn"],df["t0"],df["t1"],y))
def act_for_attack(atk):
    p=policy.get(atk) or policy.get("default") or {"name":"none"}
    return p["name"]
def run_once():
    df=pd.read_csv("bus/window_features.csv")
    if df.empty: return
    scn,t0,t1,atk = predict_last(df.tail(1))[0]
    action = act_for_attack(atk)
    print(f"[detect] atk={atk} -> action={action}")
    subprocess.run(["bash","rl/apply_mtd_action.sh", action, "gcs", "mavlink"], check=False)
if __name__=="__main__":
    # 단발 실행; 루프 운용은 외부 쉘에서
    run_once()
