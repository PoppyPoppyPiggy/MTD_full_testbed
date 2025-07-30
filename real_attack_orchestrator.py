#!/usr/bin/env python3
"""
실제 DVD 공격 스크립트 순회 실행기
기존 dvd_attacks 디렉토리의 실제 run_*.sh 스크립트들을 자동으로 찾아서 실행

구조:
/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/
├── reconnaissance/run_reconnaissance.sh
├── protocol_tampering/run_protocol_tampering.sh  
├── denial_of_service/run_denial_of_service.sh
├── injection/run_injection.sh
├── exfiltration/run_exfiltration.sh
└── firmware_attacks/run_firmware_attacks.sh
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import re

# =============================================================================
# 설정 및 상수
# =============================================================================

BASE_PATH = Path("/home/kali/MTD/MTD_full_testbed")
DVD_ATTACKS_PATH = BASE_PATH / "dvd_lite" / "dvd_attacks"
RESULTS_PATH = BASE_PATH / "results"
LOGS_PATH = BASE_PATH / "logs"

# 디렉토리 생성
RESULTS_PATH.mkdir(parents=True, exist_ok=True)
LOGS_PATH.mkdir(parents=True, exist_ok=True)

@dataclass
class AttackScriptResult:
    """공격 스크립트 실행 결과"""
    tactic: str
    script_path: str
    success: bool
    exit_code: int
    execution_time: float
    stdout: str
    stderr: str
    iocs: List[str]
    timestamp: str
    pid: int

# =============================================================================
# 로깅 설정
# =============================================================================

def setup_logging() -> logging.Logger:
    """로깅 시스템 초기화"""
    logger = logging.getLogger("DVD_Attack_Runner")
    logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 파일 핸들러
    file_handler = logging.FileHandler(
        LOGS_PATH / f"dvd_attack_runner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    file_handler.setLevel(logging.INFO)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 포맷터
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# =============================================================================
# 공격 스크립트 발견 및 실행
# =============================================================================

class DVDAttackScriptRunner:
    """DVD 공격 스크립트 실행기"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.discovered_scripts: Dict[str, Path] = {}
        self.results: List[AttackScriptResult] = []
        
    def discover_attack_scripts(self) -> Dict[str, Path]:
        """공격 스크립트 자동 발견"""
        self.logger.info("공격 스크립트 자동 발견 중...")
        
        if not DVD_ATTACKS_PATH.exists():
            self.logger.error(f"DVD attacks 경로를 찾을 수 없습니다: {DVD_ATTACKS_PATH}")
            return {}
        
        discovered = {}
        
        # dvd_attacks 하위 디렉토리 탐색
        for tactic_dir in DVD_ATTACKS_PATH.iterdir():
            if not tactic_dir.is_dir():
                continue
                
            tactic_name = tactic_dir.name
            
            # run_*.sh 스크립트 찾기
            possible_script_names = [
                f"run_{tactic_name}.sh",
                f"run_{tactic_name}s.sh",  # 복수형
                "run_attacks.sh",
                "run.sh",
                "attack.sh"
            ]
            
            script_found = False
            for script_name in possible_script_names:
                script_path = tactic_dir / script_name
                if script_path.exists() and script_path.is_file():
                    discovered[tactic_name] = script_path
                    self.logger.info(f"발견: {tactic_name} -> {script_path}")
                    script_found = True
                    break
            
            if not script_found:
                # 모든 .sh 파일 확인
                sh_files = list(tactic_dir.glob("*.sh"))
                if sh_files:
                    # 가장 그럴듯한 스크립트 선택
                    best_script = None
                    for sh_file in sh_files:
                        if "run" in sh_file.name.lower() or "attack" in sh_file.name.lower():
                            best_script = sh_file
                            break
                    
                    if best_script:
                        discovered[tactic_name] = best_script
                        self.logger.info(f"발견 (추정): {tactic_name} -> {best_script}")
                    else:
                        # 첫 번째 .sh 파일 사용
                        discovered[tactic_name] = sh_files[0]
                        self.logger.info(f"발견 (기본): {tactic_name} -> {sh_files[0]}")
                else:
                    self.logger.warning(f"공격 스크립트를 찾을 수 없습니다: {tactic_dir}")
        
        self.discovered_scripts = discovered
        self.logger.info(f"총 {len(discovered)}개의 공격 스크립트 발견됨")
        
        return discovered
    
    def inspect_script_content(self, script_path: Path) -> Dict[str, Any]:
        """스크립트 내용 분석"""
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            info = {
                'has_shebang': content.startswith('#!'),
                'line_count': len(content.split('\n')),
                'has_echo_commands': 'echo' in content,
                'has_sleep_commands': 'sleep' in content,
                'has_network_commands': any(cmd in content for cmd in ['wget', 'curl', 'nc', 'nmap']),
                'has_python_calls': 'python' in content,
                'estimated_duration': self._estimate_duration(content)
            }
            
            return info
            
        except Exception as e:
            self.logger.warning(f"스크립트 분석 실패 {script_path}: {e}")
            return {}
    
    def _estimate_duration(self, content: str) -> int:
        """스크립트 실행 시간 추정"""
        duration = 5  # 기본 5초
        
        # sleep 명령어 찾기
        sleep_matches = re.findall(r'sleep\s+(\d+)', content)
        if sleep_matches:
            duration += sum(int(match) for match in sleep_matches)
        
        # 복잡도에 따른 추가 시간
        if 'for' in content or 'while' in content:
            duration += 10
        if 'nmap' in content:
            duration += 30
        if 'wget' in content or 'curl' in content:
            duration += 10
            
        return min(duration, 300)  # 최대 5분
    
    async def run_attack_script(
        self, 
        tactic: str, 
        script_path: Path, 
        timeout: int = 300
    ) -> AttackScriptResult:
        """개별 공격 스크립트 실행"""
        self.logger.info(f"공격 스크립트 실행 시작: {tactic} ({script_path})")
        
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        
        try:
            # 스크립트 실행 권한 확인 및 부여
            if not os.access(script_path, os.X_OK):
                os.chmod(script_path, 0o755)
                self.logger.info(f"실행 권한 부여: {script_path}")
            
            # 스크립트 실행
            process = await asyncio.create_subprocess_exec(
                'bash', str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=script_path.parent  # 스크립트가 있는 디렉토리에서 실행
            )
            
            pid = process.pid
            self.logger.info(f"프로세스 시작됨: PID {pid}")
            
            try:
                # 타임아웃과 함께 프로세스 완료 대기
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
                
                exit_code = process.returncode
                execution_time = time.time() - start_time
                
                # 출력 디코딩
                stdout_text = stdout.decode('utf-8', errors='ignore')
                stderr_text = stderr.decode('utf-8', errors='ignore')
                
                # IOCs 추출
                iocs = self._extract_iocs_from_output(stdout_text, stderr_text)
                
                success = exit_code == 0
                
                self.logger.info(
                    f"스크립트 완료: {tactic} - "
                    f"종료코드: {exit_code}, "
                    f"실행시간: {execution_time:.2f}초, "
                    f"IOCs: {len(iocs)}개"
                )
                
                if not success and stderr_text:
                    self.logger.warning(f"스크립트 오류 출력: {stderr_text[:200]}...")
                
            except asyncio.TimeoutError:
                self.logger.error(f"스크립트 타임아웃: {tactic} ({timeout}초)")
                process.kill()
                await process.wait()
                
                execution_time = timeout
                exit_code = -1
                stdout_text = ""
                stderr_text = f"Script timeout after {timeout} seconds"
                iocs = []
                success = False
                
        except Exception as e:
            self.logger.error(f"스크립트 실행 실패: {tactic} - {e}")
            execution_time = time.time() - start_time
            exit_code = -2
            stdout_text = ""
            stderr_text = str(e)
            iocs = []
            success = False
            pid = -1
        
        # 결과 객체 생성
        result = AttackScriptResult(
            tactic=tactic,
            script_path=str(script_path),
            success=success,
            exit_code=exit_code,
            execution_time=execution_time,
            stdout=stdout_text,
            stderr=stderr_text,
            iocs=iocs,
            timestamp=timestamp,
            pid=pid
        )
        
        self.results.append(result)
        return result
    
    def _extract_iocs_from_output(self, stdout: str, stderr: str) -> List[str]:
        """출력에서 IOCs 추출"""
        iocs = []
        combined_output = stdout + "\n" + stderr
        
        # IOC 패턴들
        patterns = {
            'IP': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'MAC': r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b',
            'PORT': r'\bport\s*:?\s*(\d+)\b',
            'URL': r'https?://[^\s]+',
            'DOMAIN': r'\b[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}\b',
            'HASH_MD5': r'\b[a-fA-F0-9]{32}\b',
            'HASH_SHA1': r'\b[a-fA-F0-9]{40}\b',
            'HASH_SHA256': r'\b[a-fA-F0-9]{64}\b'
        }
        
        for ioc_type, pattern in patterns.items():
            matches = re.findall(pattern, combined_output, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                ioc = f"{ioc_type}:{match}"
                if ioc not in iocs:
                    iocs.append(ioc)
        
        # 명시적 IOC 태그 찾기 (예: "IOC:TYPE:VALUE")
        explicit_iocs = re.findall(r'IOC:([^:\s]+):([^\s]+)', combined_output)
        for ioc_type, ioc_value in explicit_iocs:
            ioc = f"{ioc_type}:{ioc_value}"
            if ioc not in iocs:
                iocs.append(ioc)
        
        return iocs
    
    async def run_all_attacks(
        self, 
        tactics: Optional[List[str]] = None,
        concurrent_limit: int = 2,
        attack_interval: float = 2.0
    ) -> List[AttackScriptResult]:
        """모든 공격 스크립트 순차 실행"""
        self.logger.info("=== 모든 DVD 공격 스크립트 실행 시작 ===")
        
        # 스크립트 발견
        discovered = self.discover_attack_scripts()
        
        if not discovered:
            self.logger.error("실행할 공격 스크립트를 찾을 수 없습니다")
            return []
        
        # 필터링 (특정 전술만 실행하는 경우)
        if tactics:
            discovered = {k: v for k, v in discovered.items() if k in tactics}
            self.logger.info(f"필터링된 전술: {list(discovered.keys())}")
        
        # 스크립트 분석
        self.logger.info("스크립트 내용 분석 중...")
        script_info = {}
        for tactic, script_path in discovered.items():
            info = self.inspect_script_content(script_path)
            script_info[tactic] = info
            self.logger.info(
                f"{tactic}: {info.get('line_count', 0)}줄, "
                f"예상 소요시간: {info.get('estimated_duration', 0)}초"
            )
        
        total_scripts = len(discovered)
        self.logger.info(f"총 {total_scripts}개 스크립트 실행 예정")
        
        # 순차 실행 (동시 실행하면 리소스 충돌 가능성)
        results = []
        for i, (tactic, script_path) in enumerate(discovered.items(), 1):
            self.logger.info(f"\n[{i}/{total_scripts}] {tactic} 전술 공격 시작")
            
            # 예상 소요시간에 따른 타임아웃 설정
            estimated_time = script_info.get(tactic, {}).get('estimated_duration', 60)
            timeout = max(estimated_time * 2, 120)  # 최소 2분
            
            try:
                result = await self.run_attack_script(tactic, script_path, timeout)
                results.append(result)
                
                # 성공/실패 요약 출력
                status = "✅ 성공" if result.success else "❌ 실패"
                self.logger.info(
                    f"{status} {tactic} - "
                    f"실행시간: {result.execution_time:.2f}초, "
                    f"IOCs: {len(result.iocs)}개"
                )
                
                # 공격 간 간격
                if i < total_scripts:
                    self.logger.info(f"{attack_interval}초 대기 중...")
                    await asyncio.sleep(attack_interval)
                    
            except KeyboardInterrupt:
                self.logger.warning("사용자에 의해 중단됨")
                break
            except Exception as e:
                self.logger.error(f"{tactic} 실행 중 예외 발생: {e}")
                continue
        
        self.logger.info(f"\n=== 모든 공격 스크립트 실행 완료 ===")
        self.logger.info(f"실행된 스크립트: {len(results)}개")
        self.logger.info(f"성공한 공격: {sum(1 for r in results if r.success)}개")
        self.logger.info(f"수집된 IOCs: {sum(len(r.iocs) for r in results)}개")
        
        return results
    
    def save_results(self, results: List[AttackScriptResult]) -> str:
        """결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 상세 결과 JSON
        detailed_results = {
            "execution_info": {
                "timestamp": timestamp,
                "total_scripts": len(results),
                "successful_attacks": sum(1 for r in results if r.success),
                "total_execution_time": sum(r.execution_time for r in results),
                "base_path": str(BASE_PATH),
                "dvd_attacks_path": str(DVD_ATTACKS_PATH)
            },
            "script_results": [asdict(result) for result in results],
            "tactics_summary": self._create_tactics_summary(results),
            "ioc_summary": self._create_ioc_summary(results)
        }
        
        # JSON 파일 저장
        results_file = RESULTS_PATH / f"dvd_attack_results_{timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2, ensure_ascii=False, default=str)
        
        # IOCs CSV 저장
        iocs_file = RESULTS_PATH / f"dvd_iocs_{timestamp}.csv"
        self._save_iocs_csv(results, iocs_file)
        
        # 실행 요약 텍스트 저장
        summary_file = RESULTS_PATH / f"dvd_summary_{timestamp}.txt"
        self._save_summary_text(results, summary_file)
        
        self.logger.info(f"결과 저장 완료:")
        self.logger.info(f"  - 상세 결과: {results_file}")
        self.logger.info(f"  - IOCs: {iocs_file}")
        self.logger.info(f"  - 요약: {summary_file}")
        
        return str(results_file)
    
    def _create_tactics_summary(self, results: List[AttackScriptResult]) -> Dict[str, Any]:
        """전술별 요약 생성"""
        summary = {}
        for result in results:
            tactic = result.tactic
            if tactic not in summary:
                summary[tactic] = {
                    "success": False,
                    "execution_time": 0,
                    "ioc_count": 0,
                    "exit_code": 0,
                    "script_path": ""
                }
            
            summary[tactic].update({
                "success": result.success,
                "execution_time": result.execution_time,
                "ioc_count": len(result.iocs),
                "exit_code": result.exit_code,
                "script_path": result.script_path
            })
        
        return summary
    
    def _create_ioc_summary(self, results: List[AttackScriptResult]) -> Dict[str, Any]:
        """IOC 요약 생성"""
        all_iocs = []
        ioc_types = {}
        
        for result in results:
            all_iocs.extend(result.iocs)
            for ioc in result.iocs:
                ioc_type = ioc.split(':')[0] if ':' in ioc else 'UNKNOWN'
                ioc_types[ioc_type] = ioc_types.get(ioc_type, 0) + 1
        
        return {
            "total_iocs": len(all_iocs),
            "unique_iocs": len(set(all_iocs)),
            "ioc_types": ioc_types,
            "iocs_by_tactic": {
                result.tactic: len(result.iocs) for result in results
            }
        }
    
    def _save_iocs_csv(self, results: List[AttackScriptResult], file_path: Path):
        """IOCs CSV 저장"""
        import csv
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Tactic', 'IOC_Type', 'IOC_Value', 'Timestamp', 'Script_Path'])
            
            for result in results:
                for ioc in result.iocs:
                    if ':' in ioc:
                        ioc_type, ioc_value = ioc.split(':', 1)
                    else:
                        ioc_type, ioc_value = 'UNKNOWN', ioc
                    
                    writer.writerow([
                        result.tactic,
                        ioc_type,
                        ioc_value,
                        result.timestamp,
                        result.script_path
                    ])
    
    def _save_summary_text(self, results: List[AttackScriptResult], file_path: Path):
        """요약 텍스트 저장"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("DVD 공격 스크립트 실행 요약\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"총 스크립트 수: {len(results)}\n")
            f.write(f"성공한 공격: {sum(1 for r in results if r.success)}\n")
            f.write(f"실패한 공격: {sum(1 for r in results if not r.success)}\n")
            f.write(f"총 실행 시간: {sum(r.execution_time for r in results):.2f}초\n")
            f.write(f"수집된 IOCs: {sum(len(r.iocs) for r in results)}개\n\n")
            
            f.write("전술별 상세 결과:\n")
            f.write("-" * 30 + "\n")
            
            for result in results:
                status = "성공" if result.success else "실패"
                f.write(f"\n{result.tactic}: {status}\n")
                f.write(f"  스크립트: {result.script_path}\n")
                f.write(f"  실행시간: {result.execution_time:.2f}초\n")
                f.write(f"  종료코드: {result.exit_code}\n")
                f.write(f"  IOCs: {len(result.iocs)}개\n")
                
                if result.iocs:
                    f.write(f"  수집된 IOCs:\n")
                    for ioc in result.iocs[:5]:  # 최대 5개만 표시
                        f.write(f"    - {ioc}\n")
                    if len(result.iocs) > 5:
                        f.write(f"    ... 외 {len(result.iocs) - 5}개\n")

# =============================================================================
# CLI 인터페이스
# =============================================================================

async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="DVD 공격 스크립트 자동 순회 실행기"
    )
    parser.add_argument(
        "--tactics", 
        nargs='+', 
        help="실행할 특정 전술들 (예: reconnaissance injection)"
    )
    parser.add_argument(
        "--list", 
        action="store_true", 
        help="사용 가능한 공격 스크립트 목록만 출력"
    )
    parser.add_argument(
        "--interval", 
        type=float, 
        default=2.0, 
        help="공격 간 대기 시간(초)"
    )
    parser.add_argument(
        "--timeout", 
        type=int, 
        default=300, 
        help="스크립트 실행 타임아웃(초)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="실제 실행 없이 발견된 스크립트만 출력"
    )
    
    args = parser.parse_args()
    
    # 실행기 생성
    runner = DVDAttackScriptRunner()
    
    try:
        if args.list or args.dry_run:
            # 스크립트 목록만 출력
            discovered = runner.discover_attack_scripts()
            if discovered:
                print("\n발견된 공격 스크립트:")
                print("=" * 50)
                for tactic, script_path in discovered.items():
                    info = runner.inspect_script_content(script_path)
                    print(f"{tactic:20} -> {script_path}")
                    print(f"{'':20}    예상 소요시간: {info.get('estimated_duration', 0)}초")
                print(f"\n총 {len(discovered)}개 스크립트 발견됨")
            else:
                print("발견된 공격 스크립트가 없습니다.")
            return 0
        
        # 실제 공격 실행
        results = await runner.run_all_attacks(
            tactics=args.tactics,
            attack_interval=args.interval
        )
        
        if results:
            # 결과 저장
            results_file = runner.save_results(results)
            
            # 요약 출력
            print("\n" + "="*80)
            print("DVD 공격 스크립트 실행 완료")
            print("="*80)
            print(f"실행된 스크립트: {len(results)}개")
            print(f"성공한 공격: {sum(1 for r in results if r.success)}개")
            print(f"실패한 공격: {sum(1 for r in results if not r.success)}개")
            print(f"총 실행 시간: {sum(r.execution_time for r in results):.2f}초")
            print(f"수집된 IOCs: {sum(len(r.iocs) for r in results)}개")
            print(f"결과 파일: {results_file}")
            print("="*80)
        else:
            print("실행된 공격이 없습니다.")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
        return 1
    except Exception as e:
        print(f"\n실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))