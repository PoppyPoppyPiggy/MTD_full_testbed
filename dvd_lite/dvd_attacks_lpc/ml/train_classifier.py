#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI Classifier Trainer v2.0 (Paper-Ready)
==========================================
CTI 공격 분류기 학습 및 평가
"""

import os
import json
import time
import argparse
import sys

import pandas as pd
import numpy as np
import joblib
from tqdm import tqdm

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score
from sklearn.model_selection import RandomizedSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("[!] XGBoost not found.")

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("[!] LightGBM not found.")

ML_DIR = os.path.dirname(os.path.realpath(__file__))
OUTPUT_DIR = os.path.join(ML_DIR, 'output')
MAPPING_FILE = os.path.join(ML_DIR, 'event_mapping.json')
TACTIC_FILE = os.path.join(ML_DIR, 'tactic_mapping.json')


def load_mappings(use_tactic: bool = False):
    id_to_name = {}
    
    if use_tactic and os.path.exists(TACTIC_FILE):
        try:
            with open(TACTIC_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                id_to_name = {int(k): v for k, v in data.get('tactic_names', {}).items()}
        except Exception as e:
            print(f"[!] Tactic mapping 로드 실패: {e}")
    
    if not id_to_name and os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
                name_to_id = json.load(f)
                id_to_name = {v: k for k, v in name_to_id.items()}
        except Exception as e:
            print(f"[!] Event mapping 로드 실패: {e}")
    
    if 0 not in id_to_name:
        id_to_name[0] = 'Normal'
    
    return id_to_name


def plot_confusion_matrix(y_true, y_pred, labels, target_names, filepath, title_suffix="", normalize=False):
    try:
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        
        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            cm = np.nan_to_num(cm)
            fmt = '.2f'
        else:
            fmt = 'd'
        
        cm_df = pd.DataFrame(cm, index=target_names, columns=target_names)

        fig_size = max(10, len(labels) * 0.8)
        plt.figure(figsize=(fig_size + 2, fig_size))
        
        sns.set(font_scale=1.0)
        sns.heatmap(cm_df, annot=True, fmt=fmt, cmap='Blues', linewidths=0.5, 
                    linecolor='gray', annot_kws={"size": 10}, cbar_kws={"shrink": 0.8})
        
        title = f'Confusion Matrix {title_suffix}'
        if normalize:
            title += ' (Normalized)'
        plt.title(title, fontsize=14, fontweight='bold')
        plt.xlabel('Predicted Label', fontsize=12)
        plt.ylabel('True Label', fontsize=12)
        plt.xticks(rotation=45, ha='right', fontsize=9)
        plt.yticks(rotation=0, fontsize=9)
        plt.tight_layout()
        
        plt.savefig(filepath, dpi=200, bbox_inches='tight')
        plt.close()
        print(f"[*] Confusion Matrix 저장: '{filepath}'")
    except Exception as e:
        print(f"❌ CM 저장 실패: {e}", file=sys.stderr)


def plot_feature_importance(model, feature_names, filepath, top_n=30, title_suffix=""):
    if isinstance(model, Pipeline):
        est = model.steps[-1][1]
    else:
        est = model

    if not hasattr(est, 'feature_importances_'):
        return
    
    try:
        importances = est.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        top_n = min(top_n, len(feature_names))
        top_indices = indices[:top_n]

        plt.figure(figsize=(10, max(6, top_n * 0.3)))
        colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(top_indices)))
        
        plt.barh(range(len(top_indices)), importances[top_indices][::-1], 
                 color=colors[::-1], align='center', edgecolor='gray', linewidth=0.5)
        plt.yticks(range(len(top_indices)), [feature_names[i] for i in top_indices[::-1]], fontsize=9)
        
        plt.title(f'Top {top_n} Feature Importances {title_suffix}', fontsize=14, fontweight='bold')
        plt.xlabel('Relative Importance', fontsize=11)
        plt.ylabel('Feature', fontsize=11)
        plt.gca().invert_yaxis()
        plt.tight_layout()
        
        plt.savefig(filepath, dpi=200, bbox_inches='tight')
        plt.close()
        print(f"[*] Feature Importance 저장: '{filepath}'")
    except Exception as e:
        print(f"❌ FI 저장 실패: {e}", file=sys.stderr)


def get_model_pipeline(model_type: str = 'rf', num_classes: int = 2):
    if model_type == 'rf':
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', RandomForestClassifier(class_weight='balanced_subsample', n_jobs=-1, random_state=42))
        ])
        param_dist = {
            'clf__n_estimators': [200, 300, 400],
            'clf__max_depth': [20, 30, None],
            'clf__min_samples_split': [2, 5],
            'clf__min_samples_leaf': [1, 2],
            'clf__max_features': ['sqrt', 'log2']
        }
        
    elif model_type == 'xgb' and HAS_XGBOOST:
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', XGBClassifier(eval_metric='mlogloss', n_jobs=-1, random_state=42,
                                  objective='multi:softprob', num_class=num_classes, use_label_encoder=False))
        ])
        param_dist = {
            'clf__n_estimators': [200, 300],
            'clf__learning_rate': [0.05, 0.1],
            'clf__max_depth': [7, 10, 15],
            'clf__subsample': [0.8, 0.9],
            'clf__colsample_bytree': [0.8, 0.9],
            'clf__min_child_weight': [1, 3]
        }

    elif model_type == 'lgbm' and HAS_LIGHTGBM:
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LGBMClassifier(class_weight='balanced', n_jobs=-1, random_state=42, verbose=-1))
        ])
        param_dist = {
            'clf__n_estimators': [200, 300],
            'clf__learning_rate': [0.05, 0.1],
            'clf__num_leaves': [50, 80, 100],
            'clf__max_depth': [-1, 20, 30]
        }
    else:
        return None, None

    return pipeline, param_dist


def main():
    parser = argparse.ArgumentParser(description="CTI Classifier Trainer v2.0")
    parser.add_argument('--train-data', default=os.path.join(OUTPUT_DIR, 'train_dataset.csv'))
    parser.add_argument('--test-data', default=os.path.join(OUTPUT_DIR, 'test_dataset.csv'))
    parser.add_argument('--model-output', default=os.path.join(OUTPUT_DIR, 'cti_classifier_model.joblib'))
    parser.add_argument('--features-output', default=os.path.join(OUTPUT_DIR, 'training_features.json'))
    parser.add_argument('--report-output', default=os.path.join(OUTPUT_DIR, 'classification_report.json'))
    parser.add_argument('--cm-output', default=os.path.join(OUTPUT_DIR, 'confusion_matrix_best.png'))
    parser.add_argument('--fi-output', default=os.path.join(OUTPUT_DIR, 'feature_importance_best.png'))
    parser.add_argument('--model-type', default='auto', choices=['rf', 'xgb', 'lgbm', 'auto'])
    parser.add_argument('--n-iter', type=int, default=10)
    parser.add_argument('--cv', type=int, default=3)
    parser.add_argument('--tactic-level', action='store_true')
    parser.add_argument('--normalize-cm', action='store_true')
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 [CTI Classifier Trainer v2.0] Paper-Ready")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(args.train_data):
        print(f"❌ 훈련 데이터 없음: {args.train_data}")
        sys.exit(1)

    train_df = pd.read_csv(args.train_data)
    test_df = pd.read_csv(args.test_data)
    
    train_df = train_df.replace([np.inf, -np.inf], np.nan).fillna(0)
    test_df = test_df.replace([np.inf, -np.inf], np.nan).fillna(0)

    X_train = train_df.drop('label', axis=1)
    y_train_raw = train_df['label']
    X_test = test_df.drop('label', axis=1)
    y_test_raw = test_df['label']

    training_features = list(X_train.columns)
    with open(args.features_output, 'w') as f:
        json.dump({'features': training_features, 'count': len(training_features)}, f, indent=4)
    print(f"[*] Features: {len(training_features)}개")

    for col in training_features:
        if col not in X_test.columns:
            X_test[col] = 0
    X_test = X_test[training_features]

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(y_train_raw)
    y_test = label_encoder.transform(y_test_raw)
    
    num_classes = len(label_encoder.classes_)
    print(f"[*] Classes ({num_classes}): {label_encoder.classes_}")

    id_to_name = load_mappings(use_tactic=args.tactic_level)
    target_names = [f"{lbl}: {id_to_name.get(lbl, 'Unknown')}" for lbl in label_encoder.classes_]

    models_to_try = []
    if args.model_type == 'auto':
        models_to_try = ['rf']
        if HAS_XGBOOST: models_to_try.append('xgb')
        if HAS_LIGHTGBM: models_to_try.append('lgbm')
    else:
        models_to_try = [args.model_type]

    best_model = None
    best_score = -1.0
    best_name = ""
    all_results = {}

    for m_name in models_to_try:
        print(f"\n{'='*60}")
        print(f"📊 Training: {m_name.upper()}")
        print(f"{'='*60}")
        
        pipeline, param_dist = get_model_pipeline(m_name, num_classes)
        if pipeline is None:
            continue

        sample_weights = compute_sample_weight('balanced', y_train)

        search = RandomizedSearchCV(
            pipeline, param_distributions=param_dist, n_iter=args.n_iter,
            cv=args.cv, scoring='f1_macro', verbose=1, random_state=42, n_jobs=-1
        )
        
        start_time = time.time()
        try:
            search.fit(X_train, y_train, clf__sample_weight=sample_weights)
        except TypeError:
            search.fit(X_train, y_train)
        elapsed = time.time() - start_time
        
        print(f"   -> Best CV F1: {search.best_score_:.4f} (Time: {elapsed:.1f}s)")

        temp_model = search.best_estimator_
        y_pred = temp_model.predict(X_test)
        
        test_f1 = f1_score(y_test, y_pred, average='macro')
        test_acc = accuracy_score(y_test, y_pred)
        
        print(f"\n[{m_name.upper()} Test]")
        print(f"   Accuracy: {test_acc:.4f}, F1-Macro: {test_f1:.4f}")
        print(classification_report(y_test, y_pred, target_names=target_names, zero_division=0))

        cm_path = os.path.join(OUTPUT_DIR, f'confusion_matrix_{m_name}.png')
        fi_path = os.path.join(OUTPUT_DIR, f'feature_importance_{m_name}.png')
        
        plot_confusion_matrix(y_test, y_pred, range(num_classes), target_names, cm_path,
                              title_suffix=f"({m_name.upper()})", normalize=args.normalize_cm)
        plot_feature_importance(temp_model, training_features, fi_path, title_suffix=f"({m_name.upper()})")

        all_results[m_name] = {
            'cv_score': search.best_score_, 'test_f1': test_f1, 
            'test_accuracy': test_acc, 'params': search.best_params_
        }

        if search.best_score_ > best_score:
            best_score = search.best_score_
            best_model = search.best_estimator_
            best_name = m_name

    print("\n" + "=" * 60)
    print(f"🏆 최종: {best_name.upper()} (CV F1: {best_score:.4f})")
    print("=" * 60)

    final_artifact = {
        'model': best_model, 'encoder': label_encoder, 'mapping': id_to_name,
        'features': training_features, 'model_type': best_name, 'cv_score': best_score
    }
    joblib.dump(final_artifact, args.model_output)
    print(f"[*] Model saved: {args.model_output}")

    y_pred_final = best_model.predict(X_test)
    
    report_dict = classification_report(y_test, y_pred_final, target_names=target_names, zero_division=0, output_dict=True)
    report_dict['all_models'] = all_results
    
    with open(args.report_output, 'w') as f:
        json.dump(report_dict, f, indent=4)

    plot_confusion_matrix(y_test, y_pred_final, range(num_classes), target_names, args.cm_output,
                          title_suffix="(Best)", normalize=args.normalize_cm)
    plot_feature_importance(best_model, training_features, args.fi_output, title_suffix="(Best)")

    cm_norm_path = os.path.join(OUTPUT_DIR, 'confusion_matrix_normalized.png')
    plot_confusion_matrix(y_test, y_pred_final, range(num_classes), target_names, cm_norm_path,
                          title_suffix="(Best)", normalize=True)

    print("\n✅ Complete!")
    print(f"   Accuracy: {accuracy_score(y_test, y_pred_final):.4f}")
    print(f"   F1-Macro: {f1_score(y_test, y_pred_final, average='macro'):.4f}")


if __name__ == "__main__":
    main()
