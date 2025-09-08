#!/usr/bin/env bash
set -Eeuo pipefail

# ---------- 기본 경로 / 환경 ----------
BASE="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc"
cd "$BASE"

# venv 자동 활성화(있으면)
if [ -f ../../mtd_env/bin/activate ]; then
  # shellcheck disable=SC1091
  source ../../mtd_env/bin/activate || true
fi

# 환경 로드(확장판)
if [ -f ./00_env_ext.sh ]; then
  # shellcheck disable=SC1091
  source ./00_env_ext.sh
else
  echo "[WARN] 00_env_ext.sh 가 없어 기본 경로로 진행합니다."
  export OUT_DIR="$BASE/bus"
  export BUS_LOG="$OUT_DIR/bus.log"
  export BUS_DVD_LOG="$OUT_DIR/bus_dvd.log"
  mkdir -p "$OUT_DIR"
fi

echo "[ENV] BASE=$BASE"
echo "[ENV] OUT_DIR=$OUT_DIR"

# 옵션
FAST="${FAST:-0}"           # FAST=1 이면 가벼운 시나리오만
APPLY="${APPLY:-0}"         # APPLY=1 이면 실적용(tc/셔플). 기본 0(DRY)
CONF_TH="${CONF_TH:-0.60}"  # 신뢰도 임계치
WIN_S="${WIN_S:-5}"         # 슬라이딩 윈도 크기(sec)

# ---------- 0. 사전 점검 ----------
echo "[CHK] 디스크 여유/버스 폴더:"
df -h | awk 'NR==1 || /\/home|Filesystem/'
mkdir -p bus/captures/pcap

# ---------- 1. 시나리오 실행(데이터 생성) ----------
echo "[RUN] 시나리오 실행 시작"
bash scenarios/run_onoff_compare.sh || true
if [ "$FAST" = "0" ]; then
  bash scenarios/run_multi_parallel_example.sh || true
  # 필요 시: bash scenarios/run_mitre_wifi_recon_chain.sh || true
fi

echo "[CHK] 산출물 빠른 확인"
ls -lt bus/dvd_netanim_*.xml 2>/dev/null | head || true
ls -lt bus/ns3_metrics_*.csv 2>/dev/null | head || true
ls -lt bus/events_*.csv      2>/dev/null | head || true
find bus/captures/pcap -type f | tail -n 5 || true

# ---------- 2. 피처 생성 → 지도학습 ----------
echo "[ML] 윈도 피처 생성(WIN_S=${WIN_S})"
WIN_S="$WIN_S" python3 tools/make_window_features.py

echo "[ML] 분류기 학습(+리포트/모델 저장)"
python3 ml/train_attack_clf.py

# ---------- 3. 실시간 추론(정책 매핑) ----------
if [ "$APPLY" = "1" ]; then
  echo "[DET] 실적용 모드(DRY_RUN=0, CONF_TH=$CONF_TH)"
  WIN_S="$WIN_S" DRY_RUN=0 CONF_TH="$CONF_TH" bash scripts/run_detector.sh
else
  echo "[DET] DRY-RUN 모드(DRY_RUN=1, CONF_TH=$CONF_TH)"
  WIN_S="$WIN_S" DRY_RUN=1 CONF_TH="$CONF_TH" bash scripts/run_detector.sh
fi
tail -n 20 bus/detections.log || true

# ---------- 4. ns-3 메트릭 강제 보강(필요 시) ----------
echo "[NS3] NetAnim 기준 ns-3 메트릭 강제 생성(비어있을 때만)"
for XML in $(ls -1t bus/dvd_netanim_*.xml 2>/dev/null | head -n 50); do
  BAS="$(basename "$XML" .xml)" # dvd_netanim_<ATK>_<LV>_<MTD>_<SCN>
  SCN="${BAS##*_}"; tmp="${BAS%_${SCN}}"
  MTD="${tmp##*_}"; case "$MTD" in True|true) MTD=on;; False|false) MTD=off;; esac
  tmp="${BAS%_${MTD}_${SCN}}"; LV="${tmp##*_}"
  prefix="${BAS#dvd_netanim_}"; suffix="${LV}_${MTD}_${SCN}"
  ATK="${prefix%_${suffix}}"
  ETF="bus/effect_timeline_${SCN}.csv"
  [ -s "$ETF" ] || python3 tools/gen_effect_timestamp.py bus/bus.log --dvd bus/bus_dvd.log -o "$ETF" || true
  MET="bus/ns3_metrics_${ATK}_${LV}_${MTD}_${SCN}.csv"
  [ -s "$MET" ] || SIM_TIME=40 bash scripts/ns3_eval.sh "$SCN" "$ATK" "$LV" "$MTD" || true
done
ls -lt bus/ns3_metrics_*.csv 2>/dev/null | head || true

# ---------- 5. 결과 요약 ----------
echo "[RPT] 스루풋/드롭 등 요약 리포트 생성"
python3 tools/summarize_metrics.py || true
tail -n 10 bus/impact_report.csv 2>/dev/null || echo "[RPT] impact_report.csv 없음"

# ---------- 6. 다음 액션 힌트 ----------
echo
echo "=== NEXT SUGGESTIONS ==="
echo "• 표본 확대: run_onoff_compare/run_multi_parallel_example 추가 반복 → make_window_features → 재학습"
echo "• 임계치/윈도 스윕: for W in 3 5 8; do WIN_S=\$W python3 tools/make_window_features.py; python3 ml/train_attack_clf.py; done"
echo "• DRY→실적용 전환: APPLY=1 CONF_TH=0.65 ./quickstart_all.sh"
echo "• 용량 정리: docker system prune -af --volumes ; find bus/captures/pcap -type f -name '*.pcap' -mtime +3 -delete"
echo "========================="
