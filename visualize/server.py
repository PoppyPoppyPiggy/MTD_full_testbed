#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
초경량 시각화 서버 (표준 라이브러리만 사용)
- GET /              -> index.html
- GET /api/read      -> 로그 읽기 (bus, bus_dvd)
- GET /api/state     -> MTD 상태 조회 (mtd_state.json)
- GET /api/ping      -> 헬스체크

기본 경로(환경변수/옵션으로 변경 가능):
  BUS_PATH        = /home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus.log
  BUS_DVD_PATH    = /home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus_dvd.log
  MTD_STATE_PATH  = /home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/shared_state/mtd_state.json
"""

import argparse
import json
import os
import re
import sys
import time
import html
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# ---------- 기본 경로 ----------
DEFAULT_BUS = "/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus.log"
DEFAULT_DVD = "/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus_dvd.log"
DEFAULT_STATE = "/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/shared_state/mtd_state.json"

# ---------- 유틸 ----------
def parse_iso(ts: str) -> Optional[float]:
    try:
        # 2025-09-16T06:30:29.437303+00:00 형태
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return None

def to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

def normalize_line(raw: str) -> Optional[Dict[str, Any]]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        evt = json.loads(raw)
    except Exception:
        return None

    # 다양한 스키마 normalize
    etype = evt.get("type") or evt.get("event_type") or ""
    source = evt.get("source") or evt.get("component") or ""
    data = evt.get("data") or {}

    # ts 계산
    ts = None
    if isinstance(evt.get("ts"), (int, float)):
        ts = float(evt["ts"])
    elif isinstance(evt.get("timestamp"), (int, float)):
        ts = float(evt["timestamp"])
    elif isinstance(evt.get("timestamp"), str):
        ts = parse_iso(evt["timestamp"])
    if ts is None:
        # data 내부에 타임스탬프가 있는 경우도 시도
        if isinstance(data.get("ts"), (int, float)):
            ts = float(data["ts"])
        elif isinstance(data.get("timestamp"), (int, float)):
            ts = float(data["timestamp"])
        elif isinstance(data.get("timestamp"), str):
            ts = parse_iso(data["timestamp"])
    if ts is None:
        ts = time.time()

    # 편의 필드 병합(상단->data 순으로 병합)
    merged = {}
    merged.update(evt)
    # 상단 key 보호: type, source, ts, timestamp 등은 유지
    for k, v in data.items():
        if k in ("type", "source", "event_type", "ts", "timestamp"):
            continue
        merged[k] = v

    # 공통 필드 추출
    dst_ip = merged.get("dst_ip") or merged.get("dip") or merged.get("dest_ip")
    dst_port = merged.get("dst_port") or merged.get("dport")
    src_ip = merged.get("src_ip") or merged.get("sip") or merged.get("src")
    src_port = merged.get("src_port") or merged.get("sport")
    action = merged.get("action")
    new_target = merged.get("new_target") or merged.get("target")

    # 숫자화
    try:
        if isinstance(dst_port, str): dst_port = int(dst_port)
    except Exception:
        dst_port = None
    try:
        if isinstance(src_port, str): src_port = int(src_port)
    except Exception:
        src_port = None

    return {
        "ts": ts,
        "iso": to_iso(ts),
        "type": etype,
        "source": source,
        "fields": {
            "dst_ip": dst_ip, "dst_port": dst_port,
            "src_ip": src_ip, "src_port": src_port,
            "action": action, "new_target": new_target,
            "proto": merged.get("proto") or merged.get("protocol"),
            "context": merged.get("context"),
            "filters": merged.get("filters"),
            "attack": merged.get("attack"),
            "return_code": merged.get("return_code"),
            "containers": merged.get("containers"),
            "state": merged.get("state"),
            "want_ip": merged.get("want_ip"),
            "want_port": merged.get("want_port"),
            "hits_in_window": merged.get("hits_in_window"),
            "current_hits_in_window": merged.get("current_hits_in_window"),
        },
        "raw": evt,               # 원본 JSON (프런트에서 상세보기)
        "line_raw": raw           # 원문 문자열
    }

def read_tail(path: str, max_lines: int) -> List[str]:
    """파일 끝에서 최대 max_lines 줄만 빠르게 읽기"""
    if not os.path.isfile(path):
        return []
    # 너무 큰 파일도 고려하여 블록 단위로 뒤에서부터 읽음
    lines: List[str] = []
    block_size = 8192
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        buffer = b""
        pos = file_size
        while pos > 0 and len(lines) <= max_lines:
            read_size = block_size if pos >= block_size else pos
            pos -= read_size
            f.seek(pos, os.SEEK_SET)
            chunk = f.read(read_size)
            buffer = chunk + buffer
            # 줄 분리
            parts = buffer.split(b"\n")
            buffer = parts[0]
            for line in parts[1:]:
                try:
                    lines.append(line.decode("utf-8", errors="replace"))
                except Exception:
                    pass
            if len(lines) >= max_lines:
                break
        # 맨 앞 버퍼
        if buffer:
            try:
                lines.append(buffer.decode("utf-8", errors="replace"))
            except Exception:
                pass
    lines = [l for l in lines if l.strip()]
    lines = lines[-max_lines:]
    return lines

# ---------- HTTP 핸들러 ----------
class Handler(SimpleHTTPRequestHandler):
    # 정적 루트는 프로그램 실행 디렉토리(visualize/)
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/ping":
            self._json({"ok": True, "now": time.time()})
            return

        if path == "/api/state":
            state_path = qs.get("path", [self.server.opts.mtd_state])[0]
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    js = json.load(f)
                self._json({"ok": True, "path": state_path, "state": js})
            except Exception as e:
                self._json({"ok": False, "error": str(e), "path": state_path}, code=404)
            return

        if path == "/api/read":
            # ?source=bus|dvdbus 또는 ?path=/abs/file  + since_ts(옵션) + limit(기본 500)
            src = (qs.get("source", [""])[0] or "").lower()
            file_path = qs.get("path", [""])[0]
            limit = int(qs.get("limit", ["500"])[0])
            since_ts = qs.get("since_ts", [None])[0]
            since = float(since_ts) if since_ts is not None else None

            if not file_path:
                if src == "bus":
                    file_path = self.server.opts.bus_path
                elif src in ("dvdbus", "bus_dvd", "internal"):
                    file_path = self.server.opts.bus_dvd_path
                else:
                    # 기본은 public bus
                    file_path = self.server.opts.bus_path

            raw_lines = read_tail(file_path, limit)
            items = []
            last_ts = since or 0.0
            for line in raw_lines:
                obj = normalize_line(line)
                if not obj:
                    continue
                if since is not None and obj["ts"] <= since:
                    continue
                items.append(obj)
                if obj["ts"] > last_ts:
                    last_ts = obj["ts"]
            self._json({"ok": True, "path": file_path, "count": len(items), "last_ts": last_ts, "items": items})
            return

        # 기본 정적 파일 서빙 (index.html 등)
        if path == "/":
            return super().do_GET()
        # 그 외 파일도 허용
        return super().do_GET()

    # CORS + JSON 헬퍼
    def _json(self, obj: Dict[str, Any], code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def serve(opts):
    # 작업 디렉토리를 visualize/ 로 고정 (index.html 찾게)
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    Handler.protocol_version = "HTTP/1.1"
    httpd = HTTPServer((opts.host, opts.port), Handler)
    # 옵션을 핸들러에서 접근 가능하도록
    httpd.opts = opts
    print(f"[viz] serving on http://{opts.host}:{opts.port}")
    print(f"[viz] bus      : {opts.bus_path}")
    print(f"[viz] bus_dvd  : {opts.bus_dvd_path}")
    print(f"[viz] mtd_state: {opts.mtd_state}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[viz] bye")

def main():
    p = argparse.ArgumentParser(description="MTD bus visualizer server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8088)
    p.add_argument("--bus", dest="bus_path", default=os.getenv("BUS_PATH", DEFAULT_BUS))
    p.add_argument("--dvdbus", dest="bus_dvd_path", default=os.getenv("BUS_DVD_PATH", DEFAULT_DVD))
    p.add_argument("--state", dest="mtd_state", default=os.getenv("MTD_STATE_PATH", DEFAULT_STATE))
    opts = p.parse_args()
    serve(opts)

if __name__ == "__main__":
    main()
