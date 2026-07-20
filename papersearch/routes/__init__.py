"""
路由层 — 注册所有 API 端点
"""
from flask import Flask


def register_routes(app: Flask, task_manager, sse_broker, agents_config: dict,
                    reports_dir: str) -> None:
    """将各子模块的 Blueprint 注册到 Flask app 上。

    Args:
        app: Flask 应用实例。
        task_manager: TaskManager 实例（持久化任务状态）。
        sse_broker: SSEBroker 全局单例（实时事件推送）。
        agents_config: Agent 配置字典（AGENTS_CONFIG）。
        reports_dir: 报告输出目录。
    """
    from .upload_routes import register_upload_routes
    from .task_routes import register_task_routes
    from .report_routes import register_report_routes
    from .cnki_routes import register_cnki_routes
    from engine.pipeline import execute_pipeline, _runtime_state

    register_upload_routes(app, agents_config)
    register_task_routes(app, task_manager, sse_broker, agents_config,
                         execute_pipeline, _runtime_state, reports_dir)
    register_report_routes(app, task_manager)
    register_cnki_routes(app)
