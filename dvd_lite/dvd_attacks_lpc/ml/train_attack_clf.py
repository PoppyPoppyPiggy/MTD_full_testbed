
import json, warnings
from pathlib import Path
import pandas as pd, numpy as np
import joblib
from collections import Counter

BUS=Path("bus"); OUT=BUS/"models/attack_clf.pkl"; OUT.parent.mkdir(parents=True,exist_ok=True)

def train_centroid(df):
    feats=["pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"]
    X=df[feats].fillna(0.0).astype(float).to_numpy()
    y=df["atk"].astype(str).to_numpy()
    labels=sorted(pd.unique(y))
    centroids={}; stdevs={}
    for lab in labels:
        sub=X[y==lab]
        centroids[lab]=sub.mean(axis=0).tolist()
        st=np.std(sub,axis=0); st[st==0]=1.0
        stdevs[lab]=st.tolist()
    return {"type":"centroid_v1","feats":feats,"labels":labels,
            "centroids":centroids,"stdevs":stdevs}

def main():
    BUS.mkdir(exist_ok=True)
    df=pd.read_csv(BUS/"window_features.csv")
    if df.empty:
        raise SystemExit("no features")
    # 최소 표본 보호: 클래스 1개뿐이면 전부 baseline 취급
    if df["atk"].nunique()<2:
        df["atk"]="baseline"
    model=train_centroid(df)
    joblib.dump(model, OUT)
    print("SAVED", OUT)

if __name__=="__main__":
    main()
