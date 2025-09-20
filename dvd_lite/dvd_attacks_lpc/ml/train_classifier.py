import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

def main():
    dataset_path = "labeled_cti_dataset.csv"
    try:
        df = pd.read_csv(dataset_path)
    except FileNotFoundError:
        print(f"오류: '{dataset_path}' 파일 없음. data_builder.py를 먼저 실행하세요.")
        return

    X_train, X_test, y_train, y_test = train_test_split(df['log_text'], df['category'], test_size=0.2, random_state=42)

    # 파이프라인: 텍스트 데이터 -> 숫자 벡터 -> 분류 모델
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer()),
        ('clf', LogisticRegression())
    ])

    print("AI 모델 학습 시작...")
    pipeline.fit(X_train, y_train)
    print("학습 완료.")

    print("\n[AI 모델 성능 평가]\n")
    print(classification_report(y_test, pipeline.predict(X_test)))

    model_path = "cti_classifier_model.joblib"
    joblib.dump(pipeline, model_path)
    print(f"학습된 AI 모델 저장 완료 -> '{model_path}'")

if __name__ == "__main__":
    main()