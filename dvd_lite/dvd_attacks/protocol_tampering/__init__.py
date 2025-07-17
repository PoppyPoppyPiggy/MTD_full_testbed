# dvd_lite/dvd_attacks/protocol_tampering/__init__.py
"""
protocol_tampering 공격 모듈
"""
# 모든 공격 클래스들을 import하고 __all__에 추가
__all__ = []

# 에러 방지를 위한 try-except 처리
try:
    import os
    import importlib
    
    # 현재 디렉토리의 모든 .py 파일 스캔
    current_dir = os.path.dirname(__file__)
    for file in os.listdir(current_dir):
        if file.endswith('.py') and file != '__init__.py':
            module_name = file[:-3]
            try:
                module = importlib.import_module(f'.{module_name}', package=__name__)
                # 모듈에서 클래스들 찾기
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, '_get_attack_type') and 
                        attr.__name__ != 'BaseAttack'):
                        globals()[attr_name] = attr
                        __all__.append(attr_name)
            except ImportError:
                pass
except Exception:
    pass
