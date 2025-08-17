#!/usr/bin/env python3
"""
dvd_lite/dvd_attacks_lpc/ml/train_baseline.py

시간 분할(TimeSeriesSplit)로 멀티클래스 분류 베이스라인(LogReg/RF)을 학습·평가한다.
입력: ../../supervised_data/unified_dataset.{parquet|csv}
출력: 콘솔(분류 리포트, macro PR-AUC)
"""
from pathlib import Path
import argparse, numpy as np, pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, average_precision_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

def load_table(path: Path):
    if path.suffix == ".parquet":
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.read_csv(str(path).replace(".parquet",".csv"))
    return pd.read_csv(path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=str, default="../../supervised_data/unified_dataset.parquet")
    args = ap.parse_args()

    df = load_table(Path(args.dataset))
    assert "module" in df.columns, "dataset must include 'module'"

    # 피처: 수치형만 사용 (시간 경계는 drop)
    Xdf = df.select_dtypes(include=[float,int]).drop(
        columns=[c for c in df.columns if c.startswith("end_t")], errors="ignore"
    )
    X = Xdf.to_numpy()
    # 결측 평균 대치
    col_means = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_means, inds[1])

    # 레이블
    y = df["module"].astype("category").cat.codes.to_numpy()
    classes = df["module"].astype("category").cat.categories.tolist()

    # 시간 순서 유지(가능하면 start_t 기준)
    if "start_t" in df.columns:
        order = np.argsort(df["start_t"].to_numpy())
        X, y = X[order], y[order]

    models = {
        "logreg": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=200, class_weight="balanced"))
        ]),
        "rf": Pipeline([
            ("clf", RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=42))
        ])
    }

    tscv = TimeSeriesSplit(n_splits=5)
    for name, pipe in models.items():
        print(f"\n=== {name.upper()} ===")
        pr_aucs = []
        for fold, (tr, te) in enumerate(tscv.split(X), 1):
            pipe.fit(X[tr], y[tr])
            yhat = pipe.predict(X[te])
            print(f"[Fold {fold}]")
            print(classification_report(y[te], yhat, target_names=classes, digits=3))
            if hasattr(pipe, "predict_proba"):
                P = pipe.predict_proba(X[te])
                ap = [average_precision_score((y[te]==k).astype(int), P[:,k]) for k in range(len(classes))]
                pr_aucs.append(np.mean(ap))
        if pr_aucs:
            print(f"Mean macro PR AUC: {np.mean(pr_aucs):.3f}")

if __name__ == "__main__":
    main()
