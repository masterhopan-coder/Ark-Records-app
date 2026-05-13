# 🛶 방주의 기록

> **나 + 메모 기록 + AI** 의 3중주 하모니로 생각과 실행을 누적하는 개인 기록 시스템.

Streamlit 기반의 가벼운 로컬-우선 앱이지만, OpenAI · Google OIDC · Telegram을 붙이면
개인 분석 보고서 + 다중 사용자 + 모바일 알림이 가능한 SaaS급 앱으로 확장됩니다.

---

## 📑 목차
1. [주요 기능](#-주요-기능)
2. [프로젝트 구조](#-프로젝트-구조)
3. [빠른 시작 (로컬)](#-빠른-시작-로컬)
4. [API 키 없이도 되는 기능](#-api-키-없이도-되는-기능)
5. [API 키 연동](#-api-키-연동)
6. [Streamlit Cloud 배포](#️-streamlit-cloud-배포)
7. [DB 백엔드 교체 (Supabase / PostgreSQL)](#-db-백엔드-교체-supabase--postgresql)
8. [트러블슈팅](#-트러블슈팅)
9. [실행 체크리스트](#-실행-체크리스트)

---

## ✨ 주요 기능

| 기능 | 설명 | API 필요 |
|------|------|----------|
| 기록 저장 | SQLite DB에 영구 저장, 사용자별 분리 | ❌ |
| 주제 관리 | 기본/광고 프로젝트/독서/아이디어/업무/건강 등 + 커스텀 추가 | ❌ |
| 날짜·키워드·주제 검색 | 다중 조건 필터링 | ❌ |
| Excel 다운로드 | 헤더 서식 / 자동 필터 / 열너비 자동화 | ❌ |
| PDF 다운로드 | 한글 폰트(`HYSMyeongJo-Medium`) + 표 형식 보고서 | ❌ |
| 월간·주간·일간 로드맵 | 상태 변경(진행 중/완료/보류) 가능 | ❌ |
| 음성 입력 → 텍스트 | `st.audio_input` + OpenAI Whisper | ✅ OpenAI |
| 방주 AI 7가지 자아 분석 | 지성/감정/습관/관계/에너지/경제 관념/건강 | ✅ OpenAI |
| Telegram 알림 | 모바일 푸시 (테스트 알림 버튼) | ✅ Telegram |
| Google 계정 로그인 | OIDC 기반 사용자별 기록 분리 | ✅ Google |

---

## 📁 프로젝트 구조

```
bangju_records_app/
├── app.py                          # 메인 Streamlit 앱 (UI 조립)
├── core/                           # 비즈니스 로직 (DB 백엔드 교체 시 여기만 수정)
│   ├── __init__.py
│   ├── config.py                   # secrets / 환경 변수 헬퍼
│   ├── repository.py               # 데이터 접근 추상화 (현재 SQLite)
│   ├── ai.py                       # OpenAI STT + 7가지 자아 분석
│   ├── exporters.py                # Excel + PDF (한글 폰트)
│   └── notifications.py            # Telegram 알림
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    ├── config.toml                 # 테마 (Navy + Slate)
    └── secrets.toml.example        # 시크릿 예시 (실제 키 없음)
```

**왜 모듈을 분리했나요?**
`core/` 폴더 안의 각 모듈은 단일 책임을 가집니다. 예를 들어 SQLite를 PostgreSQL이나
Supabase로 바꿔야 할 때, `app.py`는 손대지 않고 `core/repository.py`만 새 백엔드로
다시 작성하면 됩니다. AI 모델을 바꾸거나, Telegram 대신 Slack을 쓰고 싶을 때도 동일합니다.

---

## 🚀 빠른 시작 (로컬)

> ⚠️ **PowerShell 주의** : `&&`와 `source`는 PowerShell에서 동작하지 않습니다.
> 아래 명령어를 **한 줄씩** 실행하세요.

---

### macOS / Linux

```bash
cd bangju_records_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

---

### Windows PowerShell (명령을 한 줄씩 실행)

**1단계 — 폴더 이동**
```powershell
cd bangju_records_app
```

**2단계 — 가상환경 생성**
```powershell
python -m venv .venv
```

**3단계 — 가상환경 활성화**
```powershell
.venv\Scripts\Activate.ps1
```

> ❗ `이 시스템에서 스크립트를 실행할 수 없습니다` 오류가 나면?
> PowerShell을 **관리자 권한**으로 열고, 아래 명령을 **한 번만** 실행한 뒤 3단계를 다시 시도하세요.
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

활성화에 성공하면 프롬프트 앞에 `(.venv)` 가 붙습니다.
```
(.venv) PS C:\...\bangju_records_app>
```

**4단계 — 패키지 설치**
```powershell
pip install -r requirements.txt
```

**5단계 — 앱 실행**
```powershell
streamlit run app.py
```

브라우저가 자동으로 열리고 `http://localhost:8501` 에 접속됩니다.

> 💡 **PowerShell 7+** 사용자는 `&&`를 써서 한 줄로 연결할 수 있습니다.
> 버전 확인: `$PSVersionTable.PSVersion`

> 🟢 이 단계까지만으로도 **기록 저장, 검색, Excel/PDF 다운로드, 로드맵** 기능이 모두 동작합니다.

---

## 🟢 API 키 없이도 되는 기능

`.streamlit/secrets.toml`이 없거나 비어 있어도 아래 기능은 즉시 사용 가능합니다.

- ✅ 텍스트 기록 입력 / 주제 관리
- ✅ 날짜 / 키워드 / 주제 검색
- ✅ SQLite 영구 저장
- ✅ Excel / PDF 다운로드 (한글 정상 표시)
- ✅ 월간·주간·일간 로드맵 관리
- ✅ 대시보드 (최근 기록, 주제별 통계, 7일 추이)

> 💡 `local_user`라는 단일 가상 사용자로 동작하며, 모든 데이터는 로컬 `bangju_records.db`에 저장됩니다.

---

## 🔌 API 키 연동

**연동 순서를 OpenAI → Telegram → Google 순으로 권장합니다.**

### A. OpenAI (음성 변환 + AI 분석)

1. https://platform.openai.com/api-keys 에서 키 발급
2. `.streamlit/secrets.toml.example`을 `secrets.toml`로 복사

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
3. `[openai]` 섹션을 채웁니다.

   ```toml
   [openai]
   api_key = "sk-..."
   text_model = "gpt-4o-mini"
   transcription_model = "whisper-1"
   ```
4. 앱을 재시작하면 사이드바 하단의 "OpenAI" 배지가 **연결됨**으로 바뀌고,
   - 사이드바의 **음성 → 텍스트 변환** 버튼이 동작합니다.
   - **방주 AI 분석** 탭이 실제 GPT 분석으로 전환됩니다.

> 모델을 바꾸려면 `text_model`, `transcription_model` 값만 교체하세요.
> 코드는 **신형 Responses API** → **전통 Chat Completions API** 순으로 자동 폴백합니다.

### B. Telegram (모바일 알림)

1. 텔레그램에서 [@BotFather](https://t.me/BotFather) 검색 → `/newbot` → 토큰 발급
2. 자신의 봇과 대화를 한 번 시작한 뒤, 브라우저에서
   `https://api.telegram.org/bot<TOKEN>/getUpdates` 로 chat_id 확인
3. secrets.toml에 입력:

   ```toml
   [telegram]
   token = "123456789:ABCdef..."
   chat_id = "123456789"
   ```
4. 사이드바의 **🔔 텔레그램 테스트 알림** 버튼으로 검증

### C. Google 로그인 (OIDC, 다중 사용자)

1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) 접속
2. **OAuth 2.0 클라이언트 ID** 생성 (애플리케이션 유형: **웹 애플리케이션**)
3. **승인된 리디렉션 URI**에 다음 두 개를 모두 등록:
   - 로컬:    `http://localhost:8501/oauth2callback`
   - 배포:    `https://YOUR-APP-NAME.streamlit.app/oauth2callback`
4. secrets.toml의 `[auth]` 섹션을 채웁니다.

   ```toml
   [auth]
   redirect_uri = "http://localhost:8501/oauth2callback"
   cookie_secret = "충분히_긴_랜덤_문자열"
   client_id = "xxx.apps.googleusercontent.com"
   client_secret = "GOCSPX-xxx"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

   `cookie_secret` 생성 방법:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

5. 앱 재시작 시 첫 화면에서 **🔵 Google 계정으로 로그인** 버튼이 보입니다.
   - 로그인 후에는 각 사용자의 이메일별로 기록이 완전히 분리됩니다.

> ⚠️ `redirect_uri` 값은 **로컬 개발 시에는 localhost**, **Streamlit Cloud에 배포할 때에는 배포 URL**을
> 가리켜야 합니다. Google Cloud Console에 두 개 다 등록해 두고, `secrets.toml`만 환경에 맞게 바꿔주세요.

---

## ☁️ Streamlit Cloud 배포

### 1단계: GitHub 푸시

```bash
git init
git add app.py core/ requirements.txt README.md .gitignore .streamlit/config.toml .streamlit/secrets.toml.example
git commit -m "Initial commit: 방주의 기록"
git remote add origin https://github.com/<YOUR_ID>/bangju-records-app.git
git push -u origin main
```

> ⚠️ **절대로 같이 올리면 안 되는 것:**
> - `.streamlit/secrets.toml`  (실제 API 키)
> - `bangju_records.db`         (개인 기록 데이터)
> - `.venv/`                    (가상환경)
>
> 위 세 가지는 `.gitignore`에 이미 등록되어 있어 자동으로 제외됩니다.

### 2단계: Streamlit Cloud에서 앱 생성

1. https://share.streamlit.io 접속
2. **Create app** 클릭
3. 다음과 같이 선택:
   - **Repository**: `<YOUR_ID>/bangju-records-app`
   - **Branch**: `main`
   - **Main file path**: `app.py`

### 3단계: Secrets 입력

배포 후 **Settings → Secrets** 에 로컬 `.streamlit/secrets.toml` 내용을 그대로 붙여넣습니다.

### 4단계: Google Redirect URI 추가

배포 URL이 정해진 뒤 (예: `https://bangju-records.streamlit.app`):

1. Google Cloud Console → 해당 OAuth 클라이언트 편집
2. **승인된 리디렉션 URI**에 추가:
   `https://bangju-records.streamlit.app/oauth2callback`
3. Streamlit Cloud의 Secrets에서 `redirect_uri` 값을 배포 URL로 교체

---

## 🔄 DB 백엔드 교체 (Supabase / PostgreSQL)

`core/repository.py`는 SQLite 구현이지만, 공개 함수 시그니처가 안정적으로 정의되어 있어
다른 백엔드로 교체할 때 `app.py`나 다른 모듈을 수정할 필요가 없습니다.

**교체해야 할 함수들:**
- `init()`
- `list_themes(user_email)` / `add_theme(...)` / `ensure_default_themes(...)`
- `add_record(...)` / `load_records(...)` / `delete_record(...)` / `search_records(...)`
- `add_plan(...)` / `load_plans(...)` / `update_plan_status(...)` / `delete_plan(...)`

**Supabase로 옮기는 예시:**

```python
# core/repository.py 의 함수들을 Supabase 클라이언트 호출로 바꾸면 됨
from supabase import create_client

def load_records(user_email: str) -> pd.DataFrame:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = sb.table("records").select("*").eq("user_email", user_email).order(
        "created_at", desc=True
    ).execute()
    return pd.DataFrame(res.data)
```

함수 이름과 인자, 반환 타입만 같으면 앱 전체가 그대로 동작합니다.

---

## 🛠 트러블슈팅

| 증상 | 원인 / 조치 |
|------|-------------|
| `ModuleNotFoundError: openai` | `pip install -r requirements.txt` 재실행. 가상환경 활성화 확인. |
| 한글 PDF가 □로 깨짐 | reportlab CIDFont 등록 실패 (드물게 발생). reportlab 4.2+ 재설치. |
| Google 로그인 후 redirect 오류 | Google Cloud Console의 redirect URI와 `secrets.toml`의 `redirect_uri`가 정확히 일치하는지 확인. 끝의 슬래시, http vs https 주의. |
| `gpt-5.2` 같은 모델 오류 | 존재하지 않는 모델. `text_model = "gpt-4o-mini"` 등 실제 사용 가능한 모델로 변경. |
| Telegram 알림 실패 | `chat_id`가 올바른지 확인. 봇과 1회 이상 대화한 후 `getUpdates`로 다시 추출. |
| Streamlit Cloud에서 DB가 매번 초기화됨 | 정상. Cloud 컨테이너는 휘발성. 영구 저장이 필요하면 Supabase/PostgreSQL로 교체. |
| `st.user` 관련 오류 | Streamlit 1.42 이상 필요. `pip install --upgrade streamlit`. |

---

## ✅ 실행 체크리스트

| 단계 | 필수/선택 | 확인 |
|------|----------|------|
| `pip install -r requirements.txt` | 필수 | ⬜ |
| `streamlit run app.py` 정상 실행 | 필수 | ⬜ |
| 기록 저장 / 검색 / 삭제 동작 | 필수 | ⬜ |
| Excel 다운로드 (한글 포함 OK) | 필수 | ⬜ |
| PDF 다운로드 (한글 정상 표시) | 필수 | ⬜ |
| OpenAI 키 입력 후 AI 분석 실제 동작 | 선택 | ⬜ |
| 음성 입력 → 텍스트 변환 동작 | 선택 | ⬜ |
| Telegram 테스트 알림 도착 | 선택 | ⬜ |
| Google 로그인 화면 진입 + 로그인 성공 | 선택 | ⬜ |
| Streamlit Cloud 배포 + Secrets 입력 | 선택 | ⬜ |

---

## 📝 라이선스 / 개인정보

- 본 앱은 개인 기록 관리를 위한 도구입니다.
- 로컬 모드에서는 모든 데이터가 사용자 PC의 `bangju_records.db`에만 저장됩니다.
- OpenAI를 연동하면 입력 텍스트가 OpenAI 서버로 전송됩니다. 민감 정보 입력 시 주의하세요.
- 배포 시 `secrets.toml`을 절대 공개 저장소에 올리지 마세요.

---

🛶 *"기록은 미래의 나를 위한 가장 친절한 선물입니다."*
