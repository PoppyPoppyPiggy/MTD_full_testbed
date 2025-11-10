#!/usr/bin/env python3
import torch
import argparse
import os

def analyze_pth_file(policy_path):
    """
    .pth (state_dict) 파일을 로드하여 내부의 모든 키와
    각 키에 해당하는 텐서(가중치)의 shape를 출력합니다.
    """
    print(f"--- PyTorch 모델 분석기 ---")
    print(f"파일 로드 시도: {policy_path}\n")
    
    try:
        # CPU로 state_dict 로드
        state_dict = torch.load(policy_path, map_location=torch.device('cpu'))
        
        print(f"[성공] 파일 로드 완료. 총 {len(state_dict)}개의 키를 찾았습니다.")
        print("-" * 40)
        
        max_key_len = max(len(key) for key in state_dict.keys())
        
        for key, tensor in state_dict.items():
            # 키 이름을 왼쪽 정렬하고, shape를 출력
            print(f"Key: {key:<{max_key_len}} | Shape: {tensor.shape}")
            
        print("-" * 40)
        print("\n분석 완료.")

    except FileNotFoundError:
        print(f"오류: 파일을 찾을 수 없습니다: {policy_path}")
    except Exception as e:
        print(f"파일 로드 중 오류 발생: {e}")
        print("이 파일은 PyTorch state_dict 파일이 아닐 수 있습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyTorch .pth state_dict 분석기")
    
    # rl_driven_deception_manager.py와 동일한 기본 경로 사용
    default_path = "mtd/shared_state/defender_policy_L4.pth"
    
    parser.add_argument("--policy", type=str, 
                        default=default_path,
                        help=f"분석할 .pth 파일 경로 (기본값: {default_path})")
    args = parser.parse_args()

    if not os.path.exists(args.policy):
        print(f"경고: 기본 경로에서 파일을 찾을 수 없습니다: {args.policy}")
        print("스크립트가 dvd_attacks_lpc 디렉토리에서 실행되고 있는지 확인하세요.")
    else:
        analyze_pth_file(args.policy)