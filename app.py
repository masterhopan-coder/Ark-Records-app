"""방주의 기록 - Streamlit 메인 앱.

실행 순서 (순서 변경 불가)
--------------------------
1. st.set_page_config()          ← Streamlit 규칙: 반드시 첫 번째 st.* 호출
2. Google OAuth 헬퍼 함수 정의
3. [OAuth 콜백 인터셉터]          ← ?code= 감지 → 토큰 교환 → session_state 저장
                                    반드시 UI(CSS/위젯) 렌더링 전에 실행해야 한다.
                                    위젯이 하나라도 그려진 뒤 st.rerun()을 호출하면
                                    Streamlit이 비정상 종료 처리할 수 있기 때문이다.
4. CSS / 사이드바 / 탭 등 UI 렌더링
"""
from __future__ import annotations

import secrets
import urllib.parse
from datetime import date, datetime
from typing import Optional, Tuple

import pandas as pd
import requests as http_requests
import streamlit as st

from core import ai, config, exporters, notifications, repository


# =============================================================================
# 1. 페이지 기본 설정 — 반드시 첫 번째 st.* 호출
# =============================================================================
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# 2. Google OAuth 2.0 헬퍼 함수 (st.* 호출 없음)
# =============================================================================
_GOOGLE_AUTH_ENDPOINT  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL   = "https://www.googleapis.com/oauth2/v2/userinfo"


def _build_google_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",
    }
    return _GOOGLE_AUTH_ENDPOINT + "?" + urllib.parse.urlencode(params)


def _exchange_code_for_token(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Authorization Code → Access Token.  반환: (token, error)"""
    try:
        r = http_requests.post(
            _GOOGLE_TOKEN_ENDPOINT,
            data={
                "code":          code,
                "client_id":     client_id,
                "client_secret": client_secret,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            },
            timeout=10,
        )
        data = r.json()
        if "access_token" in data:
            return data["access_token"], None
        return None, data.get("error_description") or data.get("error") or str(data)
    except Exception as exc:
        return None, f"네트워크 오류: {exc}"


def _get_user_email(access_token: str) -> Tuple[Optional[str], Optional[str]]:
    """Access Token → 이메일.  반환: (email, error)"""
    try:
        r = http_requests.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        info = r.json()
        email = info.get("email")
        if email:
            return email, None
        return None, f"이메일 없음: {info}"
    except Exception as exc:
        return None, f"UserInfo 조회 실패: {exc}"


# =============================================================================
# 3. OAuth 콜백 인터셉터 ← 반드시 CSS / 위젯보다 먼저 실행
#
#    Google 이 /?code=xxx&state=yyy 로 리디렉션해 오면
#    이 블록이 즉시 코드를 잡아 토큰 교환을 수행한다.
#    성공하면 session_state["user_email"] 에 이메일을 저장하고 st.rerun() 으로
#    깨끗한 URL 상태에서 대시보드를 보여 준다.
# =============================================================================
if config.has_google_auth_config() and not st.session_state.get("user_email"):
    _qp = st.query_params.to_dict()   # 현재 URL 파라미터 스냅샷

    if "code" in _qp:
        _code = _qp["code"]

        # ── URL 즉시 클리어 (위젯 렌더링 전, 재진입 방지) ──────────────────
        st.query_params.clear()

        # ── Token Exchange ────────────────────────────────────────────────
        _token, _token_err = _exchange_code_for_token(
            _code,
            config.get_secret("auth", "redirect_uri"),
            config.get_secret("auth", "client_id"),
            config.get_secret("auth", "client_secret"),
        )

        if _token:
            # ── UserInfo 조회 ─────────────────────────────────────────────
            _email, _email_err = _get_user_email(_token)
            if _email:
                st.session_state["user_email"] = _email
                # 성공: 재실행하면 대시보드가 표시된다
            else:
                st.session_state["_auth_error"] = (
                    f"사용자 정보를 가져오지 못했습니다: {_email_err}"
                )
        else:
            st.session_state["_auth_error"] = (
                f"토큰 교환 실패: {_token_err}\n\n"
                "**확인 항목**\n"
                "- Streamlit Cloud Secrets 의 `redirect_uri` 가 "
                "Google Console 등록값과 **정확히** 일치하는지\n"
                "- `client_secret` 이 올바른지\n"
                "- authorization code 가 10분 이내에 교환됐는지"
            )

        # 성공·실패 모두 rerun → 깨끗한 URL + 올바른 화면
        st.rerun()


# -----------------------------------------------------------------------------
# 임원 보고서 스타일 CSS
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --bj-navy: #1F2A44;
        --bj-accent: #3B82F6;
        --bj-muted: #6B7280;
        --bj-border: #E5E7EB;
        --bj-soft: #F8FAFC;
    }

    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 3rem;
        max-width: 1280px;
    }

    /* 타이틀 */
    h1, h2, h3 { color: var(--bj-navy); letter-spacing: -0.01em; }
    h1 { font-weight: 700; }
    h2 { font-weight: 650; }

    /* 본문 캡션 */
    .bj-tagline {
        color: var(--bj-muted);
        font-size: 0.95rem;
        margin-top: -0.4rem;
        margin-bottom: 1.6rem;
    }

    /* KPI 카드 */
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 18px 20px;
        border-radius: 14px;
        border: 1px solid var(--bj-border);
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    div[data-testid="stMetricLabel"] {
        color: var(--bj-muted);
        font-size: 0.85rem;
        font-weight: 500;
    }
    div[data-testid="stMetricValue"] {
        color: var(--bj-navy);
        font-weight: 700;
    }

    /* 카드 */
    .bj-card {
        padding: 1.15rem 1.25rem;
        border-radius: 14px;
        border: 1px solid var(--bj-border);
        background: #FFFFFF;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
        margin-bottom: 0.8rem;
    }
    .bj-card .bj-card-meta {
        color: var(--bj-muted);
        font-size: 0.8rem;
        margin-top: 0.4rem;
    }
    .bj-card .bj-card-theme {
        display: inline-block;
        background: var(--bj-soft);
        color: var(--bj-navy);
        font-size: 0.75rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid var(--bj-border);
        margin-bottom: 0.45rem;
    }

    /* 탭 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        font-weight: 500;
        color: var(--bj-muted);
    }
    .stTabs [aria-selected="true"] {
        color: var(--bj-navy) !important;
    }

    /* 사이드바 - 입력 영역 */
    section[data-testid="stSidebar"] {
        background: var(--bj-soft);
    }

    /* 버튼 - primary */
    .stButton button[kind="primary"] {
        background: var(--bj-navy);
        border-color: var(--bj-navy);
    }
    .stButton button[kind="primary"]:hover {
        background: #111827;
        border-color: #111827;
    }

    /* 작은 상태 배지 */
    .bj-status {
        display: inline-block;
        font-size: 0.72rem;
        padding: 2px 8px;
        border-radius: 999px;
        font-weight: 600;
    }
    .bj-status-on  { background: #DCFCE7; color: #166534; }
    .bj-status-off { background: #FEE2E2; color: #991B1B; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 4. 로그인 상태 관리 (session_state 읽기만 담당)
#    콜백 처리는 위의 인터셉터 블록에서 이미 완료됐다.
# =============================================================================
def resolve_user_email() -> str:
    """현재 사용자 이메일을 반환한다.

    - 로컬 데모 모드: 'local_user'
    - Google 로그인 성공: 이메일 주소
    - 미로그인: 로그인 화면을 렌더링하고 st.stop()
    """

    # ── 로컬 데모 모드 ─────────────────────────────────────────────────────
    if not config.has_google_auth_config():
        with st.sidebar:
            st.caption("🧭 현재 모드: **Local Demo**")
            st.caption("Google 로그인은 `secrets.toml`의 `[auth]` 3개 키를 채우면 활성화됩니다.")
        return "local_user"

    # ── 로그인 완료 ────────────────────────────────────────────────────────
    if st.session_state.get("user_email"):
        email = str(st.session_state["user_email"])
        with st.sidebar:
            st.success(f"✅ 로그인: **{email}**")
            if st.button("로그아웃", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        return email

    # ── 미로그인 → 로그인 화면 ─────────────────────────────────────────────
    client_id    = config.get_secret("auth", "client_id")
    redirect_uri = config.get_secret("auth", "redirect_uri")

    # state 생성 (CSRF 방지 — Google 리디렉션 후 새 세션이 열리므로 검증은 생략)
    state    = secrets.token_urlsafe(16)
    auth_url = _build_google_auth_url(client_id, redirect_uri, state)

    # 인증 오류가 있었으면 표시
    if st.session_state.get("_auth_error"):
        st.error(st.session_state.pop("_auth_error"))

    # 전체 화면 로그인 UI
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown(
            f"<h1 style='text-align:center'>{config.APP_ICON} {config.APP_TITLE}</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align:center;color:#6B7280'>{config.APP_TAGLINE}</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button(
            "🔵  Google 계정으로 로그인",
            url=auth_url,
            use_container_width=True,
            type="primary",
        )
        st.caption(
            "<div style='text-align:center;margin-top:.5rem;color:#9CA3AF'>"
            "로그인하면 개인 기록 공간으로 연결됩니다</div>",
            unsafe_allow_html=True,
        )
    st.stop()


USER_EMAIL = resolve_user_email()


# =============================================================================
# DB 초기화
# =============================================================================
repository.init()
repository.ensure_default_themes(USER_EMAIL)


# =============================================================================
# 헤더
# =============================================================================
st.title(f"{config.APP_ICON} {config.APP_TITLE}")
st.markdown(f"<div class='bj-tagline'>{config.APP_TAGLINE}</div>", unsafe_allow_html=True)


# =============================================================================
# 사이드바 - 기록 입력
# =============================================================================
records_df = repository.load_records(USER_EMAIL)
themes = repository.list_themes(USER_EMAIL)

with st.sidebar:
    st.header("✍️ 기록 입력")

    # 주제 관리
    with st.expander("주제 관리", expanded=False):
        new_theme = st.text_input("새 주제 추가", placeholder="예: 신규 사업")
        if st.button("주제 추가", use_container_width=True):
            if new_theme.strip():
                repository.add_theme(USER_EMAIL, new_theme)
                st.success(f"'{new_theme}' 주제가 추가됐습니다.")
                st.rerun()

    selected_theme = st.selectbox("주제 선택", themes)

    st.divider()

    # 음성 입력
    st.markdown("**🎤 음성으로 기록하기**")
    audio = st.audio_input("마이크로 말하기", key="audio_input")

    if "draft_text" not in st.session_state:
        st.session_state.draft_text = ""

    if audio is not None:
        st.audio(audio)
        if st.button("음성 → 텍스트 변환", use_container_width=True):
            with st.spinner("음성을 변환하는 중..."):
                text, err = ai.transcribe_audio(audio)
            if text:
                st.session_state.draft_text = text
                st.success("음성 변환 완료")
            else:
                st.error(err or "변환 결과가 없습니다.")

    # 텍스트 입력
    content = st.text_area(
        "기록 내용",
        value=st.session_state.draft_text,
        height=160,
        placeholder="오늘의 생각, 업무 판단, 감정, 아이디어를 적어보세요.",
        key="content_input",
    )
    category = st.text_input("분류", value="일상/생각")
    tags = st.text_input("태그", value="#기록 #방주의기록")

    col_save1, col_save2 = st.columns(2)
    with col_save1:
        if st.button("💾 저장", type="primary", use_container_width=True):
            if content.strip():
                source = "voice" if audio is not None else "text"
                repository.add_record(
                    USER_EMAIL, selected_theme, content, category, tags, source
                )
                st.session_state.draft_text = ""
                st.success("기록 저장 완료")
                st.rerun()
            else:
                st.warning("기록 내용을 입력하세요.")
    with col_save2:
        if st.button("🧹 초기화", use_container_width=True):
            st.session_state.draft_text = ""
            st.rerun()

    st.divider()

    # 텔레그램 테스트
    if st.button("🔔 텔레그램 테스트 알림", use_container_width=True):
        ok, msg = notifications.send_telegram(
            f"🛶 방주의 기록 알림\n{datetime.now():%Y-%m-%d %H:%M}\n오늘의 기록을 남겨보세요."
        )
        if ok:
            st.success("텔레그램 알림 전송 완료")
        else:
            st.error(msg)

    # 통합 상태
    st.divider()
    st.markdown("**연동 상태**")
    on, off = "bj-status bj-status-on", "bj-status bj-status-off"
    st.markdown(
        f"- OpenAI &nbsp; <span class='{on if config.has_openai_config() else off}'>"
        f"{'연결됨' if config.has_openai_config() else '미설정'}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"- Telegram &nbsp; <span class='{on if config.has_telegram_config() else off}'>"
        f"{'연결됨' if config.has_telegram_config() else '미설정'}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"- Google Auth &nbsp; <span class='{on if config.has_google_auth_config() else off}'>"
        f"{'연결됨' if config.has_google_auth_config() else '미설정'}</span>",
        unsafe_allow_html=True,
    )


# =============================================================================
# KPI
# =============================================================================
today_str = datetime.now().strftime("%Y-%m-%d")
today_count = int((records_df["date"] == today_str).sum()) if not records_df.empty else 0
theme_count = int(records_df["theme"].nunique()) if not records_df.empty else 0
total_count = int(len(records_df))

# 이번 주 기록 수 (월요일 기준 ISO 주차)
def _count_this_week(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    try:
        dt = pd.to_datetime(df["date"], errors="coerce")
        iso = dt.dt.isocalendar()
        now = datetime.now().isocalendar()
        return int(((iso.year == now.year) & (iso.week == now.week)).sum())
    except Exception:
        return 0


week_count = _count_this_week(records_df)


k1, k2, k3, k4 = st.columns(4)
k1.metric("전체 기록", f"{total_count:,}")
k2.metric("오늘 기록", today_count)
k3.metric("이번 주 기록", week_count)
k4.metric("주제 수", theme_count)

st.write("")  # 여백


# =============================================================================
# 메인 탭
# =============================================================================
tab_dash, tab_search, tab_ai, tab_plan, tab_export, tab_setup = st.tabs(
    ["📊 대시보드", "🔍 검색·관리", "🤖 방주 AI 분석", "🗺️ 로드맵", "📥 내보내기", "⚙️ 설정·배포"]
)


# -----------------------------------------------------------------------------
# 대시보드
# -----------------------------------------------------------------------------
with tab_dash:
    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("최근 기록")
        if records_df.empty:
            st.info("아직 기록이 없습니다. 왼쪽 사이드바에서 첫 기록을 저장해 보세요.")
        else:
            for _, row in records_df.head(8).iterrows():
                preview = (row["content"][:90] + "…") if len(row["content"]) > 90 else row["content"]
                st.markdown(
                    f"""
                    <div class="bj-card">
                        <span class="bj-card-theme">{row['theme']}</span>
                        <div>{preview}</div>
                        <div class="bj-card-meta">
                            🕐 {row['created_at']} &nbsp;·&nbsp; 분류: {row['category'] or '—'}
                            &nbsp;·&nbsp; {row['tags'] or ''}
                            &nbsp;·&nbsp; 입력: {row['source']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with c2:
        st.subheader("주제별 기록 수")
        if records_df.empty:
            st.caption("데이터 없음")
        else:
            chart_df = (
                records_df.groupby("theme")
                .size()
                .reset_index(name="기록 수")
                .sort_values("기록 수", ascending=False)
            )
            st.bar_chart(chart_df.set_index("theme"), height=260)

        st.subheader("최근 7일 추이")
        if records_df.empty:
            st.caption("데이터 없음")
        else:
            trend_df = records_df.copy()
            trend_df["date_dt"] = pd.to_datetime(trend_df["date"], errors="coerce")
            recent = trend_df[trend_df["date_dt"] >= (pd.Timestamp.now().normalize() - pd.Timedelta(days=6))]
            if recent.empty:
                st.caption("최근 7일 기록 없음")
            else:
                by_day = recent.groupby(recent["date_dt"].dt.date).size().reset_index(name="건수")
                by_day.columns = ["날짜", "건수"]
                st.line_chart(by_day.set_index("날짜"), height=200)


# -----------------------------------------------------------------------------
# 검색·관리
# -----------------------------------------------------------------------------
with tab_search:
    st.subheader("🔍 과거 기록 검색 및 관리")

    s1, s2, s3 = st.columns([1, 1, 2])
    with s1:
        # 기본값을 30일 전으로 잡아 첫 검색에서도 결과가 나오도록 함
        default_start = (datetime.now() - pd.Timedelta(days=30)).date()
        start_date = st.date_input("시작일", value=default_start)
    with s2:
        end_date = st.date_input("종료일", value=date.today())
    with s3:
        keyword = st.text_input("키워드", placeholder="예: 광고, 클로드, 운동, 비용")

    selected_themes = st.multiselect("주제 필터", themes, default=themes)

    filtered = repository.search_records(
        USER_EMAIL,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        themes=selected_themes,
        keyword=keyword,
    )

    st.caption(f"검색 결과: **{len(filtered)}건**")
    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "content": st.column_config.TextColumn("내용", width="large"),
            "created_at": st.column_config.TextColumn("일시", width="medium"),
        },
    )

    if not filtered.empty:
        with st.expander("기록 삭제"):
            delete_id = st.number_input("삭제할 기록 ID", min_value=0, step=1)
            if st.button("선택 ID 삭제", type="primary"):
                if delete_id > 0:
                    repository.delete_record(USER_EMAIL, int(delete_id))
                    st.success(f"ID {delete_id} 삭제 완료")
                    st.rerun()


# -----------------------------------------------------------------------------
# 방주 AI 분석
# -----------------------------------------------------------------------------
with tab_ai:
    st.subheader("🤖 방주 AI · 7가지 자아 분석")
    st.write(
        "최근 기록 **10개**를 바탕으로 *지성, 감정, 습관, 관계, 에너지, 경제 관념, 건강 상태* 7가지 기준으로 피드백을 생성합니다."
    )

    if not config.has_openai_config():
        st.info("ℹ️ OpenAI API 키가 없어서 데모 피드백이 표시됩니다. `secrets.toml`에 키를 넣으면 실제 분석으로 전환됩니다.")

    if st.button("나의 기록 분석하기", type="primary"):
        with st.spinner("방주 AI가 기록을 분석 중입니다..."):
            feedback = ai.generate_feedback(records_df)
        st.markdown('<div class="bj-card">', unsafe_allow_html=True)
        st.markdown(feedback)
        st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 로드맵
# -----------------------------------------------------------------------------
with tab_plan:
    st.subheader("🗺️ 월간·주간·일간 로드맵")

    p1, p2, p3 = st.columns(3)
    with p1:
        monthly = st.text_input("월간 목표", key="plan_monthly")
        if st.button("월간 추가", use_container_width=True):
            repository.add_plan(USER_EMAIL, "월간", monthly)
            st.rerun()
    with p2:
        weekly = st.text_input("주간 목표", key="plan_weekly")
        if st.button("주간 추가", use_container_width=True):
            repository.add_plan(USER_EMAIL, "주간", weekly)
            st.rerun()
    with p3:
        daily = st.text_input("일간 목표", key="plan_daily")
        if st.button("일간 추가", use_container_width=True):
            repository.add_plan(USER_EMAIL, "일간", daily)
            st.rerun()

    plans_df = repository.load_plans(USER_EMAIL)
    if plans_df.empty:
        st.info("아직 등록된 목표가 없습니다.")
    else:
        st.dataframe(plans_df, use_container_width=True, hide_index=True)

        with st.expander("상태 변경 / 삭제"):
            c_a, c_b, c_c = st.columns([1, 1, 1])
            with c_a:
                plan_id = st.number_input("목표 ID", min_value=0, step=1, key="plan_id")
            with c_b:
                new_status = st.selectbox("새 상태", ["진행 중", "완료", "보류"])
            with c_c:
                st.write("")
                st.write("")
                col_s, col_d = st.columns(2)
                with col_s:
                    if st.button("상태 변경", use_container_width=True):
                        if plan_id > 0:
                            repository.update_plan_status(USER_EMAIL, int(plan_id), new_status)
                            st.success("상태 변경 완료")
                            st.rerun()
                with col_d:
                    if st.button("삭제", use_container_width=True):
                        if plan_id > 0:
                            repository.delete_plan(USER_EMAIL, int(plan_id))
                            st.success("삭제 완료")
                            st.rerun()


# -----------------------------------------------------------------------------
# 내보내기
# -----------------------------------------------------------------------------
with tab_export:
    st.subheader("📥 Excel / PDF 다운로드")

    e1, e2 = st.columns(2)
    with e1:
        export_themes = st.multiselect("주제 필터", themes, default=themes, key="export_themes")
    with e2:
        export_keyword = st.text_input("키워드 필터", key="export_keyword")

    export_df = repository.search_records(
        USER_EMAIL,
        themes=export_themes,
        keyword=export_keyword,
    )
    st.caption(f"다운로드 대상: **{len(export_df)}건**")

    if export_df.empty:
        st.info("내보낼 기록이 없습니다.")
    else:
        c_x, c_p = st.columns(2)
        with c_x:
            try:
                excel_bytes = exporters.to_excel_bytes(export_df)
                st.download_button(
                    "📊 Excel 다운로드",
                    data=excel_bytes,
                    file_name=f"bangju_records_{datetime.now():%Y%m%d_%H%M}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary",
                )
            except Exception as e:
                st.error(f"Excel 생성 실패: {e}")
        with c_p:
            try:
                pdf_bytes = exporters.to_pdf_bytes(export_df)
                st.download_button(
                    "📄 PDF 다운로드",
                    data=pdf_bytes,
                    file_name=f"bangju_records_{datetime.now():%Y%m%d_%H%M}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"PDF 생성 실패: {e}")


# -----------------------------------------------------------------------------
# 설정·배포
# -----------------------------------------------------------------------------
with tab_setup:
    st.subheader("⚙️ 설치 및 배포 메모")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(
            """
            **🔧 로컬 실행**
            ```bash
            python -m venv .venv
            source .venv/bin/activate     # macOS / Linux
            # Windows: .venv\\Scripts\\activate
            pip install -r requirements.txt
            streamlit run app.py
            ```

            **🔑 선택 API 활성화 순서 (권장)**
            1. OpenAI API 키 → 음성 변환 + AI 분석
            2. Telegram → 모바일 알림
            3. Google OIDC → 다중 사용자 지원
            """
        )

    with col_r:
        st.markdown(
            """
            **☁️ Streamlit Cloud 배포**
            1. GitHub에 본 폴더를 푸시 (단, `bangju_records.db`와 `secrets.toml` 제외)
            2. Streamlit Cloud → New app → 저장소 연결
            3. **Settings → Secrets**에 `.streamlit/secrets.toml` 내용 그대로 붙여넣기
            4. Google Cloud Console의 승인된 Redirect URI에 배포 주소 추가:
               `https://YOUR-APP.streamlit.app/oauth2callback`

            **🛡️ 보안 체크리스트**
            - `.streamlit/secrets.toml`은 `.gitignore`에 포함됨
            - DB 파일(`bangju_records.db`)도 커밋 금지
            - 배포 후 redirect URI는 로컬용과 배포용 두 개 모두 등록
            """
        )

    st.divider()
    st.caption("👤 현재 사용자: " + (USER_EMAIL if USER_EMAIL != "local_user" else "Local Demo"))
