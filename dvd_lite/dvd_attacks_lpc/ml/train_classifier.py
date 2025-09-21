import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report

# --- 경로 설정 ---
ML_DIR = os.path.dirname(__file__)
INPUT_CSV_PATH = os.path.join(ML_DIR, 'output', 'labeled_cti_dataset.csv')
OUTPUT_MODEL_PATH = os.path.join(ML_DIR, 'output', 'cti_classifier_model.joblib')

def main():
    try:
        df = pd.read_csv(INPUT_CSV_PATH)
        print(f"데이터셋 로드 완료. 총 {len(df)}개 레코드.")
    except FileNotFoundError:
        print(f"오류: '{INPUT_CSV_PATH}' 파일을 찾을 수 없습니다. data_builder.py를 먼저 실행하세요.")
        return

    # '기동부', '통신부', '제어부' 라벨은 향후 추가 예정. 우선 'Attack' vs 'Normal' 분류.
    y = df['label_attack']
    
    numeric_features = df.select_dtypes(include=['number']).columns.tolist()
    categorical_features = df.select_dtypes(include=['object', 'bool']).columns.tolist()

    # 타겟 변수 및 불필요한 변수 제외
    features_to_drop = ['label_attack', 'label_mtd', 'timestamp']
    numeric_features = [f for f in numeric_features if f not in features_to_drop]
    categorical_features = [f for f in categorical_features if f not in features_to_drop]

    X = df[numeric_features + categorical_features]

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', Pipeline([('imputer', SimpleImputer(strategy='median')), ('scaler', StandardScaler())]), numeric_features),
            ('cat', Pipeline([('imputer', SimpleImputer(strategy='most_frequent')), ('onehot', OneHotEncoder(handle_unknown='ignore'))]), categorical_features)
        ])
    
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1))
    ])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    
    print("\n🤖 AI 모델 학습 시작...")
    model_pipeline.fit(X_train, y_train)
    print("✅ 학습 완료.")

    y_pred = model_pipeline.predict(X_test)
    print("\n[📊 AI 모델 성능 평가]\n")
    print(classification_report(y_test, y_pred))

    joblib.dump(model_pipeline, OUTPUT_MODEL_PATH)
    print(f"💾 학습된 AI 모델 저장 완료 -> '{OUTPUT_MODEL_PATH}'")

if __name__ == "__main__":
    main()