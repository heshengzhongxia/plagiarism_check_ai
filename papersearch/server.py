"""
六智Agent论文工坊 - 后端服务（向后兼容入口）

新代码请使用 app.py 作为入口。
"""
from app import app  # noqa: F401

if __name__ == '__main__':
    from app import app as _app
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    from config import PAPER_PORT
    _app.run(debug=False, host='0.0.0.0', port=PAPER_PORT)
