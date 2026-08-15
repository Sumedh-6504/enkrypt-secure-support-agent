import datetime
import hashlib
import os
import sqlite3

from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

try:
    import psycopg2
except ImportError:
    psycopg2 = None

class DatabaseManager:
    def __init__(self, db_type=None, cache_dir='local_cache'):
        if db_type is None:
            if os.getenv("VECTOR_MODE", "local") == "production":
                db_type = "postgres"
            else:
                db_type = os.getenv("DB_TYPE", "sqlite")
                
        self.db_type = db_type
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.sqlite_path = os.path.join(self.cache_dir, "essa.db")
        self.postgres_url = os.getenv("POSTGRES_URL")
        self._init_schema()

    def _get_connection(self):
        if self.db_type == "postgres" and self.postgres_url:
            if not psycopg2:
                raise ImportError("psycopg2 is required for Postgres. Run 'pip install psycopg2-binary'")
            return psycopg2.connect(self.postgres_url)
        else:
            return sqlite3.connect(self.sqlite_path)

    def _init_schema(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Telemetry Logs
        if self.db_type == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    question TEXT,
                    status TEXT,
                    policy_violation TEXT
                )
            """)
            # Knowledge Base Registry
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base_registry (
                    id SERIAL PRIMARY KEY,
                    filename TEXT UNIQUE,
                    content_hash TEXT,
                    chunk_count INTEGER,
                    last_embedded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Session Store
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    context_window TEXT,
                    last_active TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    question TEXT,
                    status TEXT,
                    policy_violation TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE,
                    content_hash TEXT,
                    chunk_count INTEGER,
                    last_embedded_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    context_window TEXT,
                    last_active TEXT
                )
            """)
        
        conn.commit()
        conn.close()

    def log_security_event(self, question, status, policy="None"):
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        if self.db_type == "postgres":
            cursor.execute(
                "INSERT INTO security_logs (question, status, policy_violation) VALUES (%s, %s, %s)",
                (question, status, policy)
            )
        else:
            cursor.execute(
                "INSERT INTO security_logs (timestamp, question, status, policy_violation) VALUES (?, ?, ?, ?)",
                (timestamp, question, status, policy)
            )
        conn.commit()
        conn.close()

    def get_file_hash(self, filename):
        conn = self._get_connection()
        cursor = conn.cursor()
        if self.db_type == "postgres":
            cursor.execute("SELECT content_hash FROM knowledge_base_registry WHERE filename = %s", (filename,))
        else:
            cursor.execute("SELECT content_hash FROM knowledge_base_registry WHERE filename = ?", (filename,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    def update_registry(self, filename, content_hash, chunk_count):
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        if self.db_type == "postgres":
            cursor.execute("""
                INSERT INTO knowledge_base_registry (filename, content_hash, chunk_count, last_embedded_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (filename) DO UPDATE 
                SET content_hash = EXCLUDED.content_hash, 
                    chunk_count = EXCLUDED.chunk_count,
                    last_embedded_at = CURRENT_TIMESTAMP
            """, (filename, content_hash, chunk_count))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO knowledge_base_registry (filename, content_hash, chunk_count, last_embedded_at)
                VALUES (?, ?, ?, ?)
            """, (filename, content_hash, chunk_count, timestamp))
        conn.commit()
        conn.close()

    @staticmethod
    def calculate_hash(content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def update_chat_session(self, session_id, history_text):
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        if self.db_type == "postgres":
            cursor.execute("""
                INSERT INTO chat_sessions (session_id, context_window, last_active)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (session_id) DO UPDATE 
                SET context_window = EXCLUDED.context_window, 
                    last_active = CURRENT_TIMESTAMP
            """, (session_id, history_text))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO chat_sessions (session_id, context_window, last_active)
                VALUES (?, ?, ?)
            """, (session_id, history_text, timestamp))
        conn.commit()
        conn.close()

    def get_chat_session(self, session_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        if self.db_type == "postgres":
            cursor.execute("SELECT context_window FROM chat_sessions WHERE session_id = %s", (session_id,))
        else:
            cursor.execute("SELECT context_window FROM chat_sessions WHERE session_id = ?", (session_id,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else ""
