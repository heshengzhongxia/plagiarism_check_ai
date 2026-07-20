"""
Agent1: 深析·奥利 - 论文解析
纯 LLM 提取：关键词 + 标题 + AIGC（一次调用，秒出）
输出：论文全文纯文本（传给agent2、agent3、agent6）
"""
from agents.base import BaseAgent
from llm_client import call_deepseek, extract_json


class Agent1Parser(BaseAgent):

    def think(self, input_data, context=None):
        messages = []
        paper_text = input_data if isinstance(input_data, str) else str(input_data)
        full_text = paper_text.strip()

        messages.append(self.speak(
            f"正在解析论文全文，共 {len(full_text)} 字符..."
        ))

        user_prompt = f"""请解析以下论文，完成三项任务：

【论文全文】
{full_text[:5000]}

【任务】
1. 提取 5-10 个核心关键词，按重要性排序。
   **严格要求**：每个关键词必须是论文原文中真实出现的原词或短语，不得自己编造或改写。
2. 提取论文标题。
3. 检测 AIGC 率（0-100 整数，评估 AI 生成痕迹：模板化程度、逻辑跳跃、用词重复、"AI味"套话等）。
4. 给出 AIGC 检测简要分析。

输出JSON：
{{"title":"论文标题","keywords":["关键词1","关键词2",...],"aigc_rate":整数,"aigc_analysis":"简要分析"}}"""

        try:
            response, usage = call_deepseek(
                self.api_key, self.model,
                self.system_prompt, user_prompt,
                temperature=self.temperature,
            )
            result = extract_json(response)

            # 原文校验：只保留在原文中真实出现的关键词
            raw_kw = result.get("keywords", [])
            validated = [kw.strip() for kw in raw_kw if kw.strip() and kw.strip() in full_text]

            # 如果被剔除太多，用 LLM 原文作为兜底
            if len(validated) < 3:
                validated = raw_kw

            result["keywords"] = validated[:10]
            result["full_text"] = full_text

            tk = usage.get('total_tokens', 0)
            kw_list = result.get("keywords", [])
            kw_str = ', '.join(kw_list)
            aigc = result.get("aigc_rate", "?")
            messages.append(self.speak(
                f"解析完成：标题「{result.get('title','')[:40]}」"
                f"| 关键词({len(kw_list)}个): {kw_str}"
                f"| AIGC率: {aigc}%"
            ))
            if result.get("aigc_analysis"):
                messages.append(self.speak(
                    f"AIGC分析: {str(result['aigc_analysis'])[:120]}"
                ))
            result["token_usage"] = usage

        except Exception as e:
            messages.append(self.speak(f"LLM解析异常: {str(e)[:100]}"))
            result = {
                "title": full_text[:80],
                "keywords": [],
                "full_text": full_text,
            }

        return {"messages": messages, "result": result}
