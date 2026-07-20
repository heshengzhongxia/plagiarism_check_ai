"""
Agent5: 智囊·赛诺 - 具体修改方案
输入：逐句修改方向 + 总体建议（来自agent4）
输出：每句的具体改写方案（传给agent6）
"""
from agents.base import BaseAgent
from llm_client import call_deepseek, extract_json


class Agent5Suggester(BaseAgent):

    def think(self, input_data, context=None):
        messages = []

        directions = input_data.get("sentence_directions", [])
        overall = input_data.get("overall_suggestions", [])
        n = len(directions)

        messages.append(self.speak(f"收到 {n} 条修改方向，生成具体改写方案..."))

        if n == 0:
            messages.append(self.speak("无修改方向，跳过"))
            return {"messages": messages, "result": {
                "modifications": [],
                "overall_suggestions": overall,
            }}

        dirs_text = ""
        for i, d in enumerate(directions[:25]):
            dirs_text += (
                f"[{i+1}] 原句: {d.get('user_sentence','')[:120]}\n"
                f"    修改方向: {d.get('direction','')}\n"
                f"    理由: {d.get('reason','')[:80]}\n\n"
            )

        user_prompt = f"""请为以下 {n} 个重复句子生成具体修改方案：

{dirs_text}

为每个句子给出修改后的完整句子，使其既保留原意又降低重复率。"""

        try:
            response, usage = call_deepseek(
                self.api_key, self.model, self.system_prompt,
                user_prompt, temperature=self.temperature,
            )
            result = extract_json(response)

            mods = result.get("modifications", [])
            messages.append(self.speak(
                f"生成 {len(mods)} 条具体修改方案 (消耗 {usage.get('total_tokens', 0)} tokens)"
            ))
            # 透传总体建议
            result["overall_suggestions"] = overall
            result["token_usage"] = usage

        except Exception as e:
            messages.append(self.speak(f"生成异常: {e}"))
            result = {
                "modifications": [],
                "overall_suggestions": overall,
            }

        return {"messages": messages, "result": result}
