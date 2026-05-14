"""
skill_manager.py
Skill 管理核心 —— 支持增删查、启用/禁用、快捷键触发
"""
from __future__ import annotations  # Python 3.9 兼容：支持 X | Y 类型注解
import json
import os
import sys
import zipfile


def _skills_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "skills.json")


class SkillManager:
    def __init__(self):
        self.skills: list[dict] = []
        self.load()

    # ── 持久化 ──────────────────────────────
    def load(self):
        path = _skills_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 兼容旧格式（纯列表 vs 新格式）
                if isinstance(data, list):
                    # 升级旧格式：每项可能只有 name/content
                    upgraded = []
                    for item in data:
                        if isinstance(item, dict):
                            upgraded.append({
                                "name":        item.get("name", "未命名"),
                                "description": item.get("description", ""),
                                "content":     item.get("content", ""),
                                "enabled":     item.get("enabled", True),
                                "hotkey":      item.get("hotkey", ""),
                                "category":    item.get("category", "通用"),
                            })
                    self.skills = upgraded
            except Exception:
                self.skills = []
        else:
            self.skills = []

    def save(self):
        with open(_skills_path(), "w", encoding="utf-8") as f:
            json.dump(self.skills, f, ensure_ascii=False, indent=2)

    # ── CRUD ────────────────────────────────
    def add_skill(self, name: str, content: str,
                  description: str = "", category: str = "通用",
                  hotkey: str = "") -> dict:
        skill = {
            "name":        name,
            "description": description,
            "content":     content,
            "enabled":     True,
            "hotkey":      hotkey,
            "category":    category,
        }
        self.skills.append(skill)
        self.save()
        return skill

    def update_skill(self, index: int, **kwargs):
        if 0 <= index < len(self.skills):
            self.skills[index].update(kwargs)
            self.save()

    def delete_skill(self, index: int):
        if 0 <= index < len(self.skills):
            self.skills.pop(index)
            self.save()

    def toggle_enabled(self, index: int) -> bool:
        """切换启用/禁用，返回新状态"""
        if 0 <= index < len(self.skills):
            new_val = not self.skills[index].get("enabled", True)
            self.skills[index]["enabled"] = new_val
            self.save()
            return new_val
        return False

    def move_up(self, index: int):
        if index > 0:
            self.skills[index], self.skills[index - 1] = (
                self.skills[index - 1], self.skills[index]
            )
            self.save()

    def move_down(self, index: int):
        if index < len(self.skills) - 1:
            self.skills[index], self.skills[index + 1] = (
                self.skills[index + 1], self.skills[index]
            )
            self.save()

    # ── 查询 ────────────────────────────────
    def get_enabled(self) -> list[dict]:
        return [s for s in self.skills if s.get("enabled", True)]

    def get_categories(self) -> list[str]:
        cats = []
        for s in self.skills:
            c = s.get("category", "通用")
            if c not in cats:
                cats.append(c)
        return cats or ["通用"]

    def find_by_hotkey(self, hotkey: str) -> dict | None:
        for s in self.skills:
            if s.get("hotkey") == hotkey and s.get("enabled", True):
                return s
        return None

    # ── 导入 ────────────────────────────────
    def import_skill(self, path: str) -> tuple[bool, str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            name = os.path.splitext(os.path.basename(path))[0]
            # 尝试从文件顶部注释解析描述
            desc = ""
            for line in content.splitlines()[:5]:
                if line.startswith("#"):
                    desc = line.lstrip("#").strip()
                    break
            self.add_skill(name, content, description=desc)
            return True, f"[OK] Skill 「{name}」 导入成功"
        except Exception as e:
            return False, f"[FAIL] 导入失败：{e}"

    def import_from_zip(self, zip_path: str) -> tuple[bool, str, int]:
        """
        从 ZIP 包批量导入 Skill。
        支持两种格式：
        1. ZIP 内含 skill.json（数组格式，每项含 name/description/content）
        2. ZIP 内含多个 *.txt / *.md / *.py / *.sql 文件，每文件一个 Skill
        返回: (是否成功, 消息, 导入数量)
        """
        try:
            imported = 0
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()

                # 优先查找 skill.json
                skill_json_names = [n for n in names if n.strip("/").endswith("skill.json")]
                if skill_json_names:
                    # 只取第一个
                    json_name = skill_json_names[0]
                    raw = zf.read(json_name).decode("utf-8")
                    data = json.loads(raw)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        self.add_skill(
                            name=item.get("name", "未命名"),
                            content=item.get("content", ""),
                            description=item.get("description", ""),
                            category=item.get("category", "通用"),
                            hotkey=item.get("hotkey", ""),
                        )
                        imported += 1
                else:
                    # 按文件导入
                    for name in names:
                        # 跳过目录和隐藏文件
                        if name.endswith("/") or "/" in name.lstrip("/"):
                            base = name.rsplit("/", 1)[-1]
                        else:
                            base = name
                        if not base or base.startswith("."):
                            continue
                        ext = os.path.splitext(base)[1].lower()
                        if ext not in (".txt", ".md", ".py", ".sql", ".json"):
                            continue
                        content = zf.read(name).decode("utf-8")
                        skill_name = os.path.splitext(base)[0]
                        desc = ""
                        for line in content.splitlines()[:5]:
                            if line.startswith("#"):
                                desc = line.lstrip("#").strip()
                                break
                        self.add_skill(skill_name, content, description=desc)
                        imported += 1

            if imported == 0:
                return False, "[FAIL] ZIP 中未找到可导入的 Skill 文件（支持 skill.json 或 .txt/.md/.py/.sql）", 0
            return True, f"[OK] 从 ZIP 导入 {imported} 个 Skill", imported
        except json.JSONDecodeError:
            return False, "[FAIL] skill.json 格式错误，无法解析", 0
        except Exception as e:
            return False, f"[FAIL] ZIP 导入失败：{e}", 0

    def export_skill(self, index: int, save_path: str) -> tuple[bool, str]:
        if not (0 <= index < len(self.skills)):
            return False, "索引越界"
        skill = self.skills[index]
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(skill.get("content", ""))
            return True, f"[OK] 导出到 {save_path}"
        except Exception as e:
            return False, f"[FAIL] 导出失败：{e}"

    # ── 应用 Skill（返回拼装好的系统提示词）──
    def build_system_prompt(self, skill_index: int, base_prompt: str = "") -> str:
        if not (0 <= skill_index < len(self.skills)):
            return base_prompt
        skill = self.skills[skill_index]
        skill_content = skill.get("content", "").strip()
        if not skill_content:
            return base_prompt
        parts = []
        if base_prompt:
            parts.append(base_prompt)
        parts.append(f"\n\n--- Skill: {skill['name']} ---\n{skill_content}")
        return "\n".join(parts)
