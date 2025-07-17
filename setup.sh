#!/bin/bash
# DVD 공격 시나리오 자동 설정 스크립트

echo "🚁 DVD 공격 시나리오 환경 설정을 시작합니다..."

# 1. 디렉토리 구조 생성
echo "📁 디렉토리 구조 생성 중..."
mkdir -p dvd_lite/dvd_attacks/{core,reconnaissance,protocol_tampering,denial_of_service,injection,exfiltration,firmware_attacks,utils,registry}
mkdir -p tests

# 2. __init__.py 파일들 생성
echo "📝 __init__.py 파일들 생성 중..."

# dvd_lite/__init__.py
cat > dvd_lite/__init__.py << 'EOF'
"""
DVD-Lite 패키지
"""
__version__ = "1.0.0"
EOF

# 각 디렉토리에 빈 __init__.py 생성
touch dvd_lite/dvd_attacks/__init__.py
touch dvd_lite/dvd_attacks/core/__init__.py
touch dvd_lite/dvd_attacks/reconnaissance/__init__.py
touch dvd_lite/dvd_attacks/protocol_tampering/__init__.py
touch dvd_lite/dvd_attacks/denial_of_service/__init__.py
touch dvd_lite/dvd_attacks/injection/__init__.py
touch dvd_lite/dvd_attacks/exfiltration/__init__.py
touch dvd_lite/dvd_attacks/firmware_attacks/__init__.py
touch dvd_lite/dvd_attacks/utils/__init__.py
touch dvd_lite/dvd_attacks/registry/__init__.py
touch tests/__init__.py

# 3. requirements.txt 생성
echo "📦 requirements.txt 생성 중..."
cat > requirements.txt << 'EOF'
# DVD 공격 시나리오 의존성
asyncio-3.4.3; python_version < "3.7"
dataclasses; python_version < "3.7"
typing-extensions
enum34; python_version < "3.4"
EOF

# 4. .gitignore 생성
echo "🔒 .gitignore 생성 중..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Logs
*.log
logs/

# Environment
.env
.venv
env/
venv/
ENV/

# DVD specific
attack_results/
*.pcap
*.dump
EOF

# 5. 기본 테스트 파일 생성
echo "🧪 기본 테스트 파일 생성 중..."
cat > tests/test_basic.py << 'EOF'
"""
기본 테스트
"""
import unittest
import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBasic(unittest.TestCase):
    
    def test_imports(self):
        """기본 import 테스트"""
        try:
            from dvd_lite.main import DVDLite, BaseAttack, AttackType
            from dvd_lite.dvd_attacks.core.enums import DVDAttackTactic, DVDFlightState
            print("✅ 기본 import 성공")
        except ImportError as e:
            self.fail(f"Import 실패: {e}")
    
    def test_dvd_lite_creation(self):
        """DVD-Lite 인스턴스 생성 테스트"""
        try:
            from dvd_lite.main import DVDLite
            dvd = DVDLite()
            self.assertIsInstance(dvd, DVDLite)
            print("✅ DVD-Lite 인스턴스 생성 성공")
        except Exception as e:
            self.fail(f"DVD-Lite 생성 실패: {e}")

if __name__ == "__main__":
    unittest.main()
EOF

# 6. README.md 생성
echo "📖 README.md 생성 중..."
cat > README.md << 'EOF'
# DVD (Damn Vulnerable Drone) 공격 시나리오

드론 보안 테스트를 위한 모듈화된 공격 시나리오 프레임워크

## 빠른 시작

### 1. 환경 설정
```bash
# 자동 설정 (Linux/Mac)
chmod +x setup.sh
./setup.sh

# 수동 설정
pip install -r requirements.txt
```

### 2. 기본 테스트
```bash
python tests/test_basic.py
```

### 3. 실행
```bash
# 모든 데모 실행
python quick_start.py

# 특정 모드 실행
python quick_start.py single      # 단일 공격
python quick_start.py multiple    # 여러 공격
python quick_start.py interactive # 대화형 모드
python quick_start.py list        # 공격 목록
```

## 구조

```
dvd_lite/
├── main.py                    # DVD-Lite 베이스
└── dvd_attacks/
    ├── core/                  # 핵심 정의
    ├── reconnaissance/        # 정찰 공격
    ├── protocol_tampering/    # 프로토콜 조작
    ├── denial_of_service/     # DoS 공격
    ├── injection/             # 주입 공격
    ├── exfiltration/          # 데이터 탈취
    ├── firmware_attacks/      # 펌웨어 공격
    └── registry/              # 공격 관리
```

## 현재 구현된 공격

- WiFi 네트워크 발견
- MAVLink 서비스 발견  
- GPS 스푸핑
- 텔레메트리 데이터 탈취

## CTI 수집 활용

```python
from dvd_lite.main import DVDLite
from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks

dvd = DVDLite()
register_all_dvd_attacks(dvd)

# 공격 실행
result = await dvd.run_attack("wifi_network_discovery")
print(f"IOCs: {result.iocs}")
```
EOF

# 7. 권한 설정
echo "🔧 권한 설정 중..."
chmod +x quick_start.py

# 8. Python 패키지 설치 (가상환경 권장)
echo "📦 Python 패키지 설치 중..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "❌ Python이 설치되어 있지 않습니다."
    exit 1
fi

# pip 설치 확인
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo "❌ pip이 설치되어 있지 않습니다."
    exit 1
fi

# 가상환경 생성 권장
echo "💡 가상환경 사용을 권장합니다:"
echo "   python3 -m venv dvd_env"
echo "   source dvd_env/bin/activate  # Linux/Mac"
echo "   dvd_env\\Scripts\\activate     # Windows"

# 패키지 설치
echo "📦 의존성 설치 중..."
$PYTHON_CMD -m pip install --upgrade pip
$PYTHON_CMD -m pip install -r requirements.txt

echo ""
echo "✅ DVD 공격 시나리오 환경 설정 완료!"
echo ""
echo "🚀 다음 단계:"
echo "   1. 파일들을 해당 디렉토리에 복사"
echo "   2. python quick_start.py 실행"
echo "   3. python tests/test_basic.py 테스트"
echo ""
echo "📋 주요 명령어:"
echo "   python quick_start.py list        # 공격 목록"
echo "   python quick_start.py interactive # 대화형 실행"
echo "   python quick_start.py single      # 단일 공격 데모"