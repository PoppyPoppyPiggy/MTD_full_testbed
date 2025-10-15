#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
from sklearn.model_selection import train_test_split
import argparse
import sys

# --- Path Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'ml', 'output')

def main():
    parser = argparse.ArgumentParser(description="CTI Dataset Manager v4.0")
    parser.add_argument('--input', default=os.path.join(OUTPUT_DIR, 'cti_features_dataset.csv'), help="Input dataset CSV file path")
    parser.add_argument('--test-size', type=float, default=0.2, help="Ratio of the test set (0.0 to 1.0)")
    parser.add_argument('--random-state', type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    print("🚀 [Dataset Manager v4.0] Starting dataset splitting.")
    
    if not os.path.exists(args.input):
        print(f"❌ Error: Input file '{args.input}' not found.")
        print("    Please ensure data_builder.py was run first to generate the feature dataset.")
        sys.exit(1)
        
    # 1. Load Dataset
    df = pd.read_csv(args.input)
    print(f"[*] Original dataset loaded: {df.shape[0]} samples, {df.shape[1]} features")

    X = df.drop('label', axis=1)
    y = df['label']
    
    # Check for stratification requirement
    if y.nunique() < 2:
        print("❌ Error: Only one class exists in the labels. Cannot perform stratified split.")
        print("    The data must contain at least one attack label in addition to 'normal'.")
        sys.exit(1)
    
    # Ensure all features are numeric and fill NaNs (safety check)
    X = X.apply(pd.to_numeric, errors='coerce').fillna(0)
    
    # 2. Train/Test Split (Stratified Sampling)
    print(f"[*] Splitting data into Training ({1-args.test_size:.0%}) and Testing ({args.test_size:.0%}) sets.")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=args.test_size, 
        random_state=args.random_state,
        stratify=y # ⭐️ IMPORTANT: Maintain label distribution for imbalanced data
    )

    # 3. Save Split Data
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    train_path = os.path.join(OUTPUT_DIR, 'train_dataset.csv')
    test_path = os.path.join(OUTPUT_DIR, 'test_dataset.csv')
    
    pd.concat([X_train, y_train], axis=1).to_csv(train_path, index=False)
    pd.concat([X_test, y_test], axis=1).to_csv(test_path, index=False)

    print("\n" + "="*60)
    print("✅ Dataset splitting and saving complete!")
    print(f"  - Training Data: {train_path} ({len(X_train)} samples)")
    print(f"  - Testing Data: {test_path} ({len(X_test)} samples)")
    print("\n[Training Set Label Distribution]")
    print(y_train.value_counts(normalize=True).apply(lambda x: f'{x:.2%}'))
    print("\n[Testing Set Label Distribution]")
    print(y_test.value_counts(normalize=True).apply(lambda x: f'{x:.2%}'))
    print("="*60)

if __name__ == "__main__":
    main()
