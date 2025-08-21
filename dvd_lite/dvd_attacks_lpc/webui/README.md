# 🌐 MTD 드론 보안 테스트베드 WebUI

완전한 웹 기반 사용자 인터페이스로 MTD 드론 보안 테스트베드를 제어하고 모니터링하세요.

## 🚀 빠른 시작

```bash
cd webui
./run.sh
```

웹 브라우저에서 http://localhost:5000 접속

## 📊 주요 기능

### 1. 실시간 대시보드
- 네트워크 성능 메트릭 실시간 모니터링
- 보안 위협 탐지 현황
- MTD 전략 적용 상태
- 시스템 리소스 사용률

### 2. 실험 제어 패널
- 다양한 공격 시나리오 선택 및 실행
- 방어 수준 설정
- 실험 진행 상황 실시간 추적
- 결과 자동 분석 및 보고서 생성

### 3. 데이터 분석
- 과거 실험 결과 비교 분석
- 통계적 유의성 검정
- 인터랙티브 차트 및 그래프
- 데이터 내보내기 (CSV, JSON)

### 4. DVD 통합
- Docker 컨테이너 상태 모니터링
- 네트워크 토폴로지 시각화
- 컨테이너 로그 실시간 조회
- 컨테이너 제어 (재시작, 중지)

### 5. NS-3 시뮬레이션
- 네트워크 시뮬레이션 실행 및 제어
- 시뮬레이션 결과 실시간 분석
- 토폴로지 구성 및 파라미터 조정

## 🏗️ 아키텍처

```
webui/
├── backend/           # Flask 백엔드
│   ├── app.py        # 메인 애플리케이션
│   ├── api/          # REST API 엔드포인트
│   ├── services/     # 비즈니스 로직
│   └── utils/        # 유틸리티 함수
├── frontend/         # 프론트엔드 리소스
│   ├── static/       # CSS, JS, 이미지
│   ├── templates/    # HTML 템플릿
│   └── components/   # 재사용 가능한 컴포넌트
└── config/           # 설정 파일
```

## 🔌 API 엔드포인트

### 시스템 제어
- `GET /api/system/status` - 시스템 상태 조회
- `POST /api/system/start` - 시스템 시작
- `POST /api/system/stop` - 시스템 중지

### 실험 관리
- `GET /api/experiments/scenarios` - 시나리오 목록
- `POST /api/experiments/run` - 실험 실행
- `GET /api/experiments/list` - 실험 결과 목록
- `GET /api/experiments/status/<id>` - 실험 상태 조회

### 데이터 조회
- `GET /api/data/metrics` - 메트릭 데이터
- `GET /api/data/statistics` - 통계 데이터
- `GET /api/data/realtime` - 실시간 데이터
- `GET /api/data/export/<format>` - 데이터 내보내기

### DVD 통합
- `GET /api/dvd/status` - DVD 컨테이너 상태
- `GET /api/dvd/container/<name>/logs` - 컨테이너 로그
- `POST /api/dvd/container/<name>/restart` - 컨테이너 재시작
- `GET /api/dvd/network` - 네트워크 정보

### NS-3 시뮬레이션
- `GET /api/ns3/status` - NS-3 상태
- `POST /api/ns3/run` - 시뮬레이션 실행
- `GET /api/ns3/results` - 시뮬레이션 결과
- `GET /api/ns3/topology` - 네트워크 토폴로지

## 🎛️ 실시간 통신

WebSocket을 통한 실시간 데이터 스트리밍:
- 메트릭 업데이트 브로드캐스트
- 시스템 상태 변경 알림
- 실험 진행 상황 실시간 업데이트
- DVD 컨테이너 이벤트 스트리밍

## 🔧 커스터마이징

### 차트 설정
`frontend/static/js/common.js`에서 차트 기본 옵션 수정

### 스타일 변경
`frontend/static/css/style.css`에서 UI 스타일 커스터마이징

### API 확장
`backend/api/` 디렉토리에 새로운 API 모듈 추가

## 📱 반응형 디자인

- 모바일, 태블릿, 데스크톱 완벽 지원
- Bootstrap 5 기반 반응형 레이아웃
- 터치 친화적 인터페이스

## 🌙 다크 모드

시스템 설정에 따른 자동 다크 모드 지원

---

**🎯 MTD 드론 보안 연구의 새로운 차원을 경험하세요!**
