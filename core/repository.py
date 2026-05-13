"""데이터 접근 계층 (Repository Pattern).

설계 의도
---------
- 모든 DB 연산은 이 모듈을 통해서만 수행한다.
- 현재 백엔드는 SQLite지만, 추후 Supabase/PostgreSQL로 교체할 때
  app.py를 손대지 않고 이 파일만 새 백엔드로 갈아 끼울 수 있도록
  공개 함수(시그니처)를 안정적으로 유지한다.

공개 함수
---------
- init() : 테이블 초기화
- list_themes / add_theme / ensure_default_themes
- add_record / load_records / delete_record / search_records
- add_plan / load_plans / update_plan_status
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# 백엔드 구성
# ---------------------------------------------------------------------------
DB_PATH = Path("bangju_records.db")

DEFAULT_THEMES = [
    "기본",
    "광고 프로젝트",
    "독서 기록",
    "아이디어",
    "업무",
    "건강",
]


# ---------------------------------------------------------------------------
# 커넥션 관리
# ---------------------------------------------------------------------------
@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """SQLite 커넥션 컨텍스트 매니저.

    Streamlit은 매 스크립트 실행마다 함수가 다시 호출되므로
    매번 커넥션을 열고 닫는 단순한 패턴을 유지한다 (안정성 우선).
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 초기화
# ---------------------------------------------------------------------------
def init() -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                created_at TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                theme TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                source TEXT DEFAULT 'text'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                theme TEXT NOT NULL,
                UNIQUE(user_email, theme)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                created_at TEXT NOT NULL,
                level TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT DEFAULT '진행 중'
            )
            """
        )
        # 인덱스 - 사용자별 조회 최적화
        cur.execute("CREATE INDEX IF NOT EXISTS idx_records_user_date ON records(user_email, date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_plans_user ON plans(user_email)")


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
def ensure_default_themes(user_email: str) -> None:
    with _connect() as conn:
        cur = conn.cursor()
        for theme in DEFAULT_THEMES:
            cur.execute(
                "INSERT OR IGNORE INTO themes(user_email, theme) VALUES (?, ?)",
                (user_email, theme),
            )


def list_themes(user_email: str) -> List[str]:
    with _connect() as conn:
        df = pd.read_sql_query(
            "SELECT theme FROM themes WHERE user_email=? ORDER BY theme",
            conn,
            params=(user_email,),
        )
    return df["theme"].tolist() if not df.empty else ["기본"]


def add_theme(user_email: str, theme: str) -> None:
    theme = (theme or "").strip()
    if not theme:
        return
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO themes(user_email, theme) VALUES (?, ?)",
            (user_email, theme),
        )


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------
def add_record(
    user_email: str,
    theme: str,
    content: str,
    category: str = "",
    tags: str = "",
    source: str = "text",
) -> None:
    now = datetime.now()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO records(user_email, created_at, date, time, theme, content, category, tags, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_email,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                theme,
                (content or "").strip(),
                (category or "").strip(),
                (tags or "").strip(),
                source,
            ),
        )


def load_records(user_email: str) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT id, created_at, date, time, theme, content, category, tags, source
            FROM records
            WHERE user_email=?
            ORDER BY created_at DESC
            """,
            conn,
            params=(user_email,),
        )
    return df


def delete_record(user_email: str, record_id: int) -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM records WHERE user_email=? AND id=?", (user_email, record_id))


def search_records(
    user_email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    themes: Optional[List[str]] = None,
    keyword: Optional[str] = None,
) -> pd.DataFrame:
    """간단한 필터 조회. 모든 인자는 선택값."""
    df = load_records(user_email)
    if df.empty:
        return df

    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]
    if themes:
        df = df[df["theme"].isin(themes)]
    if keyword:
        kw = keyword.strip().lower()
        if kw:
            df = df[
                df["content"].str.lower().str.contains(kw, na=False)
                | df["tags"].str.lower().str.contains(kw, na=False)
                | df["category"].str.lower().str.contains(kw, na=False)
            ]
    return df


# ---------------------------------------------------------------------------
# Plan (월간/주간/일간 로드맵)
# ---------------------------------------------------------------------------
def add_plan(user_email: str, level: str, goal: str) -> None:
    goal = (goal or "").strip()
    if not goal:
        return
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO plans(user_email, created_at, level, goal, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_email,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                level,
                goal,
                "진행 중",
            ),
        )


def load_plans(user_email: str) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            "SELECT id, created_at, level, goal, status FROM plans WHERE user_email=? ORDER BY id DESC",
            conn,
            params=(user_email,),
        )
    return df


def update_plan_status(user_email: str, plan_id: int, status: str) -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE plans SET status=? WHERE user_email=? AND id=?",
            (status, user_email, plan_id),
        )


def delete_plan(user_email: str, plan_id: int) -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM plans WHERE user_email=? AND id=?", (user_email, plan_id))
