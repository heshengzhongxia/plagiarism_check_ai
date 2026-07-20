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
from services.message_utils import system_msg

task_bp = Blueprint('task', __name__)

# 简单的任务计数器（用于生成 task_id）
_task_counter = [0]


def register_task_routes(app, task_manager, sse_broker, agents_config,
                         pipeline_fn, runtime_state: dict, reports_dir: str):
    """注册任务相关路由。

    Args:
        app: Flask 应用实例。
        task_manager: TaskManager 持久化实例。
        sse_broker: SSE 事件代理全局单例。
        agents_config: Agent 配置。
        pipeline_fn: 流水线执行函数（来自 engine.pipeline）。
        runtime_state: 运行时瞬态状态字典（暂停/确认等）。
        reports_dir: 报告输出目录。
    """

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

        _task_counter[0] += 1
        task_id = f"task_{_task_counter[0]}"

        # 持久化任务
        task_manager.create_task(task_id, {
            "auto_mode": auto_mode,
            "threshold": threshold,
        })

        # 初始化运行时状态（瞬态字段）
        runtime_state[task_id] = {
            "paused": False,
            "needs_confirm": False,
            "current_agent": 0,
            "sources": sources or list(ALL_SOURCES.keys()),
            "cnki_url": cnki_url,
            "cnki_html": cnki_html,
            "cnki_papers": cnki_papers_upload,
            "real_papers": None,
        }

        task_manager.add_message(task_id, system_msg(
            f"论文分析任务已创建，{'自动' if auto_mode else '手动'}流转模式，相似度阈值{threshold}%", "🚀"))

        sse_broker.publish(task_id, 'task_start', {'task_id': task_id})

        thread = threading.Thread(
            target=pipeline_fn,
            args=(task_id, paper_text, auto_mode, threshold,
                  task_manager, sse_broker, agents_config, reports_dir),
            daemon=True,
        )
        thread.start()
        return jsonify({"task_id": task_id, "status": "started"})

    @task_bp.route('/api/status/<task_id>', methods=['GET'])
    def get_status(task_id):
        task = task_manager.get_status(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404

        rt = runtime_state.get(task_id, {})

        since = request.args.get('since', 0, type=int)
        messages = task_manager.get_messages(task_id, since)
        total_messages = len(task_manager.get_messages(task_id, 0))

        return jsonify({
            "task_id": task_id,
            "status": task.get("status"),
            "auto_mode": task.get("auto_mode"),
            "paused": rt.get("paused", False),
            "needs_confirm": rt.get("needs_confirm", False),
            "current_agent": rt.get("current_agent", 0),
            "agents_status": task.get("agents_status", {}),
            "conversation": messages,
            "total_messages": total_messages,
            "report": task.get("final_report"),
            "docx_ready": bool(task.get("docx_path")),
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
        if task_id not in runtime_state:
            return jsonify({"error": "任务不存在"}), 404
        runtime_state[task_id]["paused"] = False
        runtime_state[task_id]["needs_confirm"] = False
        task_manager.add_message(task_id, system_msg("用户已确认", "▶️"))
        return jsonify({"status": "ok"})

    @task_bp.route('/api/retry/<task_id>', methods=['POST'])
    def retry_agent(task_id):
        if task_id not in runtime_state:
            return jsonify({"error": "任务不存在"}), 404
        runtime_state[task_id]["retry_requested"] = True
        runtime_state[task_id]["paused"] = False
        runtime_state[task_id]["needs_confirm"] = False
        task_manager.add_message(task_id, system_msg("用户要求重新处理", "🔄"))
        return jsonify({"status": "ok"})

    app.register_blueprint(task_bp)
