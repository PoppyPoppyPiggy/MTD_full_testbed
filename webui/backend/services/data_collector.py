import sqlite3
import threading
import time
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

class DataCollector:
    def __init__(self):
        self.running = False
        self.db_path = '../attack_output/unified_metrics.db'
        
    def start(self):
        """데이터 수집 시작"""
        self.running = True
        threading.Thread(target=self._collect_loop, daemon=True).start()
    
    def stop(self):
        """데이터 수집 중지"""
        self.running = False
    
    def _collect_loop(self):
        """데이터 수집 루프"""
        while self.running:
            try:
                # 시뮬레이션 데이터 수집
                self._collect_simulation_data()
                time.sleep(5)  # 5초마다 수집
            except Exception as e:
                print(f"데이터 수집 오류: {e}")
                time.sleep(10)
    
    def _collect_simulation_data(self):
        """시뮬레이션 데이터 수집 및 저장"""
        try:
            # 데이터베이스 확인 및 생성
            self._ensure_database()
            
            # 시뮬레이션 메트릭 생성
            metrics = {
                'timestamp': time.time(),
                'latency_ms': np.random.normal(50, 15),
                'packet_loss_pct': np.random.exponential(2),
                'throughput_mbps': np.random.normal(100, 20),
                'cpu_usage_pct': np.random.normal(45, 10),
                'memory_usage_pct': np.random.normal(60, 15),
                'attacks_detected': np.random.poisson(0.5),
                'mtd_activations': np.random.poisson(0.2),
                'detection_accuracy': np.random.beta(8, 2),
                'defense_level': np.random.choice(['standard', 'enhanced', 'maximum']),
                'mtd_strategy': np.random.choice(['none', 'ip_hopping', 'port_shuffling', 'decoy_deployment'])
            }
            
            # 데이터베이스에 저장
            self._save_metrics(metrics)
            
        except Exception as e:
            print(f"시뮬레이션 데이터 수집 오류: {e}")
    
    def _ensure_database(self):
        """데이터베이스 존재 확인 및 생성"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                latency_ms REAL,
                packet_loss_pct REAL,
                throughput_mbps REAL,
                cpu_usage_pct REAL,
                memory_usage_pct REAL,
                attacks_detected INTEGER,
                mtd_activations INTEGER,
                detection_accuracy REAL,
                defense_level TEXT,
                mtd_strategy TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _save_metrics(self, metrics):
        """메트릭 데이터베이스 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO unified_metrics 
            (timestamp, latency_ms, packet_loss_pct, throughput_mbps,
             cpu_usage_pct, memory_usage_pct, attacks_detected,
             mtd_activations, detection_accuracy, defense_level, mtd_strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metrics['timestamp'], metrics['latency_ms'], metrics['packet_loss_pct'],
            metrics['throughput_mbps'], metrics['cpu_usage_pct'], metrics['memory_usage_pct'],
            metrics['attacks_detected'], metrics['mtd_activations'], metrics['detection_accuracy'],
            metrics['defense_level'], metrics['mtd_strategy']
        ))
        
        conn.commit()
        conn.close()
    
    def get_latest_metrics(self):
        """최신 메트릭 조회"""
        try:
            if not os.path.exists(self.db_path):
                return None
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM unified_metrics 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            
            return None
            
        except Exception as e:
            print(f"최신 메트릭 조회 오류: {e}")
            return None
    
    def get_realtime_metrics(self):
        """실시간 메트릭 조회 (최근 30개)"""
        try:
            if not os.path.exists(self.db_path):
                return []
            
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query('''
                SELECT * FROM unified_metrics 
                ORDER BY timestamp DESC 
                LIMIT 30
            ''', conn)
            conn.close()
            
            return df.to_dict('records')
            
        except Exception as e:
            print(f"실시간 메트릭 조회 오류: {e}")
            return []
    
    def get_ns3_results(self):
        """NS-3 시뮬레이션 결과 조회"""
        try:
            results_file = '../attack_output/ns3_honeydrone_metrics.csv'
            
            if os.path.exists(results_file):
                df = pd.read_csv(results_file)
                return df.to_dict('records')
            
            return []
            
        except Exception as e:
            print(f"NS-3 결과 조회 오류: {e}")
            return []
