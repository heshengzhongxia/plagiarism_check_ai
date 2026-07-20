"""
基于 KeyBERT + 原文短语匹配的关键词提取模块

核心原则：所有关键词必须是论文全文中连续出现的真实子串，
不能增加、删除或修改任何字符。

流程：
  1. 文本预处理 + 语言检测
  2. 基于分词位置生成候选短语（从原文精确截取）
  3. KeyBERT 语义向量 + 余弦相似度排序 → Top 20
  4. MMR 多样性重排 → Top 10
  5. 后处理：强制原文校验 + 包含关系去重
  6. 不足5个时 TF-IDF 补充
"""

import re
import os
import numpy as np

# ============================================================
# 全局模型缓存（避免重复加载）
# ============================================================
_MODEL_CACHE = {}
_KEYBERT_CACHE = {}


def _get_keybert_model(model_name):
    """懒加载 KeyBERT 模型，缓存复用"""
    if model_name not in _KEYBERT_CACHE:
        from keybert import KeyBERT
        _KEYBERT_CACHE[model_name] = KeyBERT(model=model_name)
    return _KEYBERT_CACHE[model_name]


def _get_sentence_model(model_name):
    """懒加载 sentence-transformers 模型"""
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer
        # 强制离线优先，避免每次检查更新
        _MODEL_CACHE[model_name] = SentenceTransformer(
            model_name,
            # cache_folder=os.path.join(os.path.dirname(__file__), ".model_cache"),
        )
    return _MODEL_CACHE[model_name]


# ============================================================
# 1. 文本预处理 & 语言检测
# ============================================================

def detect_language(text):
    """
    检测文本语言，返回 'zh' 或 'en'。
    基于中文字符占比，阈值 30%。
    """
    if not text:
        return "en"
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    # 排除空白后的总有效字符数
    total = len(re.sub(r'\s', '', text))
    if total == 0:
        return "en"
    ratio = chinese_chars / total
    return "zh" if ratio > 0.3 else "en"


# ============================================================
# 中文停用词（学术论文中过于泛化的词，不应作为关键词）
# ============================================================
_CN_STOP_WORDS = {
    # 虚词/代词/数量
    "的", "了", "在", "是", "有", "和", "与", "或", "及", "等", "对", "从", "到",
    "也", "就", "都", "而", "但", "且", "被", "把", "将", "以", "能", "会", "要",
    "可以", "一个", "一种", "这个", "那个", "我们", "他们", "它们", "其", "该",
    "这", "那", "之", "中", "上", "下", "内", "外", "前", "后", "所",
    "不", "为", "已", "则", "又", "如", "更", "最",
    # 过于泛化的学术词
    "研究", "分析", "方法", "提出", "实验", "结果", "数据", "基于", "问题",
    "通过", "进行", "使用", "利用", "采用", "实现", "设计", "表明", "发现",
    "本文", "文章", "论文", "介绍", "讨论", "验证", "证明", "总结", "相关",
    "不同", "影响", "应用", "作用", "比较", "发展", "技术", "系统", "模型",
    "结构", "过程", "解决", "处理", "提高", "增加", "减少", "主要", "重要",
    "具有", "存在", "需要", "包括", "涉及", "提出", "结合", "考虑", "特征",
    "以下", "上述", "大量", "显著", "较好", "情况", "条件", "效果",
    "能够", "不仅", "用时", "集上",
}
# 停用词最小长度以上才检查（避免检查过短词导致误杀）
_STOP_MIN_LEN = 1


def generate_candidates_zh(full_text):
    """
    中文候选短语生成。
    使用 jieba 分词并记录每个词在原文中的起止位置，
    生成所有 2-4 连续词组合，根据位置从 full_text 截取原始子串。
    过滤停用词和纯数字/标点。
    """
    import jieba

    # jieba.tokenize 返回 (word, start, end)
    tokens = list(jieba.tokenize(full_text))
    if not tokens:
        return []

    candidates = set()
    n = len(tokens)

    for i in range(n):
        for length in range(2, 5):  # 2-4词短语（不含单字词，避免碎片）
            if i + length > n:
                break
            start = tokens[i][1]
            end = tokens[i + length - 1][2]
            # ---- 从原文按位置截取，绝不拼接 ----
            phrase = full_text[start:end].strip()

            if not phrase:
                continue
            # 最少4个字符（中文2词短语通常≥4字）
            if len(phrase) < 4:
                continue
            # 过滤纯数字
            if re.match(r'^\d+$', phrase):
                continue
            # 过滤纯标点
            if re.match(
                r'^[\d\s\.\,\;\:\!\?\-\+\=\(\)\[\]\{\}\'\"\、\。\，\；\：\！\？\（\）\【\】\《\》\%\#\@\$]+$',
                phrase,
            ):
                continue
            # 过滤停用词（精确匹配或短语中每个子词都是停用词）
            if phrase in _CN_STOP_WORDS:
                continue
            # 如果短语的所有组成词都是停用词，跳过
            sub_words = [tokens[k][0] for k in range(i, i + length)]
            if all(w in _CN_STOP_WORDS or len(w) <= _STOP_MIN_LEN for w in sub_words):
                continue

            candidates.add(phrase)

    return list(candidates)


def generate_candidates_en(full_text):
    """
    英文候选短语生成。
    按单词边界分词（含连字符、缩写），生成 1-3 单词子串，
    根据位置从 full_text 截取。
    """
    # 匹配英文单词（含连字符、缩写's、数字字母混合等）
    word_re = re.compile(r"[A-Za-z][A-Za-z\-']*[A-Za-z]|[A-Za-z]")
    matches = list(word_re.finditer(full_text))
    if not matches:
        return []

    # (word, start, end)
    words = [(m.group(), m.start(), m.end()) for m in matches]

    candidates = set()
    n = len(words)

    for i in range(n):
        for length in range(1, 4):
            if i + length > n:
                break
            start = words[i][1]
            end = words[i + length - 1][2]
            phrase = full_text[start:end].strip()

            if not phrase:
                continue
            if len(phrase) < 3:
                continue
            if re.match(r'^[\d\s\.\,\;\:\!\?\-\+\(\)\[\]\{\}\'\"\%\#\@\$]+$', phrase):
                continue

            candidates.add(phrase)

    return list(candidates)


# ============================================================
# 3. MMR 多样性重排
# ============================================================

def _cosine_sim(a, b):
    """两个向量的余弦相似度"""
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


def mmr_rerank(doc_embedding, candidate_embeddings, candidates,
               top_n=10, diversity=0.5):
    """
    MMR（最大边际相关度）多样性重排。

    每一步选择最大化以下分数的候选：
      score = diversity * sim(doc, c) - (1-diversity) * max(sim(selected, c))

    Args:
        doc_embedding: 文档的语义向量
        candidate_embeddings: 候选短语向量列表
        candidates: 候选短语文本列表
        top_n: 最终保留数量
        diversity: 多样性权重（0=全多样化, 1=全相关性）

    Returns:
        list[str]: 重排后的关键词列表
    """
    if not candidates:
        return []

    n_candidates = len(candidates)
    if n_candidates <= top_n:
        return list(candidates)

    # 预计算每个候选与文档的相似度
    sim_to_doc = np.array([
        _cosine_sim(doc_embedding, candidate_embeddings[i])
        for i in range(n_candidates)
    ])

    # 预计算候选之间的相似度矩阵
    sim_matrix = np.zeros((n_candidates, n_candidates))
    for i in range(n_candidates):
        for j in range(i + 1, n_candidates):
            s = _cosine_sim(candidate_embeddings[i], candidate_embeddings[j])
            sim_matrix[i][j] = s
            sim_matrix[j][i] = s

    selected = []
    remaining = set(range(n_candidates))

    while len(selected) < top_n and remaining:
        best_idx = None
        best_score = -float('inf')

        for idx in remaining:
            relevance = sim_to_doc[idx]
            # 与已选中的最大相似度
            if selected:
                max_red = max(sim_matrix[idx][sel] for sel in selected)
            else:
                max_red = 0.0
            mmr_score = diversity * relevance - (1 - diversity) * max_red

            # 长度加成：长短语更有意义（每超出4字加0.02）
            length_bonus = max(0, (len(candidates[idx]) - 4) * 0.02)
            mmr_score += length_bonus

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx is None:
            break

        selected.append(best_idx)
        remaining.remove(best_idx)

    return [candidates[i] for i in selected]


# ============================================================
# 4. 后处理 & 校验
# ============================================================

def postprocess_keywords(keywords, full_text, similarities=None):
    """
    后处理与强制校验：

    1. 强制校验：keyword 必须出现在 full_text 中（用 keyword in full_text 检查）
    2. 包含关系去重：若 kw_a 包含 kw_b，保留较长的
    3. 长度相同时保留相似度较高的
    """
    # Step 1: 原文子串强制校验
    valid = []
    valid_sims = []
    for i, kw in enumerate(keywords):
        if kw and kw in full_text:
            valid.append(kw)
            if similarities and i < len(similarities):
                valid_sims.append(similarities[i])
            else:
                valid_sims.append(0.0)

    if not valid:
        return []

    # Step 2: 包含关系去重
    paired = list(zip(valid, valid_sims))
    # 按长度降序、相似度降序排列
    paired.sort(key=lambda x: (-len(x[0]), -x[1]))

    result = []
    for kw, sim in paired:
        is_contained = False
        for existing_kw, _ in result:
            if kw != existing_kw and kw in existing_kw:
                is_contained = True
                break
        if not is_contained:
            result.append((kw, sim))

    return [kw for kw, _ in result]


# ============================================================
# 5. TF-IDF 回退（不足 5 个关键词时）
# ============================================================

def tfidf_fallback(full_text, lang, top_n=10):
    """
    TF-IDF 提取作为关键词补充。
    将文本按句号分句作为伪文档集合，提取 TF-IDF 最高的词。
    同样要求：词必须在原文中出现。
    """
    if lang == 'zh':
        sentences = re.split(r'[。！？\n；]+', full_text)
    else:
        sentences = re.split(r'[.!?\n]+', full_text)

    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if len(sentences) < 2:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        if lang == 'zh':
            import jieba
            docs = [' '.join(jieba.cut(s)) for s in sentences]
            vec = TfidfVectorizer(
                max_features=60,
                token_pattern=r'(?u)\b\w+\b',
            )
        else:
            docs = sentences
            vec = TfidfVectorizer(
                max_features=60,
                stop_words='english',
            )

        tfidf_matrix = vec.fit_transform(docs)
        feature_names = vec.get_feature_names_out()
        scores = np.array(tfidf_matrix.sum(axis=0)).flatten()

        # 按分数降序
        top_indices = scores.argsort()[::-1][:top_n * 2]

        result = []
        for idx in top_indices:
            word = feature_names[idx]
            # 必须在原文中出现
            if word in full_text and len(word) >= 2:
                if word not in result:
                    result.append(word)
            if len(result) >= top_n:
                break

        return result
    except Exception:
        return []


# ============================================================
# 6. 主入口
# ============================================================

def _fallback_keywords(full_text, lang, top_n=10):
    """快速回退：纯 TF-IDF 提取，不走模型，CPU 友好"""
    keywords = tfidf_fallback(full_text, lang, top_n=top_n)
    keywords = postprocess_keywords(keywords, full_text)
    return keywords[:top_n]


def extract_keywords(full_text, top_n=10):
    """
    从论文全文中提取关键词。

    策略：先尝试 KeyBERT 语义提取（限时 20 秒），超时则回退到 TF-IDF。
    所有关键词均为原文中连续出现的真实子串。

    Args:
        full_text: 论文全文纯文本
        top_n: 最大关键词数，默认 10

    Returns:
        list[str]: 关键词列表。若论文过短（< 50 字符）返回空列表。
    """
    full_text = full_text.strip()
    if not full_text or len(full_text) < 50:
        return []

    # ---- 语言检测 ----
    lang = detect_language(full_text)

    # ---- 生成候选短语 ----
    if lang == 'zh':
        candidates = generate_candidates_zh(full_text)
    else:
        candidates = generate_candidates_en(full_text)

    if not candidates:
        return []

    # 去重 + 限制候选数量（CPU 服务器最多 300 个，控制嵌入耗时）
    candidates = list(set(candidates))
    if len(candidates) > 300:
        # 优先保留较长的短语（更有意义）
        candidates.sort(key=lambda x: -len(x))
        candidates = candidates[:300]

    # ---- KeyBERT 语义提取（带超时保护） ----
    keywords = []
    _embedding_done = {"ok": False}

    def _do_embedding():
        """在独立上下文中执行嵌入计算，可被超时中断"""
        nonlocal keywords
        try:
            if lang == 'zh':
                model_name = 'shibing624/text2vec-base-chinese'
            else:
                model_name = 'all-MiniLM-L6-v2'

            kw_model = _get_keybert_model(model_name)
            embedder = kw_model.model

            # 文档嵌入
            doc_embedding = embedder.encode(
                [full_text], show_progress_bar=False
            )[0]

            # 候选嵌入（小批量，CPU 友好）
            candidate_embeddings = embedder.encode(
                candidates,
                show_progress_bar=False,
                batch_size=32,
            )

            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(
                [doc_embedding], candidate_embeddings
            )[0]

            # Top 20
            sorted_indices = similarities.argsort()[-20:][::-1]
            pool_candidates = [candidates[i] for i in sorted_indices]
            pool_embeddings = [candidate_embeddings[i] for i in sorted_indices]

            keywords = mmr_rerank(
                doc_embedding, pool_embeddings, pool_candidates,
                top_n=top_n, diversity=0.5,
            )
            _embedding_done["ok"] = True
        except Exception as e:
            print(f"[keyword_extractor] 嵌入失败: {e}")

    # 在独立线程中执行，等待最多 20 秒
    import threading
    t = threading.Thread(target=_do_embedding, daemon=True)
    t.start()
    t.join(timeout=45)

    if t.is_alive() or not _embedding_done["ok"]:
        print(f"[keyword_extractor] KeyBERT 超时或失败，回退到 TF-IDF")
        keywords = []

    # ---- 后处理 & 强制校验 ----
    keywords = postprocess_keywords(keywords, full_text)

    # ---- 不足 5 个时 TF-IDF 补充 ----
    if len(keywords) < 5:
        fallback_kw = tfidf_fallback(full_text, lang, top_n=10)
        existing = set(keywords)
        for fw in fallback_kw:
            if fw not in existing and fw in full_text:
                keywords.append(fw)
                existing.add(fw)
            if len(keywords) >= top_n:
                break
        keywords = postprocess_keywords(keywords, full_text)

    keywords = keywords[:top_n]
    return keywords
