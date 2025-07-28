#!/usr/bin/env python3
"""
DVD 웹 인터페이스 탐색 스크립트
"""
import urllib.request
import urllib.error
import json

def explore_web_interface():
    """웹 인터페이스 탐색"""
    
    base_urls = [
        "http://10.13.0.5:8000",
        "http://10.13.0.5:8080", 
        "http://10.13.0.3:5000"
    ]
    
    common_paths = [
        "/",
        "/api",
        "/status",
        "/config",
        "/admin",
        "/debug",
        "/info",
        "/version"
    ]
    
    for base_url in base_urls:
        print(f"\n🔍 탐색 중: {base_url}")
        
        for path in common_paths:
            url = base_url + path
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    if response.status == 200:
                        content = response.read().decode('utf-8', errors='ignore')
                        print(f"✅ {path}: {response.status} ({len(content)} chars)")
                        
                        # JSON 응답인지 확인
                        if 'application/json' in response.headers.get('content-type', ''):
                            try:
                                json_data = json.loads(content)
                                print(f"   📊 JSON 키: {list(json_data.keys())}")
                            except:
                                pass
                    else:
                        print(f"⚠️  {path}: {response.status}")
                        
            except urllib.error.HTTPError as e:
                if e.code != 404:  # 404는 일반적이므로 무시
                    print(f"⚠️  {path}: HTTP {e.code}")
            except Exception as e:
                print(f"❌ {path}: {str(e)}")

if __name__ == "__main__":
    explore_web_interface()
