# app/main.py

from __future__ import annotations
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config
from app.self_update import apply_file_update, make_update_plan
from app.self_heal import SelfHealer  # ⬅ 自我修复引擎

# ----------------------------------------
# FastAPI APP
# ----------------------------------------

app = FastAPI(
    title="Her Server",
    description="Core backend for Her — voice, memory, emotion, self-update.",
    version=config.HER_VERSION if hasattr(config, "HER_VERSION") else "1.0.0",
)

# CORS – allow frontend / tools to call your API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 可以以后再收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------
# 全局实例（自我修复）
# ----------------------------------------

self_healer = SelfHealer()

# ----------------------------------------
# Request Models
# ----------------------------------------

class ChatRequest(BaseModel):
    user_id: str
    input: str
    mode: str = "text"


class SelfUpdateRequest(BaseModel):
    target_file: str          # 相对路径，例如: app/self_heal.py
    new_content: str          # 新文件内容（完整覆盖）
    commit_message: str = "chore: self-update"


class SelfUpdatePlanRequest(BaseModel):
    target_file: str          # app/self_heal.py
    goal: str                 # “加强错误恢复能力”之类


# ----------------------------------------
# Routes
# ----------------------------------------

@app.get("/")
def root():
    """
    根路径，用于健康检查&方便测试
    """
    return {
        "message": "hello — Her is online on Cloud Run.",
        "health": "/health",
        "chat_api": "/api/chat",
        "self_heal": "/self_heal",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """
    让 Cloud Run / 监控系统能确认服务存活
    """
    return {"status": "ok", "env": "cloud-run"}


@app.get("/self_heal")
async def self_heal():
    """
    Her 的自我修复入口：
    - 现在返回最近错误 + 建议修复动作
    - 未来可以通过自我更新系统修改 self_heal 里的策略
    """
    result = self_healer.heal()
    return result


# ----------------------------------------
# Chat Endpoint (simplified)
# ----------------------------------------

def _format_chat_response(reply: str, emotion: str = "neutral") -> dict:
    return {
        "reply": reply,
        "emotion": emotion,
        "conversation_id": "paddy",
        "meta": {
            "model": "gpt-4.1-mini-2025-04-14",
            "from_cloud": True,
            "mode": "text",
        }
    }


@app.post("/api/chat")
async def chat_api(req: ChatRequest):
    """
    你之前用来测试的聊天接口
    这里先给一个稳定可部署的版本
    （正式 Her NLU 模块你可以之后继续集成）
    """
    reply = f"我收到了你的输入：{req.input}"
    # 将来可以在这里接 OpenAI，再把结果丢给 _format_chat_response
    return _format_chat_response(reply, emotion="warm")


# ========================================
# Self Update 系统（核心）
# ========================================

@app.post("/admin/self_update_plan")
async def self_update_plan(req: SelfUpdatePlanRequest):
    """
    生成更新计划，不实际修改文件。
    """
    if not config.AUTO_UPDATE_ENABLED:
        raise HTTPException(status_code=400, detail="Auto update is disabled by config.")

    plan = make_update_plan(req.target_file, req.goal)
    return {"status": "ok", "plan": plan}


@app.post("/admin/self_update_apply")
async def self_update_apply(req: SelfUpdateRequest):
    """
    真正执行自我更新：
    - 写入新文件
    - 自动跑 pytest
    - 测试通过则自动 git commit + push
    - 任何失败自动回滚
    """

    if not config.AUTO_UPDATE_ENABLED:
        raise HTTPException(status_code=400, detail="Auto update is disabled by config.")

    result = apply_file_update(
        rel_path=req.target_file,
        new_content=req.new_content,
        commit_message=req.commit_message,
    )
    return result


# ----------------------------------------
# Startup Event
# ----------------------------------------

@app.on_event("startup")
async def on_startup():
    print("Her Server started — Cloud Run backend ready.")
