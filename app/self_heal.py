# app/self_heal.py
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class HealAction:
    """一次修复操作描述（纯数据，不直接执行危险操作）"""
    name: str
    status: str
    detail: str = ""


@dataclass
class SelfHealState:
    """Her 当前的一些内部状态，用来决定怎么修复"""
    last_error: str | None = None
    openai_ok: bool = True
    firestore_ok: bool = True
    history: List[HealAction] = field(default_factory=list)


class SelfHealer:
    """
    自我修复引擎：
    - 不直接动系统，只给出「建议动作」和状态
    - 以后自我更新系统可以改这里的逻辑
    """

    def __init__(self):
        self.state = SelfHealState()

    def record_error(self, err: str):
        self.state.last_error = err
        self.state.history.append(
            HealAction(name="record_error", status="logged", detail=err)
        )

    def run_basic_diagnostics(self) -> List[HealAction]:
        actions: List[HealAction] = []

        # 示例：检查 OpenAI 状态
        if not self.state.openai_ok:
            actions.append(
                HealAction(
                    name="check_openai_key",
                    status="needs_attention",
                    detail="OPENAI_API_KEY 可能失效或请求失败过多",
                )
            )

        # 示例：检查 Firestore 状态
        if not self.state.firestore_ok:
            actions.append(
                HealAction(
                    name="check_firestore",
                    status="needs_attention",
                    detail="Firestore 连接或配置可能有问题",
                )
            )

        if not actions:
            actions.append(
                HealAction(
                    name="basic_diagnostics",
                    status="ok",
                    detail="暂时未发现需要修复的问题",
                )
            )

        self.state.history.extend(actions)
        return actions

    def heal(self) -> Dict[str, Any]:
        """
        对外的统一入口：
        - 现在只是返回诊断 + 建议动作
        - 以后可以由自我更新系统进化这里的策略
        """
        actions = self.run_basic_diagnostics()
        return {
            "status": "ok",
            "last_error": self.state.last_error,
            "actions": [a.__dict__ for a in actions],
        }
