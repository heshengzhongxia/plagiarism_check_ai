"""
Agent基类 - 定义Agent的通用行为：think、verify、discuss、speak
"""
import json
import time
from llm_client import call_deepseek, extract_json


class BaseAgent:
    """所有Agent的基类，提供验证、讨论、发言等通用能力"""

    def __init__(self, config):
        self.id = config["id"]
        self.name = config["name"]
        self.role = config["role"]
        self.emoji = config["emoji"]
        self.color = config.get("color", "#5b9bd5")
        self.api_key = config["api_key"]
        self.model = config.get("model", "deepseek-chat")
        self.temperature = config.get("temperature", 0.3)
        self.system_prompt = config["system_prompt"]

    # ---- 发言 ----

    def speak(self, message):
        """生成一条发言记录"""
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "emoji": self.emoji,
            "color": self.color,
            "message": message,
            "timestamp": time.time(),
        }

    def append_message(self, task_store, task_id, message):
        """向任务的对话记录追加一条消息"""
        if task_id in task_store and "conversation" in task_store[task_id]:
            task_store[task_id]["conversation"].append(message)

    # ---- 核心方法 ----

    def think(self, input_data, context=None):
        """
        主处理逻辑。子类必须重写此方法。

        Args:
            input_data: 上游Agent的输出数据
            context: 可选的上下文信息

        Returns:
            dict: {"messages": [发言列表], "result": {处理结果}}
        """
        raise NotImplementedError(f"{self.name} 未实现 think() 方法")

    # ---- 验证 ----

    def verify(self, received_data):
        """
        验证上游数据的准确率和完整性。
        调用LLM评估数据质量。

        Args:
            received_data: 上游Agent的输出数据（dict）

        Returns:
            (score: float, feedback: str)
        """
        prompt = f"""请严格评估以下Agent输出数据的准确性和完整性：

待评估数据：
{json.dumps(received_data, ensure_ascii=False, indent=2)}

评估标准：
1. 数据是否与原始任务相关（关键词是否准确、分析是否合理）
2. 字段是否完整（所有必要字段是否都有合理值）
3. 内容是否有逻辑错误或明显矛盾
4. JSON结构是否符合要求

请按JSON格式回复：
{{"score": 85, "feedback": "评估说明（score低于60时必须指出具体问题及改进方向）"}}

只输出JSON，不要加其他内容。"""

        try:
            response, _ = call_deepseek(
                self.api_key, self.model,
                "你是数据质量评估专家。严格但公正地评估Agent输出的准确性。低于60分必须给出具体问题和改进方向。",
                prompt,
                temperature=0.1,
            )
            result = extract_json(response)
            score = int(result.get("score", 70))
            feedback = result.get("feedback", "无具体反馈")
            return min(100, max(0, score)), feedback
        except Exception as e:
            # 验证失败时默认通过（避免因LLM调用异常而阻塞流水线）
            return 70, f"验证异常（{str(e)[:100]}），默认通过"

    # ---- 讨论 ----

    def discuss(self, downstream_feedback, my_original_output):
        """
        与下游Agent讨论，根据反馈修正自己的输出。

        Args:
            downstream_feedback: 下游Agent的反馈意见
            my_original_output: 本Agent的原始输出数据

        Returns:
            dict: 修正后的输出数据
        """
        prompt = f"""你的下游Agent对你的工作提出了质疑，请认真考虑并修正：

【你的原始输出】
{json.dumps(my_original_output, ensure_ascii=False, indent=2)}

【下游Agent的反馈】
{downstream_feedback}

请修正你的输出，按JSON格式回复修正后的完整结果。
- 如果反馈合理，修正对应部分
- 如果反馈不合理，在数据中保留你的判断并简要说明理由
- 只输出JSON"""

        try:
            response, _ = call_deepseek(
                self.api_key, self.model,
                self.system_prompt + "\n你正在与下游Agent讨论。请认真对待反馈，合理则修正，不合理则坚持并说明。",
                prompt,
                temperature=self.temperature,
            )
            return extract_json(response)
        except Exception as e:
            # 讨论失败时返回原始输出
            return my_original_output

    # ---- 完整执行流程 ----

    def run_with_verification(self, task_store, task_id, input_data,
                              previous_output=None, previous_agent=None,
                              context=None):
        """
        执行Agent主流程：验证（必要时讨论）→ 处理 → 输出。
        所有发言自动追加到任务对话记录。

        Args:
            task_store: 全局任务存储字典
            task_id: 当前任务ID
            input_data: 输入数据
            previous_output: 上游Agent的原始输出（用于验证）
            previous_agent: 上游Agent实例（用于讨论）
            context: 额外上下文（如真实论文库数据）

        Returns:
            dict: 处理结果
        """
        # 步骤1: 确认收到数据
        msg = self.speak("收到上游数据，准备开始处理...")
        self.append_message(task_store, task_id, msg)

        # 步骤2: 验证上游数据（首个Agent跳过）
        if previous_output is not None and previous_agent is not None:
            msg = self.speak("正在验证上游数据的准确性...")
            self.append_message(task_store, task_id, msg)

            score, feedback = self.verify(previous_output)

            passed = score >= 60
            emoji_status = "✅" if passed else "❌"
            msg = self.speak(
                f"验证完成：准确率 {score}%。"
                f"{emoji_status} {'通过验证，开始处理。' if passed else '不达标！问题：' + feedback}"
            )
            self.append_message(task_store, task_id, msg)

            if not passed:
                # ---- 触发一轮讨论 ----
                msg = previous_agent.speak(
                    f"收到来自 {self.emoji} {self.name} 的反馈：\"{feedback}\"。正在重新检查并修正..."
                )
                self.append_message(task_store, task_id, msg)

                corrected = previous_agent.discuss(feedback, previous_output)

                msg = previous_agent.speak("已修正完毕，重新提交数据。")
                self.append_message(task_store, task_id, msg)

                # 重新验证
                score2, feedback2 = self.verify(corrected)
                msg = self.speak(
                    f"重新验证：准确率 {score2}%。"
                    f"{'✅ 通过，继续处理。' if score2 >= 60 else '⚠️ 仍不达标但继续流程。'}"
                )
                self.append_message(task_store, task_id, msg)

                # 使用修正后的数据
                input_data = corrected

        # 步骤3: Agent核心处理
        msg = self.speak(f"正在执行 {self.role} 任务...")
        self.append_message(task_store, task_id, msg)

        result = self.think(input_data, context=context)

        # 输出思考过程中的发言
        if result.get("messages"):
            for m in result["messages"]:
                self.append_message(task_store, task_id, m)

        # 步骤4: 完成
        msg = self.speak(f"{self.role}任务完成 ✅")
        self.append_message(task_store, task_id, msg)

        return result.get("result", result)
