"""
ai_sql.py
AI 生成 SQL / 优化 SQL
支持多提供商：OpenAI Compatible、DeepSeek、Anthropic、Ollama、LiteLLM、Hermes Agent
"""
import requests
from app_config.model_config import ModelConfig


class AISQLGenerator:
    def __init__(self):
        self.cfg = ModelConfig()

    # ────────────────────────────────────────────────
    # 核心：向 AI 发送消息，返回文本
    # ────────────────────────────────────────────────
    def _call_ai(self, system_prompt: str, user_prompt: str) -> str:
        """
        重新加载配置，获取当前激活提供商，发请求。
        返回 AI 回复的文本，或以 '--' 开头的错误信息。
        """
        # 每次调用都刷新配置，保证使用最新保存的值
        self.cfg = ModelConfig()
        active = self.cfg.get_active()

        provider   = active.get("provider", "openai")
        api_url    = active.get("api_url", "").strip().rstrip("/")
        api_key    = active.get("api_key", "").strip()
        model      = active.get("model", "").strip()
        temperature = float(active.get("temperature", 0.7))
        max_tokens  = int(active.get("max_tokens", 4096))

        if not model:
            return "-- AI调用失败：未配置模型名称，请先在「模型配置」中填写模型"

        # ── Anthropic 单独处理 ────────────────────
        if provider == "anthropic":
            return self._call_anthropic(
                api_url, api_key, model,
                system_prompt, user_prompt,
                temperature, max_tokens
            )

        # ── Hermes Agent Python 库 ─────────────────
        if provider == "hermes":
            return self._call_hermes(active, system_prompt, user_prompt)

        # ── OpenAI / DeepSeek / LiteLLM / Ollama ─
        # 确定端点
        if not api_url:
            if provider == "deepseek":
                api_url = "https://api.deepseek.com/v1"
            elif provider == "ollama":
                api_url = "http://localhost:11434/v1"
            else:
                return "-- AI调用失败：未配置 API 地址，请先在「模型配置」中填写"

        endpoint = f"{api_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            return f"-- AI调用失败：无法连接到 {endpoint}，请检查网络或 API 地址"
        except requests.exceptions.Timeout:
            return "-- AI调用失败：请求超时（30s），请检查网络或换更快的模型"
        except requests.exceptions.HTTPError as e:
            try:
                err_body = e.response.json()
                err_msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            return f"-- AI调用失败：HTTP {e.response.status_code} - {err_msg}"
        except KeyError as e:
            return f"-- AI调用失败：响应格式异常（缺少字段 {e}）"
        except Exception as e:
            return f"-- AI调用失败：{str(e)}"

    def _call_anthropic(self, api_url, api_key, model,
                        system_prompt, user_prompt,
                        temperature, max_tokens) -> str:
        if not api_url:
            api_url = "https://api.anthropic.com"
        endpoint = f"{api_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        }
        payload = {
            "model":      model,
            "max_tokens": max_tokens,
            "system":     system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"].strip()
        except requests.exceptions.HTTPError as e:
            try:
                err_msg = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            return f"-- AI调用失败：HTTP {e.response.status_code} - {err_msg}"
        except Exception as e:
            return f"-- AI调用失败：{str(e)}"

    def _call_hermes(self, active: dict, system_prompt: str, user_prompt: str) -> str:
        """通过 Hermes Agent Python 库调用 AI（替代 HTTP 请求）"""
        model      = active.get("model", "").strip()
        skip_mem   = active.get("skip_memory", False)
        max_iter   = int(active.get("max_iterations", 10))

        if not model:
            return "-- AI调用失败：Hermes 模式未配置模型名称，请在「模型配置」中填写（OpenRouter 格式如 anthropic/claude-sonnet-4）"

        try:
            from run_agent import AIAgent  # vendored: core/vendor/hermes-agent/
        except ImportError as e:
            return f"-- AI调用失败：Hermes Agent 加载失败：{e}"

        try:
            agent = AIAgent(
                model=model,
                quiet_mode=True,
                skip_memory=skip_mem,
                max_iterations=max_iter,
                # Hermes 会自动从环境变量读取 OPENROUTER_API_KEY 等
            )
            combined = f"{system_prompt}\n\n用户：{user_prompt}"
            response = agent.chat(combined)
            return response.strip() if response else "-- AI调用失败：Hermes 返回了空内容"
        except Exception as e:
            err = str(e)
            if "API key" in err or "api key" in err.lower():
                return f"-- AI调用失败：Hermes 未找到 API Key。请确保设置了环境变量 OPENROUTER_API_KEY / OPENAI_API_KEY 等"
            if "Connection" in err or "connection" in err:
                return f"-- AI调用失败：无法连接到模型 API，请检查网络或 API Key"
            return f"-- AI调用失败（Hermes）：{err}"

    # ────────────────────────────────────────────────
    # 公开接口
    # ────────────────────────────────────────────────
    def generate_sql(self, prompt: str, db_type: str = "mysql", schema: str = "") -> str:
        """根据自然语言描述生成 SQL，schema 为当前库的表结构文本"""
        if not prompt.strip():
            return "-- 请先在输入框中描述你的需求"

        schema_section = ""
        if schema:
            schema_section = f"\n\n当前数据库表结构如下（严格按照这些表名和列名生成 SQL，不要使用不存在的列）：\n{schema}"

        system = (
            f"你是一个专业的 {db_type.upper()} 数据库专家。"
            f"请根据用户描述生成 {db_type.upper()} SQL 语句。"
            "只返回 SQL 代码，不要任何解释和 markdown 代码块，代码直接可执行。"
            "如果需要多条语句，用分号分隔。"
            "必须只使用表结构中存在的表名和列名，不能编造或使用占位符。"
            f"{schema_section}"
        )
        result = self._call_ai(system, prompt)
        result = self._strip_markdown(result)
        return result

    def optimize_sql(self, sql: str, db_type: str = "mysql", schema: str = "") -> str:
        """对现有 SQL 进行优化，返回优化后的 SQL（含注释说明）"""
        if not sql.strip():
            return "-- 请先在 SQL 编辑器中输入 SQL 语句"

        schema_section = ""
        if schema:
            schema_section = f"\n\n当前数据库表结构如下（只能使用这些表名和列名，不要替换为占位符或添加不存在的列）：\n{schema}"

        system = (
            f"你是一个专业的 {db_type.upper()} 数据库性能优化专家。"
            "请对用户提供的 SQL 进行优化，要求：\n"
            "1. 只使用已有的真实列名，绝对不能用 column1、column2 等占位符替换\n"
            "2. 返回优化后的完整可执行 SQL\n"
            "3. 在 SQL 上方以注释形式（-- ）说明做了哪些优化\n"
            "4. 不要使用 markdown 代码块，直接返回可执行的 SQL 代码和注释\n"
            "5. 如果 SQL 已经最优，保持原 SQL 不变并注释说明原因"
            f"{schema_section}"
        )
        result = self._call_ai(system, f"请优化以下 SQL：\n\n{sql}")
        result = self._strip_markdown(result)
        return result

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """去掉 ```sql ... ``` 等 markdown 代码块标记"""
        lines = text.strip().splitlines()
        # 去掉首行 ```xxx
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        # 去掉末行 ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
