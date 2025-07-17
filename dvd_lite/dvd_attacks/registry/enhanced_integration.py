# dvd_lite/dvd_attacks/registry/enhanced_integration.py
"""
DVD 공격 레지스트리 통합 개선
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def ensure_registry_initialization():
    """레지스트리 초기화 보장"""
    try:
        from .attack_registry import DVD_ATTACK_REGISTRY
        from .management import register_all_dvd_attacks
        
        # 아직 등록되지 않았다면 등록
        if not DVD_ATTACK_REGISTRY.list_attacks():
            registered = register_all_dvd_attacks()
            logger.info(f"레지스트리 자동 초기화: {len(registered)}개 공격 등록")
        
        return DVD_ATTACK_REGISTRY
    except Exception as e:
        logger.error(f"레지스트리 초기화 실패: {e}")
        return None

def get_integrated_attack_list() -> List[str]:
    """통합된 공격 목록 반환"""
    registry = ensure_registry_initialization()
    if registry:
        return registry.list_attacks()
    return []

def get_integrated_attack_class(attack_name: str):
    """통합된 공격 클래스 반환"""
    registry = ensure_registry_initialization()
    if registry:
        return registry.get_attack_class(attack_name)
    return None

def test_registry_integration():
    """레지스트리 통합 테스트"""
    print("🧪 레지스트리 통합 테스트...")
    
    try:
        registry = ensure_registry_initialization()
        if registry:
            attacks = registry.list_attacks()
            print(f"✅ 등록된 공격: {len(attacks)}개")
            
            # 몇 개 공격 클래스 테스트
            for attack_name in attacks[:3]:
                attack_class = registry.get_attack_class(attack_name)
                if attack_class:
                    print(f"✅ {attack_name} 클래스 확인됨: {attack_class.__name__}")
                else:
                    print(f"❌ {attack_name} 클래스 없음")
            
            return True
        else:
            print("❌ 레지스트리 초기화 실패")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    test_registry_integration()
