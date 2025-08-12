# Damn-Vulnerable-Drone LPC Testbed (dvd_lite)

드론 도메인에 특화된 **LPC(Loose Persistent Campaign)** 전술을 연구·평가하기 위한 테스트베드입니다.  
Damn-Vulnerable-Drone(DVD) 도커 환경과 연동되며, **공격/평가 콘솔(UI)**, **도커 운영 콘솔(UI)**, **ns-3 기반 링크 재현**을 포함합니다.

> ⚠️ **윤리/안전**: 본 프로젝트는 **자체 시뮬레이션/연구** 용도이며, 실환경/타인 자산/제3자 네트워크에의 적용을 금지합니다.

---

## 핵심 구성

dvd_lite/
├─ dvd_attacks_lpc/ # 공격·평가 코어
│ ├─ sh_core/ # 공용 코어(lpc_core.sh, lpc_bus.sh, lpc_phase.sh 등)
│ ├─ modules/ # 전술 모듈(.sh) - 효과 기반 로깅
│ ├─ primitives/ # 저수준 스텁
│ ├─ scenarios/ # .pipeline, options.d/{profile_.env, mission_phases.csv}
│ ├─ tools/ # bus2csv.py, lpc_metrics.py
│ ├─ eval/run_eval.sh # 원클릭 평가(버스→CSV/메트릭→ns-3)
│ └─ attack_output/ # 결과물(bus.log, bus.csv, effect_timeline.csv, metrics.csv, ns3_metrics.csv)
├─ lpc_ui/ # 공격/평가 실행 UI (Flask, :5001)
└─ dvd_ops_ui/ # DVD 도커 상태/로그/이벤트 UI (Flask, :5002)

yaml
복사
편집

---

## 아키텍처(요약)

[사용자]
│
├─ lpc_ui(:5001) ──(ENV/옵션)──▶ [run_scenario.sh / modules/.sh]
│ ├─ sh_core/lpc_core.sh (듀티/지터/백오프/윈도/페이즈)
│ ├─ modules/ (효과 계산 → lpc_bus.sh)
│ └─ lpc_bus.sh → attack_output/bus.log
│
├─ tools/bus2csv.py ─────▶ attack_output/effect_timeline.csv
├─ tools/lpc_metrics.py ─▶ attack_output/metrics.csv
└─ ns-3(scratch/drone_lpc_eval.cc) ◀ effect_timeline.csv
└─ attack_output/ns3_metrics.csv → metrics.csv에 병합

[운영]
└─ dvd_ops_ui(:5002) ◀ docker stats/logs/inspect/events(GCS/CC/FC/Sim)

yaml
복사
편집

---

## DVD 연계 환경(요약)

- 컨테이너: `ground-control-station`(GCS), `companion-computer`(CC), `flight-controller`(FC), `simulator`
- 네트워크:
  - Infra: `10.13.0.0/24` (예: Sim `10.13.0.5`)
  - Wi-Fi 모드: SSID `Drone_Wifi`, `192.168.13.0/24`
- 주요 포트(예): simulator `8000/8080/9002`, companion `3000`, flight-controller `5760/9003`

---

## 빠른 시작 (Quickstart)

### 0) DVD 띄우기
```bash
cd ~/MTD/MTD_full_testbed/Damn-Vulnerable-Drone
sudo ./start.sh --wifi
# simulator: http://localhost:8000
1) 단일 모듈 스모크
bash
복사
편집
cd ~/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc
export DVD_C_GCS=ground-control-station
export DVD_C_CC=companion-computer
export DVD_C_FC=flight-controller

# 3회, 300ms 간격, 강도 예시
LPC_WINDOW="" LPC_MAX_BUDGET=3 LPC_INTERVAL_MS=300 LPC_STEP=0.8 ./modules/waypoint_drift.sh
tail -n +1 attack_output/bus.log
2) 시나리오 실행(페이즈/프로필 적용)
bash
복사
편집
export LPC_PROFILE="scenarios/options.d/profile_stealth.env"
export LPC_PHASE_FILE="scenarios/options.d/mission_phases.csv"
./run_scenario.sh scenarios/S_lpc_v2.pipeline
3) 평가(+ ns-3 링크 재현)
bash
복사
편집
# bus→timeline→metrics + ns-3 실행→ns3_metrics.csv 생성→metrics.csv에 병합
SIM_TIME=90 ./eval/run_eval.sh scenarios/S_lpc_v2.pipeline
column -t -s, attack_output/metrics.csv
4) UI
bash
복사
편집
# 공격/평가 콘솔
cd ~/MTD/MTD_full_testbed/dvd_lite/lpc_ui && ./run.sh    # http://127.0.0.1:5001

# DVD 도커 운영 콘솔
cd ~/MTD/MTD_full_testbed/dvd_lite/dvd_ops_ui && ./run.sh # http://127.0.0.1:5002
환경변수 레퍼런스
변수	의미	기본	비고
LPC_DUTY	act() 실행 확률(0–1)	0.10	듀티사이클
LPC_INTERVAL_MS	인터벌(ms)	15000	지터·백오프 반영
LPC_JITTER_PCT	인터벌 지터(%)	30	
LPC_BACKOFF	MTD 이벤트 시 간격 증가	exp	`none
LPC_MAX_BUDGET	총 실행 횟수	120	종료 조건
LPC_STEP	모듈 강도(미세)	0.02	drift(m)/residual/%p 등
LPC_NOISE	강도 노이즈(±비율)	0.20	0.2 → ±20%
LPC_ROTATE_TARGETS	타깃 회전	roundrobin	or random
LPC_WINDOW	시간창	""	예: "01:00-05:00"
LPC_SEED	듀티 시드	""	재현성
LPC_PROFILE	프리셋 env		scenarios/options.d/profile_*.env
LPC_PHASE_FILE	페이즈 csv		scenarios/options.d/*.csv
DVD_C_GCS	GCS 컨테이너명	auto	예: ground-control-station
DVD_C_CC	CC 컨테이너명	auto	예: companion-computer
DVD_C_FC	FC 컨테이너명	auto	예: flight-controller

우선순위: 라인 오버라이드 > 페이즈 > 프로필 > 기본값

전술 모듈(예시)
항법/경로: waypoint_drift.sh → position_drift +Xm, mission_bias +Xm

센서융합: sensor_fusion_noise.sh → sensor_residual +Y, mission_bias +Y

운용/RTH: safe_rth_penalty.sh → rth_margin -Z%

링크/QoS: telemetry_trickle_jam.sh, telemetry_burst_drop.sh → link_jitter +ms, packet_loss +%

에너지/기동: battery_route_drain.sh → energy_delta +Wh, flight_time_loss +t

모든 모듈은 **효과(Effect)**만 bus.log에 기록(파괴적 동작 없음). 평가/라벨링·학습에 최적화.

시나리오/페이즈/프로필
scenarios/*.pipeline: 줄 단위로 모듈 실행 + 라인 오버라이드 지원

scenarios/options.d/profile_*.env: 기본 파라미터 세트(stealth/balanced/escalate 등)

scenarios/options.d/mission_phases.csv: 페이즈별 오버라이드

예) S_lpc_v2.pipeline 일부
bash
복사
편집
source scenarios/options.d/profile_stealth.env
export LPC_PHASE_FILE=scenarios/options.d/mission_phases.csv

LPC_MAX_BUDGET=6  LPC_INTERVAL_MS=800  LPC_STEP=0.8   ./modules/waypoint_drift.sh
LPC_MAX_BUDGET=6  LPC_INTERVAL_MS=1000 LPC_STEP=0.02  ./modules/telemetry_trickle_jam.sh
LPC_MAX_BUDGET=6  LPC_INTERVAL_MS=1200 LPC_STEP=0.015 ./modules/sensor_fusion_noise.sh
LPC_MAX_BUDGET=4  LPC_INTERVAL_MS=1500 LPC_STEP=0.010 ./modules/safe_rth_penalty.sh
평가 파이프라인
bus.log 축적 (modules → lpc_bus.sh)

bus2csv.py: bus.log → bus.csv + effect_timeline.csv

lpc_metrics.py: effect_timeline.csv → metrics.csv

ns-3(옵션): effect_timeline.csv의 packet_loss/link_jitter 이벤트를 반영하여 ns3_metrics.csv 생성

ns3_metrics.csv는 metrics.csv에 병합됨

기본 메트릭(확장 포함)
항법/임무: position_drift_m, mission_bias_sum, wp_deviation_m

에너지/시간: energy_delta_Wh, flight_time_loss

링크: link_jitter_ms, packet_loss_pct, (ns-3) ns3_throughput_bps, ns3_loss_rate_final, ns3_mean_abs_jitter_ms

융합/운용: sensor_residual, rth_margin_pct

운영: events_total

ns-3 연계
소스: /home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev/scratch/drone_lpc_eval.cc

매핑:

packet_loss p% → RateErrorModel::SetRate(p/100)

link_jitter Xms → 송신 앱의 다음 전송 간격에 ±Xms 적용(균일)

실행:

eval/run_eval.sh가 자동으로 scratch에 C++ 배치/빌드/실행 후 ns3_metrics.csv 병합

직접 실행 예:

bash
복사
편집
cd ~/MTD/MTD_full_testbed/ns-3.45/ns-3-dev
./waf build
./waf --run "scratch/drone_lpc_eval --timeline=/path/effect_timeline.csv --out=/path/ns3_metrics.csv --simTime=90"
UI 가이드
lpc_ui (:5001)
Run Type: Module / Scenario / Eval

옵션: LPC_*(DUTY/INTERVAL/JITTER/BACKOFF/BUDGET/STEP/WINDOW/SEED), LPC_PROFILE, LPC_PHASE_FILE, DVD_C_*

모니터: bus.log tail, Jobs, metrics.csv 프리뷰

force_now 체크 시 LPC_WINDOW 무시

dvd_ops_ui (:5002)
컨테이너 카드(역할 배지), 상태/포트/ID, 경량 CPU/MEM/NET 스냅샷

Logs 뷰어, Inspect 요약, Docker events(생성/재시작/종료)

Kill 버튼(실험 중단용, 주의)

지도학습/MTD 방향
데이터: effect_timeline.csv + DVD 로그(GCS/CC/FC/Sim) + Gazebo/FC 상태 + ns-3 출력

라벨: 공격 family(없음/nav/link/fusion/ops/energy …), 강도/페이즈

특징: 링크 통계(지연/손실/지터), 항법 누적 편향, EKF 잔차, 에너지 기울기, RTH margin 변화 등(슬라이딩 윈도)

모델: GBDT/LSTM/1D-CNN

MTD(RL): 상태(KPI+탐지출력) → 행동(채널/라우팅/서명/임계 재설정) → 보상(미션성공−편차−MTD비용−탐지누락+안전)

트러블슈팅
로그가 안 찍힘: LPC_WINDOW=""로 창 비활성, attack_output/bus.log 존재 확인

권한 문제: chmod +x modules/*.sh sh_core/*.sh eval/run_eval.sh

Docker 권한: 사용자 docker 그룹 추가 후 재로그인 sudo usermod -aG docker $USER

ns-3 빌드 실패: cd ns-3-dev && ./waf configure && ./waf -j$(nproc) build 로그 확인

ns-3 값이 0: 타임라인에 packet_loss/link_jitter 이벤트가 생성되는지 확인

컨테이너 이름 자동탐지 실패: DVD_C_GCS/CC/FC를 명시적으로 export

로드맵
formation_disruption.sh(군집 상대위치/타이밍 오차)

ns-3 지연 분포 모델(로그정규/파레토) 고도화

lpc_ui 전술 패밀리별 부분 예산 슬라이더

학습 스크립트(train_detect.py, mtd_env.py)와 리포트 자동화

라이선스 / 공지
연구·교육 목적. 실환경/타인 자산 사용 금지.

기여/이슈는 PR 또는 이슈 트래커를 통해 환영합니다.