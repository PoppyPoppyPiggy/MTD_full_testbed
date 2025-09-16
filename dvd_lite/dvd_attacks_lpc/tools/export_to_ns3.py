#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, argparse
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import pandas as pd

# --- 기본 경로 (dvd_lite/dvd_attacks_lpc/tools 기준) ---
HERE = os.path.abspath(os.path.dirname(__file__))
LPC_ROOT = os.path.abspath(os.path.join(HERE, '..'))           # .../dvd_attacks_lpc
BUS_DIR  = os.path.join(LPC_ROOT, 'bus')

BUS_LOG_PATH      = os.path.join(BUS_DIR, 'bus.log')
BUS_DVD_LOG_PATH  = os.path.join(BUS_DIR, 'bus_dvd.log')

DEFAULT_OUT_DIR   = os.path.join(LPC_ROOT, 'attack_output')
DEFAULT_CSV_PATH  = os.path.join(DEFAULT_OUT_DIR, 'ns3_events_timeline.csv')
DEFAULT_XML_PATH  = os.path.join(DEFAULT_OUT_DIR, 'netanim_trace_detailed.xml')

# NS-3에서 쓸 노드/주소 매핑(시뮬 코드와 합의)
#   Node index: 0=Attacker, 1=Drone(companion-computer-lite), 2=Decoy(decoy_target)
#   Subnet: 10.13.0.0/24  -> Attacker 10.13.0.1, Drone 10.13.0.2, Decoy 10.13.0.3
NS3_NODE_IP = {
    "attacker": "10.13.0.200",
    "companion-computer-lite": "10.13.0.2",
    "drone": "10.13.0.2",           # alias
    "decoy_target": "10.13.0.3",
    "decoy": "10.13.0.3",           # alias
}

NODE_VIZ = {
    "attacker": {"id": 0, "x": 10, "y": 50, "color": (255, 0, 0)},   # red
    "companion-computer-lite": {"id": 1, "x": 50, "y": 50, "color": (0, 255, 0)}, # green
    "decoy_target": {"id": 2, "x": 90, "y": 50, "color": (0, 0, 255)}             # blue
}

def to_epoch(v):
    """float/iso8601/Z 문자열 섞여도 안전 변환"""
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        try:
            s = v.replace('Z', '+00:00')
            return datetime.fromisoformat(s).timestamp()
        except Exception:
            return 0.0
    return 0.0

def read_jsonl(path):
    if not os.path.exists(path): return []
    out = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                out.append(json.loads(line))
            except Exception:
                # 일부 로그는 이미 JSON-obj거나 노이즈일 수 있음
                continue
    return out

def extract_target_ip(s: str) -> str:
    """
    '10.13.0.2:14550' -> '10.13.0.2'
    'companion-computer-lite' -> 매핑된 IP
    """
    if not s: return ""
    s = s.strip()
    if ':' in s:
        s = s.split(':', 1)[0]
    if s.count('.') == 3:
        return s
    return NS3_NODE_IP.get(s, s)

def build_netanim_xml(all_events, t0, xml_path):
    """NetAnim 보조 시각화(XML) 생성(선택 기능)"""
    root = Element('anim')

    # 노드 배치/색
    for name, meta in NODE_VIZ.items():
        nodeinfo = Element('nodeinfo', id=str(meta['id']),
                           x=str(meta['x']), y=str(meta['y']))
        root.append(nodeinfo)
        r,g,b = meta['color']
        nu = Element('nu', id=str(meta['id']), r=str(r), g=str(g), b=str(b))
        SubElement(nu, 'ts', t="0.0")
        root.append(nu)

    # AttackStart -> attacker를 노란색으로 깜빡
    # BatteryUpdate -> (옵션) 이벤트 타임스탬프만 찍어둠
    for ev in all_events:
        st = to_epoch(ev.get('ts', ev.get('timestamp'))) - t0
        t = f"{max(0.0, st):.6f}"
        if ev.get('event') == 'AttackStart':
            nu = Element('nu', id=str(NODE_VIZ['attacker']['id']),
                         r="255", g="255", b="0") # yellow
            SubElement(nu, 'ts', t=t)
            root.append(nu)
            # 0.5초 뒤 원복(red)
            nu2 = Element('nu', id=str(NODE_VIZ['attacker']['id']),
                          r="255", g="0", b="0")
            SubElement(nu2, 'ts', t=f"{max(0.0, st+0.5):.6f}")
            root.append(nu2)
        elif ev.get('event') == 'MTD_IP_Shuffle':
            # 타겟 전환 시각 찍어두기
            nu = Element('nu', id=str(NODE_VIZ['companion-computer-lite']['id']),
                         r="0", g="255", b="0")
            SubElement(nu, 'ts', t=t)
            root.append(nu)

    xml = minidom.parseString(tostring(root, 'utf-8')).toprettyxml(indent="  ")
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml)

def main():
    ap = argparse.ArgumentParser(description="bus(.log/.bus_dvd.log) → NS-3 이벤트 CSV/NetAnim XML 변환기")
    ap.add_argument("--bus", default=BUS_LOG_PATH, help="bus.log 경로")
    ap.add_argument("--dvd", default=BUS_DVD_LOG_PATH, help="bus_dvd.log 경로")
    ap.add_argument("--outdir", default=DEFAULT_OUT_DIR, help="출력 폴더")
    ap.add_argument("--csv", default=DEFAULT_CSV_PATH, help="NS-3 이벤트 CSV 출력 경로")
    ap.add_argument("--xml", default=DEFAULT_XML_PATH, help="보조 NetAnim XML 출력 경로")
    ap.add_argument("--no-xml", action="store_true", help="보조 NetAnim XML 생성 안 함")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    bus = read_jsonl(args.bus)
    dvd = read_jsonl(args.dvd)
    if not bus and not dvd:
        print("❌ 입력 로그가 비었습니다. 종료.")
        return

    # 통합 & 시간 정렬
    unified = []
    for e in (bus + dvd):
        # 공통필드 정규화
        ts = e.get('ts', e.get('timestamp'))
        src = e.get('source') or e.get('src') or e.get('component')
        typ = e.get('type') or e.get('event_type')

        # attack_orchestrator가 남기는 'attack_started_by_orchestrator' 표준화
        if e.get('event_type') == 'attack_started_by_orchestrator':
            target = extract_target_ip((e.get('data') or {}).get('target', ''))
            unified.append({
                "timestamp": ts,
                "event": "AttackStart",
                "target": target,                       # 순수 IP 또는 공백
                "params": "packet_size=100,interval_ms=200"
            })
            continue

        # MTD 액션 표준화: ip shuffle류를 'MTD_IP_Shuffle'로
        if typ == 'mtd_action':
            data = e.get('data') or {}
            action = str(data.get('action', '')).lower()
            container = str(data.get('container', ''))
            if 'ip' in action and 'shuffle' in action or action in ('ip_shuffle','shuffle_ip'):
                # 우선순위: new_target/new_ip -> container 이름을 NS-3 매핑
                new_ip = (data.get('new_target') or data.get('new_ip') or "").strip()
                if not new_ip:
                    new_ip = NS3_NODE_IP.get(container, container)
                new_ip = extract_target_ip(new_ip)
                unified.append({
                    "timestamp": ts,
                    "event": "MTD_IP_Shuffle",
                    "target": new_ip,                   # 순수 IP일 수도, 비어있을 수도
                    "params": f"new_target={new_ip}:14550"
                })
            continue

        # DVD 내부 상태 -> 배터리 업데이트 등
        if e.get('type') == 'drone_state_detailed':
            level = None
            try:
                level = int((e.get('data') or {}).get('battery_remaining_pct'))
            except Exception:
                pass
            unified.append({
                "timestamp": ts,
                "event": "BatteryUpdate",
                "target": "companion-computer-lite",
                "params": f"level={level}" if level is not None else ""
            })
            continue

    if not unified:
        print("⚠️ 변환 가능한 이벤트가 없습니다. CSV를 만들지 않습니다.")
        return

    # 기준 시간
    t0 = min(to_epoch(u["timestamp"]) for u in unified)
    # 레코드 작성
    rows = []
    for u in unified:
        rows.append({
            "sim_time": max(0.0, to_epoch(u["timestamp"]) - t0),
            "event": u["event"],
            "target": u.get("target", ""),
            "params": u.get("params", "")
        })

    df = pd.DataFrame(rows).sort_values(by="sim_time").reset_index(drop=True)
    df.to_csv(args.csv, index=False)
    print(f"✅ NS-3 이벤트 CSV 생성: {args.csv}")

    if not args.no_xml:
        build_netanim_xml(unified, t0, args.xml)
        print(f"✅ 보조 NetAnim XML 생성: {args.xml}")

if __name__ == "__main__":
    main()
