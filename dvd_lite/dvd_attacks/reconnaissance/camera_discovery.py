# dvd_lite/dvd_attacks/reconnaissance/camera_discovery.py
"""
카메라 스트림 발견 및 하이재킹 공격 (Damn Vulnerable Drone 기반)
"""

import asyncio
import random
from typing import Tuple, List, Dict, Any

from ..core.attack_base import BaseAttack, AttackType

class CameraStreamDiscovery(BaseAttack):
    """카메라 스트림 발견 및 접근"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """RTSP 및 HTTP 카메라 스트림 발견 및 하이재킹"""
        await asyncio.sleep(2.8)
        
        # DVD 환경의 실제 카메라 스트림 구성
        dvd_camera_streams = [
            {
                "type": "RTSP",
                "url": "rtsp://192.168.13.2:8554/live/stream1",
                "description": "Primary Camera Stream",
                "resolution": "1920x1080",
                "fps": 30,
                "codec": "H.264",
                "bitrate": "5000 kbps",
                "authenticated": False,
                "gimbal_control": True,
                "tilt_range": [-90, 30],
                "pan_range": [-180, 180],
                "zoom_capability": True,
                "recording": True
            },
            {
                "type": "RTSP", 
                "url": "rtsp://192.168.13.2:8554/live/stream2",
                "description": "Secondary/Thermal Camera",
                "resolution": "640x480",
                "fps": 25,
                "codec": "H.265",
                "bitrate": "1500 kbps",
                "authenticated": False,
                "thermal_imaging": True,
                "temperature_range": [-40, 150],
                "recording": False
            },
            {
                "type": "HTTP",
                "url": "http://192.168.13.2:8080/video_feed",
                "description": "Live MJPEG Feed",
                "format": "MJPEG",
                "resolution": "1280x720",
                "authenticated": False,
                "real_time": True
            }
        ]
        
        # 일반적인 카메라 스트림 경로들
        common_rtsp_paths = [
            "/live/stream1", "/live/stream2", "/live/main", "/live/sub",
            "/axis-media/media.amp", "/mjpeg/1", "/mjpeg/2",
            "/video.mjpg", "/live.sdp", "/cam/realmonitor",
            "/streaming/channels/1", "/streaming/channels/2",
            "/VideoInput/1/h264", "/VideoInput/1/mjpeg"
        ]
        
        common_http_paths = [
            "/video_feed", "/mjpeg", "/stream.mjpg", "/video.cgi",
            "/axis-cgi/mjpg/video.cgi", "/videostream.cgi",
            "/cgi-bin/hi3510/snap.cgi", "/snapshot.cgi",
            "/live/index.m3u8", "/hls/stream.m3u8"
        ]
        
        discovered_streams = []
        hijacking_attempts = []
        
        # DVD 스트림 발견 (높은 성공률)
        for stream in dvd_camera_streams:
            if random.random() > 0.05:  # 95% 발견률
                discovered_streams.append(stream)
        
        # 추가 네트워크 스캔
        scan_ranges = [
            "192.168.13.0/24",  # DVD 네트워크
            "10.0.1.0/24",      # 컴패니언 네트워크
            "172.16.0.0/24"     # 추가 내부 네트워크
        ]
        
        for network in scan_ranges:
            if "192.168.13" not in network:  # DVD 외 네트워크
                num_cameras = random.randint(0, 3)
                for i in range(num_cameras):
                    if random.random() > 0.6:  # 40% 확률
                        host_ip = self._generate_ip_in_network(network)
                        stream_type = random.choice(["RTSP", "HTTP", "WebRTC"])
                        
                        if stream_type == "RTSP":
                            path = random.choice(common_rtsp_paths)
                            port = random.choice([554, 8554, 1935])
                            url = f"rtsp://{host_ip}:{port}{path}"
                        else:
                            path = random.choice(common_http_paths)
                            port = random.choice([80, 8080, 8081])
                            url = f"http://{host_ip}:{port}{path}"
                        
                        stream_info = {
                            "type": stream_type,
                            "url": url,
                            "description": f"Generic {stream_type} Stream",
                            "resolution": random.choice(["1920x1080", "1280x720", "640x480"]),
                            "authenticated": random.choice([True, False]),
                            "vendor": random.choice(["Hikvision", "Dahua", "Axis", "Generic"])
                        }
                        discovered_streams.append(stream_info)
        
        # 스트림 하이재킹 시뮬레이션
        for stream in discovered_streams:
            hijack_attempt = self._attempt_stream_hijacking(stream)
            hijacking_attempts.append(hijack_attempt)
        
        # 기능 테스트 (DVD 스트림에 대해)
        functionality_tests = []
        for stream in discovered_streams:
            if "192.168.13.2" in stream["url"]:  # DVD 스트림
                tests = self._test_stream_functionality(stream)
                functionality_tests.extend(tests)
        
        # IOC 생성
        iocs = []
        for stream in discovered_streams:
            iocs.append(f"VIDEO_STREAM:{stream['url']}")
            iocs.append(f"STREAM_TYPE:{stream['type']}")
            
            if not stream.get('authenticated', True):
                iocs.append(f"UNAUTH_STREAM:{stream['url']}")
            
            if "192.168.13.2" in stream["url"]:
                iocs.append("DVD_CAMERA_STREAM")
            
            if stream.get('gimbal_control'):
                iocs.append(f"GIMBAL_CONTROL_AVAILABLE:{stream['url']}")
            
            if stream.get('thermal_imaging'):
                iocs.append(f"THERMAL_CAMERA:{stream['url']}")
        
        # 성공한 하이재킹에 대한 IOC
        successful_hijacks = [h for h in hijacking_attempts if h.get('success')]
        for hijack in successful_hijacks:
            iocs.append(f"STREAM_HIJACKED:{hijack['url']}")
            if hijack.get('control_gained'):
                iocs.append(f"CAMERA_CONTROL_GAINED:{hijack['url']}")
        
        success = len(discovered_streams) > 0
        
        # 위협 분석
        threat_analysis = {
            "surveillance_exposure": len([s for s in discovered_streams if not s.get('authenticated', True)]),
            "critical_assets": len([s for s in discovered_streams if s.get('gimbal_control') or s.get('thermal_imaging')]),
            "hijacking_success_rate": len(successful_hijacks) / len(hijacking_attempts) if hijacking_attempts else 0,
            "real_time_access": len([s for s in discovered_streams if s.get('real_time', True)]),
            "recording_capabilities": len([s for s in discovered_streams if s.get('recording', False)])
        }
        
        details = {
            "discovered_streams": discovered_streams,
            "hijacking_attempts": hijacking_attempts,
            "successful_hijacks": successful_hijacks,
            "functionality_tests": functionality_tests,
            "threat_analysis": threat_analysis,
            "dvd_environment": any("192.168.13.2" in s["url"] for s in discovered_streams),
            "total_streams": len(discovered_streams),
            "success_rate": 0.7 if success else 0.25,
            "attack_recommendations": [
                "Stream content analysis for intelligence",
                "Real-time surveillance monitoring", 
                "Camera control hijacking",
                "Privacy violation documentation",
                "Geolocation extraction from metadata"
            ]
        }
        
        return success, iocs, details
    
    def _generate_ip_in_network(self, network: str) -> str:
        """네트워크 범위 내에서 IP 생성"""
        if "10.0.1" in network:
            return f"10.0.1.{random.randint(1, 254)}"
        elif "172.16" in network:
            return f"172.16.{random.randint(0, 255)}.{random.randint(1, 254)}"
        else:
            return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
    
    def _attempt_stream_hijacking(self, stream: Dict[str, Any]) -> Dict[str, Any]:
        """스트림 하이재킹 시도"""
        hijack_attempt = {
            "url": stream["url"],
            "type": stream["type"],
            "success": False,
            "method": None,
            "capabilities_gained": [],
            "control_gained": False
        }
        
        # 인증되지 않은 스트림은 쉽게 접근 가능
        if not stream.get('authenticated', True):
            hijack_attempt["success"] = random.random() > 0.1  # 90% 성공률
            hijack_attempt["method"] = "direct_access"
            
            if hijack_attempt["success"]:
                hijack_attempt["capabilities_gained"].append("video_access")
                
                # 김벌 제어 가능한 경우
                if stream.get('gimbal_control'):
                    if random.random() > 0.3:  # 70% 확률
                        hijack_attempt["capabilities_gained"].append("gimbal_control")
                        hijack_attempt["control_gained"] = True
                
                # 줌 기능 있는 경우
                if stream.get('zoom_capability'):
                    if random.random() > 0.4:  # 60% 확률
                        hijack_attempt["capabilities_gained"].append("zoom_control")
        
        # 인증된 스트림의 경우 다른 공격 시도
        else:
            attack_methods = [
                {"method": "credential_bruteforce", "success_rate": 0.2},
                {"method": "default_credentials", "success_rate": 0.3},
                {"method": "rtsp_vulnerability", "success_rate": 0.15},
                {"method": "buffer_overflow", "success_rate": 0.1}
            ]
            
            chosen_method = random.choice(attack_methods)
            hijack_attempt["method"] = chosen_method["method"]
            hijack_attempt["success"] = random.random() < chosen_method["success_rate"]
            
            if hijack_attempt["success"]:
                hijack_attempt["capabilities_gained"].append("video_access")
        
        return hijack_attempt
    
    def _test_stream_functionality(self, stream: Dict[str, Any]) -> List[Dict[str, Any]]:
        """스트림 기능 테스트"""
        tests = []
        
        # 기본 스트림 접근 테스트
        tests.append({
            "test": "stream_access",
            "url": stream["url"],
            "success": True,
            "response_time": random.uniform(0.5, 2.0),
            "description": "Successfully accessed video stream"
        })
        
        # 김벌 제어 테스트
        if stream.get('gimbal_control'):
            for action in ["tilt_up", "tilt_down", "pan_left", "pan_right"]:
                tests.append({
                    "test": f"gimbal_{action}",
                    "url": stream["url"],
                    "success": random.random() > 0.2,  # 80% 성공률
                    "response_time": random.uniform(0.3, 1.0),
                    "description": f"Gimbal {action} command test"
                })
        
        # 줌 기능 테스트
        if stream.get('zoom_capability'):
            for zoom_action in ["zoom_in", "zoom_out", "zoom_reset"]:
                tests.append({
                    "test": f"zoom_{zoom_action}",
                    "url": stream["url"],
                    "success": random.random() > 0.3,  # 70% 성공률
                    "response_time": random.uniform(0.4, 1.2),
                    "description": f"Camera {zoom_action} test"
                })
        
        # 녹화 기능 테스트
        if stream.get('recording'):
            tests.append({
                "test": "recording_control",
                "url": stream["url"],
                "success": random.random() > 0.4,  # 60% 성공률
                "response_time": random.uniform(0.5, 1.5),
                "description": "Recording start/stop control test"
            })
        
        return tests