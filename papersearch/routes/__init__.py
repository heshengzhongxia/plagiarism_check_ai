"""
路由层 — 注册所有 API 端点
"""
from flask import Flask


def register_routes(app: Flask, deps: dict) -> None:
    """将各子模块的 Blueprint 注册到 Flask app 上。

    deps 携带共享状态：
        task_store, task_lock, task_counter, REPORTS_DIR,
        AGENTS_CONFIG, sse_broker, pipeline_fn
    """
    from .upload_routes import register_upload_routes
    from .task_routes import register_task_routes
    from .report_routes import register_report_routes
    from .cnki_routes import register_cnki_routes

    register_upload_routes(app, deps)
    register_task_routes(app, deps)
    register_report_routes(app, deps)
    register_cnki_routes(app, deps)
