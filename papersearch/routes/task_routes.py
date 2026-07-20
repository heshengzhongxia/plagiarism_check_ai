"""
任务流水线路由
- POST /api/start             — 启动分析流水线
- GET  /api/status/<task_id>  — 任务状态快照
- GET  /api/stream/<task_id>  — SSE 实时事件流
- POST /api/confirm/<task_id> — 手动模式确认
- POST /api/retry/<task_id>   — 重试当前 Agent
"""
import time
import threading
import json
import queue as queue_module
from flask import Blueprint, request, jsonify, Response, stream_with_context

from services.paper_api import ALL_SOURCES
from engine.sse_broker import sse_broker

task_bp = Blueprint('task', __name__)


def _add_message(task_store, task_id, msg):
    if task_id in task_store:
        task_store[task_id]["conversation"].append(msg)


def _system_msg(message, emoji="⚙️"):
    return {"agent_id": "system", "agent_name": "系统", "emoji": emoji,
            "color": "#7b8ca8", "message": message, "timestamp": time.time()}


def register_task_routes(app, deps):
    task_store = deps['task_store']
    task_lock = deps['task_lock']
    pipeline_fn = deps['pipeline_fn']

    @task_bp.route('/api/start', methods=['POST'])
    def start_analysis():
        data = request.json or {}
        paper_text = data.get('paper', '').strip()
        auto_mode = data.get('auto_mode', True)
        sources = data.get('sources', None)
        threshold = data.get('threshold', 60)
        cnki_url = data.get('cnki_url', '').strip()
        cnki_html = data.get('cnki_html', '').strip()
        cnki_papers_upload = data.get('cnki_papers', [])

        if not paper_text:
            return jsonify({"error": "论文内容不能为空"}), 400

        with task_lock:
            deps['task_counter'] += 1
            task_id = f"task_{deps['task_counter']}"

        task_store[task_id] = {
            "status": "processing", "auto_mode": auto_mode, "paused": False,
            "current_agent": 0, "conversation": [],
            "agents_status": {f"agent{i}": {"status": "待命", "progress": 0} for i in range(1, 7)},
            "agent_results": {}, "final_report": None, "docx_path": None,
            "sources": sources or list(ALL_SOURCES.keys()), "real_papers": None,
            "threshold": threshold, "cnki_url": cnki_url, "cnki_html": cnki_html, "cnki_papers": cnki_papers_upload,
        }

        _add_message(task_store, task_id, _system_msg(f"论文分析任务已创建，{'自动' if auto_mode else '手动'}流转模式，相似度阈值{threshold}%", "🚀"))

        thread = threading.Thread(target=pipeline_fn, args=(task_id, paper_text, auto_mode, threshold), daemon=True)
        thread.start()
        return jsonify({"task_id": task_id, "status": "started"})

    @task_bp.route('/api/status/<task_id>', methods=['GET'])
    def get_status(task_id):
        task = task_store.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404
        since = request.args.get('since', 0, type=int)
        conversation = task.get("conversation", [])
        return jsonify({
            "task_id": task_id, "status": task["status"],
            "auto_mode": task.get("auto_mode", True), "paused": task.get("paused", False),
            "needs_confirm": task.get("needs_confirm", False),
            "current_agent": task.get("current_agent", 0),
            "agents_status": task.get("agents_status", {}),
            "conversation": conversation[since:], "total_messages": len(conversation),
            "report": task.get("final_report"), "docx_ready": bool(task.get("docx_path")),
            "cnki_task_id": task.get("cnki_task_id"),
            "batch_progress": task.get("batch_progress", ""),
            "batch_pct": task.get("batch_pct", 0),
        })

    @task_bp.route('/api/stream/<task_id>', methods=['GET'])
    def stream(task_id):
        q = sse_broker.subscribe(task_id)

        def generate():
            try:
                while True:
                    msg = q.get(timeout=30)
                    yield f"event: {msg['event']}\n"
                    yield f"data: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                    if msg['event'] in ('task_complete', 'task_error'):
                        break
            except queue_module.Empty:
                yield "event: heartbeat\ndata: {}\n\n"
            finally:
                sse_broker.unsubscribe(task_id)

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
        )

    @task_bp.route('/api/confirm/<task_id>', methods=['POST'])
    def confirm_agent(task_id):
        task = task_store.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404
        task["paused"] = False
        task["needs_confirm"] = False
        _add_message(task_store, task_id, _system_msg("用户已确认", "▶️"))
        return jsonify({"status": "ok"})

    @task_bp.route('/api/retry/<task_id>', methods=['POST'])
    def retry_agent(task_id):
        task = task_store.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404
        task["retry_requested"] = True
        task["paused"] = False
        task["needs_confirm"] = False
        _add_message(task_store, task_id, _system_msg("用户要求重新处理", "🔄"))
        return jsonify({"status": "ok"})

    app.register_blueprint(task_bp)
