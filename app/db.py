from __future__ import annotations

import os
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras


def get_conn():
    """Создать подключение к базе."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def get_or_create_user(tg_id: int, username: Optional[str], first_name: Optional[str]) -> int:
    """
    Вернуть id пользователя из таблицы users.
    Если такого нет — создать и вернуть новый id.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE tg_id = %s", (tg_id,))
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO users (tg_id, username, first_name)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (tg_id, username, first_name),
        )
        new_id = cur.fetchone()[0]
        return new_id


WordItem = Dict[str, str]


def available_words(user_id: int) -> List[Dict[str, str]]:
    """
    Вернуть все слова, доступные пользователю:
    (глобальные, которые не скрыты) ∪ (его собственные, не удалённые).
    """
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT 'global' AS source, gw.id, gw.en, gw.ru
            FROM global_words gw
            WHERE NOT EXISTS (
                SELECT 1 FROM user_hidden_global_words uh
                WHERE uh.user_id = %s AND uh.word_id = gw.id
            )
            UNION ALL
            SELECT 'user' AS source, uw.id, uw.en, uw.ru
            FROM user_words uw
            WHERE uw.user_id = %s AND NOT uw.deleted
            """,
            (user_id, user_id),
        )
        return [dict(r) for r in cur.fetchall()]


def add_user_word(user_id: int, en: str, ru: str) -> int:
    """Добавить новое слово для пользователя."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_words (user_id, en, ru)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (user_id, en.strip(), ru.strip()),
        )
        return cur.fetchone()[0]


def hide_global_word_for_user(user_id: int, word_id: int) -> None:
    """Скрыть глобальное слово для конкретного пользователя."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_hidden_global_words (user_id, word_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, word_id) DO NOTHING
            """,
            (user_id, word_id),
        )


def soft_delete_user_word(word_id: int, user_id: int) -> None:
    """Пометить пользовательское слово как удалённое."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE user_words SET deleted = TRUE WHERE id = %s AND user_id = %s",
            (word_id, user_id),
        )


def user_studied_count(user_id: int) -> int:
    """Подсчитать количество доступных слов для пользователя."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT (
                SELECT COUNT(*) FROM global_words gw
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_hidden_global_words uh
                    WHERE uh.user_id = %s AND uh.word_id = gw.id
                )
            ) + (
                SELECT COUNT(*) FROM user_words uw
                WHERE uw.user_id = %s AND NOT uw.deleted
            ) AS total
            """,
            (user_id, user_id),
        )
        return int(cur.fetchone()[0])
