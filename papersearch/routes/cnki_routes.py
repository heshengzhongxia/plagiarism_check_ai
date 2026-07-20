"""
CNKI 知网爬取相关路由
- POST /api/cnki/start             — 启动知网爬取
- GET  /api/cnki/status/<task_id>  — 知网爬取状态
- POST /api/cnki/solve/<task_id>   — 提交验证码/手动确认
- POST /api/cnki/parse             — 解析知网检索结果 HTML
- GET  /api/cnki/download/<task_id> — 打包下载爬取的论文
"""
import os
import time
import threading
import base64 as b64
import zipfile
import tempfile
from flask import Blueprint, request, jsonify, send_file

from cnki_spider import cnki_tasks, run_spider

cnki_bp = Blueprint('cnki', __name__)


def register_cnki_routes(app, deps):

    @cnki_bp.route('/api/cnki/start', methods=['POST'])
    def cnki_start():
        """启动知网爬取（非阻塞）"""
        data = request.json or {}
        cnki_url = data.get('url', '').strip()
        if not cnki_url:
            return jsonify({"error": "知网URL不能为空"}), 400

        task_id = f"cnki_{int(time.time())}"
        cnki_tasks[task_id] = {
            "status": "running", "progress": 0,
            "message": "初始化...", "papers": [],
        }

        thread = threading.Thread(target=run_spider, args=(task_id, cnki_url), daemon=True)
        thread.start()

        return jsonify({"task_id": task_id, "status": "started"})

    @cnki_bp.route('/api/cnki/status/<task_id>', methods=['GET'])
    def cnki_status(task_id):
        """获取知网爬取状态（含验证码信息）"""
        task = cnki_tasks.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404

        resp = dict(task)
        # captcha_image 是bytes，需要转base64
        if isinstance(resp.get("captcha_image"), bytes):
            resp["captcha_image"] = b64.b64encode(resp["captcha_image"]).decode('utf-8')
        return jsonify(resp)

    @cnki_bp.route('/api/cnki/solve/<task_id>', methods=['POST'])
    def cnki_solve(task_id):
        """提交验证码答案 / 确认手动操作"""
        data = request.json or {}
        answer = data.get('answer', '').strip()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        confirm = data.get('confirm', False)

        if task_id in cnki_tasks:
            if answer:
                cnki_tasks[task_id]["captcha_answer"] = answer
            if username and password:
                cnki_tasks[task_id]["credentials"] = {"username": username, "password": password}
            if confirm:
                cnki_tasks[task_id]["user_confirmed"] = True
            new_url = data.get('new_url', '').strip()
            if new_url:
                cnki_tasks[task_id]["new_url"] = new_url
            return jsonify({"status": "ok"})
        return jsonify({"error": "任务不存在"}), 404

    @cnki_bp.route('/api/cnki/parse', methods=['POST'])
    def cnki_parse():
        """解析用户粘贴的知网检索结果页HTML，提取论文列表"""
        data = request.json or {}
        html_content = data.get('html', '').strip()
        if not html_content:
            return jsonify({"error": "HTML内容为空"}), 400

        papers = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # 知网检索结果的结构：找所有论文标题和摘要
            # 方式1：找标题链接
            for a in soup.find_all('a'):
                href = a.get('href', '')
                title = a.get_text(strip=True)
                if title and len(title) > 10 and ('kns.cnki.net' in href or 'detail' in href.lower()):
                    papers.append({"title": title[:200], "url": href, "abstract": "", "source": "知网CNKI"})

            # 方式2：通过class找（知网结构多变，也尝试通用方式）
            if not papers:
                # 找所有看起来像论文标题的文本
                for el in soup.find_all(['h3', 'h4', 'dt', 'p', 'a']):
                    text = el.get_text(strip=True)
                    if 15 < len(text) < 200:
                        # 检查是否有相邻的摘要
                        next_el = el.find_next_sibling()
                        abstract = next_el.get_text(strip=True)[:500] if next_el else ""
                        papers.append({"title": text, "url": "", "abstract": abstract, "source": "知网CNKI"})

            # 去重
            seen = set()
            unique = []
            for p in papers:
                key = p["title"][:30]
                if key not in seen:
                    seen.add(key)
                    unique.append(p)

            return jsonify({"papers": unique[:15], "total": len(unique), "status": "ok"})
        except Exception as e:
            return jsonify({"error": f"解析失败: {e}"}), 500

    @cnki_bp.route('/api/cnki/download/<task_id>', methods=['GET'])
    def cnki_download(task_id):
        """打包下载知网爬取的论文"""
        task = cnki_tasks.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404

        papers = task.get("papers", [])
        if not papers:
            return jsonify({"error": "无论文可下载"}), 404

        # 打包为zip
        zip_path = os.path.join(tempfile.gettempdir(), f"cnki_{task_id}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for p in papers:
                fp = p.get("file_path")
                if fp and os.path.exists(fp):
                    zf.write(fp, os.path.basename(fp))
        return send_file(zip_path, as_attachment=True,
                         download_name=f"知网论文_{task_id}.zip",
                         mimetype='application/zip')

    app.register_blueprint(cnki_bp)
