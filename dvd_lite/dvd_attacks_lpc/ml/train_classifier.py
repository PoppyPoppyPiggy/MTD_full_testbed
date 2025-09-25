import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report

# --- 경로 설정 ---
ML_DIR = os.path.dirname(__file__)
INPUT_CSV_PATH = os.path.join(ML_DIR, 'output', 'labeled_cti_dataset.csv')
OUTPUT_MODEL_PATH = os.path.join(ML_DIR, 'output', 'cti_classifier_model.joblib')

def create_ensemble_model():
    """다양한 알고리즘을 결합한 앙상블 모델을 생성하여 탐지 정확도와 안정성을 향상시킵니다."""
    
    # 개별 분류기 정의
    clf1 = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf2 = GradientBoostingClassifier(n_estimators=100, random_state=42)
    clf3 = SVC(probability=True, random_state=42) # 확률 예측을 위해 probability=True 설정

    # VotingClassifier를 사용한 앙상블 모델 (Soft Voting)
    # 각 모델의 예측 확률을 평균내어 최종 클래스를 결정하므로 더 부드러운 결정 경계를 가짐
    ensemble_model = VotingClassifier(
        estimators=[('rf', clf1), ('gb', clf2), ('svc', clf3)],
        voting='soft'
    )
    return ensemble_model

def main():
    try:
        df = pd.read_csv(INPUT_CSV_PATH)
        print(f"데이터셋 로드 완료. 총 {len(df)}개 레코드, {len(df.columns)}개 피처.")
    except FileNotFoundError:
        print(f"[!] 오류: '{INPUT_CSV_PATH}' 파일을 찾을 수 없습니다. data_builder.py를 먼저 실행하세요.")
        return

    # 타겟 변수 설정
    y = df['label_attack']
    
    # 숫자형/범주형 피처 자동 선택
    numeric_features = df.select_dtypes(include=['number']).columns.tolist()
    categorical_features = df.select_dtypes(include=['object', 'bool']).columns.tolist()

    # 타겟 변수 및 불필요한 변수 제외
    features_to_drop = ['label_attack', 'timestamp', 'ts', 'log_source'] 
    numeric_features = [f for f in numeric_features if f not in features_to_drop and df[f].nunique() > 1]
    categorical_features = [f for f in categorical_features if f not in features_to_drop and df[f].nunique() > 1]

    X = df[numeric_features + categorical_features]

    # 전처리기 정의
    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('onehot', OneHotEncoder(handle_unknown='ignore'))])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features)])
    
    # 앙상블 모델 생성
    ensemble = create_ensemble_model()
    
    # 전체 파이프라인 구성
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', ensemble)
    ])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    
    print("\n🤖 AI 앙상블 모델 학습 시작...")
    model_pipeline.fit(X_train, y_train)
    print("✅ 학습 완료.")

    y_pred = model_pipeline.predict(X_test)
    print("\n[📊 AI 모델 성능 평가]\n")
    print(classification_report(y_test, y_pred))

    joblib.dump(model_pipeline, OUTPUT_MODEL_PATH)
    print(f"💾 학습된 AI 모델 저장 완료 -> '{OUTPUT_MODEL_PATH}'")

if __name__ == "__main__":
    main()