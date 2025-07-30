#!/usr/bin/env python3
"""
DVD 환경 점검 스크립트
실제 공격 스크립트들의 존재 여부와 실행 가능성을 점검
"""

import os
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# 색상 코드
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

def print_colored(text: str, color: str):
    """색상이 있는 텍스트 출력"""
    print(f"{color}{text}{Colors.NC}")

def check_directory_structure() -> Dict[str, bool]:
    """디렉토리 구조 점검"""
    print_colored("=== 디렉토리 구조 점검 ===", Colors.BLUE)
    
    base_path = Path("/home/kali/MTD/MTD_full_testbed")
    dvd_attacks_path = base_path / "dvd_lite" / "dvd_attacks"
    
    checks = {
        "base_directory": base_path.exists(),
        "dvd_lite_directory": (base_path / "dvd_lite").exists(),
        "dvd_attacks_directory": dvd_attacks_path.exists(),
        "results_directory": (base_path / "results").exists(),
        "logs_directory": (base_path / "logs").exists()
    }
    
    for check_name, exists in checks.items():
        status = "✅ 존재" if exists else "❌ 없음"
        path = base_path if check_name == "base_directory" else base_path / check_name.replace("_directory", "").replace("_", "_")
        print(f"{check_name:25} {status} ({path})")
    
    return checks

def discover_attack_scripts() -> Dict[str, List[Path]]:
    """공격 스크립트 발견"""
    print_colored("\n=== 공격 스크립트 발견 ===", Colors.BLUE)
    
    dvd_attacks_path = Path("/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks")
    
    if not dvd_attacks_path.exists():
        print_colored("DVD attacks 디렉토리가 존재하지 않습니다.", Colors.RED)
        return {}
    
    discovered_scripts = {}
    
    # 하위 디렉토리 탐색
    for tactic_dir in dvd_attacks_path.iterdir():
        if not tactic_dir.is_dir():
            continue
        
        tactic_name = tactic_dir.name
        scripts = []
        
        # .sh 파일 찾기
        for sh_file in tactic_dir.glob("*.sh"):
            scripts.append(sh_file)
        
        if scripts:
            discovered_scripts[tactic_name] = scripts
            print(f"{tactic_name:25} ✅ {len(scripts)}개 스크립트 발견")
            for script in scripts:
                print(f"{'':27} └─ {script.name}")
        else:
            print(f"{tactic_name:25} ❌ 스크립트 없음")
    
    return discovered_scripts

def check_script_permissions(discovered_scripts: Dict[str, List[Path]]) -> Dict[str, Dict[str, bool]]:
    """스크립트 실행 권한 점검"""
    print_colored("\n=== 스크립트 실행 권한 점검 ===", Colors.BLUE)
    
    permission_status = {}
    
    for tactic, scripts in discovered_scripts.items():
        permission_status[tactic] = {}
        
        for script in scripts:
            # 파일 권한 확인
            file_stat = script.stat()
            is_executable = bool(file_stat.st_mode & stat.S_IEXEC)
            is_readable = bool(file_stat.st_mode & stat.S_IREAD)
            
            permission_status[tactic][script.name] = {
                'executable': is_executable,
                'readable': is_readable,
                'path': str(script)
            }
            
            status_str = []
            if is_readable:
                status_str.append("읽기가능")
            if is_executable:
                status_str.append("실행가능")
            
            if is_executable and is_readable:
                status_icon = "✅"
                status_color = Colors.GREEN
            elif is_readable:
                status_icon = "⚠️"
                status_color = Colors.YELLOW
            else:
                status_icon = "❌"
                status_color = Colors.RED
            
            status_text = " + ".join(status_str) if status_str else "접근불가"
            print(f"{tactic:15} {script.name:30} {status_icon} {status_text}")
    
    return permission_status

def check_script_content(discovered_scripts: Dict[str, List[Path]]) -> Dict[str, Dict[str, Dict]]:
    """스크립트 내용 분석"""
    print_colored("\n=== 스크립트 내용 분석 ===", Colors.BLUE)
    
    content_analysis = {}
    
    for tactic, scripts in discovered_scripts.items():
        content_analysis[tactic] = {}
        
        for script in scripts:
            try:
                with open(script, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                analysis = {
                    'line_count': len(content.split('\n')),
                    'has_shebang': content.startswith('#!'),
                    'has_echo': 'echo' in content,
                    'has_sleep': 'sleep' in content,
                    'has_python': any(word in content for word in ['python', 'python3']),
                    'has_network_tools': any(tool in content for tool in ['wget', 'curl', 'nc', 'nmap', 'ping']),
                    'size_bytes': len(content.encode('utf-8'))
                }
                
                content_analysis[tactic][script.name] = analysis
                
                # 분석 결과 출력
                features = []
                if analysis['has_shebang']:
                    features.append("shebang")
                if analysis['has_python']:
                    features.append("Python")
                if analysis['has_network_tools']:
                    features.append("네트워크도구")
                if analysis['has_sleep']:
                    features.append("지연명령")
                
                feature_str = ", ".join(features) if features else "기본스크립트"
                print(f"{tactic:15} {script.name:30} {analysis['line_count']:3}줄 ({feature_str})")
                
            except Exception as e:
                content_analysis[tactic][script.name] = {'error': str(e)}
                print(f"{tactic:15} {script.name:30} ❌ 읽기실패: {e}")
    
    return content_analysis

def check_system_dependencies() -> Dict[str, bool]:
    """시스템 의존성 점검"""
    print_colored("\n=== 시스템 의존성 점검 ===", Colors.BLUE)
    
    # 점검할 도구들
    tools_to_check = [
        'bash',
        'python3', 
        'wget',
        'curl',
        'nc',
        'nmap',
        'ping',
        'netstat',
        'ps',
        'kill'
    ]
    
    dependency_status = {}
    
    for tool in tools_to_check:
        try:
            result = subprocess.run(['which', tool], 
                                 capture_output=True, 
                                 text=True, 
                                 timeout=5)
            is_available = result.returncode == 0
            dependency_status[tool] = is_available
            
            if is_available:
                path = result.stdout.strip()
                print(f"{tool:15} ✅ 사용가능 ({path})")
            else:
                print(f"{tool:15} ❌ 없음")
                
        except subprocess.TimeoutExpired:
            dependency_status[tool] = False
            print(f"{tool:15} ⏰ 타임아웃")
        except Exception as e:
            dependency_status[tool] = False
            print(f"{tool:15} ❌ 오류: {e}")
    
    return dependency_status

def fix_permissions(discovered_scripts: Dict[str, List[Path]]) -> bool:
    """스크립트 권한 자동 수정"""
    print_colored("\n=== 스크립트 권한 자동 수정 ===", Colors.BLUE)
    
    fixed_count = 0
    error_count = 0
    
    for tactic, scripts in discovered_scripts.items():
        for script in scripts:
            try:
                # 현재 권한 확인
                current_stat = script.stat()
                is_executable = bool(current_stat.st_mode & stat.S_IEXEC)
                
                if not is_executable:
                    # 실행 권한 추가
                    new_mode = current_stat.st_mode | stat.S_IEXEC
                    script.chmod(new_mode)
                    fixed_count += 1
                    print(f"✅ 권한 수정: {script}")
                else:
                    print(f"✓  권한 정상: {script}")
                    
            except Exception as e:
                error_count += 1
                print(f"❌ 권한 수정 실패: {script} - {e}")
    
    if fixed_count > 0:
        print_colored(f"\n{fixed_count}개 스크립트 권한이 수정되었습니다.", Colors.GREEN)
    if error_count > 0:
        print_colored(f"{error_count}개 스크립트 권한 수정에 실패했습니다.", Colors.RED)
    
    return error_count == 0

def generate_summary_report(
    dir_checks: Dict[str, bool],
    discovered_scripts: Dict[str, List[Path]],
    dependency_status: Dict[str, bool]
) -> str:
    """요약 리포트 생성"""
    print_colored("\n=== 환경 점검 요약 ===", Colors.BLUE)
    
    total_dirs = len(dir_checks)
    valid_dirs = sum(dir_checks.values())
    
    total_tactics = len(discovered_scripts)
    total_scripts = sum(len(scripts) for scripts in discovered_scripts.values())
    
    total_tools = len(dependency_status)
    available_tools = sum(dependency_status.values())
    
    print(f"디렉토리 구조:     {valid_dirs}/{total_dirs} 정상")
    print(f"공격 전술:         {total_tactics}개 발견")
    print(f"공격 스크립트:     {total_scripts}개 발견")
    print(f"시스템 도구:       {available_tools}/{total_tools} 사용가능")
    
    # 전체 상태 판정
    if valid_dirs == total_dirs and total_scripts > 0 and available_tools >= total_tools * 0.8:
        overall_status = "✅ 환경 정상"
        status_color = Colors.GREEN
    elif total_scripts > 0 and available_tools >= total_tools * 0.6:
        overall_status = "⚠️  부분적 문제"
        status_color = Colors.YELLOW
    else:
        overall_status = "❌ 심각한 문제"
        status_color = Colors.RED
    
    print_colored(f"\n전체 상태: {overall_status}", status_color)
    
    return overall_status

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DVD 환경 점검 도구")
    parser.add_argument("--fix-permissions", action="store_true", help="스크립트 권한 자동 수정")
    parser.add_argument("--summary-only", action="store_true", help="요약만 출력")
    
    args = parser.parse_args()
    
    print_colored("DVD 환경 점검 도구", Colors.BLUE)
    print_colored("=" * 50, Colors.BLUE)
    
    # 1. 디렉토리 구조 점검
    dir_checks = check_directory_structure()
    
    # 2. 공격 스크립트 발견
    discovered_scripts = discover_attack_scripts()
    
    if not args.summary_only:
        # 3. 스크립트 권한 점검
        permission_status = check_script_permissions(discovered_scripts)
        
        # 4. 스크립트 내용 분석
        content_analysis = check_script_content(discovered_scripts)
        
        # 5. 시스템 의존성 점검
        dependency_status = check_system_dependencies()
        
        # 6. 권한 자동 수정 (옵션)
        if args.fix_permissions:
            fix_permissions(discovered_scripts)
    else:
        dependency_status = check_system_dependencies()
    
    # 7. 요약 리포트
    overall_status = generate_summary_report(dir_checks, discovered_scripts, dependency_status)
    
    # 추천 사항 출력
    print_colored("\n=== 추천 사항 ===", Colors.BLUE)
    
    if not all(dir_checks.values()):
        print("• 누락된 디렉토리를 생성하세요: mkdir -p results logs")
    
    if not discovered_scripts:
        print("• DVD 공격 스크립트가 없습니다. 레포지토리를 확인하세요.")
    
    if sum(dependency_status.values()) < len(dependency_status) * 0.8:
        missing_tools = [tool for tool, available in dependency_status.items() if not available]
        print(f"• 누락된 도구들을 설치하세요: sudo apt-get install {' '.join(missing_tools)}")
    
    if args.fix_permissions:
        print("• 권한이 수정되었습니다. 이제 공격 스크립트를 실행할 수 있습니다.")
    elif discovered_scripts:
        print("• 스크립트 권한 문제가 있다면 --fix-permissions 옵션을 사용하세요.")
    
    print(f"\n실행 명령:")
    print(f"  python3 real_attack_orchestrator.py --list     # 스크립트 목록 확인")
    print(f"  python3 real_attack_orchestrator.py           # 모든 공격 실행")
    print(f"  ./run_all_dvd_attacks.sh                      # 배치 스크립트로 실행")

if __name__ == "__main__":
    main()