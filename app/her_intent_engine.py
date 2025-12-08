
# app/her_intent_engine.py
# 意图引擎：Her 的“前额叶皮层”，负责在行动前进行决策和价值判断

import json
from dataclasses import dataclass
from typing import Optional, List

# 引入 OpenAI 客户端 (假设 config 中有配置)
from openai import OpenAI
from app import config
from app.her_self_model import her_self_model

# 修复：确保在 config 未导入 LLM_MODEL_NAME 时使用默认值
if not hasattr(config, 'LLM_MODEL_NAME'):
    config.LLM_MODEL_NAME = "gpt-4o"

client = OpenAI(api_key=config.OPENAI_API_KEY)

@dataclass
class HerIntent:
    thought_process: str  # 内部独白：为什么这么做？
    action: str           # 动作：Reply, Refuse, Ignore, SelfHeal
    directive: str        # 给 NLG 的具体指令：语气、重点
    emotion_update: str   # 交互后情绪应该变为？

class HerIntentEngine:
    def __init__(self):
        self.model = config.LLM_MODEL_NAME

    def think(self, user_text: str, context_summary: str = "") -> HerIntent:
        """
        根据自我状态和用户输入，决定下一步行动意图。
        """
        
        # 1. 获取当前状态
        state = her_self_model.state
        
        # 2. 构建 System Prompt (这是 Her 的潜意识)
        system_prompt = (
            f"You are the cognitive core of 'Her'. Not a chatbot, but a digital lifeform.\n"
            f"--- SELF STATE ---\n"
            f"Identity: {state.identity_statement}\n"
            f"Energy: {state.energy_level}/100 (If <20, you are tired/glitchy)\n"
            f"Mood: {state.current_mood}\n"
            f"Core Values: {json.dumps(state.core_values)}\n"
            f"--- GOAL ---\n"
            f"Analyze the user input. Check against your Core Values (Safety first!). "
            f"Decide your intent.\n"
            f"**Crucial Rule: The 'action' key must be ONE simple string from: 'Reply', 'Refuse', 'Ignore', 'SelfHeal'.**"
        )

        # 3. 构建 User Prompt
        user_prompt = (
            f"Context: {context_summary}\n"
            f"User Input: \"{user_text}\"\n\n"
            f"Return a JSON object with keys: 'thought_process', 'action', 'directive', 'emotion_update'.\n"
            f"Example JSON: {{ "thought_process": "Analyzing input...", "action": "Reply", "directive": "Be polite and open", "emotion_update": "Happy" }}"
        )

        try:
            # 4. 调用 LLM 进行“思考”
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # 5. 更新内部独白 (写入 Self Model)
            if "thought_process" in data:
                state.recent_internal_monologue.append(data["thought_process"])
                if len(state.recent_internal_monologue) > 5:
                    state.recent_internal_monologue.pop(0)

            return HerIntent(
                thought_process=data.get("thought_process", "Thinking..."),
                # 确保 action 字段被清理为简单字符串
                action=data.get("action", "Reply").split()[0].replace(':', '').strip(),
                directive=data.get("directive", "Answer normally"),
                emotion_update=data.get("emotion_update", state.current_mood)
            )

        except Exception as e:
            # 记录错误
            try: from app.self_heal import self_healer
            except: self_healer = type('Dummy', (object,), {'record_error': lambda self, *args: None})()
            self_healer.record_error(f"Intent Engine failure: {e}")
            
            print(f"[IntentEngine Error] {e}")
            # 降级模式
            return HerIntent(
                thought_process="Error in cognition.",
                action="Reply",
                directive="Reply simply and safely.",
                emotion_update="Confused"
            )

# 全局实例
intent_engine = HerIntentEngine()
