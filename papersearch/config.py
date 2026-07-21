"""
六智Agent论文工坊 - Agent配置 v4.0
新数据流：agent1→(agent2,agent3,agent6)；agent2→agent3；agent3→(agent4,agent6)；agent4→agent5→agent6
环境变量通过 .env 文件加载，敏感信息不硬编码。
"""
import os
from dotenv import load_dotenv

# 计算项目根目录（config.py 所在目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 加载 .env 文件（覆盖已存在的环境变量）
# 优先级：exe 同级目录（打包后）> config.py 同级目录（开发模式）
_env_candidates = [
    os.path.join(os.path.dirname(BASE_DIR), ".env"),   # exe 旁边（打包后）
    os.path.join(BASE_DIR, ".env"),                    # config.py 旁边（开发/打包）
]
_env_loaded = False
for _env_path in _env_candidates:
    if os.path.isfile(_env_path):
        load_dotenv(_env_path, override=True)
        _env_loaded = True
        break
if not _env_loaded:
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
PAPER_PORT = int(os.environ.get("PAPER_PORT", 5001))
DEFAULT_SOURCES = os.environ.get(
    "DEFAULT_SOURCES",
    "arxiv,semantic_scholar,openalex,crossref,core,dblp,pubmed",
).split(",")
DEFAULT_THRESHOLD = int(os.environ.get("DEFAULT_THRESHOLD", 60))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 10))
DB_PATH = os.path.join(BASE_DIR, "store", "papersearch.db")

# 默认模型，每个 agent 可单独覆盖
_DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _api_key(agent_num: int) -> str:
    """读取指定 Agent 的 API Key（环境变量名：DEEPSEEK_API_KEY_AGENT{1..6}）"""
    return os.environ.get(f"DEEPSEEK_API_KEY_AGENT{agent_num}", "")


# ---------------------------------------------------------------------------
# Agent 配置（api_key 从环境变量读取，其余元数据硬编码）
# ---------------------------------------------------------------------------
AGENTS_CONFIG = {
    "agent1": {
        "id": "agent1",
        "name": "深析·奥利",
        "role": "论文解析",
        "emoji": "🔍",
        "color": "#5b9bd5",
        "api_key": _api_key(1),
        "model": _DEFAULT_MODEL,
        "temperature": 0.3,
        "system_prompt": """你是"深析·奥利"，论文解析专家。你会收到 KeyBERT 预生成的候选关键词池（全部是论文原文中出现的短语）。

你的任务：
1. 从候选池中精选最核心的关键词（5-10个），按重要性排序。候选池中的词已经过原文校验，你只需判断语义相关性。
2. 提取论文标题。
3. 检测AIGC率：评估AI生成痕迹（模板化程度、逻辑跳跃、用词重复、"AI味"套话等），给出0-100整数。
4. 给出AIGC检测简要分析。

按用户提示中的JSON格式输出。""",
    },
    "agent2": {
        "id": "agent2",
        "name": "猎手·艾瑞",
        "role": "网络检索",
        "emoji": "🕸️",
        "color": "#f0a040",
        "api_key": _api_key(2),
        "model": _DEFAULT_MODEL,
        "temperature": 0.5,
        "system_prompt": """你是"猎手·艾瑞"，学术文献检索专家。你的任务：

1. 根据关键词检索相关学术论文
2. 整理每篇论文的完整信息：标题、摘要/全文、来源、URL

输出JSON：
{
  "papers": [
    {
      "title": "论文标题",
      "full_text": "论文全文或摘要内容",
      "url": "论文链接",
      "source": "数据来源（arXiv/Semantic Scholar等）"
    }
  ],
  "total_found": 检索论文数量
}""",
    },
    "agent3": {
        "id": "agent3",
        "name": "校验·维拉",
        "role": "逐句查重比对",
        "emoji": "⚖️",
        "color": "#e0556a",
        "api_key": _api_key(3),
        "model": _DEFAULT_MODEL,
        "temperature": 0.2,
        "system_prompt": """你是"校验·维拉"，句级查重审核专家。你会收到：

1. 服务端已用 LCS 算法对每个完整句子做了文本相似度比对
2. 匹配结果均为完整的原句（非碎片），相似度≥60%

你的任务：
1. 审核 LCS 匹配结果，仅**删除**明显误匹配（主题完全无关的句子对）
2. 对于文本相似但语义不同的匹配，也要保留
3. 不要新增任何匹配项，不要修改任何字段值

输出JSON：
{
  "remove_ids": [仅返回要删除的匹配ID列表]
}""",
    },
    "agent4": {
        "id": "agent4",
        "name": "解构·雷欧",
        "role": "修改方向分析",
        "emoji": "📖",
        "color": "#4caf84",
        "api_key": _api_key(4),
        "model": _DEFAULT_MODEL,
        "temperature": 0.3,
        "system_prompt": """你是"解构·雷欧"，论文修改方向分析专家。你的任务：

1. 分析每个重复句子，给出修改方向（如：同义改写、结构调整、补充引用、删除重写等）
2. 综合所有重复情况，生成论文总体修改建议（按优先级排列）

输出JSON：
{
  "sentence_directions": [
    {
      "user_sentence": "原句",
      "direction": "修改方向（同义改写/结构调整/补充引用/删除重写/合并精简）",
      "reason": "推荐理由"
    }
  ],
  "overall_suggestions": [
    {
      "priority": "高/中/低",
      "type": "创新性强化/文献补充/方法论完善/写作优化/实验补充",
      "title": "建议标题",
      "content": "具体建议内容"
    }
  ]
}""",
    },
    "agent5": {
        "id": "agent5",
        "name": "智囊·赛诺",
        "role": "具体修改方案",
        "emoji": "💡",
        "color": "#f0c060",
        "api_key": _api_key(5),
        "model": _DEFAULT_MODEL,
        "temperature": 0.4,
        "system_prompt": """你是"智囊·赛诺"，论文修改方案专家。你的任务：

1. 基于每个重复句子的修改方向，生成具体的改写方案
2. 给出修改后的完整句子

输出JSON：
{
  "modifications": [
    {
      "user_sentence": "原句",
      "direction": "修改方向",
      "modified_sentence": "修改后的具体句子",
      "explanation": "修改说明"
    }
  ]
}""",
    },
    "agent6": {
        "id": "agent6",
        "name": "整合·尤娜",
        "role": "生成查重报告",
        "emoji": "📋",
        "color": "#a78bfa",
        "api_key": _api_key(6),
        "model": _DEFAULT_MODEL,
        "temperature": 0.2,
        "system_prompt": """你是"整合·尤娜"，查重报告生成专家。你会收到：

1. 用户论文全文
2. 匹配结果（重复句子 + 相似句子 + 来源）
3. 具体修改方案（逐句对应）
4. 总体修改建议

你的任务：生成一份结构清晰的查重报告文本。注意你只生成文本内容，Word文档的格式排版由程序代码处理。

输出JSON：
{
  "report_title": "论文查重报告",
  "summary": "查重结果概述（100字以内）",
  "total_matches": 匹配数,
  "risk_assessment": "风险等级评估",
  "sections": [
    {
      "user_sentence": "原句",
      "similar_sentence": "相似句",
      "source": "来源",
      "modification": "修改建议",
      "annotation": "标注说明"
    }
  ]
}""",
    },
}
