import csv
import os
from datetime import datetime, timezone

class EffectsLogger:
    def __init__(self, log_dir):
        self.log_file = os.path.join(log_dir, "effects.csv")
        self.start_time = datetime.now(timezone.utc)
        os.makedirs(log_dir, exist_ok=True)
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["sim_time", "event_type", "packet_loss", "delay", "jitter", "throughput_cap"])
        self.record_effect("SCENARIO_START")

    def record_effect(self, event_type, packet_loss=0.0, delay=0, jitter=0, throughput_cap=0):
        sim_time = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([f"{sim_time:.2f}", event_type, packet_loss, delay, jitter, throughput_cap])
        print(f"EFFECTS LOGGER: t={sim_time:.2f}s, event={event_type}, loss={packet_loss}, delay={delay}ms")