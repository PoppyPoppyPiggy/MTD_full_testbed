import os,csv,joblib,sys
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
IN="bus/window_features.csv"; assert os.path.exists(IN), IN
df=pd.read_csv(IN)
# 학습용: 공격/CTI 특성
X=df[["pps","bytes","loss_pct","delay_ms","jitter_ms","dup_pct"]].fillna(0.0)
y=df["atk"].astype(str)
le=LabelEncoder(); y_enc=le.fit_transform(y)
Xtr,Xte,ytr,yte=train_test_split(X,y_enc,test_size=0.25,random_state=42,stratify=y_enc)
clf=RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced")
clf.fit(Xtr,ytr)
yp=clf.predict(Xte)
print(classification_report(yte, yp, target_names=le.classes_))
print(confusion_matrix(yte, yp))
os.makedirs("bus/models",exist_ok=True)
joblib.dump(clf,"bus/models/attack_clf.joblib")
joblib.dump(le, "bus/models/attack_labels.joblib")
print("SAVED models to bus/models/")
