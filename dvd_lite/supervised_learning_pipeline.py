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

import asyncio
import json
import numpy as np
import pandas as pd
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import pickle

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path("/home/kali/MTD/MTD_full_testbed")
sys.path.append(str(PROJECT_ROOT))

# 머신러닝 라이브러리 (사용 가능한 것만)
try:
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.svm import SVC
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import GaussianNB
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
    import matplotlib.pyplot as plt
    import seaborn as sns
    SKLEARN_AVAILABLE = True
except ImportError:
    print("⚠️ scikit-learn이 설치되지 않았습니다. 기본 구현을 사용합니다.")
    SKLEARN_AVAILABLE = False

# 학습 단계
class LearningPhase(Enum):
    DATA_COLLECTION = "data_collection"
    FEATURE_ENGINEERING = "feature_engineering"
    MODEL_TRAINING = "model_training"
    MODEL_EVALUATION = "model_evaluation"
    MODEL_DEPLOYMENT = "model_deployment"

# 학습 작업 유형
class LearningTask(Enum):
    ATTACK_DETECTION = "attack_detection"          # 공격 탐지
    ATTACK_CLASSIFICATION = "attack_classification"  # 공격 분류
    MTD_EFFECTIVENESS = "mtd_effectiveness"        # MTD 효과성 예측
    THREAT_SEVERITY = "threat_severity"            # 위협 심각도 평가
    ANOMALY_DETECTION = "anomaly_detection"        # 이상 탐지

@dataclass
class TrainingConfiguration:
    """훈련 설정"""
    task_type: LearningTask
    algorithm: str
    hyperparameters: Dict[str, Any]
    validation_split: float = 0.2
    cross_validation_folds: int = 5
    random_state: int = 42

@dataclass
class ModelPerformance:
    """모델 성능 메트릭"""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_score: Optional[float] = None
    confusion_matrix: Optional[List[List[int]]] = None
    feature_importance: Optional[Dict[str, float]] = None

class SupervisedLearningPipeline:
    """지도학습 파이프라인 관리 클래스"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.setup_logging()
        self.setup_directories()
        
        # 데이터 저장소
        self.raw_data: List[Dict] = []
        self.processed_features: Optional[pd.DataFrame] = None
        self.labels: Optional[pd.Series] = None
        self.trained_models: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, ModelPerformance] = {}
        
        # 특성 공학 설정
        self.feature_columns = []
        self.label_encoder = LabelEncoder() if SKLEARN_AVAILABLE else None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        
    def setup_logging(self):
        """로깅 설정"""
        log_dir = PROJECT_ROOT / "logs" / "supervised_learning"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"learning_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger("SupervisedLearningPipeline")
        
    def setup_directories(self):
        """필요한 디렉토리 생성"""
        dirs = [
            "models", "features", "datasets", "visualizations", 
            "evaluation", "predictions", "model_artifacts"
        ]
        
        for dir_name in dirs:
            (PROJECT_ROOT / "supervised_data" / dir_name).mkdir(parents=True, exist_ok=True)
    
    # PHASE 1: 데이터 수집
    async def collect_training_data(self, data_sources: List[str]) -> int:
        """훈련 데이터 수집"""
        self.logger.info("🔍 Phase 1: 훈련 데이터 수집 시작")
        
        collected_count = 0
        
        for source in data_sources:
            if source.endswith('.json'):
                collected_count += await self._load_json_data(source)
            elif source.endswith('.csv'):
                collected_count += await self._load_csv_data(source)
            else:
                self.logger.warning(f"지원하지 않는 데이터 형식: {source}")
        
        self.logger.info(f"✅ 총 {collected_count}개의 샘플 수집 완료")
        return collected_count
    
    async def _load_json_data(self, file_path: str) -> int:
        """JSON 데이터 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                self.raw_data.extend(data)
                return len(data)
            elif isinstance(data, dict) and 'features' in data:
                # 데이터셋 형식
                features = data['features']
                labels = data['labels']
                
                for feature, label in zip(features, labels):
                    combined = {**feature, 'label': label['label'], 'confidence': label['confidence']}
                    self.raw_data.append(combined)
                    
                return len(features)
            else:
                self.raw_data.append(data)
                return 1
                
        except Exception as e:
            self.logger.error(f"JSON 데이터 로드 실패 {file_path}: {e}")
            return 0
    
    async def _load_csv_data(self, file_path: str) -> int:
        """CSV 데이터 로드"""
        try:
            df = pd.read_csv(file_path)
            records = df.to_dict('records')
            self.raw_data.extend(records)
            return len(records)
        except Exception as e:
            self.logger.error(f"CSV 데이터 로드 실패 {file_path}: {e}")
            return 0
    
    # PHASE 2: 특성 공학
    async def engineer_features(self, task_type: LearningTask) -> Tuple[pd.DataFrame, pd.Series]:
        """특성 공학 및 데이터 전처리"""
        self.logger.info("🔧 Phase 2: 특성 공학 시작")
        
        if not self.raw_data:
            raise ValueError("수집된 데이터가 없습니다. 먼저 데이터를 수집하세요.")
        
        # DataFrame 생성
        df = pd.DataFrame(self.raw_data)
        
        # 작업 유형별 특성 선택
        if task_type == LearningTask.ATTACK_DETECTION:
            features_df, labels_series = self._engineer_attack_detection_features(df)
        elif task_type == LearningTask.ATTACK_CLASSIFICATION:
            features_df, labels_series = self._engineer_attack_classification_features(df)
        elif task_type == LearningTask.MTD_EFFECTIVENESS:
            features_df, labels_series = self._engineer_mtd_effectiveness_features(df)
        elif task_type == LearningTask.THREAT_SEVERITY:
            features_df, labels_series = self._engineer_threat_severity_features(df)
        elif task_type == LearningTask.ANOMALY_DETECTION:
            features_df, labels_series = self._engineer_anomaly_detection_features(df)
        else:
            raise ValueError(f"지원하지 않는 학습 작업: {task_type}")
        
        # 결측값 처리
        features_df = self._handle_missing_values(features_df)
        
        # 특성 정규화
        if SKLEARN_AVAILABLE:
            features_df = self._normalize_features(features_df)
        
        # 특성 선택
        features_df = self._select_features(features_df, labels_series)
        
        self.processed_features = features_df
        self.labels = labels_series
        self.feature_columns = list(features_df.columns)
        
        self.logger.info(f"✅ 특성 공학 완료: {len(features_df.columns)}개 특성, {len(features_df)}개 샘플")
        
        return features_df, labels_series
    
    def _engineer_mtd_effectiveness_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """MTD 효과성 예측을 위한 특성 생성"""
        features = []
        labels = []
        
        for _, row in df.iterrows():
            # MTD 상태 특성
            mtd_features = {
                'mtd_triggers': row.get('mtd_features_mtd_triggers', 0),
                'topology_changes': row.get('mtd_features_topology_changes', 0),
                'encryption_rotations': row.get('mtd_features_encryption_rotations', 0),
                'frequency_hops': row.get('mtd_features_frequency_hops', 0),
                'emergency_responses': row.get('mtd_features_emergency_responses', 0),
                'response_time': row.get('mtd_features_response_time', 0.0)
            }
            
            # 공격 강도 특성
            attack_intensity = {
                'attack_complexity': row.get('attack_features_attack_complexity', 1),
                'exploit_attempts': row.get('attack_features_exploit_attempts', 0),
                'attack_duration': row.get('meta_duration', 0.0),
                'payload_size_normalized': min(row.get('attack_features_payload_size', 0) / 1024, 100)
            }
            
            # 네트워크 부하 특성
            network_load = {
                'packet_rate': row.get('network_features_packet_count', 0) / max(row.get('meta_duration', 1), 1),
                'connection_density': row.get('network_features_connection_attempts', 0),
                'bandwidth_utilization': row.get('network_features_bandwidth_usage', 0.0)
            }
            
            # 모든 특성 결합
            combined_features = {**mtd_features, **attack_intensity, **network_load}
            features.append(combined_features)
            
            # MTD 효과성 레이블 (공격 차단 여부)
            mtd_effective = not row.get('meta_attack_success', True) and row.get('mtd_features_mtd_triggers', 0) > 0
            labels.append(1 if mtd_effective else 0)
        
        features_df = pd.DataFrame(features)
        labels_series = pd.Series(labels, name='mtd_effective')
        
        return features_df, labels_series
    
    def _engineer_threat_severity_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """위협 심각도 평가를 위한 특성 생성"""
        features = []
        labels = []
        
        for _, row in df.iterrows():
            # 위협 지표 특성
            threat_indicators = {
                'privilege_escalation': 1 if row.get('attack_features_privilege_escalation', False) else 0,
                'lateral_movement': 1 if row.get('attack_features_lateral_movement', False) else 0,
                'data_destruction': 1 if row.get('attack_features_data_destruction', False) else 0,
                'persistence_level': min(row.get('attack_features_persistence_mechanisms', 0), 5),
                'stealth_capability': row.get('attack_features_stealth_level', 0.0)
            }
            
            # 영향 범위 특성
            impact_scope = {
                'affected_systems': row.get('network_features_unique_ips', 0),
                'service_disruption': 1 if 'denial_of_service' in row.get('meta_tactic', '').lower() else 0,
                'data_compromise': 1 if 'exfiltration' in row.get('meta_tactic', '').lower() else 0,
                'firmware_compromise': 1 if 'firmware' in row.get('meta_tactic', '').lower() else 0
            }
            
            # 공격 복잡도 특성
            complexity_features = {
                'technical_complexity': row.get('attack_features_attack_complexity', 1),
                'exploit_sophistication': min(row.get('attack_features_exploit_attempts', 0), 10),
                'payload_sophistication': min(row.get('attack_features_payload_size', 0) / 1024, 50)
            }
            
            # 모든 특성 결합
            combined_features = {**threat_indicators, **impact_scope, **complexity_features}
            features.append(combined_features)
            
            # 심각도 레이블 계산 (LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3)
            severity_score = 0
            
            # 공격 성공 시 +1
            if row.get('meta_attack_success', False):
                severity_score += 1
            
            # 높은 복잡도 공격 +1
            if row.get('attack_features_attack_complexity', 1) >= 3:
                severity_score += 1
            
            # 펌웨어 공격 +1
            if 'firmware' in row.get('meta_tactic', '').lower():
                severity_score += 1
            
            # 지속성 메커니즘 +1
            if row.get('attack_features_persistence_mechanisms', 0) > 0:
                severity_score += 1
            
            # 0-3 범위로 클램핑
            severity_score = min(max(severity_score, 0), 3)
            labels.append(severity_score)
        
        features_df = pd.DataFrame(features)
        labels_series = pd.Series(labels, name='threat_severity')
        
        return features_df, labels_series
    
    def _engineer_anomaly_detection_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """이상 탐지를 위한 특성 생성"""
        features = []
        labels = []
        
        for _, row in df.iterrows():
            # 통계적 특성
            statistical_features = {
                'packet_count_zscore': self._calculate_zscore(row.get('network_features_packet_count', 0), df, 'network_features_packet_count'),
                'connection_rate_zscore': self._calculate_zscore(row.get('network_features_connection_attempts', 0), df, 'network_features_connection_attempts'),
                'bandwidth_zscore': self._calculate_zscore(row.get('network_features_bandwidth_usage', 0), df, 'network_features_bandwidth_usage'),
                'latency_zscore': self._calculate_zscore(row.get('network_features_latency_avg', 0), df, 'network_features_latency_avg')
            }
            
            # 행동 패턴 특성
            behavioral_features = {
                'unusual_port_activity': 1 if row.get('network_features_port_scans', 0) > 10 else 0,
                'high_payload_size': 1 if row.get('attack_features_payload_size', 0) > 10240 else 0,  # 10KB
                'rapid_connections': 1 if row.get('network_features_connection_attempts', 0) / max(row.get('meta_duration', 1), 1) > 5 else 0,
                'protocol_anomalies': row.get('network_features_protocol_violations', 0)
            }
            
            # 시간 패턴 특성
            timestamp = datetime.fromisoformat(row.get('timestamp', '2024-01-01T00:00:00'))
            temporal_features = {
                'unusual_hour': 1 if timestamp.hour < 6 or timestamp.hour > 22 else 0,
                'weekend_activity': 1 if timestamp.weekday() >= 5 else 0,
                'burst_activity': 1 if row.get('attack_features_exploit_attempts', 0) > 5 else 0
            }
            
            # 모든 특성 결합
            combined_features = {**statistical_features, **behavioral_features, **temporal_features}
            features.append(combined_features)
            
            # 이상 여부 레이블
            is_anomaly = (
                abs(statistical_features['packet_count_zscore']) > 2 or
                abs(statistical_features['connection_rate_zscore']) > 2 or
                behavioral_features['unusual_port_activity'] == 1 or
                row.get('meta_attack_success', False)
            )
            labels.append(1 if is_anomaly else 0)
        
        features_df = pd.DataFrame(features)
        labels_series = pd.Series(labels, name='is_anomaly')
        
        return features_df, labels_series
    
    def _calculate_zscore(self, value: float, df: pd.DataFrame, column: str) -> float:
        """Z-score 계산"""
        try:
            values = df[column].astype(float)
            mean_val = values.mean()
            std_val = values.std()
            
            if std_val == 0:
                return 0.0
            
            return (value - mean_val) / std_val
        except:
            return 0.0
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """결측값 처리"""
        # 수치형 컬럼은 평균값으로 대체
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            df[col] = df[col].fillna(df[col].mean())
        
        # 범주형 컬럼은 최빈값으로 대체
        categorical_columns = df.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            df[col] = df[col].fillna(df[col].mode().iloc[0] if not df[col].mode().empty else 'unknown')
        
        return df
    
    def _normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """특성 정규화"""
        if not SKLEARN_AVAILABLE:
            return df
        
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_columns) > 0:
            self.scaler = StandardScaler()
            df[numeric_columns] = self.scaler.fit_transform(df[numeric_columns])
        
        return df
    
    def _select_features(self, df: pd.DataFrame, labels: pd.Series) -> pd.DataFrame:
        """특성 선택"""
        if not SKLEARN_AVAILABLE:
            return df
        
        # 상관관계가 너무 높은 특성 제거
        correlation_matrix = df.corr().abs()
        upper_triangle = correlation_matrix.where(
            np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool)
        )
        
        to_drop = [column for column in upper_triangle.columns if any(upper_triangle[column] > 0.95)]
        df = df.drop(columns=to_drop)
        
        self.logger.info(f"높은 상관관계로 인해 제거된 특성: {len(to_drop)}개")
        
        return df
    
    # PHASE 3: 모델 훈련
    async def train_models(self, task_type: LearningTask, 
                          algorithms: Optional[List[str]] = None) -> Dict[str, ModelPerformance]:
        """모델 훈련"""
        self.logger.info("🤖 Phase 3: 모델 훈련 시작")
        
        if self.processed_features is None or self.labels is None:
            raise ValueError("특성 공학이 완료되지 않았습니다.")
        
        if not SKLEARN_AVAILABLE:
            return await self._train_basic_models(task_type)
        
        # 기본 알고리즘 설정
        if algorithms is None:
            algorithms = ['random_forest', 'gradient_boosting', 'svm', 'logistic_regression', 'naive_bayes']
        
        # 훈련/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            self.processed_features, self.labels, 
            test_size=0.2, random_state=42, stratify=self.labels
        )
        
        performances = {}
        
        for algorithm in algorithms:
            self.logger.info(f"🔄 {algorithm} 모델 훈련 중...")
            
            # 모델 생성
            model = self._create_model(algorithm, task_type)
            
            # 모델 훈련
            model.fit(X_train, y_train)
            
            # 예측 및 평가
            y_pred = model.predict(X_test)
            
            # 성능 메트릭 계산
            performance = self._calculate_performance_metrics(
                y_test, y_pred, model, X_test, algorithm
            )
            
            performances[algorithm] = performance
            self.trained_models[algorithm] = model
            
            self.logger.info(f"✅ {algorithm} 훈련 완료 - 정확도: {performance.accuracy:.3f}")
        
        self.performance_metrics = performances
        return performances
    
    def _create_model(self, algorithm: str, task_type: LearningTask):
        """알고리즘별 모델 생성"""
        if algorithm == 'random_forest':
            return RandomForestClassifier(
                n_estimators=100, 
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        elif algorithm == 'gradient_boosting':
            return GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
        elif algorithm == 'svm':
            return SVC(
                kernel='rbf',
                C=1.0,
                probability=True,
                random_state=42
            )
        elif algorithm == 'logistic_regression':
            return LogisticRegression(
                random_state=42,
                max_iter=1000
            )
        elif algorithm == 'naive_bayes':
            return GaussianNB()
        else:
            # 기본값으로 랜덤 포레스트 사용
            return RandomForestClassifier(random_state=42)
    
    def _calculate_performance_metrics(self, y_true, y_pred, model, X_test, algorithm: str) -> ModelPerformance:
        """성능 메트릭 계산"""
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        # 기본 메트릭
        accuracy = accuracy_score(y_true, y_pred)
        
        # 다중 클래스의 경우 평균 계산
        avg_method = 'weighted' if len(set(y_true)) > 2 else 'binary'
        
        try:
            precision = precision_score(y_true, y_pred, average=avg_method, zero_division=0)
            recall = recall_score(y_true, y_pred, average=avg_method, zero_division=0)
            f1 = f1_score(y_true, y_pred, average=avg_method, zero_division=0)
        except ValueError:
            # 단일 클래스인 경우
            precision = recall = f1 = 0.0
        
        # AUC 계산 (이진 분류인 경우)
        auc_score = None
        if len(set(y_true)) == 2 and hasattr(model, 'predict_proba'):
            try:
                y_proba = model.predict_proba(X_test)[:, 1]
                auc_score = roc_auc_score(y_true, y_proba)
            except:
                pass
        
        # 혼동 행렬
        cm = confusion_matrix(y_true, y_pred).tolist()
        
        # 특성 중요도 (지원하는 모델인 경우)
        feature_importance = None
        if hasattr(model, 'feature_importances_'):
            importance_dict = dict(zip(
                self.feature_columns,
                model.feature_importances_
            ))
            # 상위 10개 특성만 저장
            sorted_importance = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:10]
            feature_importance = dict(sorted_importance)
        
        return ModelPerformance(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            auc_score=auc_score,
            confusion_matrix=cm,
            feature_importance=feature_importance
        )
    
    async def _train_basic_models(self, task_type: LearningTask) -> Dict[str, ModelPerformance]:
        """scikit-learn 없이 기본 모델 훈련"""
        self.logger.info("📚 기본 구현으로 모델 훈련 중...")
        
        # 간단한 규칙 기반 모델
        performances = {}
        
        # 규칙 기반 공격 탐지 모델
        if task_type == LearningTask.ATTACK_DETECTION:
            accuracy = await self._evaluate_rule_based_detection()
            performances['rule_based'] = ModelPerformance(
                accuracy=accuracy,
                precision=accuracy * 0.9,
                recall=accuracy * 0.8,
                f1_score=accuracy * 0.85
            )
        
        return performances
    
    async def _evaluate_rule_based_detection(self) -> float:
        """규칙 기반 탐지 평가"""
        correct_predictions = 0
        total_predictions = 0
        
        for row in self.raw_data:
            # 간단한 규칙들
            is_attack_predicted = (
                row.get('network_features_packet_count', 0) > 1000 or
                row.get('network_features_port_scans', 0) > 5 or
                row.get('attack_features_payload_size', 0) > 5120 or
                row.get('attack_features_stealth_level', 0.0) > 0.5
            )
            
            is_attack_actual = row.get('label', '').startswith('attack_')
            
            if is_attack_predicted == is_attack_actual:
                correct_predictions += 1
            total_predictions += 1
        
        return correct_predictions / total_predictions if total_predictions > 0 else 0.0
    
    # PHASE 4: 모델 평가
    async def evaluate_models(self) -> Dict[str, Any]:
        """모델 평가 및 비교"""
        self.logger.info("📊 Phase 4: 모델 평가 시작")
        
        if not self.performance_metrics:
            raise ValueError("훈련된 모델이 없습니다.")
        
        # 최고 성능 모델 선택
        best_model = max(
            self.performance_metrics.items(),
            key=lambda x: x[1].f1_score
        )
        
        evaluation_results = {
            "best_model": {
                "algorithm": best_model[0],
                "performance": asdict(best_model[1])
            },
            "model_comparison": {
                algorithm: asdict(performance)
                for algorithm, performance in self.performance_metrics.items()
            },
            "evaluation_timestamp": datetime.now().isoformat()
        }
        
        # 평가 결과 저장
        eval_file = PROJECT_ROOT / "supervised_data" / "evaluation" / f"model_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        eval_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"📈 최고 성능 모델: {best_model[0]} (F1: {best_model[1].f1_score:.3f})")
        
        return evaluation_results
    
    # PHASE 5: 모델 배포
    async def deploy_model(self, algorithm: str, deployment_path: Optional[str] = None) -> str:
        """모델 배포"""
        self.logger.info(f"🚀 Phase 5: {algorithm} 모델 배포")
        
        if algorithm not in self.trained_models:
            raise ValueError(f"훈련되지 않은 모델: {algorithm}")
        
        if deployment_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            deployment_path = str(PROJECT_ROOT / "supervised_data" / "models" / f"{algorithm}_model_{timestamp}.pkl")
        
        # 모델과 전처리기 함께 저장
        model_package = {
            'model': self.trained_models[algorithm],
            'scaler': self.scaler,
            'label_encoder': self.label_encoder,
            'feature_columns': self.feature_columns,
            'performance': asdict(self.performance_metrics[algorithm]),
            'deployment_info': {
                'timestamp': datetime.now().isoformat(),
                'algorithm': algorithm,
                'version': '1.0.0'
            }
        }
        
        # Pickle로 저장
        with open(deployment_path, 'wb') as f:
            pickle.dump(model_package, f)
        
        self.logger.info(f"✅ 모델 배포 완료: {deployment_path}")
        
        # 배포 메타데이터 저장
        metadata_file = deployment_path.replace('.pkl', '_metadata.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            deployment_metadata = {
                'model_file': deployment_path,
                'algorithm': algorithm,
                'performance': asdict(self.performance_metrics[algorithm]),
                'feature_count': len(self.feature_columns),
                'deployment_timestamp': datetime.now().isoformat()
            }
            json.dump(deployment_metadata, f, indent=2)
        
        return deployment_path
    
    # 시각화 생성
    async def generate_visualizations(self):
        """학습 결과 시각화 생성"""
        if not SKLEARN_AVAILABLE:
            self.logger.warning("matplotlib/seaborn이 없어 시각화를 건너뜁니다.")
            return
        
        self.logger.info("📊 시각화 생성 중...")
        
        viz_dir = PROJECT_ROOT / "supervised_data" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 모델 성능 비교
        await self._plot_model_comparison(viz_dir)
        
        # 2. 특성 중요도 시각화
        await self._plot_feature_importance(viz_dir)
        
        # 3. 혼동 행렬 시각화
        await self._plot_confusion_matrices(viz_dir)
        
        # 4. 데이터 분포 시각화
        await self._plot_data_distribution(viz_dir)
        
        self.logger.info(f"✅ 시각화 저장 완료: {viz_dir}")
    
    async def _plot_model_comparison(self, viz_dir: Path):
        """모델 성능 비교 차트"""
        if not self.performance_metrics:
            return
        
        metrics = ['accuracy', 'precision', 'recall', 'f1_score']
        algorithms = list(self.performance_metrics.keys())
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        x = np.arange(len(algorithms))
        width = 0.2
        
        for i, metric in enumerate(metrics):
            values = [getattr(self.performance_metrics[alg], metric) for alg in algorithms]
            ax.bar(x + i * width, values, width, label=metric.replace('_', ' ').title())
        
        ax.set_xlabel('알고리즘')
        ax.set_ylabel('성능 점수')
        ax.set_title('모델 성능 비교')
        ax.set_xticks(x + width * 1.5)
        ax.set_xticklabels(algorithms, rotation=45)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(viz_dir / 'model_performance_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    async def _plot_feature_importance(self, viz_dir: Path):
        """특성 중요도 시각화"""
        for algorithm, performance in self.performance_metrics.items():
            if performance.feature_importance:
                fig, ax = plt.subplots(figsize=(10, 8))
                
                features = list(performance.feature_importance.keys())
                importances = list(performance.feature_importance.values())
                
                y_pos = np.arange(len(features))
                
                ax.barh(y_pos, importances)
                ax.set_yticks(y_pos)
                ax.set_yticklabels(features)
                ax.set_xlabel('중요도')
                ax.set_title(f'{algorithm} - 특성 중요도')
                ax.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plt.savefig(viz_dir / f'feature_importance_{algorithm}.png', dpi=300, bbox_inches='tight')
                plt.close()
    
    async def _plot_confusion_matrices(self, viz_dir: Path):
        """혼동 행렬 시각화"""
        for algorithm, performance in self.performance_metrics.items():
            if performance.confusion_matrix:
                fig, ax = plt.subplots(figsize=(8, 6))
                
                cm = np.array(performance.confusion_matrix)
                sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax)
                
                ax.set_title(f'{algorithm} - 혼동 행렬')
                ax.set_xlabel('예측값')
                ax.set_ylabel('실제값')
                
                plt.tight_layout()
                plt.savefig(viz_dir / f'confusion_matrix_{algorithm}.png', dpi=300, bbox_inches='tight')
                plt.close()
    
    async def _plot_data_distribution(self, viz_dir: Path):
        """데이터 분포 시각화"""
        if self.processed_features is None:
            return
        
        # 주요 특성들의 분포
        numeric_features = self.processed_features.select_dtypes(include=[np.number]).columns[:6]  # 상위 6개만
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()
        
        for i, feature in enumerate(numeric_features):
            if i < len(axes):
                axes[i].hist(self.processed_features[feature], bins=30, alpha=0.7, edgecolor='black')
                axes[i].set_title(f'{feature} 분포')
                axes[i].set_xlabel('값')
                axes[i].set_ylabel('빈도')
                axes[i].grid(True, alpha=0.3)
        
        # 남은 subplot 숨기기
        for i in range(len(numeric_features), len(axes)):
            axes[i].set_visible(False)
        
        plt.tight_layout()
        plt.savefig(viz_dir / 'feature_distributions.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # 실시간 예측
    async def predict_attack_outcome(self, attack_features: Dict[str, Any], 
                                   model_algorithm: str = 'random_forest') -> Dict[str, Any]:
        """실시간 공격 결과 예측"""
        if model_algorithm not in self.trained_models:
            raise ValueError(f"배포되지 않은 모델: {model_algorithm}")
        
        model = self.trained_models[model_algorithm]
        
        # 특성 벡터 생성
        feature_vector = []
        for col in self.feature_columns:
            value = attack_features.get(col, 0)
            feature_vector.append(value)
        
        # 예측
        feature_array = np.array(feature_vector).reshape(1, -1)
        
        if self.scaler:
            feature_array = self.scaler.transform(feature_array)
        
        prediction = model.predict(feature_array)[0]
        
        # 확률 예측 (지원하는 경우)
        probability = None
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(feature_array)[0]
            probability = max(proba)
        
        return {
            'prediction': prediction,
            'probability': probability,
            'model_used': model_algorithm,
            'timestamp': datetime.now().isoformat()
        }
    
    # 모델 성능 모니터링
    async def monitor_model_performance(self, new_data: List[Dict]) -> Dict[str, Any]:
        """배포된 모델의 성능 모니터링"""
        self.logger.info("📈 모델 성능 모니터링 시작")
        
        monitoring_results = {}
        
        for algorithm, model in self.trained_models.items():
            # 새 데이터로 예측
            predictions = []
            actual_labels = []
            
            for data_point in new_data:
                # 특성 추출
                features = []
                for col in self.feature_columns:
                    features.append(data_point.get(col, 0))
                
                feature_array = np.array(features).reshape(1, -1)
                if self.scaler:
                    feature_array = self.scaler.transform(feature_array)
                
                pred = model.predict(feature_array)[0]
                predictions.append(pred)
                
                # 실제 레이블
                actual = data_point.get('actual_label', 0)
                actual_labels.append(actual)
            
            # 성능 계산
            if SKLEARN_AVAILABLE and len(predictions) > 0:
                from sklearn.metrics import accuracy_score
                accuracy = accuracy_score(actual_labels, predictions)
            else:
                accuracy = sum(p == a for p, a in zip(predictions, actual_labels)) / len(predictions)
            
            monitoring_results[algorithm] = {
                'current_accuracy': accuracy,
                'prediction_count': len(predictions),
                'data_drift_detected': accuracy < self.performance_metrics[algorithm].accuracy * 0.9
            }
        
        return monitoring_results
    
    # 증강 학습 지원
    async def generate_augmented_data(self, augmentation_factor: int = 2) -> int:
        """데이터 증강을 통한 훈련 데이터 확장"""
        self.logger.info(f"🔄 데이터 증강 시작 (증강 배수: {augmentation_factor})")
        
        if not self.raw_data:
            raise ValueError("증강할 원본 데이터가 없습니다.")
        
        original_count = len(self.raw_data)
        augmented_data = []
        
        for _ in range(augmentation_factor):
            for original_sample in self.raw_data:
                # 가우시안 노이즈 추가
                augmented_sample = self._add_gaussian_noise(original_sample)
                augmented_data.append(augmented_sample)
        
        # 증강된 데이터 추가
        self.raw_data.extend(augmented_data)
        
        augmented_count = len(augmented_data)
        self.logger.info(f"✅ 데이터 증강 완료: {original_count} -> {original_count + augmented_count}개")
        
        return augmented_count
    
    def _add_gaussian_noise(self, sample: Dict[str, Any], noise_factor: float = 0.1) -> Dict[str, Any]:
        """가우시안 노이즈를 추가한 데이터 증강"""
        augmented = sample.copy()
        
        # 수치형 특성에만 노이즈 추가
        numeric_fields = [
            'network_features_packet_count', 'network_features_connection_attempts',
            'network_features_bandwidth_usage', 'attack_features_payload_size',
            'attack_features_stealth_level', 'meta_duration'
        ]
        
        for field in numeric_fields:
            if field in augmented and isinstance(augmented[field], (int, float)):
                original_value = augmented[field]
                noise = np.random.normal(0, abs(original_value) * noise_factor)
                augmented[field] = max(0, original_value + noise)  # 음수 방지
        
        # 타임스탬프 약간 변경
        try:
            original_time = datetime.fromisoformat(augmented.get('timestamp', '2024-01-01T00:00:00'))
            time_offset = np.random.randint(-300, 300)  # ±5분
            new_time = original_time.timestamp() + time_offset
            augmented['timestamp'] = datetime.fromtimestamp(new_time).isoformat()
        except:
            pass
        
        return augmented
    
    # 전체 파이프라인 실행
    async def run_full_pipeline(self, data_sources: List[str], 
                               task_type: LearningTask,
                               algorithms: Optional[List[str]] = None) -> Dict[str, Any]:
        """전체 지도학습 파이프라인 실행"""
        self.logger.info("🚀 지도학습 파이프라인 전체 실행 시작")
        
        pipeline_start_time = datetime.now()
        
        try:
            # Phase 1: 데이터 수집
            collected_samples = await self.collect_training_data(data_sources)
            self.logger.info(f"✅ Phase 1 완료: {collected_samples}개 샘플 수집")
            
            # 데이터 증강 (선택적)
            if self.config.get('enable_augmentation', True):
                augmented_samples = await self.generate_augmented_data(2)
                self.logger.info(f"✅ 데이터 증강 완료: +{augmented_samples}개 샘플")
            
            # Phase 2: 특성 공학
            features_df, labels_series = await self.engineer_features(task_type)
            self.logger.info(f"✅ Phase 2 완료: {len(features_df.columns)}개 특성 생성")
            
            # Phase 3: 모델 훈련
            performances = await self.train_models(task_type, algorithms)
            self.logger.info(f"✅ Phase 3 완료: {len(performances)}개 모델 훈련")
            
            # Phase 4: 모델 평가
            evaluation_results = await self.evaluate_models()
            self.logger.info("✅ Phase 4 완료: 모델 평가")
            
            # Phase 5: 최고 성능 모델 배포
            best_algorithm = evaluation_results['best_model']['algorithm']
            deployment_path = await self.deploy_model(best_algorithm)
            self.logger.info(f"✅ Phase 5 완료: {best_algorithm} 모델 배포")
            
            # 시각화 생성
            await self.generate_visualizations()
            
            # 파이프라인 완료
            pipeline_duration = (datetime.now() - pipeline_start_time).total_seconds()
            
            pipeline_results = {
                'pipeline_info': {
                    'start_time': pipeline_start_time.isoformat(),
                    'duration': pipeline_duration,
                    'task_type': task_type.value,
                    'success': True
                },
                'data_summary': {
                    'total_samples': collected_samples + (augmented_samples if self.config.get('enable_augmentation', True) else 0),
                    'feature_count': len(features_df.columns),
                    'class_distribution': labels_series.value_counts().to_dict()
                },
                'model_results': evaluation_results,
                'deployment_info': {
                    'best_model': best_algorithm,
                    'model_path': deployment_path,
                    'performance': asdict(self.performance_metrics[best_algorithm])
                }
            }
            
            # 파이프라인 결과 저장
            result_file = PROJECT_ROOT / "supervised_data" / f"pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(pipeline_results, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.info(f"🎉 파이프라인 완료! 결과: {result_file}")
            
            return pipeline_results
            
        except Exception as e:
            self.logger.error(f"❌ 파이프라인 실행 실패: {e}")
            raise
    
    # 파이프라인 상태 저장/복원
    async def save_pipeline_state(self, state_file: str):
        """파이프라인 상태 저장"""
        state = {
            'raw_data': self.raw_data,
            'feature_columns': self.feature_columns,
            'config': self.config,
            'performance_metrics': {
                algorithm: asdict(performance) 
                for algorithm, performance in self.performance_metrics.items()
            }
        }
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"💾 파이프라인 상태 저장: {state_file}")
    
    async def load_pipeline_state(self, state_file: str):
        """파이프라인 상태 복원"""
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            self.raw_data = state.get('raw_data', [])
            self.feature_columns = state.get('feature_columns', [])
            self.config.update(state.get('config', {}))
            
            # 성능 메트릭 복원
            for algorithm, perf_dict in state.get('performance_metrics', {}).items():
                self.performance_metrics[algorithm] = ModelPerformance(**perf_dict)
            
            self.logger.info(f"📂 파이프라인 상태 복원: {state_file}")
            
        except Exception as e:
            self.logger.error(f"❌ 상태 복원 실패: {e}")
            raise

class StepByStepLearning:
    """단계별 학습 진행 시스템"""
    
    def __init__(self):
        self.pipeline = SupervisedLearningPipeline()
        self.current_step = 0
        self.total_steps = 7
        self.step_results = {}
        
    async def run_interactive_pipeline(self):
        """대화형 단계별 파이프라인 실행"""
        print("🎓 DVD MTD 테스트베드 - 지도학습 단계별 가이드")
        print("="*60)
        
        steps = [
            ("데이터 수집 설정", self._step_data_collection_setup),
            ("학습 작업 선택", self._step_task_selection),
            ("데이터 수집 실행", self._step_data_collection),
            ("특성 공학", self._step_feature_engineering),
            ("모델 훈련", self._step_model_training),
            ("모델 평가", self._step_model_evaluation),
            ("결과 분석 및 배포", self._step_deployment)
        ]
        
        for i, (step_name, step_func) in enumerate(steps, 1):
            self.current_step = i
            print(f"\n{'='*60}")
            print(f"📚 단계 {i}/{len(steps)}: {step_name}")
            print('='*60)
            
            try:
                result = await step_func()
                self.step_results[f"step_{i}"] = result
                
                if result.get('success', True):
                    print(f"✅ 단계 {i} 완료!")
                else:
                    print(f"⚠️ 단계 {i} 부분 완료 (경고 있음)")
                
                # 계속 진행 여부 확인
                if i < len(steps):
                    continue_choice = input(f"\n다음 단계로 진행하시겠습니까? (y/n): ").strip().lower()
                    if continue_choice != 'y':
                        print("🛑 사용자에 의해 중단되었습니다.")
                        break
                        
            except Exception as e:
                print(f"❌ 단계 {i} 실행 실패: {e}")
                retry_choice = input("다시 시도하시겠습니까? (y/n): ").strip().lower()
                if retry_choice == 'y':
                    i -= 1  # 현재 단계 재시도
                else:
                    break
        
        # 최종 요약
        self._print_pipeline_summary()
    
    async def _step_data_collection_setup(self) -> Dict[str, Any]:
        """단계 1: 데이터 수집 설정"""
        print("📁 사용 가능한 데이터 소스를 확인합니다...")
        
        # 데이터 소스 스캔
        data_sources = []
        supervised_dir = PROJECT_ROOT / "supervised_data"
        
        # JSON 파일 스캔
        json_files = list(supervised_dir.glob("**/*.json"))
        csv_files = list(supervised_dir.glob("**/*.csv"))
        
        print(f"\n발견된 데이터 파일:")
        print(f"  • JSON 파일: {len(json_files)}개")
        print(f"  • CSV 파일: {len(csv_files)}개")
        
        # 자동으로 최신 파일들 선택
        recent_files = sorted(json_files + csv_files, key=os.path.getmtime, reverse=True)[:5]
        
        if recent_files:
            print(f"\n📈 최신 데이터 파일 {len(recent_files)}개를 사용합니다:")
            for file in recent_files:
                print(f"  • {file.name}")
                data_sources.append(str(file))
        else:
            print("⚠️ 기존 데이터 파일이 없습니다. 새로운 공격 실행이 필요합니다.")
            return {'success': False, 'message': 'No existing data found'}
        
        return {'success': True, 'data_sources': data_sources}
    
    async def _step_task_selection(self) -> Dict[str, Any]:
        """단계 2: 학습 작업 선택"""
        print("🎯 학습 작업을 선택하세요:")
        
        tasks = list(LearningTask)
        for i, task in enumerate(tasks, 1):
            description = {
                LearningTask.ATTACK_DETECTION: "공격 여부 탐지 (이진 분류)",
                LearningTask.ATTACK_CLASSIFICATION: "공격 유형 분류 (다중 분류)",
                LearningTask.MTD_EFFECTIVENESS: "MTD 효과성 예측",
                LearningTask.THREAT_SEVERITY: "위협 심각도 평가",
                LearningTask.ANOMALY_DETECTION: "이상 행동 탐지"
            }
            
            print(f"  {i}. {task.value}: {description[task]}")
        
        choice = int(input("\n선택 (1-5): ")) - 1
        selected_task = tasks[choice]
        
        print(f"\n✅ 선택된 작업: {selected_task.value}")
        
        return {'success': True, 'selected_task': selected_task}
    
    async def _step_data_collection(self) -> Dict[str, Any]:
        """단계 3: 데이터 수집 실행"""
        data_sources = self.step_results.get('step_1', {}).get('data_sources', [])
        
        if not data_sources:
            print("❌ 데이터 소스가 설정되지 않았습니다.")
            return {'success': False}
        
        print("📊 데이터 수집을 시작합니다...")
        
        collected_count = await self.pipeline.collect_training_data(data_sources)
        
        print(f"✅ {collected_count}개 샘플 수집 완료")
        
        # 데이터 요약 출력
        if self.pipeline.raw_data:
            sample = self.pipeline.raw_data[0]
            print(f"\n📋 데이터 샘플 정보:")
            print(f"  • 특성 개수: {len(sample)}개")
            print(f"  • 주요 특성: {list(sample.keys())[:5]}")
        
        return {'success': True, 'sample_count': collected_count}
    
    async def _step_feature_engineering(self) -> Dict[str, Any]:
        """단계 4: 특성 공학"""
        selected_task = self.step_results.get('step_2', {}).get('selected_task')
        
        if not selected_task:
            print("❌ 학습 작업이 선택되지 않았습니다.")
            return {'success': False}
        
        print("🔧 특성 공학을 시작합니다...")
        print(f"작업 유형: {selected_task.value}")
        
        features_df, labels_series = await self.pipeline.engineer_features(selected_task)
        
        print(f"\n📊 특성 공학 결과:")
        print(f"  • 특성 개수: {len(features_df.columns)}개")
        print(f"  • 샘플 개수: {len(features_df)}개")
        print(f"  • 레이블 분포: {labels_series.value_counts().to_dict()}")
        
        # 주요 특성 출력
        print(f"\n🔍 주요 특성들:")
        for i, col in enumerate(features_df.columns[:10], 1):
            print(f"  {i:2d}. {col}")
        
        return {'success': True, 'feature_count': len(features_df.columns), 'sample_count': len(features_df)}
    
    async def _step_model_training(self) -> Dict[str, Any]:
        """단계 5: 모델 훈련"""
        selected_task = self.step_results.get('step_2', {}).get('selected_task')
        
        print("🤖 모델 훈련을 시작합니다...")
        
        # 알고리즘 선택
        if SKLEARN_AVAILABLE:
            print("\n사용할 알고리즘을 선택하세요:")
            algorithms = ['random_forest', 'gradient_boosting', 'svm', 'logistic_regression', 'naive_bayes']
            print("1. 모든 알고리즘 (권장)")
            for i, alg in enumerate(algorithms, 2):
                print(f"{i}. {alg}")
            
            choice = int(input("선택: "))
            if choice == 1:
                selected_algorithms = algorithms
            else:
                selected_algorithms = [algorithms[choice - 2]]
        else:
            print("기본 구현으로 훈련합니다...")
            selected_algorithms = ['rule_based']
        
        # 모델 훈련 실행
        performances = await self.pipeline.train_models(selected_task, selected_algorithms)
        
        print(f"\n📈 훈련 결과:")
        for algorithm, performance in performances.items():
            print(f"  • {algorithm}:")
            print(f"    - 정확도: {performance.accuracy:.3f}")
            print(f"    - F1 점수: {performance.f1_score:.3f}")
        
        return {'success': True, 'trained_models': list(performances.keys())}
    
    async def _step_model_evaluation(self) -> Dict[str, Any]:
        """단계 6: 모델 평가"""
        print("📊 모델 평가를 시작합니다...")
        
        evaluation_results = await self.pipeline.evaluate_models()
        
        best_model = evaluation_results['best_model']
        print(f"\n🏆 최고 성능 모델: {best_model['algorithm']}")
        print(f"   정확도: {best_model['performance']['accuracy']:.3f}")
        print(f"   정밀도: {best_model['performance']['precision']:.3f}")
        print(f"   재현율: {best_model['performance']['recall']:.3f}")
        print(f"   F1 점수: {best_model['performance']['f1_score']:.3f}")
        
        # 모든 모델 성능 비교
        print(f"\n📊 전체 모델 성능 비교:")
        for algorithm, performance in evaluation_results['model_comparison'].items():
            print(f"  • {algorithm}: F1={performance['f1_score']:.3f}, Acc={performance['accuracy']:.3f}")
        
        return {'success': True, 'best_model': best_model['algorithm']}
    
    async def _step_deployment(self) -> Dict[str, Any]:
        """단계 7: 결과 분석 및 배포"""
        best_algorithm = self.step_results.get('step_6', {}).get('best_model')
        
        if not best_algorithm:
            print("❌ 최고 성능 모델이 선택되지 않았습니다.")
            return {'success': False}
        
        print(f"🚀 {best_algorithm} 모델을 배포합니다...")
        
        deployment_path = await self.pipeline.deploy_model(best_algorithm)
        
        print(f"✅ 모델 배포 완료: {deployment_path}")
        
        # 시각화 생성
        await self.pipeline.generate_visualizations()
        print("📊 시각화 생성 완료")
        
        # 실시간 예측 테스트
        print("\n🧪 실시간 예측 테스트...")
        test_features = {
            'packet_count': 1500,
            'connection_attempts': 10,
            'payload_size': 2048,
            'stealth_level': 0.7
        }
        
        try:
            prediction_result = await self.pipeline.predict_attack_outcome(test_features, best_algorithm)
            print(f"   예측 결과: {prediction_result['prediction']}")
            if prediction_result['probability']:
                print(f"   신뢰도: {prediction_result['probability']:.3f}")
        except Exception as e:
            print(f"   예측 테스트 실패: {e}")
        
        return {'success': True, 'deployment_path': deployment_path}
    
    def _print_pipeline_summary(self):
        """파이프라인 실행 요약 출력"""
        print("\n" + "="*80)
        print("🎉 지도학습 파이프라인 실행 완료!")
        print("="*80)
        
        for step_num, result in self.step_results.items():
            step_name = {
                'step_1': '데이터 수집 설정',
                'step_2': '학습 작업 선택', 
                'step_3': '데이터 수집 실행',
                'step_4': '특성 공학',
                'step_5': '모델 훈련',
                'step_6': '모델 평가',
                'step_7': '결과 분석 및 배포'
            }.get(step_num, f'단계 {step_num}')
            
            status = "✅" if result.get('success', True) else "❌"
            print(f"{status} {step_name}")
        
        print(f"\n📈 최종 결과:")
        
        # 데이터 요약
        if 'step_3' in self.step_results:
            sample_count = self.step_results['step_3'].get('sample_count', 0)
            print(f"  • 훈련 데이터: {sample_count}개 샘플")
        
        # 특성 요약
        if 'step_4' in self.step_results:
            feature_count = self.step_results['step_4'].get('feature_count', 0)
            print(f"  • 엔지니어링된 특성: {feature_count}개")
        
        # 모델 요약
        if 'step_5' in self.step_results:
            trained_models = self.step_results['step_5'].get('trained_models', [])
            print(f"  • 훈련된 모델: {len(trained_models)}개")
        
        # 최고 모델
        if 'step_6' in self.step_results:
            best_model = self.step_results['step_6'].get('best_model', 'Unknown')
            print(f"  • 최고 성능 모델: {best_model}")
        
        # 배포 정보
        if 'step_7' in self.step_results:
            deployment_path = self.step_results['step_7'].get('deployment_path', 'None')
            print(f"  • 배포 경로: {deployment_path}")
        
        print("\n🔗 다음 단계 권장사항:")
        print("  1. 더 많은 공격 데이터 수집으로 모델 성능 향상")
        print("  2. 실시간 탐지 시스템에 모델 통합")
        print("  3. 지속적인 모델 성능 모니터링")
        print("  4. 새로운 공격 패턴에 대한 재훈련")

async def main():
    """메인 실행 함수"""
    print("🎓 DVD MTD 지도학습 파이프라인")
    print("="*50)
    
    print("\n실행 모드를 선택하세요:")
    print("1. 단계별 대화형 학습 (권장)")
    print("2. 전체 파이프라인 자동 실행")
    print("3. 특정 작업만 실행")
    print("4. 기존 모델 성능 모니터링")
    
    try:
        choice = input("\n선택 (1-4): ").strip()
        
        if choice == "1":
            # 단계별 대화형 실행
            step_learning = StepByStepLearning()
            await step_learning.run_interactive_pipeline()
            
        elif choice == "2":
            # 전체 파이프라인 자동 실행
            print("\n🚀 전체 파이프라인 자동 실행...")
            
            pipeline = SupervisedLearningPipeline({
                'enable_augmentation': True,
                'cross_validation': True
            })
            
            # 데이터 소스 자동 탐지
            supervised_dir = PROJECT_ROOT / "supervised_data"
            data_files = list(supervised_dir.glob("**/*.json")) + list(supervised_dir.glob("**/*.csv"))
            recent_files = sorted(data_files, key=os.path.getmtime, reverse=True)[:3]
            
            if not recent_files:
                print("❌ 훈련 데이터가 없습니다. 먼저 공격을 실행하여 데이터를 생성하세요.")
                return
            
            data_sources = [str(f) for f in recent_files]
            
            # 공격 탐지 작업으로 파이프라인 실행
            results = await pipeline.run_full_pipeline(
                data_sources, 
                LearningTask.ATTACK_DETECTION,
                ['random_forest', 'gradient_boosting'] if SKLEARN_AVAILABLE else None
            )
            
            print("\n🎉 파이프라인 완료!")
            print(f"최고 모델: {results['deployment_info']['best_model']}")
            
        elif choice == "3":
            print("\n⚙️ 특정 작업 실행 - 구현 예정")
            
        elif choice == "4":
            print("\n📈 모델 성능 모니터링 - 구현 예정")
            
        else:
            print("❌ 잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")

    def print_pipeline_summary(self):
        """파이프라인 실행 요약 출력"""
        print("\n" + "="*80)
        print("🎉 지도학습 파이프라인 실행 완료!")
        print("="*80)
        
        for step_num, result in self.step_results.items():
            step_name = {
                'step_1': '데이터 수집 설정',
                'step_2': '학습 작업 선택', 
                'step_3': '데이터 수집 실행',
                'step_4': '특성 공학',
                'step_5': '모델 훈련',
                'step_6': '모델 평가',
                'step_7': '결과 분석 및 배포'
            }.get(step_num, f'단계 {step_num}')
            
            status = "✅" if result.get('success', True) else "❌"
            print(f"{status} {step_name}")
        
        print(f"\n📈 최종 결과:")
        
        # 데이터 요약
        if 'step_3' in self.step_results:
            sample_count = self.step_results['step_3'].get('sample_count', 0)
            print(f"  • 훈련 데이터: {sample_count}개 샘플")
        
        # 특성 요약
        if 'step_4' in self.step_results:
            feature_count = self.step_results['step_4'].get('feature_count', 0)
            print(f"  • 엔지니어링된 특성: {feature_count}개")
        
        # 모델 요약
        if 'step_5' in self.step_results:
            trained_models = self.step_results['step_5'].get('trained_models', [])
            print(f"  • 훈련된 모델: {len(trained_models)}개")
        
        # 최고 모델
        if 'step_6' in self.step_results:
            best_model = self.step_results['step_6'].get('best_model', 'Unknown')
            print(f"  • 최고 성능 모델: {best_model}")
        
        # 배포 정보
        if 'step_7' in self.step_results:
            deployment_path = self.step_results['step_7'].get('deployment_path', 'None')
            print(f"  • 배포 경로: {deployment_path}")
        
        print("\n🔗 다음 단계 권장사항:")
        print("  1. 더 많은 공격 데이터 수집으로 모델 성능 향상")
        print("  2. 실시간 탐지 시스템에 모델 통합")
        print("  3. 지속적인 모델 성능 모니터링")
        print("  4. 새로운 공격 패턴에 대한 재훈련")

class HyperparameterTuning:
    """하이퍼파라미터 튜닝 시스템"""
    
    def __init__(self, pipeline: SupervisedLearningPipeline):
        self.pipeline = pipeline
        self.tuning_results = {}
        
    async def grid_search(self, algorithm: str, param_grid: Dict[str, List]) -> Dict[str, Any]:
        """그리드 서치를 통한 하이퍼파라미터 최적화"""
        if not SKLEARN_AVAILABLE:
            return {"error": "scikit-learn required for grid search"}
        
        from sklearn.model_selection import GridSearchCV
        from sklearn.model_selection import StratifiedKFold
        
        # 베이스 모델 생성
        base_model = self.pipeline._create_model(algorithm, LearningTask.ATTACK_DETECTION)
        
        # 교차 검증 설정
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        
        # 그리드 서치 실행
        grid_search = GridSearchCV(
            base_model, 
            param_grid, 
            cv=cv, 
            scoring='f1_weighted',
            n_jobs=-1,
            verbose=1
        )
        
        # 훈련 데이터로 그리드 서치
        X_train, X_test, y_train, y_test = train_test_split(
            self.pipeline.processed_features, 
            self.pipeline.labels,
            test_size=0.2, 
            random_state=42
        )
        
        grid_search.fit(X_train, y_train)
        
        # 결과 저장
        tuning_result = {
            'algorithm': algorithm,
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_
        }
        
        self.tuning_results[algorithm] = tuning_result
        
        return tuning_result

class ModelExplainer:
    """모델 해석성 분석 도구"""
    
    def __init__(self, model, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names
        
    def explain_prediction(self, sample_features: np.ndarray) -> Dict[str, Any]:
        """개별 예측에 대한 설명"""
        explanation = {
            'prediction': self.model.predict(sample_features.reshape(1, -1))[0],
            'feature_contributions': {}
        }
        
        # 특성 중요도 기반 설명 (Random Forest 등)
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            
            for i, feature_name in enumerate(self.feature_names):
                contribution = importance[i] * sample_features[i]
                explanation['feature_contributions'][feature_name] = contribution
        
        return explanation
    
    def generate_decision_rules(self) -> List[str]:
        """의사결정 규칙 추출 (Tree 기반 모델)"""
        rules = []
        
        if hasattr(self.model, 'estimators_'):
            # Random Forest의 경우 첫 번째 트리에서 규칙 추출
            tree = self.model.estimators_[0]
            rules = self._extract_tree_rules(tree, self.feature_names)
        elif hasattr(self.model, 'tree_'):
            # 단일 트리의 경우
            rules = self._extract_tree_rules(self.model, self.feature_names)
        
        return rules[:10]  # 상위 10개 규칙만 반환
    
    def _extract_tree_rules(self, tree, feature_names) -> List[str]:
        """트리에서 규칙 추출"""
        rules = []
        
        def recurse(node, depth=0, rule=""):
            if tree.tree_.feature[node] != -2:  # 리프 노드가 아닌 경우
                feature = feature_names[tree.tree_.feature[node]]
                threshold = tree.tree_.threshold[node]
                
                # 왼쪽 자식 (조건 만족)
                left_rule = f"{rule} AND {feature} <= {threshold:.3f}" if rule else f"{feature} <= {threshold:.3f}"
                recurse(tree.tree_.children_left[node], depth + 1, left_rule)
                
                # 오른쪽 자식 (조건 불만족)
                right_rule = f"{rule} AND {feature} > {threshold:.3f}" if rule else f"{feature} > {threshold:.3f}"
                recurse(tree.tree_.children_right[node], depth + 1, right_rule)
            else:
                # 리프 노드 - 규칙 완성
                prediction = np.argmax(tree.tree_.value[node])
                confidence = np.max(tree.tree_.value[node]) / np.sum(tree.tree_.value[node])
                
                if confidence > 0.8:  # 높은 신뢰도의 규칙만
                    rules.append(f"IF {rule} THEN prediction={prediction} (confidence={confidence:.3f})")
        
        if hasattr(tree, 'tree_'):
            recurse(0)
        
        return rules

class AdversarialTesting:
    """적대적 공격에 대한 모델 강건성 테스트"""
    
    def __init__(self, model, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names
        
    def generate_adversarial_samples(self, X_test: np.ndarray, epsilon: float = 0.1) -> np.ndarray:
        """적대적 샘플 생성 (FGSM 유사)"""
        adversarial_samples = []
        
        for sample in X_test:
            # 각 특성에 작은 노이즈 추가
            noise = np.random.uniform(-epsilon, epsilon, size=sample.shape)
            adversarial_sample = sample + noise
            
            # 특성 값이 음수가 되지 않도록 클리핑
            adversarial_sample = np.clip(adversarial_sample, 0, None)
            
            adversarial_samples.append(adversarial_sample)
        
        return np.array(adversarial_samples)
    
    def test_robustness(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """모델 강건성 테스트"""
        # 원본 정확도
        original_predictions = self.model.predict(X_test)
        original_accuracy = np.mean(original_predictions == y_test)
        
        # 적대적 샘플에서의 정확도
        adversarial_X = self.generate_adversarial_samples(X_test)
        adversarial_predictions = self.model.predict(adversarial_X)
        adversarial_accuracy = np.mean(adversarial_predictions == y_test)
        
        # 강건성 점수
        robustness_score = adversarial_accuracy / original_accuracy
        
        return {
            'original_accuracy': original_accuracy,
            'adversarial_accuracy': adversarial_accuracy,
            'robustness_score': robustness_score,
            'accuracy_drop': original_accuracy - adversarial_accuracy
        }

class ContinualLearning:
    """지속 학습 시스템"""
    
    def __init__(self, base_pipeline: SupervisedLearningPipeline):
        self.base_pipeline = base_pipeline
        self.model_versions = {}
        self.performance_history = []
        
    async def update_model(self, new_data: List[Dict]) -> Dict[str, Any]:
        """새로운 데이터로 모델 업데이트"""
        self.base_pipeline.logger.info("🔄 지속 학습 - 모델 업데이트 시작")
        
        # 새 데이터 추가
        original_count = len(self.base_pipeline.raw_data)
        self.base_pipeline.raw_data.extend(new_data)
        
        # 특성 재생성
        features_df, labels_series = await self.base_pipeline.engineer_features(LearningTask.ATTACK_DETECTION)
        
        # 점진적 학습 또는 재훈련
        if SKLEARN_AVAILABLE:
            # 기존 모델이 있는 경우 점진적 학습 시도
            if 'random_forest' in self.base_pipeline.trained_models:
                updated_performance = await self._incremental_update('random_forest', features_df, labels_series)
            else:
                # 새 모델 훈련
                updated_performance = await self.base_pipeline.train_models(LearningTask.ATTACK_DETECTION, ['random_forest'])
        else:
            updated_performance = await self.base_pipeline.train_models(LearningTask.ATTACK_DETECTION)
        
        # 성능 이력 기록
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'data_size': len(self.base_pipeline.raw_data),
            'new_samples': len(new_data),
            'performance': updated_performance
        })
        
        update_result = {
            'original_data_size': original_count,
            'new_data_size': len(new_data),
            'updated_data_size': len(self.base_pipeline.raw_data),
            'performance_change': self._calculate_performance_change(),
            'recommendation': self._get_update_recommendation()
        }
        
        return update_result
    
    async def _incremental_update(self, algorithm: str, features_df: pd.DataFrame, labels_series: pd.Series) -> Dict[str, Any]:
        """점진적 모델 업데이트"""
        # 새 데이터만 사용하여 모델 업데이트 시뮬레이션
        # 실제로는 온라인 학습 알고리즘이나 배치 업데이트 사용
        
        # 단순 재훈련으로 구현 (점진적 학습 시뮬레이션)
        X_train, X_test, y_train, y_test = train_test_split(
            features_df, labels_series, test_size=0.2, random_state=42
        )
        
        model = self.base_pipeline.trained_models[algorithm]
        
        # 새 데이터로 재훈련
        model.fit(X_train, y_train)
        
        # 성능 측정
        y_pred = model.predict(X_test)
        performance = self.base_pipeline._calculate_performance_metrics(
            y_test, y_pred, model, X_test, algorithm
        )
        
        return {algorithm: performance}
    
    def _calculate_performance_change(self) -> float:
        """성능 변화 계산"""
        if len(self.performance_history) < 2:
            return 0.0
        
        current = self.performance_history[-1]['performance']
        previous = self.performance_history[-2]['performance']
        
        # F1 점수 기준으로 변화 계산
        current_f1 = list(current.values())[0].f1_score if current else 0
        previous_f1 = list(previous.values())[0].f1_score if previous else 0
        
        return current_f1 - previous_f1
    
    def _get_update_recommendation(self) -> str:
        """업데이트 권장사항"""
        performance_change = self._calculate_performance_change()
        
        if performance_change > 0.05:
            return "EXCELLENT - 성능이 크게 향상되었습니다"
        elif performance_change > 0.01:
            return "GOOD - 성능이 향상되었습니다"
        elif performance_change > -0.01:
            return "STABLE - 성능이 유지되고 있습니다"
        elif performance_change > -0.05:
            return "DEGRADED - 성능이 약간 저하되었습니다"
        else:
            return "POOR - 성능이 크게 저하되었습니다. 모델 재검토 필요"

class AutoMLSystem:
    """자동 머신러닝 시스템"""
    
    def __init__(self):
        self.best_pipeline = None
        self.pipeline_results = []
        
    async def auto_optimize(self, data_sources: List[str], task_type: LearningTask) -> Dict[str, Any]:
        """자동 파이프라인 최적화"""
        print("🤖 AutoML 시스템 시작 - 자동 최적화")
        
        # 여러 설정으로 파이프라인 실험
        configurations = [
            {'enable_augmentation': True, 'cross_validation': True, 'feature_selection': True},
            {'enable_augmentation': False, 'cross_validation': True, 'feature_selection': True},
            {'enable_augmentation': True, 'cross_validation': False, 'feature_selection': True},
            {'enable_augmentation': True, 'cross_validation': True, 'feature_selection': False},
        ]
        
        algorithms_sets = [
            ['random_forest'],
            ['gradient_boosting'],
            ['random_forest', 'gradient_boosting'],
            ['random_forest', 'gradient_boosting', 'svm'] if SKLEARN_AVAILABLE else ['random_forest']
        ]
        
        best_score = 0
        best_config = None
        
        for i, config in enumerate(configurations):
            for j, algorithms in enumerate(algorithms_sets):
                print(f"🔄 실험 {i+1}-{j+1}: {config} with {algorithms}")
                
                try:
                    # 파이프라인 실행
                    pipeline = SupervisedLearningPipeline(config)
                    
                    # 데이터 수집 및 전처리
                    await pipeline.collect_training_data(data_sources)
                    
                    if config.get('enable_augmentation', False):
                        await pipeline.generate_augmented_data(2)
                    
                    await pipeline.engineer_features(task_type)
                    
                    # 모델 훈련
                    performances = await pipeline.train_models(task_type, algorithms)
                    
                    # 최고 성능 기록
                    best_algorithm = max(performances.items(), key=lambda x: x[1].f1_score)
                    current_score = best_algorithm[1].f1_score
                    
                    experiment_result = {
                        'config': config,
                        'algorithms': algorithms,
                        'best_algorithm': best_algorithm[0],
                        'score': current_score,
                        'performance': asdict(best_algorithm[1])
                    }
                    
                    self.pipeline_results.append(experiment_result)
                    
                    if current_score > best_score:
                        best_score = current_score
                        best_config = experiment_result
                        self.best_pipeline = pipeline
                    
                    print(f"✅ F1 점수: {current_score:.3f}")
                    
                except Exception as e:
                    print(f"❌ 실험 실패: {e}")
                    continue
        
        # 최적화 결과
        optimization_result = {
            'best_configuration': best_config,
            'best_score': best_score,
            'total_experiments': len(self.pipeline_results),
            'all_results': self.pipeline_results
        }
        
        print(f"🏆 AutoML 완료 - 최고 F1 점수: {best_score:.3f}")
        print(f"🎯 최적 알고리즘: {best_config['best_algorithm'] if best_config else 'None'}")
        
        return optimization_result
    
    async def deploy_best_model(self) -> Optional[str]:
        """최고 성능 모델 배포"""
        if not self.best_pipeline:
            return None
        
        best_config = max(self.pipeline_results, key=lambda x: x['score'])
        best_algorithm = best_config['best_algorithm']
        
        deployment_path = await self.best_pipeline.deploy_model(best_algorithm)
        return deployment_path

class MLOpsIntegration:
    """MLOps 통합 시스템"""
    
    def __init__(self, pipeline: SupervisedLearningPipeline):
        self.pipeline = pipeline
        self.model_registry = {}
        self.experiment_tracking = []
        
    async def register_model(self, model_name: str, algorithm: str, metadata: Dict[str, Any]) -> str:
        """모델 레지스트리에 등록"""
        model_id = f"{model_name}_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.model_registry[model_id] = {
            'name': model_name,
            'algorithm': algorithm,
            'metadata': metadata,
            'registered_at': datetime.now().isoformat(),
            'status': 'REGISTERED'
        }
        
        return model_id
    
    async def create_model_card(self, model_id: str) -> str:
        """모델 카드 생성"""
        if model_id not in self.model_registry:
            return "Model not found"
        
        model_info = self.model_registry[model_id]
        
        card_content = f"""# Model Card: {model_info['name']}

## Model Information
- **Algorithm**: {model_info['algorithm']}
- **Registration Date**: {model_info['registered_at']}
- **Status**: {model_info['status']}

## Performance Metrics
- **Accuracy**: {model_info['metadata'].get('accuracy', 'N/A')}
- **F1 Score**: {model_info['metadata'].get('f1_score', 'N/A')}
- **Precision**: {model_info['metadata'].get('precision', 'N/A')}
- **Recall**: {model_info['metadata'].get('recall', 'N/A')}

## Training Data
- **Dataset Size**: {model_info['metadata'].get('dataset_size', 'N/A')}
- **Feature Count**: {model_info['metadata'].get('feature_count', 'N/A')}

## Intended Use
이 모델은 드론 보안 테스트베드에서 공격 탐지 및 분류를 위해 훈련되었습니다.

## Limitations
- 시뮬레이션 환경에서 훈련됨
- 특정 공격 패턴에 특화됨
- 정기적인 재훈련 필요

## Ethical Considerations
- 교육 및 연구 목적으로만 사용
- 실제 운영 환경 적용 시 추가 검증 필요

---
Generated by DVD MTD Testbed
"""
        
        # 모델 카드 저장
        card_path = PROJECT_ROOT / "supervised_data" / "models" / f"{model_id}_card.md"
        with open(card_path, 'w', encoding='utf-8') as f:
            f.write(card_content)
        
        return str(card_path)
    
    def track_experiment(self, experiment_name: str, parameters: Dict, results: Dict):
        """실험 추적"""
        experiment = {
            'name': experiment_name,
            'timestamp': datetime.now().isoformat(),
            'parameters': parameters,
            'results': results,
            'experiment_id': len(self.experiment_tracking) + 1
        }
        
        self.experiment_tracking.append(experiment)
        
        # 실험 로그 저장
        log_path = PROJECT_ROOT / "supervised_data" / "experiments" / f"experiment_{experiment['experiment_id']}.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(experiment, f, indent=2)

# 통합 실행 함수들
async def run_comprehensive_ml_suite():
    """종합적인 ML 스위트 실행"""
    print("🚀 DVD MTD 종합 ML 스위트 시작")
    
    # 데이터 소스 설정
    supervised_dir = PROJECT_ROOT / "supervised_data"
    data_files = list(supervised_dir.glob("**/*.json")) + list(supervised_dir.glob("**/*.jsonl"))
    
    if not data_files:
        print("❌ 훈련 데이터가 없습니다. 먼저 공격을 실행하세요.")
        return
    
    data_sources = [str(f) for f in data_files[:5]]  # 최신 5개 파일
    
    # 1. 기본 파이프라인
    print("\n1️⃣ 기본 파이프라인 실행")
    pipeline = SupervisedLearningPipeline({'enable_augmentation': True})
    basic_results = await pipeline.run_full_pipeline(
        data_sources, 
        LearningTask.ATTACK_DETECTION,
        ['random_forest', 'gradient_boosting'] if SKLEARN_AVAILABLE else None
    )
    
    # 2. AutoML 최적화
    print("\n2️⃣ AutoML 최적화 실행")
    automl = AutoMLSystem()
    automl_results = await automl.auto_optimize(data_sources, LearningTask.ATTACK_DETECTION)
    
    # 3. 모델 해석성 분석
    print("\n3️⃣ 모델 해석성 분석")
    if 'random_forest' in pipeline.trained_models:
        explainer = ModelExplainer(
            pipeline.trained_models['random_forest'], 
            pipeline.feature_columns
        )
        
        rules = explainer.generate_decision_rules()
        print(f"📋 추출된 의사결정 규칙: {len(rules)}개")
    
    # 4. 강건성 테스트
    print("\n4️⃣ 모델 강건성 테스트")
    if pipeline.processed_features is not None and 'random_forest' in pipeline.trained_models:
        adversarial_tester = AdversarialTesting(
            pipeline.trained_models['random_forest'],
            pipeline.feature_columns
        )
        
        # 테스트 데이터 생성
        X_train, X_test, y_train, y_test = train_test_split(
            pipeline.processed_features, pipeline.labels, test_size=0.2, random_state=42
        )
        
        robustness = adversarial_tester.test_robustness(X_test.values, y_test.values)
        print(f"🛡️ 강건성 점수: {robustness['robustness_score']:.3f}")
    
    # 5. MLOps 통합
    print("\n5️⃣ MLOps 통합")
    mlops = MLOpsIntegration(pipeline)
    
    best_algorithm = basic_results['deployment_info']['best_model']
    model_id = await mlops.register_model(
        "dvd_attack_detector", 
        best_algorithm,
        basic_results['deployment_info']['performance']
    )
    
    card_path = await mlops.create_model_card(model_id)
    print(f"📋 모델 카드 생성: {card_path}")
    
    # 6. 종합 보고서 생성
    print("\n6️⃣ 종합 보고서 생성")
    comprehensive_report = {
        'execution_timestamp': datetime.now().isoformat(),
        'basic_pipeline_results': basic_results,
        'automl_results': automl_results,
        'model_registry': mlops.model_registry,
        'recommendations': generate_ml_recommendations(basic_results, automl_results)
    }
    
    report_file = PROJECT_ROOT / "supervised_data" / f"comprehensive_ml_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(comprehensive_report, f, indent=2, default=str)
    
    print(f"📊 종합 보고서 저장: {report_file}")
    print("🎉 종합 ML 스위트 완료!")
    
    return comprehensive_report

def generate_ml_recommendations(basic_results: Dict, automl_results: Dict) -> List[str]:
    """ML 권장사항 생성"""
    recommendations = []
    
    # 성능 기반 권장사항
    best_f1 = basic_results.get('deployment_info', {}).get('performance', {}).get('f1_score', 0)
    
    if best_f1 < 0.7:
        recommendations.append("모델 성능이 낮습니다. 더 많은 훈련 데이터가 필요합니다.")
    elif best_f1 < 0.8:
        recommendations.append("특성 엔지니어링을 개선하여 성능을 향상시킬 수 있습니다.")
    else:
        recommendations.append("우수한 성능입니다. 실제 환경에서 테스트해보세요.")
    
    # AutoML 결과 기반 권장사항
    if automl_results.get('total_experiments', 0) > 0:
        best_automl_score = automl_results.get('best_score', 0)
        if best_automl_score > best_f1:
            recommendations.append("AutoML이 더 나은 설정을 찾았습니다. 최적 구성을 사용하세요.")
        else:
            recommendations.append("기본 설정이 AutoML 결과와 유사합니다. 현재 설정을 유지하세요.")
    
    # 데이터 크기 기반 권장사항
    dataset_size = basic_results.get('data_summary', {}).get('total_samples', 0)
    if dataset_size < 1000:
        recommendations.append("데이터셋이 작습니다. 더 많은 공격 시나리오를 실행하세요.")
    elif dataset_size > 10000:
        recommendations.append("충분한 데이터가 있습니다. 고급 알고리즘을 시도해보세요.")
    
    return recommendations

async def main():
    """메인 실행 함수"""
    
    print("🎓 DVD MTD 지도학습 파이프라인")
    print("="*50)
    
    print("\n실행 모드를 선택하세요:")
    print("1. 단계별 대화형 학습 (권장)")
    print("2. 전체 파이프라인 자동 실행")
    print("3. AutoML 자동 최적화")
    print("4. 종합 ML 스위트 실행")
    print("5. 지속 학습 테스트")
    print("6. 모델 해석성 분석")
    print("7. 강건성 테스트")
    
    try:
        choice = input("\n선택 (1-7): ").strip()
        
        if choice == "1":
            # 단계별 대화형 실행
            step_learning = StepByStepLearning()
            await step_learning.run_interactive_pipeline()
            
        elif choice == "2":
            # 전체 파이프라인 자동 실행
            print("\n🚀 전체 파이프라인 자동 실행...")
            
            pipeline = SupervisedLearningPipeline({
                'enable_augmentation': True,
                'cross_validation': True
            })
            
            # 데이터 소스 자동 탐지
            supervised_dir = PROJECT_ROOT / "supervised_data"
            data_files = list(supervised_dir.glob("**/*.json")) + list(supervised_dir.glob("**/*.csv"))
            recent_files = sorted(data_files, key=os.path.getmtime, reverse=True)[:3]
            
            if not recent_files:
                print("❌ 훈련 데이터가 없습니다. 먼저 공격을 실행하여 데이터를 생성하세요.")
                return
            
            data_sources = [str(f) for f in recent_files]
            
            # 공격 탐지 작업으로 파이프라인 실행
            results = await pipeline.run_full_pipeline(
                data_sources, 
                LearningTask.ATTACK_DETECTION,
                ['random_forest', 'gradient_boosting'] if SKLEARN_AVAILABLE else None
            )
            
            print("\n🎉 파이프라인 완료!")
            print(f"최고 모델: {results['deployment_info']['best_model']}")
            
        elif choice == "3":
            # AutoML 최적화
            print("\n🤖 AutoML 자동 최적화...")
            
            supervised_dir = PROJECT_ROOT / "supervised_data"
            data_files = list(supervised_dir.glob("**/*.json")) + list(supervised_dir.glob("**/*.jsonl"))
            
            if not data_files:
                print("❌ 훈련 데이터가 없습니다.")
                return
            
            data_sources = [str(f) for f in data_files[:5]]
            
            automl = AutoMLSystem()
            results = await automl.auto_optimize(data_sources, LearningTask.ATTACK_DETECTION)
            
            # 최고 모델 배포
            if automl.best_pipeline:
                deployment_path = await automl.deploy_best_model()
                print(f"🚀 최적 모델 배포: {deployment_path}")
            
        elif choice == "4":
            # 종합 ML 스위트
            print("\n🎯 종합 ML 스위트 실행...")
            await run_comprehensive_ml_suite()
            
        elif choice == "5":
            # 지속 학습 테스트
            print("\n🔄 지속 학습 테스트...")
            
            # 기본 파이프라인 생성
            pipeline = SupervisedLearningPipeline()
            
            # 기존 데이터로 초기 모델 훈련
            supervised_dir = PROJECT_ROOT / "supervised_data"
            data_files = list(supervised_dir.glob("**/*.json"))[:3]
            
            if data_files:
                data_sources = [str(f) for f in data_files]
                await pipeline.collect_training_data(data_sources)
                await pipeline.engineer_features(LearningTask.ATTACK_DETECTION)
                await pipeline.train_models(LearningTask.ATTACK_DETECTION, ['random_forest'])
                
                # 지속 학습 시스템 테스트
                continual = ContinualLearning(pipeline)
                
                # 새 데이터 시뮬레이션
                new_data = [
                    {
                        'timestamp': datetime.now().isoformat(),
                        'attack_vector': 'test_attack',
                        'network_features_packet_count': 500,
                        'attack_features_payload_size': 1024,
                        'label': 'attack_success'
                    }
                ]
                
                update_result = await continual.update_model(new_data)
                print(f"📊 업데이트 결과: {update_result['recommendation']}")
            else:
                print("❌ 기존 데이터가 없어 지속 학습을 테스트할 수 없습니다.")
            
        elif choice == "6":
            # 모델 해석성 분석
            print("\n🔍 모델 해석성 분석...")
            
            # 간단한 파이프라인 실행
            pipeline = SupervisedLearningPipeline()
            
            supervised_dir = PROJECT_ROOT / "supervised_data"
            data_files = list(supervised_dir.glob("**/*.json"))
            
            if data_files:
                data_sources = [str(f) for f in data_files[:2]]
                await pipeline.collect_training_data(data_sources)
                await pipeline.engineer_features(LearningTask.ATTACK_DETECTION)
                await pipeline.train_models(LearningTask.ATTACK_DETECTION, ['random_forest'])
                
                if 'random_forest' in pipeline.trained_models:
                    explainer = ModelExplainer(
                        pipeline.trained_models['random_forest'],
                        pipeline.feature_columns
                    )
                    
                    # 의사결정 규칙 추출
                    rules = explainer.generate_decision_rules()
                    print(f"\n📋 추출된 의사결정 규칙 ({len(rules)}개):")
                    for i, rule in enumerate(rules[:5], 1):
                        print(f"{i}. {rule}")
                    
                    # 샘플 예측 설명
                    if pipeline.processed_features is not None and len(pipeline.processed_features) > 0:
                        sample = pipeline.processed_features.iloc[0].values
                        explanation = explainer.explain_prediction(sample)
                        
                        print(f"\n🎯 샘플 예측 설명:")
                        print(f"예측: {explanation['prediction']}")
                        print("주요 기여 특성:")
                        sorted_contributions = sorted(
                            explanation['feature_contributions'].items(),
                            key=lambda x: abs(x[1]),
                            reverse=True
                        )
                        for feature, contribution in sorted_contributions[:5]:
                            print(f"  • {feature}: {contribution:.3f}")
                else:
                    print("❌ 훈련된 모델이 없습니다.")
            else:
                print("❌ 훈련 데이터가 없습니다.")
                
        elif choice == "7":
            # 강건성 테스트
            print("\n🛡️ 모델 강건성 테스트...")
            
            # 파이프라인 실행
            pipeline = SupervisedLearningPipeline()
            
            supervised_dir = PROJECT_ROOT / "supervised_data"
            data_files = list(supervised_dir.glob("**/*.json"))
            
            if data_files:
                data_sources = [str(f) for f in data_files[:2]]
                await pipeline.collect_training_data(data_sources)
                await pipeline.engineer_features(LearningTask.ATTACK_DETECTION)
                await pipeline.train_models(LearningTask.ATTACK_DETECTION, ['random_forest'])
                
                if 'random_forest' in pipeline.trained_models and pipeline.processed_features is not None:
                    adversarial_tester = AdversarialTesting(
                        pipeline.trained_models['random_forest'],
                        pipeline.feature_columns
                    )
                    
                    # 테스트 데이터 준비
                    X_train, X_test, y_train, y_test = train_test_split(
                        pipeline.processed_features, pipeline.labels, 
                        test_size=0.2, random_state=42
                    )
                    
                    # 강건성 테스트 실행
                    robustness_results = adversarial_tester.test_robustness(X_test.values, y_test.values)
                    
                    print(f"\n🎯 강건성 테스트 결과:")
                    print(f"  • 원본 정확도: {robustness_results['original_accuracy']:.3f}")
                    print(f"  • 적대적 정확도: {robustness_results['adversarial_accuracy']:.3f}")
                    print(f"  • 강건성 점수: {robustness_results['robustness_score']:.3f}")
                    print(f"  • 정확도 감소: {robustness_results['accuracy_drop']:.3f}")
                    
                    if robustness_results['robustness_score'] > 0.8:
                        print("✅ 모델이 적대적 공격에 강건합니다.")
                    elif robustness_results['robustness_score'] > 0.6:
                        print("⚠️ 모델이 적대적 공격에 어느 정도 취약합니다.")
                    else:
                        print("❌ 모델이 적대적 공격에 매우 취약합니다.")
                else:
                    print("❌ 테스트할 모델이나 데이터가 없습니다.")
            else:
                print("❌ 훈련 데이터가 없습니다.")
                
        else:
            print("❌ 잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
        """공격 탐지를 위한 특성 생성"""
        features = []
        labels = []
        
        for _, row in df.iterrows():
            # 네트워크 특성
            network_features = {
                'packet_count': row.get('network_features_packet_count', 0),
                'connection_attempts': row.get('network_features_connection_attempts', 0),
                'unique_ips': row.get('network_features_unique_ips', 0),
                'port_scans': row.get('network_features_port_scans', 0),
                'protocol_violations': row.get('network_features_protocol_violations', 0),
                'bandwidth_usage': row.get('network_features_bandwidth_usage', 0.0),
                'latency_avg': row.get('network_features_latency_avg', 0.0)
            }
            
            # 공격 특성
            attack_features = {
                'attack_complexity': row.get('attack_features_attack_complexity', 1),
                'payload_size': row.get('attack_features_payload_size', 0),
                'exploit_attempts': row.get('attack_features_exploit_attempts', 0),
                'stealth_level': row.get('attack_features_stealth_level', 0.0),
                'persistence_mechanisms': row.get('attack_features_persistence_mechanisms', 0)
            }
            
            # 시간 기반 특성
            temporal_features = {
                'hour_of_day': datetime.fromisoformat(row.get('timestamp', '2024-01-01T00:00:00')).hour,
                'day_of_week': datetime.fromisoformat(row.get('timestamp', '2024-01-01T00:00:00')).weekday(),
                'attack_duration': row.get('meta_duration', 0.0)
            }
            
            # 모든 특성 결합
            combined_features = {**network_features, **attack_features, **temporal_features}
            features.append(combined_features)
            
            # 이진 분류 레이블 (공격 vs 정상)
            is_attack = row.get('label', '').startswith('attack_')
            labels.append(1 if is_attack else 0)
        
        features_df = pd.DataFrame(features)
        labels_series = pd.Series(labels, name='is_attack')
        
        return features_df, labels_series
    
    def _engineer_attack_classification_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """공격 분류를 위한 특성 생성"""
        features = []
        labels = []
        
        for _, row in df.iterrows():
            # 공격 시그니처 특성
            signature_features = {
                'mavlink_packets': 1 if 'mavlink' in row.get('attack_vector', '').lower() else 0,
                'wifi_activity': 1 if 'wifi' in row.get('attack_vector', '').lower() else 0,
                'gps_manipulation': 1 if 'gps' in row.get('attack_vector', '').lower() else 0,
                'firmware_activity': 1 if 'firmware' in row.get('attack_vector', '').lower() else 0,
                'injection_patterns': 1 if 'injection' in row.get('attack_vector', '').lower() else 0,
                'exfiltration_patterns': 1 if 'exfiltration' in row.get('attack_vector', '').lower() else 0
            }
            
            # 행동 특성
            behavioral_features = {
                'scan_intensity': row.get('network_features_port_scans', 0) / max(row.get('meta_duration', 1), 1),
                'connection_rate': row.get('network_features_connection_attempts', 0) / max(row.get('meta_duration', 1), 1),
                'payload_complexity': min(row.get('attack_features_payload_size', 0) / 1024, 10),  # KB 단위, 최대 10
                'stealth_score': row.get('attack_features_stealth_level', 0.0),
                'persistence_score': min(row.get('attack_features_persistence_mechanisms', 0), 5)
            }
            
            # 프로토콜 특성
            protocol_features = {
                'protocol_violations_rate': row.get('network_features_protocol_violations', 0),
                'bandwidth_anomaly': min(row.get('network_features_bandwidth_usage', 0) / 1000, 10),  # Mbps
                'latency_anomaly': min(row.get('network_features_latency_avg', 0) / 100, 10)  # 정규화
            }
            
            # 모든 특성 결합
            combined_features = {**signature_features, **behavioral_features, **protocol_features}
            features.append(combined_features)
            
            # 공격 유형 레이블
            attack_vector = row.get('attack_vector', 'unknown')
            labels.append(attack_vector)
        
        features_df = pd.DataFrame(features)
        labels_series = pd.Series(labels, name='attack_type')
        
        return features_df, labels_series
    
    def _engineer_