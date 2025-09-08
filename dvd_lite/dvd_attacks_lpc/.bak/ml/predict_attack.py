import sys,joblib,pandas as pd
mdl="bus/models/attack_clf.joblib"; le="bus/models/attack_labels.joblib"
clf=joblib.load(mdl); lab=joblib.load(le)
df=pd.read_csv(sys.argv[1] if len(sys.argv)>1 else "bus/window_features.csv")
X=df[["pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"]].fillna(0.0)
pred=lab.inverse_transform(clf.predict(X))
out=df[["scn","t0","t1"]].copy(); out["pred_atk"]=pred
out.to_csv("bus/predictions.csv", index=False)
print("WROTE bus/predictions.csv rows", len(out))
