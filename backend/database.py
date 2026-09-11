import sqlite3
import hashlib
import json
import os
import logging

logger = logging.getLogger("adaptify.db")
DB_PATH = os.path.join(os.path.dirname(__file__), "adaptify_cache.db")

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_cache (
                cache_hash TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error initializing SQLite cache DB: {e}")

def compute_cache_hash(file_content: bytes, subject: str, school_type: str, focus_topic: str, task_count: int, target_format: str, hefteintrag_topic: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(file_content or b"")
    param_str = f"{subject}|{school_type}|{focus_topic}|{task_count}|{target_format}|{hefteintrag_topic}"
    hasher.update(param_str.encode('utf-8'))
    return hasher.hexdigest()

def get_cached_generation(cache_hash: str) -> dict:
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT response_json FROM generation_cache WHERE cache_hash = ?", (cache_hash,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            logger.info(f"⚡ Cache HIT for hash {cache_hash[:10]}...")
            return json.loads(row[0])
    except Exception as e:
        logger.error(f"Error reading from SQLite cache: {e}")
    return None

def set_cached_generation(cache_hash: str, data: dict):
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO generation_cache (cache_hash, response_json) VALUES (?, ?)",
            (cache_hash, json.dumps(data, ensure_ascii=False))
        )
        conn.commit()
        conn.close()
        logger.info(f"💾 Cached generation result for hash {cache_hash[:10]}...")
    except Exception as e:
        logger.error(f"Error writing to SQLite cache: {e}")
