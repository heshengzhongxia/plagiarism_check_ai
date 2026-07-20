"""
六智Agent论文工坊 - 后端服务 v4.0
DAG数据流：agent1→(agent2,agent3,agent6)；agent2→agent3；agent3→(agent4,agent6)；agent4→agent5→agent6
"""
import os
import json
import time
import threading
import sys
import tempfile
import base64 as b64
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

from config import AGENTS_CONFIG
from agents import create_agent
from paper_apis import search_all, ALL_SOURCES
from cnki_spider import cnki_tasks, run_spider, TEMP_DIR as CNKI_TEMP_DIR, HAS_PLAYWRIGHT

app = Flask(__name__, static_folder='.')
CORS(app)

PORT = int(os.environ.get("PAPER_PORT", 5001))
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

task_store = {}
task_counter = 0
task_lock = threading.Lock()


def _add_message(task_id, msg):
    if task_id in task_store:
        task_store[task_id]["conversation"].append(msg)


def _system_msg(message, emoji="⚙️"):
    return {"agent_id": "system", "agent_name": "系统", "emoji": emoji,
            "color": "#7b8ca8", "message": message, "timestamp": time.time()}


# ============================================================
# 文件解析
# ============================================================

def extract_text_from_pdf(filepath):
    """从PDF文件提取文本"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"PDF解析失败: {e}")


def extract_text_from_docx(filepath):
    """从Word文件提取文本"""
    try:
        from docx import Document
        doc = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text.strip()
    except Exception as e:
        raise ValueError(f"Word解析失败: {e}")


def extract_text(filepath, filename):
    """根据文件扩展名自动选择解析方式"""
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(filepath)
    elif ext in ('.docx', '.doc'):
        return extract_text_from_docx(filepath)
    elif ext == '.txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read().strip()
    else:
        raise ValueError(f"不支持的文件格式: {ext}，请上传 PDF / Word / TXT 文件")


# ============================================================
# Routes
# ============================================================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/sources', methods=['GET'])
def get_sources():
    sources = [{"id": sid, "name": info["name"], "desc": info["desc"]}
               for sid, info in ALL_SOURCES.items()]
    return jsonify({"sources": sources})


@app.route('/api/keywords', methods=['POST'])
def extract_keywords_only():
    """
    只跑 agent1 出关键词（复用和流水线完全相同的 Agent1Parser）。
    前端收到关键词 → 用户去知网搜 → 上传PDF → 点「开始比对」→ /api/start。
    """
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


@app.route('/api/start', methods=['POST'])
def start_analysis():
    global task_counter
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
        task_counter += 1
        task_id = f"task_{task_counter}"

    task_store[task_id] = {
        "status": "processing", "auto_mode": auto_mode, "paused": False,
        "current_agent": 0, "conversation": [],
        "agents_status": {f"agent{i}": {"status": "待命", "progress": 0} for i in range(1, 7)},
        "agent_results": {}, "final_report": None, "docx_path": None,
        "sources": sources or list(ALL_SOURCES.keys()), "real_papers": None,
        "threshold": threshold, "cnki_url": cnki_url, "cnki_html": cnki_html, "cnki_papers": cnki_papers_upload,
    }

    _add_message(task_id, _system_msg(f"论文分析任务已创建，{'自动' if auto_mode else '手动'}流转模式，相似度阈值{threshold}%", "🚀"))

    thread = threading.Thread(target=execute_pipeline, args=(task_id, paper_text, auto_mode, threshold), daemon=True)
    thread.start()
    return jsonify({"task_id": task_id, "status": "started"})


@app.route('/api/status/<task_id>', methods=['GET'])
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


@app.route('/api/confirm/<task_id>', methods=['POST'])
def confirm_agent(task_id):
    task = task_store.get(task_id)
    if not task: return jsonify({"error": "任务不存在"}), 404
    task["paused"] = False; task["needs_confirm"] = False
    _add_message(task_id, _system_msg("用户已确认", "▶️"))
    return jsonify({"status": "ok"})


@app.route('/api/retry/<task_id>', methods=['POST'])
def retry_agent(task_id):
    task = task_store.get(task_id)
    if not task: return jsonify({"error": "任务不存在"}), 404
    task["retry_requested"] = True; task["paused"] = False; task["needs_confirm"] = False
    _add_message(task_id, _system_msg("用户要求重新处理", "🔄"))
    return jsonify({"status": "ok"})


@app.route('/api/report/<task_id>', methods=['GET'])
def get_report(task_id):
    task = task_store.get(task_id)
    if not task: return jsonify({"error": "任务不存在"}), 404
    return jsonify({
        "task_id": task_id, "report": task.get("final_report", {}),
        "agent_results": task.get("agent_results", {}),
        "conversation": task.get("conversation", []),
        "real_papers": task.get("real_papers"),
        "docx_ready": bool(task.get("docx_path")),
    })


@app.route('/api/upload', methods=['POST'])
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


@app.route('/api/download/<task_id>', methods=['GET'])
def download_report(task_id):
    task = task_store.get(task_id)
    if not task: return jsonify({"error": "任务不存在"}), 404
    docx_path = task.get("docx_path")
    if not docx_path or not os.path.exists(docx_path):
        return jsonify({"error": "报告文件不存在或尚未生成"}), 404
    return send_file(
        docx_path,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name="查重报告_原论文.docx"
    )


# ============================================================
# CNKI 知网爬取
# ============================================================

@app.route('/api/cnki/start', methods=['POST'])
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


@app.route('/api/cnki/status/<task_id>', methods=['GET'])
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


@app.route('/api/cnki/solve/<task_id>', methods=['POST'])
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


@app.route('/api/cnki/parse', methods=['POST'])
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


@app.route('/api/cnki/download/<task_id>', methods=['GET'])
def cnki_download(task_id):
    """打包下载知网爬取的论文"""
    task = cnki_tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    papers = task.get("papers", [])
    if not papers:
        return jsonify({"error": "无论文可下载"}), 404

    # 打包为zip
    import zipfile, tempfile
    zip_path = os.path.join(tempfile.gettempdir(), f"cnki_{task_id}.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for p in papers:
            fp = p.get("file_path")
            if fp and os.path.exists(fp):
                zf.write(fp, os.path.basename(fp))
    return send_file(zip_path, as_attachment=True,
                     download_name=f"知网论文_{task_id}.zip",
                     mimetype='application/zip')


# ============================================================
# DAG Pipeline
# ============================================================

def execute_pipeline(task_id, paper_text, auto_mode, threshold=60):
    """DAG流水线：每个Agent接收精确的输入数据"""

    # 创建所有Agent
    agents = {}
    for aid in ["agent1","agent2","agent3","agent4","agent5","agent6"]:
        try:
            agents[aid] = create_agent(aid, AGENTS_CONFIG[aid])
        except Exception as e:
            _add_message(task_id, _system_msg(f"Agent {aid} 初始化失败: {e}", "❌"))
            task_store[task_id]["status"] = "error"
            return

    task = task_store.get(task_id)
    agent_results = {}

    # ===== Agent1: 解析论文 =====
    _update(task, "agent1", "运行中", 0)
    _add_message(task_id, _system_msg(f"{agents['agent1'].emoji} {agents['agent1'].name}（{agents['agent1'].role}）开始工作 · 预计 5~15s", "➡️"))
    _add_message(task_id, {"agent_id":"agent1","agent_name":agents['agent1'].name,"emoji":agents['agent1'].emoji,"color":agents['agent1'].color,"message":"正在解析论文...","timestamp":time.time()})

    r1 = agents["agent1"].think(paper_text)
    for m in r1.get("messages", []): _add_message(task_id, m)
    agent_results["agent1"] = r1["result"]
    _update(task, "agent1", "完成", 100)

    keywords = agent_results["agent1"].get("keywords", [])
    user_full_text = agent_results["agent1"].get("full_text", paper_text)

    # ---- 手动确认 ----
    if not auto_mode:
        if _wait_confirm(task_id, "agent1"): return

    # ===== Agent2: 检索论文 ====
    _update(task, "agent2", "运行中", 0)
    _add_message(task_id, _system_msg(f"{agents['agent2'].emoji} {agents['agent2'].name}（{agents['agent2'].role}）开始工作 · 预计 10~20s", "➡️"))

    # 真实API搜索
    sources = task.get("sources", list(ALL_SOURCES.keys()))
    obj = agent_results["agent1"].get("title", "")
    search_kw = [obj] + keywords[:5] if obj else keywords[:5]
    search_kw = [k for k in search_kw if k and len(k) >= 2]

    _add_message(task_id, _system_msg(f"检索: {', '.join(search_kw[:5])}，从 {len(sources)} 个论文库...", "📡"))
    api_result = search_all(search_kw, sources=sources, max_per_source=5)
    task["real_papers"] = api_result
    by_src = ', '.join(f'{ALL_SOURCES.get(s,{}).get("name",s)}:{c}' for s, c in api_result["by_source"].items() if c > 0)
    _add_message(task_id, _system_msg(f"API完成：{api_result['total']} 篇（{by_src}）", "✅"))

    # ---- 知网上传论文（用户F12下载后上传的PDF）----
    cnki_papers_upload = task.get("cnki_papers", []) if task else []
    if cnki_papers_upload:
        api_result["papers"].extend(cnki_papers_upload)
        api_result["total"] += len(cnki_papers_upload)
        api_result["by_source"]["cnki"] = len(cnki_papers_upload)
        _add_message(task_id, _system_msg(
            f"知网上传论文：已加入 {len(cnki_papers_upload)} 篇全文", "✅"
        ))

    # ---- 知网：解析用户粘贴的检索结果页HTML ----
    cnki_html = task.get("cnki_html", "") if task else ""
    if cnki_html:
        _add_message(task_id, _system_msg("正在解析知网检索结果页...", "📚"))
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(cnki_html, 'html.parser')
            cnki_papers = []
            # 找所有论文标题链接
            for a in soup.find_all('a'):
                title = a.get_text(strip=True)
                href = a.get('href', '')
                if title and len(title) > 10:
                    cnki_papers.append({
                        "title": title[:200],
                        "url": href if href else "",
                        "abstract": "",
                        "full_text": title + "。" + (a.find_parent().get_text(strip=True)[:500] if a.find_parent() else ""),
                        "source": "知网CNKI",
                    })

            # 去重
            seen = set()
            unique = []
            for p in cnki_papers:
                key = p["title"][:30]
                if key not in seen:
                    seen.add(key)
                    unique.append(p)

            if unique:
                api_result["papers"].extend(unique[:15])
                api_result["total"] += len(unique[:15])
                api_result["by_source"]["cnki"] = len(unique[:15])
                _add_message(task_id, _system_msg(
                    f"知网解析完成：提取 {len(unique[:15])} 篇论文摘要", "✅"
                ))
            else:
                _add_message(task_id, _system_msg("知网HTML未提取到论文，请确认复制的是检索结果页内容", "⚠️"))
        except Exception as e:
            _add_message(task_id, _system_msg(f"知网解析失败: {e}", "⚠️"))

    r2 = agents["agent2"].think({"keywords": keywords}, context={"real_papers": api_result})
    for m in r2.get("messages", []): _add_message(task_id, m)
    agent_results["agent2"] = r2["result"]
    _update(task, "agent2", "完成", 100)

    crawled_papers = agent_results["agent2"].get("papers", [])

    if not auto_mode:
        if _wait_confirm(task_id, "agent2"): return

    # ===== Agent3: 逐句查重比对 ====
    _update(task, "agent3", "运行中", 0)
    _add_message(task_id, _system_msg(f"{agents['agent3'].emoji} {agents['agent3'].name}（{agents['agent3'].role}）开始工作 · 预计 5~15s", "➡️"))

    agent3_input = {
        "user_full_text": user_full_text,
        "crawled_papers": crawled_papers,
        "threshold": threshold,
    }
    r3 = agents["agent3"].think(agent3_input)
    for m in r3.get("messages", []): _add_message(task_id, m)
    agent_results["agent3"] = r3["result"]
    _update(task, "agent3", "完成", 100)

    matches = agent_results["agent3"].get("matches", [])
    total_matches = len(matches)

    if total_matches == 0:
        _add_message(task_id, _system_msg("未发现重复句子，跳过后续分析", "✅"))
        agent_results["agent4"] = {"sentence_directions": [], "overall_suggestions": []}
        agent_results["agent5"] = {"modifications": [], "overall_suggestions": []}
        agent_results["agent6"] = {"summary": "未检测到重复", "total_matches": 0, "docx_path": None}
        task["agent_results"] = agent_results
        task["status"] = "completed"
        return

    # 释放爬取论文全文（已比对完毕，不再需要）
    agent_results["agent2"]["papers"] = [
        {"title": p.get("title",""), "url": p.get("url",""), "source": p.get("source","")}
        for p in agent_results["agent2"].get("papers", [])
    ]
    task["real_papers"] = None

    _all_matches = matches
    # 清空 task 内的引用（省内存，matches 太大）
    task["agent_results"]["agent3"]["matches"] = []

    BATCH_SIZE = 10
    total_batches = (total_matches + BATCH_SIZE - 1) // BATCH_SIZE
    _add_message(task_id, _system_msg(f"共 {total_matches} 处重复，分 {total_batches} 批处理（每批 {BATCH_SIZE} 条）", "📦"))

    all_directions = []
    all_modifications = []
    all_overall_suggestions = []

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total_matches)
        batch_num = batch_idx + 1
        progress_pct = int(batch_idx / max(total_batches, 1) * 100)

        batch_matches = _all_matches[start:end]

        _add_message(task_id, _system_msg(
            f"📦 批次 {batch_num}/{total_batches}（{start+1}-{end}）开始处理 · 进度 {progress_pct}%"
        ))
        task["batch_progress"] = f"{batch_num}/{total_batches}"
        task["batch_pct"] = progress_pct

        # ---- Agent4 ----
        _update(task, "agent4", "运行中", progress_pct)
        _add_message(task_id, {"agent_id":"agent4","agent_name":agents['agent4'].name,"emoji":agents['agent4'].emoji,"color":agents['agent4'].color,"message":f"批次{batch_num}：分析 {len(batch_matches)} 句修改方向...","timestamp":time.time()})
        r4 = agents["agent4"].think({"matches": batch_matches})
        for m in r4.get("messages", []): _add_message(task_id, m)
        _update(task, "agent4", "完成", progress_pct)

        batch_dirs = r4["result"].get("sentence_directions", [])
        batch_sug = r4["result"].get("overall_suggestions", [])
        all_directions.extend(batch_dirs)
        if batch_sug:
            all_overall_suggestions = batch_sug

        if not auto_mode:
            if _wait_confirm(task_id, "agent4"): return

        # ---- Agent5 ----
        _update(task, "agent5", "运行中", progress_pct)
        _add_message(task_id, {"agent_id":"agent5","agent_name":agents['agent5'].name,"emoji":agents['agent5'].emoji,"color":agents['agent5'].color,"message":f"批次{batch_num}：生成 {len(batch_dirs)} 句修改方案...","timestamp":time.time()})
        r5 = agents["agent5"].think({
            "sentence_directions": batch_dirs,
            "overall_suggestions": batch_sug,
        })
        for m in r5.get("messages", []): _add_message(task_id, m)
        _update(task, "agent5", "完成", progress_pct)

        batch_mods = r5["result"].get("modifications", [])
        all_modifications.extend(batch_mods)

        _add_message(task_id, _system_msg(
            f"✅ 批次 {batch_num}/{total_batches} 完成"
        ))
        task["batch_progress"] = f"{batch_num}/{total_batches}"
        task["batch_pct"] = int(batch_num / total_batches * 100)

    # ---- Agent6: 汇总生成报告 ----
    _update(task, "agent6", "运行中", 95)
    _add_message(task_id, _system_msg(f"{agents['agent6'].emoji} {agents['agent6'].name} 汇总 {total_matches} 条匹配，生成报告 · 预计 5~10s", "➡️"))

    agent6_input = {
        "user_full_text": user_full_text,
        "matches": _all_matches,
        "modifications": all_modifications,
        "overall_suggestions": all_overall_suggestions,
        "aigc_rate": agent_results["agent1"].get("aigc_rate", 0),
        "aigc_analysis": agent_results["agent1"].get("aigc_analysis", ""),
    }
    r6 = agents["agent6"].think(agent6_input, context={"report_dir": REPORTS_DIR})
    for m in r6.get("messages", []): _add_message(task_id, m)
    agent_results["agent6"] = r6["result"]
    _update(task, "agent6", "完成", 100)

    # 保存结果
    task["agent_results"] = agent_results
    task["final_report"] = agent_results["agent6"]
    task["docx_path"] = agent_results["agent6"].get("docx_path")
    task["status"] = "completed"
    task["current_agent"] = 0
    _add_message(task_id, _system_msg("所有Agent协作完成！查重报告已生成。", "✅"))


def _update(task, agent_id, status, progress):
    if task:
        task["agents_status"][agent_id] = {"status": status, "progress": progress}
        # Update current_agent based on agent_id
        nums = {"agent1":1,"agent2":2,"agent3":3,"agent4":4,"agent5":5,"agent6":6}
        task["current_agent"] = nums.get(agent_id, 0)


def _wait_confirm(task_id, agent_id):
    """手动模式下等待用户确认"""
    task_store[task_id]["paused"] = True
    task_store[task_id]["needs_confirm"] = True
    _add_message(task_id, {"agent_id":"system","agent_name":"系统","emoji":"⏸️","color":"#f0c060",
        "message":f"手动模式：请检查 {agent_id} 的结果，点击确认继续。","timestamp":time.time(),
        "needs_confirm":True})
    while True:
        time.sleep(0.5)
        t = task_store.get(task_id)
        if not t or not t.get("paused"): break
        if t.get("status") == "cancelled": return True
    task_store[task_id]["needs_confirm"] = False
    return False


# ============================================================
if __name__ == '__main__':
    print("=" * 55)
    print("  六智Agent论文工坊 - 后端服务 v4.0")
    print("  DAG数据流 · 语义查重 · CNKI · Docx报告")
    print(f"  访问地址: http://127.0.0.1:{PORT}")
    print("=" * 55)

    # 启动临时文件清理（每小时清理超过24小时的知网文件）
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
                        except:
                            pass

    threading.Thread(target=_cleanup_loop, daemon=True).start()

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    app.run(debug=DEBUG, host='0.0.0.0', port=PORT)
