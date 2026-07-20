"""
DeepSeek API 调用封装
使用 OpenAI 兼容 SDK 调用 DeepSeek Chat API
"""
import json
import re
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def call_deepseek(api_key, model, system_prompt, user_message, history=None, temperature=0.3):
    """
    调用 DeepSeek Chat API

    Args:
        api_key: DeepSeek API密钥
        model: 模型名 (deepseek-chat / deepseek-reasoner)
        system_prompt: 系统提示词
        user_message: 用户输入内容
        history: 可选的历史消息列表 [{"role": "user/assistant", "content": "..."}]
        temperature: 生成温度 (0.0-1.0)

    Returns:
        (response_text: str, usage: dict)
        usage: {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
    """
    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=60.0)

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=4096,
    )

    text = response.choices[0].message.content
    usage = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        "total_tokens": response.usage.total_tokens if response.usage else 0,
    }

    return text, usage


def extract_json(text):
    """
    从LLM回复中提取JSON对象。
    处理模型在JSON前后添加markdown代码块或额外文本的情况。

    Args:
        text: LLM回复的原始文本

    Returns:
        dict: 解析后的JSON对象

    Raises:
        ValueError: 无法提取有效的JSON
    """
    if not text or not text.strip():
        raise ValueError("LLM回复为空")

    # 尝试直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { 到最后一个 } 之间的内容
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从回复中提取有效的JSON:\n{text[:500]}")
