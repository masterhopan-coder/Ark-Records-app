"""설정 / Secrets 헬퍼.

- Streamlit secrets에서 값을 안전하게 읽는다 (없으면 default 반환, 예외 무시).
- Google OIDC 설정, OpenAI 설정, Telegram 설정 가용성을 한 번에 점검한다.
"""
from __future__ import annotations

import os
from typing import Optional

import streamlit as st


# ---------------------------------------------------------------------------
# 기본 모델 / 상수
# ---------------------------------------------------------------------------
DEFAULT_TEXT_MODEL = "gpt-4o-mini"          # secrets에서 바꿀 수 있음
DEFAULT_TRANSCRIPTION_MODEL = "whisper-1"   # secrets에서 바꿀 수 있음

APP_TITLE = "방주의 기록"
APP_ICON = "🛶"
APP_TAGLINE = "나 + 메모 기록 + AI의 3중주 하모니로 생각과 실행을 누적하는 개인 기록 시스템"


# ---------------------------------------------------------------------------
# Secrets 접근
# ---------------------------------------------------------------------------
def get_secret(section: str, key: str, default: str = "") -> str:
    """Streamlit secrets[section][key]를 안전하게 읽는다.

    - secrets.toml 자체가 없거나(파일이 없는 로컬 첫 실행), 섹션/키가 없으면 default 반환.
    - 환경변수 `<SECTION>_<KEY>` (대문자)가 있으면 그것을 우선 사용 (CI/도커 친화).
    """
    env_key = f"{section.upper()}_{key.upper()}"
    if os.environ.get(env_key):
        return str(os.environ[env_key])

    try:
        section_data = st.secrets.get(section)  # type: ignore[attr-defined]
    except Exception:
        return default

    if not section_data:
        return default

    try:
        value = section_data.get(key) if hasattr(section_data, "get") else section_data[key]  # type: ignore[index]
    except Exception:
        return default

    if value in (None, ""):
        return default
    return str(value)


# ---------------------------------------------------------------------------
# 기능별 가용성 점검
# ---------------------------------------------------------------------------
def has_google_auth_config() -> bool:
    """수동 OAuth 2.0 에 필요한 최소 설정이 있는지 확인.

    수동 구현에서는 cookie_secret 이 불필요하므로 3개 키만 확인한다.
    (st.login() 방식을 쓰지 않으므로 server_metadata_url 도 제외)
    """
    needed = ["client_id", "client_secret", "redirect_uri"]
    return all(get_secret("auth", k) for k in needed)


def has_openai_config() -> bool:
    return bool(get_secret("openai", "api_key"))


def has_telegram_config() -> bool:
    return bool(get_secret("telegram", "token")) and bool(get_secret("telegram", "chat_id"))


def openai_text_model() -> str:
    return get_secret("openai", "text_model", DEFAULT_TEXT_MODEL)


def openai_transcription_model() -> str:
    return get_secret("openai", "transcription_model", DEFAULT_TRANSCRIPTION_MODEL)


# ---------------------------------------------------------------------------
# 로그인 URL 자동 감지 (로컬 vs Streamlit Cloud)
# ---------------------------------------------------------------------------
def detect_redirect_uri() -> Optional[str]:
    """현재 secrets에 등록된 redirect_uri 반환.

    Streamlit Cloud와 로컬을 동시에 지원하려면 Google OAuth 콘솔에
    두 개의 redirect URI를 모두 등록해두는 방식을 권장한다.
    - 로컬: http://localhost:8501/oauth2callback
    - Cloud: https://<app>.streamlit.app/oauth2callback
    """
    uri = get_secret("auth", "redirect_uri")
    return uri or None
