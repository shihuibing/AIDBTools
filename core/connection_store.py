"""
connection_store.py
连接信息持久化模块：将数据库连接配置保存为 JSON 文件，支持增删改查。
保存路径：优先使用 ui_prefs.json 中用户配置的目录，否则使用程序同目录
"""
import json
import os
import sys


def _normalize_conn_info(conn_info: dict) -> dict:
    """对连接配置做兼容性归一化，避免旧配置触发新驱动要求。"""
    info = dict(conn_info or {})
    db_type = str(info.get("db_type") or "").strip().lower()
    if db_type == "xugu":
        if not str(info.get("port") or "").strip():
            info["port"] = "5138"
        dbname = str(info.get("dbname") or "").strip()
        info["dbname"] = dbname
    # 确保新字段有默认值（向后兼容旧连接文件）
    info.setdefault("color", "")       # 颜色标记（空字符串=无标记）
    info.setdefault("starred", False)  # 收藏（星标）
    info.setdefault("group", "")       # 分组名称
    return info


def update_connection_meta(name: str, **kwargs):
    """
    更新连接的元数据字段（color / starred / group 等），不影响其他字段。
    kwargs 中可传 color="red", starred=True, group="生产环境" 等。
    """
    conns = load_connections()
    for c in conns:
        if c.get("name") == name:
            c.update(kwargs)
            break
    _write(conns)


def get_config_path():
    """获取 connections.json 的存储路径（优先用户配置目录，否则默认路径）"""
    return _config_path()


def _config_path():
    """获取 connections.json 的存储路径"""
    # 优先使用用户配置的目录
    custom_dir = _get_custom_config_dir()
    if custom_dir:
        return os.path.join(custom_dir, "connections.json")

    # 默认路径：程序同目录
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.dirname(base)
    return os.path.join(base, "connections.json")


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


def load_connections():
    """加载所有已保存的连接，返回列表，每项为 dict"""
    path = _config_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [_normalize_conn_info(item) for item in data if isinstance(item, dict)]
    except Exception:
        return []


def save_connection(conn_info: dict):
    """
    保存一条连接信息（同名覆盖）。
    conn_info 需包含字段：name, db_type, host, port, user, pwd, dbname
    name 字段作为唯一标识。
    """
    normalized = _normalize_conn_info(conn_info)
    conns = load_connections()
    # 去重：同名覆盖
    conns = [c for c in conns if c.get("name") != normalized.get("name")]
    conns.append(normalized)
    _write(conns)


def delete_connection(name: str):
    """删除指定名称的连接"""
    conns = load_connections()
    conns = [c for c in conns if c.get("name") != name]
    _write(conns)


def rename_connection(old_name: str, new_name: str):
    """重命名连接"""
    conns = load_connections()
    for c in conns:
        if c.get("name") == old_name:
            c["name"] = new_name
            break
    _write(conns)


def _write(conns):
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conns, f, ensure_ascii=False, indent=2)
