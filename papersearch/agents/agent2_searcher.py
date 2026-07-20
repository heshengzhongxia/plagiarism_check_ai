"""
Agent2: 猎手·艾瑞 - 网络检索
输入：关键词列表（仅来自agent1）
输出：爬取到的论文全文（传给agent3，不直接传agent6）
"""
from agents.base import BaseAgent
from llm_client import call_deepseek, extract_json


class Agent2Searcher(BaseAgent):

    def think(self, input_data, context=None):
        messages = []

        keywords = input_data.get("keywords", [])
        messages.append(self.speak(f"检索关键词: {', '.join(keywords[:8])}"))

        # 真实API检索
        real_papers_list = []
        if context and context.get("real_papers"):
            rp = context["real_papers"]
            real_papers_list = rp.get("papers", [])
            by_src = ', '.join(f'{k}:{v}' for k, v in rp.get('by_source', {}).items() if v > 0)
            messages.append(self.speak(
                f"真实论文库返回 {len(real_papers_list)} 篇（{by_src}）"
            ))

        total_real = len(real_papers_list)

        # 无真实论文时让LLM补充
        if total_real == 0:
            user_prompt = f"""请基于关键词列出相关论文（5-8篇）：{', '.join(keywords)}"""
            try:
                response, usage = call_deepseek(
                    self.api_key, self.model, self.system_prompt,
                    user_prompt, temperature=self.temperature,
                )
                result = extract_json(response)
                papers = result.get("papers", result.get("matched_papers", []))
                messages.append(self.speak(f"LLM补充 {len(papers)} 篇"))
                return {"messages": messages, "result": {
                    "papers": papers, "total_found": len(papers),
                }}
            except Exception as e:
                messages.append(self.speak(f"检索异常: {e}"))
                return {"messages": messages, "result": {
                    "papers": [], "total_found": 0,
                }}

        # 以真实论文为主
        papers_text = ""
        for i, p in enumerate(real_papers_list):
            papers_text += (
                f"[{i+1}] {p.get('title','')}\n"
                f"    摘要: {p.get('abstract','')[:300]}\n"
                f"    链接: {p.get('url','')}\n"
                f"    来源: {p.get('source','')}\n\n"
            )

        user_prompt = f"""以下是 {total_real} 篇检索到的论文，请整理每篇的完整信息。
关键词: {', '.join(keywords)}

{papers_text}

请保留所有 {total_real} 篇论文，输出JSON。"""

        try:
            response, usage = call_deepseek(
                self.api_key, self.model, self.system_prompt,
                user_prompt, temperature=self.temperature,
            )
            result = extract_json(response)
            llm_papers = result.get("papers", result.get("matched_papers", []))

            # 以真实数据为底合并，尽可能保留更多文本
            final_papers = []
            for rp in real_papers_list:
                paper = dict(rp)
                # 合并标题+摘要作为"全文"（免费API通常只有摘要）
                title_text = paper.get("title", "")
                abstract = paper.get("abstract", "")
                paper["full_text"] = f"{title_text}。{abstract}" if abstract else title_text
                # 找LLM补充的分析
                for lp in llm_papers:
                    if (lp.get("url") and rp.get("url") and lp["url"] == rp["url"]) or \
                       (lp.get("title", "")[:30] == rp.get("title", "")[:30]):
                        paper["full_text"] = lp.get("full_text", paper.get("abstract", ""))
                        break
                final_papers.append(paper)

            messages.append(self.speak(
                f"整理完成：{len(final_papers)} 篇论文 (消耗 {usage.get('total_tokens', 0)} tokens)"
            ))

            return {"messages": messages, "result": {
                "papers": final_papers,
                "total_found": len(final_papers),
            }}

        except Exception as e:
            messages.append(self.speak(f"分析异常: {e}，使用原始数据"))
            for rp in real_papers_list:
                rp["full_text"] = f"{rp.get('title','')}。{rp.get('abstract','')}"
            return {"messages": messages, "result": {
                "papers": real_papers_list,
                "total_found": total_real,
            }}
