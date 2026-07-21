"""
设置路由：API Key 的保存和读取（支持 6 个 Agent 独立 Key）
"""
import os
import json
from flask import Blueprint, request, jsonify
from dotenv import set_key as dotenv_set_key

from config import BASE_DIR, AGENTS_CONFIG

settings_bp = Blueprint('settings', __name__)

# .env 写入位置：exe 旁边（打包后）或 config.py 同级（开发模式）
_ENV_FILE = os.path.join(os.path.dirname(BASE_DIR), ".env")
if not os.path.exists(os.path.dirname(_ENV_FILE)):
    _ENV_FILE = os.path.join(BASE_DIR, ".env")


def _update_memory_keys(keys: list[str]):
    """运行时更新内存中 6 个 Agent 的 API Key"""
    agent_ids = sorted(AGENTS_CONFIG.keys())
    for i, agent_id in enumerate(agent_ids):
        if i < len(keys) and keys[i]:
            AGENTS_CONFIG[agent_id]["api_key"] = keys[i]


@settings_bp.route("/api/settings", methods=["GET"])
def get_settings():
    """返回当前各 Agent 的 API Key（脱敏）"""
    agent_ids = sorted(AGENTS_CONFIG.keys())
    keys_full = []
    keys_masked = []
    for aid in agent_ids:
        key = AGENTS_CONFIG[aid].get("api_key", "")
        keys_full.append(key)
        if key and len(key) > 12:
            keys_masked.append(key[:8] + "****" + key[-4:])
        elif key:
            keys_masked.append("****")
        else:
            keys_masked.append("")
    return jsonify({
        "keys": keys_full,
        "keys_masked": keys_masked,
        "any_key": any(keys_full),
    })


@settings_bp.route("/api/settings", methods=["POST"])
def save_settings():
    """保存 API Keys 到 .env 并立即生效。
    支持两种格式：
    - {"keys": ["k1","k2","k3","k4","k5","k6"]}  分别设置
    - {"api_key": "sk-xxx"}                        所有 Agent 共用
    """
    data = request.get_json(silent=True) or {}
    keys = data.get("keys")
    single_key = (data.get("api_key") or "").strip()

    if keys and isinstance(keys, list) and len(keys) == 6:
        # 6 个独立 Key
        for i, k in enumerate(keys):
            k = (k or "").strip()
            if k:
                dotenv_set_key(_ENV_FILE, f"DEEPSEEK_API_KEY_AGENT{i+1}", k)
        _update_memory_keys(keys)
        masked = [(k[:8] + "****" + k[-4:]) if len(k) > 12 else ("****" if k else "") for k in keys]
        return jsonify({"ok": True, "keys_masked": masked})

    elif single_key:
        # 单个 Key → 所有 Agent 共用
        for i in range(1, 7):
            dotenv_set_key(_ENV_FILE, f"DEEPSEEK_API_KEY_AGENT{i}", single_key)
        _update_memory_keys([single_key] * 6)
        m = single_key[:8] + "****" + single_key[-4:] if len(single_key) > 12 else "****"
        return jsonify({"ok": True, "keys_masked": [m] * 6})

    else:
        return jsonify({"error": "请提供 keys 数组(6个) 或 api_key 字段"}), 400
