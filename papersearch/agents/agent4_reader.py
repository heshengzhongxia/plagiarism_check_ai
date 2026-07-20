"""
Agent4: 解构·雷欧 - 修改方向分析
输入：匹配结果（来自agent3）
输出：逐句修改方向 + 论文总体修改建议（传给agent5）
"""
from agents.base import BaseAgent
from llm_client import call_deepseek, extract_json


class Agent4Reader(BaseAgent):

    def think(self, input_data, context=None):
        messages = []

        matches = input_data.get("matches", [])
        n = len(matches)
        messages.append(self.speak(f"收到 {n} 处重复句子，分析修改方向..."))

        if n == 0:
            messages.append(self.speak("无重复句子，跳过分析"))
            return {"messages": messages, "result": {
                "sentence_directions": [],
                "overall_suggestions": [{
                    "priority": "低", "type": "写作优化",
                    "title": "未检测到重复",
                    "content": "论文未发现明显重复，建议关注文献引用规范。"
                }],
            }}

        matches_text = ""
        for i, m in enumerate(matches[:25]):
            matches_text += (
                f"[{i+1}] 原句: {m.get('user_sentence','')[:150]}\n"
                f"    相似: {m.get('similar_sentence','')[:120]}\n"
                f"    来源: {m.get('source_title','')[:50]}\n\n"
            )

        user_prompt = f"""请为以下 {n} 处重复句子分析修改方向，并生成总体建议：

{matches_text}

为每个句子给出修改方向（同义改写/结构调整/补充引用/删除重写/合并精简），
并综合所有情况给出论文总体修改建议（按优先级排列）。"""

        try:
            response, usage = call_deepseek(
                self.api_key, self.model, self.system_prompt,
                user_prompt, temperature=self.temperature,
            )
            result = extract_json(response)

            n_dirs = len(result.get("sentence_directions", []))
            n_sug = len(result.get("overall_suggestions", []))
            messages.append(self.speak(
                f"分析完成：{n_dirs} 条修改方向，{n_sug} 条总体建议 (消耗 {usage.get('total_tokens', 0)} tokens)"
            ))
            result["token_usage"] = usage

        except Exception as e:
            messages.append(self.speak(f"分析异常: {e}"))
            result = {
                "sentence_directions": [],
                "overall_suggestions": [],
            }

        return {"messages": messages, "result": result}
