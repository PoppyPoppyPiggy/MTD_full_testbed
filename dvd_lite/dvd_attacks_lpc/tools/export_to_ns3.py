import json
import os
import pandas as pd
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# --- 설정 ---
LPC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUS_LOG_PATH = os.path.join(LPC_ROOT, 'bus', 'bus.log')
DVD_LOG_PATH = os.path.join(LPC_ROOT, 'bus', 'bus_dvd.log')
OUTPUT_DIR = os.path.join(LPC_ROOT, 'attack_output')
NS3_EVENT_CSV_PATH = os.path.join(OUTPUT_DIR, 'ns3_events_timeline.csv')
NETANIM_XML_PATH = os.path.join(OUTPUT_DIR, 'netanim_trace_detailed.xml')

NODE_MAP = {
    "attacker": {"id": 0, "pos_x": 10, "pos_y": 50, "color": (255, 0, 0)}, # Red
    "companion-computer-lite": {"id": 1, "pos_x": 50, "pos_y": 50, "color": (0, 255, 0)}, # Green
    "decoy_target": {"id": 2, "pos_x": 90, "pos_y": 50, "color": (0, 0, 255)} # Blue
}

def read_jsonl_log(file_path):
    events = []
    if not os.path.exists(file_path):
        print(f"경고: 로그 파일을 찾을 수 없습니다: {file_path}")
        return []
    with open(file_path, 'r') as f:
        for line in f:
            try: events.append(json.loads(line))
            except json.JSONDecodeError: continue
    return events

def main():
    print("NS-3 및 NetAnim 상세 데이터 변환 시작...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    bus_events = read_jsonl_log(BUS_LOG_PATH)
    dvd_events = read_jsonl_log(DVD_LOG_PATH)
    
    if not bus_events and not dvd_events:
        print("에러: 모든 로그 파일이 비어있습니다. 변환을 중단합니다.")
        return

    all_events = sorted(bus_events + dvd_events, key=lambda x: x.get('timestamp'))
    if not all_events: return

    t_start = all_events[0]['timestamp']
    ns3_records = []
    root = Element('anim')

    for name, info in NODE_MAP.items():
        node_info = Element('nodeinfo', id=str(info['id']), x=str(info['pos_x']), y=str(info['pos_y']))
        root.append(node_info)
        nu_elem = Element('nu', id=str(info['id']), r=str(info['color'][0]), g=str(info['color'][1]), b=str(info['color'][2]))
        SubElement(nu_elem, 'ts', t="0.0")
        root.append(nu_elem)

    for event in all_events:
        sim_time = event['timestamp'] - t_start
        
        if 'event_type' in event:
            event_type, data = event['event_type'], event.get('data', {})
            if event_type == 'attack_started_by_orchestrator':
                target_ip = data.get('target', '').split(':')[0]
                ns3_records.append({'sim_time': sim_time, 'event': 'AttackStart', 'target': target_ip, 'params': json.dumps(data)})
                
                nu_elem = Element('nu', id='0', r="255", g="255", b="0") # Yellow
                SubElement(nu_elem, 'ts', t=f"{sim_time:.6f}")
                root.append(nu_elem)
                nu_elem_back = Element('nu', id='0', r="255", g="0", b="0") # Red
                SubElement(nu_elem_back, 'ts', t=f"{sim_time + 0.5:.6f}")
                root.append(nu_elem_back)

            elif event_type == 'mtd_action':
                action = data.get('action')
                ns3_records.append({'sim_time': sim_time, 'event': f'MTD_{action.upper()}', 'target': data.get('container'), 'params': ''})

        elif 'source' in event:
            source, metrics = event['source'], event.get('metrics', {})
            if metrics.get('mavpackettype') == 'SYS_STATUS':
                battery = metrics.get('battery_remaining', -1)
                ns3_records.append({'sim_time': sim_time, 'event': 'BatteryUpdate', 'target': source, 'params': f"level={battery}"})
                
                size = max(0.2, battery / 100.0)
                if source in NODE_MAP:
                    ns_elem = Element('ns', id=str(NODE_MAP[source]['id']), s=str(size))
                    SubElement(ns_elem, 'ts', t=f"{sim_time:.6f}")
                    root.append(ns_elem)

    if ns3_records:
        pd.DataFrame(ns3_records).to_csv(NS3_EVENT_CSV_PATH, index=False)
        print(f"성공! NS-3 상세 타임라인이 생성되었습니다: {NS3_EVENT_CSV_PATH}")

    xml_str = tostring(root, 'utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")
    with open(NETANIM_XML_PATH, 'w') as f:
        f.write(pretty_xml)
    print(f"성공! NetAnim 상세 추적 파일이 생성되었습니다: {NETANIM_XML_PATH}")

if __name__ == "__main__":
    main()