import os
import json
import pandas as pd

# 1.1 단계에서 정의한 라벨링 가이드
ATTACK_TO_CATEGORY = {
    "gps-spoofing.sh": "기동부", "attitude-spoofing.sh": "기동부", "geofencing-attack.sh": "기동부",
    "communication-link-flooding.sh": "통신부", "wifi-deauth-attack.sh": "통신부", "packet-sniffing.sh": "통신부",
    "flight-mode-injection.sh": "제어부", "battery-spoofing.sh": "제어부", "flight-termination.sh": "제어부",
}

def process_log_file(filepath, attack_name):
    category = ATTACK_TO_CATEGORY.get(attack_name)
    if not category: return []
    
    records = []
    with open(filepath, 'r') as f:
        for line in f:
            try:
                log = json.loads(line)
                # 로그를 하나의 의미 있는 텍스트 덩어리로 변환
                log_text = f"{log.get('type', '')} {' '.join([f'{k}_{v}' for k, v in log.get('data', {}).items()])}"
                records.append({'log_text': log_text.strip(), 'category': category})
            except: continue
    return records

def main():
    data_source_dir = "collected_logs"
    if not os.path.exists(data_source_dir):
        os.makedirs(os.path.join(data_source_dir, "기동부")); os.makedirs(os.path.join(data_source_dir, "통신부")); os.makedirs(os.path.join(data_source_dir, "제어부"))
        print(f"'{data_source_dir}' 폴더 구조를 생성했습니다. 각 카테고리에 맞는 로그 파일을 저장해주세요.")
        return

    all_records = []
    for category_name in os.listdir(data_source_dir):
        category_path = os.path.join(data_source_dir, category_name)
        if os.path.isdir(category_path):
            for log_filename in os.listdir(category_path):
                attack_name = log_filename.replace(".log", "")
                records = process_log_file(os.path.join(category_path, log_filename), attack_name)
                all_records.extend(records)
    
    df = pd.DataFrame(all_records)
    output_path = "labeled_cti_dataset.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"총 {len(df)}개 로그 처리 완료! -> '{output_path}'")

if __name__ == "__main__":
    main()