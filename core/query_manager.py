"""
query_manager.py
SQL 查询管理模块 - 类似 Navicat 的查询保存和管理功能
"""
import os
import json
from datetime import datetime


def get_query_dir():
    """获取查询文件存储目录"""
    import sys
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    query_dir = os.path.join(base, "queries")
    os.makedirs(query_dir, exist_ok=True)
    return query_dir


def get_query_file_path(conn_name, db_name, query_name):
    """获取查询文件的完整路径"""
    query_dir = get_query_dir()
    conn_dir = os.path.join(query_dir, conn_name)
    os.makedirs(conn_dir, exist_ok=True)
    
    db_dir = os.path.join(conn_dir, db_name)
    os.makedirs(db_dir, exist_ok=True)
    
    filename = f"{query_name}.sql"
    return os.path.join(db_dir, filename)


def save_query(conn_name, db_name, query_name, sql_content, description=""):
    """保存 SQL 查询"""
    try:
        filepath = get_query_file_path(conn_name, db_name, query_name)
        
        metadata = {
            "name": query_name,
            "connection": conn_name,
            "database": db_name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        data = {
            "metadata": metadata,
            "sql": sql_content
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存查询失败: {e}")
        return False


def load_query(conn_name, db_name, query_name):
    """加载 SQL 查询"""
    try:
        filepath = get_query_file_path(conn_name, db_name, query_name)
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    except Exception as e:
        print(f"加载查询失败: {e}")
        return None


def list_queries(conn_name=None, db_name=None):
    """列出所有查询"""
    queries = []
    query_dir = get_query_dir()
    
    if not os.path.exists(query_dir):
        return queries
    
    for conn in os.listdir(query_dir):
        if conn_name and conn != conn_name:
            continue
        
        conn_dir = os.path.join(query_dir, conn)
        if not os.path.isdir(conn_dir):
            continue
        
        for db in os.listdir(conn_dir):
            if db_name and db != db_name:
                continue
            
            db_dir = os.path.join(conn_dir, db)
            if not os.path.isdir(db_dir):
                continue
            
            for filename in os.listdir(db_dir):
                if filename.endswith('.sql'):
                    filepath = os.path.join(db_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            metadata = data.get("metadata", {})
                            queries.append({
                                "name": metadata.get("name", filename[:-4]),
                                "connection": metadata.get("connection", conn),
                                "database": metadata.get("database", db),
                                "description": metadata.get("description", ""),
                                "created_at": metadata.get("created_at", ""),
                                "updated_at": metadata.get("updated_at", ""),
                                "filepath": filepath
                            })
                    except Exception:
                        pass
    
    queries.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return queries


def delete_query(conn_name, db_name, query_name):
    """删除查询文件"""
    try:
        filepath = get_query_file_path(conn_name, db_name, query_name)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception as e:
        print(f"删除查询失败: {e}")
        return False


def rename_query(conn_name, db_name, old_name, new_name):
    """重命名查询"""
    try:
        old_path = get_query_file_path(conn_name, db_name, old_name)
        new_path = get_query_file_path(conn_name, db_name, new_name)
        
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
            
            with open(new_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data["metadata"]["name"] = new_name
            data["metadata"]["updated_at"] = datetime.now().isoformat()
            
            with open(new_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        return False
    except Exception as e:
        print(f"重命名查询失败: {e}")
        return False
