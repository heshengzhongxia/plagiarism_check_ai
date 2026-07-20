"""
报告与历史相关路由
- GET    /api/report/<task_id>   — 获取报告 JSON
- GET    /api/download/<task_id> — 下载 DOCX 文件
- GET    /api/history            — 列出所有已完成任务
- DELETE /api/history/<task_id>  — 删除指定任务
"""
import os
from flask import Blueprint, jsonify, send_file

report_bp = Blueprint('report', __name__)


def register_report_routes(app, deps):
    task_store = deps['task_store']

    @report_bp.route('/api/report/<task_id>', methods=['GET'])
    def get_report(task_id):
        task = task_store.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404
        return jsonify({
            "task_id": task_id, "report": task.get("final_report", {}),
            "agent_results": task.get("agent_results", {}),
            "conversation": task.get("conversation", []),
            "real_papers": task.get("real_papers"),
            "docx_ready": bool(task.get("docx_path")),
        })

    @report_bp.route('/api/download/<task_id>', methods=['GET'])
    def download_report(task_id):
        task = task_store.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404
        docx_path = task.get("docx_path")
        if not docx_path or not os.path.exists(docx_path):
            return jsonify({"error": "报告文件不存在或尚未生成"}), 404
        return send_file(
            docx_path,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name="查重报告_原论文.docx"
        )

    @report_bp.route('/api/history', methods=['GET'])
    def history():
        """列出所有已完成（非 processing 状态）的任务"""
        items = []
        for tid, t in task_store.items():
            if t.get("status") != "processing":
                items.append({
                    "task_id": tid,
                    "status": t.get("status"),
                    "auto_mode": t.get("auto_mode"),
                    "created_at": t.get("created_at"),
                    "report": t.get("final_report"),
                    "docx_ready": bool(t.get("docx_path")),
                })
        return jsonify({"tasks": items})

    @report_bp.route('/api/history/<task_id>', methods=['DELETE'])
    def delete_history(task_id):
        """从 task_store 中删除指定任务"""
        if task_id not in task_store:
            return jsonify({"error": "任务不存在"}), 404
        del task_store[task_id]
        return jsonify({"status": "ok"})

    app.register_blueprint(report_bp)
