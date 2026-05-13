"""Telegram 알림.

- token / chat_id가 secrets에 없으면 명확한 에러 메시지를 돌려준다.
- 네트워크 예외도 사용자가 읽을 수 있는 문자열로 변환한다.
"""
from __future__ import annotations

from typing import Tuple

import requests

from . import config


def send_telegram(message: str) -> Tuple[bool, str]:
    """Telegram 메시지 전송.

    Returns
    -------
    (ok, msg)
        - ok=True  : 전송 성공, msg는 'ok'
        - ok=False : 전송 실패, msg에 원인이 들어 있음
    """
    token = config.get_secret("telegram", "token")
    chat_id = config.get_secret("telegram", "chat_id")

    if not token or not chat_id:
        return False, "Telegram 설정이 없습니다. secrets.toml의 [telegram] token/chat_id를 확인하세요."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
    except requests.exceptions.Timeout:
        return False, "Telegram 서버 응답이 10초를 초과했습니다."
    except requests.exceptions.RequestException as e:
        return False, f"네트워크 오류로 전송하지 못했습니다: {e}"

    if r.status_code == 200:
        return True, "ok"

    # Telegram이 돌려주는 description을 추출
    try:
        detail = r.json().get("description", r.text)
    except Exception:
        detail = r.text
    return False, f"전송 실패 (HTTP {r.status_code}): {detail}"
