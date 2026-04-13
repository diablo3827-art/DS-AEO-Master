import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 모델 설정 (Failsafe 자동 탐색 + 예외 처리 강화)
MODEL_PRIORITY = [
    "models/gemini-1.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-1.5-pro",
    "models/gemini-pro",
]

@st.cache_resource
def load_model(api_key):
    if not api_key:
        return None, "API 키가 없습니다. Streamlit Secrets에서 GOOGLE_API_KEY를 설정하세요."
    try:
        genai.configure(api_key=api_key)
        try:
            available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        except Exception:
            available = MODEL_PRIORITY  # list_models 실패 시 전체 시도

        for target in MODEL_PRIORITY:
            if target in available:
                try:
                    m = genai.GenerativeModel(target)
                    # 간단한 ping으로 유효성 확인
                    m.generate_content("Hi", generation_config={"max_output_tokens": 5})
                    return m, target
                except Exception as ping_err:
                    err_str = str(ping_err)
                    if "429" in err_str or "quota" in err_str.lower():
                        continue  # 다음 모델 시도
                    # 그 외 에러는 모델 자체는 유효하다고 판단하고 반환
                    return m, target
        return None, "사용 가능한 모델이 없습니다 (모든 모델 할당량 초과)."
    except Exception as e:
        return None, str(e)

api_key = st.secrets.get("GOOGLE_API_KEY", "")
model, active_model = load_model(api_key)

# 3. 사이드바 및 상태 표시
with st.sidebar:
    st.header("⚙️ System")
    if model:
        st.success(f"🟢 {active_model} 가동 중")
    else:
        st.error(f"🔴 {active_model}")
        st.stop()

# 4. 입력 섹션
st.title("DS AEO & Schema Master")
urls_input = st.text_area("Target URLs", height=80, placeholder="(검색하고 싶은 URL 주소를 복사해서 붙여넣기 해주세요)")
context_input = st.text_area("Context Details (강조할 키워드/의도)", placeholder="예: 클래시스, 볼뉴머, 6.78MHz 고주파, 안전한 리프팅")

def extract_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return None
    except Exception:
        return None

def generate_with_fallback(prompt):
    """Quota 초과 시 다른 모델로 자동 fallback"""
    global model, active_model
    
    # 현재 모델로 먼저 시도
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        err_str = str(e)
        if "429" not in err_str and "quota" not in err_str.lower():
            raise e  # quota 에러가 아니면 그대로 raise

    # Quota 초과: 다른 모델로 fallback
    st.warning(f"⚠️ {active_model} 할당량 초과. 다른 모델로 전환 중...")
    genai.configure(api_key=api_key)
    
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception:
        available = MODEL_PRIORITY

    for target in MODEL_PRIORITY:
        if target == active_model:
            continue  # 이미 실패한 모델 건너뜀
        if target not in available:
            continue
        try:
            fallback_model = genai.GenerativeModel(target)
            response = fallback_model.generate_content(prompt)
            # 성공 시 전역 모델 교체
            model = fallback_model
            active_model = target
            st.sidebar.success(f"🟢 {active_model} 전환 완료")
            return response.text
        except Exception as inner_e:
            inner_str = str(inner_e)
            if "429" in inner_str or "quota" in inner_str.lower():
                continue
            raise inner_e

    raise RuntimeError("모든 Gemini 모델의 할당량이 초과되었습니다. 잠시 후 다시 시도해주세요.")

# 5. 실행 로직
if st.button("🚀 데이터 추출 및 AEO 분석 시작", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    if not urls:
        st.warning("URL을 한 줄에 하나씩 입력해주세요.")
    else:
        for url in urls:
            st.markdown(f"### 🌐 분석 결과: [{url}]({url})")
            try:
                # [Step 1] 크롤링 및 기존 데이터 노출
                with st.spinner("현재 페이지 데이터 수집 중..."):
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    # 스키마 추출
                    scripts = soup.find_all("script", type="application/ld+json")
                    current_schemas = []
                    for s in scripts:
                        if s.string:
                            try:
                                current_schemas.append(json.loads(s.string, strict=False))
                            except json.JSONDecodeError:
                                pass

                    # 텍스트 추출
                    for tag in soup(["script", "style"]):
                        tag.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                # 크롤링 내용 선노출
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

                # [Step 2] AI 분석 (정석, 신뢰, 트렌드)
                with st.spinner("Gemini AI가 AEO 전략 수립 중..."):
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
                    raw_text = generate_with_fallback(prompt)
                    result = extract_json(raw_text)

                # [Step 3] 결과 디스플레이
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
                                    f"🔍 '{q}' 테스트",
                                    f"https://www.genspark.ai/search?query={urllib.parse.quote(q)}",
                                    use_container_width=True
                                )
                else:
                    st.error("AI 분석 결과 파싱 실패. 응답 원문:")
                    with st.expander("원문 보기"):
                        st.text(raw_text[:2000] if 'raw_text' in dir() else "응답 없음")

            except RuntimeError as re_err:
                st.error(f"🚫 {str(re_err)}")
            except requests.exceptions.RequestException as req_err:
                st.error(f"🌐 URL 접근 오류: {str(req_err)}")
            except Exception as e:
                st.error(f"오류: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Digital AI Alchemist DS - VAIB-X Team</div>", unsafe_allow_html=True)