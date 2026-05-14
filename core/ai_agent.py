"""
ai_agent.py
AI Agent 引擎 —— OpenClaw/ReAct 风格
=====================================================
特性：
  1. ReAct Loop：Thought → Action(SQL) → Observation → 继续，循环直到完成
  2. 多任务拆解：AI 可将复杂需求拆成多个步骤依次执行
  3. 流式回调：每个 token / 步骤完成都通过 on_token / on_step 回调推送
  4. 自动执行 SQL / 需确认两种模式
  5. 可随时中断（stop()）

Agent 状态机：
  IDLE → RUNNING → (WAITING_CONFIRM) → RUNNING → DONE / ERROR / STOPPED

协议（System Prompt 中定义的 Tool 调用格式）：
  <think>…</think>         AI 推理过程（展示给用户）
  <sql>…</sql>             要执行的 SQL
  <done>…</done>           任务结束，最终回复
  <error>…</error>         AI 判断遇到不可恢复的错误
  纯文本                    普通对话回复（不触发 SQL 执行）
"""

import re
import datetime
import json
import os
import sys
import requests
from typing import Callable, Optional

from app_config.model_config import ModelConfig


def _get_custom_config_dir() -> str:
    """从 ui_prefs.json 读取用户配置的目录，返回空字符串表示未设置"""
    try:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pref_path = os.path.join(base, "ui_prefs.json")
        if os.path.exists(pref_path):
            with open(pref_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("config_dir", "") or ""
    except Exception:
        pass
    return ""


# ── 持久化路径 ──────────────────────────────────────────
def _get_history_path() -> str:
    """获取 agent 历史记录的存储路径"""
    custom_dir = _get_custom_config_dir()
    if custom_dir:
        return os.path.join(custom_dir, "agent_history.json")

    # 默认路径：程序同目录的 config 子目录
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "agent_history.json")


def _get_long_term_memory_path() -> str:
    """获取长期记忆的存储路径"""
    custom_dir = _get_custom_config_dir()
    if custom_dir:
        return os.path.join(custom_dir, "long_term_memory.json")

    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "long_term_memory.json")


MAX_HISTORY_ROUNDS = 30   # 保留的历史轮数（user+assistant 各算一条）
MAX_LOOPS = 12            # 单次任务最多 ReAct 轮数，防死循环


# ── 工具标签正则 ───────────────────────────────────────
_RE_THINK = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_RE_SQL   = re.compile(r"<sql>(.*?)</sql>",   re.DOTALL | re.IGNORECASE)
_RE_DONE  = re.compile(r"<done>(.*?)</done>", re.DOTALL | re.IGNORECASE)
_RE_ERROR = re.compile(r"<error>(.*?)</error>", re.DOTALL | re.IGNORECASE)


# ── 系统提示词 ─────────────────────────────────────────
_SYSTEM_TMPL = """\
你是一个专业的 AI 数据库 Agent，能够自动拆解复杂任务并逐步执行 SQL。

## 工作模式（ReAct）
每一步你的回复必须严格使用以下 XML 标签格式之一，不要混合使用：

1. 思考 + 执行 SQL（需要执行查询/修改时）：
<think>
分析当前步骤，说明要做什么以及为什么这样做。
</think>
<sql>
SELECT ... FROM ...
</sql>

2. 任务完成（所有步骤都完成时）：
<done>
对用户的完整总结回复，包含结果、结论、建议等。
</done>

3. 遇到无法继续的错误时：
<error>
错误说明和建议。
</error>

4. 普通对话（不需要执行 SQL，只是回答问题时）：
直接用自然语言回复即可，不需要任何标签。

## 重要规则
- 每次只输出一个 SQL（<sql> 块只有一条或一组相关语句）
- SQL 执行结果会以 [OBSERVATION] 的形式返回给你
- 根据观察结果决定下一步：继续执行、修正 SQL 或者输出 <done>
- 数据库类型：{db_type}
- 严格使用以下真实表结构，不要使用不存在的表名或列名！

{schema_section}
"""

_SYSTEM_NO_SCHEMA = """\
你是一个专业的 AI 数据库 Agent，能够自动拆解复杂任务并逐步执行 SQL。

## 工作模式（ReAct）
每一步你的回复必须严格使用以下 XML 标签格式之一：

1. 思考 + 执行 SQL：
<think>分析...</think>
<sql>SELECT ...</sql>

2. 任务完成：
<done>总结...</done>

3. 遇到错误：
<error>错误说明...</error>

4. 普通对话：直接自然语言回复。

## 规则
- 每次只输出一个 SQL 块
- SQL 执行结果以 [OBSERVATION] 返回
- 数据库类型：{db_type}
- 当前未连接数据库（无表结构可用）。
"""


class AgentState:
    IDLE    = "idle"
    RUNNING = "running"
    WAITING = "waiting_confirm"   # 等待用户确认后才执行 SQL
    DONE    = "done"
    ERROR   = "error"
    STOPPED = "stopped"


class AIAgent:
    """
    ReAct AI Agent 引擎。

    回调参数：
      on_token(text: str)           每收到一段 AI 文本（用于流式显示）
      on_step(step_type, content)   步骤事件，step_type in:
                                      "think"   AI 思考内容
                                      "sql"     要执行的 SQL
                                      "obs"     SQL 执行结果（观察）
                                      "done"    任务完成内容
                                      "error"   错误信息
                                      "info"    普通信息提示
      on_sql_confirm(sql, callback) 需要用户确认时调用；用户调用 callback(True/False)
      execute_fn(sql)               执行 SQL 的函数，返回 (cols, rows) 或抛出异常
    """

    def __init__(
        self,
        execute_fn: Callable[[str], tuple],
        on_token:  Callable[[str], None]    = None,
        on_step:   Callable[[str, str], None] = None,
        on_sql_confirm: Callable[[str, Callable], None] = None,
        auto_execute: bool = True,
        
    ):
        self.execute_fn      = execute_fn
        self.on_token        = on_token  or (lambda t: None)
        self.on_step         = on_step   or (lambda s, c: None)
        self.on_sql_confirm  = on_sql_confirm
        self.auto_execute    = auto_execute   # True=自动执行，False=每次确认
        

        self.state  = AgentState.IDLE
        self._stop  = False

        # 对话历史（含 agent 内部 observation）
        self.history: list[dict] = []
        self._load_history()

        # 长期记忆（Hermes 特性）
        self.long_term_memory: list[dict] = []
        self._load_long_term_memory()

        # 任务列表（WorkBuddy 特性）
        self.task_list: list[dict] = []
        # 工具调用计数
        self.tool_call_counts: dict = {}
        # Hermes 配置
        self.hermes_config = {}
        self._load_hermes_config()

    # ── 任务列表与工具计数 ──────────────────────
    def add_task(self, description: str, status: str = "pending", metadata: dict = None) -> str:
        """
        添加任务到任务列表，返回任务 ID。
        """
        import datetime
        task_id = datetime.datetime.now().isoformat()
        task = {
            "id": task_id,
            "description": description,
            "status": status,
            "created_at": task_id,
            "completed_at": None,
            "metadata": metadata or {}
        }
        self.task_list.append(task)
        return task_id

    def complete_task(self, task_id: str) -> bool:
        """
        将指定任务标记为完成（status = "completed"）。
        返回 True 如果任务存在且被更新，否则 False。
        """
        for task in self.task_list:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.datetime.now().isoformat()
                return True
        return False

    def get_tasks(self) -> list[dict]:
        """
        返回当前任务列表的副本。
        """
        return [task.copy() for task in self.task_list]

    def increment_tool_call(self, tool_name: str):
        """
        增加指定工具的调用计数。
        """
        self.tool_call_counts[tool_name] = self.tool_call_counts.get(tool_name, 0) + 1

    def get_tool_call_counts(self) -> dict:
        """
        返回工具调用计数字典的副本。
        """
        return self.tool_call_counts.copy()

    # ── 持久化 ──────────────────────────────────────
    def _load_history(self):
        try:
            if os.path.exists(_get_history_path()):
                with open(_get_history_path(), "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if isinstance(d, list):
                        self.history = d
        except Exception:
            self.history = []

    def _save_history(self):
        try:
            path = _get_history_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def clear_history(self):
        self.history = []
        try:
            if os.path.exists(_get_history_path()):
                os.remove(_get_history_path())
        except Exception:
            pass

    # ── 长期记忆 ──────────────────────────────────────
    def _load_long_term_memory(self):
        try:
            if os.path.exists(_get_long_term_memory_path()):
                with open(_get_long_term_memory_path(), "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if isinstance(d, list):
                        self.long_term_memory = d
        except Exception:
            self.long_term_memory = []

    def _save_long_term_memory(self):
        try:
            path = _get_long_term_memory_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.long_term_memory, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Hermes 配置 ───────────────────────────────────
    def _load_hermes_config(self):
        try:
            cfg = ModelConfig()
            self.hermes_config = cfg.config.get("hermes", {})
        except Exception:
            self.hermes_config = {}

    # ── 反思与学习 ──────────────────────────────────
    def _reflect(self, task_result: str):
        """
        对任务执行过程进行反思，提取经验教训，存储到长期记忆。
        """
        if self.hermes_config.get("skip_memory", False):
            return
        # 简单的反思：记录任务摘要和结果
        reflection = {
            "timestamp": datetime.datetime.now().isoformat(),
            "task": self.history[-1] if self.history else {},
            "result": task_result,
            "insights": []  # 可以调用 AI 生成见解，这里先留空
        }
        self.long_term_memory.append(reflection)
        self._save_long_term_memory()

    def _learn(self):
        """
        从长期记忆中学习，更新内部知识。
        目前仅做简单示例。
        """
        # 这里可以实现更复杂的学习逻辑，比如总结模式、更新提示词等
        pass

    # ── 停止 ────────────────────────────────────────
    def stop(self):
        self._stop = True

    # ── 主入口 ──────────────────────────────────────
    def run(self, user_input: str, schema: str = "", db_type: str = "mysql") -> str:
        """
        同步运行 Agent（建议在后台线程调用）。
        返回最终的 done 内容，或错误字符串。
        """
        self._stop = False
        self.state = AgentState.RUNNING

        # 应用 Hermes 配置
        max_loops = self.hermes_config.get("max_iterations", MAX_LOOPS)
        if max_loops <= 0:
            max_loops = MAX_LOOPS

        cfg = ModelConfig()
        active = cfg.get_active()
        if not active.get("model"):
            self.state = AgentState.ERROR
            return "[错误] 未配置模型，请先在「大模型配置」中填写模型"

        # 构建 system prompt
        system = self._build_system(schema, db_type)

        # 记录用户消息
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.history.append({"role": "user", "content": user_input, "time": now})

        

        # ReAct Agent 循环
        for loop_i in range(max_loops):
            if self._stop:
                self.state = AgentState.STOPPED
                return "[已停止]"

            # 调用 AI
            messages = self._build_messages(system)
            ai_reply = self._call_ai(active, messages)

            if ai_reply.startswith("[错误]"):
                self.state = AgentState.ERROR
                self.on_step("error", ai_reply)
                return ai_reply

            # 记录 AI 回复到历史
            now = datetime.datetime.now().strftime("%H:%M:%S")
            self.history.append({"role": "assistant", "content": ai_reply, "time": now})

            # 解析回复
            result = self._parse_and_act(ai_reply, active, system)

            if result["action"] == "done":
                self.state = AgentState.DONE
                self._save_history()
                # 反思学习
                self._reflect(result["content"])
                return result["content"]

            elif result["action"] == "error":
                self.state = AgentState.ERROR
                self._save_history()
                return result["content"]

            elif result["action"] == "plain":
                # 普通对话，直接结束
                self.state = AgentState.DONE
                self._save_history()
                return result["content"]

            elif result["action"] == "continue":
                # 把 observation 追加到历史，继续循环
                obs_msg = result["observation"]
                now = datetime.datetime.now().strftime("%H:%M:%S")
                self.history.append({"role": "user", "content": obs_msg, "time": now})
                continue

        # 达到最大轮数
        self.state = AgentState.ERROR
        self._save_history()
        return "[错误] 任务超过最大步骤限制（可能进入了循环），已自动停止。"

    # ── 解析 AI 回复并执行动作 ──────────────────────
    def _parse_and_act(self, ai_reply: str, active: dict, system: str) -> dict:
        """
        解析 AI 回复中的 XML 标签，执行对应动作。
        返回 dict：{"action": "done"|"error"|"continue"|"plain", "content": ..., "observation": ...}
        """
        # 发流式 token（整体回复）
        self.on_token(ai_reply)

        # 1. <done>
        m_done = _RE_DONE.search(ai_reply)
        if m_done:
            content = m_done.group(1).strip()
            self.on_step("done", content)
            self.increment_tool_call("done")
            return {"action": "done", "content": content}

        # 2. <error>
        m_err = _RE_ERROR.search(ai_reply)
        if m_err:
            content = m_err.group(1).strip()
            self.on_step("error", content)
            self.increment_tool_call("error")
            return {"action": "error", "content": f"[Agent错误] {content}"}

        # 3. <think> + <sql>
        m_think = _RE_THINK.search(ai_reply)
        m_sql   = _RE_SQL.search(ai_reply)

        if m_think:
            self.on_step("think", m_think.group(1).strip())
            self.increment_tool_call("think")

        if m_sql:
            sql = m_sql.group(1).strip()
            self.on_step("sql", sql)
            self.increment_tool_call("sql")

            # 执行 SQL
            observation = self._execute_sql(sql)
            self.on_step("obs", observation)
            self.increment_tool_call("obs")

            return {"action": "continue", "observation": f"[OBSERVATION]\n{observation}"}

        # 4. 纯文本回复（普通对话）
        # 去除任何残留标签后取文本
        plain = re.sub(r"<[^>]+>.*?</[^>]+>", "", ai_reply, flags=re.DOTALL).strip()
        if not plain:
            plain = ai_reply.strip()
        self.on_step("done", plain)
        self.increment_tool_call("done")
        return {"action": "plain", "content": plain}

    # ── 执行 SQL ────────────────────────────────────
    def _execute_sql(self, sql: str) -> str:
        """执行 SQL，返回结果文本供 AI 观察"""
        try:
            cols, rows = self.execute_fn(sql)
            if not cols and not rows:
                return "执行成功（无返回行，DML/DDL 操作）"
            # 格式化结果（最多显示 20 行给 AI 看）
            lines = [" | ".join(str(c) for c in cols)]
            lines.append("-" * len(lines[0]))
            for row in rows[:20]:
                lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))
            if len(rows) > 20:
                lines.append(f"... 共 {len(rows)} 行（仅展示前 20 行）")
            return "\n".join(lines)
        except Exception as e:
            return f"[执行出错] {str(e)}"

    # ── 构建消息列表 ────────────────────────────────
    def _build_system(self, schema: str, db_type: str) -> str:
        if schema:
            return _SYSTEM_TMPL.format(
                db_type=db_type.upper(),
                schema_section=f"## 当前数据库表结构\n{schema}"
            )
        else:
            return _SYSTEM_NO_SCHEMA.format(db_type=db_type.upper())

    def _build_messages(self, system: str) -> list[dict]:
        messages = [{"role": "system", "content": system}]
        # 截取最近 N 轮历史
        recent = self.history[-(MAX_HISTORY_ROUNDS * 2):]
        for h in recent:
            role = h.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": h["content"]})
        return messages

    # ── AI 调用 ──────────────────────────────────────
    def _call_ai(self, active: dict, messages: list[dict]) -> str:
        provider    = active.get("provider", "openai")
        api_url     = active.get("api_url", "").strip().rstrip("/")
        api_key     = active.get("api_key", "").strip()
        model       = active.get("model", "").strip()
        temperature = float(active.get("temperature", 0.3))   # agent 用低温
        max_tokens  = int(active.get("max_tokens", 4096))

        if provider == "anthropic":
            return self._call_anthropic(api_url, api_key, model,
                                        messages, temperature, max_tokens)

        

        if not api_url:
            if provider == "deepseek":
                api_url = "https://api.deepseek.com/v1"
            elif provider == "ollama":
                api_url = "http://localhost:11434/v1"
            elif provider == "qwen":
                api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            elif provider == "doubao":
                api_url = "https://ark.cn-beijing.volces.com/api/v3"
            elif provider == "kimi":
                api_url = "https://api.moonshot.cn/v1"
            elif provider == "glm":
                api_url = "https://open.bigmodel.cn/api/paas/v4"
            elif provider == "minimax":
                api_url = "https://api.minimax.chat/v1"
            else:
                return "[错误] 未配置 API 地址"

        endpoint = f"{api_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model":       model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        
        # 阿里千问特殊处理：某些参数组合可能导致 API 不响应
        if provider == "qwen":
            # 千问对 temperature 敏感，过高可能导致生成失败
            payload["temperature"] = min(temperature, 1.0)
            # 千问 API 有时对 max_tokens 过大值会卡住，限制到 2048
            payload["max_tokens"] = min(max_tokens, 2048)
        
        try:
            # 阿里千问等国产模型响应通常较快，缩短超时以便更快失败
            timeout_sec = 60 if provider in ("qwen", "doubao", "kimi", "glm", "minimax") else 90
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_sec)
            resp.raise_for_status()
            data = resp.json()
            # 健壮性：处理不同的响应格式
            if "choices" not in data or not data["choices"]:
                return f"[错误] API 返回异常：缺少 choices 字段 - {data}"
            choice = data["choices"][0]
            if "message" not in choice:
                return f"[错误] API 返回异常：缺少 message 字段 - {choice}"
            content = choice["message"].get("content", "")
            if not content:
                # 可能是流式响应或空内容
                return f"[错误] API 返回空内容，请检查模型配置或 API 状态"
            return content.strip()
        except requests.exceptions.ConnectionError:
            return f"[错误] 无法连接到 {endpoint}"
        except requests.exceptions.Timeout:
            return f"[错误] 请求超时（{timeout_sec}s），请检查网络、API Key 或模型配置。阿里千问等模型请确认模型名称正确（如 qwen-plus）"
        except requests.exceptions.HTTPError as e:
            try:
                err_data = e.response.json()
                err = err_data.get("error", {}).get("message", str(e))
                # 阿里千问特定错误处理
                if "does not exist" in str(err).lower() or "access" in str(err).lower():
                    err = f"模型不存在或无权访问：{model}。请检查模型名称是否正确（如 qwen-plus、qwen-turbo）"
            except Exception:
                err = str(e)
            return f"[错误] HTTP {e.response.status_code} - {err}"
        except (KeyError, IndexError) as e:
            return f"[错误] API 响应格式异常：{str(e)}，请检查模型配置"
        except Exception as e:
            return f"[错误] {str(e)}"

    def _call_anthropic(self, api_url, api_key, model,
                        messages, temperature, max_tokens) -> str:
        if not api_url:
            api_url = "https://api.anthropic.com"
        # 提取 system（Anthropic 单独传）
        system_content = ""
        chat_messages  = []
        for m in messages:
            if m["role"] == "system":
                system_content = m["content"]
            else:
                chat_messages.append({"role": m["role"], "content": m["content"]})
        endpoint = f"{api_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        }
        payload = {
            "model":      model,
            "max_tokens": max_tokens,
            "system":     system_content,
            "messages":   chat_messages,
        }
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=90)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()
        except Exception as e:
            return f"[错误] {str(e)}"

    

    @staticmethod
    def _resolve_api_url(provider: str, api_url: str) -> str:
        """根据 provider 填充默认 API URL。"""
        if api_url:
            return api_url.rstrip("/")
        defaults = {
            "deepseek": "https://api.deepseek.com/v1",
            "ollama":   "http://localhost:11434/v1",
            "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "doubao":   "https://ark.cn-beijing.volces.com/api/v3",
            "kimi":     "https://api.moonshot.cn/v1",
            "glm":      "https://open.bigmodel.cn/api/paas/v4",
            "minimax":  "https://api.minimax.chat/v1",
        }
        return defaults.get(provider, "https://api.openai.com/v1")

    
