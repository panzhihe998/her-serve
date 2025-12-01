# app/self_update.py
"""
Her 的自我更新引擎（Version C 基础版）

能力：
- 接收一个目标文件路径 + 新内容 + commit message
- 自动备份原文件
- 写入新内容
- 自动运行 pytest
- 测试通过则 git commit + git push
- 任何一步失败就自动回滚到备份版本
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any

from app import config


ROOT_DIR = Path(config.PROJECT_ROOT).resolve()


def run_cmd(cmd: list[str]) -> Dict[str, Any]:
    """
    在项目根目录执行一个命令，并返回执行结果。
    """
    proc = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        shell=False,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_tests() -> Dict[str, Any]:
    """
    运行 pytest，验证更新后的代码是否健康。
    """
    result = run_cmd(["pytest"])
    result["success"] = result["returncode"] == 0
    return result


def git_commit_and_push(message: str) -> Dict[str, Any]:
    """
    自动 git add / commit / push。
    要求本地已经配置好 Git 远程和认证（你之前已经可以手动 push 说明没问题）。
    """
    logs = []

    for cmd in [
        ["git", "add", "."],
        ["git", "commit", "-m", message],
        ["git", "push", "origin", config.UPDATE_BRANCH],
    ]:
        res = run_cmd(cmd)
        logs.append(res)
        if res["returncode"] != 0 and "nothing to commit" not in res["stderr"].lower():
            return {
                "success": False,
                "step": res["cmd"],
                "log": logs,
            }

    return {"success": True, "log": logs}


def apply_file_update(
    rel_path: str,
    new_content: str,
    commit_message: str,
) -> Dict[str, Any]:
    """
    自我更新的核心流程：

    1. 备份原文件
    2. 写入新内容
    3. 跑 pytest
    4. 测试通过 → git commit & push
    5. 测试失败或 git 失败 → 自动回滚备份
    """
    target_path = (ROOT_DIR / rel_path).resolve()

    if not target_path.exists():
        return {
            "status": "error",
            "reason": "file_not_found",
            "detail": str(target_path),
        }

    if ROOT_DIR not in target_path.parents and target_path != ROOT_DIR:
        # 防止越权修改其它目录
        return {
            "status": "error",
            "reason": "outside_project_root",
            "detail": str(target_path),
        }

    backup_path = target_path.with_suffix(target_path.suffix + ".bak")

    try:
        # 1. 备份
        shutil.copy2(target_path, backup_path)

        # 2. 写入新内容
        target_path.write_text(new_content, encoding="utf-8")

        # 3. 跑测试
        test_result = run_tests()
        if not test_result.get("success"):
            # 回滚
            shutil.copy2(backup_path, target_path)
            return {
                "status": "tests_failed",
                "tests": test_result,
            }

        # 4. 测试通过 → 自动 git commit + push
        git_result = git_commit_and_push(commit_message)
        if not git_result.get("success"):
            # git 出错也回滚
            shutil.copy2(backup_path, target_path)
            return {
                "status": "git_failed",
                "git": git_result,
            }

        return {
            "status": "ok",
            "tests": test_result,
            "git": git_result,
        }

    except Exception as e:
        # 发生任何异常 → 尝试回滚
        try:
            if backup_path.exists():
                shutil.copy2(backup_path, target_path)
        finally:
            return {
                "status": "error",
                "reason": "exception",
                "detail": str(e),
            }
    finally:
        # 你可以选择是否删除备份文件，这里暂时保留
        pass


def make_update_plan(target_file: str, goal: str) -> Dict[str, Any]:
    """
    只生成一个“更新计划”，不真正改代码。
    方便你或未来的 Her 用 LLM 来生成实际的新代码。
    """
    return {
        "target_file": target_file,
        "goal": goal,
        "suggested_steps": [
            "读取当前文件内容",
            "根据 goal 设计需要修改/新增的函数、类或逻辑",
            "生成完整的新文件内容（而不是只生成 diff，方便简单覆盖）",
            "调用 /admin/self_update_apply 将新内容写入并触发测试和 push",
        ],
    }
