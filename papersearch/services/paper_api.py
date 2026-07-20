"""
学术论文API集成 — 7个免费数据库
arXiv | Semantic Scholar | OpenAlex | Crossref | CORE | DBLP | PubMed
支持中英文自动检测，中文查询优先中文覆盖、英文作为补充
"""
import re
import json
import time
import urllib.request
import urllib.parse
import ssl
import threading

try:
    import requests as req_lib
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ============================================================
# 语言检测
# ============================================================

def detect_language(text):
    """检测文本是否为中文为主"""
    if not text:
        return "en"
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    return "zh" if chinese_chars > 3 else "en"


def translate_keywords_en(keywords):
    """
    简单的中文关键词英文映射（高频学术词汇）。
    完整翻译可接入DeepSeek，这里提供基础覆盖。
    """
    BASIC_MAP = {
        "深度学习": "deep learning",
        "机器学习": "machine learning",
        "神经网络": "neural network",
        "图神经网络": "graph neural network",
        "注意力机制": "attention mechanism",
        "自然语言处理": "natural language processing",
        "计算机视觉": "computer vision",
        "强化学习": "reinforcement learning",
        "迁移学习": "transfer learning",
        "生成对抗": "generative adversarial",
        "Transformer": "Transformer",
        "BERT": "BERT",
        "GPT": "GPT",
        "大语言模型": "large language model",
        "交通流预测": "traffic flow prediction",
        "时间序列": "time series",
        "推荐系统": "recommender system",
        "知识图谱": "knowledge graph",
        "联邦学习": "federated learning",
        "对比学习": "contrastive learning",
        "自监督学习": "self supervised learning",
        "多模态": "multimodal",
        "图像分割": "image segmentation",
        "目标检测": "object detection",
        "语音识别": "speech recognition",
        "情感分析": "sentiment analysis",
        "文本分类": "text classification",
        "命名实体识别": "named entity recognition",
        "数据挖掘": "data mining",
        "异常检测": "anomaly detection",
        "优化算法": "optimization algorithm",
        "卷积神经网络": "convolutional neural network",
        "循环神经网络": "recurrent neural network",
        "长短期记忆": "LSTM",
        "编码器解码器": "encoder decoder",
        "预训练": "pre-training",
        "微调": "fine-tuning",
        "推理": "inference",
        "分类": "classification",
        "回归": "regression",
        "聚类": "clustering",
        "特征工程": "feature engineering",
    }
    result = []
    for kw in keywords:
        if kw in BASIC_MAP:
            result.append(BASIC_MAP[kw])
        elif re.search(r'[一-鿿]', kw):
            # 含中文但无映射，保留原词（可能有拼音匹配）
            result.append(kw)
        else:
            result.append(kw)
    return result


# ============================================================
# HTTP 工具
# ============================================================

def _http_get(url, timeout=6, headers=None):
    """GET请求，返回 (content, status)"""
    default_headers = {
        "User-Agent": "LiuzhiAgent/2.0 Academic Paper Tool",
        "Accept": "application/json,application/xml,text/html,*/*",
    }
    if headers:
        default_headers.update(headers)

    if HAS_REQUESTS:
        try:
            r = req_lib.get(url, headers=default_headers, timeout=timeout)
            return r.text, r.status_code
        except Exception:
            return None, "error"

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=default_headers)
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.read().decode("utf-8", errors="ignore"), resp.status
    except Exception as e:
        return None, str(e)


def _timed(fn, *args, timeout=5, **kwargs):
    """在线程中执行函数，超时返回空列表"""
    result = []
    def run():
        try:
            r = fn(*args, **kwargs)
            if r:
                result.extend(r)
        except Exception:
            pass
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return result


# ============================================================
# 1. arXiv API
# ============================================================

def search_arxiv(query_keywords, max_results=10):
    """http://export.arxiv.org/api/query"""
    query = ' AND '.join(f'all:{kw}' for kw in query_keywords[:5])
    url = f"http://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&start=0&max_results={max_results}&sortBy=relevance"

    content, status = _http_get(url, timeout=6)
    if not content:
        return []

    papers = []
    entries = re.split(r'<(?:entry|atom:entry)>', content)
    for block in entries[1:]:
        title_m = re.search(r'<(?:title|atom:title)[^>]*>(.*?)</(?:title|atom:title)>', block, re.DOTALL)
        title = re.sub(r'\s+', ' ', (title_m.group(1) or "").strip()) if title_m else ""
        if len(title) < 5:
            continue
        id_m = re.search(r'<(?:id|atom:id)[^>]*>(.*?)</(?:id|atom:id)>', block, re.DOTALL)
        paper_url = id_m.group(1).strip() if id_m else ""
        summary_m = re.search(r'<(?:summary|atom:summary)[^>]*>(.*?)</(?:summary|atom:summary)>', block, re.DOTALL)
        abstract = re.sub(r'\s+', ' ', (summary_m.group(1) or "").strip())[:600] if summary_m else ""
        authors_m = re.findall(r'<(?:name|atom:name)[^>]*>(.*?)</(?:name|atom:name)>', block)
        papers.append({
            "title": title[:200], "abstract": abstract or "No abstract",
            "url": paper_url, "authors": ', '.join(authors_m[:5]),
            "source": "arXiv",
        })
    return papers[:max_results]


# ============================================================
# 2. Semantic Scholar API
# ============================================================

def search_semantic_scholar(query_keywords, limit=10):
    """https://api.semanticscholar.org/graph/v1/paper/search"""
    query = ' '.join(query_keywords[:6])
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={urllib.parse.quote(query)}&limit={limit}"
        f"&fields=title,abstract,url,authors,year,externalIds"
    )
    content, status = _http_get(url, timeout=6)
    if not content:
        return []
    papers = []
    try:
        data = json.loads(content)
        for item in data.get('data', []):
            authors = [a.get('name', '') for a in item.get('authors', [])[:5]]
            abstract = item.get('abstract') or f"Authors: {', '.join(authors)}"
            ext = item.get('externalIds', {}) or {}
            url_p = item.get('url', '') or f"https://doi.org/{ext.get('DOI','')}"
            papers.append({
                "title": item.get('title', '')[:200],
                "abstract": abstract[:600],
                "url": url_p,
                "authors": ', '.join(authors),
                "year": item.get('year', ''),
                "source": "Semantic Scholar",
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return papers[:limit]


# ============================================================
# 3. OpenAlex API
# ============================================================

def search_openalex(query_keywords, limit=10):
    """https://api.openalex.org/works — 2.5亿+论文"""
    query = ' '.join(query_keywords[:5])
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(query)}&per_page={limit}&sort=cited_by_count:desc"
    # 已知中文问题：OpenAlex支持多语言搜索
    content, status = _http_get(url, timeout=6)
    if not content:
        return []
    papers = []
    try:
        data = json.loads(content)
        for item in data.get('results', []):
            title = item.get('title') or item.get('display_name') or ''
            abstract = ''
            # OpenAlex用abstract_inverted_index
            ab_idx = item.get('abstract_inverted_index')
            if ab_idx:
                words = sorted((pos, w) for w, positions in ab_idx.items() for pos in positions)
                abstract = ' '.join(w for _, w in words)[:600]
            doi = item.get('doi', '')
            url_p = f"https://doi.org/{doi}" if doi else item.get('primary_location', {}).get('landing_page_url', '')
            papers.append({
                "title": title[:200],
                "abstract": abstract or "No abstract available",
                "url": url_p,
                "authors": '',
                "source": "OpenAlex",
                "cited_by": item.get('cited_by_count', 0),
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return papers[:limit]


# ============================================================
# 4. Crossref API
# ============================================================

def search_crossref(query_keywords, limit=10):
    """https://api.crossref.org/works"""
    query = '+'.join(query_keywords[:5])
    url = f"https://api.crossref.org/works?query={urllib.parse.quote(query)}&rows={limit}&sort=relevance"
    content, status = _http_get(url, timeout=6)
    if not content:
        return []
    papers = []
    try:
        data = json.loads(content)
        for item in data.get('message', {}).get('items', []):
            title_list = item.get('title', ['Unknown'])
            title = title_list[0] if title_list else 'Unknown'
            abstract = item.get('abstract', 'No abstract')[:600]
            doi = item.get('DOI', '')
            url_p = f"https://doi.org/{doi}" if doi else ''
            authors = [a.get('given', '') + ' ' + a.get('family', '')
                       for a in item.get('author', [])[:5]]
            papers.append({
                "title": title[:200],
                "abstract": abstract[:600],
                "url": url_p,
                "authors": ', '.join(authors),
                "year": item.get('created', {}).get('date-time', '')[:4],
                "source": "Crossref",
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return papers[:limit]


# ============================================================
# 5. CORE API
# ============================================================

def search_core(query_keywords, limit=10):
    """https://api.core.ac.uk/v3/search/works"""
    query = ' '.join(query_keywords[:5])
    url = f"https://api.core.ac.uk/v3/search/works?q={urllib.parse.quote(query)}&limit={limit}"
    content, status = _http_get(url, timeout=6, headers={"Authorization": "Bearer "})  # free tier, no key
    # CORE v3 需要API key，免费注册可得。这里尝试无key访问
    if not content or (isinstance(status, int) and status >= 400):
        # 回退到 v2
        url_v2 = f"https://api.core.ac.uk/v2/search?q={urllib.parse.quote(query)}&pageSize={limit}"
        content, _ = _http_get(url_v2, timeout=6)
        if not content:
            return []
    papers = []
    try:
        data = json.loads(content)
        items = data.get('results', data.get('data', []))
        for item in items[:limit]:
            title = item.get('title', '') or item.get('name', '')
            abstract = (item.get('abstract', '') or item.get('description', ''))[:600]
            url_p = item.get('downloadUrl', '') or item.get('sourceUrl', '') or ''
            papers.append({
                "title": title[:200],
                "abstract": abstract or "No abstract",
                "url": url_p,
                "authors": '',
                "source": "CORE",
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return papers[:limit]


# ============================================================
# 6. DBLP API (计算机科学)
# ============================================================

def search_dblp(query_keywords, limit=10):
    """https://dblp.org/search/publ/api"""
    query = ' '.join(query_keywords[:5])
    url = f"https://dblp.org/search/publ/api?q={urllib.parse.quote(query)}&h={limit}&format=json"
    content, status = _http_get(url, timeout=6)
    if not content:
        return []
    papers = []
    try:
        data = json.loads(content)
        hits = data.get('result', {}).get('hits', {}).get('hit', [])
        for item in hits[:limit]:
            info = item.get('info', {})
            title = info.get('title', '')
            url_p = info.get('url', '') or info.get('ee', '')
            venue = info.get('venue', '')
            authors_info = info.get('authors', {}).get('author', [])
            if isinstance(authors_info, dict):
                authors_info = [authors_info]
            author_names = [a.get('text', '') for a in authors_info[:5]]
            papers.append({
                "title": str(title)[:200],
                "abstract": f"Published in: {venue}" if venue else "No abstract",
                "url": str(url_p) if url_p else '',
                "authors": ', '.join(author_names),
                "source": "DBLP",
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return papers[:limit]


# ============================================================
# 7. PubMed / NCBI E-utilities
# ============================================================

def search_pubmed(query_keywords, limit=10):
    """https://eutils.ncbi.nlm.nih.gov/entrez/eutils"""
    query = '+'.join(query_keywords[:5])
    # Step 1: search for IDs
    search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmax={limit}&retmode=json&sort=relevance&term={urllib.parse.quote(query)}"
    content, _ = _http_get(search_url, timeout=6)
    if not content:
        return []
    papers = []
    try:
        search_data = json.loads(content)
        ids = search_data.get('esearchresult', {}).get('idlist', [])
        if not ids:
            return []
        # Step 2: fetch summaries
        ids_str = ','.join(ids[:limit])
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={ids_str}&retmode=json"
        content2, _ = _http_get(fetch_url, timeout=6)
        if not content2:
            return []
        fetch_data = json.loads(content2)
        for pid in ids[:limit]:
            item = fetch_data.get('result', {}).get(pid, {})
            title = item.get('title', '')
            abstract = ''  # esummary doesn't include abstract; use efetch for that
            url_p = f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
            authors = [a.get('name', '') for a in item.get('authors', [])[:5]]
            papers.append({
                "title": title[:200],
                "abstract": abstract or f"PubMed ID: {pid}",
                "url": url_p,
                "authors": ', '.join(authors),
                "source": "PubMed",
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return papers[:limit]


# ============================================================
# 统一搜索入口
# ============================================================

# 所有可用的API源
ALL_SOURCES = {
    "arxiv": {"name": "arXiv", "fn": search_arxiv, "desc": "物理/CS/AI 预印本"},
    "semantic_scholar": {"name": "Semantic Scholar", "fn": search_semantic_scholar, "desc": "全学科 + 引用图谱"},
    "openalex": {"name": "OpenAlex", "fn": search_openalex, "desc": "2.5亿+ 全学科"},
    "crossref": {"name": "Crossref", "fn": search_crossref, "desc": "全学科 DOI 检索"},
    "core": {"name": "CORE", "fn": search_core, "desc": "开放获取全文库"},
    "dblp": {"name": "DBLP", "fn": search_dblp, "desc": "计算机科学专库"},
    "pubmed": {"name": "PubMed", "fn": search_pubmed, "desc": "生物医学专库"},
}


def search_all(keywords, sources=None, max_per_source=8):
    """
    并行查询所有（或指定）学术API。

    Args:
        keywords: 关键词列表
        sources: 要查询的源列表（None=全部，或 ["arxiv","openalex"] 等）
        max_per_source: 每个源最多返回的论文数

    Returns:
        {
            "papers": [论文列表（去重后）],
            "total": 去重后总数,
            "by_source": {"arxiv": N, "semantic_scholar": N, ...},
            "sources_queried": ["arxiv", ...],
            "keywords_used": {"zh": [...], "en": [...]},
        }
    """
    if sources is None:
        sources = list(ALL_SOURCES.keys())
    else:
        sources = [s for s in sources if s in ALL_SOURCES]

    lang = detect_language(' '.join(keywords))
    zh_keywords = keywords
    en_keywords = translate_keywords_en(keywords) if lang == "zh" else keywords

    # 中文查询时对英文库使用翻译关键词
    en_sources = {"arxiv", "semantic_scholar", "openalex", "crossref", "core", "pubmed"}
    cn_sources = {"dblp"}  # DBLP 部分支持中文

    results_by_source = {}
    threads = {}

    for src in sources:
        actual_kw = en_keywords if src in en_sources else zh_keywords
        fn = ALL_SOURCES[src]["fn"]
        t = threading.Thread(target=lambda s=src, f=fn, kw=actual_kw: results_by_source.update({s: f(kw, max_per_source)}))
        t.daemon = True
        threads[src] = t
        t.start()

    # 等待所有线程（最长8秒）
    deadline = time.time() + 8
    for src, t in threads.items():
        remaining = deadline - time.time()
        if remaining > 0:
            t.join(timeout=remaining)

    # 合并去重
    seen = set()
    all_papers = []
    by_source_count = {}

    for src in sources:
        papers = results_by_source.get(src, [])
        by_source_count[src] = len(papers)
        for p in papers:
            key = p.get("title", "").lower().strip()[:60]
            if key and key not in seen:
                seen.add(key)
                all_papers.append(p)

    return {
        "papers": all_papers[:30],
        "total": len(all_papers),
        "by_source": by_source_count,
        "sources_queried": sources,
        "keywords_used": {"zh": zh_keywords, "en": en_keywords},
    }
