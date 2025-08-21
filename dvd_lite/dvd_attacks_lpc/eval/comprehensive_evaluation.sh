#!/usr/bin/env bash
# 종합 평가 스크립트 - 공격 -> 분석 -> NS-3 -> 보고서 자동화

set -euo pipefail

BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
ATT_OUT="$BASE/attack_output"
SCENARIO="${1:-scenarios/S_comprehensive_attack.pipeline}"
SIM_TIME="${SIM_TIME:-120}"

echo "=== DVD-LPC 종합 평가 시작 ==="
echo "시나리오: $SCENARIO"
echo "시뮬레이션 시간: ${SIM_TIME}초"

# 1단계: 공격 실행
echo "[1/5] 공격 시나리오 실행..."
cd "$BASE"
./run_scenario.sh "$SCENARIO"

# 2단계: 타임라인 생성
echo "[2/5] 공격 타임라인 생성..."
python3 tools/bus2csv.py

# 3단계: 기본 메트릭 계산
echo "[3/5] 기본 메트릭 계산..."
python3 tools/lpc_metrics.py

# 4단계: NS-3 시뮬레이션 (선택적)
if [[ "${ENABLE_NS3:-true}" == "true" && -d "${NS3_ROOT:-}" ]]; then
    echo "[4/5] NS-3 네트워크 시뮬레이션..."
    eval/run_ns3_eval.sh "$ATT_OUT/effect_timeline.csv" "$ATT_OUT/ns3_metrics.csv" "$SIM_TIME"
else
    echo "[4/5] NS-3 시뮬레이션 스킵 (ENABLE_NS3=false 또는 NS3_ROOT 미설정)"
fi

# 5단계: 고급 분석 및 보고서
echo "[5/5] 고급 분석 및 보고서 생성..."
python3 tools/advanced_metrics.py --base-path "$BASE"

# 결과 요약
echo ""
echo "=== 평가 완료 ==="
echo "결과 파일:"
echo "  - 공격 로그: $ATT_OUT/bus.log"
echo "  - 효과 타임라인: $ATT_OUT/effect_timeline.csv"
echo "  - 기본 메트릭: $ATT_OUT/metrics.csv"
[[ -f "$ATT_OUT/ns3_metrics.csv" ]] && echo "  - NS-3 메트릭: $ATT_OUT/ns3_metrics.csv"
echo "  - 분석 보고서: $ATT_OUT/attack_analysis_report.json"
echo "  - 요약 보고서: $ATT_OUT/attack_summary.txt"

# 핵심 메트릭 미리보기
if [[ -f "$ATT_OUT/attack_summary.txt" ]]; then
    echo ""
    echo "=== 요약 ==="
    cat "$ATT_OUT/attack_summary.txt"
fi

echo ""
echo "상세 분석을 위해 다음을 실행하세요:"
echo "  column -t -s, $ATT_OUT/metrics.csv"
echo "  cat $ATT_OUT/attack_analysis_report.json | jq ."
