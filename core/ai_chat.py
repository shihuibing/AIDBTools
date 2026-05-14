"""
ai_chat.py
AI 多轮对话引擎
- 维护 system_prompt + 对话历史（messages 列表）
- 历史自动持久化到 config/chat_history.json
- 支持按数据库上下文分组历史
- 支持传入 schema 作为上下文
- 支持 Hermes Agent Python 库模式（provider=hermes）
"""
from __future__ import annotations

import json
import os
import sys
import datetime
import requests
from typing import Optional
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


# 历史记录存储路径（优先用户配置的目录，否则使用默认路径）
def _get_history_path() -> str:
    custom_dir = _get_custom_config_dir()
    if custom_dir:
        return os.path.join(custom_dir, "chat_history.json")

    # 默认路径：程序同目录的 config 子目录
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "chat_history.json")

# 单次对话最多保留的历史轮数（防止 token 爆炸）
MAX_HISTORY_ROUNDS = 20
DEFAULT_HISTORY_KEY = "__default__"


class AIChatEngine:
    """
    多轮对话引擎。
    history: list of {
        "role": "user"|"assistant",
        "content": str,
        "time": str,
        "history_key": str,
        "db_label": str,
        "db_type": str,
        "provider": str,
        "model": str,
    }
    """

    def __init__(self):
        self.cfg = ModelConfig()
        self.history: list[dict] = []
        self._extra_system_prompt: str = ""   # Skill 注入的额外系统提示词
        self._load_history()

    def set_system_prompt(self, prompt: str):
        """设置额外系统提示词（由 Skill 注入）"""
        self._extra_system_prompt = prompt

    @staticmethod
    def make_history_key(conn_name: str = "", db_name: str = "", db_type: str = "") -> str:
        conn_name = (conn_name or "").strip()
        db_name = (db_name or "").strip()
        db_type = (db_type or "").strip()
        if not any((conn_name, db_name, db_type)):
            return DEFAULT_HISTORY_KEY
        return f"{conn_name}|{db_name}|{db_type}"

    @staticmethod
    def _entry_time() -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def _normalize_entry(entry: dict) -> dict:
        normalized = dict(entry or {})
        normalized.setdefault("role", "user")
        normalized.setdefault("content", "")
        normalized.setdefault("time", "")
        normalized.setdefault("history_key", DEFAULT_HISTORY_KEY)
        normalized.setdefault("db_label", "默认会话")
        normalized.setdefault("db_type", "")
        normalized.setdefault("provider", "")
        normalized.setdefault("model", "")
        return normalized

    # ─── 历史持久化 ──────────────────────────────
    def _load_history(self):
        """从磁盘加载历史记录"""
        try:
            if os.path.exists(_get_history_path()):
                with open(_get_history_path(), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.history = [self._normalize_entry(item) for item in data if isinstance(item, dict)]
        except Exception:
            self.history = []

    def _save_history(self):
        """将历史记录持久化到磁盘"""
        try:
            path = _get_history_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_history(self, history_key: Optional[str] = None) -> list[dict]:
        key = history_key or DEFAULT_HISTORY_KEY
        return [item for item in self.history if item.get("history_key", DEFAULT_HISTORY_KEY) == key]

    def list_history_groups(self) -> list[dict]:
        groups: dict[str, dict] = {}
        order: list[str] = []
        for item in self.history:
            entry = self._normalize_entry(item)
            key = entry.get("history_key", DEFAULT_HISTORY_KEY)
            if key not in groups:
                groups[key] = {
                    "key": key,
                    "label": entry.get("db_label") or "默认会话",
                    "db_type": entry.get("db_type") or "",
                    "count": 0,
                    "last_time": entry.get("time", ""),
                }
                order.append(key)
            groups[key]["count"] += 1
            groups[key]["last_time"] = entry.get("time", "") or groups[key]["last_time"]
        return [groups[key] for key in order]

    def append_message(
        self,
        role: str,
        content: str,
        *,
        time_str: str = "",
        history_key: str = DEFAULT_HISTORY_KEY,
        db_label: str = "默认会话",
        db_type: str = "",
        provider: str = "",
        model: str = "",
        save: bool = True,
    ):
        entry = self._normalize_entry({
            "role": role,
            "content": content,
            "time": time_str or self._entry_time(),
            "history_key": history_key or DEFAULT_HISTORY_KEY,
            "db_label": db_label or "默认会话",
            "db_type": db_type or "",
            "provider": provider or "",
            "model": model or "",
        })
        self.history.append(entry)
        if save:
            self._save_history()

    def clear_history(self, history_key: Optional[str] = None):
        """清除历史记录；不传 history_key 时清空全部。"""
        if history_key:
            self.history = [
                item for item in self.history
                if item.get("history_key", DEFAULT_HISTORY_KEY) != history_key
            ]
        else:
            self.history = []
            self._extra_system_prompt = ""
        try:
            if self.history:
                self._save_history()
            elif os.path.exists(_get_history_path()):
                os.remove(_get_history_path())
        except Exception:
            pass

    def _resolve_model(self, provider_override: str = "", model_override: str = "") -> dict:
        self.cfg = ModelConfig()
        provider = (provider_override or self.cfg.config.get("active_provider", "openai")).strip() or "openai"
        pconf = self.cfg.config.get(provider, {})
        active = self.cfg.get_active()
        return {
            "provider": provider,
            "api_url": pconf.get("api_url", active.get("api_url", "")),
            "api_key": pconf.get("api_key", active.get("api_key", "")),
            "model": (model_override or pconf.get("model", "") or active.get("model", "")).strip(),
            "temperature": float(self.cfg.config.get("temperature", active.get("temperature", 0.7))),
            "max_tokens": int(self.cfg.config.get("max_tokens", active.get("max_tokens", 4096))),
        }

    # ─── 发送消息 ────────────────────────────────
    def chat(
        self,
        user_input: str,
        schema: str = "",
        db_type: str = "",
        *,
        history_key: str = DEFAULT_HISTORY_KEY,
        db_label: str = "默认会话",
        provider_override: str = "",
        model_override: str = "",
    ) -> str:
        """
        发送一条用户消息，返回 AI 回复文本。
        失败时返回以 '[错误]' 开头的字符串。
        """
        if not user_input.strip():
            return "[错误] 消息不能为空"

        active = self._resolve_model(provider_override, model_override)
        provider = active.get("provider", "openai")
        api_url = active.get("api_url", "").strip().rstrip("/")
        api_key = active.get("api_key", "").strip()
        model = active.get("model", "").strip()
        temperature = float(active.get("temperature", 0.7))
        max_tokens = int(active.get("max_tokens", 4096))

        if not model:
            return "[错误] 未配置模型名称，请先在「AI设置 → 大模型配置」中填写模型"

        system_parts = [
            "你是一个专业的数据库 AI 助手，擅长 SQL 编写、数据库设计和性能优化。",
            "请用中文回答，回答要简洁清晰。",
        ]
        if db_type:
            system_parts.append(f"当前数据库类型：{db_type.upper()}。")
        if db_label and db_label != "默认会话":
            system_parts.append(f"当前数据库上下文：{db_label}。")
        if schema:
            system_parts.append(
                f"\n当前数据库表结构如下（回答时请参考这些真实的表名和列名）：\n{schema}"
            )
        if self._extra_system_prompt:
            system_parts.append(f"\n{self._extra_system_prompt}")
        system_prompt = "\n".join(system_parts)

        recent = self.get_history(history_key)[-MAX_HISTORY_ROUNDS * 2:]
        now_str = self._entry_time()
        self.append_message(
            "user", user_input,
            time_str=now_str,
            history_key=history_key,
            db_label=db_label,
            db_type=db_type,
            provider=provider,
            model=model,
            save=False,
        )

        reply = self._call_ai(
            provider, api_url, api_key, model,
            temperature, max_tokens,
            system_prompt, recent, user_input,
        )

        self.append_message(
            "assistant", reply,
            time_str=self._entry_time(),
            history_key=history_key,
            db_label=db_label,
            db_type=db_type,
            provider=provider,
            model=model,
            save=False,
        )
        self._save_history()
        return reply

    # ─── AI 调用 ─────────────────────────────────
    def _call_ai(self, provider, api_url, api_key, model,
                 temperature, max_tokens,
                 system_prompt, history, user_input) -> str:

        if provider == "anthropic":
            return self._call_anthropic(
                api_url, api_key, model,
                system_prompt, history, user_input,
                temperature, max_tokens,
            )

        

        # ── OpenAI / DeepSeek / Ollama / LiteLLM / 国产大模型 ─────────
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
                return "[错误] 未配置 API 地址，请先在「大模型配置」中填写"

        endpoint = f"{api_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        messages = [{"role": "system", "content": system_prompt}]
        for h in history:
            if h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": h.get("content", "")})
        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            return f"[错误] 无法连接到 {endpoint}，请检查网络或 API 地址"
        except requests.exceptions.Timeout:
            return "[错误] 请求超时（60s），请检查网络或换更快的模型"
        except requests.exceptions.HTTPError as e:
            try:
                err_msg = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            return f"[错误] HTTP {e.response.status_code} - {err_msg}"
        except KeyError as e:
            return f"[错误] 响应格式异常（缺少字段 {e}）"
        except Exception as e:
            return f"[错误] {str(e)}"

    
