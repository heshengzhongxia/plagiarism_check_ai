"""
知网论文爬取模块
使用Playwright模拟人类行为，突破反爬机制。
遇到验证码/登录时暂停，要求用户在网页端手动处理。
下载的PDF存入临时目录，24小时后自动清理。
"""
import os
import time
import json
import base64
import threading
import tempfile
import re

HAS_PLAYWRIGHT = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    pass

TEMP_DIR = os.path.join(tempfile.gettempdir(), "cnki_papers")
os.makedirs(TEMP_DIR, exist_ok=True)

# 全局任务存储（captcha状态、下载进度）
cnki_tasks = {}
cnki_lock = threading.Lock()


def _status(task_id, msg, **kw):
    """更新任务状态"""
    with cnki_lock:
        if task_id not in cnki_tasks:
            cnki_tasks[task_id] = {}
        cnki_tasks[task_id].update({"message": msg, "timestamp": time.time(), **kw})


def run_spider(task_id, cnki_url, max_papers=10):
    """
    主爬取流程，在独立线程中运行。

    Args:
        task_id: 任务ID（用于状态通信）
        cnki_url: 知网检索结果页URL
        max_papers: 最多下载的论文数

    状态更新通过 _status() 写入 cnki_tasks，
    前端通过 /api/cnki/status 轮询。
    """
    if not HAS_PLAYWRIGHT:
        _status(task_id, "Playwright未安装", error=True)
        return

    _status(task_id, "正在启动浏览器...", progress=5)

    try:
        with sync_playwright() as p:
            # 启动浏览器（headless模式，兼容无显示器服务器）
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768},
                locale='zh-CN',
            )
            page = context.new_page()

            # 注入反检测脚本
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                window.chrome = {runtime: {}};
            """)

            _status(task_id, "正在访问知网...", progress=10)
            page.goto(cnki_url, timeout=30000, wait_until='domcontentloaded')
            time.sleep(3)

            # ---- 检测并处理登录/验证 ----
            MAX_RETRIES = 8
            for retry in range(MAX_RETRIES):
                # 1. 先检查是否已到达结果页
                if _is_on_results_page(page):
                    _status(task_id, "已到达检索结果页", progress=25)
                    break

                # 2. 检查是否有验证码
                captcha_img = _detect_captcha(page)
                if captcha_img:
                    _status(task_id, "请完成验证码", need_action="captcha",
                            captcha_image=captcha_img)
                    answer = _wait_user_captcha(task_id, timeout=60)
                    if answer:
                        _fill_captcha(page, answer)
                        _status(task_id, "验证码已提交，等待页面跳转...", progress=20)
                        time.sleep(3)
                        continue
                    else:
                        _status(task_id, "验证码超时", progress=100, error=True)
                        browser.close()
                        return

                # 3. 检查是否有登录表单
                login_info = _detect_login_form(page)
                if login_info:
                    _status(task_id, "检测到学校登录页",
                            need_action="login",
                            screenshot=login_info.get("screenshot"))
                    creds = _wait_user_credentials(task_id, timeout=120)
                    if creds:
                        _fill_login_form(page, creds.get("username", ""), creds.get("password", ""))
                        _status(task_id, "登录信息已提交，等待跳转...", progress=20)
                        time.sleep(5)
                        # 登录后可能重定向到校内主页（不是知网）
                        if not _is_on_results_page(page):
                            # 让用户手动在校内主页找到知网入口
                            _status(task_id,
                                    "登录成功但未到达知网（当前可能是校内主页）。"
                                    "请在校内主页中找到知网入口，进入知网检索结果页后，把该URL粘贴回来。",
                                    need_action="manual_nav",
                                    screenshot=_screenshot(page))
                            new_url = _wait_user_url(task_id, timeout=180)
                            if new_url:
                                page.goto(new_url, timeout=30000, wait_until='domcontentloaded')
                                time.sleep(3)
                        continue
                    else:
                        _status(task_id, "登录超时", progress=100, error=True)
                        browser.close()
                        return

                # 4. 已登录但不在知网（如校内主页），提示用户手动导航
                if retry >= 2 and not _is_on_results_page(page) and not _detect_login_form(page):
                    _status(task_id,
                            "当前不在知网检索结果页。请手动导航到知网检索结果页，然后粘贴该URL。",
                            need_action="manual_nav",
                            screenshot=_screenshot(page))
                    new_url = _wait_user_url(task_id, timeout=180)
                    if new_url:
                        page.goto(new_url, timeout=30000, wait_until='domcontentloaded')
                        time.sleep(3)
                    else:
                        _status(task_id, "等待导航超时", progress=100, error=True)
                        browser.close()
                        return

                time.sleep(2)

            if retry == MAX_RETRIES - 1 and not _is_on_results_page(page):
                _status(task_id, "无法到达检索结果页。请检查URL是否正确，以及是否在校内网络环境。",
                        error=True, progress=100)
                browser.close()
                return

            # ---- 收集论文链接 ----
            _status(task_id, "正在收集论文链接...", progress=30)
            paper_links = _collect_paper_links(page, max_papers)
            total = len(paper_links)
            _status(task_id, f"找到 {total} 篇论文", progress=40, total=total)

            if total == 0:
                _status(task_id, "未找到论文链接。请确认URL是知网检索结果页，且在学校内网环境。", error=True, progress=100)
                browser.close()
                return

            # ---- 逐篇下载 ----
            downloaded = []
            for i, link in enumerate(paper_links):
                _status(task_id, f"下载中 ({i+1}/{total})...", progress=40 + int(50 * (i+1) / total),
                        current=i+1, total=total)

                pdf_path = _download_paper(page, context, link, f"cnki_{task_id}_{i}")
                if pdf_path:
                    text = extract_text_from_pdf(pdf_path)
                    downloaded.append({
                        "title": os.path.basename(pdf_path).replace(".pdf", ""),
                        "full_text": text,
                        "url": link,
                        "source": "知网CNKI",
                        "file_path": pdf_path,
                    })
                time.sleep(3 + (i % 4) * 1.5)  # 随机间隔3-6秒

            browser.close()

            _status(task_id, f"完成：下载 {len(downloaded)}/{total} 篇",
                    progress=100, completed=True, papers=downloaded)

    except Exception as e:
        _status(task_id, f"异常: {str(e)[:200]}", error=True)
        try:
            browser.close()
        except:
            pass


# ============================================================
# 辅助函数
# ============================================================

def _screenshot(page):
    """截取当前页面，返回base64"""
    img = page.screenshot(full_page=False)
    return base64.b64encode(img).decode('utf-8')


def _detect_login_form(page):
    """检测页面是否有登录表单（学校统一认证/知网登录等），有则返回表单信息"""
    try:
        # 检查是否有密码输入框（最可靠的登录页判断）
        pwd_inputs = page.query_selector_all('input[type="password"]')
        if pwd_inputs and len(pwd_inputs) > 0:
            # 尝试找到用户名输入框
            user_input = None
            for sel in ['input[name="username"]', 'input[name="user"]', 'input[id="username"]',
                         'input[name="uname"]', 'input[type="text"]', 'input[type="email"]']:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    user_input = sel
                    break
            # 尝试找到验证码输入框
            captcha_input = None
            for sel in ['input[name*="captcha"]', 'input[id*="captcha"]', 'input[name*="code"]',
                         'input[name*="check"]']:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    captcha_input = sel
                    break
            return {
                "has_password": True,
                "user_selector": user_input,
                "pwd_selector": 'input[type="password"]',
                "captcha_selector": captcha_input,
                "screenshot": _screenshot(page),
            }
        return None
    except:
        return None


def _fill_login_form(page, username, password):
    """在登录表单中填入账号密码并提交"""
    try:
        # 找用户名框
        for sel in ['input[name="username"]', 'input[name="user"]', 'input[id="username"]',
                     'input[type="text"]', 'input[type="email"]']:
            inp = page.query_selector(sel)
            if inp and inp.is_visible():
                inp.fill(username)
                break
        # 找密码框
        for sel in ['input[type="password"]']:
            inp = page.query_selector(sel)
            if inp and inp.is_visible():
                inp.fill(password)
                break
        # 点击登录按钮
        time.sleep(0.5)
        for sel in ['button[type="submit"]', 'input[type="submit"]', 'button',
                     'a.btn', '.login-btn', '#loginBtn', '[onclick*="login"]']:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                return
        # 没找到按钮就回车
        page.keyboard.press('Enter')
    except:
        page.keyboard.press('Enter')


def _detect_captcha(page):
    """检测页面是否有验证码，有则返回验证码图片bytes"""
    try:
        for sel in ['img[src*="captcha"]', 'img[src*="Captcha"]', 'img[src*="checkcode"]',
                     'img[src*="verify"]', 'img[id*="captcha"]', 'img[class*="captcha"]',
                     '#verificationCodeImg', '.captcha-img img', 'img[src*="code"]',
                     'img[src*="Code"]', 'img[src*="Verification"]']:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el.screenshot()
        return None
    except:
        return None


def _fill_captcha(page, answer):
    """填入验证码并提交"""
    try:
        for sel in ['input[name*="captcha"]', 'input[id*="captcha"]', 'input[name*="code"]',
                     'input[name*="check"]', 'input[class*="captcha"]']:
            inp = page.query_selector(sel)
            if inp and inp.is_visible():
                inp.fill(answer)
                page.keyboard.press('Enter')
                return
    except:
        pass


def _is_on_results_page(page):
    """检查是否到了论文检索结果页"""
    try:
        text = page.content()[:5000]
        # 知网结果页特征
        cnki_markers = ['检索结果', '条结果', 'kns.cnki.net', 'detail',
                        'result', 'search-result', 'result-list']
        hits = sum(1 for m in cnki_markers if m in text.lower() if m.strip())
        return hits >= 2
    except:
        return False


def _collect_paper_links(page, max_papers):
    """收集论文详情页链接"""
    links = set()
    # 知网检索结果中的论文链接
    for a in page.query_selector_all('a'):
        href = a.get_attribute('href') or ''
        if 'kns.cnki.net' in href or 'detail' in href:
            links.add(href)
    return list(links)[:max_papers]


def _download_paper(page, context, detail_url, prefix):
    """打开论文详情页，尝试下载PDF"""
    try:
        new_page = context.new_page()
        new_page.goto(detail_url, timeout=20000, wait_until='domcontentloaded')
        time.sleep(2)

        # 查找PDF下载链接
        pdf_url = None
        for a in new_page.query_selector_all('a'):
            href = a.get_attribute('href') or ''
            text = a.inner_text() or ''
            if '.pdf' in href.lower() or 'PDF' in text or '下载' in text:
                pdf_url = href
                break

        if pdf_url:
            # 创建下载
            filename = f"{prefix}_{int(time.time())}.pdf"
            filepath = os.path.join(TEMP_DIR, filename)
            with new_page.expect_download(timeout=30000) as download_info:
                new_page.click(f'a[href="{pdf_url}"]')
            download = download_info.value
            download.save_as(filepath)
            new_page.close()
            return filepath

        new_page.close()
        return None
    except Exception as e:
        print(f"[CNKI] 下载失败: {detail_url[:60]} - {e}")
        return None


def extract_text_from_pdf(filepath):
    """从下载的PDF提取文本"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text.strip()
    except:
        return ""


def _wait_user_credentials(task_id, timeout=120):
    """等待用户通过前端输入学校账号密码"""
    with cnki_lock:
        cnki_tasks[task_id]["credentials"] = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        with cnki_lock:
            task = cnki_tasks.get(task_id, {})
            creds = task.get("credentials")
            if creds:
                task["credentials"] = None
                return creds
        time.sleep(1)
    return None


def _wait_user_url(task_id, timeout=180):
    """等待用户粘贴导航后的知网URL"""
    with cnki_lock:
        cnki_tasks[task_id]["new_url"] = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        with cnki_lock:
            task = cnki_tasks.get(task_id, {})
            url = task.get("new_url")
            if url:
                task["new_url"] = None
                return url
        time.sleep(1)
    return None


def _wait_user_captcha(task_id, timeout=60):
    """等待用户输入验证码"""
    with cnki_lock:
        if task_id in cnki_tasks:
            cnki_tasks[task_id]["captcha_answer"] = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        with cnki_lock:
            task = cnki_tasks.get(task_id, {})
            if task.get("captcha_answer"):
                ans = task["captcha_answer"]
                task["captcha_answer"] = None
                return ans
        time.sleep(1)
    return None
