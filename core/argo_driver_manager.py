"""
argo_driver_manager.py
星环科技（Transwarp）数据库驱动自动探测与管理。

优先级策略：
  Windows / Linux：优先 JDBC（quark-driver > inceptor-driver）
  若系统已配置星环 ODBC DSN，也可回退 ODBC


对外接口：
  ArgoDriverManager.detect(jar_path=None) -> DriverInfo
  DriverInfo.mode        : "odbc" | "jdbc" | "none"
  DriverInfo.param       : ODBC DSN 驱动名 / JDBC jar 路径
  DriverInfo.driver_class: JDBC 驱动类（ODBC 模式为 None）
  DriverInfo.description : 人类可读说明
  DriverInfo.odbc_installer : ODBC 安装包路径（未安装时指引）
"""

import os
import re
import sys
import zipfile
import subprocess
from dataclasses import dataclass, field
from typing import Optional


# ── 项目内置驱动目录（相对于本文件） ─────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_DRIVERS_DIR = os.path.join(_PROJECT_ROOT, "drivers", "transwarp")

# JDBC jar 搜索顺序（首选 quark-driver）
_JDBC_JAR_NAMES = [
    "quark-driver-8.37.3.jar",
    "quark-driver-8.37.jar",
    "inceptor-driver-8.37.3.jar",
    "inceptor-driver-8.37.jar",
]

# Windows ODBC 安装包
_ODBC_WIN64_EXE = os.path.join(_DRIVERS_DIR, "odbc", "win64", "inceptor-connector-odbc-8.37.3-winx64.exe")
_ODBC_WIN32_EXE = os.path.join(_DRIVERS_DIR, "odbc", "win32", "inceptor-connector-odbc-8.37.3-win32.exe")

# Linux ODBC 包列表（供用户指引）
_ODBC_LINUX_PKGS = {
    "x86_64.rpm": os.path.join(_DRIVERS_DIR, "odbc", "linux", "inceptor-connector-odbc-8.37-1.el7.x86_64.rpm"),
    "i686.rpm"  : os.path.join(_DRIVERS_DIR, "odbc", "linux", "inceptor-connector-odbc-8.37-1.el7.i686.rpm"),
    "aarch64.rpm": os.path.join(_DRIVERS_DIR, "odbc", "linux", "inceptor-connector-odbc-8.37.0-1.ky10.ky10.aarch64.rpm"),
    ".deb"      : os.path.join(_DRIVERS_DIR, "odbc", "linux", "inceptor-connector-odbc-8.37.0.deb"),
}

# JDBC 驱动类优先级（从 JAR 实际内容自动选）
_JDBC_DRIVER_CANDIDATES = [
    "io.transwarp.jdbc.QuarkDriver",
    "io.transwarp.jdbc.InceptorDriver",
    "io.transwarp.hadoop.hive.jdbc.HiveDriver",
    "org.apache.hive.jdbc.HiveDriver",
]

# Windows ODBC 驱动注册名（安装后系统注册的名称）
_ODBC_DRIVER_NAMES = [
    "Transwarp Inceptor",
    "Inceptor",
    "TW Inceptor ODBC Driver",
]


@dataclass
class DriverInfo:
    mode: str                          # "odbc" | "jdbc" | "none"
    param: str = ""                    # ODBC: DSN驱动名; JDBC: jar路径
    driver_class: Optional[str] = None # JDBC 驱动类
    description: str = ""              # 人类可读说明
    odbc_installer: str = ""           # Windows 安装包路径（未安装时）
    jdbc_jar: str = ""                 # JDBC jar 的实际路径
    extra: dict = field(default_factory=dict)


class ArgoDriverManager:
    """星环驱动自动探测管理器（单例风格，无实例）"""

    # ── 对外主入口 ─────────────────────────────────────────────────────
    @classmethod
    def detect(cls, jar_path: str = "") -> DriverInfo:
        """
        自动探测可用驱动并返回 DriverInfo。
        jar_path: 用户手动指定的 JAR 路径（优先使用；为空则搜索内置目录）
        优先级：JDBC > ODBC（仅在系统已配置星环 DSN 时启用）

        """
        jdbc_info = cls._detect_jdbc(jar_path)
        if jdbc_info.mode == "jdbc":
            return jdbc_info

        odbc_info = cls._detect_odbc()
        if odbc_info:
            return odbc_info

        odbc_drivers = cls._get_transwarp_odbc_drivers()
        if odbc_drivers:
            installer = cls.get_odbc_installer_path()
            return DriverInfo(
                mode="none",
                description=(
                    f"{jdbc_info.description}；已检测到星环 ODBC 驱动：{'、'.join(odbc_drivers)}，"
                    "但系统中尚未配置可用的星环 DSN。为避免直接 Driver=... 硬连触发 HY000/517，"
                    "当前程序将优先使用 JDBC；若你必须走 ODBC，请先在系统 ODBC 数据源管理器中创建 DSN。"
                ),
                odbc_installer=installer,
                jdbc_jar=jdbc_info.jdbc_jar,
                extra={"odbc_drivers": odbc_drivers},
            )

        return jdbc_info


    @classmethod
    def detect_jdbc(cls, jar_path: str = "") -> DriverInfo:
        """只探测 JDBC，供连接阶段在 ODBC 失败时做兜底回退。"""
        return cls._detect_jdbc(jar_path)


    # ── ODBC 探测（跨平台）────────────────────────────────────────────
    @classmethod
    def _get_transwarp_odbc_drivers(cls) -> list[str]:
        """返回系统里已注册的星环 ODBC 驱动名称列表。"""
        try:
            import pyodbc
            installed = list(pyodbc.drivers())
        except Exception:
            return []

        hits = []
        seen = set()
        for drv in installed:
            drv_text = str(drv or "").strip()
            if not drv_text:
                continue
            lower_drv = drv_text.lower()
            if any(name.lower() in lower_drv or lower_drv in name.lower() for name in _ODBC_DRIVER_NAMES):
                if lower_drv not in seen:
                    seen.add(lower_drv)
                    hits.append(drv_text)
        return hits

    @classmethod
    def _get_transwarp_odbc_dsns(cls) -> list[tuple[str, str]]:
        """返回系统中已配置且绑定到星环驱动的 DSN 列表。"""
        try:
            import pyodbc
            data_sources = pyodbc.dataSources()
        except Exception:
            return []

        items = list(data_sources.items()) if hasattr(data_sources, "items") else list(data_sources)
        hits = []
        seen = set()
        for dsn_name, driver_name in items:
            dsn_text = str(dsn_name or "").strip()
            driver_text = str(driver_name or "").strip()
            if not dsn_text or not driver_text:
                continue
            lower_driver = driver_text.lower()
            if any(name.lower() in lower_driver or lower_driver in name.lower() for name in _ODBC_DRIVER_NAMES):
                key = (dsn_text.lower(), lower_driver)
                if key not in seen:
                    seen.add(key)
                    hits.append((dsn_text, driver_text))
        return hits

    @classmethod
    def _detect_odbc(cls) -> Optional[DriverInfo]:
        """仅在系统已配置星环 DSN 时启用 ODBC，避免 DSN-less 直连触发 517。"""
        dsns = cls._get_transwarp_odbc_dsns()
        if not dsns:
            return None

        dsn_name, driver_name = dsns[0]
        return DriverInfo(
            mode="odbc",
            param=dsn_name,
            description=f"[OK] ODBC DSN 已配置：{dsn_name} → {driver_name}",
            odbc_installer="",
            extra={"dsn_name": dsn_name, "driver_name": driver_name},
        )


    # ── JDBC 探测 ─────────────────────────────────────────────────────
    @classmethod
    def _detect_jdbc(cls, user_jar: str = "") -> DriverInfo:
        """按优先级找 JAR 并探测驱动类，同时检查 Java 环境"""
        jar = cls._resolve_jar(user_jar)
        installer = cls.get_odbc_installer_path()

        if not jar:
            return DriverInfo(
                mode="none",
                description="[FAIL] 未找到可用的星环驱动（JDBC jar 或 ODBC）",
                odbc_installer=installer,
            )

        # 检查 Java 是否可用
        java_ok, java_hint = cls._check_java()
        if not java_ok:
            return DriverInfo(
                mode="none",
                description=f"[FAIL] 找到 JAR 但缺少 Java 运行环境：{java_hint}",
                odbc_installer=installer,
                jdbc_jar=jar,
            )

        driver_cls = cls._detect_jar_driver_class(jar)
        return DriverInfo(
            mode="jdbc",
            param=jar,
            driver_class=driver_cls,
            jdbc_jar=jar,
            description=f"[OK] JDBC：{os.path.basename(jar)} → {driver_cls.split('.')[-1]}  [Java: {java_hint}]",
            odbc_installer=installer,
        )

    # ── Java 检测 ─────────────────────────────────────────────────────
    @staticmethod
    def _parse_java_major(ver_line: str) -> int:
        """从 java -version 首行里提取主版本号。"""
        text = str(ver_line or "").strip()
        if not text:
            return 0
        match = re.search(r'"([^"]+)"', text)
        version_text = match.group(1) if match else text
        if version_text.startswith("1."):
            parts = version_text.split(".")
            if len(parts) > 1 and parts[1].isdigit():
                return int(parts[1])
        match = re.match(r"(\d+)", version_text)
        return int(match.group(1)) if match else 0

    @classmethod
    def _run_java_version(cls, java_cmd: str) -> tuple[int, str]:
        """运行指定 java 可执行文件并返回 (主版本号, 首行说明)。"""
        try:
            result = subprocess.run(
                [java_cmd, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
        except FileNotFoundError:
            return 0, ""
        except Exception:
            return 0, ""

        output = (result.stderr or result.stdout or "").strip()
        if not output:
            return 0, ""
        first_line = output.splitlines()[0].strip()
        return cls._parse_java_major(first_line), first_line

    @staticmethod
    def _is_java_home(path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        java_exe = "java.exe" if sys.platform.startswith("win") else "java"
        return os.path.isfile(os.path.join(path, "bin", java_exe))

    @classmethod
    def _set_java_home(cls, java_home: str) -> None:
        """设置 JAVA_HOME，并把对应 bin 提到 PATH 前面。"""
        if not cls._is_java_home(java_home):
            return
        java_home = os.path.abspath(java_home)
        os.environ["JAVA_HOME"] = java_home
        bin_dir = os.path.join(java_home, "bin")
        current_path = os.environ.get("PATH", "")
        path_parts = current_path.split(os.pathsep) if current_path else []
        norm_bin = os.path.normcase(bin_dir)
        filtered = [p for p in path_parts if os.path.normcase(p) != norm_bin]
        os.environ["PATH"] = os.pathsep.join([bin_dir, *filtered]) if filtered else bin_dir

    @classmethod
    def _iter_java_home_candidates(cls) -> list[str]:
        """枚举当前机器可能存在的 Java 安装目录。"""
        candidates = []
        seen = set()

        def add(path: str):
            if not path:
                return
            abs_path = os.path.abspath(path)
            norm_path = os.path.normcase(abs_path)
            if norm_path in seen or not cls._is_java_home(abs_path):
                return
            seen.add(norm_path)
            candidates.append(abs_path)

        add(os.environ.get("JAVA_HOME", ""))

        if sys.platform.startswith("win"):
            roots = []
            for base in [
                os.environ.get("ProgramFiles", ""),
                os.environ.get("ProgramW6432", ""),
                os.environ.get("ProgramFiles(x86)", ""),
            ]:
                if base:
                    roots.extend([
                        os.path.join(base, "Java"),
                        os.path.join(base, "Eclipse Adoptium"),
                        os.path.join(base, "AdoptOpenJDK"),
                        os.path.join(base, "Zulu"),
                        os.path.join(base, "BellSoft"),
                        os.path.join(base, "Amazon Corretto"),
                        os.path.join(base, "Microsoft"),
                    ])
            for root in roots:
                if not os.path.isdir(root):
                    continue
                try:
                    for name in os.listdir(root):
                        add(os.path.join(root, name))
                except OSError:
                    continue
        else:
            for jd in [
                "/usr/lib/jvm/default-java",
                "/usr/lib/jvm/java-21-openjdk-amd64",
                "/usr/lib/jvm/java-21-openjdk-arm64",
                "/usr/lib/jvm/java-17-openjdk-amd64",
                "/usr/lib/jvm/java-17-openjdk-arm64",
                "/usr/lib/jvm/java-11-openjdk-amd64",
                "/usr/lib/jvm/java-11-openjdk-arm64",
                "/usr/lib/jvm/java-8-openjdk-amd64",
                "/usr/lib/jvm/java-8-openjdk-arm64",
                "/usr/local/java",
                "/opt/jdk",
                "/usr/java/default",
            ]:
                add(jd)
            try:
                r = subprocess.run(
                    ["readlink", "-f", "/usr/bin/java"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=3,
                )
                if r.returncode == 0 and r.stdout.strip():
                    java_bin = r.stdout.strip()
                    add(os.path.dirname(os.path.dirname(java_bin)))
            except Exception:
                pass


        return candidates

    @classmethod
    def _pick_java_runtime(cls, min_major: int = 11) -> tuple[str, int, str]:
        """挑选满足最低版本要求的最佳 Java 运行时。"""
        java_exe = "java.exe" if sys.platform.startswith("win") else "java"
        best_home = ""
        best_major = 0
        best_line = ""

        for java_home in cls._iter_java_home_candidates():
            major, line = cls._run_java_version(os.path.join(java_home, "bin", java_exe))
            if major >= min_major and major > best_major:
                best_home = java_home
                best_major = major
                best_line = line

        return best_home, best_major, best_line

    @classmethod
    def _check_java(cls) -> tuple[bool, str]:
        """
        检查 Java 是否可用，同时优先切换到 JPype 可用的 Java 11+ 运行时。
        返回 (可用, 说明字符串)
        """
        min_major = 11
        current_major, current_line = cls._run_java_version("java")
        current_line_text = current_line.strip('"').strip() if current_line else ""
        if current_major >= min_major:
            return True, current_line_text

        java_home, major, line = cls._pick_java_runtime(min_major=min_major)
        if java_home:
            cls._set_java_home(java_home)
            chosen = line.strip('"').strip()
            if current_major and current_line_text:
                return True, f"{chosen}（已自动切换，原 PATH 为 {current_line_text}）"
            return True, f"{chosen}（已自动设置 JAVA_HOME={java_home}）"

        if current_major and current_line_text:
            return False, (
                f"当前检测到 {current_line_text}，但 JPype1 1.6 需要 Java 11 或更高版本。"
                "请安装或切换到 JDK 17 / 21 后重试。"
            )

        return False, "未检测到可用的 Java 11+ 运行环境，请先安装 JDK 17 / 21。"

    # ── JAR 路径解析 ──────────────────────────────────────────────────

    @classmethod
    def _resolve_jar(cls, user_jar: str) -> str:
        """
        解析最终使用的 JAR 路径：
        1. 用户手动填写的路径（优先）
        2. 项目内置 drivers/transwarp/jdbc/ 里的 JAR
        """
        if user_jar and os.path.isfile(user_jar):
            return user_jar

        jdbc_dir = os.path.join(_DRIVERS_DIR, "jdbc")
        for name in _JDBC_JAR_NAMES:
            p = os.path.join(jdbc_dir, name)
            if os.path.isfile(p):
                return p

        # 向上在项目根目录找 jar（兼容旧位置）
        for name in _JDBC_JAR_NAMES:
            p = os.path.join(_PROJECT_ROOT, name)
            if os.path.isfile(p):
                return p

        return ""

    # ── JAR 驱动类探测 ────────────────────────────────────────────────
    @classmethod
    def _detect_jar_driver_class(cls, jar_path: str) -> str:
        """从 JAR 文件内容选最优驱动类"""
        try:
            with zipfile.ZipFile(jar_path, 'r') as z:
                names = set(z.namelist())
            for cls_name in _JDBC_DRIVER_CANDIDATES:
                cls_path = cls_name.replace('.', '/') + '.class'
                if cls_path in names:
                    return cls_name
        except Exception:
            pass
        return _JDBC_DRIVER_CANDIDATES[-1]

    # ── ODBC 安装包获取 ───────────────────────────────────────────────
    @classmethod
    def get_odbc_installer_path(cls) -> str:
        """返回当前平台对应的 ODBC 安装包路径"""
        if sys.platform.startswith("win"):
            import struct
            is64 = struct.calcsize("P") * 8 == 64
            return _ODBC_WIN64_EXE if is64 else _ODBC_WIN32_EXE
        else:
            # Linux：根据架构和包管理器返回最合适的包
            import platform
            arch = platform.machine().lower()
            if "aarch64" in arch or "arm64" in arch:
                return _ODBC_LINUX_PKGS["aarch64.rpm"]
            # deb 系（麒麟/UOS/Deepin/Ubuntu）优先 deb
            if os.path.isfile(_ODBC_LINUX_PKGS[".deb"]):
                try:
                    result = subprocess.run(
                        ["dpkg", "--version"], capture_output=True, timeout=2
                    )
                    if result.returncode == 0:
                        return _ODBC_LINUX_PKGS[".deb"]
                except Exception:
                    pass
            return _ODBC_LINUX_PKGS["x86_64.rpm"]

    # ── 列出内置 JDBC JARs ────────────────────────────────────────────
    @classmethod
    def list_builtin_jars(cls) -> list[str]:
        """返回项目内置的所有 JDBC jar 路径列表"""
        jdbc_dir = os.path.join(_DRIVERS_DIR, "jdbc")
        if not os.path.isdir(jdbc_dir):
            return []
        return [
            os.path.join(jdbc_dir, f)
            for f in os.listdir(jdbc_dir)
            if f.endswith(".jar")
        ]

    # ── JDBC URL 构建 ─────────────────────────────────────────────────
    @staticmethod
    def build_jdbc_url(host: str, port: str, dbname: str = "") -> str:
        db_part = f"/{dbname}" if dbname else ""
        return f"jdbc:hive2://{host}:{port}{db_part}"

    # ── ODBC 连接字符串构建 ───────────────────────────────────────────
    @staticmethod
    def build_odbc_conn_str(driver_name: str, host: str, port: str,
                            user: str, pwd: str, dbname: str = "",
                            dsn_name: str = "") -> str:
        """
        生成 pyodbc 原生连接字符串。

        星环官方 ODBC 更推荐先在系统里配置 DSN，再由应用通过 DSN 连接；
        这里优先走 DSN，只有兼容旧逻辑时才回退到直连串。
        """
        if dsn_name:
            parts = [f"DSN={dsn_name}"]
            if user:
                parts.append(f"UID={user}")
            parts.append(f"PWD={pwd}")
            if dbname:
                parts.append(f"Database={dbname}")
            return ";".join(parts) + ";"

        parts = [
            f"Driver={{{driver_name}}}",
            f"Host={host}",
            f"Port={port}",
            f"UID={user}",
            f"PWD={pwd}",
            "AuthMech=3",
        ]
        if dbname:
            parts.append(f"Database={dbname}")
        return ";".join(parts) + ";"


