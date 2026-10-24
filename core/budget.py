"""
Strict Token Budget Governor & Semantic Response Cache.
Protects the user's limited Gemini API quota by enforcing daily caps,
rate limits, and local SQLite response caching.
"""

from __future__ import annotations
from contextlib import contextmanager
import datetime
import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator

from config import DB_PATH, DEFAULT_CONFIG, NexusConfig


class BudgetExhaustedError(RuntimeError):
    """Raised when the daily token budget or per-minute rate limit is exceeded."""


class TokenBudgetGovernor:
    """
    Tracks every token spent by Tier-1 Gemini API models in SQLite and blocks
    calls that would violate the user's daily budget or RPM limits.
    """

    def __init__(self, db_path: Path = DB_PATH, config: NexusConfig = DEFAULT_CONFIG):
        self.db_path = db_path
        self.config = config
        self.config.ensure_directories()
        self._init_tables()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS budget_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_str TEXT NOT NULL,
                    model TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_budget_date ON budget_ledger(date_str);

                CREATE TABLE IF NOT EXISTS prompt_cache (
                    prompt_hash TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    prompt_preview TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    tokens_saved INTEGER NOT NULL DEFAULT 0,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );
                """
            )

    @staticmethod
    def _today_str() -> str:
        return datetime.date.today().isoformat()

    @staticmethod
    def _hash_prompt(model: str, system_instruction: str, user_input: str) -> str:
        normalized = f"{model.strip()}||{system_instruction.strip()}||{' '.join(user_input.lower().split())}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def check_cache(
        self, model: str, system_instruction: str, user_input: str
    ) -> str | None:
        if not self.config.enable_semantic_cache:
            return None
        phash = self._hash_prompt(model, system_instruction, user_input)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_text FROM prompt_cache WHERE prompt_hash = ?",
                (phash,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE prompt_cache SET hit_count = hit_count + 1 WHERE prompt_hash = ?",
                    (phash,),
                )
                return str(row["response_text"])
        return None

    def save_cache(
        self,
        model: str,
        system_instruction: str,
        user_input: str,
        response_text: str,
        tokens_estimate: int,
    ) -> None:
        if not self.config.enable_semantic_cache:
            return
        phash = self._hash_prompt(model, system_instruction, user_input)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO prompt_cache (
                    prompt_hash, model, prompt_preview, response_text, tokens_saved, hit_count, created_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(prompt_hash) DO UPDATE SET
                    response_text = excluded.response_text
                """,
                (
                    phash,
                    model,
                    user_input[:200],
                    response_text,
                    tokens_estimate,
                    time.time(),
                ),
            )

    def get_today_usage(self) -> dict[str, Any]:
        today = self._today_str()
        one_min_ago = time.time() - 60.0
        with self._connect() as conn:
            day_row = conn.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS used_tokens,
                       COUNT(*) AS call_count
                FROM budget_ledger
                WHERE date_str = ?
                """,
                (today,),
            ).fetchone()
            rpm_row = conn.execute(
                "SELECT COUNT(*) AS rpm FROM budget_ledger WHERE timestamp >= ?",
                (one_min_ago,),
            ).fetchone()
            cache_row = conn.execute(
                "SELECT COALESCE(SUM(tokens_saved * hit_count), 0) AS saved, COALESCE(SUM(hit_count), 0) AS hits FROM prompt_cache"
            ).fetchone()

        used = int(day_row["used_tokens"])
        limit = self.config.daily_token_limit
        return {
            "date": today,
            "used_tokens": used,
            "daily_limit": limit,
            "remaining_tokens": max(0, limit - used),
            "usage_percent": round((used / max(1, limit)) * 100.0, 2),
            "calls_today": int(day_row["call_count"]),
            "calls_last_minute": int(rpm_row["rpm"]),
            "cache_hits": int(cache_row["hits"]),
            "estimated_tokens_saved_by_cache": int(cache_row["saved"]),
        }

    def verify_can_spend(self, estimated_tokens: int = 500) -> None:
        status = self.get_today_usage()
        if status["used_tokens"] + estimated_tokens > self.config.daily_token_limit:
            raise BudgetExhaustedError(
                f"Đã chạm trần ngân sách token hôm nay ({status['used_tokens']}/{self.config.daily_token_limit} tokens). "
                "Tự động chuyển sang chế độ Offline / Cầu nối Giáo viên Argon Ultra."
            )
        if status["calls_last_minute"] >= self.config.max_calls_per_minute:
            raise BudgetExhaustedError(
                f"Chạm giới hạn tần suất gọi API ({status['calls_last_minute']}/{self.config.max_calls_per_minute} RPM)."
            )

    def record_spend(self, model: str, purpose: str, total_tokens: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO budget_ledger (date_str, model, purpose, total_tokens, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self._today_str(), model, purpose, max(1, int(total_tokens)), time.time()),
            )
