# app/config.py
"""
Her 的配置中心：
- 所有敏感信息一律从环境变量读取（不写在代码里）
- 方便本地 (.env) + Cloud Run 环境变量统一管理
"""

import os
from functools import lru_cache


# ========= 基础配置 =========

# 从环境变量读取 OpenAI API Key（本地由 .env 提供，Cloud Run 在控制台或 gcloud 里配置）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# GitHub Personal Access Token（用于自我更新 / 自我修复时访问仓库）
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Her 的代码仓库
GITHUB_REPO = os.getenv("GITHUB_REPO", "panzhihe998/her-serve")

# 是否启用自动更新（自我更新系统开关）
AUTO_UPDATE_ENABLED = os.getenv("AUTO_UPDATE_ENABLED", "true").lower() == "true"

# Her 当前版本号（你可以随便改）
HER_VERSION = "0.1.0"


@lru_cache
def debug_config() -> dict:
    """
    方便在调试的时候打印当前配置状态（不会打印真正的 Key，只打印是否存在）。
    """
    return {
        "OPENAI_CONFIGURED": bool(OPENAI_API_KEY),
        "GITHUB_CONFIGURED": bool(GITHUB_TOKEN),
        "GITHUB_REPO": GITHUB_REPO,
        "AUTO_UPDATE_ENABLED": AUTO_UPDATE_ENABLED,
        "HER_VERSION": HER_VERSION,
    }
