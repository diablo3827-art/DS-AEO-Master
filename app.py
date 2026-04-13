import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re
import time

# ─────────────────────────────────────────────
# 1. 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# ─────────────────────────────────────────────
# 2. API 키 로드
# ─────────────────────────────────────────────
GOOGLE_API_KEY    = st.secrets.get("GOOGLE_API_KEY", "")
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")

# Gemini 모델 우선순위
GEMINI_MODELS = [
    "models/gemini-1.5-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.0-flash",
    "models/gemini-1.5-pro",
]

# OpenRouter 무료 모델 우선순위 (:free 접미사 필수)
OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ─────────────────────────────────────────────
# 3. 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ System")

    gemini_ok = bool(GOOGLE_API_KEY)
    openrouter_ok = bool(OPENROUTER_API_KEY)

    if gemini_ok:
        st.success("🟢 Gemini API 연결됨")
    else:
        st.warning("🟡 Gemini API 키 없음")

    if openrouter_ok:
        st.success("🟢 OpenRouter API 연결됨 (백업)")
    else:
        st.info("⚪ OpenRouter 미설정 (선택사항)")

    if not gemini_ok and not openrouter_ok:
        st.error("🔴 API 키가 하나도 없습니다. Secrets를 설정하세요.")
        st.stop()

    st.markdown("---")
    # 키가 하나라도 없을 때만 설정 안내 노출
    if not gemini_ok or not openrouter_ok:
        with st.expander("🔑 API 키 설정 방법", expanded=not gemini_ok):
            st.markdown("""
**Streamlit Secrets** (`.streamlit/secrets.toml`) 에 추가:

```toml
GOOGLE_API_KEY = "AIza..."
OPENROUTER_API_KEY = "sk-or-..."
```

**OpenRouter 무료 키 발급:**
1. [openrouter.ai](https://openrouter.ai) 회원가입
2. API Keys → Create Key
3. 무료 모델은 하루 50회 사용 가능
""")

    st.markdown("**모델 우선 순위**")
    st.caption("Gemini → OpenRouter 순으로 자동 전환")

# ─────────────────────────────────────────────
# 4. 유틸 함수
# ─────────────────────────────────────────────
def extract_json(text: str):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return None
    except Exception:
        return None


def call_openrouter(prompt: str, model: str) -> str:
    """OpenRouter API 호출 (OpenAI 호환)"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ds-aeo-master.streamlit.app",
        "X-Title": "DS AEO & Schema Master",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000,
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def generate_with_fallback(prompt: str) -> tuple[str, str]:
    """
    1) Gemini 모델 순서대로 시도
    2) 모두 Quota 초과 시 OpenRouter 무료 모델로 자동 fallback
    반환: (응답 텍스트, 사용된 모델명)
    """
    quota_errors = []

    # ── Gemini 시도 ──────────────────────────────
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        for model_name in GEMINI_MODELS:
            try:
                m = genai.GenerativeModel(model_name)
                response = m.generate_content(prompt)
                return response.text, f"Gemini · {model_name.replace('models/', '')}"
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower() or "exhausted" in err.lower():
                    quota_errors.append(f"Gemini/{model_name.replace('models/', '')}: quota 초과")
                    time.sleep(0.3)
                    continue
                elif "not found" in err.lower() or "404" in err:
                    continue
                else:
                    raise e

    # ── OpenRouter fallback ───────────────────────
    if OPENROUTER_API_KEY:
        for or_model in OPENROUTER_MODELS:
            try:
                text = call_openrouter(prompt, or_model)
                return text, f"OpenRouter · {or_model.split('/')[1].split(':')[0]}"
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                    quota_errors.append(f"OpenRouter/{or_model}: quota 초과")
                    time.sleep(0.3)
                    continue
                else:
                    raise e

    # ── 모두 실패 ─────────────────────────────────
    errors_str = "\n".join(quota_errors)
    raise RuntimeError(
        f"모든 AI 모델의 할당량이 초과되었습니다.\n\n"
        f"**시도한 모델:**\n{errors_str}\n\n"
        f"**해결 방법:**\n"
        f"1. 잠시 후 재시도 (무료 quota는 분/일 단위 초기화)\n"
        f"2. [OpenRouter](https://openrouter.ai) 무료 API 키 발급 후 Secrets에 추가\n"
        f"3. [Google AI Studio](https://aistudio.google.com/app/apikey) 에서 새 Gemini 키 발급"
    )


# ─────────────────────────────────────────────
# 5. 메인 UI
# ─────────────────────────────────────────────
st.title("DS AEO & Schema Master")
urls_input = st.text_area(
    "Target URLs",
    height=80,
    placeholder="분석할 URL 주소를 한 줄에 하나씩 입력하세요"
)
context_input = st.text_area(
    "Context Details (강조할 키워드/의도)",
    placeholder="예: 클래시스, 볼뉴머, 6.78MHz 고주파, 안전한 리프팅"
)

# ─────────────────────────────────────────────
# 6. 실행
# ─────────────────────────────────────────────
if st.button("🚀 데이터 추출 및 AEO 분석 시작", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    if not urls:
        st.warning("URL을 한 줄에 하나씩 입력해주세요.")
    else:
        for url in urls:
            st.markdown(f"### 🌐 분석 결과: [{url}]({url})")
            try:
                # ── Step 1: 크롤링 ──────────────────────────
                with st.spinner("현재 페이지 데이터 수집 중..."):
                    resp = requests.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=10
                    )
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    current_schemas = []
                    for s in soup.find_all("script", type="application/ld+json"):
                        if s.string:
                            try:
                                current_schemas.append(json.loads(s.string, strict=False))
                            except json.JSONDecodeError:
                                pass

                    for tag in soup(["script", "style"]):
                        tag.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    with st.expander("📄 현재 페이지 텍스트 (요약)", expanded=True):
                        st.write(page_text[:500] + "...")
                with col_c2:
                    with st.expander("🧩 발견된 기존 스키마", expanded=True):
                        if current_schemas:
                            st.json(current_schemas)
                        else:
                            st.info("스키마 없음")

                # ── Step 2: AI 분석 ─────────────────────────
                with st.spinner("AI가 AEO 전략 수립 중..."):
                    prompt = f"""
URL: {url}
Context: {context_input}
Page Text: {page_text}

Task: Generate AEO optimization contents in 3 Tones:
1. '정석 타입' (Formal, SEO-standard, Classic)
2. '신뢰 타입' (Expert, Authoritative, Trustworthy)
3. '글로벌 트렌드' (Trendy, Modern, Global Trend)

Requirements:
- Provide content in both Korean (ko) and English (en).
- Recommend a Schema.org type and JSON-LD code for each.
- Provide a 'searchQuery' for testing.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "정석 타입": {{"ko": "...", "en": "...", "schema": "...", "code": {{}}, "query": "..."}},
  "신뢰 타입": {{"ko": "...", "en": "...", "schema": "...", "code": {{}}, "query": "..."}},
  "글로벌 트렌드": {{"ko": "...", "en": "...", "schema": "...", "code": {{}}, "query": "..."}}
}}
"""
                    raw_text, used_model = generate_with_fallback(prompt)
                    st.caption(f"✅ 사용 모델: `{used_model}`")
                    result = extract_json(raw_text)

                # ── Step 3: 결과 표시 ───────────────────────
                if result:
                    st.markdown("#### 💡 AEO 전략 제안")
                    t_cols = st.columns(3)
                    tones = ["정석 타입", "신뢰 타입", "글로벌 트렌드"]

                    for i, tone in enumerate(tones):
                        with t_cols[i]:
                            st.subheader(f"🎭 {tone}")
                            data = result.get(tone, {})

                            tab_ko, tab_en = st.tabs(["🇰🇷 한국어", "🇺🇸 English"])
                            with tab_ko:
                                st.write(data.get('ko', '내용 없음'))
                                st.code(data.get('ko', ''), language="text")
                            with tab_en:
                                st.write(data.get('en', 'No Content'))
                                st.code(data.get('en', ''), language="text")

                            st.caption(f"**추천 스키마:** `{data.get('schema', 'N/A')}`")
                            with st.expander("JSON-LD 코드 보기"):
                                code_data = data.get('code', {})
                                if code_data:
                                    st.json(code_data)
                                else:
                                    st.info("코드 없음")

                            q = data.get('query', '')
                            if q:
                                st.link_button(
                                    f"🔍 '{q}' Genspark 검색",
                                    f"https://www.genspark.ai/search?query={urllib.parse.quote(q)}",
                                    use_container_width=True
                                )
                else:
                    st.error("AI 응답 파싱 실패. 원문을 확인하세요.")
                    with st.expander("원문 보기"):
                        st.text(raw_text[:3000] if raw_text else "응답 없음")

            except RuntimeError as re_err:
                st.error(str(re_err))
            except requests.exceptions.RequestException as req_err:
                st.error(f"🌐 URL 접근 오류: {str(req_err)}")
            except Exception as e:
                st.error(f"오류: {str(e)}")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>Digital AI Alchemist DS - VAIB-X Team</div>",
    unsafe_allow_html=True
)