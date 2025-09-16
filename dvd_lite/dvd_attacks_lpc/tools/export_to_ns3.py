#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
import argparse
import os
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# --- 경로 설정 ---
TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.abspath(os.path.join(TOOLS_DIR, '..'))
BUS_DIR = os.path.join(LPC_DIR, 'bus')

# --- 시각화/시뮬레이션 설정 ---
# docker-compose.yml의 주요 서비스 이름을 여기에 매핑합니다.
NODE_VIZ_MAP = {
    "flight-controller-lite": {"id": 1, "desc": "Flight Controller", "pos": (100, 50)},
    "companion-computer-lite": {"id": 2, "desc": "Companion Computer", "pos": (100, 90)},
    "decoy":                  {"id": 3, "desc": "Decoy", "pos": (180, 50)},
    "attacker":               {"id": 4, "desc": "Attacker", "pos": (20, 50)},
    "prober":                 {"id": 5, "desc": "Prober", "pos": (20, 90)},
    "mtd-engine":             {"id": 6, "desc": "MTD Engine", "pos": (140, 10)},
    "observer":               {"id": 7, "desc": "Observer", "pos": (180, 10)},
    "rl-agent":               {"id": 8, "desc": "RL Agent", "pos": (100, 10)},
    "gcs":                    {"id": 9, "desc": "GCS", "pos": (20, 10)},
}

def parse_iso(ts):
    """다양한 형식의 타임스탬프를 datetime 객체로 안전하게 변환"""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    if not isinstance(ts, str):
        return None
    try:
        s = ts.replace('Z', '+00:00')
        if '+' in s and s.count(':') >= 3:
            s = s[::-1].replace(':', '', 1)[::-1]
        return datetime.fromisoformat(s)
    except Exception:
        return None

def normalize_log_entry(line):
    """JSONL 한 줄을 표준화된 이벤트 딕셔너리로 변환"""
    try:
        e = json.loads(line.strip())
        ts_val = e.get("timestamp") or e.get("ts")
        if not ts_val: return None
        
        dt = parse_iso(ts_val)
        if not dt: return None

        return {
            "ts": dt.timestamp(),
            "dt": dt,
            "type": e.get("type") or e.get("event_type", ""),
            "data": e.get("data", {}),
            "raw": e
        }
    except Exception:
        return None

def load_all_logs(bus_dir):
    """bus 디렉토리의 모든 로그를 읽어 시간순으로 병합"""
    events = []
    log_files = ["bus.log", "bus_dvd.log", "bus_dvd_instances.log"]
    for fn in log_files:
        path = os.path.join(bus_dir, fn)
        if not os.path.exists(path): continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                norm_event = normalize_log_entry(line)
                if norm_event: events.append(norm_event)
    events.sort(key=lambda x: x["ts"])
    return events

def generate_ns3_csv(events, out_path, t0_epoch):
    """NS-3 시뮬레이션 로직을 위한 이벤트 CSV 파일을 생성"""
    rows = []
    for e in events:
        sim_time = e["ts"] - t0_epoch
        event_type = e["type"]
        data = e["data"]

        if event_type == "attack_started_by_orchestrator":
            attack_name = e["raw"].get("attack", "unknown")
            rows.append([f"{sim_time:.6f}", "AttackStart", "drone", f"name={attack_name}"])
        elif event_type == "mtd_action" and data.get("action") == "ip_shuffle":
            new_target = data.get("new_target", "")
            rows.append([f"{sim_time:.6f}", "MTD_IP_Shuffle", new_target, f"new_target={new_target}"])

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sim_time", "event", "target", "params"])
        writer.writerows(rows)
    print(f"✅ NS-3 이벤트 CSV 생성 완료: {out_path} ({len(rows)}개 이벤트)")

def generate_netanim_xml(events, out_path, t0_epoch):
    """NetAnim 시각화용 XML 파일을 생성"""
    root = Element("netanim")

    # 1. 노드 초기화: ID, 위치, 설명, 기본 색상 설정
    node_map = {}
    for name, data in NODE_VIZ_MAP.items():
        node_id = data["id"]
        node_map[name] = node_id
        x, y = data["pos"]
        r, g, b = data.get("color", (128, 128, 128))
        SubElement(root, "node", id=str(node_id), x=f"{x:.1f}", y=f"{y:.1f}", desc=data["desc"])
        SubElement(root, "anim", id=str(node_id), time="0.0", type='c', r=str(r), g=str(g), b=str(b))

    # 2. 이벤트 기반 애니메이션 생성
    for e in events:
        sim_time = f"{(e['ts'] - t0_epoch):.6f}"
        event_type = e["type"]
        data = e["data"]

        # 드론 상태 변화 (색상/크기)
        if event_type == "drone_state_detailed":
            drone_data = data.get("data", {})
            drone_id = str(node_map["flight-controller-lite"])
            
            # 배터리
            battery_pct = drone_data.get("battery_remaining_pct")
            if battery_pct is not None and 0 <= battery_pct <= 100:
                r = min(255, 510 * (1 - battery_pct / 100.0))
                g = min(255, 510 * (battery_pct / 100.0))
                SubElement(root, "anim", id=drone_id, time=sim_time, type='c', r=f"{r:.0f}", g=f"{g:.0f}", b="0")

            # Arming 상태
            if drone_data.get("armed") is True:
                SubElement(root, "anim", id=drone_id, time=sim_time, type='s', size="15.0")
            elif drone_data.get("armed") is False:
                SubElement(root, "anim", id=drone_id, time=sim_time, type='s', size="10.0")

    xml_str = minidom.parseString(tostring(root)).toprettyxml(indent="  ")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"✅ NetAnim 상세 시각화 XML 생성 완료: {out_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bus-dir', default=BUS_DIR)
    parser.add_argument('--output-dir', default=os.path.join(LPC_DIR, 'test_output', 'latest'))
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    events = load_all_logs(args.bus_dir)
    
    if not events:
        print("❌ 처리할 이벤트가 로그 파일에 없습니다.")
        return

    t0_epoch = events[0]["ts"]
    print(f"총 {len(events)}개의 정규화된 이벤트를 찾았습니다.")
    
    csv_path = os.path.join(args.output_dir, 'ns3_events_timeline.csv')
    xml_path = os.path.join(args.output_dir, 'netanim_trace.xml')
    
    generate_ns3_csv(events, csv_path, t0_epoch)
    generate_netanim_xml(events, xml_path, t0_epoch)
    
    print("\n--- 모든 작업 완료 ---")

if __name__ == "__main__":
    main()