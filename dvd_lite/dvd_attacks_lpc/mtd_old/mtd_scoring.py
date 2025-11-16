#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Scoring Manager (W&B Logger) - v3 (Unified)

- [MODIFIED] W&B 로그 키 이름을 'MTD_RL/ver_02/train_mtd_only.py'와 완벽히 일치시킴.
  (예: 'MTD_Score_Overall' -> 'Metric/MTD_Score_Overall')
- [MODIFIED] 'ver_01/plotting.py'의 로컬 그래프 생성 기능 통합.
  (W&B 로깅과 동시에 'mtd_scoring_plots/[group_name]/'에 PNG 그래프 저장)
- [FIXED] 'calculate_mtd_cost' 함수 중복 정의 오류 수정.
- [FIXED] 텍스트 인코딩 오류 ('&nbsp;' 등) 수정.

This script runs in parallel to the MTD manager.
It reads the shared state files (from CTI, Hands, Monitors) to calculate
the MTD performance scores based on the defined metrics (S_D, R_A, C_M)
and logs them to Weights & Biases (W&B) and local PNG files.
"""

import wandb
import yaml
import json
import time
import os
import argparse
import sys
from collections import deque

# [MODIFICATION] Add plotting imports
import pathlib
import numpy as np
from typing import Dict, List, Tuple
import matplotlib
matplotlib.use("Agg") # Non-GUI backend
import matplotlib.pyplot as plt

# [MODIFICATION] Add plotting helper function (from ver_01/plotting.py logic)
def _plot_scoring_helper(x, ys, labels, title, ylabel, path: pathlib.Path, y2s=None, y2labels=None, y2label=None):
    """Internal plotting helper function for MTD Scoring"""
    path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 6))
    ax = plt.gca()
    if x is None or len(x) == 0:
        ax.set_title(title); ax.set_xlabel("Time (sec)"); ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--")
        plt.tight_layout(); plt.savefig(path, dpi=200); plt.close()
        return

    for y, l in zip(ys, labels):
        ax.plot(x, y, label=l)
    ax.set_title(title); ax.set_xlabel("Time (sec)"); ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--"); ax.legend(loc='upper left')

    if y2s:
        ax2 = ax.twinx()
        for y, l in zip(y2s, y2labels):
            ax2.plot(x, y, label=l, linestyle='--', alpha=0.8)
        ax2.set_ylabel(y2label or ylabel); ax2.legend(loc='upper right')

    plt.tight_layout(); plt.savefig(path, dpi=200); plt.close()

class MTDScoringManager:
    """Calculates MTD scores based on PPT metrics and logs to W&B."""

    def __init__(self, config_path, wandb_project, wandb_group):
        print(f"[Scoring] MTD 스코어링 매니저 초기화. (Config: {config_path})")
        self.config = self.load_config(config_path)

        # --- 1. Load File Paths from Config ---
        shared_files_config = self.config.get('shared_files', {})
        self.state_dir = os.path.join(os.path.dirname(__file__), 'shared_state')

        self.action_state_file = os.path.join(self.state_dir, shared_files_config.get('action_state', 'mtd_action_state.json'))
        self.cti_assessment_file = os.path.join(self.state_dir, shared_files_config.get('cti_assessment', 'cti_threat_assessment.json'))
        self.system_health_file = os.path.join(self.state_dir, shared_files_config.get('system_health', 'dvd_system_health.json'))

        print(f"[Scoring] Action State File: {self.action_state_file}")
        print(f"[Scoring] CTI Assessment File: {self.cti_assessment_file}")
        print(f"[Scoring] System Health File: {self.system_health_file}")

        # --- 2. Load Scoring Weights ---
        weights_config = self.config.get('weights', {})
        self.w_s_d = weights_config.get('w_deception_success', 0.5)
        self.w_r_a = weights_config.get('w_attack_resilience', 0.3)
        self.w_c_m = weights_config.get('w_mtd_cost', 0.2)

        cost_weights_config = self.config.get('cost_metric_weights', {})
        self.w_cost_latency = cost_weights_config.get('w_latency', 0.7)
        self.w_cost_packet_loss = cost_weights_config.get('w_packet_loss', 0.3)

        # --- 3. Load QoS Baselines ---
        baseline_qos_config = self.config.get('baseline_qos', {})
        self.baseline_latency = baseline_qos_config.get('latency_ms', 50.0)
        self.baseline_packet_loss = baseline_qos_config.get('packet_loss_percent', 0.1)

        # --- 4. Initialize Experiment Tracking State ---
        self.start_time = time.time()
        self.total_attack_time = 0.0
        self.total_decoy_time = 0.0
        self.total_reconfigurations = 0
        self.total_successful_attacks = 0
        self.last_mtd_action_id = -1
        self.attack_start_times = {} # { "gps_spoof": 16788... }
        self.decoy_active_start_time = None
        self.processed_breach_timestamps = set() # N_A 중복 계산 방지

        self.scoring_interval = self.config.get('scoring_interval', 5)

        # --- 5. W&B Initialization ---
        try:
            run_name = f"MTD_Scorer_for_{wandb_group}"
            self.wandb_run = wandb.init(
                project=wandb_project,
                group=wandb_group,
                job_type="scorer",
                name=run_name
            )
            print(f"[Scoring] W&B 연동 성공. (Project: {wandb_project}, Group: {wandb_group}, Run: {run_name})")
        except Exception as e:
            print(f"[Scoring] W&B 연동 실패: {e}", file=sys.stderr)
            print("          'wandb login'을 실행했는지 확인하세요.", file=sys.stderr)
            self.wandb_run = None

        # --- [MODIFICATION] 6. Plotting Initialization ---
        self.plot_outdir = pathlib.Path(f"mtd_scoring_plots/{wandb_group}")
        self.plot_outdir.mkdir(parents=True, exist_ok=True)
        print(f"[Scoring] 로컬 플로팅 활성화. 출력 디렉토리: {self.plot_outdir.resolve()}")

        self.plot_history = {'global_step': []}
        # W&B 키 이름을 'train_mtd_only.py'와 정확히 일치시킴
        self.plot_metrics_list = [
            "Metric/MTD_Score_Overall",
            "Metric/Metric_Deception_Success (S_D)",
            "Metric/Metric_Attack_Resilience (R_A)",
            "Metric/Metric_MTD_Cost (C_M)",
            "Metric/Detail_Reconfigurations (N_R)",
            "Metric/Detail_Successful_Attacks (N_A)",
            "Metric/Detail_Total_Attack_Steps (T_A)", # T_A (Time -> Steps)
            "Metric/Detail_Total_Decoy_Steps (T_D)", # T_D (Time -> Steps)
            "Metric/QoS_Latency_Cost",
            "Metric/QoS_Packet_Loss_Cost"
        ]
        for metric in self.plot_metrics_list:
            self.plot_history[metric] = []

        # Plot update interval (every N scoring loops)
        self.plot_update_interval = self.config.get('plot_update_interval', 6) # e.g., 6 * 5s = 30s
        self.run_loop_count = 0


    def load_config(self, config_path):
        """Loads the mtd_scoring.yaml config file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Error: 스코어링 설정 파일({config_path})을 찾을 수 없습니다!", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: 스코어링 설정 파일 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

    def load_json_state(self, file_path):
        """Safely loads a JSON state file."""
        try:
            if os.path.exists(file_path):
                # 파일이 너무 오래되었는지 확인 (staleness check, 예: 30초)
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age > 30:
                    # print(f"Warning: JSON 파일이 너무 오래되었습니다 ({file_age:.0f}s): {file_path}", file=sys.stderr)
                    return None # 오래된 데이터는 무시

                with open(file_path, 'r') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: JSON 파일 파싱 오류: {file_path}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: JSON 파일 읽기 오류 ({file_path}): {e}", file=sys.stderr)
        return None

    def calculate_deception_success(self, cti_data, action_data, current_time):
        """S_D = T_D / T_A (기만 성공률)"""

        is_attack_detected = False
        if cti_data and cti_data.get('alert_detected', False):
            is_attack_detected = True
            active_attacks = cti_data.get('active_attack_types', [])
            for attack in active_attacks:
                if attack not in self.attack_start_times:
                    self.attack_start_times[attack] = current_time # 공격 시작 시간 기록

        # T_A (Total Attack Time) 계산
        # (현재는 공격이 탐지된 이후 모든 시간을 누적)
        self.total_attack_time = 0.0
        for attack, start_time in self.attack_start_times.items():
            self.total_attack_time += (current_time - start_time)

        # T_D (Time on Decoy) 누적
        # [고도화] 공격이 탐지되었고, 동시에 MTD가 디코이를 활성한 경우에만 시간 누적
        is_decoy_active = False
        if action_data:
            is_decoy_active = action_data.get('current_action', {}).get('is_decoy', False)

        if is_attack_detected and is_decoy_active:
            if self.decoy_active_start_time is None:
                self.decoy_active_start_time = current_time
            # 현재 스코어링 주기만큼 디코이 시간 누적
            self.total_decoy_time += self.scoring_interval
        else:
            self.decoy_active_start_time = None

        if self.total_attack_time == 0:
            return 0.0  # 공격이 없었으면 기만 성공률은 0

        s_d = self.total_decoy_time / self.total_attack_time
        return min(s_d, 1.0) # 100% 초과 방지

    def calculate_attack_resilience(self, cti_data, action_data):
        """R_A = N_R / N_A (공격 탄력성)"""

        # N_R (Number of Reconfigurations) 누적
        if action_data:
            current_action_id = action_data.get('current_action', {}).get('action_id', -1)
            if current_action_id != self.last_mtd_action_id:
                if self.last_mtd_action_id != -1: # 초기 설정 제외
                    self.total_reconfigurations += 1
                self.last_mtd_action_id = current_action_id

        # N_A (Number of Successful Attacks) 누적
        # [고도화] CTI가 'Breach'를 보고하고, 동시에 MTD 타겟이 'Decoy'가 아니었을 때만 카운트
        if cti_data and cti_data.get('attack_stage_assessment', '') == 'Breach' and action_data:

            is_decoy = action_data.get('current_action', {}).get('is_decoy', False)
            breach_timestamp = cti_data.get('last_analysis_timestamp')

            # CTI가 Breach를 보고했고, MTD가 디코이로 방어하지 못한 경우 (실제 타겟 피격)
            if not is_decoy:
                # 이 Breach가 이전에 카운트되지 않은 새로운 Breach인 경우
                if breach_timestamp not in self.processed_breach_timestamps:
                    self.total_successful_attacks += 1
                    self.processed_breach_timestamps.add(breach_timestamp) # 중복 방지
                    print(f"[Scoring] ❗ 신규 침해(Breach) 감지! (N_A: {self.total_successful_attacks})")


        n_r = self.total_reconfigurations
        n_a = self.total_successful_attacks

        if n_a == 0:
            # 공격 성공이 0이면, 재설정 횟수 자체가 보너스 점수 (최대 10점)
            return min(n_r, 10.0)

        r_a = n_r / n_a
        return r_a

    # [FIXED] 'calculate_mtd_cost' 함수 중복 정의 수정.
    # 이 함수가 'all', 'latency', 'packet_loss' 타입을 모두 처리합니다.
    def calculate_mtd_cost(self, health_data, metric_type='all'):
        """C_M = w_lat * Cost(lat) + w_loss * Cost(loss) (MTD 비용)"""
        if not health_data:
            return 0.0

        # 1. Latency Cost 계산
        p_n_latency = health_data.get('qos_metrics', {}).get('latency_ms', self.baseline_latency)
        p_o_latency = self.baseline_latency
        cost_latency = 0.0
        if p_o_latency > 0:
            cost_latency = (p_n_latency - p_o_latency) / p_o_latency
        cost_latency = max(0, cost_latency) # 비용이 음수(-)가 될 수 없음

        if metric_type == 'latency':
            return cost_latency

        # 2. Packet Loss Cost 계산
        p_n_loss = health_data.get('qos_metrics', {}).get('packet_loss_percent', self.baseline_packet_loss)
        p_o_loss = self.baseline_packet_loss
        cost_packet_loss = 0.0
        if p_o_loss > 0:
            cost_packet_loss = (p_n_loss - p_o_loss) / p_o_loss
        cost_packet_loss = max(0, cost_packet_loss) # 비용이 음수(-)가 될 수 없음

        if metric_type == 'packet_loss':
            return cost_packet_loss

        # 3. 가중 평균으로 최종 비용 계산 (metric_type == 'all')
        c_m = (self.w_cost_latency * cost_latency) + (self.w_cost_packet_loss * cost_packet_loss)
        return c_m

    # [MODIFICATION] Add plot generation method
    def generate_plots(self):
        """누적된 self.plot_history를 기반으로 PNG 그래프 생성"""
        print(f"[Scoring] Generating plots in {self.plot_outdir}...")
        x = self.plot_history['global_step']
        if not x:
            print("[Scoring] No data to plot yet.")
            return

        try:
            # Plot 1: Overall Score
            _plot_scoring_helper(
                x, [self.plot_history["Metric/MTD_Score_Overall"]], ["MTD Score"],
                "MTD Overall Score (S_MTD)", "Score",
                self.plot_outdir / "01_mtd_overall_score.png"
            )
            
            # Plot 2: Core Metrics (S_D, R_A, C_M)
            _plot_scoring_helper(
                x, 
                [self.plot_history["Metric/Metric_Deception_Success (S_D)"], 
                 self.plot_history["Metric/Metric_Attack_Resilience (R_A)"],
                 self.plot_history["Metric/Metric_MTD_Cost (C_M)"]],
                ["S_D (Deception)", "R_A (Resilience)", "C_M (Cost)"],
                "MTD Core Metrics", "Value",
                self.plot_outdir / "02_mtd_core_metrics.png"
            )

            # Plot 3: Detail Metrics (N_R, N_A)
            # (train_mtd_only.py와 동일하게 누적 카운트로 표시)
            _plot_scoring_helper(
                x, 
                [self.plot_history["Metric/Detail_Reconfigurations (N_R)"]], ["N_R (Reconfigurations)"],
                "MTD Attack Resilience Details", "Count (Cumulative)",
                self.plot_outdir / "03_mtd_resilience_details.png",
                y2s=[self.plot_history["Metric/Detail_Successful_Attacks (N_A)"]], 
                y2labels=["N_A (Successful Attacks)"], 
                y2label="Count (Cumulative)"
            )
            
            # Plot 4: QoS Cost Details
            _plot_scoring_helper(
                x, 
                [self.plot_history["Metric/QoS_Latency_Cost"]], ["Latency Cost"],
                "MTD Cost Details (QoS)", "Cost (Normalized)",
                self.plot_outdir / "04_mtd_cost_details.png",
                y2s=[self.plot_history["Metric/QoS_Packet_Loss_Cost"]], 
                y2labels=["Packet Loss Cost"], 
                y2label="Cost (Normalized)"
            )
            
            # Plot 5: Deception Time Details (T_A, T_D)
            _plot_scoring_helper(
                x, 
                [self.plot_history["Metric/Detail_Total_Attack_Steps (T_A)"]], ["Total Attack Time (sec)"],
                "MTD Deception Details (Time)", "Time (sec)",
                self.plot_outdir / "05_mtd_deception_details.png",
                y2s=[self.plot_history["Metric/Detail_Total_Decoy_Steps (T_D)"]], 
                y2labels=["Total Decoy Time (sec)"], 
                y2label="Time (sec)"
            )
            
            print(f"[Scoring] Plots generated successfully.")

        except Exception as e:
            print(f"Error: 플롯 생성 중 오류 발생: {e}", file=sys.stderr)


    def run(self):
        """Main loop to calculate scores periodically."""
        print(f"[Scoring] 스코어링 루프 시작. ({self.scoring_interval}초마다 갱신)")

        try:
            while True:
                # [MODIFICATION] Increment loop count
                self.run_loop_count += 1
                
                current_time = time.time()
                # X축을 경과 시간(초)으로 통일
                current_step = int(current_time - self.start_time)

                # 1. Load all data sources
                action_data = self.load_json_state(self.action_state_file)
                cti_data = self.load_json_state(self.cti_assessment_file)
                health_data = self.load_json_state(self.system_health_file)

                # 2. Calculate metrics
                s_d = self.calculate_deception_success(cti_data, action_data, current_time)
                r_a = self.calculate_attack_resilience(cti_data, action_data)
                
                # [FIXED] Call cost function correctly
                c_m = self.calculate_mtd_cost(health_data, 'all')
                cost_latency = self.calculate_mtd_cost(health_data, 'latency')
                cost_packet_loss = self.calculate_mtd_cost(health_data, 'packet_loss')

                # S_MTD = w1 * S_D + w2 * R_A - w3 * C_M
                s_mtd = (self.w_s_d * s_d) + (self.w_r_a * r_a) - (self.w_c_m * c_m)

                # 3. Log to W&B
                # [MODIFICATION] W&B 키 이름을 'train_mtd_only.py'와 정확히 일치시킴
                logs = {
                    "General/global_step": current_step,
                    
                    "Metric/MTD_Score_Overall": s_mtd,
                    "Metric/Metric_Deception_Success (S_D)": s_d,
                    "Metric/Metric_Attack_Resilience (R_A)": r_a,
                    "Metric/Metric_MTD_Cost (C_M)": c_m,
                    
                    # 'T_A'/'T_D'는 'train_mtd_only.py'의 키 이름과 맞춤 (의미: 시간)
                    "Metric/Detail_Total_Attack_Steps (T_A)": self.total_attack_time,
                    "Metric/Detail_Total_Decoy_Steps (T_D)": self.total_decoy_time,
                    "Metric/Detail_Reconfigurations (N_R)": self.total_reconfigurations,
                    "Metric/Detail_Successful_Attacks (N_A)": self.total_successful_attacks,
                    
                    # QoS 비용은 'train_mtd_only.py'에 없지만, 일관성을 위해 'Metric/' 그룹에 추가
                    "Metric/QoS_Latency_Cost": cost_latency,
                    "Metric/QoS_Packet_Loss_Cost": cost_packet_loss,
                    
                    "General/CTI_Threat_Level": cti_data.get('current_threat_level', 'NONE') if cti_data else 'UNKNOWN',
                    "General/CTI_Active_Attacks": ", ".join(cti_data.get('active_attack_types', [])) if cti_data else "NONE"
                }

                if self.wandb_run:
                    self.wandb_run.log(logs)

                print(f"[Scoring] Step {current_step}s: S_MTD = {s_mtd:.2f} (S_D={s_d:.2f}, R_A={r_a:.2f}, C_M={c_m:.2f})")

                # --- [MODIFICATION] 4. Plotting ---
                # 로그 히스토리에 누적
                self.plot_history['global_step'].append(current_step)
                for metric in self.plot_metrics_list:
                    # 'logs' 딕셔너리에서 'Metric/'이 포함된 키를 찾아서 값 추가
                    self.plot_history[metric].append(logs.get(metric, np.nan))
                
                # 주기적으로 플롯 생성
                if self.run_loop_count % self.plot_update_interval == 0:
                    self.generate_plots()
                # --- End Modification ---
                
                time.sleep(self.scoring_interval)

        except KeyboardInterrupt:
            print("\n[Scoring] 스코어링 매니저 중지됨.")
        finally:
            # [MODIFICATION] Add final plot generation
            print("[Scoring] 종료 전 최종 그래프 생성 중...")
            self.generate_plots()
            
            if self.wandb_run:
                self.wandb_run.finish()
                print("[Scoring] W&B run 종료.")

# [FIXED] Remove duplicated helper function definition
# (The correct one is inside the MTDScoringManager class)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MTD Scoring Manager (Advanced, with Plotting)")
    parser.add_argument("--config", type=str,
                        default="mtd/configs/mtd_scoring.yaml",
                        help="MTD 스코어링 설정 YAML 파일 경로")
    parser.add_argument("--project", type=str,
                        default="mtd_testbed_live",
                        help="W&B 프로젝트 이름")
    parser.add_argument("--group", type=str,
                        required=True,
                        help="W&B 그룹 이름 (예: L0_Seeker). MTD 매니저의 그룹과 동일해야 합니다.")
    
    args = parser.parse_args()
    
    # [MODIFICATION] matplotlib 백엔드 설정 확인
    print(f"[Scoring] Matplotlib backend: {matplotlib.get_backend()}")

    manager = MTDScoringManager(
        config_path=args.config,
        wandb_project=args.project,
        wandb_group=args.group
    )
    manager.run()