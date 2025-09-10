#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2attacks_sh.py (fixed)
- Damn-Vulnerable-Drone.wiki 하위 .md -> 공격 스크립트(.sh) 자동 생성기
- HTML <pre><code> 블록 + 펜스 코드블록 둘 다 지원
- $ 프롬프트만 허용(# 금지) -> Heading 오인 제거
- 설치/세팅 라인 필터링, 언어 휴리스틱, 원본 순서 유지
- 출력: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/modules/attacks_wiki/*.sh
"""

import os, re, sys, json, csv, stat, html
from pathlib import Path
from datetime import datetime

# ---------------- Paths ----------------
BASE = Path(os.environ.get("BASE", os.getcwd()))
WIKI_DIR = Path(os.environ.get("WIKI_DIR", str("/home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki")))
OUT_DIR = Path("../modules/attacks_wiki")
META_DIR = Path(os.environ.get("OUT_META", str(BASE / "attack_output")))
META_DIR.mkdir(parents=True, exist_ok=True)
INDEX_JSON = META_DIR / "attacks_wiki_index.json"
INDEX_CSV  = META_DIR / "attacks_wiki_index.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -------------- Rules/Heuristics --------------
SHELL_LANGS = {"bash", "sh", "zsh", "shell", "console"}
PY_LANGS    = {"python", "py"}

SHELL_HINTS = (
    r"\b(mavproxy|qgroundcontrol|airodump|aireplay|airmon|nmap|nping|hping3|iptables|socat|nc|netcat|tcpdump|tshark|iw|iwconfig|ip\s|route|arp|curl|wget|python3?\s+[-\w./]+\.py\b|python3?\s+-)\b",
)
SETUP_LINE = (
    r"(?i)^\s*(sudo\s+)?apt(-get)?\s+(update|install|upgrade)\b",
    r"(?i)^\s*(sudo\s+)?pip\d?\s+install\b",
    r"(?i)^\s*(pacman|yum|dnf|brew)\b",
)

RE_FENCE = re.compile(r"```([a-zA-Z0-9_+\-]*)\n(.*?)```", re.S)
RE_HTML_CODE = re.compile(r"<pre><code([^>]*)>(.*?)</code></pre>", re.S | re.I)
RE_PROMPT = re.compile(r"(?m)^[ \t]*\$\s+(?P<cmd>.+)$")

PY_PROLOGUE = r"""
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:127.0.0.1:14550')
    if ep.startswith('udp:'):
        try:
            _, rest = ep.split(':', 1)
            ep = rest
        except ValueError:
            pass
    # expect ip:port
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', ep):
        sys.argv = [sys.argv[0], ep]
"""

def sanitize_name(stem: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", stem.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "attack"

def is_setup_line(ln: str) -> bool:
    return any(re.search(p, ln) for p in SETUP_LINE)

def is_setup_block(text: str) -> bool:
    # 블록 내 대부분이 설치라인이면 설치블록으로 간주
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines: return False
    hits = sum(1 for l in lines if is_setup_line(l))
    return hits >= max(1, int(0.6*len(lines)))

def looks_shell(text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in SHELL_HINTS)

def guess_lang_from_body(body: str) -> str:
    t = body.strip()
    if is_setup_block(t):            # 1) 설치 블록은 무조건 shell
        return "shell"
    if re.search(r"(?m)^\s*(from|import)\s+\w+", t): return "python"
    if re.search(r"(?m)\bmavutil\.", t): return "python"
    if re.search(r"(?m)^\s*def\s+\w+\s*\(", t): return "python"
    if looks_shell(t): return "shell"
    return "shell"

def strip_prompt(line: str) -> str:
    m = re.match(r"^\s*\$\s+(?P<cmd>.+)\s*$", line)
    return m.group("cmd") if m else line

def collect_blocks(md_text: str):
    items = []
    for m in RE_FENCE.finditer(md_text):
        lang = (m.group(1) or "").strip().lower()
        body = m.group(2)
        items.append((m.start(), "fence", lang, body))
    for m in RE_HTML_CODE.finditer(md_text):
        attrs = (m.group(1) or "").lower()
        body  = html.unescape(m.group(2))
        lang = ""
        if "python" in attrs: lang = "python"
        elif any(l in attrs for l in ("bash","shell","sh","console")): lang = "shell"
        items.append((m.start(), "html", lang, body))
    for m in RE_PROMPT.finditer(md_text):
        items.append((m.start(), "prompt", "shell", m.group("cmd")))
    items.sort(key=lambda x: x[0])

    blocks = []
    for _, kind, lang, body in items:
        b = body.strip()
        if not b: 
            continue
        if kind in {"fence","html"}:
            l = (lang or "").strip().lower()
            if l in PY_LANGS:
                blocks.append(("python", b))
            elif l in SHELL_LANGS:
                blocks.append(("shell", b))
            else:
                blocks.append((guess_lang_from_body(b), b))
        elif kind == "prompt":
            blocks.append(("shell_line", strip_prompt(b)))
    return blocks

def filter_shell_text(text: str) -> str:
    out = []
    for ln in text.splitlines():
        raw = strip_prompt(ln)
        if not raw.strip(): 
            continue
        if re.match(r"^\s*#.*$", raw): 
            continue
        if is_setup_line(raw):        # 설치라인 제거
            continue
        out.append(raw)
    return "\n".join(out).strip()

def build_sh(stem: str, src_md: Path, blocks: list):
    attack_id = sanitize_name(stem)
    shead = f"""#!/usr/bin/env bash
# Auto-generated from: {src_md}
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${{BASE:-$PWD}}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${{DVD_LOG:-$BASE/attack_output/dvd.log}}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){{ echo "[`date +%F_%T`] $*"; }}; export -f log
fi

log "[ATTACK] id={attack_id} src={src_md.name}"
"""
    body_lines, nblock = [], 0
    for kind, body in blocks:
        # 설치 블록은 아예 스킵(셸 정리 후 비면 패스)
        if kind in {"shell","shell_line"}:
            cleaned = filter_shell_text(body if kind=="shell" else body)
            if not cleaned:
                continue
        if kind == "python" and is_setup_block(body):
            # 파이썬으로 잘못 표기된 설치블록: 제거
            continue

        nblock += 1
        body_lines.append(f'log "[BLOCK {nblock}] type={kind}"')

        if kind == "python":
            body_lines.append("python3 - <<'PY'")
            body_lines.append(PY_PROLOGUE.strip())
            body_lines.append(body.strip())
            body_lines.append("PY")
        elif kind == "shell":
            body_lines.append(cleaned)
        elif kind == "shell_line":
            body_lines.append(cleaned)
        body_lines.append("")  # blank between blocks

    if not body_lines:
        body_lines.append('log "[INFO] No executable blocks found; nothing to do."')

    return shead + "\n".join(body_lines) + "\n"

def main():
    if not WIKI_DIR.exists():
        print(f"[ERROR] Wiki dir not found: {WIKI_DIR}", file=sys.stderr)
        sys.exit(2)

    index_rows, generated = [], 0
    for md in sorted(WIKI_DIR.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        blocks = collect_blocks(text)
        exec_blocks = [(k,b) for (k,b) in blocks if k in {"python","shell","shell_line"}]
        if not exec_blocks:
            continue

        stem = sanitize_name(md.stem)
        sh_path = OUT_DIR / f"{stem}.sh"
        sh_text = build_sh(stem, md, exec_blocks)
        sh_path.write_text(sh_text, encoding="utf-8")
        sh_path.chmod(sh_path.stat().st_mode | stat.S_IEXEC)

        nshell = sum(1 for k,_ in exec_blocks if k.startswith("shell"))
        npy    = sum(1 for k,_ in exec_blocks if k == "python")
        index_rows.append({"md": str(md), "sh": str(sh_path), "shell_blocks": nshell, "python_blocks": npy})
        generated += 1
        print(f"[OK] {md.name} -> {sh_path.name} (shell={nshell}, py={npy})")

    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump({"generated": generated, "items": index_rows}, f, ensure_ascii=False, indent=2)
    with open(INDEX_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["md","sh","shell_blocks","python_blocks"])
        for r in index_rows: w.writerow([r["md"], r["sh"], r["shell_blocks"], r["python_blocks"]])

    print(f"[DONE] generated={generated} out_dir={OUT_DIR}")
    print(f"[INDEX] {INDEX_JSON}")
    print(f"[INDEX] {INDEX_CSV}")

if __name__ == "__main__":
    main()