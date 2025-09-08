import json, os, warnings
import pandas as pd, joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report

df=pd.read_csv("bus/window_features.csv")
y=df["atk"].fillna("baseline")
# 희소 라벨 정리
vc=y.value_counts()
keep=set(vc[vc>=3].index.tolist()+["baseline"])
y=y.where(y.isin(keep),"unknown")

feat_base=["pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"]
feat_extra=[c for c in ["status_len_mean","param_id_nuniq","atk_pps_mean"] if c in df.columns]
X=df[feat_base+feat_extra].fillna(0.0)

n=len(X); n_classes=y.nunique()
print("LABEL COUNTS:\n",y.value_counts())

# 분할 전략 결정
do_strat = (y.value_counts().min()>=2 and n>=12 and n_classes>=2)
test_size = 0.25 if n>=12 else (0.33 if n>=6 else 0.5 if n>=4 else 0.2)
if n<4:
    Xtr,Xte,ytr,yte = X, X, y, y
else:
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=test_size,random_state=42,
                                     stratify=y if do_strat else None)

base=make_pipeline(StandardScaler(with_mean=False),
                   LogisticRegression(max_iter=3000,class_weight="balanced"))

# 데이터가 충분하면 확률보정, 아니면 베이스 사용
try:
    if do_strat and n>=30:
        clf=CalibratedClassifierCV(base, method="isotonic", cv=3).fit(Xtr,ytr)
    else:
        clf=base.fit(Xtr,ytr)
except Exception as e:
    warnings.warn(f"calibration fallback due to {e}")
    clf=base.fit(Xtr,ytr)

print(classification_report(yte, clf.predict(Xte), zero_division=0))
Path("bus/models").mkdir(parents=True, exist_ok=True)
joblib.dump(clf,"bus/models/attack_clf.pkl")
print("SAVED bus/models/attack_clf.pkl")

pol={"policy":{
    "mavlink_statustext_noise":{"action":"tc_filter","args":{"loss_pct":1.0,"delay_ms":2,"jitter_ms":1,"dup_pct":0.0}},
    "mavlink_param_poll":{"action":"tc_filter","args":{"loss_pct":0.5,"delay_ms":1,"jitter_ms":1,"dup_pct":0.0}},
    "gps_slow_spoof":{"action":"port_shuffle","args":{}},
    "baseline":{"action":"none","args":{}},
    "unknown":{"action":"tc_filter","args":{"loss_pct":0.5,"delay_ms":1,"jitter_ms":1,"dup_pct":0.0}}
}}
Path("bus/models/mtd_policy.json").write_text(json.dumps(pol,indent=2))
print("WROTE bus/models/mtd_policy.json")
