"""
version.py — AIDBTools 版本与开发者信息

所有需要引用版本/作者信息的模块，统一从此处 import。
日常运行直接读取本文件；打包脚本会调用下方工具函数自动递增补丁版本。
"""

from __future__ import annotations

import datetime as _dt
import pathlib as _pathlib
import re as _re
from typing import Optional, Tuple


# ── 版本号 ─────────────────────────────────────────────────────────
VERSION       = "1.1.25"
VERSION_TUPLE = (1, 1, 25)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)          # (major, minor, patch)
RELEASE_DATE  = "2026-05-12"

# ── 构建平台标识（由打包脚本写入，源码默认 "source"）──────────────
# 可选值: "windows" | "linux" | "domestic"（国产系统）| "source"
BUILD_PLATFORM = "source"

# ── 开发者信息 ─────────────────────────────────────────────────────
AUTHOR        = "石慧兵"
AUTHOR_EMAIL  = "1795794877@qq.com"

# ── 产品信息 ───────────────────────────────────────────────────────
APP_NAME      = "团子"
APP_FULL_NAME = "团子"
APP_DESC      = "新一代 AI 数据库工具，支持 MySQL / PostgreSQL / SQL Server / Oracle / 达梦 / 人大金仓 / 虚谷 / 星环等多种数据库的智能管理与 AI 协作"
HOMEPAGE      = ""


_VERSION_LINE_RE = _re.compile(r'^VERSION\s*=\s*"([^"]+)"', _re.MULTILINE)
_VERSION_TUPLE_LINE_RE = _re.compile(r'^VERSION_TUPLE\s*=\s*\([^\)]*\)', _re.MULTILINE)
_RELEASE_DATE_LINE_RE = _re.compile(r'^RELEASE_DATE\s*=\s*"([^"]+)"', _re.MULTILINE)
_BUILD_PLATFORM_LINE_RE = _re.compile(r'^BUILD_PLATFORM\s*=\s*"([^"]+)"', _re.MULTILINE)
_VALID_BUILD_PLATFORMS = {"windows", "linux", "domestic", "kylin_arm", "kylin_x86", "kylin_x86_offline", "source"}


# ── 版权声明 ───────────────────────────────────────────────────────
COPYRIGHT = f"Copyright © {RELEASE_DATE[:4]}  {AUTHOR}  <{AUTHOR_EMAIL}>"


def _version_file_path(file_path: Optional[str] = None) -> _pathlib.Path:
    return _pathlib.Path(file_path) if file_path else _pathlib.Path(__file__)


def _replace_once(pattern: _re.Pattern[str], text: str, replacement: str, label: str) -> str:
    new_text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"未找到 {label} 定义，无法更新版本文件")
    return new_text


def parse_version(version: str) -> Tuple[int, int, int]:
    parts = version.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"不支持的版本号格式：{version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _read_version_text(file_path: Optional[str] = None) -> str:
    return _version_file_path(file_path).read_text(encoding="utf-8")


def read_current_version(file_path: Optional[str] = None) -> str:
    text = _read_version_text(file_path)
    match = _VERSION_LINE_RE.search(text)
    if not match:
        raise RuntimeError("version.py 中缺少 VERSION 定义")
    return match.group(1)


def update_version_metadata(
    version: Optional[str] = None,
    build_platform: Optional[str] = None,
    release_date: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    path = _version_file_path(file_path)
    text = path.read_text(encoding="utf-8")

    current_version_match = _VERSION_LINE_RE.search(text)
    if not current_version_match:
        raise RuntimeError("version.py 中缺少 VERSION 定义")
    current_version = current_version_match.group(1)

    current_release_date_match = _RELEASE_DATE_LINE_RE.search(text)
    if not current_release_date_match:
        raise RuntimeError("version.py 中缺少 RELEASE_DATE 定义")
    current_release_date = current_release_date_match.group(1)

    final_version = version or current_version
    major, minor, patch = parse_version(final_version)

    if build_platform is not None and build_platform not in _VALID_BUILD_PLATFORMS:
        raise ValueError(f"不支持的构建平台：{build_platform}")

    if release_date is not None:
        final_release_date = release_date
    elif version is not None and final_version != current_version:
        final_release_date = _dt.date.today().isoformat()
    else:
        final_release_date = current_release_date

    text = _replace_once(_VERSION_LINE_RE, text, f'VERSION       = "{final_version}"', "VERSION")
    text = _replace_once(_VERSION_TUPLE_LINE_RE, text, f'VERSION_TUPLE = ({major}, {minor}, {patch})          # (major, minor, patch)', "VERSION_TUPLE")
    text = _replace_once(_RELEASE_DATE_LINE_RE, text, f'RELEASE_DATE  = "{final_release_date}"', "RELEASE_DATE")
    if build_platform is not None:
        text = _replace_once(_BUILD_PLATFORM_LINE_RE, text, f'BUILD_PLATFORM = "{build_platform}"', "BUILD_PLATFORM")

    path.write_text(text, encoding="utf-8")
    return final_version


def bump_patch_version(file_path: Optional[str] = None) -> str:
    """
    递增补丁版本号。
    规则：patch 超过 99 时自动进位到 minor，patch 归零。
    例如：1.0.99 → 1.1.0，1.0.100 → 1.1.0，1.2.150 → 1.3.0
    """
    current_version = read_current_version(file_path)
    major, minor, patch = parse_version(current_version)
    patch += 1
    if patch > 99:
        patch = 0
        minor += 1
    new_version = f"{major}.{minor}.{patch}"
    return update_version_metadata(version=new_version, file_path=file_path)


def set_build_platform(build_platform: str, file_path: Optional[str] = None) -> str:
    update_version_metadata(build_platform=build_platform, file_path=file_path)
    return build_platform


def get_version_string() -> str:
    """返回完整版本字符串，例如：AIDBTools v1.0.0 (windows)"""
    plat = f" [{BUILD_PLATFORM}]" if BUILD_PLATFORM != "source" else ""
    return f"{APP_NAME} v{VERSION}{plat}"


def get_about_text() -> str:
    """返回「关于」对话框的 HTML 富文本"""
    plat_map = {
        "windows": "Windows",
        "linux":   "Linux",
        "domestic": "国产操作系统（银河麒麟 / 统信UOS 等）",
        "kylin_arm": "银河麒麟 ARM aarch64",
        "kylin_x86": "银河麒麟 x86_64",
        "kylin_x86_offline": "银河麒麟 x86_64（完全离线版）",
        "source":  "源码运行",
    }
    plat_label = plat_map.get(BUILD_PLATFORM, BUILD_PLATFORM)
    return f"""
<div style="font-family: '微软雅黑', 'PingFang SC', sans-serif; line-height: 1.8;">
  <h2 style="margin:0 0 4px 0;">{APP_FULL_NAME}</h2>
  <p style="margin:0; color:#888; font-size:13px;">版本 {VERSION} &nbsp;·&nbsp; {RELEASE_DATE} &nbsp;·&nbsp; {plat_label}</p>
  <hr style="border:none; border-top:1px solid #ddd; margin:10px 0;">
  <p>{APP_DESC}</p>
  <hr style="border:none; border-top:1px solid #ddd; margin:10px 0;">
  <table style="font-size:13px; border-collapse:collapse;">
    <tr><td style="color:#888; padding-right:12px;">开发者</td><td><b>{AUTHOR}</b></td></tr>
    <tr><td style="color:#888; padding-right:12px;">联系邮箱</td>
        <td><a href="mailto:{AUTHOR_EMAIL}" style="color:#1677FF;">{AUTHOR_EMAIL}</a></td></tr>
    <tr><td style="color:#888; padding-right:12px;">版权</td><td style="color:#666;">{COPYRIGHT}</td></tr>
  </table>
  <hr style="border:none; border-top:1px solid #ddd; margin:10px 0;">
  <p style="font-size:12px; color:#aaa;">
    团子是一款面向开发、运维与数据分析场景的新一代AI数据库工具。<br>
    支持数据库：MySQL · PostgreSQL · SQL Server · Oracle · 虚谷<br>
    达梦 · 人大金仓 · 高斯 · OceanBase · 星环 ArgoDB/Inceptor 等
  </p>
</div>
""".strip()
