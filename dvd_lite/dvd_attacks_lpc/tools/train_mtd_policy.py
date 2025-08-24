#!/usr/bin/env python3
import pandas as pd, numpy as np, sys, argparse, joblib
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor

parser = argparse.ArgumentParser()
parser.add_argument("csv", nargs="?", default="attack_output/dataset.csv")
parser.add_argument("--no-split", action="store_true", help="데이터가 적든 많든 train/test split 없이 전체로 학습")
parser.add_argument("--test-size", type=float, default=0.3, help="split 비율(기본 0.3)")
parser.add_argument("--min-split", type=int, default=5, help="split을 시도하기 위한 최소 샘플 개수(기본 5)")
args = parser.parse_args()

df = pd.read_csv(args.csv).replace({np.nan: 0, "": 0})

X = df[["mtd_action","drop_old","grace","feat_pre_loss","feat_pre_delay","feat_pre_jitter"]]
y = df["label_disruption_window"].astype(float).fillna(0)

cat_cols=["mtd_action","drop_old"]
num_cols=["grace","feat_pre_loss","feat_pre_delay","feat_pre_jitter"]
pre = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ("num", "passthrough", num_cols)
])

pipe = Pipeline([
    ("pre", pre),
    ("rf", RandomForestRegressor(n_estimators=200, random_state=42))
])

n = len(df)
def fit_all():
    pipe.fit(X, y)
    print(f"[WARN] n={n}. Split 미수행(전량 학습). R2(train)=NA  R2(test)=NA")

if args.no_split or n < args.min_split or n < 3:
    fit_all()
else:
    from sklearn.model_selection import train_test_split
    try:
        Xtr,Xte,ytr,yte = train_test_split(X, y, test_size=args.test_size, random_state=42)
        pipe.fit(Xtr,ytr)
        print("R2(train)=", pipe.score(Xtr,ytr), " R2(test)=", pipe.score(Xte,yte))
    except ValueError as e:
        print(f"[WARN] split 실패({e}). 전량 학습으로 전환.")
        fit_all()

joblib.dump(pipe, "attack_output/mtd_policy_rf.joblib")
print("[OK] saved -> attack_output/mtd_policy_rf.joblib")
