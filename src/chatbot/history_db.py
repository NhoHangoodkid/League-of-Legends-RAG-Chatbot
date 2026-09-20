"""
PostgreSQL Chat History Manager for LoL RAG Knowledge Bot.
File: src/chatbot/history_db.py

Provides session management and persistent chat history storage with JSONB RAG metadata.
Includes automatic database and schema provisioning, auto-reconnect, and error handling.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load env variables if not loaded
project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / ".env")

logger = logging.getLogger("ChatHistoryDB")

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.extras import RealDictCursor
    psycopg2_available = True
except ImportError:
    psycopg2_available = False
    logger.warning("psycopg2 is not installed. Chat history persistence will be disabled.")


class ChatHistoryDB:
    """Manages chat sessions and messages stored in PostgreSQL."""

    def __init__(
        self,
        host = None,
        port = None,
        dbname = None,
        user = None,
        password = None,
    ):
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(port or os.getenv("POSTGRES_PORT", 5432))
        self.dbname = dbname or os.getenv("POSTGRES_DB", "lol_chat_db")
        self.user = user or os.getenv("POSTGRES_USER", "postgres")
        self.password = password or os.getenv("POSTGRES_PASSWORD") or os.getenv("postgres_password") or ""

        self.is_connected = False
        self.ensure_db_and_schema()

    def get_connection(self, dbname = None):
        """Create a single connection to PostgreSQL with search_path set to public."""
        if not psycopg2_available:
            return None
        target_db = dbname or self.dbname
        conn = psycopg2.connect(
            host = self.host,
            port = self.port,
            dbname = target_db,
            user = self.user,
            password = self.password,
            connect_timeout = 3,
        )
        # Explicitly ensure search_path is set to public
        with conn.cursor() as cur:
            cur.execute("SET search_path TO public;")
        return conn

    def ensure_db_and_schema(self):
        """Ensure database exists and create tables if they do not exist."""
        if not psycopg2_available:
            return

        # 1. Ensure Database exists
        try:
            conn = self.get_connection(dbname = "postgres")
            if conn:
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (self.dbname,))
                    if not cur.fetchone():
                        cur.execute(f'CREATE DATABASE "{self.dbname}";')
                        logger.info(f"Created database '{self.dbname}'.")
                conn.close()
        except Exception as e:
            logger.warning(f"Could not verify/create database '{self.dbname}': {e}")

        # 2. Ensure Tables exist in target DB
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cur:
                    # Sessions table
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS lol_chat_sessions (
                            session_id VARCHAR(64) PRIMARY KEY,
                            title VARCHAR(255) NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    # Messages table
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS lol_chat_messages (
                            id SERIAL PRIMARY KEY,
                            session_id VARCHAR(64) REFERENCES lol_chat_sessions(session_id) ON DELETE CASCADE,
                            role VARCHAR(20) NOT NULL,
                            content TEXT NOT NULL,
                            rag_meta JSONB,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE INDEX IF NOT EXISTS idx_lol_messages_session ON lol_chat_messages(session_id);
                        CREATE INDEX IF NOT EXISTS idx_lol_messages_created ON lol_chat_messages(created_at);
                        """
                    )
                conn.commit()
                conn.close()
                self.is_connected = True
                logger.info("PostgreSQL Chat History tables verified and ready.")
                self.cleanup_empty_sessions()
        except Exception as e:
            logger.error(f"Failed to initialize chat history schema: {e}")
            self.is_connected = False

    def is_available(self):
        """Check if database connection is alive."""
        if not psycopg2_available:
            return False
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                conn.close()
                self.is_connected = True
                return True
        except Exception:
            self.is_connected = False
        return False

    def create_session(self, session_id = None, title = "New Conversation"):
        """Create a new chat session."""
        sid = session_id or str(uuid.uuid4())
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO lol_chat_sessions (session_id, title, created_at, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (session_id) DO UPDATE SET title = EXCLUDED.title, updated_at = CURRENT_TIMESTAMP;
                        """,
                        (sid, title),
                    )
                conn.commit()
                conn.close()
                return sid
        except Exception as e:
            logger.error(f"create_session error: {e}")
        return sid

    def list_sessions(self, only_with_messages = True):
        """List all chat sessions ordered by newest updated first."""
        sessions = []
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor(cursor_factory = RealDictCursor) as cur:
                    having_clause = "HAVING COUNT(m.id) > 0" if only_with_messages else ""
                    cur.execute(
                        f"""
                        SELECT s.session_id, s.title, s.created_at, s.updated_at,
                               COUNT(m.id) as message_count
                        FROM lol_chat_sessions s
                        LEFT JOIN lol_chat_messages m ON s.session_id = m.session_id
                        GROUP BY s.session_id, s.title, s.created_at, s.updated_at
                        {having_clause}
                        ORDER BY s.updated_at DESC;
                        """
                    )
                    rows = cur.fetchall()
                    for r in rows:
                        sessions.append(dict(r))
                conn.close()
        except Exception as e:
            logger.error(f"list_sessions error: {e}")
        return sessions

    def cleanup_empty_sessions(self):
        """Remove sessions that have no messages to prevent empty chat clutter."""
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        DELETE FROM lol_chat_sessions
                        WHERE session_id NOT IN (SELECT DISTINCT session_id FROM lol_chat_messages);
                        """
                    )
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"cleanup_empty_sessions error: {e}")

    def get_session_messages(self, session_id):
        """Fetch all messages for a specific session in chronological order."""
        messages = []
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor(cursor_factory = RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT role, content, rag_meta, created_at
                        FROM lol_chat_messages
                        WHERE session_id = %s
                        ORDER BY created_at ASC, id ASC;
                        """,
                        (session_id,),
                    )
                    rows = cur.fetchall()
                    for r in rows:
                        rag_meta = r.get("rag_meta")
                        if isinstance(rag_meta, str):
                            try:
                                rag_meta = json.loads(rag_meta)
                            except Exception:
                                pass
                        messages.append({
                            "role": r["role"],
                            "content": r["content"],
                            "rag_meta": rag_meta,
                            "created_at": r["created_at"],
                        })
                conn.close()
        except Exception as e:
            logger.error(f"get_session_messages error: {e}")
        return messages

    def add_message(
        self,
        session_id,
        role,
        content,
        rag_meta = None,
    ):
        """Add a message to a session and update session's updated_at."""
        try:
            conn = self.get_connection()
            if conn:
                # Ensure session exists
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO lol_chat_sessions (session_id, title, created_at, updated_at)
                        VALUES (%s, 'New Conversation', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (session_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP;
                        """,
                        (session_id,),
                    )

                    meta_json = json.dumps(rag_meta, ensure_ascii = False) if rag_meta else None
                    cur.execute(
                        """
                        INSERT INTO lol_chat_messages (session_id, role, content, rag_meta, created_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP);
                        """,
                        (session_id, role, content, meta_json),
                    )

                    # Update updated_at of the session
                    cur.execute(
                        """
                        UPDATE lol_chat_sessions
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s;
                        """,
                        (session_id,),
                    )
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            logger.error(f"add_message error: {e}")
        return False

    def update_session_title(self, session_id, new_title):
        """Update session title (e.g. summarized from first user prompt)."""
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE lol_chat_sessions
                        SET title = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s;
                        """,
                        (new_title[:250], session_id),
                    )
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            logger.error(f"update_session_title error: {e}")
        return False

    def delete_session(self, session_id):
        """Delete a chat session and its messages (cascade)."""
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM lol_chat_sessions WHERE session_id = %s;",
                        (session_id,),
                    )
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            logger.error(f"delete_session error: {e}")
        return False


# Singleton instance
history_db_instance = None


def get_history_db():
    """Get or create singleton ChatHistoryDB instance."""
    global history_db_instance
    if history_db_instance is None:
        history_db_instance = ChatHistoryDB()
    return history_db_instance


if __name__ == "__main__":
    db = get_history_db()
    print(f"DB Available: {db.is_available()}")
    if db.is_available():
        test_sid = db.create_session(title = "Test Session Yasuo")
        print(f"Created session: {test_sid}")
        db.add_message(test_sid, "user", "Who counters Yasuo?")
        db.add_message(test_sid, "assistant", "Renekton, Pantheon, and Malphite counter Yasuo...", {"intent": "COUNTER_QUERY"})
        msgs = db.get_session_messages(test_sid)
        print(f"Messages count: {len(msgs)}")
        print(f"Sessions: {db.list_sessions()}")
