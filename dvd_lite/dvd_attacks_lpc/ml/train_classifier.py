#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
import joblib
import json
import argparse
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import matplotlib.pyplot as plt
import seaborn as sns

# --- Path Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'ml', 'output')

def main():
    parser = argparse.ArgumentParser(description="CTI Classifier Trainer v4.0 (Multi-class)")
    parser.add_argument('--train-data', default=os.path.join(OUTPUT_DIR, 'train_dataset.csv'), help="Training dataset CSV file path")
    parser.add_argument('--test-data', default=os.path.join(OUTPUT_DIR, 'test_dataset.csv'), help="Testing dataset CSV file path")
    args = parser.parse_args()
    
    print("🚀 [Classifier Trainer v4.0] Starting CTI model training.")

    # 1. Load Data
    try:
        train_df = pd.read_csv(args.train_data)
        test_df = pd.read_csv(args.test_data)
    except FileNotFoundError as e:
        print(f"❌ Error: Data file not found. '{e.filename}'")
        print("    Ensure data_builder.py and dataset_manager.py were run first.")
        sys.exit(1)

    X_train = train_df.drop('label', axis=1).fillna(0) 
    y_train = train_df['label']
    X_test = test_df.drop('label', axis=1).fillna(0)
    y_test = test_df['label']

    # ⭐️ IMPORTANT: Save the list of features used for training (maintains order for real-time agent)
    training_features = list(X_train.columns)
    features_path = os.path.join(OUTPUT_DIR, 'training_features.json')
    with open(features_path, 'w') as f:
        json.dump({'features': training_features}, f, indent=4)
    print(f"[*] Saved {len(training_features)} feature names to '{features_path}' for model consistency.")

    # 2. Model Training
    print("[*] Training RandomForestClassifier model...")
    # class_weight='balanced' handles data imbalance
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced', n_jobs=-1)
    model.fit(X_train, y_train)
    print("✅ Model training complete.")

    # 3. Model Saving
    model_path = os.path.join(OUTPUT_DIR, 'cti_classifier_model.joblib')
    joblib.dump(model, model_path)
    print(f"[*] Trained model saved to '{model_path}'.")
    
    # 4. Model Evaluation
    print("\n" + "="*60)
    print("📊 Model Performance Evaluation (Test Set)")
    print("="*60)
    y_pred = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n- Overall Accuracy: {accuracy:.4f}\n")
    
    print("- Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    # 5. Confusion Matrix Visualization
    print("- Confusion Matrix:")
    class_labels = model.classes_
    cm = confusion_matrix(y_test, y_pred, labels=class_labels)
    cm_df = pd.DataFrame(cm, index=class_labels, columns=class_labels)
    print(cm_df)
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', linewidths=.5, linecolor='gray')
    plt.title('Confusion Matrix')
    plt.xlabel('Predicted Label')
    plt.ylabel('True Label')
    plt.tight_layout()
    
    cm_path = os.path.join(OUTPUT_DIR, 'confusion_matrix.png')
    plt.savefig(cm_path)
    print(f"\n[*] Confusion Matrix plot saved to '{cm_path}'.")
    print("="*60)

if __name__ == "__main__":
    main()
