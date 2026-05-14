"""
model_config_window.py
模型配置窗口 —— 参考 Cursor/WindTerm 设置页风格
左侧分类导航 + 右侧滚动内容区，深色主题
"""
from __future__ import annotations

import requests
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from typing import Optional
from app_config.model_config import ModelConfig
from ui.theme_manager import load_theme, get_theme_tokens, build_popup_base_style, load_window_state, save_window_state, make_frameless_title_bar, build_dialog_frame
from ui.iconfont_loader import Icon



def _theme_tokens() -> dict:
    return get_theme_tokens(load_theme())


# ── 主题样式 ────────────────────────────────────────────────────────────────

def _build_window_style(tokens: dict) -> str:
    return build_popup_base_style(tokens, f"""
QWidget#mcwNavPanel {{
    background: {tokens['surface_muted']};
    border-right: 1px solid {tokens['border']};
}}
QWidget#mcwContentPanel {{
    background: {tokens['surface']};
}}
/* ── 左侧导航列表 ── */
QListWidget {{
    background: transparent;
    border: none;
    color: {tokens['text']};
    font-size: 12px;
    outline: none;
    padding: 0 4px 8px 4px;
}}
QListWidget::item {{
    padding: 5px 10px;
    border-radius: 2px;
    margin: 0px 0px;
    min-height: 20px;
}}
QListWidget::item:selected {{
    background: {tokens['accent']};
    color: #ffffff;
}}
QListWidget::item:hover:!selected {{
    background: {tokens['surface_alt']};
}}
/* 分组标题行（通过 setData 标记，不可选中） */
QListWidget::item[isGroupHeader="true"] {{
    color: {tokens['text_muted']};
    background: transparent;
    padding: 10px 8px 3px 8px;
    font-size: 10px;
}}
/* ── 右侧内容区 ── */
QScrollArea {{
    border: none;
    background: transparent;
}}
QWidget#content_bg {{
    background: {tokens['surface']};
}}
/* ── 页面内元素 ── */
QLabel#section_title {{
    color: {tokens['accent']};
    font-size: 15px;
    font-weight: bold;
    padding: 0;
    margin: 0;
}}
QLabel#group_title {{
    color: {tokens['text_soft']};
    font-size: 11px;
    font-weight: bold;
    padding: 0;
    margin: 0;
}}
QLabel#hint_label {{
    color: {tokens['text_muted']};
    font-size: 11px;
}}
QFrame#h_line {{
    color: {tokens['border']};
    background: {tokens['border']};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QLabel#model_tag {{
    background: {tokens['accent_soft']};
    color: {tokens['accent']};
    border-radius: 2px;
    padding: 2px 8px;
    font-size: 12px;
}}
/* ── 导航头部 ── */
QLabel#nav_title {{
    color: {tokens['text']};
    font-size: 13px;
    font-weight: bold;
    padding: 12px 12px 6px 12px;
}}
/* ── 窗口内专用按钮（覆盖 build_popup_base_style 全局规则） ── */
QPushButton#mcw_btn {{
    min-height: 0px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 500;
    border-radius: 2px;
    border: 1px solid {tokens['border']};
    background: {tokens['surface_alt']};
    color: {tokens['text']};
}}
QPushButton#mcw_btn:hover {{
    border-color: {tokens['accent']};
    color: {tokens['accent']};
    background: {tokens['accent_soft']};
}}
QPushButton#mcw_btn[role="primary"] {{
    background: {tokens['accent']};
    color: #ffffff;
    border-color: {tokens['accent']};
}}
QPushButton#mcw_btn[role="primary"]:hover {{
    background: {tokens['accent_hover']};
    border-color: {tokens['accent_hover']};
}}
QPushButton#mcw_btn[role="primary"]:pressed {{
    background: {tokens['accent_pressed']};
    border-color: {tokens['accent_pressed']};
}}
QPushButton#mcw_btn[role="check"] {{
    background: {tokens['surface_alt']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
}}
QPushButton#mcw_btn[role="check"]:hover {{
    border-color: {tokens['accent']};
    color: {tokens['accent']};
}}
/* ── preset 快捷模型按钮 ── */
QPushButton#preset_btn {{
    background: {tokens['surface_alt']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    padding: 2px 8px;
    font-size: 11px;
    min-height: 0px;
}}
QPushButton#preset_btn:hover {{
    background: {tokens['accent_soft']};
    color: {tokens['accent']};
    border-color: {tokens['accent']};
}}
/* ── check/save 按钮覆盖 build_popup_base_style 默认值 ── */
QPushButton[role="check"] {{
    background: {tokens['surface_alt']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    padding: 3px 10px;
    font-size: 12px;
    min-height: 0px;
    font-weight: 600;
}}
QPushButton[role="check"]:hover {{
    border-color: {tokens['accent']};
    color: {tokens['accent']};
    background: {tokens['surface_alt']};
}}
""")









def _make_btn(text: str, role: str = "default", tokens: Optional[dict] = None) -> QPushButton:
    """
    创建窗口内专用按钮，内联样式拥有最高优先级，
    彻底覆盖 build_popup_base_style 全局 QPushButton 规则。
    role: 'primary' | 'default' | 'check'
    """
    t = tokens or _theme_tokens()
    btn = QPushButton(text)

    if role == "primary":
        style = (
            f"QPushButton{{min-height:0px;padding:4px 14px;font-size:12px;"
            f"font-weight:500;border-radius: 4px;"
            f"background:{t['accent']};color:#ffffff;"
            f"border:none;}}"
            f"QPushButton:hover{{background:{t['accent_hover']};}}"
            f"QPushButton:pressed{{background:{t['accent_pressed']};}}"
        )
    elif role == "check":
        style = (
            f"QPushButton{{min-height:0px;padding:4px 12px;font-size:12px;"
            f"font-weight:500;border-radius: 4px;"
            f"background:{t['surface_alt']};color:{t['text']};"
            f"border:none;}}"
            f"QPushButton:hover{{color:{t['accent']};"
            f"background:{t['surface_alt']};}}"
        )
    else:
        style = (
            f"QPushButton{{min-height:0px;padding:4px 14px;font-size:12px;"
            f"font-weight:500;border-radius: 4px;"
            f"background:{t['surface_alt']};color:{t['text']};"
            f"border:none;}}"
            f"QPushButton:hover{{color:{t['accent']};"
            f"background:{t['accent_soft']};}}"
        )
    btn.setStyleSheet(style)
    return btn


def _hint(text: str):
    lbl = QLabel(text)
    lbl.setObjectName("hint_label")
    lbl.setWordWrap(True)
    return lbl


def _section_title(text: str):
    lbl = QLabel(text)
    lbl.setObjectName("section_title")
    return lbl


def _group_title(text: str):
    lbl = QLabel(text)
    lbl.setObjectName("group_title")
    return lbl


def _info_box(parent, title: str, text: str):
    """用主题样式弹出信息对话框，避免继承父窗口深色 QSS 导致黑底黑字。"""
    tokens = _theme_tokens()
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Information)
    box.setStyleSheet(build_popup_base_style(tokens))
    box.exec()


def _warn_box(parent, title: str, text: str):
    """用主题样式弹出警告对话框。"""
    tokens = _theme_tokens()
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setStyleSheet(build_popup_base_style(tokens))
    box.exec()


def _eye_button(line_edit: QLineEdit, tokens: Optional[dict] = None) -> QPushButton:
    """密码显示/隐藏按钮"""
    tokens = tokens or _theme_tokens()
    btn = QPushButton(Icon.char('eye'))
    btn.setFont(Icon.font(14))
    btn.setFixedSize(28, 28)
    btn.setStyleSheet(
        "QPushButton{" 
        f"background:transparent;border:none;color:{tokens['text_muted']};"
        "}"
        "QPushButton:hover{" 
        f"color:{tokens['accent']};"
        "}"
    )
    btn.setCheckable(True)

    def toggle(checked):
        btn.setText(Icon.char('eye_off' if checked else 'eye'))
        line_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
    btn.toggled.connect(toggle)
    return btn


def _key_field(placeholder="请输入API Key", tokens: Optional[dict] = None) -> tuple[QHBoxLayout, QLineEdit]:
    """带眼睛按钮的 Key 输入行"""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setEchoMode(QLineEdit.EchoMode.Password)
    row.addWidget(le)
    row.addWidget(_eye_button(le, tokens))
    return row, le


# ────────────────────────────────────────────────────────────────────────────
# 各提供商配置页面（QWidget）
# ────────────────────────────────────────────────────────────────────────────

class _BaseProviderPage(QWidget):
    """所有提供商页的基类"""

    def __init__(self, cfg: ModelConfig, provider_key: str):
        super().__init__()
        self.cfg = cfg
        self.key = provider_key
        self._build()

    def _build(self):
        raise NotImplementedError

    def _pconf(self) -> dict:
        return self.cfg.config.get(self.key, {})

    def _check_and_save(self, layout_parent, model_edit: QLineEdit, get_url_key=None, get_api_key=None):
        """通用 Check + Save 按钮行"""
        layout_parent.addSpacing(4)
        layout_parent.addWidget(QLabel("模型"))

        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        row.setSpacing(6)
        row.addWidget(model_edit, stretch=1)

        btn_check = _make_btn("检测", role="check")
        btn_save  = _make_btn("保存", role="primary")

        row.addWidget(btn_check)
        row.addWidget(btn_save)

        def do_check():
            _info_box(self, "检测", "配置检测中（实际测试需真实 Key）")

        def do_save():
            self._save_fields()
            model_name = model_edit.text().strip()
            # 自动激活：加入 active_models + 设为当前提供商
            self.cfg.save_and_activate(self.key, model_name)
            _info_box(self, "已保存", f"{self.key} 配置已保存并设为当前模型")

        btn_check.clicked.connect(do_check)
        btn_save.clicked.connect(do_save)
        layout_parent.addLayout(row)

    def _save_fields(self):
        raise NotImplementedError


class OpenAIPage(_BaseProviderPage):
    def __init__(self, cfg):
        super().__init__(cfg, "openai")

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_section_title("OpenAI Compatible"))
        v.addSpacing(16)

        v.addWidget(QLabel("API 地址"))
        v.addSpacing(4)
        self.url_edit = QLineEdit(self._pconf().get("api_url", "https://api.openai.com/v1"))
        v.addWidget(self.url_edit)
        v.addSpacing(3)
        v.addWidget(_hint("默认 https://api.openai.com/v1，兼容 OpenAI 格式的第三方接口也可填写"))
        v.addSpacing(12)

        v.addWidget(QLabel("API 格式"))
        v.addSpacing(4)
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["Chat Completions", "Responses"])
        self.fmt_combo.setFixedWidth(200)
        cur_fmt = self._pconf().get("api_format", "Chat Completions")
        self.fmt_combo.setCurrentText(cur_fmt)
        v.addWidget(self.fmt_combo)
        v.addSpacing(12)

        v.addWidget(QLabel("API Key"))
        v.addSpacing(4)
        key_row, self.key_edit = _key_field()
        self.key_edit.setText(self._pconf().get("api_key", ""))
        v.addLayout(key_row)
        v.addSpacing(3)
        v.addWidget(_hint("此密钥存储在本地，仅用于从此客户端发出 API 请求"))
        v.addSpacing(12)

        self.model_edit = QLineEdit(self._pconf().get("model", ""))
        self.model_edit.setPlaceholderText("例: gpt-4o / gpt-4o-mini / o1")
        self._check_and_save(v, self.model_edit)

        v.addStretch()

    def _save_fields(self):
        self.cfg.config["openai"]["api_url"]    = self.url_edit.text().strip()
        self.cfg.config["openai"]["api_key"]    = self.key_edit.text()
        self.cfg.config["openai"]["api_format"] = self.fmt_combo.currentText()
        self.cfg.config["openai"]["model"]      = self.model_edit.text().strip()


class DeepSeekPage(_BaseProviderPage):
    def __init__(self, cfg):
        super().__init__(cfg, "deepseek")

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_section_title("DeepSeek"))
        v.addSpacing(16)

        v.addWidget(QLabel("API Key"))
        v.addSpacing(4)
        key_row, self.key_edit = _key_field()
        self.key_edit.setText(self._pconf().get("api_key", ""))
        v.addLayout(key_row)
        v.addSpacing(3)
        v.addWidget(_hint("此密钥存储在本地，仅用于从此客户端发出 API 请求"))
        v.addSpacing(12)

        self.model_edit = QLineEdit(self._pconf().get("model", "deepseek-chat"))
        self.model_edit.setPlaceholderText("例: deepseek-chat / deepseek-reasoner")
        self._check_and_save(v, self.model_edit)

        v.addStretch()

    def _save_fields(self):
        self.cfg.config["deepseek"]["api_key"] = self.key_edit.text()
        self.cfg.config["deepseek"]["model"]   = self.model_edit.text().strip()


class AnthropicPage(_BaseProviderPage):
    def __init__(self, cfg):
        super().__init__(cfg, "anthropic")

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_section_title("Anthropic"))
        v.addSpacing(16)

        v.addWidget(QLabel("API 地址"))
        v.addSpacing(4)
        self.url_edit = QLineEdit(self._pconf().get("api_url", "https://api.anthropic.com"))
        self.url_edit.setPlaceholderText("默认: https://api.anthropic.com")
        v.addWidget(self.url_edit)
        v.addSpacing(3)
        v.addWidget(_hint("可选，留空使用官方地址"))
        v.addSpacing(12)

        v.addWidget(QLabel("API Key"))
        v.addSpacing(4)
        key_row, self.key_edit = _key_field()
        self.key_edit.setText(self._pconf().get("api_key", ""))
        v.addLayout(key_row)
        v.addSpacing(3)
        v.addWidget(_hint("此密钥存储在本地，仅用于从此客户端发出 API 请求"))
        v.addSpacing(12)

        self.model_edit = QLineEdit(self._pconf().get("model", "claude-3-5-sonnet-20241022"))
        self.model_edit.setPlaceholderText("例: claude-3-5-sonnet-20241022")
        self._check_and_save(v, self.model_edit)

        v.addStretch()

    def _save_fields(self):
        self.cfg.config["anthropic"]["api_url"] = self.url_edit.text().strip()
        self.cfg.config["anthropic"]["api_key"] = self.key_edit.text()
        self.cfg.config["anthropic"]["model"]   = self.model_edit.text().strip()


class LiteLLMPage(_BaseProviderPage):
    def __init__(self, cfg):
        super().__init__(cfg, "litellm")

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_section_title("LiteLLM"))
        v.addSpacing(16)

        v.addWidget(QLabel("API 地址"))
        v.addSpacing(4)
        self.url_edit = QLineEdit(self._pconf().get("api_url", ""))
        self.url_edit.setPlaceholderText("请输入 LiteLLM 代理地址")
        v.addWidget(self.url_edit)
        v.addSpacing(12)

        v.addWidget(QLabel("API Key"))
        v.addSpacing(4)
        key_row, self.key_edit = _key_field("请输入 API Key")
        self.key_edit.setText(self._pconf().get("api_key", ""))
        v.addLayout(key_row)
        v.addSpacing(3)
        v.addWidget(_hint("密钥存储在本地，仅用于从此客户端发出 API 请求"))
        v.addSpacing(12)

        self.model_edit = QLineEdit(self._pconf().get("model", ""))
        self.model_edit.setPlaceholderText("请输入模型名称")
        self._check_and_save(v, self.model_edit)

        v.addStretch()

    def _save_fields(self):
        self.cfg.config["litellm"]["api_url"] = self.url_edit.text().strip()
        self.cfg.config["litellm"]["api_key"] = self.key_edit.text()
        self.cfg.config["litellm"]["model"]   = self.model_edit.text().strip()


class BedrockPage(_BaseProviderPage):
    def __init__(self, cfg):
        super().__init__(cfg, "bedrock")

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_section_title("Amazon Bedrock"))
        v.addSpacing(16)

        v.addWidget(QLabel("AWS Access Key"))
        v.addSpacing(4)
        self.ak_edit = QLineEdit(self._pconf().get("access_key", ""))
        self.ak_edit.setPlaceholderText("请输入 AWS Access Key")
        v.addWidget(self.ak_edit)
        v.addSpacing(10)

        v.addWidget(QLabel("AWS Secret Key"))
        v.addSpacing(4)
        sk_row, self.sk_edit = _key_field("请输入 AWS Secret Key")
        self.sk_edit.setText(self._pconf().get("secret_key", ""))
        v.addLayout(sk_row)
        v.addSpacing(10)

        v.addWidget(QLabel("AWS Session Token（可选）"))
        v.addSpacing(4)
        st_row, self.st_edit = _key_field("请输入 AWS Session Token")
        self.st_edit.setText(self._pconf().get("session_token", ""))
        v.addLayout(st_row)
        v.addSpacing(10)

        v.addWidget(QLabel("AWS 区域"))
        v.addSpacing(4)
        self.region_edit = QLineEdit(self._pconf().get("region", "us-east-1"))
        self.region_edit.setFixedWidth(160)
        v.addWidget(self.region_edit)
        v.addSpacing(3)
        v.addWidget(_hint("通过以上密钥或默认凭证链（~/.aws/credentials）进行身份验证，凭证仅在本地使用"))
        v.addSpacing(10)

        self.chk_vpc = QCheckBox("使用自定义 VPC 端点")
        self.chk_vpc.setChecked(self._pconf().get("use_custom_vpc", False))
        self.chk_cross = QCheckBox("使用跨区域推理")
        self.chk_cross.setChecked(self._pconf().get("cross_region", False))
        v.addWidget(self.chk_vpc)
        v.addSpacing(4)
        v.addWidget(self.chk_cross)
        v.addSpacing(12)

        self.model_edit = QLineEdit(self._pconf().get("model", ""))
        self.model_edit.setPlaceholderText("例: anthropic.claude-3-5-sonnet-20241022-v2:0")
        self._check_and_save(v, self.model_edit)

        v.addStretch()

    def _save_fields(self):
        self.cfg.config["bedrock"]["access_key"]    = self.ak_edit.text()
        self.cfg.config["bedrock"]["secret_key"]    = self.sk_edit.text()
        self.cfg.config["bedrock"]["session_token"] = self.st_edit.text()
        self.cfg.config["bedrock"]["region"]        = self.region_edit.text().strip()
        self.cfg.config["bedrock"]["use_custom_vpc"]= self.chk_vpc.isChecked()
        self.cfg.config["bedrock"]["cross_region"]  = self.chk_cross.isChecked()
        self.cfg.config["bedrock"]["model"]         = self.model_edit.text().strip()


class OllamaPage(_BaseProviderPage):
    def __init__(self, cfg):
        super().__init__(cfg, "ollama")

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_section_title("Ollama（本地）"))
        v.addSpacing(16)

        v.addWidget(QLabel("Ollama 服务地址"))
        v.addSpacing(4)
        self.url_edit = QLineEdit(self._pconf().get("api_url", "http://localhost:11434/v1"))
        v.addWidget(self.url_edit)
        v.addSpacing(3)
        v.addWidget(_hint("确保本地已启动 Ollama 服务，默认端口 11434"))
        v.addSpacing(12)

        self.model_edit = QLineEdit(self._pconf().get("model", "llama3"))
        self.model_edit.setPlaceholderText("例: llama3 / qwen2.5 / mistral")
        self._check_and_save(v, self.model_edit)

        v.addStretch()

    def _save_fields(self):
        self.cfg.config["ollama"]["api_url"] = self.url_edit.text().strip()
        self.cfg.config["ollama"]["model"]   = self.model_edit.text().strip()


# ── 通用国产大模型配置页基类 ─────────────────────────────────────────────
class _DomesticProviderPage(_BaseProviderPage):
    """
    千问/豆包/Kimi/GLM/MiniMax 结构都是 api_url + api_key + model，
    子类只需提供 title / default_url / default_model / url_hint / key_hint / model_hint
    """
    title: str = ""
    default_url: str = ""
    default_model: str = ""
    url_hint: str = ""
    key_hint: str = ""
    model_hint: str = ""
    model_presets: list = []

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)

        # ── 标题区 ──
        v.addWidget(_section_title(self.title))
        v.addSpacing(16)

        # ── API 地址 ──
        v.addWidget(QLabel("API 地址"))
        v.addSpacing(4)
        self.url_edit = QLineEdit(self._pconf().get("api_url", self.default_url))
        self.url_edit.setPlaceholderText(self.default_url)
        v.addWidget(self.url_edit)
        if self.url_hint:
            v.addSpacing(3)
            v.addWidget(_hint(self.url_hint))
        v.addSpacing(12)

        # ── API Key ──
        v.addWidget(QLabel("API Key"))
        v.addSpacing(4)
        key_row, self.key_edit = _key_field()
        self.key_edit.setText(self._pconf().get("api_key", ""))
        v.addLayout(key_row)
        if self.key_hint:
            v.addSpacing(3)
            v.addWidget(_hint(self.key_hint))
        v.addSpacing(12)

        # ── 模型 + Check/Save ──
        self.model_edit = QLineEdit(self._pconf().get("model", self.default_model))
        if self.model_hint:
            self.model_edit.setPlaceholderText(self.model_hint)
        self._check_and_save(v, self.model_edit)

        # ── 常用模型快捷按钮 ──
        if self.model_presets:
            v.addSpacing(14)
            preset_label = _group_title("常用模型")
            v.addWidget(preset_label)
            v.addSpacing(6)
            preset_row = QHBoxLayout()
            preset_row.setContentsMargins(0, 0, 0, 0)
            preset_row.setSpacing(6)
            for m in self.model_presets:
                btn = _make_btn(m, role="default")
                btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
                btn.clicked.connect(lambda _checked=False, _m=m: self.model_edit.setText(_m))
                preset_row.addWidget(btn)
            preset_row.addStretch()
            v.addLayout(preset_row)

        v.addStretch()

    def _save_fields(self):
        k = self.key
        self.cfg.config[k]["api_url"] = self.url_edit.text().strip()
        self.cfg.config[k]["api_key"] = self.key_edit.text()
        self.cfg.config[k]["model"]   = self.model_edit.text().strip()


class QwenPage(_DomesticProviderPage):
    """千问 / 通义（阿里云 DashScope）"""
    def __init__(self, cfg):
        self.title = "千问 / 通义（阿里云）"
        self.default_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.default_model = "qwen-plus"
        self.url_hint = "阿里云 DashScope OpenAI 兼容接口，通常无需修改"
        self.key_hint = "在阿里云百炼控制台创建 API Key：https://bailian.console.aliyun.com"
        self.model_hint = "例: qwen-plus / qwen-turbo / qwen-max / qwen-long"
        self.model_presets = ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-max-longcontext", "qwen-long"]
        super().__init__(cfg, "qwen")


class DoubaoPage(_DomesticProviderPage):
    """豆包（字节跳动 Ark）"""
    def __init__(self, cfg):
        self.title = "豆包（字节跳动）"
        self.default_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.default_model = "doubao-pro-4k"
        self.url_hint = "字节跳动方舟平台 OpenAI 兼容接口"
        self.key_hint = "在方舟控制台（https://console.volcengine.com/ark）创建 API Key"
        self.model_hint = "例: doubao-pro-4k / doubao-pro-32k / doubao-lite-4k（填写 Endpoint ID）"
        self.model_presets = ["doubao-pro-4k", "doubao-pro-32k", "doubao-pro-128k", "doubao-lite-4k"]
        super().__init__(cfg, "doubao")


class KimiPage(_DomesticProviderPage):
    """Kimi（Moonshot AI）"""
    def __init__(self, cfg):
        self.title = "Kimi（Moonshot AI）"
        self.default_url = "https://api.moonshot.cn/v1"
        self.default_model = "moonshot-v1-8k"
        self.url_hint = "Moonshot AI OpenAI 兼容接口，通常无需修改"
        self.key_hint = "在 Moonshot 开放平台创建 API Key：https://platform.moonshot.cn"
        self.model_hint = "例: moonshot-v1-8k / moonshot-v1-32k / moonshot-v1-128k"
        self.model_presets = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
        super().__init__(cfg, "kimi")


class GLMPage(_DomesticProviderPage):
    """GLM（智谱 AI）"""
    def __init__(self, cfg):
        self.title = "GLM / 智谱 AI"
        self.default_url = "https://open.bigmodel.cn/api/paas/v4"
        self.default_model = "glm-4"
        self.url_hint = "智谱 AI OpenAI 兼容接口，通常无需修改"
        self.key_hint = "在智谱开放平台创建 API Key：https://open.bigmodel.cn"
        self.model_hint = "例: glm-4 / glm-4-flash / glm-4-air / glm-4-long / glm-3-turbo"
        self.model_presets = ["glm-4", "glm-4-flash", "glm-4-air", "glm-4-long", "glm-3-turbo"]
        super().__init__(cfg, "glm")


class MiniMaxPage(_DomesticProviderPage):
    """MiniMax"""
    def __init__(self, cfg):
        self.title = "MiniMax"
        self.default_url = "https://api.minimax.chat/v1"
        self.default_model = "abab6.5s-chat"
        self.url_hint = "MiniMax OpenAI 兼容接口，通常无需修改"
        self.key_hint = "在 MiniMax 开放平台创建 API Key：https://www.minimax.chat"
        self.model_hint = "例: abab6.5s-chat / abab6.5g-chat / abab5.5-chat"
        self.model_presets = ["abab6.5s-chat", "abab6.5g-chat", "abab5.5s-chat", "abab5.5-chat"]
        super().__init__(cfg, "minimax")


# ────────────────────────────────────────────────────────────────────────────
# 模型列表页（顶部 Models List）
# ────────────────────────────────────────────────────────────────────────────

class ModelsListPage(QWidget):
    """
    新版模型列表页：
    - 直接展示 4 个区块：已激活模型 | 当前使用模型
                            当前使用Agent | 通用参数
    - 已激活模型 = 所有已配置的模型（来自各provider配置）
    - 所有「应用/保存」按钮统一在每个区块右侧
    """
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self._build()

    def _build(self):
        tokens = _theme_tokens()
        border = tokens["border"]

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── 标题 ──
        root.addWidget(_section_title("模型列表"))
        root.addSpacing(12)

        # ── 区块分隔线 ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"QFrame{{color:{border};background:{border};max-height:1px;min-height:1px;border:none;}}")
        root.addWidget(sep)
        root.addSpacing(12)

        # ── 区块1：已激活模型 ──
        self._build_active_models_content()   # 初始化 self.btn_refresh_active
        blk1 = self._build_block(
            "已激活模型",
            self._active_models_content_w,
            [self.btn_refresh_active],
            tokens,
        )
        root.addWidget(blk1)
        root.addSpacing(10)

        # 区块2：当前使用模型
        self._build_current_model_content()   # 初始化 self.btn_apply_model
        blk2 = self._build_block(
            "当前使用模型",
            self._curr_model_content_w,
            [self.btn_apply_model],
            tokens,
        )
        root.addWidget(blk2)
        root.addSpacing(10)

        # 区块3：通用参数
        self._build_params_content()          # 初始化 self.btn_save_params
        blk4 = self._build_block(
            "通用参数",
            self._params_content_w,
            [self.btn_save_params],
            tokens,
        )
        root.addWidget(blk4)

        root.addStretch()

    # ── 区块构建器 ─────────────────────────────────────────────────────────
    def _block_title_style(self, tokens):
        return f"QLabel{{color:{tokens['text_soft']};font-size:11px;font-weight:bold;padding:0;margin:0;}}"

    def _block_style(self, tokens):
        return (
            f"QWidget{{background:{tokens['surface_muted']};"
            f"border:1px solid {tokens['border']};border-radius: 2px;}}"
        )

    def _build_block(self, title: str, content_widget: QWidget, btns: list, tokens: dict) -> QWidget:
        """统一区块：标题行 + 内容行（右侧按钮）"""
        blk = QWidget()
        blk.setStyleSheet(self._block_style(tokens))
        v = QVBoxLayout(blk)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)

        # 标题行
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        lbl = QLabel(title)
        lbl.setStyleSheet(self._block_title_style(tokens))
        title_row.addWidget(lbl)
        title_row.addStretch()
        for b in btns:
            title_row.addWidget(b)
        v.addLayout(title_row)

        # 内容行
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(8)
        content_row.addWidget(content_widget, stretch=1)
        v.addLayout(content_row)

        return blk

    # ── 区块1：已激活模型（展示所有已配置的模型） ─────────────────────
    def _build_active_models_content(self):
        tokens = _theme_tokens()
        self._active_models_content_w = QWidget()
        self._active_models_content_w.setStyleSheet(
            f"QWidget{{background:transparent;border:none;}}"
        )
        v = QVBoxLayout(self._active_models_content_w)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(4)
        self.active_tags_w = QWidget()
        self.active_tags_lay = QFlowLayout(self.active_tags_w)
        self.active_tags_lay.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.active_tags_w)
        self._refresh_active_tags()
        self.btn_refresh_active = _make_btn("刷新", role="check")
        self.btn_refresh_active.clicked.connect(self._refresh_active_tags)

    def _refresh_active_tags(self):
        """收集所有已配置的模型（遍历各provider的model字段）"""
        while self.active_tags_lay.count():
            item = self.active_tags_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        tokens = _theme_tokens()
        accent = tokens["accent"]
        accent_soft = tokens["accent_soft"]
        text_muted = tokens["text_muted"]
        danger = tokens["danger"]

        # 遍历所有 provider，收集有 model 配置的项
        configured = []
        for prov_key in ["openai", "deepseek", "anthropic", "ollama",
                         "qwen", "doubao", "kimi", "glm", "minimax"]:
            pconf = self.cfg.config.get(prov_key, {})
            m = pconf.get("model", "").strip()
            key = pconf.get("api_key", "").strip()
            if m and key:
                configured.append((prov_key, m))

        if not configured:
            lbl = QLabel("暂无已配置模型，请在左侧「模型配置」中添加")
            lbl.setStyleSheet(
                f"QLabel{{color:{tokens['text_muted']};font-size:11px;"
                f"background:transparent;border:none;}}"
            )
            self.active_tags_lay.addWidget(lbl)
            return

        for prov_key, m in configured:
            tag = QWidget()
            tag.setStyleSheet(
                f"QWidget{{background:{accent_soft};"
                f"border:1px solid {accent};border-radius: 2px;}}"
            )
            tl = QHBoxLayout(tag)
            tl.setContentsMargins(8, 3, 4, 3)
            tl.setSpacing(4)
            # 显示：模型名 [provider]
            ml = QLabel(f"{m}  <span style='color:{tokens['text_muted']};font-size:10px;'>[{prov_key}]</span>")
            ml.setStyleSheet(
                f"QLabel{{color:{accent};font-size:12px;"
                f"background:transparent;border:none;}}"
            )
            tl.addWidget(ml)
            self.active_tags_lay.addWidget(tag)

    # ── 区块2：当前使用模型（醒目版）────────────────────────────────────
    def _build_current_model_content(self):
        tokens = _theme_tokens()
        accent = tokens["accent"]
        accent_soft = tokens["accent_soft"]
        surface_muted = tokens["surface_muted"]
        border = tokens["border"]
        text = tokens["text"]
        text_muted = tokens["text_muted"]
        danger = tokens.get("danger", "#e5534b")

        self._curr_model_content_w = QWidget()
        self._curr_model_content_w.setStyleSheet(
            f"QWidget{{background:transparent;border:none;}}"
        )
        v = QVBoxLayout(self._curr_model_content_w)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(10)

        # 当前模型大字高亮卡片
        self.model_highlight = QWidget()
        self.model_highlight.setStyleSheet(
            f"QWidget{{"
            f"background:{accent_soft};"
            f"border:2px solid {accent};"
            f"border-radius: 2px;"
            f"padding:10px 12px;"
            f"}}"
        )
        mh_layout = QVBoxLayout(self.model_highlight)
        mh_layout.setContentsMargins(8, 6, 8, 6)
        mh_layout.setSpacing(4)

        self.lbl_curr_tag = QLabel("◉ 当前使用模型")
        self.lbl_curr_tag.setStyleSheet(
            f"QLabel{{color:{accent};font-size:10px;font-weight:bold;"
            f"background:transparent;border:none;letter-spacing:0.5px;}}"
        )
        self.lbl_current_model = QLabel()
        self.lbl_current_model.setStyleSheet(
            f"QLabel{{color:{text};font-size:15px;font-weight:bold;"
            f"background:transparent;border:none;}}"
        )
        self.lbl_current_provider = QLabel()
        self.lbl_current_provider.setStyleSheet(
            f"QLabel{{color:{text_muted};font-size:11px;"
            f"background:transparent;border:none;}}"
        )
        mh_layout.addWidget(self.lbl_curr_tag)
        mh_layout.addWidget(self.lbl_current_model)
        mh_layout.addWidget(self.lbl_current_provider)
        v.addWidget(self.model_highlight)

        v.addSpacing(8)

        # 切换下拉
        sel_row = QHBoxLayout()
        sel_row.setContentsMargins(0, 0, 0, 0)
        sel_row.setSpacing(8)
        lbl = QLabel("切换模型")
        lbl.setStyleSheet(
            f"QLabel{{color:{text};font-size:12px;font-weight:bold;"
            f"background:transparent;border:none;}}"
        )
        sel_row.addWidget(lbl)
        self.cmb_curr_model = QComboBox()
        self.cmb_curr_model.setFixedWidth(200)
        self.cmb_curr_model.setStyleSheet(
            f"QComboBox{{"
            f"background:{tokens['surface']};"
            f"border:none;"
            f"border-radius: 2px;"
            f"padding:4px 8px;"
            f"color:{tokens['text']};"
            f"font-size:12px;"
            f"}}"
            f"QComboBox:hover{{background:{tokens['surface_muted']};}}"
            f"QComboBox:focus{{background:{tokens['surface_muted']};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox::down-arrow{{image:none; border-left:4px solid transparent; border-right:4px solid transparent; border-top:5px solid {tokens['text_muted']}; margin-right:6px;}}"
            f"QComboBox QAbstractItemView{{"
            f"background:{tokens['surface']};"
            f"color:{tokens['text']};"
            f"selection-background-color:{tokens['accent']};"
            f"border:none;"
            f"border-radius: 2px;"
            f"}}"
        )
        self._populate_curr_model_combo()
        sel_row.addWidget(self.cmb_curr_model)
        self.btn_apply_model = _make_btn("应用", role="primary")
        self.btn_apply_model.clicked.connect(self._apply_current_model)
        sel_row.addWidget(self.btn_apply_model)
        sel_row.addStretch()
        v.addLayout(sel_row)
        # 初始化时更新当前模型标签
        self._update_current_model_label()

    def _update_current_model_label(self):
        active = self.cfg.get_active()
        provider = active.get("provider", "—")
        model = active.get("model", "—")
        prov_display = {"openai": "OpenAI", "deepseek": "DeepSeek", "anthropic": "Anthropic",
                        "ollama": "Ollama", "qwen": "通义千问", "doubao": "豆包",
                        "kimi": "Kimi", "glm": "智谱GLM", "minimax": "MiniMax"}.get(provider, provider)
        self.lbl_current_model.setText(model if model else "— 未选择 —")
        self.lbl_current_provider.setText(f"提供方：{prov_display}")

    def _populate_curr_model_combo(self):
        self.cmb_curr_model.blockSignals(True)
        self.cmb_curr_model.clear()
        items = []
        for prov_key in ["openai", "deepseek", "anthropic", "ollama",
                         "qwen", "doubao", "kimi", "glm", "minimax"]:
            pconf = self.cfg.config.get(prov_key, {})
            m = pconf.get("model", "").strip()
            if m:
                items.append((prov_key, m))
        for pk, m in items:
            self.cmb_curr_model.addItem(f"{pk} / {m}", userData=pk)
        cur = self.cfg.config.get("active_provider", "openai")
        idx = self.cmb_curr_model.findData(cur)
        if idx >= 0:
            self.cmb_curr_model.setCurrentIndex(idx)
        self.cmb_curr_model.blockSignals(False)

    def _apply_current_model(self):
        idx = self.cmb_curr_model.currentIndex()
        if idx < 0:
            return
        prov_key = self.cmb_curr_model.currentData()
        model = self.cmb_curr_model.currentText().split(" / ", 1)[-1].strip()
        self.cfg.config["active_provider"] = prov_key
        models = self.cfg.config.setdefault("active_models", [])
        if model not in models:
            models.append(model)
        self.cfg.save()
        self._update_current_model_label()
        self._refresh_active_tags()
        _info_box(self, "已应用", f"当前模型已切换为 {model}（{prov_key}）")

    # ── 区块3：通用参数 ──────────────────────────────────────────────────
    def _build_params_content(self):
        self._params_content_w = QWidget()
        self._params_content_w.setStyleSheet(
            f"QWidget{{background:transparent;border:none;}}"
        )
        v = QVBoxLayout(self._params_content_w)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(6)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 80)
        grid.setColumnMinimumWidth(1, 100)
        grid.setColumnStretch(2, 1)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setDecimals(2)
        self.temp_spin.setFixedWidth(100)
        self.temp_spin.setValue(self.cfg.config.get("temperature", 0.7))
        grid.addWidget(QLabel("Temperature"), 0, 0)
        grid.addWidget(self.temp_spin, 0, 1)
        grid.addWidget(QLabel("0=确定性，2=最发散"), 0, 2)

        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(256, 128000)
        self.tokens_spin.setSingleStep(256)
        self.tokens_spin.setFixedWidth(100)
        self.tokens_spin.setValue(self.cfg.config.get("max_tokens", 4096))
        grid.addWidget(QLabel("Max Tokens"), 1, 0)
        grid.addWidget(self.tokens_spin, 1, 1)
        grid.addWidget(QLabel("最大回复token数"), 1, 2)

        v.addLayout(grid)
        self.btn_save_params = _make_btn("保存", role="primary")
        self.btn_save_params.clicked.connect(self._save_params)

    def _save_params(self):
        self.cfg.config["temperature"] = self.temp_spin.value()
        self.cfg.config["max_tokens"] = self.tokens_spin.value()
        self.cfg.save()
        _info_box(self, "已保存", "通用参数已保存")


    # 外部刷新接口（供主窗口保存后调用）
    def refresh(self):
        self._refresh_active_tags()
        self._update_current_model_label()
        self._populate_curr_model_combo()


# ── 简易 Flow Layout（标签换行布局）──────────────────────────────────────
class QFlowLayout(QLayout):
    def __init__(self, parent=None, h_spacing=6, v_spacing=6):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, idx):
        return self._items[idx] if 0 <= idx < len(self._items) else None

    def takeAt(self, idx):
        return self._items.pop(idx) if 0 <= idx < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        x, y = rect.x() + m.left(), rect.y() + m.top()
        line_height = 0
        for item in self._items:
            w = item.widget()
            sh = item.sizeHint()
            next_x = x + sh.width() + self._h_spacing
            if next_x - self._h_spacing > rect.right() - m.right() and line_height > 0:
                x = rect.x() + m.left()
                y += line_height + self._v_spacing
                next_x = x + sh.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sh))
            x = next_x
            line_height = max(line_height, sh.height())
        return y + line_height - rect.y() + m.bottom()


# ────────────────────────────────────────────────────────────────────────────
# 主配置窗口
# ────────────────────────────────────────────────────────────────────────────

class ModelConfigWindow(QDialog):

    PAGES = [
        ("模型列表",       "models"),
        ("OpenAI",        "openai"),
        ("DeepSeek",      "deepseek"),
        ("Anthropic",     "anthropic"),
        ("LiteLLM",       "litellm"),
        ("Amazon Bedrock","bedrock"),
        ("Ollama（本地）", "ollama"),
        ("千问 / 通义",   "qwen"),
        ("豆包",          "doubao"),
        ("Kimi",          "kimi"),
        ("GLM / 智谱",    "glm"),
        ("MiniMax",       "minimax"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("AI 大模型配置")
        self.setMinimumSize(860, 600)
        self.resize(960, 680)
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        # 先创建标题栏（必须在 _build_ui 之前，因为要插入到布局顶）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "AI 大模型配置", self._tokens, title_height=38)
        self._title_close_btn.clicked.connect(self.close)
        self.cfg = ModelConfig()
        self._page_cache: dict[str, QWidget] = {}
        # 样式在 _build_ui 里设置
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(_build_window_style(self._tokens))
        # ── 左侧导航 ─────────────────────────────
        left = QWidget()
        left.setObjectName("mcwNavPanel")
        left.setFixedWidth(160)
        sep_clr = self._tokens["border"]
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        title = QLabel("设置")
        title.setObjectName("nav_title")
        lv.addWidget(title)

        # 导航列表用 QListWidget，内部分组用 separator item
        self.nav = QListWidget()
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 记录每个 page key 对应的 row index（跳过分隔行）
        self._nav_row_map: list[Optional[int]] = []  # index in nav → page index or None(separator)
        self._page_rows: list[int] = []  # page index → nav row

        # 分组定义（基础模型+国产大模型已合并）
        groups = [
            ("", ["models"]),
            ("模型配置", ["openai", "deepseek", "anthropic", "litellm", "bedrock", "ollama",
                         "qwen", "doubao", "kimi", "glm", "minimax"]),
        ]
        key_to_label = {k: lbl for lbl, k in self.PAGES}
        page_key_order = [k for _, k in self.PAGES]
        nav_row = 0
        for group_name, keys in groups:
            if group_name:
                # 分组标题行（不可选中）—— 带上边距视觉分隔
                sep_item = QListWidgetItem(group_name.upper())
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
                muted_color = QColor(self._tokens.get("text_muted", "#9ca3af"))
                sep_item.setForeground(muted_color)
                font = sep_item.font()
                font.setPointSize(9)
                font.setBold(True)
                font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
                sep_item.setFont(font)
                sep_item.setSizeHint(QSize(0, 30))
                self.nav.addItem(sep_item)
                self._nav_row_map.append(None)
                nav_row += 1
            for k in keys:
                page_idx = page_key_order.index(k)
                item = QListWidgetItem(key_to_label[k])
                self.nav.addItem(item)
                self._nav_row_map.append(page_idx)
                self._page_rows.append(nav_row)
                nav_row += 1

        lv.addWidget(self.nav, stretch=1)

        # ── 右侧内容 ─────────────────────────────
        right = QWidget()
        right.setObjectName("mcwContentPanel")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { border: none; background: transparent; }")
        rv.addWidget(self.stack)

        # 预先构建所有页（按 PAGES 顺序）
        page_map = {
            "models":  ModelsListPage,
            "openai":  OpenAIPage,
            "deepseek": DeepSeekPage,
            "anthropic": AnthropicPage,
            "litellm": LiteLLMPage,
            "bedrock": BedrockPage,
            "ollama":  OllamaPage,
            "qwen":    QwenPage,
            "doubao":  DoubaoPage,
            "kimi":    KimiPage,
            "glm":     GLMPage,
            "minimax": MiniMaxPage,
        }
        for _, key in self.PAGES:
            page = page_map[key](self.cfg)
            # 用一个带内边距的容器包裹 page
            wrapper = QWidget()
            wrapper.setStyleSheet("QWidget { background: transparent; }")
            wl = QVBoxLayout(wrapper)
            wl.setContentsMargins(28, 20, 28, 16)
            wl.setSpacing(0)
            wl.addWidget(page)
            scroll = QScrollArea()
            scroll.setWidget(wrapper)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            self.stack.addWidget(scroll)

        # ── 中间内容区：左导航 + 右内容 ──
        middle = QWidget()
        middle.setObjectName("dialogContent")
        ml = QHBoxLayout(middle)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        ml.addWidget(left)
        ml.addWidget(right, stretch=1)

        # 导航切换：跳过分隔行
        def _on_nav_changed(row):
            if row < 0 or row >= len(self._nav_row_map):
                return
            page_idx = self._nav_row_map[row]
            if page_idx is None:
                # 点到分组标题，跳到下一个可选项
                next_row = row + 1
                while next_row < len(self._nav_row_map) and self._nav_row_map[next_row] is None:
                    next_row += 1
                if next_row < len(self._nav_row_map):
                    self.nav.setCurrentRow(next_row)
                return
            self.stack.setCurrentIndex(page_idx)
            # 保存当前导航行，下次打开时恢复
            save_window_state("model_config_nav", row)

        self.nav.currentRowChanged.connect(_on_nav_changed)

        # 恢复上次选中的页面（model_config 窗口专用 key）
        saved_nav_row = load_window_state("model_config_nav", -1)
        if saved_nav_row > 0 and saved_nav_row < self.nav.count():
            self.nav.setCurrentRow(saved_nav_row)
        else:
            # 默认选中"模型列表"（找到 page_idx == 0 对应的行）
            for i, pi in enumerate(self._nav_row_map):
                if pi == 0:
                    self.nav.setCurrentRow(i)
                    break

        # ── 总布局：标题栏 + 内容 ─────────────────
        outer = QVBoxLayout()
        outer.setContentsMargins(1, 1, 1, 1)  # 1px 让 QDialog 边框可见
        outer.setSpacing(0)
        outer.addWidget(self._title_bar)  # 标题栏在最上（含 ✕ 关闭按钮）
        outer.addWidget(middle, stretch=1)  # 主内容区

        self.setLayout(outer)