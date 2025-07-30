🎉 완성된 DVD 공격 도구 파일들
각 파일을 개별적으로 완성했습니다. 다음 순서로 설치하세요:

📋 설치 순서
1단계: 디렉토리 구조 생성

bash
# setup_directories.sh 실행
chmod +x setup_directories.sh
./setup_directories.sh
2단계: 파일들을 올바른 위치에 저장

bash
# 공통 모듈
colors.sh → /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/
utils.sh → /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/

# 정찰 공격 도구들  
wifi_discovery.sh → /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/
mavlink_discovery.sh → /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/
component_enum.sh → /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/
camera_discovery.sh → /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/

# 실행기들
run_reconnaissance.sh → /home/kali/MTD/MTD_full_testbed/
quick_start.sh → /home/kali/MTD/MTD_full_testbed/
3단계: 실행 권한 부여

bash
chmod +x /home/kali/MTD/MTD_full_testbed/*.sh
chmod +x /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/*.sh
4단계: 실행

bash
# 빠른 시작
sudo /home/kali/MTD/MTD_full_testbed/quick_start.sh

# 또는 대화형 실행
sudo /home/kali/MTD/MTD_full_testbed/run_reconnaissance.sh
🎯 완성된 기능들
✅ WiFi 네트워크 발견: Monitor mode + airodump-ng
✅ MAVLink 서비스 탐지: UDP/TCP 포트 스캔 + 프로토콜 테스트
✅ 드론 컴포넌트 열거: Nmap 기반 서비스 스캔
✅ 카메라 스트림 발견: RTSP/HTTP/MJPEG 스트림 탐지
✅ 자동 IOC 생성: 각 공격별 IOC 파일 생성
✅ JSON 리포트: 논문용 구조화된 데이터
✅ 컬러풀한 UI: 실시간 진행률 및 상태 표시
📊 생성되는 출력
IOC 파일: /tmp/*_iocs.txt
로그 파일: attack_logs/*.log
JSON 리포트: attack_output/dvd_reconnaissance_report_*.json
Nmap 결과: attack_output/*.xml
이제 각 파일을 저장하고 실행하면 완전한 DVD 정찰 공격 도구가 작동합니다! 🚀




