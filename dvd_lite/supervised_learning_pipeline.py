#!/usr/bin/env python3
"""
=============================================================================
DVD 지도학습 파이프라인 - 단계별 학습 데이터 생성 및 모델 훈련
=============================================================================
파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/supervised_learning_pipeline.py
목적: 공격 패턴 학습, 탐지 모델 훈련, MTD 효과성 예측을 위한 종합 시스템
작성자: MTD Testbed Team
=============================================================================
"""

#!/usr/bin/env python3
"""
DVD MTD 테스트베드용 지도학습 파이프라인
드론 보안 공격 탐지 및 분류를 위한 머신러닝 시스템

주요 기능:
- 공격 데이터 수집 및 전처리
- 다양한 ML 모델 훈련 (분류, 회귀, 클러스터링)
- 실시간 공격 탐지 및 분류
- CTI 연동 및 IOC 추출
- 증강학습 및 강화학습 지원
"""

import os
import sys
import json
import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
import pickle
import joblib
from collections import defaultdict, deque
import warnings
warnings.filterwarnings('ignore')

# 기계학습 라이브러리
try:
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.neural_network import MLPClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn이 설치되지 않음. 기본 분류기 사용")

# 딥러닝 라이브러리 (선택적)
try:
    import tensorflow as tf
    from tensorflow import keras
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LearningTask(Enum):
    """학습 작업 유형"""
    DETECTION = "detection"          # 이진 분류: 정상/공격
    CLASSIFICATION = "classification" # 다중 분류: 공격 유형별
    REGRESSION = "regression"        # 회귀: 위험도 점수
    CLUSTERING = "clustering"        # 클러스터링: 패턴 발견
    ANOMALY = "anomaly"             # 이상 탐지

class ModelType(Enum):
    """모델 유형"""
    RANDOM_FOREST = "random_forest"
    LOGISTIC_REGRESSION = "logistic_regression"
    SVM = "svm"
    NEURAL_NETWORK = "neural_network"
    DEEP_LEARNING = "deep_learning"
    ISOLATION_FOREST = "isolation_forest"
    DBSCAN = "dbscan"
    KMEANS = "kmeans"

@dataclass
class TrainingConfig:
    """훈련 설정"""
    task_type: LearningTask = LearningTask.DETECTION
    model_type: ModelType = ModelType.RANDOM_FOREST
    test_size: float = 0.2
    random_state: int = 42
    cross_validation: bool = True
    cv_folds: int = 5
    hyperparameter_tuning: bool = False
    feature_selection: bool = True
    data_augmentation: bool = False
    save_model: bool = True

@dataclass
class FeatureConfig:
    """특성 설정"""
    network_features: bool = True
    temporal_features: bool = True
    statistical_features: bool = True
    mavlink_features: bool = True
    behavioral_features: bool = True
    frequency_features: bool = False
    
class SupervisedLearningPipeline:
    """지도학습 파이프라인"""
    
    def __init__(self, config: TrainingConfig = None):
        """초기화"""
        self.config = config or TrainingConfig()
        self.feature_config = FeatureConfig()
        
        # 모델 및 상태
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.label_encoder = LabelEncoder() if SKLEARN_AVAILABLE else None
        self.is_trained = False
        self.feature_columns = []
        self.feature_importance = {}
        
        # 훈련 결과
        self.training_history = {}
        self.evaluation_metrics = {}
        self.predictions = {}
        
        # 디렉토리 설정
        self.base_dir = Path("/home/kali/MTD/MTD_full_testbed/dvd_lite")
        self.data_dir = self.base_dir / "data" / "supervised_learning"
        self.models_dir = self.base_dir / "models"
        self.results_dir = self.base_dir / "results"
        self.logs_dir = self.base_dir / "logs"
        
        # 디렉토리 생성
        for dir_path in [self.data_dir, self.models_dir, self.results_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 실시간 처리용 버퍼
        self.data_buffer = deque(maxlen=1000)
        self.prediction_buffer = deque(maxlen=100)
        
        logger.info(f"SupervisedLearningPipeline 초기화 완료 - 작업: {self.config.task_type.value}")

    def load_data(self, data_path: Optional[str] = None) -> pd.DataFrame:
        """데이터 로드"""
        try:
            if data_path and Path(data_path).exists():
                logger.info(f"외부 데이터 로드: {data_path}")
                if data_path.endswith('.csv'):
                    df = pd.read_csv(data_path)
                elif data_path.endswith('.json'):
                    df = pd.read_json(data_path)
                elif data_path.endswith('.jsonl'):
                    df = pd.read_json(data_path, lines=True)
                else:
                    raise ValueError(f"지원되지 않는 파일 형식: {data_path}")
            else:
                # 기본 데이터 디렉토리에서 로드
                data_files = list(self.data_dir.glob("*.json")) + list(self.data_dir.glob("*.csv"))
                if data_files:
                    logger.info(f"기본 데이터 디렉토리에서 로드: {len(data_files)}개 파일")
                    dfs = []
                    for file_path in data_files:
                        if file_path.suffix == '.csv':
                            dfs.append(pd.read_csv(file_path))
                        elif file_path.suffix == '.json':
                            dfs.append(pd.read_json(file_path))
                    
                    if dfs:
                        df = pd.concat(dfs, ignore_index=True)
                    else:
                        df = self._generate_simulation_data()
                else:
                    logger.info("기존 데이터가 없어 시뮬레이션 데이터 생성")
                    df = self._generate_simulation_data()
            
            logger.info(f"데이터 로드 완료: {len(df)} 샘플, {len(df.columns)} 특성")
            return df
            
        except Exception as e:
            logger.error(f"데이터 로드 오류: {e}")
            logger.info("시뮬레이션 데이터로 대체")
            return self._generate_simulation_data()

    def _generate_simulation_data(self) -> pd.DataFrame:
        """시뮬레이션 데이터 생성"""
        logger.info("고품질 시뮬레이션 데이터 생성 중...")
        
        np.random.seed(self.config.random_state)
        n_samples = 5000
        
        data = []
        
        # 정상 트래픽 (70%)
        normal_count = int(n_samples * 0.7)
        for _ in range(normal_count):
            data.append(self._generate_normal_sample())
        
        # 공격 트래픽 (30%) - 다양한 공격 유형
        attack_types = ['reconnaissance', 'protocol_tampering', 'dos_attack', 'injection', 'data_exfiltration']
        attack_count = n_samples - normal_count
        
        for i in range(attack_count):
            attack_type = attack_types[i % len(attack_types)]
            sample = self._generate_attack_sample(attack_type)
            sample['attack_type'] = attack_type
            data.append(sample)
        
        df = pd.DataFrame(data)
        
        # 라벨 생성
        if self.config.task_type == LearningTask.DETECTION:
            df['label'] = (df.get('attack_type', 'normal') != 'normal').astype(int)
        elif self.config.task_type == LearningTask.CLASSIFICATION:
            df['label'] = df.get('attack_type', 'normal')
        
        logger.info(f"시뮬레이션 데이터 생성 완료: {len(df)} 샘플")
        return df

    def _generate_normal_sample(self) -> Dict[str, float]:
        """정상 트래픽 샘플 생성"""
        return {
            # 네트워크 특성
            'packet_rate': np.random.normal(50, 10),
            'byte_rate': np.random.normal(2048, 500),
            'connection_count': np.random.randint(1, 10),
            'unique_ips': np.random.randint(1, 5),
            
            # MAVLink 특성
            'mavlink_msg_rate': np.random.normal(10, 2),
            'mavlink_msg_types': np.random.randint(5, 15),
            'heartbeat_interval': np.random.normal(1.0, 0.1),
            
            # 시스템 특성
            'cpu_usage': np.random.normal(30, 10),
            'memory_usage': np.random.normal(40, 15),
            'disk_io': np.random.normal(100, 30),
            
            # 통계적 특성
            'error_rate': np.random.uniform(0, 0.05),
            'response_time': np.random.normal(100, 20),
            'jitter': np.random.normal(5, 2),
            
            # 시간적 특성
            'hour_of_day': np.random.randint(0, 24),
            'day_of_week': np.random.randint(0, 7),
            'session_duration': np.random.normal(300, 100),
        }

    def _generate_attack_sample(self, attack_type: str) -> Dict[str, float]:
        """공격 트래픽 샘플 생성"""
        base_sample = self._generate_normal_sample()
        
        if attack_type == 'reconnaissance':
            base_sample.update({
                'packet_rate': np.random.normal(200, 50),
                'connection_count': np.random.randint(50, 200),
                'unique_ips': np.random.randint(1, 3),
                'error_rate': np.random.uniform(0.1, 0.3),
                'mavlink_msg_types': np.random.randint(20, 50),
            })
        elif attack_type == 'protocol_tampering':
            base_sample.update({
                'mavlink_msg_rate': np.random.normal(25, 10),
                'heartbeat_interval': np.random.normal(0.5, 0.2),
                'error_rate': np.random.uniform(0.2, 0.5),
                'jitter': np.random.normal(20, 10),
            })
        elif attack_type == 'dos_attack':
            base_sample.update({
                'packet_rate': np.random.normal(1000, 200),
                'connection_count': np.random.randint(500, 2000),
                'cpu_usage': np.random.normal(80, 10),
                'memory_usage': np.random.normal(85, 10),
                'error_rate': np.random.uniform(0.5, 0.9),
            })
        elif attack_type == 'injection':
            base_sample.update({
                'mavlink_msg_rate': np.random.normal(50, 15),
                'byte_rate': np.random.normal(4096, 1000),
                'error_rate': np.random.uniform(0.1, 0.4),
                'response_time': np.random.normal(200, 50),
            })
        elif attack_type == 'data_exfiltration':
            base_sample.update({
                'byte_rate': np.random.normal(8192, 2000),
                'session_duration': np.random.normal(600, 200),
                'connection_count': np.random.randint(1, 5),
                'cpu_usage': np.random.normal(50, 15),
            })
        
        return base_sample

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """특성 엔지니어링"""
        logger.info("특성 엔지니어링 시작...")
        
        if self.config.task_type == LearningTask.DETECTION:
            return self._engineer_attack_detection_features(df)
        elif self.config.task_type == LearningTask.CLASSIFICATION:
            return self._engineer_attack_classification_features(df)
        else:
            return self._engineer_basic_features(df)

    def _engineer_attack_detection_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """공격 탐지를 위한 특성 생성"""
        logger.info("공격 탐지용 특성 엔지니어링...")
        
        # 기본 특성 복사
        engineered_df = df.copy()
        
        # 네트워크 기반 특성
        if self.feature_config.network_features:
            engineered_df['bytes_per_packet'] = engineered_df['byte_rate'] / (engineered_df['packet_rate'] + 1)
            engineered_df['packets_per_connection'] = engineered_df['packet_rate'] / (engineered_df['connection_count'] + 1)
            engineered_df['connection_density'] = engineered_df['connection_count'] / (engineered_df['unique_ips'] + 1)
        
        # 시간적 특성
        if self.feature_config.temporal_features:
            engineered_df['is_weekend'] = (engineered_df['day_of_week'] >= 5).astype(int)
            engineered_df['is_night'] = ((engineered_df['hour_of_day'] < 6) | (engineered_df['hour_of_day'] > 22)).astype(int)
            engineered_df['session_rate'] = engineered_df['packet_rate'] / (engineered_df['session_duration'] + 1)
        
        # 통계적 특성
        if self.feature_config.statistical_features:
            # 롤링 통계 (가상의 시계열 처리)
            for col in ['packet_rate', 'byte_rate', 'cpu_usage']:
                if col in engineered_df.columns:
                    engineered_df[f'{col}_zscore'] = (engineered_df[col] - engineered_df[col].mean()) / (engineered_df[col].std() + 1e-6)
        
        # MAVLink 특성
        if self.feature_config.mavlink_features:
            engineered_df['mavlink_complexity'] = engineered_df['mavlink_msg_types'] / (engineered_df['mavlink_msg_rate'] + 1)
            engineered_df['heartbeat_anomaly'] = (engineered_df['heartbeat_interval'] - 1.0).abs()
        
        # 이상 점수 계산
        if self.feature_config.behavioral_features:
            engineered_df['resource_pressure'] = (engineered_df['cpu_usage'] + engineered_df['memory_usage']) / 2
            engineered_df['network_intensity'] = engineered_df['packet_rate'] * engineered_df['byte_rate'] / 1000000
            engineered_df['error_severity'] = engineered_df['error_rate'] * engineered_df['response_time']
        
        logger.info(f"특성 엔지니어링 완료: {len(engineered_df.columns)} 특성")
        return engineered_df

    def _engineer_attack_classification_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """공격 분류를 위한 특성 생성"""
        logger.info("공격 분류용 특성 엔지니어링...")
        
        # 탐지용 특성을 기반으로 시작
        engineered_df = self._engineer_attack_detection_features(df)
        
        # 공격 유형별 특화 특성
        engineered_df['recon_indicator'] = (
            (engineered_df['connection_count'] > engineered_df['connection_count'].quantile(0.8)) &
            (engineered_df['mavlink_msg_types'] > engineered_df['mavlink_msg_types'].quantile(0.7))
        ).astype(int)
        
        engineered_df['dos_indicator'] = (
            (engineered_df['packet_rate'] > engineered_df['packet_rate'].quantile(0.9)) &
            (engineered_df['error_rate'] > 0.5)
        ).astype(int)
        
        engineered_df['injection_indicator'] = (
            (engineered_df['mavlink_msg_rate'] > engineered_df['mavlink_msg_rate'].quantile(0.8)) &
            (engineered_df['heartbeat_anomaly'] > 0.5)
        ).astype(int)
        
        engineered_df['exfiltration_indicator'] = (
            (engineered_df['byte_rate'] > engineered_df['byte_rate'].quantile(0.85)) &
            (engineered_df['session_duration'] > engineered_df['session_duration'].quantile(0.7))
        ).astype(int)
        
        logger.info(f"공격 분류용 특성 엔지니어링 완료: {len(engineered_df.columns)} 특성")
        return engineered_df

    def _engineer_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """기본 특성 엔지니어링"""
        logger.info("기본 특성 엔지니어링...")
        return df.copy()

    def select_features(self, df: pd.DataFrame, target_col: str = 'label') -> Tuple[pd.DataFrame, List[str]]:
        """특성 선택"""
        if not self.config.feature_selection or not SKLEARN_AVAILABLE:
            feature_cols = [col for col in df.columns if col != target_col and col != 'attack_type']
            return df[feature_cols + [target_col]], feature_cols
        
        logger.info("특성 선택 수행...")
        
        # 수치형 특성만 선택
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        feature_cols = [col for col in numeric_cols if col != target_col and col != 'attack_type']
        
        if len(feature_cols) < 5:
            logger.warning("특성이 너무 적어 특성 선택을 건너뜁니다")
            return df[feature_cols + [target_col]], feature_cols
        
        try:
            from sklearn.feature_selection import SelectKBest, f_classif, f_regression
            
            X = df[feature_cols].fillna(0)
            y = df[target_col]
            
            # 작업 유형에 따른 점수 함수 선택
            if self.config.task_type in [LearningTask.DETECTION, LearningTask.CLASSIFICATION]:
                score_func = f_classif
            else:
                score_func = f_regression
            
            # 상위 특성 선택 (최대 20개)
            k = min(20, len(feature_cols))
            selector = SelectKBest(score_func=score_func, k=k)
            X_selected = selector.fit_transform(X, y)
            
            selected_features = [feature_cols[i] for i in selector.get_support(indices=True)]
            
            logger.info(f"특성 선택 완료: {len(selected_features)}개 특성")
            
            result_df = df[selected_features + [target_col]].copy()
            return result_df, selected_features
            
        except Exception as e:
            logger.error(f"특성 선택 오류: {e}")
            return df[feature_cols + [target_col]], feature_cols

    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """데이터 준비 및 전처리"""
        logger.info("데이터 전처리 시작...")
        
        # 특성 엔지니어링
        df_engineered = self.engineer_features(df)
        
        # 특성 선택
        df_selected, feature_cols = self.select_features(df_engineered)
        self.feature_columns = feature_cols
        
        # 결측값 처리
        df_clean = df_selected.fillna(0)
        
        # 특성과 타겟 분리
        X = df_clean[feature_cols].values
        y = df_clean['label'].values
        
        # 라벨 인코딩 (분류 작업의 경우)
        if self.config.task_type == LearningTask.CLASSIFICATION and self.label_encoder:
            y = self.label_encoder.fit_transform(y)
        
        # 특성 정규화
        if self.scaler and X.shape[1] > 0:
            X = self.scaler.fit_transform(X)
        
        logger.info(f"데이터 전처리 완료: {X.shape[0]} 샘플, {X.shape[1]} 특성")
        return X, y, feature_cols

    def create_model(self) -> Any:
        """모델 생성"""
        if not SKLEARN_AVAILABLE:
            return SimpleClassifier()
        
        model_configs = {
            ModelType.RANDOM_FOREST: {
                'class': RandomForestClassifier,
                'params': {
                    'n_estimators': 100,
                    'max_depth': 10,
                    'random_state': self.config.random_state,
                    'n_jobs': -1
                }
            },
            ModelType.LOGISTIC_REGRESSION: {
                'class': LogisticRegression,
                'params': {
                    'random_state': self.config.random_state,
                    'max_iter': 1000
                }
            },
            ModelType.SVM: {
                'class': SVC,
                'params': {
                    'random_state': self.config.random_state,
                    'probability': True
                }
            },
            ModelType.NEURAL_NETWORK: {
                'class': MLPClassifier,
                'params': {
                    'hidden_layer_sizes': (100, 50),
                    'random_state': self.config.random_state,
                    'max_iter': 500
                }
            },
            ModelType.ISOLATION_FOREST: {
                'class': IsolationForest,
                'params': {
                    'contamination': 0.1,
                    'random_state': self.config.random_state
                }
            }
        }
        
        config = model_configs.get(self.config.model_type)
        if config:
            return config['class'](**config['params'])
        else:
            # 기본값: Random Forest
            return RandomForestClassifier(
                n_estimators=100,
                random_state=self.config.random_state,
                n_jobs=-1
            )

    def train_model(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """모델 훈련"""
        logger.info(f"모델 훈련 시작: {self.config.model_type.value}")
        
        try:
            # 모델 생성
            self.model = self.create_model()
            
            # 데이터 분할
            if len(X) > 10:  # 충분한 데이터가 있는 경우만 분할
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, 
                    test_size=self.config.test_size, 
                    random_state=self.config.random_state,
                    stratify=y if len(np.unique(y)) > 1 else None
                )
            else:
                X_train, X_test, y_train, y_test = X, X, y, y
            
            # 하이퍼파라미터 튜닝
            if self.config.hyperparameter_tuning and SKLEARN_AVAILABLE:
                self.model = self._tune_hyperparameters(self.model, X_train, y_train)
            
            # 모델 훈련
            if hasattr(self.model, 'fit'):
                self.model.fit(X_train, y_train)
            else:
                raise ValueError("모델에 fit 메서드가 없습니다")
            
            self.is_trained = True
            
            # 평가
            train_score = self.model.score(X_train, y_train) if hasattr(self.model, 'score') else 0
            test_score = self.model.score(X_test, y_test) if hasattr(self.model, 'score') else 0
            
            # 교차 검증
            cv_scores = []
            if self.config.cross_validation and SKLEARN_AVAILABLE and len(X_train) > 10:
                try:
                    cv_scores = cross_val_score(self.model, X_train, y_train, cv=self.config.cv_folds)
                except Exception as e:
                    logger.warning(f"교차 검증 실패: {e}")
            
            # 특성 중요도
            if hasattr(self.model, 'feature_importances_'):
                self.feature_importance = dict(zip(
                    self.feature_columns,
                    self.model.feature_importances_
                ))
            
            # 훈련 기록
            self.training_history = {
                'train_score': train_score,
                'test_score': test_score,
                'cv_scores': cv_scores.tolist() if len(cv_scores) > 0 else [],
                'cv_mean': np.mean(cv_scores) if len(cv_scores) > 0 else 0,
                'cv_std': np.std(cv_scores) if len(cv_scores) > 0 else 0,
                'feature_count': len(self.feature_columns),
                'training_samples': len(X_train)
            }
            
            logger.info(f"모델 훈련 완료 - 훈련 점수: {train_score:.3f}, 테스트 점수: {test_score:.3f}")
            
            return self.training_history
            
        except Exception as e:
            logger.error(f"모델 훈련 오류: {e}")
            raise

    def _tune_hyperparameters(self, model, X_train, y_train):
        """하이퍼파라미터 튜닝"""
        logger.info("하이퍼파라미터 튜닝 시작...")
        
        param_grids = {
            'RandomForestClassifier': {
                'n_estimators': [50, 100, 200],
                'max_depth': [5, 10, 15, None],
                'min_samples_split': [2, 5, 10]
            },
            'LogisticRegression': {
                'C': [0.1, 1.0, 10.0],
                'solver': ['liblinear', 'lbfgs']
            },
            'SVC': {
                'C': [0.1, 1.0, 10.0],
                'kernel': ['rbf', 'linear']
            }
        }
        
        model_name = type(model).__name__
        param_grid = param_grids.get(model_name, {})
        
        if param_grid and len(X_train) > 50:  # 충분한 데이터가 있을 때만
            try:
                grid_search = GridSearchCV(
                    model, param_grid, 
                    cv=3, scoring='accuracy', 
                    n_jobs=-1
                )
                grid_search.fit(X_train, y_train)
                logger.info(f"최적 파라미터: {grid_search.best_params_}")
                return grid_search.best_estimator_
            except Exception as e:
                logger.warning(f"하이퍼파라미터 튜닝 실패: {e}")
        
        return model

    def evaluate_model(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """모델 평가"""
        if not self.is_trained:
            raise ValueError("모델이 훈련되지 않았습니다")
        
        logger.info("모델 평가 시작...")
        
        try:
            # 예측
            predictions = self.model.predict(X)
            
            # 확률 예측 (가능한 경우)
            probabilities = None
            if hasattr(self.model, 'predict_proba'):
                try:
                    probabilities = self.model.predict_proba(X)
                except:
                    pass
            
            # 평가 메트릭 계산
            metrics = {}
            
            if SKLEARN_AVAILABLE:
                metrics['accuracy'] = accuracy_score(y, predictions)
                
                if self.config.task_type in [LearningTask.DETECTION, LearningTask.CLASSIFICATION]:
                    # 분류 메트릭
                    metrics['classification_report'] = classification_report(
                        y, predictions, output_dict=True, zero_division=0
                    )
                    metrics['confusion_matrix'] = confusion_matrix(y, predictions).tolist()
            else:
                # 간단한 정확도 계산
                metrics['accuracy'] = np.mean(predictions == y)
            
            # 예측 저장
            self.predictions = {
                'predictions': predictions.tolist(),
                'probabilities': probabilities.tolist() if probabilities is not None else None,
                'true_labels': y.tolist()
            }
            
            self.evaluation_metrics = metrics
            
            logger.info(f"모델 평가 완료 - 정확도: {metrics.get('accuracy', 0):.3f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"모델 평가 오류: {e}")
            raise

    def save_model(self, model_path: Optional[str] = None) -> str:
        """모델 저장"""
        if not self.is_trained:
            raise ValueError("저장할 훈련된 모델이 없습니다")
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if model_path is None:
                model_path = self.models_dir / f"model_{self.config.task_type.value}_{timestamp}.pkl"
            
            # 모델과 관련 객체들을 함께 저장
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'label_encoder': self.label_encoder,
                'feature_columns': self.feature_columns,
                'config': self.config,
                'feature_importance': self.feature_importance,
                'training_history': self.training_history
            }
            
            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"모델 저장 완료: {model_path}")
            return str(model_path)
            
        except Exception as e:
            logger.error(f"모델 저장 오류: {e}")
            raise

    def load_model(self, model_path: str) -> bool:
        """모델 로드"""
        try:
            if not Path(model_path).exists():
                logger.error(f"모델 파일이 존재하지 않습니다: {model_path}")
                return False
            
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data.get('scaler')
            self.label_encoder = model_data.get('label_encoder')
            self.feature_columns = model_data.get('feature_columns', [])
            self.config = model_data.get('config', self.config)
            self.feature_importance = model_data.get('feature_importance', {})
            self.training_history = model_data.get('training_history', {})
            
            self.is_trained = True
            
            logger.info(f"모델 로드 완료: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"모델 로드 오류: {e}")
            return False

    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> Dict[str, Any]:
        """예측 수행"""
        if not self.is_trained:
            raise ValueError("훈련된 모델이 없습니다")
        
        try:
            # 입력 데이터 전처리
            if isinstance(X, pd.DataFrame):
                X_processed = X[self.feature_columns].fillna(0).values
            else:
                X_processed = X
            
            # 정규화
            if self.scaler:
                X_processed = self.scaler.transform(X_processed)
            
            # 예측
            predictions = self.model.predict(X_processed)
            
            # 확률 예측
            probabilities = None
            if hasattr(self.model, 'predict_proba'):
                try:
                    probabilities = self.model.predict_proba(X_processed)
                except:
                    pass
            
            # 라벨 디코딩
            if self.config.task_type == LearningTask.CLASSIFICATION and self.label_encoder:
                predictions = self.label_encoder.inverse_transform(predictions)
            
            result = {
                'predictions': predictions.tolist(),
                'probabilities': probabilities.tolist() if probabilities is not None else None,
                'feature_importance': self.feature_importance
            }
            
            return result
            
        except Exception as e:
            logger.error(f"예측 오류: {e}")
            raise

    def save_results(self, additional_data: Optional[Dict] = None) -> str:
        """결과 저장"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = self.results_dir / f"pipeline_results_{timestamp}.json"
            
            results = {
                'timestamp': timestamp,
                'config': asdict(self.config),
                'training_history': self.training_history,
                'evaluation_metrics': self.evaluation_metrics,
                'feature_importance': self.feature_importance,
                'feature_columns': self.feature_columns,
                'predictions': self.predictions
            }
            
            if additional_data:
                results.update(additional_data)
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"결과 저장 완료: {result_file}")
            return str(result_file)
            
        except Exception as e:
            logger.error(f"결과 저장 오류: {e}")
            raise

    async def run_pipeline(self, data_path: Optional[str] = None, save_model: bool = True) -> Dict[str, Any]:
        """파이프라인 실행"""
        try:
            logger.info("=== 지도학습 파이프라인 실행 시작 ===")
            
            # 1. 데이터 로드
            logger.info("1. 데이터 로드")
            df = self.load_data(data_path)
            
            # 2. 데이터 전처리
            logger.info("2. 데이터 전처리")
            X, y, feature_cols = self.prepare_data(df)
            
            if len(X) == 0:
                raise ValueError("처리할 데이터가 없습니다")
            
            # 3. 모델 훈련
            logger.info("3. 모델 훈련")
            training_results = self.train_model(X, y)
            
            # 4. 모델 평가
            logger.info("4. 모델 평가")
            evaluation_results = self.evaluate_model(X, y)
            
            # 5. 모델 저장
            if save_model and self.config.save_model:
                logger.info("5. 모델 저장")
                model_path = self.save_model()
            else:
                model_path = None
            
            # 6. 결과 저장
            logger.info("6. 결과 저장")
            additional_data = {
                'model_path': model_path,
                'data_shape': X.shape,
                'unique_labels': np.unique(y).tolist()
            }
            result_path = self.save_results(additional_data)
            
            # 최종 결과
            pipeline_results = {
                'success': True,
                'training_results': training_results,
                'evaluation_results': evaluation_results,
                'model_path': model_path,
                'result_path': result_path,
                'data_info': {
                    'samples': len(X),
                    'features': len(feature_cols),
                    'classes': len(np.unique(y))
                }
            }
            
            logger.info("=== 지도학습 파이프라인 실행 완료 ===")
            logger.info(f"정확도: {evaluation_results.get('accuracy', 0):.3f}")
            logger.info(f"특성 개수: {len(feature_cols)}")
            logger.info(f"샘플 개수: {len(X)}")
            
            return pipeline_results
            
        except Exception as e:
            logger.error(f"파이프라인 실행 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'training_results': {},
                'evaluation_results': {}
            }

class SimpleClassifier:
    """간단한 임계값 기반 분류기 (scikit-learn 대안)"""
    
    def __init__(self):
        self.thresholds = {}
        self.is_fitted = False
        self.classes_ = None
    
    def fit(self, X, y):
        """임계값 학습"""
        try:
            self.classes_ = np.unique(y)
            normal_mask = (y == 0) if 0 in self.classes_ else (y == self.classes_[0])
            normal_X = X[normal_mask]
            
            if len(normal_X) == 0:
                # 정상 데이터가 없는 경우 전체 평균 사용
                normal_X = X
            
            self.thresholds = {}
            for i in range(X.shape[1]):
                normal_values = normal_X[:, i]
                mean_val = np.mean(normal_values)
                std_val = np.std(normal_values)
                # 평균 + 2*표준편차를 임계값으로 설정
                self.thresholds[i] = mean_val + 2 * std_val
            
            self.is_fitted = True
            
        except Exception as e:
            logger.error(f"SimpleClassifier 훈련 오류: {e}")
            raise
    
    def predict(self, X):
        """예측"""
        if not self.is_fitted:
            raise ValueError("모델이 훈련되지 않았습니다")
        
        predictions = []
        for sample in X:
            anomaly_score = 0
            for i, value in enumerate(sample):
                if i in self.thresholds and value > self.thresholds[i]:
                    anomaly_score += 1
            
            # 임계값을 초과한 특성이 2개 이상이면 공격으로 분류
            pred = 1 if anomaly_score >= 2 else 0
            predictions.append(pred)
        
        return np.array(predictions)
    
    def score(self, X, y):
        """정확도 계산"""
        predictions = self.predict(X)
        return np.mean(predictions == y)

async def main():
    """메인 실행 함수"""
    logger.info("🤖 DVD MTD 지도학습 파이프라인 시작")
    
    try:
        # 설정
        config = TrainingConfig(
            task_type=LearningTask.DETECTION,
            model_type=ModelType.RANDOM_FOREST,
            cross_validation=True,
            hyperparameter_tuning=False,
            feature_selection=True
        )
        
        # 파이프라인 생성 및 실행
        pipeline = SupervisedLearningPipeline(config)
        results = await pipeline.run_pipeline()
        
        if results['success']:
            logger.info("✅ 파이프라인 실행 성공")
            logger.info(f"📊 정확도: {results['evaluation_results'].get('accuracy', 0):.3f}")
            logger.info(f"📈 데이터 정보: {results['data_info']}")
        else:
            logger.error("❌ 파이프라인 실행 실패")
            logger.error(f"오류: {results.get('error', 'Unknown error')}")
        
        return results
        
    except Exception as e:
        logger.error(f"메인 실행 오류: {e}")
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    asyncio.run(main())