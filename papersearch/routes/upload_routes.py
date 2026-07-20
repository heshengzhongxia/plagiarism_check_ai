"""
上传与关键词相关路由
- POST /api/upload   — 文件上传与文本提取
- POST /api/keywords — 仅提取关键词（Agent1）
- GET  /api/sources  — 列出可用论文检索源
"""
import os
import tempfile
from flask import Blueprint, request, jsonify

from services.file_parser import extract_text
from services.paper_api import ALL_SOURCES

upload_bp = Blueprint('upload', __name__)


def register_upload_routes(app, deps):
    AGENTS_CONFIG = deps.get('AGENTS_CONFIG', {})

    @upload_bp.route('/api/upload', methods=['POST'])
    def upload_file():
        """上传PDF/Word/TXT文件，返回提取的文本"""
        if 'file' not in request.files:
            return jsonify({"error": "未选择文件"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "文件名为空"}), 400

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.pdf', '.docx', '.doc', '.txt'):
            return jsonify({"error": f"不支持的文件格式: {ext}，请上传 PDF / Word / TXT 文件"}), 400

        try:
            # 保存临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            text = extract_text(tmp_path, file.filename)
            os.unlink(tmp_path)  # 删除临时文件

            char_count = len(text)
            return jsonify({
                "text": text,
                "filename": file.filename,
                "char_count": char_count,
                "status": "ok",
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @upload_bp.route('/api/keywords', methods=['POST'])
    def extract_keywords_only():
        """
        只跑 agent1 出关键词（复用和流水线完全相同的 Agent1Parser）。
        前端收到关键词 → 用户去知网搜 → 上传PDF → 点「开始比对」→ /api/start。
        """
        from agents import create_agent

        data = request.json or {}
        paper_text = data.get('paper', '').strip()
        if not paper_text:
            return jsonify({"error": "论文内容不能为空"}), 400

        try:
            agent1_cfg = AGENTS_CONFIG.get("agent1", {})
            agent1 = create_agent("agent1", agent1_cfg)
            result = agent1.think(paper_text)
            inner = result.get("result", {})

            return jsonify({
                "keywords": inner.get("keywords", []),
                "title": inner.get("title", ""),
                "messages": result.get("messages", []),
                "status": "ok",
            })
        except Exception as e:
            return jsonify({"error": f"关键词提取失败: {str(e)[:200]}"}), 500

    @upload_bp.route('/api/sources', methods=['GET'])
    def get_sources():
        sources = [{"id": sid, "name": info["name"], "desc": info["desc"]}
                   for sid, info in ALL_SOURCES.items()]
        return jsonify({"sources": sources})

    app.register_blueprint(upload_bp)
