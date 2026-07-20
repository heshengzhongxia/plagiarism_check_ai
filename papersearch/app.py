"""
六智Agent论文工坊 - 入口
DAG数据流：agent1→(agent2,agent3,agent6)；agent2→agent3；agent3→(agent4,agent6)；agent4→agent5→agent6
"""
import os
import sys
import time
import threading
from flask import Flask, send_from_directory
from flask_cors import CORS

from config import AGENTS_CONFIG, PAPER_PORT, DB_PATH
from routes import register_routes
from engine.task_manager import TaskManager
from engine.sse_broker import sse_broker

app = Flask(__name__, static_folder='.')
CORS(app)

task_manager = TaskManager(DB_PATH)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

register_routes(app, task_manager, sse_broker, AGENTS_CONFIG, REPORTS_DIR)


@app.route('/api/health')
def health():
    return {"status": "ok", "agents": len(AGENTS_CONFIG)}


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    from cnki_spider import TEMP_DIR as CNKI_TEMP_DIR

    print("=" * 55)
    print("  六智Agent论文工坊 - 后端服务 v5.0")
    print("  DAG数据流 · 语义查重 · CNKI · Docx报告")
    print(f"  访问地址: http://127.0.0.1:{PAPER_PORT}")
    print("=" * 55)

    # 启动临时文件清理（每小时清理超过24小时的文件）
    def _cleanup_loop():
        while True:
            time.sleep(3600)
            cutoff = time.time() - 86400
            for d in [CNKI_TEMP_DIR, REPORTS_DIR]:
                if os.path.exists(d):
                    for f in os.listdir(d):
                        fp = os.path.join(d, f)
                        try:
                            if os.path.getmtime(fp) < cutoff:
                                os.remove(fp)
                        except Exception:
                            pass

    threading.Thread(target=_cleanup_loop, daemon=True).start()

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    app.run(debug=False, host='0.0.0.0', port=PAPER_PORT)
