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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")

# 如果有 React 构建产物，用它作为静态文件目录；否则回退到当前目录
if os.path.isdir(DIST_DIR) and os.path.isfile(os.path.join(DIST_DIR, "index.html")):
    STATIC_DIR = DIST_DIR
else:
    STATIC_DIR = BASE_DIR  # 开发模式，Vite 在另一个端口运行

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
CORS(app)

task_manager = TaskManager(DB_PATH)

REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

register_routes(app, task_manager, sse_broker, AGENTS_CONFIG, REPORTS_DIR)


@app.route('/api/health')
def health():
    return {"status": "ok", "agents": len(AGENTS_CONFIG)}


@app.route('/')
def serve_react():
    """返回 React SPA 入口。Electron 桌面应用由此加载。"""
    if os.path.isfile(os.path.join(STATIC_DIR, "index.html")):
        return send_from_directory(STATIC_DIR, "index.html")
    return send_from_directory(BASE_DIR, "index.html")


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """返回 Vite 构建的 JS/CSS 等资源"""
    assets_dir = os.path.join(STATIC_DIR, "assets")
    return send_from_directory(assets_dir, filename)


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
