"""
六智Agent论文工坊 - 后端服务 v4.0
DAG数据流：agent1→(agent2,agent3,agent6)；agent2→agent3；agent3→(agent4,agent6)；agent4→agent5→agent6
"""
import os
import json
import time
import threading
import sys
from flask import Flask, send_from_directory
from flask_cors import CORS

from config import AGENTS_CONFIG
from agents import create_agent
from services.paper_api import search_all, ALL_SOURCES
from cnki_spider import TEMP_DIR as CNKI_TEMP_DIR
from routes import register_routes

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
# Routes
# ============================================================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


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
# 注册所有 API 路由（拆分到 routes/ 子模块）
# ============================================================
_deps = {
    "task_store": task_store,
    "task_lock": task_lock,
    "task_counter": task_counter,
    "REPORTS_DIR": REPORTS_DIR,
    "AGENTS_CONFIG": AGENTS_CONFIG,
    "sse_broker": None,  # task_routes imports the global directly
    "pipeline_fn": execute_pipeline,
}
register_routes(app, _deps)

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
