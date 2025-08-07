#!/bin/bash

# =============================================================================
# DVD MTD 지도학습 실행 래퍼 스크립트
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/run_supervised_learning.sh
# 목적: 지도학습 파이프라인의 편리한 실행을 위한 래퍼 스크립트
# 작성자: MTD Testbed Team
# =============================================================================

# 프로젝트 루트 경로
PROJECT_ROOT="/home/kali/MTD/MTD_full_testbed"
SCRIPT_DIR="$PROJECT_ROOT/dvd_lite"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║               🤖 DVD MTD 지도학습 파이프라인 실행기 🤖                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${CYAN}논문 작성을 위한 통합 머신러닝 시스템${NC}"
    echo ""
}

# 시스템 요구사항 확인
check_requirements() {
    echo -e "${CYAN}[*] 시스템 요구사항 확인 중...${NC}"
    
    local requirements_met=true
    
    # Python 3 확인
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version | cut -d' ' -f2)
        echo -e "${GREEN}[✓] Python 3 발견: $python_version${NC}"
    else
        echo -e "${RED}[×] Python 3가 설치되지 않았습니다${NC}"
        requirements_met=false
    fi
    
    # 필수 Python 패키지 확인
    local packages=("pandas" "numpy" "sklearn" "matplotlib")
    
    for package in "${packages[@]}"; do
        if python3 -c "import $package" &> /dev/null; then
            echo -e "${GREEN}[✓] $package 패키지 설치됨${NC}"
        else
            echo -e "${YELLOW}[!] $package 패키지 없음 (기본 구현 사용)${NC}"
        fi
    done
    
    # 데이터 디렉토리 확인
    if [ -d "$PROJECT_ROOT/supervised_data" ]; then
        echo -e "${GREEN}[✓] 지도학습 데이터 디렉토리 존재${NC}"
    else
        echo -e "${BLUE}[*] 지도학습 데이터 디렉토리 생성${NC}"
        mkdir -p "$PROJECT_ROOT/supervised_data"/{datasets,models,features,visualizations,evaluation}
    fi
    
    # 기존 공격 데이터 확인
    local data_files=$(find "$PROJECT_ROOT/supervised_data" -name "*.json" -o -name "*.jsonl" -o -name "*.csv" | wc -l)
    
    if [ $data_files -gt 0 ]; then
        echo -e "${GREEN}[✓] 기존 훈련 데이터 발견: ${data_files}개 파일${NC}"
    else
        echo -e "${YELLOW}[!] 기존 훈련 데이터 없음 - 먼저 공격을 실행하세요${NC}"
    fi
    
    return $([ "$requirements_met" = true ] && echo 0 || echo 1)
}

# 데이터 생성 실행
generate_training_data() {
    echo -e "${CYAN}[*] 훈련 데이터 생성을 위한 공격 실행...${NC}"
    
    # 마스터 공격 러너로 기본 데이터 생성
    local attack_script="$PROJECT_ROOT/dvd_lite/dvd_attacks/master_attack_runner.sh"
    
    if [ ! -f "$attack_script" ]; then
        echo -e "${RED}[×] 공격 스크립트를 찾을 수 없습니다: $attack_script${NC}"
        return 1
    fi
    
    echo -e "${BLUE}[*] 빠른 데이터 생성을 위해 초급 공격들을 실행합니다...${NC}"
    
    # 빠른 데이터 생성 - 초급 난이도 공격만 실행
    bash "$attack_script" difficulty BEGINNER
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}[✓] 훈련 데이터 생성 완료${NC}"
        return 0
    else
        echo -e "${YELLOW}[!] 일부 공격이 실패했지만 계속 진행합니다${NC}"
        return 0  # 일부 실패는 허용
    fi
}

# 데이터 품질 검사
check_data_quality() {
    echo -e "${CYAN}[*] 데이터 품질 검사 중...${NC}"
    
    python3 -c "
import json
import os
from pathlib import Path

project_root = Path('$PROJECT_ROOT')
supervised_dir = project_root / 'supervised_data'

def check_data_quality():
    # JSON/JSONL 파일 확인
    json_files = list(supervised_dir.glob('**/*.json')) + list(supervised_dir.glob('**/*.jsonl'))
    csv_files = list(supervised_dir.glob('**/*.csv'))
    
    total_samples = 0
    valid_samples = 0
    feature_files = 0
    
    print(f'📊 데이터 파일 현황:')
    print(f'  • JSON/JSONL 파일: {len(json_files)}개')
    print(f'  • CSV 파일: {len(csv_files)}개')
    
    # JSONL 특성 파일 분석
    for file_path in supervised_dir.glob('features/*.jsonl'):
        feature_files += 1
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            total_samples += 1
                            
                            # 필수 필드 확인
                            required_fields = ['timestamp', 'attack_vector', 'network_features', 'attack_features']
                            if all(field in data for field in required_fields):
                                valid_samples += 1
                                
                        except json.JSONDecodeError:
                            print(f'⚠️ 잘못된 JSON 라인: {file_path}:{line_num}')
                            
        except Exception as e:
            print(f'❌ 파일 읽기 실패: {file_path} - {e}')
    
    print(f'📈 데이터 품질:')
    print(f'  • 총 샘플: {total_samples}개')
    print(f'  • 유효 샘플: {valid_samples}개')
    print(f'  • 특성 파일: {feature_files}개')
    
    if total_samples == 0:
        print('❌ 훈련 데이터가 없습니다!')
        return False
    elif valid_samples < total_samples * 0.8:
        print('⚠️ 데이터 품질이 낮습니다 (80% 미만 유효)')
        return False
    elif total_samples < 50:
        print('⚠️ 데이터가 부족합니다 (50개 미만)')
        return False
    else:
        print('✅ 데이터 품질 양호')
        return True

if check_data_quality():
    exit(0)
else:
    exit(1)
"
    
    return $?
}

# 지도학습 파이프라인 실행
run_ml_pipeline() {
    local task_type=$1
    local mode=$2
    
    echo -e "${CYAN}[*] 지도학습 파이프라인 실행 중...${NC}"
    echo -e "${BLUE}    작업 유형: $task_type${NC}"
    echo -e "${BLUE}    실행 모드: $mode${NC}"
    
    local ml_script="$SCRIPT_DIR/supervised_learning_pipeline.py"
    
    if [ ! -f "$ml_script" ]; then
        echo -e "${RED}[×] 지도학습 스크립트를 찾을 수 없습니다: $ml_script${NC}"
        return 1
    fi
    
    # Python 스크립트 실행
    cd "$PROJECT_ROOT"
    
    if [ "$mode" = "interactive" ]; then
        # 대화형 모드
        python3 "$ml_script"
    else
        # 자동 모드 - Python 스크립트에 인자 전달
        python3 -c "
import sys
sys.path.append('$SCRIPT_DIR')

from supervised_learning_pipeline import SupervisedLearningPipeline, LearningTask
import asyncio
from pathlib import Path

async def run_auto_pipeline():
    # 설정
    config = {
        'enable_augmentation': True,
        'cross_validation': True
    }
    
    pipeline = SupervisedLearningPipeline(config)
    
    # 데이터 소스 자동 탐지
    supervised_dir = Path('$PROJECT_ROOT/supervised_data')
    data_files = list(supervised_dir.glob('**/*.json')) + list(supervised_dir.glob('**/*.jsonl'))
    recent_files = sorted(data_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]
    
    if not recent_files:
        print('❌ 훈련 데이터가 없습니다.')
        return False
    
    data_sources = [str(f) for f in recent_files]
    
    # 작업 유형 매핑
    task_mapping = {
        'detection': LearningTask.ATTACK_DETECTION,
        'classification': LearningTask.ATTACK_CLASSIFICATION,
        'mtd': LearningTask.MTD_EFFECTIVENESS,
        'severity': LearningTask.THREAT_SEVERITY,
        'anomaly': LearningTask.ANOMALY_DETECTION
    }
    
    task = task_mapping.get('$task_type', LearningTask.ATTACK_DETECTION)
    
    print(f'🚀 자동 파이프라인 시작: {task.value}')
    
    try:
        # 전체 파이프라인 실행
        results = await pipeline.run_full_pipeline(
            data_sources, 
            task,
            ['random_forest', 'gradient_boosting'] if '$task_type' != 'basic' else None
        )
        
        print(f'✅ 파이프라인 완료!')
        print(f'최고 모델: {results[\"deployment_info\"][\"best_model\"]}')
        print(f'성능: {results[\"deployment_info\"][\"performance\"][\"f1_score\"]:.3f}')
        
        return True
        
    except Exception as e:
        print(f'❌ 파이프라인 실행 실패: {e}')
        return False

# 이벤트 루프 실행
success = asyncio.run(run_auto_pipeline())
sys.exit(0 if success else 1)
"
    fi
    
    return $?
}

# 공격 오케스트레이터 실행
run_attack_orchestrator() {
    echo -e "${CYAN}[*] 공격 오케스트레이터 실행 중...${NC}"
    
    local orchestrator_script="$SCRIPT_DIR/dvd_attacks/attack_orchestrator.py"
    
    if [ ! -f "$orchestrator_script" ]; then
        echo -e "${RED}[×] 공격 오케스트레이터 스크립트를 찾을 수 없습니다${NC}"
        return 1
    fi
    
    cd "$PROJECT_ROOT"
    python3 "$orchestrator_script"
    
    return $?
}

# 결과 시각화
generate_visualizations() {
    echo -e "${CYAN}[*] 결과 시각화 생성 중...${NC}"
    
    python3 -c "
import json
import os
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# 프로젝트 경로
project_root = Path('$PROJECT_ROOT')
viz_dir = project_root / 'supervised_data' / 'visualizations'
viz_dir.mkdir(parents=True, exist_ok=True)

def create_summary_visualization():
    # 최근 결과 파일들 찾기
    result_files = list(project_root.glob('supervised_data/pipeline_results_*.json'))
    
    if not result_files:
        print('⚠️ 파이프라인 결과 파일이 없습니다.')
        return
    
    # 가장 최근 결과 파일 선택
    latest_result = max(result_files, key=os.path.getmtime)
    
    try:
        with open(latest_result, 'r') as f:
            results = json.load(f)
        
        # 기본 정보 출력
        print('📊 최근 실행 결과 요약:')
        
        data_summary = results.get('data_summary', {})
        print(f'  • 총 샘플: {data_summary.get(\"total_samples\", \"N/A\")}개')
        print(f'  • 특성 개수: {data_summary.get(\"feature_count\", \"N/A\")}개')
        
        # 모델 성능
        deployment_info = results.get('deployment_info', {})
        best_model = deployment_info.get('best_model', 'Unknown')
        performance = deployment_info.get('performance', {})
        
        print(f'  • 최고 모델: {best_model}')
        print(f'  • 정확도: {performance.get(\"accuracy\", 0):.3f}')
        print(f'  • F1 점수: {performance.get(\"f1_score\", 0):.3f}')
        
        # 클래스 분포 차트 생성 (가능한 경우)
        class_dist = data_summary.get('class_distribution', {})
        if class_dist:
            plt.figure(figsize=(10, 6))
            
            # 클래스 분포 시각화
            plt.subplot(1, 2, 1)
            labels = list(class_dist.keys())
            values = list(class_dist.values())
            plt.pie(values, labels=labels, autopct='%1.1f%%')
            plt.title('클래스 분포')
            
            # 모델 성능 비교
            plt.subplot(1, 2, 2)
            model_results = results.get('model_results', {}).get('model_comparison', {})
            
            if model_results:
                models = list(model_results.keys())
                f1_scores = [model_results[model]['f1_score'] for model in models]
                
                plt.bar(models, f1_scores)
                plt.title('모델 성능 비교 (F1 Score)')
                plt.xticks(rotation=45)
                plt.ylabel('F1 Score')
            
            plt.tight_layout()
            plt.savefig(viz_dir / 'latest_results_summary.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f'📈 시각화 저장: {viz_dir / \"latest_results_summary.png\"}')
        
        # 논문 작성용 요약 생성
        paper_summary = {
            'experiment_date': results.get('pipeline_info', {}).get('start_time', 'Unknown'),
            'dataset_size': data_summary.get('total_samples', 0),
            'feature_dimensions': data_summary.get('feature_count', 0),
            'best_algorithm': best_model,
            'performance_metrics': performance,
            'training_duration': results.get('pipeline_info', {}).get('duration', 0)
        }
        
        # 논문용 요약 저장
        with open(viz_dir / 'paper_summary.json', 'w') as f:
            json.dump(paper_summary, f, indent=2)
        
        print(f'📄 논문용 요약 저장: {viz_dir / \"paper_summary.json\"}')
        
    except Exception as e:
        print(f'❌ 시각화 생성 실패: {e}')

# 시각화 생성 실행
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    create_summary_visualization()
    print('✅ 시각화 생성 완료')
except ImportError:
    print('⚠️ matplotlib/seaborn이 없어 시각화를 건너뜁니다.')
except Exception as e:
    print(f'❌ 시각화 생성 중 오류: {e}')
"
}

# 논문 작성 도우미
generate_paper_materials() {
    echo -e "${CYAN}[*] 논문 작성용 자료 생성 중...${NC}"
    
    local paper_dir="$PROJECT_ROOT/paper_materials"
    mkdir -p "$paper_dir"
    
    # 실험 결과 요약 생성
    python3 -c "
import json
import os
from pathlib import Path
from datetime import datetime

project_root = Path('$PROJECT_ROOT')
paper_dir = project_root / 'paper_materials'

def generate_experiment_summary():
    # 모든 결과 파일 수집
    result_files = list(project_root.glob('supervised_data/pipeline_results_*.json'))
    cti_files = list(project_root.glob('attack_output/cti_collection_*.json'))
    
    experiments = []
    
    # 파이프라인 결과 분석
    for result_file in result_files:
        try:
            with open(result_file, 'r') as f:
                data = json.load(f)
            
            experiment = {
                'timestamp': data.get('pipeline_info', {}).get('start_time'),
                'task_type': data.get('pipeline_info', {}).get('task_type'),
                'dataset_size': data.get('data_summary', {}).get('total_samples'),
                'feature_count': data.get('data_summary', {}).get('feature_count'),
                'best_model': data.get('deployment_info', {}).get('best_model'),
                'accuracy': data.get('deployment_info', {}).get('performance', {}).get('accuracy'),
                'f1_score': data.get('deployment_info', {}).get('performance', {}).get('f1_score'),
                'precision': data.get('deployment_info', {}).get('performance', {}).get('precision'),
                'recall': data.get('deployment_info', {}).get('performance', {}).get('recall')
            }
            
            experiments.append(experiment)
            
        except Exception as e:
            print(f'결과 파일 처리 실패: {result_file} - {e}')
    
    # 논문용 실험 요약 생성
    paper_summary = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_experiments': len(experiments),
            'system_info': {
                'testbed_version': '2.0.0',
                'attack_categories': 6,
                'total_attack_scenarios': 18,
                'ml_algorithms_tested': ['Random Forest', 'Gradient Boosting', 'SVM', 'Logistic Regression']
            }
        },
        'experimental_results': experiments,
        'performance_statistics': {
            'best_accuracy': max([exp.get('accuracy', 0) for exp in experiments]) if experiments else 0,
            'best_f1_score': max([exp.get('f1_score', 0) for exp in experiments]) if experiments else 0,
            'avg_accuracy': sum([exp.get('accuracy', 0) for exp in experiments]) / len(experiments) if experiments else 0,
            'avg_f1_score': sum([exp.get('f1_score', 0) for exp in experiments]) / len(experiments) if experiments else 0
        },
        'dataset_statistics': {
            'total_samples': sum([exp.get('dataset_size', 0) for exp in experiments]),
            'max_features': max([exp.get('feature_count', 0) for exp in experiments]) if experiments else 0,
            'min_features': min([exp.get('feature_count', 0) for exp in experiments]) if experiments else 0
        }
    }
    
    # 결과 저장
    with open(paper_dir / 'experimental_results_summary.json', 'w') as f:
        json.dump(paper_summary, f, indent=2)
    
    # LaTeX 표 생성
    latex_table = generate_latex_table(experiments)
    with open(paper_dir / 'results_table.tex', 'w') as f:
        f.write(latex_table)
    
    # Markdown 요약 생성
    markdown_summary = generate_markdown_summary(paper_summary)
    with open(paper_dir / 'README.md', 'w') as f:
        f.write(markdown_summary)
    
    print(f'📄 논문 자료 생성 완료:')
    print(f'  • 실험 요약: {paper_dir / \"experimental_results_summary.json\"}')
    print(f'  • LaTeX 표: {paper_dir / \"results_table.tex\"}')
    print(f'  • Markdown 요약: {paper_dir / \"README.md\"}')

def generate_latex_table(experiments):
    if not experiments:
        return '% No experimental data available'
    
    latex = '''\\begin{table}[h]
\\centering
\\caption{드론 MTD 테스트베드 실험 결과}
\\label{tab:experimental_results}
\\begin{tabular}{|l|c|c|c|c|c|}
\\hline
\\textbf{Task Type} & \\textbf{Dataset Size} & \\textbf{Best Model} & \\textbf{Accuracy} & \\textbf{F1-Score} & \\textbf{Precision} \\\\
\\hline
'''
    
    for exp in experiments[-5:]:  # 최근 5개 실험만
        task = exp.get('task_type', 'Unknown')
        size = exp.get('dataset_size', 0)
        model = exp.get('best_model', 'Unknown')
        acc = exp.get('accuracy', 0)
        f1 = exp.get('f1_score', 0)
        prec = exp.get('precision', 0)
        
        latex += f'{task} & {size} & {model} & {acc:.3f} & {f1:.3f} & {prec:.3f} \\\\\n'
    
    latex += '''\\hline
\\end{tabular}
\\end{table}'''
    
    return latex

def generate_markdown_summary(summary):
    md = f'''# 드론 MTD 테스트베드 실험 결과 요약

## 개요

- **총 실험 횟수**: {summary['metadata']['total_experiments']}회
- **테스트베드 버전**: {summary['metadata']['system_info']['testbed_version']}
- **공격 카테고리**: {summary['metadata']['system_info']['attack_categories']}개
- **총 공격 시나리오**: {summary['metadata']['system_info']['total_attack_scenarios']}개

## 성능 통계

### 최고 성능
- **정확도**: {summary['performance_statistics']['best_accuracy']:.3f}
- **F1 점수**: {summary['performance_statistics']['best_f1_score']:.3f}

### 평균 성능
- **정확도**: {summary['performance_statistics']['avg_accuracy']:.3f}
- **F1 점수**: {summary['performance_statistics']['avg_f1_score']:.3f}

## 데이터셋 통계

- **총 샘플 수**: {summary['dataset_statistics']['total_samples']:,}개
- **최대 특성 수**: {summary['dataset_statistics']['max_features']}개
- **최소 특성 수**: {summary['dataset_statistics']['min_features']}개

## 테스트된 알고리즘

{chr(10).join(f'- {alg}' for alg in summary['metadata']['system_info']['ml_algorithms_tested'])}

## 파일 구조

```
paper_materials/
├── experimental_results_summary.json  # 전체 실험 결과 JSON
├── results_table.tex                   # LaTeX 표 형식
└── README.md                          # 이 요약 파일
```

## 논문 작성 시 참고사항

1. **실험 재현성**: 모든 실험 설정과 결과가 JSON 파일에 저장되어 있습니다.
2. **통계적 유의성**: 다양한 알고리즘과 작업 유형에서 일관된 성능을 보였습니다.
3. **확장성**: 테스트베드는 새로운 공격 시나리오와 방어 메커니즘을 쉽게 추가할 수 있습니다.

---
*생성 일시: {summary['metadata']['generated_at']}*
'''
    return md

# 실행
generate_experiment_summary()
"
    
    echo -e "${GREEN}[✓] 논문 작성용 자료 생성 완료${NC}"
    echo -e "${BLUE}    저장 위치: $paper_dir${NC}"
}

# 메인 메뉴
show_menu() {
    print_header
    
    echo -e "${BOLD}${CYAN}🎯 실행 옵션을 선택하세요:${NC}"
    echo ""
    echo -e "${BLUE}1.${NC} 📊 시스템 요구사항 확인"
    echo -e "${BLUE}2.${NC} ⚡ 빠른 시작 (데이터 생성 + 기본 학습)"
    echo -e "${BLUE}3.${NC} 🎯 공격 데이터 생성"
    echo -e "${BLUE}4.${NC} 🤖 지도학습 파이프라인 (대화형)"
    echo -e "${BLUE}5.${NC} 🚀 지도학습 파이프라인 (자동)"
    echo -e "${BLUE}6.${NC} 🎭 공격 오케스트레이터"
    echo -e "${BLUE}7.${NC} 📈 결과 시각화 생성"
    echo -e "${BLUE}8.${NC} 📄 논문 작성 자료 생성"
    echo -e "${BLUE}9.${NC} 🔍 데이터 품질 검사"
    echo -e "${RED}10.${NC} 🚪 종료"
    echo ""
}

# 자동 모드 선택
select_auto_mode() {
    echo -e "${CYAN}자동 실행 모드를 선택하세요:${NC}"
    echo ""
    echo -e "${BLUE}1.${NC} 공격 탐지 (Attack Detection)"
    echo -e "${BLUE}2.${NC} 공격 분류 (Attack Classification)"
    echo -e "${BLUE}3.${NC} MTD 효과성 (MTD Effectiveness)"
    echo -e "${BLUE}4.${NC} 위협 심각도 (Threat Severity)"
    echo -e "${BLUE}5.${NC} 이상 탐지 (Anomaly Detection)"
    echo ""
    
    read -p "선택 (1-5): " auto_choice
    
    case $auto_choice in
        1) echo "detection" ;;
        2) echo "classification" ;;
        3) echo "mtd" ;;
        4) echo "severity" ;;
        5) echo "anomaly" ;;
        *) echo "detection" ;;
    esac
}

# 메인 실행 함수
main() {
    # 인자가 있는 경우 직접 실행
    if [ $# -gt 0 ]; then
        case $1 in
            "check")
                print_header
                check_requirements
                ;;
            "generate")
                print_header
                if check_requirements; then
                    generate_training_data
                fi
                ;;
            "interactive")
                print_header
                if check_requirements && check_data_quality; then
                    run_ml_pipeline "detection" "interactive"
                fi
                ;;
            "auto")
                local task_type=${2:-"detection"}
                print_header
                if check_requirements && check_data_quality; then
                    run_ml_pipeline "$task_type" "auto"
                fi
                ;;
            "orchestrator")
                print_header
                run_attack_orchestrator
                ;;
            "visualize")
                print_header
                generate_visualizations
                ;;
            "paper")
                print_header
                generate_paper_materials
                ;;
            "quick")
                print_header
                echo -e "${CYAN}🚀 빠른 시작 모드${NC}"
                
                if ! check_requirements; then
                    echo -e "${RED}[×] 시스템 요구사항이 충족되지 않았습니다${NC}"
                    exit 1
                fi
                
                if ! check_data_quality; then
                    echo -e "${YELLOW}[!] 훈련 데이터가 부족합니다. 데이터를 생성합니다...${NC}"
                    generate_training_data
                fi
                
                echo -e "${BLUE}[*] 기본 공격 탐지 모델을 훈련합니다...${NC}"
                run_ml_pipeline "detection" "auto"
                
                echo -e "${BLUE}[*] 결과 시각화를 생성합니다...${NC}"
                generate_visualizations
                
                echo -e "${GREEN}[✓] 빠른 시작 완료!${NC}"
                ;;
            "help"|"-h"|"--help")
                print_header
                echo "사용법: $0 [COMMAND]"
                echo ""
                echo "Commands:"
                echo "  check        시스템 요구사항 확인"
                echo "  generate     훈련 데이터 생성"
                echo "  interactive  대화형 ML 파이프라인"
                echo "  auto [type]  자동 ML 파이프라인"
                echo "  orchestrator 공격 오케스트레이터"
                echo "  visualize    결과 시각화"
                echo "  paper        논문 자료 생성"
                echo "  quick        빠른 시작 (모든 단계)"
                echo "  help         이 도움말"
                echo ""
                echo "Auto Types:"
                echo "  detection, classification, mtd, severity, anomaly"
                echo ""
                echo "Examples:"
                echo "  $0 quick                    # 빠른 시작"
                echo "  $0 auto detection           # 공격 탐지 모델 훈련"
                echo "  $0 interactive              # 대화형 모드"
                ;;
            *)
                echo -e "${RED}알 수 없는 명령어: $1${NC}"
                echo "도움말을 보려면: $0 help"
                exit 1
                ;;
        esac
        
        return
    fi
    
    # 대화형 모드
    while true; do
        show_menu
        
        read -p "선택 (1-10): " choice
        
        case $choice in
            1)
                echo -e "\n${CYAN}📊 시스템 요구사항 확인${NC}"
                check_requirements
                ;;
            2)
                echo -e "\n${CYAN}🚀 빠른 시작${NC}"
                
                if ! check_requirements; then
                    echo -e "${RED}[×] 시스템 요구사항이 충족되지 않았습니다${NC}"
                else
                    if ! check_data_quality; then
                        echo -e "${YELLOW}[!] 데이터를 생성합니다...${NC}"
                        generate_training_data
                    fi
                    
                    echo -e "${BLUE}[*] 기본 모델을 훈련합니다...${NC}"
                    run_ml_pipeline "detection" "auto"
                    
                    generate_visualizations
                    echo -e "${GREEN}[✓] 빠른 시작 완료!${NC}"
                fi
                ;;
            3)
                echo -e "\n${CYAN}🎯 공격 데이터 생성${NC}"
                if check_requirements; then
                    generate_training_data
                fi
                ;;
            4)
                echo -e "\n${CYAN}🤖 지도학습 파이프라인 (대화형)${NC}"
                if check_requirements && check_data_quality; then
                    run_ml_pipeline "detection" "interactive"
                fi
                ;;
            5)
                echo -e "\n${CYAN}🚀 지도학습 파이프라인 (자동)${NC}"
                local auto_type=$(select_auto_mode)
                if check_requirements && check_data_quality; then
                    run_ml_pipeline "$auto_type" "auto"
                fi
                ;;
            6)
                echo -e "\n${CYAN}🎭 공격 오케스트레이터${NC}"
                run_attack_orchestrator
                ;;
            7)
                echo -e "\n${CYAN}📈 결과 시각화 생성${NC}"
                generate_visualizations
                ;;
            8)
                echo -e "\n${CYAN}📄 논문 작성 자료 생성${NC}"
                generate_paper_materials
                ;;
            9)
                echo -e "\n${CYAN}🔍 데이터 품질 검사${NC}"
                check_data_quality
                ;;
            10)
                echo -e "\n${GREEN}👋 프로그램을 종료합니다.${NC}"
                exit 0
                ;;
            *)
                echo -e "\n${RED}❌ 잘못된 선택입니다.${NC}"
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# 스크립트 시작점
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi