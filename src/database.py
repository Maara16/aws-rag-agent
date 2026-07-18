"""
SQLite database for tracking user progress, quiz attempts, and interaction history.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import json
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    phone_number TEXT PRIMARY KEY,
                    display_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_interaction TIMESTAMP,
                    total_messages INTEGER DEFAULT 0
                )
            """)

            # Quiz attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    question_number INTEGER,
                    question_text TEXT,
                    correct_answer TEXT,
                    user_answer TEXT,
                    is_correct BOOLEAN,
                    time_spent_seconds INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (phone_number) REFERENCES users(phone_number)
                )
            """)

            # Quiz sessions table (groups multiple questions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quiz_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    domain TEXT,
                    num_questions INTEGER,
                    score INTEGER,
                    total_time_seconds INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (phone_number) REFERENCES users(phone_number)
                )
            """)

            # Interaction history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    mode TEXT,  -- 'rag' | 'quiz' | 'cheatsheet' | 'search'
                    user_input TEXT,
                    agent_output TEXT,
                    tokens_used INTEGER,
                    response_time_ms FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (phone_number) REFERENCES users(phone_number)
                )
            """)

            # User preferences
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    phone_number TEXT PRIMARY KEY,
                    preferred_domain TEXT,
                    difficulty_level TEXT DEFAULT 'intermediate',
                    notification_enabled BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (phone_number) REFERENCES users(phone_number)
                )
            """)

            conn.commit()
            logger.info(f"Database schema initialized at {self.db_path}")

    def get_or_create_user(self, phone_number: str, display_name: str = None) -> Dict:
        """Get or create a user."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM users WHERE phone_number = ?",
                (phone_number,)
            )
            user = cursor.fetchone()

            if user:
                cursor.execute(
                    "UPDATE users SET last_interaction = CURRENT_TIMESTAMP WHERE phone_number = ?",
                    (phone_number,)
                )
                conn.commit()
                return dict(user)
            else:
                cursor.execute(
                    """
                    INSERT INTO users (phone_number, display_name, last_interaction)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (phone_number, display_name or phone_number)
                )
                conn.commit()
                cursor.execute(
                    "SELECT * FROM users WHERE phone_number = ?",
                    (phone_number,)
                )
                return dict(cursor.fetchone())

    def log_interaction(
        self,
        phone_number: str,
        mode: str,
        user_input: str,
        agent_output: str,
        tokens_used: int = 0,
        response_time_ms: float = 0
    ) -> int:
        """Log an interaction."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO interactions 
                (phone_number, mode, user_input, agent_output, tokens_used, response_time_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (phone_number, mode, user_input, agent_output, tokens_used, response_time_ms)
            )
            conn.commit()
            return cursor.lastrowid

    def record_quiz_attempt(
        self,
        phone_number: str,
        domain: str,
        question_number: int,
        question_text: str,
        correct_answer: str,
        user_answer: str,
        is_correct: bool,
        time_spent_seconds: int
    ) -> int:
        """Record a quiz question attempt."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO quiz_attempts
                (phone_number, domain, question_number, question_text, correct_answer, user_answer, is_correct, time_spent_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (phone_number, domain, question_number, question_text, correct_answer, user_answer, is_correct, time_spent_seconds)
            )
            conn.commit()
            return cursor.lastrowid

    def create_quiz_session(
        self,
        phone_number: str,
        domain: str,
        num_questions: int,
        score: int,
        total_time_seconds: int
    ) -> int:
        """Create a quiz session record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO quiz_sessions
                (phone_number, domain, num_questions, score, total_time_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (phone_number, domain, num_questions, score, total_time_seconds)
            )
            conn.commit()
            return cursor.lastrowid

    def get_user_stats(self, phone_number: str) -> Dict:
        """Get user quiz statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Total quizzes
            cursor.execute(
                "SELECT COUNT(*) as total_sessions, AVG(score) as avg_score FROM quiz_sessions WHERE phone_number = ?",
                (phone_number,)
            )
            session_stats = dict(cursor.fetchone())

            # Accuracy per domain
            cursor.execute(
                """
                SELECT domain, COUNT(*) as attempts, SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct
                FROM quiz_attempts
                WHERE phone_number = ?
                GROUP BY domain
                """,
                (phone_number,)
            )
            domain_stats = [dict(row) for row in cursor.fetchall()]

            # Last 5 interactions
            cursor.execute(
                """
                SELECT mode, user_input, created_at FROM interactions
                WHERE phone_number = ?
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (phone_number,)
            )
            recent = [dict(row) for row in cursor.fetchall()]

            return {
                "session_stats": session_stats,
                "domain_stats": domain_stats,
                "recent_interactions": recent
            }

    def get_weak_domains(self, phone_number: str, threshold: float = 0.6) -> List[str]:
        """Get domains where user scored below threshold."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT domain, 
                       SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
                       COUNT(*) as total,
                       CAST(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as accuracy
                FROM quiz_attempts
                WHERE phone_number = ?
                GROUP BY domain
                HAVING accuracy < ?
                ORDER BY accuracy ASC
                """,
                (phone_number, threshold)
            )
            return [row["domain"] for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        pass  # SQLite auto-closes


# Singleton instance
_db_instance = None


def get_db(db_path: str = "data/app.db") -> Database:
    """Get or create database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance
