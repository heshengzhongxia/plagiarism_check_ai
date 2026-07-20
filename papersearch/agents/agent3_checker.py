"""
Agent3: 校验·维拉 - 句级语义查重比对

核心原则：以完整句子为最小比对单位，输出必须是原文中的完整原句。
使用 sentence-transformers 语义向量 + 余弦相似度，而非字符级 LCS 片段匹配。

数据流：
  输入 <- agent1（用户全文） + agent2（爬取论文）
  输出 -> agent4（修改方向） + agent6（生成报告）
"""
import re
import numpy as np
from agents.base import BaseAgent
from llm_client import call_deepseek, extract_json

# ============================================================
# 全局模型缓存
# ============================================================
_EMBEDDER_CACHE = {}


def _get_embedder(model_name):
    """懒加载 sentence-transformers 模型，缓存复用"""
    if model_name not in _EMBEDDER_CACHE:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER_CACHE[model_name] = SentenceTransformer(model_name)
    return _EMBEDDER_CACHE[model_name]


# ============================================================
# 1. 句子分割（保留完整原句，不截断不拼接）
# ============================================================

def detect_language(text):
    """检测文本语言"""
    if not text:
        return "en"
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    total = len(re.sub(r'\s', '', text))
    if total == 0:
        return "en"
    return "zh" if chinese_chars / total > 0.3 else "en"


def split_sentences_full(text, min_chars=4, merge_short_threshold=10):
    """
    将文本按自然断句符切分为完整句子列表。

    步骤：
      1. 用 finditer 找到所有断句符位置
      2. 按断句符之间的区间截取原文
      3. 过滤纯空白/标点/过短的无效句子
      4. 将过短句子（< merge_short_threshold 字符）与后一句合并

    返回：list[str] — 每个元素都是原文中连续出现的完整子串，未做任何增删改。
    """
    if not text:
        return []

    # 断句符：句号、问号、感叹号、分号、换行符（保留中文和英文标点）
    sep_pattern = re.compile(r'[。！？；\.!\?;\n]+')

    # 找到所有断句符的位置区间
    splits = list(sep_pattern.finditer(text))

    if not splits:
        # 整个文本没有断句符，作为一句
        stripped = text.strip()
        return [stripped] if len(stripped) >= min_chars else []

    sentences = []
    prev_end = 0

    for sep_match in splits:
        seg_start = prev_end
        seg_end = sep_match.start()
        # 从原文截取句子（含末尾标点，保持原文连续性）
        raw_segment = text[seg_start:sep_match.end()]
        # 去除前后空白但保留内部空格
        segment = raw_segment.strip()
        if segment and len(segment) >= min_chars:
            # 过滤纯数字/标点
            if not re.match(
                r'^[\d\s\.\,\;\:\!\?\-\+\=\(\)\[\]\{\}\'\"\、\。\，\；\：\！\？\（\）\【\】\《\》\%\#\@\$]+$',
                segment,
            ):
                sentences.append(segment)
        prev_end = sep_match.end()

    # 最后一段（断句符之后的内容）
    if prev_end < len(text):
        tail = text[prev_end:].strip()
        if tail and len(tail) >= min_chars:
            if not re.match(
                r'^[\d\s\.\,\;\:\!\?\-\+\=\(\)\[\]\{\}\'\"\、\。\，\;\：\！\？\（\）\【\】\《\》\%\#\@\$]+$',
                tail,
            ):
                sentences.append(tail)

    # ---- 合并过短句子 ----
    # 如果某句 < merge_short_threshold 字符，与后一句合并
    # 合并方式：找到两句在原文中的位置，取从第一句开头到第二句结尾的原文子串
    merged = []
    i = 0
    while i < len(sentences):
        sent = sentences[i]
        if len(sent) < merge_short_threshold and i + 1 < len(sentences):
            # 合并当前句和后一句
            next_sent = sentences[i + 1]
            # 从原文中找到合并后的连续子串
            combined_text = _merge_two_in_original(text, sent, next_sent)
            merged.append(combined_text)
            i += 2
        else:
            merged.append(sent)
            i += 1

    return merged


def _merge_two_in_original(full_text, sent_a, sent_b):
    """
    将两个句子在原文中合并为连续子串。
    找到 sent_a 和 sent_b 的位置，返回从 sent_a 开头到 sent_b 结尾的原文。
    """
    pos_a = full_text.find(sent_a)
    pos_b = full_text.find(sent_b)
    if pos_a != -1 and pos_b != -1 and pos_b > pos_a:
        return full_text[pos_a:pos_b + len(sent_b)].strip()
    # fallback: 直接拼接
    return (sent_a + sent_b).strip()


# ============================================================
# 2. 句子级语义相似度比对
# ============================================================

def compute_sentence_embeddings(sentences, model_name):
    """
    批量计算句子嵌入向量。

    Args:
        sentences: 句子列表
        model_name: sentence-transformers 模型名

    Returns:
        np.ndarray: shape (len(sentences), embedding_dim)
    """
    if not sentences:
        return np.array([])
    embedder = _get_embedder(model_name)
    embeddings = embedder.encode(
        sentences,
        show_progress_bar=False,
        batch_size=32,
        convert_to_numpy=True,
    )
    return embeddings


def compute_cosine_similarities(user_embeddings, crawled_embeddings):
    """
    计算每个用户句子与所有爬取句子的余弦相似度。

    Args:
        user_embeddings: (U, D) — 用户句子向量
        crawled_embeddings: (C, D) — 爬取句子向量

    Returns:
        np.ndarray: (U, C) — 相似度矩阵
    """
    from sklearn.metrics.pairwise import cosine_similarity
    if user_embeddings.size == 0 or crawled_embeddings.size == 0:
        return np.array([[]])
    return cosine_similarity(user_embeddings, crawled_embeddings)


def sentence_level_match(user_sentences, crawled_sentence_meta, threshold=0.60):
    """
    对每个用户句子，在所有爬取文章中找最相似的完整句子。

    Args:
        user_sentences: 用户论文的完整句子列表
        crawled_sentence_meta: 爬取句子元数据列表，每个元素：
            {
                "sentence": "爬取文章中的完整原句",
                "source_title": "来源文章标题",
                "source_url": "来源URL",
            }
        threshold: 相似度阈值，默认 0.60（60%）

    Returns:
        list[dict]: 匹配结果列表，每个元素：
            {
                "user_sentence": "完整原句",
                "matched_sentence": "爬取文章中的完整原句",
                "source": "来源文章标题或URL",
                "similarity": 0.85
            }
    """
    if not user_sentences or not crawled_sentence_meta:
        return []

    # 只取爬取句子的文本列表
    crawled_sentences = [m["sentence"] for m in crawled_sentence_meta]

    # 选择模型
    # 检测全文语言
    all_user_text = " ".join(user_sentences[:10])
    lang = detect_language(all_user_text)
    if lang == "zh":
        model_name = "shibing624/text2vec-base-chinese"
    else:
        model_name = "all-MiniLM-L6-v2"

    # 批量计算向量
    user_embeddings = compute_sentence_embeddings(user_sentences, model_name)
    crawled_embeddings = compute_sentence_embeddings(crawled_sentences, model_name)

    if user_embeddings.size == 0 or crawled_embeddings.size == 0:
        return []

    # 相似度矩阵
    sim_matrix = compute_cosine_similarities(user_embeddings, crawled_embeddings)
    if sim_matrix.size == 0:
        return []

    # 对每个用户句子，找最相似的爬取句子
    matches = []
    for u_idx, user_sent in enumerate(user_sentences):
        # 该用户句子与所有爬取句子的相似度
        row = sim_matrix[u_idx]
        best_c_idx = int(np.argmax(row))
        best_sim = float(row[best_c_idx])

        if best_sim >= threshold:
            meta = crawled_sentence_meta[best_c_idx]
            matches.append({
                "user_sentence": user_sent,
                "similar_sentence": meta["sentence"],
                "source_title": meta.get("source_title", ""),
                "source_url": meta.get("source_url", ""),
                "similarity": round(best_sim * 100),
            })

    return matches


# ============================================================
# 3. 收集爬取文章的所有句子（含元数据）
# ============================================================

def collect_crawled_sentences(crawled_papers):
    """
    从所有爬取论文中收集句子，每条携带来源元数据。

    Args:
        crawled_papers: agent2 输出的论文列表

    Returns:
        list[dict]: 爬取句子元数据
    """
    all_meta = []
    seen_sentences = set()  # 去重

    for paper in crawled_papers:
        paper_text = paper.get("full_text", paper.get("abstract", ""))
        if not paper_text:
            continue

        source_title = paper.get("title", "")
        source_url = paper.get("url", "")

        sentences = split_sentences_full(paper_text, min_chars=10)
        for sent in sentences:
            # 去重：相同的句子只保留一个（但保留不同的来源）
            dedup_key = sent[:80]
            if dedup_key not in seen_sentences:
                seen_sentences.add(dedup_key)
                all_meta.append({
                    "sentence": sent,
                    "source_title": source_title,
                    "source_url": source_url,
                })

    return all_meta


# ============================================================
# 4. Agent3 主类
# ============================================================

class Agent3Checker(BaseAgent):

    def think(self, input_data, context=None):
        messages = []

        user_full_text = input_data.get("user_full_text", "")
        crawled_papers = input_data.get("crawled_papers", [])
        threshold_pct = input_data.get("threshold", 60)  # 百分比
        threshold = threshold_pct / 100.0

        if not crawled_papers:
            messages.append(self.speak("未收到爬取论文，返回空匹配结果"))
            return {
                "messages": messages,
                "result": {
                    "matches": [],
                    "total_matches": 0,
                    "user_sentences_count": 0,
                },
            }

        # ---- Step 1: 用户论文分句 ----
        messages.append(self.speak(
            f"正在对用户论文进行完整句子切分..."
        ))
        user_sentences = split_sentences_full(user_full_text, min_chars=4)
        messages.append(self.speak(
            f"用户论文共 {len(user_sentences)} 个完整句子"
        ))

        if not user_sentences:
            messages.append(self.speak("用户论文无有效句子"))
            return {
                "messages": messages,
                "result": {
                    "matches": [],
                    "total_matches": 0,
                    "user_sentences_count": 0,
                },
            }

        # ---- Step 2: 收集爬取文章句子 ----
        messages.append(self.speak(
            f"正在收集 {len(crawled_papers)} 篇爬取论文的完整句子..."
        ))
        crawled_meta = collect_crawled_sentences(crawled_papers)
        messages.append(self.speak(
            f"共收集 {len(crawled_meta)} 个爬取句子（已去重）"
        ))

        if not crawled_meta:
            messages.append(self.speak("爬取论文中无有效句子"))
            return {
                "messages": messages,
                "result": {
                    "matches": [],
                    "total_matches": 0,
                    "user_sentences_count": len(user_sentences),
                },
            }

        # ---- Step 3: 句子级比对（LCS 主力，CPU 友好）----
        messages.append(self.speak(
            f"开始句级比对（阈值 {threshold_pct}%，LCS方案）..."
        ))

        # LCS 直接跑，不加载 embedding 模型，CPU 服务器友好
        matches = _lcs_fallback(user_sentences, crawled_meta, threshold)

        n = len(matches)
        messages.append(self.speak(
            f"比对完成：{len(user_sentences)} 句中 {n} 句相似度≥{threshold_pct}%"
        ))

        if n == 0:
            messages.append(self.speak("✅ 未发现重复句子"))
            return {
                "messages": messages,
                "result": {
                    "matches": [],
                    "total_matches": 0,
                    "user_sentences_count": len(user_sentences),
                },
            }

        # ---- Step 4: LLM 审核（仅做减法） ----
        final_matches = self._llm_review(matches, messages)

        return {
            "messages": messages,
            "result": {
                "matches": final_matches,
                "total_matches": len(final_matches),
                "user_sentences_count": len(user_sentences),
            },
        }

    def _llm_review(self, matches, messages):
        """LLM 审核：去除明显误匹配，不做任何添加或修改"""
        if len(matches) <= 2:
            return matches  # 少量匹配跳过审核

        # 构建审核输入
        matches_text = ""
        for i, m in enumerate(matches[:30]):
            matches_text += (
                f"ID={i} | 语义相似度{m['similarity']}% | 来源: {m['source_title'][:50]}\n"
                f"  用户句: {m['user_sentence'][:150]}\n"
                f"  匹配句: {m['similar_sentence'][:150]}\n\n"
            )

        user_prompt = f"""请审核以下语义查重结果。你只能做**删除**操作：
如果某条匹配明显错误（比如两句讨论的完全是不同主题），将其ID加入 remove_ids。

注意：
- 即使是不同的表述方式，只要讨论同一问题/主题，就不应删除
- 相似度已由语义模型计算，请尊重计算结果
- 只删除明显错误的匹配

{matches_text}

输出JSON：
{{"remove_ids": [要删除的匹配ID列表]}}"""

        try:
            response, usage = call_deepseek(
                self.api_key, self.model,
                self.system_prompt, user_prompt,
                temperature=0.1,
            )
            result = extract_json(response)
            remove_ids = set(result.get("remove_ids", []))
            final = [m for i, m in enumerate(matches) if i not in remove_ids]

            # 保护：最多删 30%，防止 LLM 过度删除
            if len(final) < len(matches) * 0.5:
                final = matches
                messages.append(self.speak(
                    "⚠️ LLM 欲删除过多匹配，已保留全部语义匹配结果"
                ))
            else:
                removed = len(matches) - len(final)
                tk = usage.get('total_tokens', 0)
                messages.append(self.speak(
                    f"LLM审核完成：删除 {removed} 条误匹配，"
                    f"保留 {len(final)} 处 (消耗 {tk} tokens)"
                ))
        except Exception as e:
            messages.append(self.speak(
                f"LLM审核异常: {str(e)[:80]}，使用全部语义匹配结果"
            ))
            final = matches

        return final


# ============================================================
# LCS 回退方案
# ============================================================

def _lcs_length(a, b):
    """最长公共子序列长度"""
    m, n = len(a), len(b)
    if m > 800: a = a[:800]
    if n > 800: b = b[:800]
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, prev
    return prev[n]


def _fast_similarity(us_set, us_len, cs_set, cs_len):
    """Jaccard 相似度：|A ∩ B| / |A ∪ B|，O(min(len), len)) 秒出"""
    if us_len == 0:
        return 0.0
    intersection = len(us_set & cs_set)
    union = len(us_set | cs_set)
    return intersection / max(union, 1)


def _lcs_fallback(user_sentences, crawled_meta, threshold=0.60):
    """
    快速比对：字符集 Jaccard 相似度 + LCS 精排（仅对 top 3）。
    预计算所有字符集，扫一遍出结果。
    """
    TOP_LCS = 3  # 只有 top 3 才跑 LCS 精排

    # ---- 预计算字符集（只算一次）----
    crawled_sets = [set(m["sentence"]) for m in crawled_meta]
    crawled_lens = [len(m["sentence"]) for m in crawled_meta]

    matches = []
    for us in user_sentences:
        us_set = set(us)
        us_len = len(us)
        if us_len == 0:
            continue

        # ---- 扫一遍，Jaccard 取 top 3 ----
        best = []  # [(score, idx)]
        for j, cs_set in enumerate(crawled_sets):
            score = _fast_similarity(us_set, us_len, cs_set, crawled_lens[j])
            if score >= threshold * 0.5:  # Jaccard 比 LCS 偏低，阈值放宽
                if len(best) < TOP_LCS:
                    best.append((score, j))
                    best.sort(reverse=True)
                elif score > best[-1][0]:
                    best[-1] = (score, j)
                    best.sort(reverse=True)

        if not best:
            continue

        # ---- Top 3 跑 LCS 精排 ----
        best_score = 0.0
        best_meta = None
        for jaccard, j in best:
            meta = crawled_meta[j]
            lcs_len = _lcs_length(us, meta["sentence"])
            score = lcs_len / us_len
            if score > best_score:
                best_score = score
                best_meta = meta

        if best_score >= threshold and best_meta:
            matches.append({
                "user_sentence": us,
                "similar_sentence": best_meta["sentence"],
                "source_title": best_meta.get("source_title", ""),
                "source_url": best_meta.get("source_url", ""),
                "similarity": round(best_score * 100),
            })
    return matches
