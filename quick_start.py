#!/usr/bin/env python3
"""
DVD 공격 시나리오 빠른 실행 스크립트 (컴포넌트화 버전)
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dvd_lite.main import DVDLite
    from dvd_lite.cti import SimpleCTI
    from dvd_lite.dvd_attacks import (
        register_all_dvd_attacks, 
        get_attacks_by_tactic, 
        get_attacks_by_difficulty,
        get_attacks_by_flight_state,
        get_attack_info,
        DVDAttackTactic,
        DVDFlightState,
        AttackDifficulty,
        AttackStatus
    )
except ImportError as e:
    print(f"❌ Import 오류: {e}")
    print("파일 구조를 확인하고 모든 __init__.py 파일이 있는지 확인하세요.")
    sys.exit(1)

def print_banner():
    """배너 출력"""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                    DVD Attack Scenarios                          ║
║              Damn Vulnerable Drone 공격 시나리오                  ║
║                                                                  ║
║  🎯 19개 완전 구현된 공격 시나리오                                  ║
║  🔥 6개 주요 공격 전술 카테고리                                     ║
║  📊 실시간 CTI 수집 및 분석                                        ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def print_attack_detail(result) -> None:
    """공격 실행 결과 상세 출력"""
    status_icon = "✅" if result.status == AttackStatus.SUCCESS else "❌"
    
    print(f"\n{status_icon} 공격 완료: {result.attack_name}")
    print(f"   📊 상태: {result.status.value}")
    print(f"   ⏱️  실행시간: {result.response_time:.2f}초")
    print(f"   🎯 성공률: {result.success_rate:.1%}")
    print(f"   🔍 IOCs: {len(result.iocs)}개")
    print(f"   🎪 타겟: {result.target}")
    
    # IOC 상세 표시
    if result.iocs:
        print("   📋 주요 IOCs:")
        for ioc in result.iocs[:5]:  # 최대 5개만 표시
            print(f"      • {ioc}")
        if len(result.iocs) > 5:
            print(f"      ... 및 {len(result.iocs) - 5}개 더")
    
    # 공격 세부사항 표시
    if result.details:
        print("   📝 세부사항:")
        interesting_keys = ['success_rate', 'attack_vector', 'vulnerabilities_found', 
                          'discovered_networks', 'system_impact', 'injection_attempts']
        
        shown_count = 0
        for key, value in result.details.items():
            if shown_count >= 3:  # 최대 3개까지만 표시
                break
                
            if key in interesting_keys or isinstance(value, (int, float, str)):
                if isinstance(value, float):
                    print(f"      • {key}: {value:.2f}")
                elif isinstance(value, list) and len(value) <= 3:
                    print(f"      • {key}: {value}")
                elif isinstance(value, dict) and len(value) <= 2:
                    print(f"      • {key}: {value}")
                else:
                    print(f"      • {key}: {str(value)[:50]}...")
                shown_count += 1

async def run_single_attack_demo():
    """단일 공격 실행 데모"""
    print("\n" + "="*60)
    print("🎯 단일 공격 실행 데모")
    print("="*60)
    
    # DVD-Lite 인스턴스 생성
    dvd = DVDLite()
    cti = SimpleCTI()
    try:
        dvd.register_cti_collector(cti)
    except AttributeError:
        # CTI 수집기가 없는 경우 무시
        logger.warning("CTI 수집기 등록을 건너뜁니다 (메서드 없음)")
        pass
    
    # 공격 등록
    registered_attacks = register_all_dvd_attacks()
    print(f"📋 등록된 공격: {len(registered_attacks)}개")
    
    # 네트워크 발견 공격 실행
    attack_name = "wifi_network_discovery"
    print(f"\n🚀 {attack_name} 공격 실행 중...")
    
    try:
        # 공격 정보 표시
        attack_info = get_attack_info(attack_name)
        if attack_info:
            print(f"   📖 설명: {attack_info['description']}")
            print(f"   🎚️  난이도: {attack_info['difficulty']}")
            print(f"   🎯 타겟: {', '.join(attack_info['targets'])}")
            print(f"   ⏱️  예상 시간: {attack_info['estimated_duration']:.1f}초")
            print(f"   🥷 은밀성: {attack_info['stealth_level']}")
            print(f"   ⚡ 영향도: {attack_info['impact_level']}")
        
        # 공격 실행
        result = await dvd.run_attack(attack_name)
        
        # 결과 상세 출력
        print_attack_detail(result)
        
        # CTI 정보 표시
        cti_summary = cti.get_summary()
        print(f"\n🔍 CTI 수집 결과:")
        print(f"   📊 수집된 지표: {cti_summary['total_indicators']}개")
        print(f"   📈 공격 패턴: {cti_summary['total_patterns']}개")
        
    except Exception as e:
        print(f"❌ 실행 실패: {e}")
        import traceback
        traceback.print_exc()

async def run_multiple_attacks_demo():
    """여러 공격 실행 데모"""
    print("\n" + "="*60)
    print("🚀 여러 공격 실행 데모")
    print("="*60)
    
    dvd = DVDLite()
    cti = SimpleCTI()
    try:
        dvd.register_cti_collector(cti)
    except AttributeError:
        # CTI 수집기가 없는 경우 무시
        logger.warning("CTI 수집기 등록을 건너뜁니다 (메서드 없음)")
        pass
    
    register_all_dvd_attacks()
    
    # 각 전술별로 하나씩 선택
    attacks_to_run = [
        "wifi_network_discovery",      # 정찰
        "gps_spoofing",               # 프로토콜 변조
        "mavlink_flood",              # 서비스 거부
        "flight_plan_injection",      # 주입
        "telemetry_exfiltration",     # 데이터 탈취
        "bootloader_exploit"          # 펌웨어 공격
    ]
    
    print(f"📋 실행할 공격 시나리오: {len(attacks_to_run)}개")
    
    # 각 공격 정보 표시
    for attack_name in attacks_to_run:
        info = get_attack_info(attack_name)
        if info:
            print(f"   • {attack_name} ({info['tactic']}) - {info['difficulty']}")
    
    print("\n🔥 공격 실행 시작...")
    
    results = []
    for i, attack_name in enumerate(attacks_to_run, 1):
        print(f"\n[{i}/{len(attacks_to_run)}] 🎯 {attack_name} 실행 중...")
        
        try:
            result = await dvd.run_attack(attack_name)
            results.append(result)
            
            # 간단한 결과 출력
            status = "✅" if result.status == AttackStatus.SUCCESS else "❌"
            print(f"   {status} 완료: {result.response_time:.2f}초, IOCs: {len(result.iocs)}개")
            
        except Exception as e:
            print(f"   ❌ 실패: {str(e)}")
            
        # 공격 간 간격
        if i < len(attacks_to_run):
            await asyncio.sleep(0.5)
    
    # 전체 결과 요약
    print("\n" + "="*60)
    print("📊 전체 실행 결과 요약")
    print("="*60)
    
    success_count = sum(1 for r in results if r.status == AttackStatus.SUCCESS)
    total_time = sum(r.response_time for r in results)
    total_iocs = sum(len(r.iocs) for r in results)
    
    print(f"📈 성공률: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    print(f"⏱️  총 실행시간: {total_time:.2f}초")
    print(f"📊 평균 실행시간: {total_time/len(results):.2f}초")
    print(f"🔍 총 IOCs: {total_iocs}개")
    
    # 전술별 성공률
    tactic_results = {}
    for result in results:
        attack_info = get_attack_info(result.attack_name)
        if attack_info:
            tactic = attack_info['tactic']
            if tactic not in tactic_results:
                tactic_results[tactic] = {'success': 0, 'total': 0}
            tactic_results[tactic]['total'] += 1
            if result.status == AttackStatus.SUCCESS:
                tactic_results[tactic]['success'] += 1
    
    print("\n📋 전술별 성공률:")
    for tactic, stats in tactic_results.items():
        rate = stats['success'] / stats['total'] * 100
        print(f"   • {tactic}: {stats['success']}/{stats['total']} ({rate:.1f}%)")
    
    # CTI 종합 분석
    cti_summary = cti.get_summary()
    print(f"\n🔍 CTI 종합 분석:")
    print(f"   📊 총 수집 지표: {cti_summary['total_indicators']}개")
    print(f"   📈 공격 패턴: {cti_summary['total_patterns']}개")
    
    if cti_summary.get('statistics', {}).get('by_attack_type'):
        print("   📋 공격 유형별 분포:")
        for attack_type, count in cti_summary['statistics']['by_attack_type'].items():
            print(f"      • {attack_type}: {count}개")

async def run_tactic_based_demo():
    """전술별 공격 실행 데모"""
    print("\n" + "="*60)
    print("🎖️  전술별 공격 실행 데모")
    print("="*60)
    
    dvd = DVDLite()
    cti = SimpleCTI()
    try:
        dvd.register_cti_collector(cti)
    except AttributeError:
        # CTI 수집기가 없는 경우 무시
        logger.warning("CTI 수집기 등록을 건너뜁니다 (메서드 없음)")
        pass
    
    register_all_dvd_attacks()
    
    # 정찰 공격 실행
    print("🔍 정찰 (RECONNAISSANCE) 공격 실행")
    print("-" * 40)
    
    recon_attacks = get_attacks_by_tactic(DVDAttackTactic.RECONNAISSANCE)
    print(f"📋 정찰 공격 목록: {len(recon_attacks)}개")
    
    for attack in recon_attacks:
        info = get_attack_info(attack)
        if info:
            print(f"   • {attack}: {info['description']}")
    
    print("\n🚀 정찰 공격 실행 중...")
    
    recon_results = []
    for attack in recon_attacks:
        try:
            result = await dvd.run_attack(attack)
            recon_results.append(result)
            
            status = "✅" if result.status == AttackStatus.SUCCESS else "❌"
            print(f"   {status} {attack}: {result.response_time:.2f}초")
            
        except Exception as e:
            print(f"   ❌ {attack}: 실행 실패 ({str(e)})")
        
        await asyncio.sleep(0.3)
    
    # 정찰 결과 분석
    print("\n📊 정찰 결과 분석:")
    successful_recon = [r for r in recon_results if r.status == AttackStatus.SUCCESS]
    
    if successful_recon:
        total_discovered = sum(len(r.iocs) for r in successful_recon)
        print(f"   🎯 발견된 항목: {total_discovered}개")
        
        # 발견된 네트워크 요소들
        network_elements = []
        for result in successful_recon:
            for ioc in result.iocs:
                if any(keyword in ioc for keyword in ['WIFI_', 'MAVLINK_', 'SERVICE_', 'COMPONENT_']):
                    network_elements.append(ioc)
        
        if network_elements:
            print(f"   🌐 네트워크 요소: {len(network_elements)}개")
            print("   📋 주요 발견사항:")
            for element in network_elements[:5]:
                print(f"      • {element}")
    
    # CTI 정찰 분석
    cti_summary = cti.get_summary()
    print(f"\n🔍 CTI 정찰 분석:")
    print(f"   📊 수집된 지표: {cti_summary['total_indicators']}개")

async def run_difficulty_based_demo():
    """난이도별 공격 실행 데모"""
    print("\n" + "="*60)
    print("🎚️  난이도별 공격 실행 데모")
    print("="*60)
    
    dvd = DVDLite()
    cti = SimpleCTI()
    try:
        dvd.register_cti_collector(cti)
    except AttributeError:
        # CTI 수집기가 없는 경우 무시
        logger.warning("CTI 수집기 등록을 건너뜁니다 (메서드 없음)")
        pass
    
    register_all_dvd_attacks()
    
    # 초급 공격 실행
    print("🟢 초급 (BEGINNER) 공격")
    print("-" * 30)
    
    beginner_attacks = get_attacks_by_difficulty(AttackDifficulty.BEGINNER)
    print(f"📋 초급 공격: {len(beginner_attacks)}개")
    
    for attack in beginner_attacks:
        info = get_attack_info(attack)
        if info:
            print(f"   • {attack} ({info['tactic']})")
    
    # 초급 공격 실행
    print("\n🚀 초급 공격 실행 중...")
    beginner_results = []
    
    for attack in beginner_attacks[:3]:  # 처음 3개만 실행
        try:
            result = await dvd.run_attack(attack)
            beginner_results.append(result)
            print_attack_detail(result)
            
        except Exception as e:
            print(f"   ❌ {attack}: 실행 실패 ({str(e)})")
        
        await asyncio.sleep(0.5)
    
    # 성과 분석
    if beginner_results:
        success_rate = sum(1 for r in beginner_results if r.status == AttackStatus.SUCCESS) / len(beginner_results)
        avg_time = sum(r.response_time for r in beginner_results) / len(beginner_results)
        
        print(f"\n📊 초급 공격 성과:")
        print(f"   🎯 성공률: {success_rate:.1%}")
        print(f"   ⏱️  평균 시간: {avg_time:.2f}초")

def show_comprehensive_attack_catalog():
    """종합적인 공격 카탈로그 표시"""
    print("\n" + "="*60)
    print("📚 DVD 공격 시나리오 종합 카탈로그")
    print("="*60)
    
    dvd = DVDLite()
    register_all_dvd_attacks()
    
    # 전술별 공격 분류
    print("\n📋 전술별 공격 분류:")
    
    for tactic in DVDAttackTactic:
        attacks = get_attacks_by_tactic(tactic)
        if attacks:
            print(f"\n🎯 {tactic.value.upper()} ({len(attacks)}개)")
            print("-" * 50)
            
            for attack in attacks:
                info = get_attack_info(attack)
                if info:
                    difficulty_icon = {
                        'beginner': '🟢',
                        'intermediate': '🟡', 
                        'advanced': '🔴'
                    }.get(info['difficulty'], '⚪')
                    
                    impact_icon = {
                        'low': '🔹',
                        'medium': '🔸',
                        'high': '🔶',
                        'critical': '🔴'
                    }.get(info['impact_level'], '⚪')
                    
                    print(f"   {difficulty_icon} {attack}")
                    print(f"      📝 {info['description']}")
                    print(f"      🎯 타겟: {', '.join(info['targets'])}")
                    print(f"      ⏱️  예상 시간: {info['estimated_duration']:.1f}초")
                    print(f"      {impact_icon} 영향도: {info['impact_level']}")
                    print()
    
    # 난이도별 통계
    print("\n📊 난이도별 통계:")
    for difficulty in AttackDifficulty:
        attacks = get_attacks_by_difficulty(difficulty)
        icon = {'beginner': '🟢', 'intermediate': '🟡', 'advanced': '🔴'}[difficulty.value]
        print(f"   {icon} {difficulty.value}: {len(attacks)}개")
    
    # 타겟별 통계
    print("\n🎯 타겟별 통계:")
    target_stats = {}
    all_attacks = [attack for tactic in DVDAttackTactic for attack in get_attacks_by_tactic(tactic)]
    
    for attack in all_attacks:
        info = get_attack_info(attack)
        if info:
            for target in info['targets']:
                target_stats[target] = target_stats.get(target, 0) + 1
    
    for target, count in sorted(target_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   🎪 {target}: {count}개 공격")

async def interactive_mode():
    """대화형 모드"""
    print("\n" + "="*60)
    print("🎮 대화형 모드")
    print("="*60)
    
    dvd = DVDLite()
    cti = SimpleCTI()
    try:
        dvd.register_cti_collector(cti)
    except AttributeError:
        # CTI 수집기가 없는 경우 무시
        logger.warning("CTI 수집기 등록을 건너뜁니다 (메서드 없음)")
        pass
    
    register_all_dvd_attacks()
    
    while True:
        print("\n🎯 선택 옵션:")
        print("   1. 전술별 공격 보기")
        print("   2. 난이도별 공격 보기")
        print("   3. 특정 공격 실행")
        print("   4. 추천 공격 실행")
        print("   5. 종료")
        
        try:
            choice = input("\n선택하세요 (1-5): ").strip()
            
            if choice == "1":
                await tactic_selection_menu(dvd, cti)
            elif choice == "2":
                await difficulty_selection_menu(dvd, cti)
            elif choice == "3":
                await specific_attack_menu(dvd, cti)
            elif choice == "4":
                await recommended_attack_menu(dvd, cti)
            elif choice == "5":
                print("👋 종료합니다.")
                break
            else:
                print("❌ 잘못된 선택입니다. 1-5 중에서 선택하세요.")
                
        except KeyboardInterrupt:
            print("\n👋 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

async def tactic_selection_menu(dvd, cti):
    """전술 선택 메뉴"""
    print("\n🎖️  전술 선택:")
    tactics = list(DVDAttackTactic)
    
    for i, tactic in enumerate(tactics, 1):
        attacks = get_attacks_by_tactic(tactic)
        print(f"   {i}. {tactic.value} ({len(attacks)}개)")
    
    try:
        choice = int(input(f"\n전술을 선택하세요 (1-{len(tactics)}): ")) - 1
        
        if 0 <= choice < len(tactics):
            selected_tactic = tactics[choice]
            attacks = get_attacks_by_tactic(selected_tactic)
            
            print(f"\n🎯 {selected_tactic.value} 공격 목록:")
            for i, attack in enumerate(attacks, 1):
                info = get_attack_info(attack)
                if info:
                    print(f"   {i}. {attack} ({info['difficulty']})")
            
            attack_choice = int(input(f"\n실행할 공격을 선택하세요 (1-{len(attacks)}): ")) - 1
            
            if 0 <= attack_choice < len(attacks):
                selected_attack = attacks[attack_choice]
                await execute_single_attack(dvd, cti, selected_attack)
            
    except (ValueError, IndexError):
        print("❌ 잘못된 입력입니다.")

async def execute_single_attack(dvd, cti, attack_name):
    """단일 공격 실행"""
    print(f"\n🚀 {attack_name} 실행 중...")
    
    # 공격 정보 표시
    info = get_attack_info(attack_name)
    if info:
        print(f"📝 설명: {info['description']}")
        print(f"🎚️  난이도: {info['difficulty']}")
        print(f"⏱️  예상 시간: {info['estimated_duration']:.1f}초")
    
    try:
        result = await dvd.run_attack(attack_name)
        print_attack_detail(result)
        
        # CTI 분석
        cti_summary = cti.get_summary()
        if cti_summary['total_indicators'] > 0:
            print(f"\n🔍 CTI 수집:")
            print(f"   📊 새로운 지표: {cti_summary['total_indicators']}개")
            
            # 최근 지표 표시
            recent_indicators = cti_summary.get('recent_indicators', [])
            if recent_indicators:
                print("   📋 최근 지표:")
                for indicator in recent_indicators[:3]:
                    print(f"      • {indicator['type']}: {indicator['value']}")
        
    except Exception as e:
        print(f"❌ 실행 실패: {e}")

async def recommended_attack_menu(dvd, cti):
    """추천 공격 메뉴"""
    print("\n🎯 추천 공격 시나리오:")
    print("   1. 보안 평가 입문자용 (초급 공격)")
    print("   2. 정찰 및 정보 수집 (정찰 공격)")
    print("   3. 실전 침투 시나리오 (중급 공격)")
    print("   4. 고급 공격자 시나리오 (고급 공격)")
    
    try:
        choice = input("\n추천 시나리오를 선택하세요 (1-4): ").strip()
        
        if choice == "1":
            # 초급 공격 실행
            attacks = get_attacks_by_difficulty(AttackDifficulty.BEGINNER)[:2]
            await execute_attack_sequence(dvd, cti, attacks, "초급 보안 평가")
            
        elif choice == "2":
            # 정찰 공격 실행
            attacks = get_attacks_by_tactic(DVDAttackTactic.RECONNAISSANCE)[:3]
            await execute_attack_sequence(dvd, cti, attacks, "정찰 및 정보 수집")
            
        elif choice == "3":
            # 중급 공격 실행
            attacks = get_attacks_by_difficulty(AttackDifficulty.INTERMEDIATE)[:2]
            await execute_attack_sequence(dvd, cti, attacks, "실전 침투 시나리오")
            
        elif choice == "4":
            # 고급 공격 실행
            attacks = get_attacks_by_difficulty(AttackDifficulty.ADVANCED)[:2]
            await execute_attack_sequence(dvd, cti, attacks, "고급 공격자 시나리오")
            
    except (ValueError, KeyboardInterrupt):
        print("❌ 잘못된 입력입니다.")

async def execute_attack_sequence(dvd, cti, attacks, scenario_name):
    """공격 시퀀스 실행"""
    print(f"\n🎬 {scenario_name} 실행")
    print("=" * 50)
    
    results = []
    for i, attack in enumerate(attacks, 1):
        print(f"\n[{i}/{len(attacks)}] 🎯 {attack}")
        
        try:
            result = await dvd.run_attack(attack)
            results.append(result)
            
            # 간단한 결과 표시
            status = "✅" if result.status == AttackStatus.SUCCESS else "❌"
            print(f"   {status} 완료: {result.response_time:.2f}초, IOCs: {len(result.iocs)}개")
            
        except Exception as e:
            print(f"   ❌ 실행 실패: {e}")
        
        if i < len(attacks):
            await asyncio.sleep(1)
    
    # 시나리오 결과 요약
    print(f"\n📊 {scenario_name} 결과:")
    success_count = sum(1 for r in results if r.status == AttackStatus.SUCCESS)
    total_iocs = sum(len(r.iocs) for r in results)
    
    print(f"   🎯 성공률: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    print(f"   🔍 총 IOCs: {total_iocs}개")
    
    # CTI 분석
    cti_summary = cti.get_summary()
    print(f"   📊 CTI 지표: {cti_summary['total_indicators']}개")

async def specific_attack_menu(dvd, cti):
    """특정 공격 메뉴"""
    all_attacks = []
    for tactic in DVDAttackTactic:
        all_attacks.extend(get_attacks_by_tactic(tactic))
    
    print(f"\n📋 전체 공격 목록 ({len(all_attacks)}개):")
    for i, attack in enumerate(all_attacks, 1):
        info = get_attack_info(attack)
        if info:
            difficulty_icon = {'beginner': '🟢', 'intermediate': '🟡', 'advanced': '🔴'}[info['difficulty']]
            print(f"   {i:2d}. {difficulty_icon} {attack} ({info['tactic']})")
    
    try:
        choice = int(input(f"\n실행할 공격을 선택하세요 (1-{len(all_attacks)}): ")) - 1
        
        if 0 <= choice < len(all_attacks):
            selected_attack = all_attacks[choice]
            await execute_single_attack(dvd, cti, selected_attack)
            
    except (ValueError, IndexError):
        print("❌ 잘못된 입력입니다.")

async def difficulty_selection_menu(dvd, cti):
    """난이도 선택 메뉴"""
    print("\n🎚️  난이도 선택:")
    difficulties = list(AttackDifficulty)
    
    for i, difficulty in enumerate(difficulties, 1):
        attacks = get_attacks_by_difficulty(difficulty)
        icon = {'beginner': '🟢', 'intermediate': '🟡', 'advanced': '🔴'}[difficulty.value]
        print(f"   {i}. {icon} {difficulty.value} ({len(attacks)}개)")
    
    try:
        choice = int(input(f"\n난이도를 선택하세요 (1-{len(difficulties)}): ")) - 1
        
        if 0 <= choice < len(difficulties):
            selected_difficulty = difficulties[choice]
            attacks = get_attacks_by_difficulty(selected_difficulty)
            
            print(f"\n🎯 {selected_difficulty.value} 공격 목록:")
            for i, attack in enumerate(attacks, 1):
                info = get_attack_info(attack)
                if info:
                    print(f"   {i}. {attack} ({info['tactic']})")
            
            attack_choice = int(input(f"\n실행할 공격을 선택하세요 (1-{len(attacks)}): ")) - 1
            
            if 0 <= attack_choice < len(attacks):
                selected_attack = attacks[attack_choice]
                await execute_single_attack(dvd, cti, selected_attack)
            
    except (ValueError, IndexError):
        print("❌ 잘못된 입력입니다.")

async def main():
    """메인 함수"""
    print_banner()
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "single":
            await run_single_attack_demo()
        elif mode == "multiple":
            await run_multiple_attacks_demo()
        elif mode == "tactic":
            await run_tactic_based_demo()
        elif mode == "difficulty":
            await run_difficulty_based_demo()
        elif mode == "catalog":
            show_comprehensive_attack_catalog()
        elif mode == "interactive":
            await interactive_mode()
        else:
            print(f"❌ 알 수 없는 모드: {mode}")
            print_usage()
    else:
        # 기본: 핵심 데모들 실행
        await run_single_attack_demo()
        await run_multiple_attacks_demo()
        await run_tactic_based_demo()
        show_comprehensive_attack_catalog()

def print_usage():
    """사용법 출력"""
    print("\n📖 사용법:")
    print("   python quick_start.py [mode]")
    print("\n🎯 모드:")
    print("   single      - 단일 공격 데모")
    print("   multiple    - 여러 공격 데모")
    print("   tactic      - 전술별 공격 데모")
    print("   difficulty  - 난이도별 공격 데모")
    print("   catalog     - 전체 공격 카탈로그")
    print("   interactive - 대화형 모드")
    print("   (없음)      - 핵심 데모 실행")
    print("\n🚀 예시:")
    print("   python quick_start.py single")
    print("   python quick_start.py interactive")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 실행 오류: {e}")
        import traceback
        traceback.print_exc()