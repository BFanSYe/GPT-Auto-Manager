import sqlite3
import json
import os
from datetime import datetime
from typing import Any

os.makedirs("data", exist_ok=True)
DB_PATH = "data/data.db"

def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def init_db():
    """初始化 SQLite 数据库，创建账号存储表"""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        c = conn.cursor()
        c.execute('PRAGMA journal_mode=WAL;')
        c.execute('PRAGMA synchronous=NORMAL;')
        c.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                password TEXT,
                token_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
                    CREATE TABLE IF NOT EXISTS system_kv (
                        key TEXT PRIMARY KEY, 
                        value TEXT
                    )
                ''')
        conn.commit()
    print(f"[{ts()}] [系统] 数据库模块初始化完成")

def save_account_to_db(email: str, password: str, token_json_str: str) -> bool:
    """账号、密码和 Token 数据存入数据库"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO accounts (email, password, token_data)
                VALUES (?, ?, ?)
            ''', (email, password, token_json_str))
            conn.commit()
            return True
    except Exception as e:
        print(f"[{ts()}] [ERROR] 数据库保存失败: {e}")
        return False

def get_all_accounts() -> list:
    """获取所有账号列表，按最新时间倒序"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT email, password, created_at FROM accounts ORDER BY id DESC")
            rows = c.fetchall()
            return [{"email": r[0], "password": r[1], "created_at": r[2]} for r in rows]
    except Exception as e:
        print(f"[{ts()}] [ERROR] 获取账号列表失败: {e}")
        return []

def get_token_by_email(email: str) -> dict:
    """根据邮箱提取完整的 Token JSON 数据（用于推送）"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT token_data FROM accounts WHERE email = ?", (email,))
            row = c.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
    except Exception as e:
        print(f"[{ts()}] [ERROR] 读取 Token 失败: {e}")
        return None

def get_tokens_by_emails(emails: list) -> list:
    """根据前端传入的邮箱列表，提取 Token"""
    if not emails:
        return []
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            placeholders = ','.join(['?'] * len(emails))
            c.execute(f"SELECT token_data FROM accounts WHERE email IN ({placeholders})", emails)
            rows = c.fetchall()
            
            export_list = []
            for r in rows:
                if r[0]:
                    try:
                        export_list.append(json.loads(r[0]))
                    except:
                        pass
            return export_list
    except Exception as e:
        return []
        
def delete_accounts_by_emails(emails: list) -> bool:
    """批量从数据库中删除账号"""
    if not emails:
        return True
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            placeholders = ','.join(['?'] * len(emails))
            c.execute(f"DELETE FROM accounts WHERE email IN ({placeholders})", emails)
            conn.commit()
            return True
    except Exception as e:
        print(f"[{ts()}] [ERROR] 数据库批量删除账号异常: {e}")
        return False

def get_accounts_page(page: int = 1, page_size: int = 50) -> dict:
    """带分页的账号拉取功能"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(1) FROM accounts")
            total = c.fetchone()[0]

            offset = (page - 1) * page_size
            c.execute("SELECT email, password, created_at FROM accounts ORDER BY id DESC LIMIT ? OFFSET ?", (page_size, offset))
            rows = c.fetchall()
            
            data = [{"email": r[0], "password": r[1], "created_at": r[2]} for r in rows]
            return {"total": total, "data": data}
    except Exception as e:
        print(f"[{ts()}] [ERROR] 分页获取账号列表失败: {e}")
        return {"total": 0, "data": []}

def set_sys_kv(key: str, value: Any):
    """保存任意数据到系统表"""
    try:
        val_str = json.dumps(value, ensure_ascii=False)
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("INSERT OR REPLACE INTO system_kv (key, value) VALUES (?, ?)", (key, val_str))
            conn.commit()
    except Exception as e:
        print(f"[{ts()}] [ERROR] 系统配置保存失败: {e}")

def get_sys_kv(key: str, default=None):
    """从系统表读取数据"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute("SELECT value FROM system_kv WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
    except Exception:
        pass
    return default


def get_all_accounts_with_token(limit: int = 10000) -> list:
    """提取包含完整 token_data 的账号列表，专门用于集群导出"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT email, password, token_data FROM accounts ORDER BY id DESC LIMIT ?", (limit,))
            rows = c.fetchall()

            return [{"email": r[0], "password": r[1], "token_data": r[2]} for r in rows]
    except Exception as e:
        print(f"[{ts()}] [ERROR] 提取完整账号数据失败: {e}")
        return []

def save_account_to_db(email: str, password: str, token_json_str: str) -> bool:
    """账号、密码和 Token 数据存入数据库"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR IGNORE INTO accounts (email, password, token_data)
                VALUES (?, ?, ?)
            ''', (email, password, token_json_str))
            conn.commit()
            return True
    except Exception as e:
        print(f"[{ts()}] [ERROR] 数据库保存失败: {e}")
        return False