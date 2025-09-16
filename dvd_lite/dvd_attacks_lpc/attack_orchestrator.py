#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import subprocess
import time
import json
import signal
import threading
import datetime
from typing import List, Dict, Any, Optional, Deque, Tuple
from collections import deque

# --- 경로 설정 ---
LPC_DIR = os.path.dirname(os.path.realpath(__file__))
ATTACKS_DIR = os.path.join(LPC_DIR, 'modules', 'attacks_wiki')
ATTACK_PROFILES_PATH = os.path.join(ATTACKS_DIR, 'attack_profiles.json')
BUS_LOG_PATH = os.path.join(LPC_DIR, 'bus', 'bus.log')

POLL_INTERVAL_SEC = 0.5

# 전역: 실행 중 공격 프로세스
attack_process: Optional[subprocess.Popen] = None
attack_lock = threading.RLock()
stop_event = threading.Event()

# -----------------------------
# 공통 유틸
# -----------------------------
def iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def epoch_now() -> float:
    return time.time()

def write_bus(event: Dict[str, Any]) -> None:
    """bus.log에 JSONL 한 줄 쓰기 (timestamp/ts 자동 추가)"""
    os.makedirs(os.path.dirname(BUS_LOG_PATH), exist_ok=True)
    payload = {
        "timestamp": event.get("timestamp", iso_now()),
        "ts": event.get("ts", epoch_now()),
        **event
    }
    try:
        with open(BUS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[bus] 로그 쓰기 실패: {e}")

# -----------------------------
# attack_process 접근 헬퍼
# -----------------------------
def set_attack_process(p: Optional[subprocess.Popen]) -> None:
    global attack_process
    with attack_lock:
        attack_process = p

def get_attack_process() -> Optional[subprocess.Popen]:
    with attack_lock:
        return attack_process

# -----------------------------
# 상태파일 경로 유틸(MTD)
# -----------------------------
def default_state_file() -> str:
    env = os.getenv("STATE_FILE")
    if env:
        return env
    shared = "/shared/mtd_state.json"
    if os.path.exists(shared) or os.path.isdir(os.path.dirname(shared)):
        return shared
    return os.path.join(LPC_DIR, "mtd", "shared_state", "mtd_state.json")

def read_mtd_target(state_file: str) -> Tuple[Optional[str], Optional[int]]:
    """
    mtd_state.json에서 current_target을 읽어 ('IP', PORT) 반환.
    형식: "10.13.0.3:14550"
    """
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            st = json.load(f)
        cur = st.get("current_target") or ""
        ip, port = cur.split(":")[0], int(cur.split(":")[1])
        return ip, port
    except Exception:
        return None, None

# -----------------------------
# 공격 프로필/목록
# -----------------------------
def load_attack_profiles():
    try:
        with open(ATTACK_PROFILES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 프로필 파일 없음: {ATTACK_PROFILES_PATH}")
        return {}
    except json.JSONDecodeError:
        print(f"❌ 프로필 JSON 파싱 실패: {ATTACK_PROFILES_PATH}")
        return {}

def get_available_attacks():
    if not os.path.isdir(ATTACKS_DIR):
        return []
    return sorted([f for f in os.listdir(ATTACKS_DIR) if f.endswith('.sh')])

# -----------------------------
# Docker 네트워크 스냅샷 (CLI 기반)
# -----------------------------
def _docker_ps_ids(name_prefix: Optional[str], label: Optional[str]) -> List[str]:
    cmd = ["docker", "ps", "-q"]
    if name_prefix:
        cmd += ["--filter", f"name=^{name_prefix}"]
    if label:
        cmd += ["--filter", f"label={label}"]
    try:
        out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace").strip()
        if not out:
            return []
        return [x for x in out.splitlines() if x]
    except Exception:
        return []

def _docker_inspect(cid: str) -> Optional[Dict[str, Any]]:
    try:
        out = subprocess.check_output(["docker", "inspect", cid], text=True, encoding="utf-8", errors="replace")
        arr = json.loads(out)
        return arr[0] if arr else None
    except Exception:
        return None

def snapshot_docker_networks(context: str, name_prefix: Optional[str], label: Optional[str]) -> None:
    cids = _docker_ps_ids(name_prefix, label)
    containers = []
    for cid in cids:
        info = _docker_inspect(cid)
        if not info:
            continue
        name = info.get("Name", "").lstrip("/")
        state = info.get("State", {})
        networks = info.get("NetworkSettings", {}).get("Networks", {}) or {}
        ports = info.get("NetworkSettings", {}).get("Ports", {}) or {}
        net_list = []
        for net_name, net in networks.items():
            net_list.append({
                "network": net_name,
                "ip": net.get("IPAddress"),
                "mac": net.get("MacAddress"),
                "gateway": net.get("Gateway"),
                "alias": net.get("Aliases"),
            })
        port_list = []
        for k, maps in ports.items():
            if maps:
                for m in maps:
                    port_list.append({"container_port": k, "host_ip": m.get("HostIp"), "host_port": m.get("HostPort")})
        containers.append({
            "id": cid[:12],
            "name": name,
            "running": bool(state.get("Running")),
            "pid": state.get("Pid"),
            "started_at": state.get("StartedAt"),
            "networks": net_list,
            "ports": port_list,
            "labels": info.get("Config", {}).get("Labels", {}),
            "image": info.get("Config", {}).get("Image"),
        })

    write_bus({
        "source": "attack_orchestrator",
        "type": "docker_net_snapshot",
        "context": context,  # pre_attack / interval / post_attack
        "filters": {"name_prefix": name_prefix, "label": label},
        "containers": containers,
    })

# -----------------------------
# 프로세스 제어/출력 스트림
# -----------------------------
def terminate_attack_process(reason: str = "manual"):
    ap = get_attack_process()
    if ap and ap.poll() is None:
        print(f"\n공격 프로세스 그룹 종료 중... (pid={ap.pid}, reason={reason})")
        write_bus({
            "source": "attack_orchestrator",
            "type": "attack_terminating",
            "reason": reason,
            "attack_pid": ap.pid,
        })
        try:
            os.killpg(os.getpgid(ap.pid), signal.SIGTERM)
            time.sleep(1)
            if ap.poll() is None:
                os.killpg(os.getpgid(ap.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"❌ 종료 오류: {e}")
    stop_event.set()

def _stream_reader(pipe, stream_name: str, attack_name: str):
    for line in iter(pipe.readline, ''):
        line = line.rstrip("\n")
        write_bus({
            "source": "attack_orchestrator",
            "type": f"attack_{stream_name}",
            "attack": attack_name,
            "line": line
        })
    pipe.close()

# -----------------------------
# 히트 이벤트 파싱(유연)
# -----------------------------
def _get(d: Dict[str, Any], *keys, default=None):
    cur = d
    try:
        for k in keys:
            cur = cur[k]
        return cur
    except Exception:
        return default

def _etype(evt: Dict[str, Any]) -> str:
    return (
        evt.get("type")
        or evt.get("event_type")
        or _get(evt, "data", "type")
        or _get(evt, "data", "event_type")
        or ""
    )

def parse_as_hit(evt: Dict[str, Any], want_ip: str, want_port: int, accept_types: set) -> Optional[Dict[str, Any]]:
    etype = _etype(evt)
    if accept_types and etype not in accept_types:
        if etype != "attack_surface_hit":
            return None

    proto = (evt.get("proto") or evt.get("protocol") or
             _get(evt, "net", "proto") or _get(evt, "data", "proto") or "").lower()

    dst_ip = (evt.get("dst_ip") or evt.get("dip") or evt.get("dest_ip") or
              _get(evt, "net", "dst_ip") or _get(evt, "data", "dst_ip"))

    dst_port = (evt.get("dst_port") or evt.get("dport") or
                _get(evt, "net", "dst_port") or _get(evt, "data", "dst_port"))

    if etype == "attack_surface_hit" and not (dst_ip and dst_port):
        target = evt.get("target") or _get(evt, "data", "target")
        if isinstance(target, str) and ":" in target:
            try:
                ti, tp = target.split(":")
                dst_ip, dst_port = ti, int(tp)
                proto = proto or "udp"
            except Exception:
                pass

    try:
        if isinstance(dst_port, str):
            dst_port = int(dst_port)
    except Exception:
        dst_port = None

    if dst_ip == want_ip and dst_port == want_port:
        return {
            "src_ip": evt.get("src_ip") or _get(evt, "net", "src_ip") or _get(evt, "data", "src_ip"),
            "src_port": evt.get("src_port") or _get(evt, "net", "src_port") or _get(evt, "data", "src_port"),
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "proto": proto or ""
        }
    return None

# -----------------------------
# 게이트: 타게팅 빈도 충족 시 공격 허용
# -----------------------------
def wait_for_targeting_gate(
    *,
    state_file: str,
    window_sec: float,
    min_hits: int,
    accept_types: List[str],
    timeout_sec: float,
    match_port_override: Optional[int],
    reset_on_shuffle: bool,
    require_unique_src: bool
) -> bool:
    want_ip, want_port = read_mtd_target(state_file)
    if want_ip is None or want_port is None:
        print(f"⚠️ state_file({state_file})에서 current_target을 읽지 못했습니다.")
        return False
    if match_port_override:
        want_port = match_port_override

    write_bus({
        "source": "attack_orchestrator",
        "type": "attack_gate_waiting",
        "want_ip": want_ip,
        "want_port": want_port,
        "window_sec": window_sec,
        "min_hits": min_hits,
        "timeout_sec": timeout_sec,
        "reset_on_shuffle": reset_on_shuffle,
        "require_unique_src": require_unique_src,
        "accept_types": accept_types
    })

    acc_types = set(t.strip() for t in accept_types if t.strip())
    hits: Deque[Tuple[float, Optional[str]]] = deque()
    t0 = time.time()
    shuffle_count = 0

    try:
        with open(BUS_LOG_PATH, "r", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)

            last_state_refresh = 0.0

            while True:
                if time.time() - t0 > timeout_sec:
                    write_bus({
                        "source": "attack_orchestrator",
                        "type": "attack_gate_timeout",
                        "elapsed_sec": time.time() - t0,
                        "hits_in_window": len(hits),
                        "mtd_shuffle_count": shuffle_count,
                        "want_ip": want_ip,
                        "want_port": want_port
                    })
                    return False

                now_wall = time.time()
                if now_wall - last_state_refresh >= 1.0:
                    s_ip, s_port = read_mtd_target(state_file)
                    if s_ip and s_port:
                        changed = (s_ip != want_ip) or (match_port_override is None and s_port != want_port)
                        if changed:
                            want_ip = s_ip
                            if match_port_override is None:
                                want_port = s_port
                            if reset_on_shuffle:
                                hits.clear()
                            write_bus({
                                "source": "attack_orchestrator",
                                "type": "attack_gate_target_update",
                                "want_ip": want_ip,
                                "want_port": want_port,
                                "reason": "state_file_poll"
                            })
                    last_state_refresh = now_wall

                pos = f.tell()
                line = f.readline()
                if not line:
                    time.sleep(POLL_INTERVAL_SEC)
                    f.seek(pos)
                    continue

                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = _etype(evt)

                if etype in ("mtd_action", "mtd_target_swap"):
                    action = evt.get("action") or _get(evt, "data", "action") or ""
                    if etype == "mtd_target_swap":
                        new_target = evt.get("to") or _get(evt, "data", "to") or ""
                    else:
                        new_target = evt.get("new_target") or _get(evt, "data", "new_target") or ""

                    if (action == "ip_shuffle") or new_target:
                        try:
                            if ":" in new_target:
                                want_ip_new, want_port_new = new_target.split(":")[0], int(new_target.split(":")[1])
                                want_ip = want_ip_new
                                if match_port_override is None:
                                    want_port = want_port_new
                            if reset_on_shuffle:
                                hits.clear()
                        except Exception:
                            pass

                        write_bus({
                            "source": "attack_orchestrator",
                            "type": "attack_gate_target_update",
                            "want_ip": want_ip,
                            "want_port": want_port,
                            "reset_on_shuffle": reset_on_shuffle,
                            "shuffle_count": shuffle_count
                        })
                        shuffle_count += 1
                        continue

                hit = parse_as_hit(evt, want_ip, want_port, acc_types)
                if hit:
                    now = evt.get("ts", epoch_now())
                    src = hit.get("src_ip")

                    hits.append((now, src))
                    while hits and (now - hits[0][0] > window_sec):
                        hits.popleft()

                    if require_unique_src:
                        uniq = len({s for _, s in hits if s})
                        current = uniq
                    else:
                        current = len(hits)

                    write_bus({
                        "source": "attack_orchestrator",
                        "type": "attack_gate_hit",
                        "want_ip": want_ip,
                        "want_port": want_port,
                        "current_hits_in_window": current,
                        "hit_src": src
                    })

                    if current >= min_hits:
                        write_bus({
                            "source": "attack_orchestrator",
                            "type": "attack_gate_open",
                            "hits_in_window": current,
                            "window_sec": window_sec,
                            "mtd_shuffle_count": shuffle_count,
                            "want_ip": want_ip,
                            "want_port": want_port
                        })
                        return True

    except FileNotFoundError:
        print(f"⚠️ {BUS_LOG_PATH} 없음: 게이트 기능 사용 불가")
        return False
    except Exception as e:
        print(f"❌ 게이트 로직 오류: {e}")
        write_bus({"source": "attack_orchestrator", "type": "attack_gate_error", "error": str(e)})
        return False

# -----------------------------
# MTD 이벤트 감시 (공격 중 단절)
# -----------------------------
def _extract_target_from_evt(evt: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
    new_target = (evt.get("new_target") or _get(evt, "data", "new_target") or
                  evt.get("to") or _get(evt, "data", "to") or "")
    if isinstance(new_target, str) and ":" in new_target:
        try:
            ip, port = new_target.split(":")
            return ip, int(port)
        except Exception:
            return None, None
    return None, None

def watch_bus_for_mtd(
    attack_name: str,
    started_at: float,
    stop_on_mtd: bool,
    mtd_grace_sec: float,
    stop_types: set,
    stop_only_if_target_changed: bool,
    attack_target_ip: Optional[str],
    attack_target_port: Optional[int],
):
    if not stop_on_mtd:
        return

    print(f"MTD 이벤트 감시 시작: {BUS_LOG_PATH} (grace={mtd_grace_sec}s)")
    try:
        with open(BUS_LOG_PATH, 'r', encoding='utf-8') as f:
            f.seek(0, os.SEEK_END)
            while not stop_event.is_set():
                ap = get_attack_process()
                if not ap or ap.poll() is not None:
                    break

                pos = f.tell()
                line = f.readline()
                if not line:
                    time.sleep(POLL_INTERVAL_SEC)
                    f.seek(pos)
                    continue

                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = _etype(evt)
                if etype not in stop_types:
                    continue

                # grace 기간 내 이벤트는 무시
                if (time.time() - started_at) < mtd_grace_sec:
                    continue

                # 타겟이 실제로 바뀐 경우에만 중단 (옵션)
                if stop_only_if_target_changed and (attack_target_ip and attack_target_port):
                    new_ip, new_port = _extract_target_from_evt(evt)
                    if new_ip and new_port:
                        if (new_ip == attack_target_ip) and (new_port == attack_target_port):
                            # 동일 타겟으로의 이벤트면 무시
                            continue

                write_bus({
                    "source": "attack_orchestrator",
                    "type": "mtd_detected",
                    "attack": attack_name,
                    "mtd_event": evt
                })
                print("🚨 MTD 이벤트 감지! 공격 중지.")
                terminate_attack_process(reason="mtd_detected")
                break
    except FileNotFoundError:
        print(f"⚠️ {BUS_LOG_PATH} 없음: MTD 감시 비활성")
    except Exception as e:
        print(f"❌ MTD 감시 오류: {e}")
        terminate_attack_process(reason="watch_error")

# -----------------------------
# 메인
# -----------------------------
def main():
    signal.signal(signal.SIGINT, lambda s, f: terminate_attack_process("sigint"))
    signal.signal(signal.SIGTERM, lambda s, f: terminate_attack_process("sigterm"))

    attack_profiles = load_attack_profiles()
    available_attacks = get_available_attacks()

    parser = argparse.ArgumentParser(description="MTD 테스트베드 공격 오케스트레이터")
    parser.add_argument('-a', '--attack', required=True, choices=available_attacks,
                        help="실행할 공격 스크립트(.sh)")

    # 스냅샷/필터
    parser.add_argument('--snapshot-interval', type=float, default=float(os.getenv("SNAPSHOT_INTERVAL", "5")),
                        help="Docker 네트워크 스냅샷 주기(초). 0이면 비활성")
    parser.add_argument('--name-prefix', type=str, default=os.getenv("ATTACK_CONTAINER_PREFIX", ""),
                        help="docker name 프리픽스 필터 (예: dvd_)")
    parser.add_argument('--label', type=str, default=os.getenv("ATTACK_CONTAINER_LABEL", ""),
                        help="docker label 필터 (예: mtd=true)")

    # 게이트(타게팅 기반) 옵션
    parser.add_argument('--gate-enable', action='store_true',
                        help="게이트 활성화: 타게팅 히트 빈도 충족 시에만 공격 시작")
    parser.add_argument('--gate-window-sec', type=float, default=float(os.getenv("GATE_WINDOW_SEC", "3600")),
                        help="슬라이딩 윈도우 길이(초). 기본 1시간")
    parser.add_argument('--gate-min-hits', type=int, default=int(os.getenv("GATE_MIN_HITS", "10")),
                        help="윈도우 내 최소 히트 수(기본 10)")
    parser.add_argument('--gate-timeout-sec', type=float, default=float(os.getenv("GATE_TIMEOUT_SEC", "900")),
                        help="게이트 대기 타임아웃(초). 기본 900s=15분")
    parser.add_argument('--gate-types', type=str, default=os.getenv("GATE_TYPES", "net_packet,udp_packet,attack_surface_hit"),
                        help="히트로 인정할 이벤트 type 목록(콤마구분)")
    parser.add_argument('--gate-match-port', type=int, default=int(os.getenv("GATE_MATCH_PORT", "0")),
                        help="타겟 포트를 강제 지정(0이면 mtd_state의 포트 사용)")
    parser.add_argument('--gate-reset-on-shuffle', action='store_true',
                        help="MTD ip_shuffle 발생 시 히트 카운트를 리셋")
    parser.add_argument('--gate-require-unique-src', action='store_true',
                        help="서로 다른 출발지 IP만 카운트(유니크 소스 기준)")

    # MTD 감시 동작 옵션
    default_stop = os.getenv("STOP_ON_MTD", "0") == "1"
    parser.add_argument('--stop-on-mtd', dest='stop_on_mtd', action='store_true',
                        default=default_stop, help="MTD 이벤트 수신 시 공격을 중단(기본: 비활성)")
    parser.add_argument('--no-stop-on-mtd', dest='stop_on_mtd', action='store_false',
                        help="MTD 이벤트가 와도 공격을 중단하지 않음")
    parser.add_argument('--mtd-grace-sec', type=float, default=float(os.getenv("MTD_GRACE_SEC", "3")),
                        help="공격 시작 직후 MTD 이벤트를 무시할 유예 시간(초)")
    parser.add_argument('--mtd-stop-types', type=str,
                        default=os.getenv("MTD_STOP_TYPES", "mtd_action,mtd_triggered,mtd_start,mtd_target_swap"),
                        help="중단 트리거가 될 MTD 이벤트 타입 목록(콤마구분)")
    parser.add_argument('--mtd-stop-only-if-target-changed', action='store_true',
                        help="이벤트에 포함된 new_target/to가 현재 공격 타겟과 다를 때만 중단")

    # MTD 상태파일
    parser.add_argument('--state-file', type=str, default=default_state_file(),
                        help="MTD 상태파일 경로 (current_target/decoy_target)")
    args = parser.parse_args()

    attack_script_path = os.path.join(ATTACKS_DIR, args.attack)
    attack_profiles = load_attack_profiles()
    attack_profile = attack_profiles.get(args.attack, {})
    attack_type = attack_profile.get('type', 'IMMEDIATE')

    # 자식 프로세스가 repo 루트를 import 가능하도록 PYTHONPATH 추가
    project_root = os.path.realpath(os.path.join(LPC_DIR, '..', '..'))
    process_env = os.environ.copy()
    process_env['PYTHONPATH'] = f"{project_root}:{process_env.get('PYTHONPATH','')}"

    # 공격 시작 예정 이벤트(게이트 전에 기록)
    write_bus({
        "source": "attack_orchestrator",
        "type": "attack_start_intent",
        "attack": args.attack,
        "profile": attack_profile,
        "script_path": attack_script_path
    })

    # 게이트: 타게팅 빈도 충족될 때까지 대기
    if args.gate_enable:
        ok = wait_for_targeting_gate(
            state_file=args.state_file,
            window_sec=args.gate_window_sec,
            min_hits=args.gate_min_hits,
            accept_types=[t.strip() for t in args.gate_types.split(",")],
            timeout_sec=args.gate_timeout_sec,
            match_port_override=(None if args.gate_match_port == 0 else args.gate_match_port),
            reset_on_shuffle=args.gate_reset_on_shuffle,
            require_unique_src=args.gate_require_unique_src
        )
        if not ok:
            print("⛔ 게이트 불충족/타임아웃으로 공격을 시작하지 않습니다.")
            write_bus({
                "source": "attack_orchestrator",
                "type": "attack_gate_blocked",
                "attack": args.attack
            })
            return
    else:
        write_bus({
            "source": "attack_orchestrator",
            "type": "attack_gate_bypassed",
            "reason": "disabled"
        })

    # 시작 전 컨테이너 상태 스냅샷
    snapshot_docker_networks("pre_attack", args.name_prefix, args.label)

    # 실제 공격 시작
    try:
        print("--- 공격 시작 ---")
        print(f"  - 공격 이름: {args.attack}")
        print(f"  - 공격 타입: {attack_type}")
        print(f"  - 스크립트: {attack_script_path}")
        print("-----------------")

        write_bus({
            "source": "attack_orchestrator",
            "type": "attack_started_by_orchestrator",
            "attack": args.attack,
            "profile": attack_profile,
            "script_path": attack_script_path
        })

        proc = subprocess.Popen(
            ['/bin/bash', attack_script_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            preexec_fn=os.setsid,
            env=process_env
        )
        set_attack_process(proc)

        # 공격 시작 시점/시작 타겟 기록(옵션 비교용)
        started_at = time.time()
        attack_target_ip, attack_target_port = read_mtd_target(args.state_file)

        # STDOUT/ERR 스트리밍
        t_out = threading.Thread(target=_stream_reader, args=(proc.stdout, "stdout", args.attack), daemon=True)
        t_err = threading.Thread(target=_stream_reader, args=(proc.stderr, "stderr", args.attack), daemon=True)
        t_out.start(); t_err.start()

        # MTD 감시 스레드(옵션에 따라)
        stop_types = set(t.strip() for t in args.mtd_stop_types.split(",") if t.strip())
        t_mtd = threading.Thread(
            target=watch_bus_for_mtd,
            args=(
                args.attack,
                started_at,
                args.stop_on_mtd,
                args.mtd_grace_sec,
                stop_types,
                args.mtd_stop_only_if_target_changed,
                attack_target_ip,
                attack_target_port,
            ),
            daemon=True
        )
        t_mtd.start()

        # 주기 스냅샷 루프
        if args.snapshot_interval and args.snapshot_interval > 0:
            while not stop_event.is_set():
                ap = get_attack_process()
                if not ap or ap.poll() is not None:
                    break
                time.sleep(args.snapshot_interval)
                snapshot_docker_networks("interval", args.name_prefix, args.label)

        # 종료 대기
        ap = get_attack_process()
        rc = ap.wait() if ap else 0
        stop_event.set()
        t_out.join(timeout=1.0)
        t_err.join(timeout=1.0)

        # 종료 후 스냅샷
        snapshot_docker_networks("post_attack", args.name_prefix, args.label)

        write_bus({
            "source": "attack_orchestrator",
            "type": "attack_terminated",
            "attack": args.attack,
            "return_code": rc
        })
        print("\n--- 공격 스크립트 종료 ---")
        print(f"Return Code: {rc}")

    except FileNotFoundError:
        print(f"❌ 스크립트 없음: {attack_script_path}")
        write_bus({
            "source": "attack_orchestrator",
            "type": "attack_error",
            "attack": args.attack,
            "error": f"script_not_found:{attack_script_path}"
        })
    except Exception as e:
        print(f"❌ 공격 실행 오류: {e}")
        write_bus({
            "source": "attack_orchestrator",
            "type": "attack_exception",
            "attack": args.attack,
            "error": str(e)
        })
    finally:
        terminate_attack_process("finalize")
        set_attack_process(None)
        print("공격 오케스트레이터 종료.")

if __name__ == "__main__":
    main()
