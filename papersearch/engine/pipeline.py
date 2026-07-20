"""
DAG流水线编排器 — 6个Agent协作完成论文查重分析

DAG数据流：agent1→(agent2,agent3,agent6)；agent2→agent3；agent3→(agent4,agent6)；agent4→agent5→agent6
"""
import json
import time
import threading

from services.message_utils import system_msg
from services.paper_api import search_all, ALL_SOURCES

# ---------------------------------------------------------------------------
# 运行时瞬态状态（确认/暂停/重试等 — 不需要持久化到 SQLite）
# ---------------------------------------------------------------------------
_runtime_state: dict[str, dict] = {}
_runtime_lock = threading.Lock()


def _get_runtime(task_id: str) -> dict:
    """获取或创建任务的运行时状态"""
    with _runtime_lock:
        if task_id not in _runtime_state:
            _runtime_state[task_id] = {}
        return _runtime_state[task_id]


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _update(task_id, agent_id, status, progress,
            task_manager, sse_broker, agents_config):
    """更新Agent状态并推送SSE事件"""
    task_manager.update_agent_status(task_id, agent_id, status, progress)

    rt = _get_runtime(task_id)
    nums = {"agent1": 1, "agent2": 2, "agent3": 3, "agent4": 4, "agent5": 5, "agent6": 6}
    rt["current_agent"] = nums.get(agent_id, 0)

    cfg = agents_config.get(agent_id, {})

    if status == "运行中":
        sse_broker.publish(task_id, 'agent_start', {
            'agent_id': agent_id,
            'agent_name': cfg.get('name', agent_id),
            'emoji': cfg.get('emoji', ''),
            'color': cfg.get('color', ''),
        })
    elif status == "完成":
        sse_broker.publish(task_id, 'agent_done', {'agent_id': agent_id})


def _wait_confirm(task_id, agent_id, task_manager, sse_broker):
    """手动模式下等待用户确认"""
    rt = _get_runtime(task_id)
    rt["paused"] = True
    rt["needs_confirm"] = True

    task_manager.add_message(task_id, {
        "agent_id": "system", "agent_name": "系统", "emoji": "⏸️",
        "color": "#f0c060",
        "message": f"手动模式：请检查 {agent_id} 的结果，点击确认继续。",
        "timestamp": time.time(),
        "needs_confirm": True,
    })

    sse_broker.publish(task_id, 'task_paused', {})

    while True:
        time.sleep(0.5)
        rt = _get_runtime(task_id)
        if not rt.get("paused"):
            break
        status = task_manager.get_status(task_id)
        if status and status.get("status") == "cancelled":
            return True

    rt["needs_confirm"] = False
    return False


# ---------------------------------------------------------------------------
# 主流水线
# ---------------------------------------------------------------------------

def execute_pipeline(task_id, paper_text, auto_mode, threshold,
                     task_manager, sse_broker, agents_config, reports_dir):
    """DAG流水线：每个Agent接收精确的输入数据"""

    from agents import create_agent

    # 创建所有Agent
    agents = {}
    for aid in ["agent1", "agent2", "agent3", "agent4", "agent5", "agent6"]:
        try:
            agents[aid] = create_agent(aid, agents_config[aid])
        except Exception as e:
            task_manager.add_message(task_id, system_msg(f"Agent {aid} 初始化失败: {e}", "❌"))
            task_manager.update_task(task_id, status="error")
            sse_broker.publish(task_id, 'task_error', {'error': f"Agent {aid} 初始化失败: {e}"})
            return

    rt = _get_runtime(task_id)
    agent_results = {}

    # ===== Agent1: 解析论文 =====
    _update(task_id, "agent1", "运行中", 0, task_manager, sse_broker, agents_config)
    task_manager.add_message(task_id, system_msg(
        f"{agents['agent1'].emoji} {agents['agent1'].name}（{agents['agent1'].role}）开始工作 · 预计 5~15s", "➡️"))
    task_manager.add_message(task_id, {
        "agent_id": "agent1", "agent_name": agents['agent1'].name,
        "emoji": agents['agent1'].emoji, "color": agents['agent1'].color,
        "message": "正在解析论文...", "timestamp": time.time(),
    })
    sse_broker.publish(task_id, 'agent_msg', {
        "agent_id": "agent1", "agent_name": agents['agent1'].name,
        "emoji": agents['agent1'].emoji, "color": agents['agent1'].color,
        "message": "正在解析论文...", "timestamp": time.time(),
    })

    try:
        r1 = agents["agent1"].think(paper_text)
    except Exception as e:
        task_manager.add_message(task_id, system_msg(f"Agent1 执行失败: {e}", "❌"))
        task_manager.update_task(task_id, status="error")
        sse_broker.publish(task_id, 'task_error', {'error': f"Agent1 执行失败: {e}"})
        return

    for m in r1.get("messages", []):
        task_manager.add_message(task_id, m)
        sse_broker.publish(task_id, 'agent_msg', m)
    agent_results["agent1"] = r1["result"]
    _update(task_id, "agent1", "完成", 100, task_manager, sse_broker, agents_config)

    keywords = agent_results["agent1"].get("keywords", [])
    user_full_text = agent_results["agent1"].get("full_text", paper_text)

    # ---- 手动确认 ----
    if not auto_mode:
        if _wait_confirm(task_id, "agent1", task_manager, sse_broker):
            return

    # ===== Agent2: 检索论文 =====
    _update(task_id, "agent2", "运行中", 0, task_manager, sse_broker, agents_config)
    task_manager.add_message(task_id, system_msg(
        f"{agents['agent2'].emoji} {agents['agent2'].name}（{agents['agent2'].role}）开始工作 · 预计 10~20s", "➡️"))

    # 真实API搜索
    sources = rt.get("sources", list(ALL_SOURCES.keys()))
    obj = agent_results["agent1"].get("title", "")
    search_kw = [obj] + keywords[:5] if obj else keywords[:5]
    search_kw = [k for k in search_kw if k and len(k) >= 2]

    task_manager.add_message(task_id, system_msg(
        f"检索: {', '.join(search_kw[:5])}，从 {len(sources)} 个论文库...", "📡"))
    api_result = search_all(search_kw, sources=sources, max_per_source=5)
    rt["real_papers"] = api_result
    by_src = ', '.join(
        f'{ALL_SOURCES.get(s, {}).get("name", s)}:{c}'
        for s, c in api_result["by_source"].items() if c > 0
    )
    task_manager.add_message(task_id, system_msg(f"API完成：{api_result['total']} 篇（{by_src}）", "✅"))

    # ---- 知网上传论文（用户F12下载后上传的PDF）----
    cnki_papers_upload = rt.get("cnki_papers", [])
    if cnki_papers_upload:
        api_result["papers"].extend(cnki_papers_upload)
        api_result["total"] += len(cnki_papers_upload)
        api_result["by_source"]["cnki"] = len(cnki_papers_upload)
        task_manager.add_message(task_id, system_msg(
            f"知网上传论文：已加入 {len(cnki_papers_upload)} 篇全文", "✅"))

    # ---- 知网：解析用户粘贴的检索结果页HTML ----
    cnki_html = rt.get("cnki_html", "")
    if cnki_html:
        task_manager.add_message(task_id, system_msg("正在解析知网检索结果页...", "📚"))
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(cnki_html, 'html.parser')
            cnki_papers = []
            for a in soup.find_all('a'):
                title = a.get_text(strip=True)
                href = a.get('href', '')
                if title and len(title) > 10:
                    cnki_papers.append({
                        "title": title[:200],
                        "url": href if href else "",
                        "abstract": "",
                        "full_text": title + "。" + (
                            a.find_parent().get_text(strip=True)[:500] if a.find_parent() else ""),
                        "source": "知网CNKI",
                    })

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
                task_manager.add_message(task_id, system_msg(
                    f"知网解析完成：提取 {len(unique[:15])} 篇论文摘要", "✅"))
            else:
                task_manager.add_message(task_id, system_msg(
                    "知网HTML未提取到论文，请确认复制的是检索结果页内容", "⚠️"))
        except Exception as e:
            task_manager.add_message(task_id, system_msg(f"知网解析失败: {e}", "⚠️"))

    try:
        r2 = agents["agent2"].think({"keywords": keywords}, context={"real_papers": api_result})
    except Exception as e:
        task_manager.add_message(task_id, system_msg(f"Agent2 执行失败: {e}", "❌"))
        task_manager.update_task(task_id, status="error")
        sse_broker.publish(task_id, 'task_error', {'error': f"Agent2 执行失败: {e}"})
        return

    for m in r2.get("messages", []):
        task_manager.add_message(task_id, m)
        sse_broker.publish(task_id, 'agent_msg', m)
    agent_results["agent2"] = r2["result"]
    _update(task_id, "agent2", "完成", 100, task_manager, sse_broker, agents_config)

    crawled_papers = agent_results["agent2"].get("papers", [])

    if not auto_mode:
        if _wait_confirm(task_id, "agent2", task_manager, sse_broker):
            return

    # ===== Agent3: 逐句查重比对 =====
    _update(task_id, "agent3", "运行中", 0, task_manager, sse_broker, agents_config)
    task_manager.add_message(task_id, system_msg(
        f"{agents['agent3'].emoji} {agents['agent3'].name}（{agents['agent3'].role}）开始工作 · 预计 5~15s", "➡️"))

    agent3_input = {
        "user_full_text": user_full_text,
        "crawled_papers": crawled_papers,
        "threshold": threshold,
    }
    try:
        r3 = agents["agent3"].think(agent3_input)
    except Exception as e:
        task_manager.add_message(task_id, system_msg(f"Agent3 执行失败: {e}", "❌"))
        task_manager.update_task(task_id, status="error")
        sse_broker.publish(task_id, 'task_error', {'error': f"Agent3 执行失败: {e}"})
        return

    for m in r3.get("messages", []):
        task_manager.add_message(task_id, m)
        sse_broker.publish(task_id, 'agent_msg', m)
    agent_results["agent3"] = r3["result"]
    _update(task_id, "agent3", "完成", 100, task_manager, sse_broker, agents_config)

    matches = agent_results["agent3"].get("matches", [])
    total_matches = len(matches)

    if total_matches == 0:
        task_manager.add_message(task_id, system_msg("未发现重复句子，跳过后续分析", "✅"))
        agent_results["agent4"] = {"sentence_directions": [], "overall_suggestions": []}
        agent_results["agent5"] = {"modifications": [], "overall_suggestions": []}
        agent_results["agent6"] = {"summary": "未检测到重复", "total_matches": 0, "docx_path": None}
        task_manager.update_task(
            task_id,
            agent_results=json.dumps(agent_results, ensure_ascii=False),
            status="completed",
        )
        task_manager.set_report(task_id, agent_results["agent6"])
        sse_broker.publish(task_id, 'task_complete', {
            'report': agent_results["agent6"],
            'docx_ready': False,
        })
        return

    # 释放爬取论文全文（已比对完毕，不再需要）
    agent_results["agent2"]["papers"] = [
        {"title": p.get("title", ""), "url": p.get("url", ""), "source": p.get("source", "")}
        for p in agent_results["agent2"].get("papers", [])
    ]
    rt["real_papers"] = None

    _all_matches = matches
    # 清空 agent_results 内的引用（省内存，matches 太大）
    agent_results["agent3"]["matches"] = []

    from config import BATCH_SIZE
    total_batches = (total_matches + BATCH_SIZE - 1) // BATCH_SIZE
    task_manager.add_message(task_id, system_msg(
        f"共 {total_matches} 处重复，分 {total_batches} 批处理（每批 {BATCH_SIZE} 条）", "📦"))

    all_directions = []
    all_modifications = []
    all_overall_suggestions = []

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total_matches)
        batch_num = batch_idx + 1
        progress_pct = int(batch_idx / max(total_batches, 1) * 100)

        batch_matches = _all_matches[start:end]

        task_manager.add_message(task_id, system_msg(
            f"📦 批次 {batch_num}/{total_batches}（{start+1}-{end}）开始处理 · 进度 {progress_pct}%"
        ))
        task_manager.update_task(task_id,
                                 batch_progress=f"{batch_num}/{total_batches}",
                                 batch_pct=progress_pct)
        sse_broker.publish(task_id, 'task_progress', {
            'batch': f"{batch_num}/{total_batches}",
            'pct': progress_pct,
        })

        # ---- Agent4 ----
        _update(task_id, "agent4", "运行中", progress_pct, task_manager, sse_broker, agents_config)
        task_manager.add_message(task_id, {
            "agent_id": "agent4", "agent_name": agents['agent4'].name,
            "emoji": agents['agent4'].emoji, "color": agents['agent4'].color,
            "message": f"批次{batch_num}：分析 {len(batch_matches)} 句修改方向...",
            "timestamp": time.time(),
        })
        sse_broker.publish(task_id, 'agent_msg', {
            "agent_id": "agent4", "agent_name": agents['agent4'].name,
            "emoji": agents['agent4'].emoji, "color": agents['agent4'].color,
            "message": f"批次{batch_num}：分析 {len(batch_matches)} 句修改方向...",
            "timestamp": time.time(),
        })

        try:
            r4 = agents["agent4"].think({"matches": batch_matches})
        except Exception as e:
            task_manager.add_message(task_id, system_msg(f"Agent4 批次{batch_num}执行失败: {e}", "❌"))
            sse_broker.publish(task_id, 'agent_error', {'agent_id': 'agent4', 'error': str(e)})
            continue

        for m in r4.get("messages", []):
            task_manager.add_message(task_id, m)
            sse_broker.publish(task_id, 'agent_msg', m)
        _update(task_id, "agent4", "完成", progress_pct, task_manager, sse_broker, agents_config)

        batch_dirs = r4["result"].get("sentence_directions", [])
        batch_sug = r4["result"].get("overall_suggestions", [])
        all_directions.extend(batch_dirs)
        if batch_sug:
            all_overall_suggestions = batch_sug

        if not auto_mode:
            if _wait_confirm(task_id, "agent4", task_manager, sse_broker):
                return

        # ---- Agent5 ----
        _update(task_id, "agent5", "运行中", progress_pct, task_manager, sse_broker, agents_config)
        task_manager.add_message(task_id, {
            "agent_id": "agent5", "agent_name": agents['agent5'].name,
            "emoji": agents['agent5'].emoji, "color": agents['agent5'].color,
            "message": f"批次{batch_num}：生成 {len(batch_dirs)} 句修改方案...",
            "timestamp": time.time(),
        })
        sse_broker.publish(task_id, 'agent_msg', {
            "agent_id": "agent5", "agent_name": agents['agent5'].name,
            "emoji": agents['agent5'].emoji, "color": agents['agent5'].color,
            "message": f"批次{batch_num}：生成 {len(batch_dirs)} 句修改方案...",
            "timestamp": time.time(),
        })

        try:
            r5 = agents["agent5"].think({
                "sentence_directions": batch_dirs,
                "overall_suggestions": batch_sug,
            })
        except Exception as e:
            task_manager.add_message(task_id, system_msg(f"Agent5 批次{batch_num}执行失败: {e}", "❌"))
            sse_broker.publish(task_id, 'agent_error', {'agent_id': 'agent5', 'error': str(e)})
            continue

        for m in r5.get("messages", []):
            task_manager.add_message(task_id, m)
            sse_broker.publish(task_id, 'agent_msg', m)
        _update(task_id, "agent5", "完成", progress_pct, task_manager, sse_broker, agents_config)

        batch_mods = r5["result"].get("modifications", [])
        all_modifications.extend(batch_mods)

        task_manager.add_message(task_id, system_msg(
            f"✅ 批次 {batch_num}/{total_batches} 完成"
        ))
        task_manager.update_task(task_id,
                                 batch_progress=f"{batch_num}/{total_batches}",
                                 batch_pct=int(batch_num / total_batches * 100))

    # ---- Agent6: 汇总生成报告 ----
    _update(task_id, "agent6", "运行中", 95, task_manager, sse_broker, agents_config)
    task_manager.add_message(task_id, system_msg(
        f"{agents['agent6'].emoji} {agents['agent6'].name} 汇总 {total_matches} 条匹配，生成报告 · 预计 5~10s", "➡️"))

    agent6_input = {
        "user_full_text": user_full_text,
        "matches": _all_matches,
        "modifications": all_modifications,
        "overall_suggestions": all_overall_suggestions,
        "aigc_rate": agent_results["agent1"].get("aigc_rate", 0),
        "aigc_analysis": agent_results["agent1"].get("aigc_analysis", ""),
    }
    try:
        r6 = agents["agent6"].think(agent6_input, context={"report_dir": reports_dir})
    except Exception as e:
        task_manager.add_message(task_id, system_msg(f"Agent6 执行失败: {e}", "❌"))
        task_manager.update_task(task_id, status="error")
        sse_broker.publish(task_id, 'task_error', {'error': f"Agent6 执行失败: {e}"})
        return

    for m in r6.get("messages", []):
        task_manager.add_message(task_id, m)
        sse_broker.publish(task_id, 'agent_msg', m)
    agent_results["agent6"] = r6["result"]
    _update(task_id, "agent6", "完成", 100, task_manager, sse_broker, agents_config)

    # 保存结果
    docx_path = agent_results["agent6"].get("docx_path")
    task_manager.update_task(
        task_id,
        agent_results=json.dumps(agent_results, ensure_ascii=False),
        status="completed",
    )
    task_manager.set_report(task_id, agent_results["agent6"], docx_path)

    rt["current_agent"] = 0
    task_manager.add_message(task_id, system_msg("所有Agent协作完成！查重报告已生成。", "✅"))
    sse_broker.publish(task_id, 'task_complete', {
        'report': agent_results["agent6"],
        'docx_ready': bool(docx_path),
    })
