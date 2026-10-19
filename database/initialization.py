"""Schema creation and forward-only migrations.

Each migration runs once and is recorded in ``schema_migrations``. Startup never
drops or recreates tables, so existing learner data is preserved. The SQL sticks
to types and syntax that translate directly to PostgreSQL (TEXT timestamps in
ISO-8601 UTC, INTEGER booleans, ON CONFLICT clauses).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (
        1,
        "initial schema",
        [
            """
            CREATE TABLE IF NOT EXISTS learner_preferences (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                proficiency_level   TEXT NOT NULL,
                romaji_enabled      INTEGER NOT NULL DEFAULT 1,
                explanation_style   TEXT NOT NULL,
                preferred_difficulty TEXT NOT NULL,
                conversation_corrections INTEGER NOT NULL DEFAULT 1,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vocabulary (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                word                TEXT NOT NULL,
                reading             TEXT NOT NULL,
                romaji              TEXT NOT NULL,
                meaning             TEXT NOT NULL,
                part_of_speech      TEXT NOT NULL,
                example_sentence    TEXT NOT NULL,
                example_reading     TEXT NOT NULL,
                example_romaji      TEXT NOT NULL,
                example_translation TEXT NOT NULL,
                usage_note          TEXT,
                topic               TEXT NOT NULL,
                proficiency_level   TEXT NOT NULL,
                created_at          TEXT NOT NULL,
                UNIQUE (word, reading, meaning)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS saved_vocabulary (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                vocabulary_id       INTEGER NOT NULL UNIQUE
                                    REFERENCES vocabulary(id) ON DELETE CASCADE,
                saved_at            TEXT NOT NULL,
                review_count        INTEGER NOT NULL DEFAULT 0,
                correct_count       INTEGER NOT NULL DEFAULT 0,
                last_reviewed_at    TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vocabulary_reviews (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                vocabulary_id       INTEGER NOT NULL
                                    REFERENCES vocabulary(id) ON DELETE CASCADE,
                remembered          INTEGER NOT NULL,
                reviewed_at         TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS grammar_lessons (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                question            TEXT NOT NULL,
                title               TEXT NOT NULL,
                pattern             TEXT NOT NULL,
                proficiency_level   TEXT NOT NULL,
                lesson_json         TEXT NOT NULL,
                created_at          TEXT NOT NULL,
                UNIQUE (title, pattern, proficiency_level)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                client_quiz_id      TEXT NOT NULL UNIQUE,
                topic               TEXT NOT NULL,
                quiz_type           TEXT NOT NULL,
                proficiency_level   TEXT NOT NULL,
                difficulty          TEXT NOT NULL,
                total_questions     INTEGER NOT NULL,
                correct_answers     INTEGER NOT NULL,
                score               REAL NOT NULL,
                attempted_at        TEXT NOT NULL,
                CHECK (correct_answers >= 0 AND correct_answers <= total_questions)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS quiz_responses (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id          INTEGER NOT NULL
                                    REFERENCES quiz_attempts(id) ON DELETE CASCADE,
                question_index      INTEGER NOT NULL,
                question_type       TEXT NOT NULL,
                prompt              TEXT NOT NULL,
                japanese_text       TEXT,
                options_json        TEXT NOT NULL,
                selected_index      INTEGER,
                correct_index       INTEGER NOT NULL,
                is_correct          INTEGER NOT NULL,
                explanation         TEXT NOT NULL,
                UNIQUE (attempt_id, question_index)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type       TEXT NOT NULL,
                description         TEXT NOT NULL,
                created_at          TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_time ON quiz_attempts(attempted_at)",
            "CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_log(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_reviews_time ON vocabulary_reviews(reviewed_at)",
        ],
    ),
    (
        2,
        "user accounts and per-user data",
        [
            """
            CREATE TABLE users (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                email               TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name        TEXT NOT NULL,
                password_hash       TEXT NOT NULL,
                failed_logins       INTEGER NOT NULL DEFAULT 0,
                locked_until        TEXT,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL,
                last_login_at       TEXT
            )
            """,
            """
            CREATE TABLE user_sessions (
                token_hash          TEXT PRIMARY KEY,
                user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at          TEXT NOT NULL,
                expires_at          TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE user_api_credentials (
                user_id             INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                encrypted_api_key   TEXT NOT NULL,
                key_hint            TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
            """,
            # Preferences: one row per user (legacy single row kept with user_id NULL).
            """
            CREATE TABLE new_learner_preferences (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                proficiency_level   TEXT NOT NULL,
                romaji_enabled      INTEGER NOT NULL DEFAULT 1,
                explanation_style   TEXT NOT NULL,
                preferred_difficulty TEXT NOT NULL,
                conversation_corrections INTEGER NOT NULL DEFAULT 1,
                openai_model        TEXT,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
            """,
            """
            INSERT INTO new_learner_preferences (
                user_id, proficiency_level, romaji_enabled, explanation_style,
                preferred_difficulty, conversation_corrections, created_at, updated_at
            )
            SELECT NULL, proficiency_level, romaji_enabled, explanation_style,
                   preferred_difficulty, conversation_corrections, created_at, updated_at
            FROM learner_preferences
            """,
            "DROP TABLE learner_preferences",
            "ALTER TABLE new_learner_preferences RENAME TO learner_preferences",
            # Vocabulary: uniqueness becomes per user.
            """
            CREATE TABLE new_vocabulary (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER REFERENCES users(id) ON DELETE CASCADE,
                word                TEXT NOT NULL,
                reading             TEXT NOT NULL,
                romaji              TEXT NOT NULL,
                meaning             TEXT NOT NULL,
                part_of_speech      TEXT NOT NULL,
                example_sentence    TEXT NOT NULL,
                example_reading     TEXT NOT NULL,
                example_romaji      TEXT NOT NULL,
                example_translation TEXT NOT NULL,
                usage_note          TEXT,
                topic               TEXT NOT NULL,
                proficiency_level   TEXT NOT NULL,
                created_at          TEXT NOT NULL,
                UNIQUE (user_id, word, reading, meaning)
            )
            """,
            """
            INSERT INTO new_vocabulary (
                id, user_id, word, reading, romaji, meaning, part_of_speech,
                example_sentence, example_reading, example_romaji, example_translation,
                usage_note, topic, proficiency_level, created_at
            )
            SELECT id, NULL, word, reading, romaji, meaning, part_of_speech,
                   example_sentence, example_reading, example_romaji, example_translation,
                   usage_note, topic, proficiency_level, created_at
            FROM vocabulary
            """,
            "DROP TABLE vocabulary",
            "ALTER TABLE new_vocabulary RENAME TO vocabulary",
            # Grammar lessons: uniqueness becomes per user.
            """
            CREATE TABLE new_grammar_lessons (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER REFERENCES users(id) ON DELETE CASCADE,
                question            TEXT NOT NULL,
                title               TEXT NOT NULL,
                pattern             TEXT NOT NULL,
                proficiency_level   TEXT NOT NULL,
                lesson_json         TEXT NOT NULL,
                created_at          TEXT NOT NULL,
                UNIQUE (user_id, title, pattern, proficiency_level)
            )
            """,
            """
            INSERT INTO new_grammar_lessons (
                id, user_id, question, title, pattern, proficiency_level, lesson_json, created_at
            )
            SELECT id, NULL, question, title, pattern, proficiency_level, lesson_json, created_at
            FROM grammar_lessons
            """,
            "DROP TABLE grammar_lessons",
            "ALTER TABLE new_grammar_lessons RENAME TO grammar_lessons",
            # Tables whose constraints do not change just gain an owner column.
            "ALTER TABLE quiz_attempts ADD COLUMN user_id INTEGER "
            "REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE activity_log ADD COLUMN user_id INTEGER "
            "REFERENCES users(id) ON DELETE CASCADE",
            "CREATE INDEX idx_vocabulary_user ON vocabulary(user_id)",
            "CREATE INDEX idx_grammar_user ON grammar_lessons(user_id)",
            "CREATE INDEX idx_quiz_attempts_user ON quiz_attempts(user_id, attempted_at)",
            "CREATE INDEX idx_activity_user ON activity_log(user_id, created_at)",
            "CREATE INDEX idx_sessions_user ON user_sessions(user_id)",
        ],
    ),
]


LATEST_SCHEMA_VERSION = MIGRATIONS[-1][0]


def initialize_database(db_path: Path) -> int:
    """Create the database if needed and apply pending migrations.

    Each migration runs in its own transaction with foreign-key enforcement
    switched off (SQLite's recommended procedure for rebuilding tables), and
    the database is checked for foreign-key violations before committing.
    Returns the schema version after initialization. Safe to call on every start.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)  # explicit transactions
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        )
        applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
        conn.execute("PRAGMA foreign_keys = OFF")
        for version, description, statements in MIGRATIONS:
            if version in applied:
                continue
            logger.info("Applying database migration %d: %s", version, description)
            conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in statements:
                    conn.execute(statement)
                if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise sqlite3.IntegrityError(f"migration {version} broke foreign keys")
                conn.execute(
                    "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                    (version, description),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        conn.execute("PRAGMA foreign_keys = ON")
        row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    finally:
        conn.close()
    return int(row["v"] or 0)
