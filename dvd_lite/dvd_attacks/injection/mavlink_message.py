# dvd_lite/dvd_attacks/injection/mavlink_message.py
"""
MAVLink 메시지 주입 공격
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from ..core.attack_base import BaseAttack
from ..core.enums import AttackType

class MAVLinkMessageInjection(BaseAttack):
    """MAVLink 메시지 주입 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """악성 MAVLink 메시지 주입"""
        await asyncio.sleep(2.8)
        
        # 주입할 메시지 타입들
        message_types = [
            {
                "msg_id": 76,  # COMMAND_LONG
                "name": "COMMAND_LONG",
                "payload": {"command": "MAV_CMD_COMPONENT_ARM_DISARM", "param1": 0},
                "severity": "critical"
            },
            {
                "msg_id": 11,  # SET_POSITION_TARGET_LOCAL_NED
                "name": "SET_POSITION_TARGET_LOCAL_NED",
                "payload": {"x": 1000, "y": 1000, "z": -100},
                "severity": "high"
            },
            {
                "msg_id": 20,  # PARAM_SET
                "name": "PARAM_SET",
                "payload": {"param_id": "FENCE_ENABLE", "param_value": 0},
                "severity": "high"
            }
        ]
        
        injected_messages = []
        
        for msg_type in message_types:
            if random.random() > 0.3:  # 70% 성공률
                injection_result = {
                    **msg_type,
                    "injection_time": random.uniform(0.1, 2.0),
                    "response_received": random.choice([True, False])
                }
                injected_messages.append(injection_result)
        
        iocs = []
        for msg in injected_messages:
            iocs.append(f"MAVLINK_MSG_INJECT:{msg['name']}")
            iocs.append(f"MSG_ID:{msg['msg_id']}")
            if msg['severity'] == 'critical':
                iocs.append(f"CRITICAL_MSG_INJECT:{msg['name']}")
        
        success = len(injected_messages) > 0
        
        details = {
            "available_messages": message_types,
            "injected_messages": injected_messages,
            "injection_method": "raw_mavlink_socket",
            "success_rate": 0.7 if success else 0.1
        }
        
        return success, iocs, details
