# dvd_lite/ml_detection/enhanced_detector.py
"""
고급 머신러닝 탐지 기능 및 성능 최적화
시계열 분석, 딥러닝, 온라인 학습 등 추가 기능
"""

import asyncio
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
import json
from collections import deque
import warnings
warnings.filterwarnings('ignore')

# 고급 ML 라이브러리들
try:
    from sklearn.ensemble import GradientBoostingClassifier, ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import GaussianNB
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE
    from sklearn.preprocessing import RobustScaler, MinMaxScaler
    from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.metrics import roc_auc_score, precision_recall_curve, f1_score
    from sklearn.base import BaseEstimator, ClassifierMixin
    import joblib
    ADVANCED_ML_AVAILABLE = True
except ImportError:
    ADVANCED_ML_AVAILABLE = False

# 딥러닝 라이브러리
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, Model
    from tensorflow.keras.layers import Dense, LSTM, Conv1D, Dropout, BatchNormalization
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    DEEP_LEARNING_AVAILABLE = True
except ImportError:
    DEEP_LEARNING_AVAILABLE = False

# 시계열 분석
try:
    from scipy import stats
    from scipy.signal import find_peaks
    import matplotlib.pyplot as plt
    import seaborn as sns
    TIME_SERIES_AVAILABLE = True
except ImportError:
    TIME_SERIES_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# 고급 특성 추출기
# =============================================================================

class AdvancedFeatureExtractor:
    """고급 특성 추출 및 엔지니어링"""
    
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.feature_history = deque(maxlen=window_size)
        self.baseline_stats = {}
        self.anomaly_scores = deque(maxlen=100)
        
    async def extract_advanced_features(self, 
                                      network_data: Dict, 
                                      system_data: Dict, 
                                      mavlink_data: Dict) -> Dict[str, Any]:
        """고급 특성 추출"""
        
        # 기본 특성
        basic_features = await self._extract_basic_features(network_data, system_data, mavlink_data)
        
        # 시계열 특성
        temporal_features = await self._extract_temporal_features(basic_features)
        
        # 통계적 특성
        statistical_features = await self._extract_statistical_features(basic_features)
        
        # 네트워크 그래프 특성
        graph_features = await self._extract_graph_features(network_data)
        
        # 주파수 도메인 특성
        frequency_features = await self._extract_frequency_features(basic_features)
        
        # 엔트로피 특성
        entropy_features = await self._extract_entropy_features(network_data, mavlink_data)
        
        # 모든 특성 결합
        combined_features = {
            **basic_features,
            **temporal_features,
            **statistical_features,
            **graph_features,
            **frequency_features,
            **entropy_features
        }
        
        # 특성 이력 업데이트
        self.feature_history.append(combined_features)
        
        return combined_features
    
    async def _extract_basic_features(self, network_data: Dict, system_data: Dict, mavlink_data: Dict) -> Dict[str, Any]:
        """기본 특성 추출"""
        return {
            # 네트워크 메트릭
            'packet_count': len(network_data.get('packets', [])),
            'unique_src_ips': len(set(p.get('src_ip', '') for p in network_data.get('packets', []))),
            'unique_dst_ips': len(set(p.get('dst_ip', '') for p in network_data.get('packets', []))),
            'avg_packet_size': np.mean([p.get('size', 0) for p in network_data.get('packets', [])]) if network_data.get('packets') else 0,
            'total_bytes': sum(p.get('size', 0) for p in network_data.get('packets', [])),
            
            # 시스템 메트릭
            'cpu_usage': system_data.get('cpu_usage', 0),
            'memory_usage': system_data.get('memory_usage', 0),
            'disk_io': system_data.get('disk_io_rate', 0),
            'network_io': system_data.get('network_io_rate', 0),
            
            # MAVLink 메트릭
            'mavlink_msg_count': len(mavlink_data.get('commands', [])),
            'gps_points': len(mavlink_data.get('gps_data', [])),
            'param_requests': len([c for c in mavlink_data.get('commands', []) if 'PARAM' in c.get('type', '')]),
        }
    
    async def _extract_temporal_features(self, current_features: Dict[str, Any]) -> Dict[str, Any]:
        """시계열 기반 특성"""
        if len(self.feature_history) < 2:
            return {
                'trend_cpu': 0.0,
                'trend_memory': 0.0,
                'trend_network': 0.0,
                'volatility_cpu': 0.0,
                'volatility_memory': 0.0,
                'change_rate_packets': 0.0,
                'autocorr_cpu': 0.0,
                'seasonality_score': 0.0
            }
        
        # 시계열 데이터 준비
        cpu_series = [f.get('cpu_usage', 0) for f in self.feature_history]
        memory_series = [f.get('memory_usage', 0) for f in self.feature_history]
        packet_series = [f.get('packet_count', 0) for f in self.feature_history]
        
        features = {}
        
        # 트렌드 분석
        if len(cpu_series) >= 3:
            features['trend_cpu'] = self._calculate_trend(cpu_series)
            features['trend_memory'] = self._calculate_trend(memory_series)
            features['trend_network'] = self._calculate_trend(packet_series)
        
        # 변동성 (표준편차)
        features['volatility_cpu'] = np.std(cpu_series) if len(cpu_series) > 1 else 0
        features['volatility_memory'] = np.std(memory_series) if len(memory_series) > 1 else 0
        
        # 변화율
        if len(packet_series) >= 2:
            features['change_rate_packets'] = (packet_series[-1] - packet_series[-2]) / max(packet_series[-2], 1)
        else:
            features['change_rate_packets'] = 0
        
        # 자기상관
        if len(cpu_series) >= 3:
            features['autocorr_cpu'] = self._calculate_autocorrelation(cpu_series, lag=1)
        else:
            features['autocorr_cpu'] = 0
        
        # 계절성 점수 (간단한 주기성 탐지)
        features['seasonality_score'] = self._detect_seasonality(cpu_series)
        
        return features
    
    def _calculate_trend(self, series: List[float]) -> float:
        """선형 트렌드 계산"""
        if len(series) < 2:
            return 0.0
        
        x = np.arange(len(series))
        try:
            slope, _, r_value, _, _ = stats.linregress(x, series)
            return slope * r_value  # 기울기 × 상관계수
        except:
            return 0.0
    
    def _calculate_autocorrelation(self, series: List[float], lag: int = 1) -> float:
        """자기상관 계산"""
        if len(series) <= lag:
            return 0.0
        
        try:
            return np.corrcoef(series[:-lag], series[lag:])[0, 1]
        except:
            return 0.0
    
    def _detect_seasonality(self, series: List[float]) -> float:
        """계절성/주기성 탐지"""
        if len(series) < 4:
            return 0.0
        
        try:
            # FFT를 이용한 주요 주파수 성분 탐지
            fft_values = np.fft.fft(series)
            freqs = np.fft.fftfreq(len(series))
            
            # 가장 강한 주파수 성분의 파워
            power_spectrum = np.abs(fft_values) ** 2
            max_power_idx = np.argmax(power_spectrum[1:len(power_spectrum)//2]) + 1
            
            return power_spectrum[max_power_idx] / np.sum(power_spectrum)
        except:
            return 0.0
    
    async def _extract_statistical_features(self, current_features: Dict[str, Any]) -> Dict[str, Any]:
        """통계적 특성"""
        if len(self.feature_history) < 3:
            return {
                'mean_cpu': current_features.get('cpu_usage', 0),
                'std_cpu': 0.0,
                'skewness_cpu': 0.0,
                'kurtosis_cpu': 0.0,
                'percentile_95_memory': current_features.get('memory_usage', 0),
                'iqr_packets': 0.0,
                'zscore_cpu': 0.0,
                'outlier_score': 0.0
            }
        
        # 시계열 데이터
        cpu_values = [f.get('cpu_usage', 0) for f in self.feature_history]
        memory_values = [f.get('memory_usage', 0) for f in self.feature_history]
        packet_values = [f.get('packet_count', 0) for f in self.feature_history]
        
        features = {}
        
        # 기본 통계량
        features['mean_cpu'] = np.mean(cpu_values)
        features['std_cpu'] = np.std(cpu_values)
        
        # 분포 특성
        try:
            features['skewness_cpu'] = stats.skew(cpu_values) if len(cpu_values) > 2 else 0
            features['kurtosis_cpu'] = stats.kurtosis(cpu_values) if len(cpu_values) > 2 else 0
        except:
            features['skewness_cpu'] = 0
            features['kurtosis_cpu'] = 0
        
        # 백분위수
        features['percentile_95_memory'] = np.percentile(memory_values, 95) if memory_values else 0
        
        # IQR (Interquartile Range)
        if len(packet_values) > 0:
            q75, q25 = np.percentile(packet_values, [75, 25])
            features['iqr_packets'] = q75 - q25
        else:
            features['iqr_packets'] = 0
        
        # Z-Score (현재 값이 얼마나 이상한지)
        current_cpu = current_features.get('cpu_usage', 0)
        if features['std_cpu'] > 0:
            features['zscore_cpu'] = (current_cpu - features['mean_cpu']) / features['std_cpu']
        else:
            features['zscore_cpu'] = 0
        
        # 이상치 점수 (Modified Z-Score 사용)
        features['outlier_score'] = self._calculate_outlier_score(cpu_values, current_cpu)
        
        return features
    
    def _calculate_outlier_score(self, series: List[float], current_value: float) -> float:
        """이상치 점수 계산"""
        if len(series) < 3:
            return 0.0
        
        try:
            median = np.median(series)
            mad = np.median([abs(x - median) for x in series])  # Median Absolute Deviation
            
            if mad == 0:
                return 0.0
            
            modified_z_score = 0.6745 * (current_value - median) / mad
            return abs(modified_z_score)
        except:
            return 0.0
    
    async def _extract_graph_features(self, network_data: Dict) -> Dict[str, Any]:
        """네트워크 그래프 특성"""
        packets = network_data.get('packets', [])
        
        if not packets:
            return {
                'node_count': 0,
                'edge_count': 0,
                'avg_degree': 0.0,
                'clustering_coefficient': 0.0,
                'network_density': 0.0,
                'max_degree': 0,
                'isolated_nodes': 0
            }
        
        # 네트워크 그래프 구성
        nodes = set()
        edges = {}
        
        for packet in packets:
            src = packet.get('src_ip', '')
            dst = packet.get('dst_ip', '')
            
            if src and dst:
                nodes.add(src)
                nodes.add(dst)
                
                edge_key = (src, dst)
                edges[edge_key] = edges.get(edge_key, 0) + 1
        
        node_count = len(nodes)
        edge_count = len(edges)
        
        if node_count == 0:
            return {
                'node_count': 0,
                'edge_count': 0,
                'avg_degree': 0.0,
                'clustering_coefficient': 0.0,
                'network_density': 0.0,
                'max_degree': 0,
                'isolated_nodes': 0
            }
        
        # 차수 계산
        degrees = {node: 0 for node in nodes}
        for (src, dst), weight in edges.items():
            degrees[src] += weight
            degrees[dst] += weight
        
        degree_values = list(degrees.values())
        
        features = {
            'node_count': node_count,
            'edge_count': edge_count,
            'avg_degree': np.mean(degree_values) if degree_values else 0,
            'max_degree': max(degree_values) if degree_values else 0,
            'isolated_nodes': sum(1 for d in degree_values if d == 0)
        }
        
        # 네트워크 밀도
        max_possible_edges = node_count * (node_count - 1) / 2
        features['network_density'] = edge_count / max_possible_edges if max_possible_edges > 0 else 0
        
        # 간단한 클러스터링 계수 (근사값)
        features['clustering_coefficient'] = self._estimate_clustering_coefficient(edges, nodes)
        
        return features
    
    def _estimate_clustering_coefficient(self, edges: Dict, nodes: set) -> float:
        """클러스터링 계수 추정"""
        if len(nodes) < 3:
            return 0.0
        
        # 각 노드의 이웃 찾기
        neighbors = {node: set() for node in nodes}
        for (src, dst) in edges.keys():
            neighbors[src].add(dst)
            neighbors[dst].add(src)
        
        clustering_sum = 0.0
        valid_nodes = 0
        
        for node in nodes:
            node_neighbors = neighbors[node]
            if len(node_neighbors) < 2:
                continue
            
            # 이웃 간 연결 수 계산
            triangles = 0
            possible_triangles = len(node_neighbors) * (len(node_neighbors) - 1) / 2
            
            for neighbor1 in node_neighbors:
                for neighbor2 in node_neighbors:
                    if neighbor1 < neighbor2 and neighbor2 in neighbors[neighbor1]:
                        triangles += 1
            
            if possible_triangles > 0:
                clustering_sum += triangles / possible_triangles
                valid_nodes += 1
        
        return clustering_sum / valid_nodes if valid_nodes > 0 else 0.0
    
    async def _extract_frequency_features(self, current_features: Dict[str, Any]) -> Dict[str, Any]:
        """주파수 도메인 특성"""
        if len(self.feature_history) < 4:
            return {
                'dominant_frequency': 0.0,
                'spectral_entropy': 0.0,
                'power_ratio_low': 0.0,
                'power_ratio_high': 0.0,
                'spectral_centroid': 0.0
            }
        
        # CPU 사용률 시계열
        cpu_series = np.array([f.get('cpu_usage', 0) for f in self.feature_history])
        
        try:
            # FFT 분석
            fft_values = np.fft.fft(cpu_series)
            freqs = np.fft.fftfreq(len(cpu_series))
            power_spectrum = np.abs(fft_values) ** 2
            
            # 주파수 특성
            features = {}
            
            # 지배적 주파수
            positive_freqs = freqs[:len(freqs)//2]
            positive_power = power_spectrum[:len(power_spectrum)//2]
            
            if len(positive_power) > 1:
                dominant_idx = np.argmax(positive_power[1:]) + 1  # DC 성분 제외
                features['dominant_frequency'] = abs(positive_freqs[dominant_idx])
            else:
                features['dominant_frequency'] = 0.0
            
            # 스펙트럼 엔트로피
            normalized_power = positive_power / (np.sum(positive_power) + 1e-10)
            features['spectral_entropy'] = -np.sum(normalized_power * np.log2(normalized_power + 1e-10))
            
            # 저주파/고주파 파워 비율
            mid_point = len(positive_power) // 2
            low_power = np.sum(positive_power[:mid_point])
            high_power = np.sum(positive_power[mid_point:])
            total_power = low_power + high_power
            
            features['power_ratio_low'] = low_power / (total_power + 1e-10)
            features['power_ratio_high'] = high_power / (total_power + 1e-10)
            
            # 스펙트럼 중심
            if np.sum(positive_power) > 0:
                features['spectral_centroid'] = np.sum(positive_freqs * positive_power) / np.sum(positive_power)
            else:
                features['spectral_centroid'] = 0.0
            
            return features
            
        except Exception as e:
            logger.warning(f"주파수 특성 추출 실패: {e}")
            return {
                'dominant_frequency': 0.0,
                'spectral_entropy': 0.0,
                'power_ratio_low': 0.0,
                'power_ratio_high': 0.0,
                'spectral_centroid': 0.0
            }
    
    async def _extract_entropy_features(self, network_data: Dict, mavlink_data: Dict) -> Dict[str, Any]:
        """엔트로피 기반 특성"""
        features = {}
        
        # 네트워크 패킷 크기 엔트로피
        packet_sizes = [p.get('size', 0) for p in network_data.get('packets', [])]
        features['packet_size_entropy'] = self._calculate_entropy(packet_sizes)
        
        # 포트 분포 엔트로피
        dst_ports = [p.get('dst_port', 0) for p in network_data.get('packets', [])]
        features['port_entropy'] = self._calculate_entropy(dst_ports)
        
        # 프로토콜 분포 엔트로피
        protocols = [p.get('protocol', '') for p in network_data.get('packets', [])]
        features['protocol_entropy'] = self._calculate_entropy(protocols)
        
        # MAVLink 명령 타입 엔트로피
        command_types = [c.get('type', '') for c in mavlink_data.get('commands', [])]
        features['command_type_entropy'] = self._calculate_entropy(command_types)
        
        # 시간 간격 엔트로피
        timestamps = [p.get('timestamp', 0) for p in network_data.get('packets', [])]
        if len(timestamps) > 1:
            intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
            features['time_interval_entropy'] = self._calculate_entropy(intervals)
        else:
            features['time_interval_entropy'] = 0.0
        
        return features
    
    def _calculate_entropy(self, data: List[Union[int, float, str]]) -> float:
        """샤논 엔트로피 계산"""
        if not data:
            return 0.0
        
        # 빈도 계산
        from collections import Counter
        counts = Counter(data)
        total = len(data)
        
        # 엔트로피 계산
        entropy = 0.0
        for count in counts.values():
            probability = count / total
            if probability > 0:
                entropy -= probability * np.log2(probability)
        
        return entropy

# =============================================================================
# 딥러닝 모델
# =============================================================================

class DeepLearningDetector:
    """딥러닝 기반 공격 탐지 모델"""
    
    def __init__(self, sequence_length: int = 10):
        self.sequence_length = sequence_length
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.is_trained = False
        self.history = deque(maxlen=sequence_length)
        
    async def build_lstm_model(self, input_shape: Tuple[int, int]) -> None:
        """LSTM 기반 모델 구축"""
        if not DEEP_LEARNING_AVAILABLE:
            raise ImportError("TensorFlow가 설치되지 않았습니다")
        
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation='relu'),
            BatchNormalization(),
            Dense(7, activation='softmax')  # 7개 클래스 (benign + 6 attack types)
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        self.model = model
    
    async def build_cnn_model(self, input_shape: Tuple[int, int]) -> None:
        """CNN 기반 모델 구축"""
        if not DEEP_LEARNING_AVAILABLE:
            raise ImportError("TensorFlow가 설치되지 않았습니다")
        
        model = Sequential([
            Conv1D(64, 3, activation='relu', input_shape=input_shape),
            Conv1D(32, 3, activation='relu'),
            Dropout(0.2),
            Conv1D(16, 3, activation='relu'),
            tf.keras.layers.GlobalMaxPooling1D(),
            Dense(32, activation='relu'),
            BatchNormalization(),
            Dropout(0.3),
            Dense(7, activation='softmax')
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        self.model = model
    
    async def train(self, features: List[Dict], labels: List[str], model_type: str = 'lstm') -> Dict[str, Any]:
        """딥러닝 모델 학습"""
        if not DEEP_LEARNING_AVAILABLE:
            raise ImportError("TensorFlow가 설치되지 않았습니다")
        
        # 데이터 준비
        df = pd.DataFrame(features)
        numeric_features = df.select_dtypes(include=[np.number]).columns
        X = df[numeric_features].fillna(0).values
        
        # 라벨 인코딩
        label_map = {
            'benign': 0, 'reconnaissance': 1, 'protocol_tampering': 2,
            'denial_of_service': 3, 'injection': 4, 'exfiltration': 5, 'firmware_attacks': 6
        }
        y = np.array([label_map.get(label, 0) for label in labels])
        
        # 정규화
        from sklearn.preprocessing import StandardScaler
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # 시퀀스 데이터 생성
        X_sequences, y_sequences = self._create_sequences(X_scaled, y)
        
        if len(X_sequences) == 0:
            raise ValueError("시퀀스 데이터가 충분하지 않습니다")
        
        # 모델 구축
        input_shape = (X_sequences.shape[1], X_sequences.shape[2])
        
        if model_type == 'lstm':
            await self.build_lstm_model(input_shape)
        elif model_type == 'cnn':
            await self.build_cnn_model(input_shape)
        else:
            raise ValueError("지원하지 않는 모델 타입")
        
        # 학습/검증 분할
        split_idx = int(0.8 * len(X_sequences))
        X_train, X_val = X_sequences[:split_idx], X_sequences[split_idx:]
        y_train, y_val = y_sequences[:split_idx], y_sequences[split_idx:]
        
        # 콜백 설정
        callbacks = [
            EarlyStopping(patience=10, restore_best_weights=True),
            ReduceLROnPlateau(patience=5, factor=0.5)
        ]
        
        # 모델 학습
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=50,
            batch_size=32,
            callbacks=callbacks,
            verbose=0
        )
        
        self.is_trained = True
        self.feature_names = numeric_features.tolist()
        
        # 성능 평가
        val_loss, val_accuracy = self.model.evaluate(X_val, y_val, verbose=0)
        
        return {
            'val_accuracy': val_accuracy,
            'val_loss': val_loss,
            'epochs_trained': len(history.history['loss']),
            'model_type': model_type,
            'sequence_length': self.sequence_length,
            'n_features': X_sequences.shape[2]
        }
    
    def _create_sequences(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """시퀀스 데이터 생성"""
        sequences = []
        labels = []
        
        for i in range(len(X) - self.sequence_length + 1):
            sequences.append(X[i:i + self.sequence_length])
            labels.append(y[i + self.sequence_length - 1])  # 마지막 시점의 라벨
        
        return np.array(sequences), np.array(labels)
    
    async def predict(self, features: Dict) -> Dict[str, Any]:
        """딥러닝 예측"""
        if not self.is_trained:
            raise ValueError("모델이 학습되지 않았습니다")
        
        # 특성 준비
        df = pd.DataFrame([features])
        numeric_features = [f for f in self.feature_names if f in df.columns]
        X = df[numeric_features].fillna(0).values
        
        # 정규화
        X_scaled = self.scaler.transform(X)
        
        # 히스토리에 추가
        self.history.append(X_scaled[0])
        
        if len(self.history) < self.sequence_length:
            # 충분한 히스토리가 없으면 패딩
            padded_history = np.zeros((self.sequence_length, len(X_scaled[0])))
            for i, hist in enumerate(self.history):
                padded_history[-(i+1)] = hist
        else:
            padded_history = np.array(list(self.history))
        
        # 예측
        X_seq = padded_history.reshape(1, self.sequence_length, -1)
        predictions = self.model.predict(X_seq, verbose=0)[0]
        
        # 결과 해석
        class_names = ['benign', 'reconnaissance', 'protocol_tampering', 
                      'denial_of_service', 'injection', 'exfiltration', 'firmware_attacks']
        
        predicted_class_idx = np.argmax(predictions)
        confidence = predictions[predicted_class_idx]
        predicted_class = class_names[predicted_class_idx]
        
        return {
            'predicted_class': predicted_class,
            'confidence': float(confidence),
            'class_probabilities': {name: float(prob) for name, prob in zip(class_names, predictions)},
            'attack_detected': predicted_class != 'benign'
        }

# =============================================================================
# 온라인 학습 모델
# =============================================================================

class OnlineLearningDetector:
    """온라인 학습 기반 적응형 탐지"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.feature_buffer = deque(maxlen=window_size)
        self.label_buffer = deque(maxlen=window_size)
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.retrain_threshold = 100  # 새 데이터 100개마다 재학습
        self.new_samples_count = 0
        
    async def initialize_model(self):
        """초기 모델 설정"""
        from sklearn.linear_model import SGDClassifier
        
        self.model = SGDClassifier(
            loss='log',  # 로지스틱 회귀
            learning_rate='adaptive',
            eta0=0.01,
            random_state=42
        )
    
    async def update_model(self, features: Dict, true_label: str):
        """새로운 데이터로 모델 업데이트"""
        if self.model is None:
            await self.initialize_model()
        
        # 데이터 버퍼에 추가
        self.feature_buffer.append(features)
        self.label_buffer.append(true_label)
        self.new_samples_count += 1
        
        # 충분한 데이터가 있으면 재학습
        if len(self.feature_buffer) >= 10 and self.new_samples_count >= self.retrain_threshold:
            await self._retrain_model()
            self.new_samples_count = 0
    
    async def _retrain_model(self):
        """모델 재학습"""
        # 버퍼에서 데이터 준비
        df = pd.DataFrame(list(self.feature_buffer))
        numeric_features = df.select_dtypes(include=[np.number]).columns
        X = df[numeric_features].fillna(0)
        
        # 라벨 인코딩
        label_map = {
            'benign': 0, 'reconnaissance': 1, 'protocol_tampering': 2,
            'denial_of_service': 3, 'injection': 4, 'exfiltration': 5, 'firmware_attacks': 6
        }
        y = np.array([label_map.get(label, 0) for label in self.label_buffer])
        
        # 스케일링
        if not self.is_trained:
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            self.is_trained = True
        else:
            X_scaled = self.scaler.transform(X)
            # 부분 학습 (온라인 학습)
            self.model.partial_fit(X_scaled, y)
        
        logger.info(f"온라인 학습 완료: {len(X)} 샘플")
    
    async def predict(self, features: Dict) -> Dict[str, Any]:
        """예측 수행"""
        if not self.is_trained:
            return {
                'predicted_class': 'benign',
                'confidence': 0.5,
                'attack_detected': False,
                'message': '모델이 아직 학습되지 않았습니다'
            }
        
        # 특성 준비
        df = pd.DataFrame([features])
        numeric_features = df.select_dtypes(include=[np.number]).columns
        X = df[numeric_features].fillna(0)
        X_scaled = self.scaler.transform(X)
        
        # 예측
        prediction = self.model.predict(X_scaled)[0]
        probabilities = self.model.predict_proba(X_scaled)[0] if hasattr(self.model, 'predict_proba') else None
        
        class_names = ['benign', 'reconnaissance', 'protocol_tampering', 
                      'denial_of_service', 'injection', 'exfiltration', 'firmware_attacks']
        
        predicted_class = class_names[prediction]
        confidence = probabilities[prediction] if probabilities is not None else 0.7
        
        return {
            'predicted_class': predicted_class,
            'confidence': float(confidence),
            'attack_detected': predicted_class != 'benign',
            'model_confidence': float(confidence)
        }

# =============================================================================
# 하이브리드 앙상블 탐지기
# =============================================================================

class HybridEnsembleDetector:
    """전통적 ML + 딥러닝 + 온라인 학습 하이브리드"""
    
    def __init__(self):
        self.traditional_models = {}
        self.deep_model = DeepLearningDetector()
        self.online_model = OnlineLearningDetector()
        self.feature_extractor = AdvancedFeatureExtractor()
        self.model_weights = {
            'random_forest': 0.25,
            'gradient_boosting': 0.25,
            'deep_learning': 0.30,
            'online_learning': 0.20
        }
        self.performance_tracker = {}
        
    async def initialize_traditional_models(self):
        """전통적 ML 모델 초기화"""
        self.traditional_models = {
            'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'gradient_boosting': GradientBoostingClassifier(random_state=42),
            'extra_trees': ExtraTreesClassifier(n_estimators=100, random_state=42),
            'logistic_regression': LogisticRegression(random_state=42, max_iter=1000)
        }
    
    async def train_all_models(self, features: List[Dict], labels: List[str]) -> Dict[str, Any]:
        """모든 모델 학습"""
        training_results = {}
        
        # 전통적 모델 초기화
        await self.initialize_traditional_models()
        
        # 데이터 준비
        df = pd.DataFrame(features)
        numeric_features = df.select_dtypes(include=[np.number]).columns
        X = df[numeric_features].fillna(0)
        
        # 라벨 인코딩
        from sklearn.preprocessing import LabelEncoder
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(labels)
        
        # 전통적 모델들 학습
        for name, model in self.traditional_models.items():
            try:
                model.fit(X, y)
                training_results[name] = {'status': 'success'}
                logger.info(f"{name} 학습 완료")
            except Exception as e:
                training_results[name] = {'status': 'failed', 'error': str(e)}
                logger.error(f"{name} 학습 실패: {e}")
        
        # 딥러닝 모델 학습
        if DEEP_LEARNING_AVAILABLE:
            try:
                dl_result = await self.deep_model.train(features, labels, model_type='lstm')
                training_results['deep_learning'] = dl_result
                logger.info("딥러닝 모델 학습 완료")
            except Exception as e:
                training_results['deep_learning'] = {'status': 'failed', 'error': str(e)}
                logger.error(f"딥러닝 학습 실패: {e}")
        
        # 온라인 학습 모델 초기화
        await self.online_model.initialize_model()
        training_results['online_learning'] = {'status': 'initialized'}
        
        return training_results
    
    async def predict_ensemble(self, features: Dict) -> Dict[str, Any]:
        """하이브리드 앙상블 예측"""
        predictions = {}
        
        # 고급 특성 추출
        enhanced_features = await self.feature_extractor.extract_advanced_features(
            features.get('network_data', {}),
            features.get('system_data', {}),
            features.get('mavlink_data', {})
        )
        
        # 전통적 모델 예측
        for name, model in self.traditional_models.items():
            try:
                df = pd.DataFrame([enhanced_features])
                numeric_features = df.select_dtypes(include=[np.number]).columns
                X = df[numeric_features].fillna(0)
                
                prediction = model.predict(X)[0]
                confidence = max(model.predict_proba(X)[0]) if hasattr(model, 'predict_proba') else 0.7
                
                predictions[name] = {
                    'prediction': prediction,
                    'confidence': confidence
                }
            except Exception as e:
                logger.warning(f"{name} 예측 실패: {e}")
        
        # 딥러닝 예측
        if self.deep_model.is_trained:
            try:
                dl_result = await self.deep_model.predict(enhanced_features)
                predictions['deep_learning'] = {
                    'prediction': dl_result['predicted_class'],
                    'confidence': dl_result['confidence']
                }
            except Exception as e:
                logger.warning(f"딥러닝 예측 실패: {e}")
        
        # 온라인 학습 예측
        if self.online_model.is_trained:
            try:
                ol_result = await self.online_model.predict(enhanced_features)
                predictions['online_learning'] = {
                    'prediction': ol_result['predicted_class'],
                    'confidence': ol_result['confidence']
                }
            except Exception as e:
                logger.warning(f"온라인 학습 예측 실패: {e}")
        
        # 앙상블 결정
        final_result = await self._ensemble_decision(predictions, enhanced_features)
        
        return final_result
    
    async def _ensemble_decision(self, predictions: Dict, features: Dict) -> Dict[str, Any]:
        """앙상블 최종 결정"""
        if not predictions:
            return {
                'attack_detected': False,
                'predicted_class': 'benign',
                'confidence': 0.5,
                'ensemble_details': {}
            }
        
        # 가중 평균 계산
        weighted_confidences = {}
        total_weight = 0
        
        for model_name, pred_data in predictions.items():
            weight = self.model_weights.get(model_name, 0.25)
            predicted_class = pred_data['prediction']
            confidence = pred_data['confidence']
            
            if predicted_class not in weighted_confidences:
                weighted_confidences[predicted_class] = 0
            
            weighted_confidences[predicted_class] += weight * confidence
            total_weight += weight
        
        # 정규화
        if total_weight > 0:
            for class_name in weighted_confidences:
                weighted_confidences[class_name] /= total_weight
        
        # 최종 예측
        if weighted_confidences:
            final_class = max(weighted_confidences.keys(), key=lambda x: weighted_confidences[x])
            final_confidence = weighted_confidences[final_class]
        else:
            final_class = 'benign'
            final_confidence = 0.5
        
        return {
            'attack_detected': final_class != 'benign',
            'predicted_class': final_class,
            'confidence': final_confidence,
            'class_confidences': weighted_confidences,
            'individual_predictions': predictions,
            'model_count': len(predictions),
            'features_analyzed': len(features)
        }
    
    async def adaptive_weight_update(self, true_label: str, predictions: Dict):
        """적응형 가중치 업데이트"""
        # 각 모델의 정확도 추적
        for model_name, pred_data in predictions.items():
            if model_name not in self.performance_tracker:
                self.performance_tracker[model_name] = {'correct': 0, 'total': 0}
            
            self.performance_tracker[model_name]['total'] += 1
            if pred_data['prediction'] == true_label:
                self.performance_tracker[model_name]['correct'] += 1
        
        # 성능 기반 가중치 조정
        for model_name in self.performance_tracker:
            tracker = self.performance_tracker[model_name]
            if tracker['total'] > 10:  # 충분한 샘플이 있을 때만
                accuracy = tracker['correct'] / tracker['total']
                # 성능이 좋은 모델의 가중치 증가
                if accuracy > 0.8:
                    self.model_weights[model_name] = min(0.4, self.model_weights.get(model_name, 0.25) * 1.1)
                elif accuracy < 0.6:
                    self.model_weights[model_name] = max(0.1, self.model_weights.get(model_name, 0.25) * 0.9)
        
        # 가중치 정규화
        total_weight = sum(self.model_weights.values())
        if total_weight > 0:
            for model_name in self.model_weights:
                self.model_weights[model_name] /= total_weight

# =============================================================================
# 성능 분석기
# =============================================================================

class PerformanceAnalyzer:
    """모델 성능 분석 및 최적화"""
    
    def __init__(self):
        self.metrics_history = []
        self.benchmark_results = {}
        
    async def comprehensive_evaluation(self, model, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        """종합적인 모델 평가"""
        from sklearn.metrics import (
            accuracy_score, precision_recall_fscore_support,
            confusion_matrix, roc_auc_score, classification_report
        )
        
        # 예측
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
        
        # 기본 메트릭
        accuracy = accuracy_score(y_test, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='weighted')
        
        # 혼동 행렬
        cm = confusion_matrix(y_test, y_pred)
        
        # ROC AUC (다중 클래스인 경우 ovr 방식)
        try:
            if y_pred_proba is not None and len(np.unique(y_test)) > 2:
                auc = roc_auc_score(y_test, y_pred_proba, multi_class='ovr')
            elif y_pred_proba is not None:
                auc = roc_auc_score(y_test, y_pred_proba[:, 1])
            else:
                auc = 0.0
        except:
            auc = 0.0
        
        # 클래스별 성능
        class_report = classification_report(y_test, y_pred, output_dict=True)
        
        # 탐지 성능 (공격 vs 정상)
        binary_y_test = (y_test > 0).astype(int)  # 0은 정상, 나머지는 공격
        binary_y_pred = (y_pred > 0).astype(int)
        
        detection_accuracy = accuracy_score(binary_y_test, binary_y_pred)
        detection_precision, detection_recall, detection_f1, _ = precision_recall_fscore_support(
            binary_y_test, binary_y_pred, average='binary'
        )
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'auc_score': auc,
            'confusion_matrix': cm.tolist(),
            'classification_report': class_report,
            'detection_metrics': {
                'accuracy': detection_accuracy,
                'precision': detection_precision,
                'recall': detection_recall,
                'f1_score': detection_f1
            }
        }
    
    async def benchmark_models(self, models: Dict, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """모델 벤치마크"""
        from sklearn.model_selection import cross_val_score
        import time
        
        results = {}
        
        for model_name, model in models.items():
            start_time = time.time()
            
            try:
                # 교차 검증
                cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
                
                # 훈련 시간
                model.fit(X, y)
                training_time = time.time() - start_time
                
                # 예측 시간
                pred_start = time.time()
                _ = model.predict(X[:100])  # 100개 샘플 예측
                prediction_time = (time.time() - pred_start) / 100 * 1000  # ms per sample
                
                results[model_name] = {
                    'cv_accuracy_mean': cv_scores.mean(),
                    'cv_accuracy_std': cv_scores.std(),
                    'training_time_seconds': training_time,
                    'prediction_time_ms': prediction_time,
                    'model_size_mb': self._estimate_model_size(model)
                }
                
            except Exception as e:
                results[model_name] = {'error': str(e)}
        
        return results
    
    def _estimate_model_size(self, model) -> float:
        """모델 크기 추정 (MB)"""
        try:
            import pickle
            model_bytes = pickle.dumps(model)
            return len(model_bytes) / (1024 * 1024)
        except:
            return 0.0
    
    async def feature_importance_analysis(self, models: Dict, feature_names: List[str]) -> Dict[str, Any]:
        """특성 중요도 분석"""
        importance_results = {}
        
        for model_name, model in models.items():
            try:
                if hasattr(model, 'feature_importances_'):
                    # Tree-based 모델
                    importances = model.feature_importances_
                elif hasattr(model, 'coef_'):
                    # Linear 모델
                    importances = np.abs(model.coef_[0] if len(model.coef_.shape) > 1 else model.coef_)
                else:
                    continue
                
                # 상위 특성들
                feature_importance = list(zip(feature_names, importances))
                feature_importance.sort(key=lambda x: x[1], reverse=True)
                
                importance_results[model_name] = {
                    'top_features': feature_importance[:10],
                    'all_importances': dict(feature_importance)
                }
                
            except Exception as e:
                importance_results[model_name] = {'error': str(e)}
        
        return importance_results

# =============================================================================
# 실시간 모니터링 대시보드
# =============================================================================

class RealTimeMonitoringDashboard:
    """실시간 모니터링 및 시각화"""
    
    def __init__(self):
        self.metrics_buffer = deque(maxlen=1000)
        self.alert_buffer = deque(maxlen=100)
        
    async def update_metrics(self, detection_result: Dict):
        """메트릭 업데이트"""
        timestamp = datetime.now()
        
        metric_entry = {
            'timestamp': timestamp,
            'attack_detected': detection_result.get('attack_detected', False),
            'confidence': detection_result.get('confidence', 0),
            'predicted_class': detection_result.get('predicted_class', 'benign'),
            'model_used': detection_result.get('model_used', 'unknown'),
            'detection_time_ms': detection_result.get('detection_time_ms', 0)
        }
        
        self.metrics_buffer.append(metric_entry)
        
        # 알림 조건 확인
        if detection_result.get('attack_detected', False) and detection_result.get('confidence', 0) > 0.8:
            alert_entry = {
                'timestamp': timestamp,
                'type': 'high_confidence_attack',
                'details': detection_result
            }
            self.alert_buffer.append(alert_entry)
    
    async def generate_dashboard_data(self) -> Dict[str, Any]:
        """대시보드 데이터 생성"""
        if not self.metrics_buffer:
            return {'message': '데이터 없음'}
        
        # 최근 메트릭
        recent_metrics = list(self.metrics_buffer)[-100:]
        
        # 통계 계산
        total_detections = len(recent_metrics)
        attack_detections = sum(1 for m in recent_metrics if m['attack_detected'])
        avg_confidence = np.mean([m['confidence'] for m in recent_metrics])
        avg_detection_time = np.mean([m['detection_time_ms'] for m in recent_metrics])
        
        # 시간별 추세
        hourly_stats = self._calculate_hourly_trends(recent_metrics)
        
        # 공격 타입별 분포
        attack_distribution = self._calculate_attack_distribution(recent_metrics)
        
        # 최근 알림
        recent_alerts = list(self.alert_buffer)[-20:]
        
        return {
            'summary': {
                'total_detections': total_detections,
                'attack_detections': attack_detections,
                'attack_rate': (attack_detections / total_detections * 100) if total_detections > 0 else 0,
                'avg_confidence': avg_confidence,
                'avg_detection_time_ms': avg_detection_time
            },
            'trends': hourly_stats,
            'attack_distribution': attack_distribution,
            'recent_alerts': recent_alerts,
            'system_health': self._assess_system_health(recent_metrics)
        }
    
    def _calculate_hourly_trends(self, metrics: List[Dict]) -> List[Dict]:
        """시간별 추세 계산"""
        from collections import defaultdict
        
        hourly_data = defaultdict(lambda: {'total': 0, 'attacks': 0})
        
        for metric in metrics:
            hour = metric['timestamp'].replace(minute=0, second=0, microsecond=0)
            hourly_data[hour]['total'] += 1
            if metric['attack_detected']:
                hourly_data[hour]['attacks'] += 1
        
        return [
            {
                'hour': hour.isoformat(),
                'total_detections': data['total'],
                'attack_detections': data['attacks'],
                'attack_rate': (data['attacks'] / data['total'] * 100) if data['total'] > 0 else 0
            }
            for hour, data in sorted(hourly_data.items())
        ]
    
    def _calculate_attack_distribution(self, metrics: List[Dict]) -> Dict[str, int]:
        """공격 타입별 분포"""
        from collections import Counter
        
        attack_types = [m['predicted_class'] for m in metrics if m['attack_detected']]
        return dict(Counter(attack_types))
    
    def _assess_system_health(self, metrics: List[Dict]) -> Dict[str, Any]:
        """시스템 건강도 평가"""
        if not metrics:
            return {'status': 'unknown'}
        
        # 최근 성능 지표
        recent_times = [m['detection_time_ms'] for m in metrics[-20:]]
        avg_response_time = np.mean(recent_times)
        
        # 상태 결정
        if avg_response_time < 100:
            status = 'excellent'
        elif avg_response_time < 500:
            status = 'good'
        elif avg_response_time < 1000:
            status = 'fair'
        else:
            status = 'poor'
        
        return {
            'status': status,
            'avg_response_time_ms': avg_response_time,
            'last_update': metrics[-1]['timestamp'].isoformat(),
            'uptime_minutes': (datetime.now() - metrics[0]['timestamp']).total_seconds() / 60
        }