"""
Agent6: 整合·尤娜 - 生成查重报告
输入：用户全文 + 匹配结果 + 修改方案 + 总体建议
处理：生成.docx文件 + JSON报告摘要
输出：报告文件路径 + 摘要数据
"""
import os
import json
import time
from agents.base import BaseAgent
from llm_client import call_deepseek, extract_json

from services.docx_generator import generate_docx
class Agent6Integrator(BaseAgent):

    def think(self, input_data, context=None):
        messages = []

        user_full_text = input_data.get("user_full_text", "")
        matches = input_data.get("matches", [])
        modifications = input_data.get("modifications", [])
        overall_suggestions = input_data.get("overall_suggestions", [])
        aigc_rate = input_data.get("aigc_rate", 0)
        aigc_analysis = input_data.get("aigc_analysis", "")

        n_matches = len(matches)
        n_mods = len(modifications)
        n_sug = len(overall_suggestions)

        messages.append(self.speak(
            f"输入：用户全文 {len(user_full_text)} 字、{n_matches} 处匹配、{n_mods} 条修改方案、{n_sug} 条建议"
        ))

        messages.append(self.speak("正在生成查重报告..."))

        # 生成docx
        report_dir = context.get("report_dir", os.path.join(os.path.dirname(__file__), "..", "reports")) if context else os.path.join(os.path.dirname(__file__), "..", "reports")
        os.makedirs(report_dir, exist_ok=True)

        docx_path, docx_error = generate_docx(
            user_full_text, matches, modifications, overall_suggestions,
            report_dir, aigc_rate, aigc_analysis
        )

        if docx_error:
            messages.append(self.speak(f"Word生成异常: {docx_error}"))
        else:
            messages.append(self.speak(f"查重报告已生成：{os.path.basename(docx_path)}"))

        # LLM生成报告摘要
        summary_prompt = f"""请生成查重报告摘要：

用户论文 {len(user_full_text)} 字 | 重复句 {n_matches} 处 | 修改方案 {n_mods} 条 | 建议 {n_sug} 条

{str(matches)[:1000]}

请给出风险评估和综合总结。输出JSON：
{{"summary": "查重结果概述", "risk_assessment": "风险等级评估", "report_title": "报告标题"}}"""

        try:
            response, usage = call_deepseek(
                self.api_key, self.model, self.system_prompt,
                summary_prompt, temperature=0.2,
            )
            result = extract_json(response)
            messages.append(self.speak(
                f"报告完成：{result.get('risk_assessment','')} (消耗 {usage.get('total_tokens', 0)} tokens)"
            ))
        except Exception as e:
            messages.append(self.speak(f"摘要生成异常: {e}"))
            result = {
                "summary": f"共检测到 {n_matches} 处重复句子",
                "risk_assessment": "未知",
                "report_title": "查重报告",
            }

        result["docx_path"] = docx_path
        result["docx_filename"] = os.path.basename(docx_path) if docx_path else None
        result["total_matches"] = n_matches
        result["total_modifications"] = n_mods
        result["total_suggestions"] = n_sug
        result["aigc_rate"] = aigc_rate
        result["aigc_analysis"] = aigc_analysis
        result["matches"] = matches
        result["modifications"] = modifications
        result["overall_suggestions"] = overall_suggestions

        return {"messages": messages, "result": result}
