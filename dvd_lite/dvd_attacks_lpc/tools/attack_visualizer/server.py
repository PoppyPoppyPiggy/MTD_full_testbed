import os
import json
from flask import Flask, jsonify, render_template, abort

# --- 경로 설정 ---
TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.abspath(os.path.join(TOOLS_DIR, '..', '..'))
JSON_DIR = os.path.join(LPC_DIR, 'modules', 'attacks_wiki', 'json')

# <<< FIX: Flask가 static 및 templates 폴더를 올바르게 인식하도록 수정
# template_folder='.' : index.html이 있는 현재 폴더를 템플릿 폴더로 지정
# static_folder='static' : CSS/JS 파일이 있는 'static' 폴더를 정적 폴더로 지정
app = Flask(__name__, template_folder='.', static_folder='static')


@app.route('/')
def index():
    """메인 index.html 페이지를 렌더링합니다."""
    return render_template('index.html')

@app.route('/api/attacks')
def list_attacks():
    """json 디렉토리에서 .json 파일 목록을 읽어와서 API로 제공합니다."""
    try:
        files = [f for f in os.listdir(JSON_DIR) if f.endswith('_attack_tree.json')]
        return jsonify(sorted(files))
    except FileNotFoundError:
        abort(500, description="JSON directory not found on the server.")

@app.route('/api/attacks/<string:filename>')
def get_attack_details(filename):
    """요청된 특정 JSON 파일의 내용을 읽어와서 API로 제공합니다."""
    if '..' in filename or '/' in filename:
        abort(400, description="Invalid filename.")
    file_path = os.path.join(JSON_DIR, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        abort(404, description=f"File '{filename}' not found.")
    except json.JSONDecodeError:
        abort(500, description=f"Error decoding JSON from '{filename}'.")


if __name__ == '__main__':
    # 이제 app.run()에는 추가 인자가 필요 없습니다.
    app.run(host='0.0.0.0', port=9000, debug=True)