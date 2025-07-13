#!/usr/bin/env python3
# scripts/dvd_attack.py
"""
DVD 공격 실행 스크립트
명령행에서 Damn Vulnerable Drone 환경에 대한 보안 테스트 실행
"""

import sys
import os
import asyncio
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dvd_connector import DVDConnector, DVDConnectionMode
from dvd_lite import DVDLite

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_argument_parser():
    """명령행 인자 파서 생성"""
    parser = argparse.ArgumentParser(
        description="DVD-Lite와 Damn Vulnerable Drone 연동 공격 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 로컬 Docker DVD 환경에 대한 기본 공격
  python3 dvd_attack.py --dvd-host docker --mode local_docker

  # 특정 IP의 DVD 환경에 대한 종합 평가
  python3 dvd_attack.py --dvd-host 10.13.0.2 --assessment comprehensive

  # 시뮬레이션 모드로 안전한 테스트
  python3 dvd_attack.py --dvd-host simulation --attacks wifi_scan drone_discovery

  # 설정 파일 사용
  python3 dvd_attack.py --config configs/dvd_local.json

  # 특정 공격만 실행
  python3 dvd_attack.py --dvd-host 10.13.0.2 --attacks wifi_scan packet_sniff --output results/
        """
    )
    
    # 필수 인자: DVD 타겟
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--dvd-host", 
        help="DVD 타겟 (IP주소, 'docker', 'simulation', 'localhost')"
    )
    target_group.add_argument(
        "--config", 
        help="설정 파일 경로"
    )
    
    # 연결 모드
    parser.add_argument(
        "--mode",
        choices=["auto", "simulation", "local_docker", "local_vm", "remote"],
        default="auto",
        help="연결 모드 (기본값: auto)"
    )
    
    # 평가 타입
    parser.add_argument(
        "--assessment",
        choices=["quick", "standard", "comprehensive"],
        default="standard",
        help="평가 타입 (기본값: standard)"
    )
    
    # 특정 공격 선택
    parser.add_argument(
        "--attacks",
        nargs="+",
        help="실행할 특정 공격들 (예: wifi_scan drone_discovery)"
    )
    
    # 출력 옵션
    parser.add_argument(
        "--output", "-o",
        default="results/",
        help="결과 출력 디렉토리 (기본값: results/)"
    )
    
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="출력 형식 (기본값: both)"
    )
    
    # 실행 옵션
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="반복 실행 횟수 (기본값: 1)"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="공격 간 지연 시간 (초, 기본값: 2.0)"
    )
    
    # 안전성 옵션
    parser.add_argument(
        "--force",
        action="store_true",
        help="안전성 검사 무시 (위험!)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 실행하지 않고 계획만 확인"
    )
    
    # 로깅 옵션
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="최소 로그 출력"
    )
    
    return parser

def setup_logging(verbose=False, quiet=False):
    """로깅 설정"""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logging.getLogger().setLevel(level)

async def load_config_file(config_path: str) -> dict:
    """설정 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"✅ 설정 파일 로드: {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"❌ 설정 파일 JSON 오류: {e}")
        sys.exit(1)

async def validate_arguments(args):
    """인자 유효성 검사"""
    errors = []
    
    # 출력 디렉토리 확인
    output_path = Path(args.output)
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 출력 디렉토리 생성: {output_path}")
        except Exception as e:
            errors.append(f"출력 디렉토리 생성 실패: {e}")
    
    # 반복 횟수 확인
    if args.iterations < 1:
        errors.append("반복 횟수는 1 이상이어야 합니다")
    
    # 지연 시간 확인
    if args.delay < 0:
        errors.append("지연 시간은 0 이상이어야 합니다")
    
    if errors:
        for error in errors:
            logger.error(f"❌ {error}")
        sys.exit(1)

async def print_banner():
    """배너 출력"""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                          DVD-Lite                                ║
║           Damn Vulnerable Drone Security Testing Tool            ║
║                                                                  ║
║  ⚠️  경고: 승인된 환경에서만 사용하세요                              ║
║  🛡️  안전성 검사가 자동으로 수행됩니다                               ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)

async def show_target_info(connector: DVDConnector):
    """타겟 정보 출력"""
    info = connector.get_connection_info()
    
    print("\n📋 타겟 정보:")
    print(f"   호스트: {info['target']['host']}")
    print(f"   모드: {info['target']['mode']}")
    print(f"   네트워크: {info['target']['network_range']}")
    print(f"   연결 상태: {'✅ 연결됨' if info['connected'] else '❌ 연결 안됨'}")
    
    if info['environment']['accessible']:
        print(f"   발견된 서비스: {len(info['environment']['services'])}개")
        if info['environment']['services']:
            print(f"   서비스 목록: {', '.join(info['environment']['services'])}")

async def run_security_assessment(connector: DVDConnector, args) -> dict:
    """보안 평가 실행"""
    logger.info(f"🛡️  보안 평가 시작: {args.assessment}")
    
    results = []
    
    if args.attacks:
        # 특정 공격들 실행
        logger.info(f"⚔️  지정된 공격 실행: {', '.join(args.attacks)}")
        
        for iteration in range(args.iterations):
            if args.iterations > 1:
                logger.info(f"반복 {iteration + 1}/{args.iterations}")
            
            for attack_name in args.attacks:
                try:
                    result = await connector.dvd_lite.run_attack(attack_name)
                    results.append(result)
                    
                    status_icon = "✅" if result.status.value == "success" else "❌"
                    logger.info(f"   {status_icon} {attack_name}: {result.status.value}")
                    
                    if attack_name != args.attacks[-1] or iteration < args.iterations - 1:
                        await asyncio.sleep(args.delay)
                        
                except Exception as e:
                    logger.error(f"   ❌ {attack_name}: {str(e)}")
            
            if iteration < args.iterations - 1:
                await asyncio.sleep(5)  # 반복 간 대기
    
    else:
        # 평가 타입에 따른 공격 실행
        assessment_results = await connector.run_security_assessment(args.assessment)
        return assessment_results
    
    # 사용자 정의 공격 결과 분석
    if results:
        summary = connector.dvd_lite.get_summary()
        return {
            "status": "completed",
            "summary": summary,
            "results": results,
            "target_info": connector.get_connection_info()
        }
    else:
        return {"status": "no_results", "message": "실행된 공격이 없습니다"}

async def save_results(results: dict, args):
    """결과 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output)
    
    saved_files = []
    
    # JSON 형식 저장
    if args.format in ["json", "both"]:
        json_file = output_dir / f"dvd_attack_results_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        saved_files.append(str(json_file))
        logger.info(f"💾 JSON 결과 저장: {json_file}")
    
    # CSV 형식 저장 (CTI 데이터가 있는 경우)
    if args.format in ["csv", "both"] and "results" in results:
        csv_file = output_dir / f"dvd_attack_indicators_{timestamp}.csv"
        
        # CSV 헤더
        csv_lines = ["Attack_Name,Attack_Type,Status,Success_Rate,Response_Time,IOC_Count,Target"]
        
        # 결과 데이터
        for result in results["results"]:
            line = f"{result.attack_name},{result.attack_type.value},{result.status.value},{result.success_rate},{result.response_time:.2f},{len(result.iocs)},{result.target}"
            csv_lines.append(line)
        
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(csv_lines))
        saved_files.append(str(csv_file))
        logger.info(f"💾 CSV 결과 저장: {csv_file}")
    
    return saved_files

async def print_results_summary(results: dict):
    """결과 요약 출력"""
    print("\n" + "="*60)
    print("📊 보안 평가 결과 요약")
    print("="*60)
    
    if results.get("status") == "completed":
        summary = results.get("summary", {})
        
        if isinstance(summary, dict) and "total_attacks" in summary:
            print(f"총 공격 수: {summary['total_attacks']}")
            print(f"성공한 공격: {summary['successful_attacks']}")
            print(f"성공률: {summary['success_rate']}")
            print(f"탐지율: {summary['detection_rate']}")
            print(f"평균 응답 시간: {summary['avg_response_time']}")
        else:
            # 종합 평가 결과인 경우
            if "summary" in results:
                eval_summary = results["summary"]
                print(f"총 공격 수: {eval_summary['total_attacks']}")
                print(f"성공한 공격: {eval_summary['successful_attacks']}")
                print(f"위험도: {eval_summary['risk_level']}")
                print(f"성공률: {eval_summary['success_rate']:.1f}%")
        
        # 권장사항 출력
        if "recommendations" in results:
            print(f"\n🔧 보안 권장사항:")
            for i, rec in enumerate(results["recommendations"], 1):
                print(f"   {i}. {rec}")
        
        # 타겟 정보 출력
        if "target_info" in results:
            target_info = results["target_info"]
            print(f"\n🎯 타겟 정보:")
            print(f"   호스트: {target_info['target']['host']}")
            print(f"   모드: {target_info['target']['mode']}")
    
    else:
        print(f"상태: {results.get('status', 'unknown')}")
        if "message" in results:
            print(f"메시지: {results['message']}")
    
    print("="*60)

async def main():
    """메인 함수"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # 로깅 설정
    setup_logging(args.verbose, args.quiet)
    
    # 배너 출력
    if not args.quiet:
        await print_banner()
    
    # 인자 유효성 검사
    await validate_arguments(args)
    
    try:
        # 설정 로드
        if args.config:
            config = await load_config_file(args.config)
            dvd_host = config.get("target", {}).get("host", "localhost")
            mode = config.get("connection", {}).get("mode", "auto")
        else:
            dvd_host = args.dvd_host
            mode = args.mode
        
        # Dry run 모드
        if args.dry_run:
            print(f"\n🔍 실행 계획 (Dry Run):")
            print(f"   타겟: {dvd_host}")
            print(f"   모드: {mode}")
            print(f"   평가: {args.assessment}")
            if args.attacks:
                print(f"   공격: {', '.join(args.attacks)}")
            print(f"   반복: {args.iterations}회")
            print(f"   출력: {args.output}")
            print(f"\n실제 실행하려면 --dry-run 옵션을 제거하세요.")
            return
        
        # DVD 연결
        logger.info(f"🔗 DVD 환경 연결 중: {dvd_host}")
        connector = DVDConnector(dvd_host, mode)
        
        # 안전성 검사 (--force 옵션으로 무시 가능)
        if not args.force:
            logger.info("🛡️  안전성 검사 중...")
            # 연결 시도 (내부적으로 안전성 검사 수행)
            
        connected = await connector.connect()
        
        if not connected:
            logger.error("❌ DVD 환경에 연결할 수 없습니다")
            logger.info("💡 해결 방법:")
            logger.info("   1. DVD 환경이 실행 중인지 확인")
            logger.info("   2. 네트워크 연결 확인")
            logger.info("   3. 방화벽 설정 확인")
            logger.info("   4. --force 옵션으로 안전성 검사 무시 (주의!)")
            sys.exit(1)
        
        # 연결 정보 출력
        if not args.quiet:
            await show_target_info(connector)
        
        # 보안 평가 실행
        results = await run_security_assessment(connector, args)
        
        # 결과 저장
        saved_files = await save_results(results, args)
        
        # 결과 요약 출력
        if not args.quiet:
            await print_results_summary(results)
        
        # 저장된 파일 정보 출력
        print(f"\n📁 결과 파일:")
        for file_path in saved_files:
            print(f"   - {file_path}")
        
        # 연결 해제
        await connector.disconnect()
        
        logger.info("✅ 보안 평가 완료")
        
    except KeyboardInterrupt:
        logger.info("\n👋 사용자에 의해 중단됨")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ 실행 실패: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())