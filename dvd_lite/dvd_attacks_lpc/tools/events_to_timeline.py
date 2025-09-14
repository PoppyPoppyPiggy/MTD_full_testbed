import pandas as pd
import os
import argparse

def main():
    ap = argparse.ArgumentParser(description="Generate NS-3 effect timeline from MTD effects log.")
    ap.add_argument("--log_dir", default="bus", help="Directory containing the effects.csv log file.")
    ap.add_argument("--sim_duration", type=int, default=120, help="Total simulation duration in seconds.")
    ap.add_argument("-o", "--out", help="Output file path for the timeline.")
    a = ap.parse_args()

    effects_log_file = os.path.join(a.log_dir, "effects.csv")
    ns3_timeline_file = a.out or os.path.join(a.log_dir, "effect_timeline.csv")
    
    if not os.path.exists(effects_log_file):
        print(f"Error: Effects log file not found at {effects_log_file}")
        return

    try:
        df = pd.read_csv(effects_log_file)
        
        # NS-3가 이해하는 컬럼명으로 변경
        df.rename(columns={
            "sim_time": "t_apply_s",
            "packet_loss": "loss_pct",
            "delay": "delay_ms",
            "jitter": "jitter_ms"
        }, inplace=True)
        # dup_pct 컬럼 추가 (필요시)
        df["dup_pct"] = 0 

        timeline = pd.DataFrame({'t_apply_s': range(a.sim_duration + 1)})
        df = df.sort_values('t_apply_s').reset_index(drop=True)
        
        # merge_asof를 사용하여 각 시간 지점의 네트워크 상태를 결정
        merged_df = pd.merge_asof(timeline, df, on='t_apply_s', direction='backward').fillna(0)
        
        # 필요한 컬럼만 선택하여 저장
        final_df = merged_df[["t_apply_s", "loss_pct", "delay_ms", "jitter_ms", "dup_pct"]]
        final_df.to_csv(ns3_timeline_file, index=False)
        
        print(f"NS-3 timeline generated successfully at: {ns3_timeline_file}")
    except Exception as e:
        print(f"An error occurred during timeline generation: {e}")

if __name__ == "__main__":
    main()