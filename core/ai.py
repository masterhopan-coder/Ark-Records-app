"""OpenAI 음성 변환 / 방주 AI 7가지 자아 분석.

핵심 설계
---------
- API 키 부재, 패키지 부재, 모델 미지원 등 모든 실패 케이스에서
  앱이 멈추지 않고 사용자에게 친절한 메시지를 돌려준다.
- 텍스트 생성은 신구 SDK 모두에 안전하도록:
  1) `client.responses.create(...)` (신형) 우선 시도
  2) 실패 시 `client.chat.completions.create(...)` (전통) 폴백
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

import pandas as pd

try:
    from openai import OpenAI  # type: ignore
except Exception:  # 패키지 미설치
    OpenAI = None  # type: ignore[assignment]

from . import config


# ---------------------------------------------------------------------------
# 시스템 프롬프트
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """당신은 사용자의 기록을 분석하는 '방주 AI'입니다.
사용자가 남긴 최근 기록을 바탕으로 아래 7가지 기준에 따라 피드백을 작성하세요.

[분석 기준]
1. 지성: 생각의 깊이, 문제 정의력, 관찰력, 연결성
2. 감정: 기록에서 드러나는 주된 감정, 긴장, 안정감, 기대감
3. 습관: 반복되는 행동, 루틴, 꾸준함, 실행 패턴
4. 관계: 타인, 조직, 고객, 가족, 사회와의 상호작용
5. 에너지: 몰입도, 피로도, 추진력, 회복 필요성
6. 경제 관념: 돈, 시간, 자원, 기회비용을 어디에 투자하는지
7. 건강 상태: 수면, 몸 상태, 식습관, 스트레스, 운동, 회복

[출력 형식]
각 항목을 다음 형식으로 작성하세요.

### 지성
- 관찰:
- 제안:

### 감정
- 관찰:
- 제안:

... 같은 형식으로 7개 항목을 모두 작성하세요.

[말투]
따뜻하지만 과장하지 말고, 실행 가능한 조언을 주세요.
기록에 근거가 부족한 항목은 '직접 언급은 적지만'이라고 조심스럽게 표현하세요.
"""


_DEMO_FEEDBACK = """### 지성
- 관찰: 최근 기록에서 생각을 구조화하려는 흐름이 보입니다.
- 제안: 기록마다 '문제-원인-다음 행동'을 한 줄씩 추가해 보세요.

### 감정
- 관찰: 새로운 시스템을 완성하려는 기대감과 실행 의지가 느껴집니다.
- 제안: 감정도 기록의 데이터입니다. 좋음/보통/불안 같은 상태값을 함께 남기세요.

### 습관
- 관찰: 기록을 도구화하려는 시도가 강합니다.
- 제안: 매일 3분 기록, 주 1회 20분 리뷰로 운영 단위를 작게 유지하세요.

### 관계
- 관찰: AI와의 협업을 통해 사고를 확장하려는 패턴이 보입니다.
- 제안: 사람/팀/고객 관련 기록은 별도 태그를 붙이면 관계 패턴 분석이 쉬워집니다.

### 에너지
- 관찰: 초기 구축 단계의 몰입도가 높습니다.
- 제안: 과몰입을 막기 위해 하루 개선 항목은 1개로 제한하세요.

### 경제 관념
- 관찰: 시간과 도구를 생산성 자산으로 전환하려는 관점이 보입니다.
- 제안: 기록마다 '투입 시간'과 '얻은 결과'를 적으면 시간 투자 효율을 볼 수 있습니다.

### 건강 상태
- 관찰: 직접적인 건강 정보는 적지만 지속 가능한 루틴이 중요해 보입니다.
- 제안: 수면, 피로, 운동 여부를 체크박스처럼 기록하면 더 정확히 분석할 수 있습니다.

> ℹ️ OpenAI API 키가 없어서 데모 피드백을 표시했습니다. `.streamlit/secrets.toml`에 API 키를 넣으면 실제 기록 기반 분석으로 전환됩니다."""


# ---------------------------------------------------------------------------
# 클라이언트
# ---------------------------------------------------------------------------
def get_client() -> Optional[Any]:
    """OpenAI 클라이언트를 반환. 키가 없거나 패키지가 없으면 None."""
    if OpenAI is None:
        return None
    api_key = config.get_secret("openai", "api_key")
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 음성 → 텍스트
# ---------------------------------------------------------------------------
def transcribe_audio(audio_file) -> Tuple[str, Optional[str]]:
    """음성 파일을 텍스트로 변환.

    Returns
    -------
    (text, error_message)
        - 성공: (변환된 텍스트, None)
        - 실패: ("", 사람이 읽을 수 있는 오류 메시지)
    """
    if OpenAI is None:
        return "", "openai 패키지가 설치되어 있지 않습니다. `pip install openai`를 실행하세요."

    client = get_client()
    if client is None:
        return "", "OpenAI API 키가 설정되어 있지 않습니다. secrets.toml의 [openai] api_key를 확인하세요."

    if audio_file is None:
        return "", "변환할 음성 데이터가 없습니다."

    model = config.openai_transcription_model()

    try:
        audio_bytes = audio_file.getvalue()
    except Exception as e:
        return "", f"음성 데이터를 읽지 못했습니다: {e}"

    suffix = Path(getattr(audio_file, "name", "audio.wav")).suffix or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(model=model, file=f)

        text = getattr(transcript, "text", None) or str(transcript)
        return (text or "").strip(), None
    except Exception as e:
        return "", f"음성 변환에 실패했습니다 (model={model}): {e}"
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# AI 피드백 (7가지 자아 분석)
# ---------------------------------------------------------------------------
def _build_record_block(records_df: pd.DataFrame, n: int = 10) -> str:
    recent = records_df.head(n)
    return "\n".join(
        f"- [{row['created_at']}] ({row['theme']}) {row['content']}"
        for _, row in recent.iterrows()
    )


def _call_text_model(client: Any, model: str, system: str, user: str) -> str:
    """신형 Responses API → 구형 Chat Completions API 순으로 시도."""
    # 1) Responses API
    try:
        response = client.responses.create(
            model=model,
            instructions=system,
            input=user,
        )
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text
        # output_text가 없는 SDK 버전 대응
        try:
            return response.output[0].content[0].text  # type: ignore[attr-defined,index]
        except Exception:
            pass
    except Exception:
        pass

    # 2) Chat Completions API
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


def generate_feedback(records_df: pd.DataFrame) -> str:
    """7가지 자아 분석 피드백을 Markdown으로 돌려준다.

    API 키가 없으면 데모 피드백을 반환한다.
    """
    if records_df is None or records_df.empty:
        return "_분석할 기록이 없습니다. 먼저 기록을 1개 이상 저장한 뒤 다시 시도하세요._"

    client = get_client()
    if client is None:
        return _DEMO_FEEDBACK

    model = config.openai_text_model()
    record_block = _build_record_block(records_df, n=10)
    user_msg = f"다음은 사용자의 최근 기록입니다.\n\n{record_block}"

    try:
        result = _call_text_model(client, model, SYSTEM_PROMPT, user_msg)
        return (result or "").strip() or "_AI가 빈 응답을 반환했습니다._"
    except Exception as e:
        return (
            f"**AI 피드백 생성에 실패했습니다.**\n\n"
            f"- 모델: `{model}`\n"
            f"- 오류: `{e}`\n\n"
            f"`.streamlit/secrets.toml`의 `[openai] text_model` 값을 사용 가능한 모델로 바꿔보세요."
        )
