import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 모델 설정 (Failsafe 자동 탐색)
@st.cache_resource
def load_model(api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        targets = ["models/gemini-1.5-flash", "models/gemini-2.0-flash", "models/gemini-pro"]
        for t in targets:
            if t in models: return genai.GenerativeModel(t), t
        return None, "No Model"
    except Exception as e: return None, str(e)

api_key = st.secrets.get("GOOGLE_API_KEY")
model, active_model = load_model(api_key)

# 3. 사이드바 및 상태 표시
with st.sidebar:
    st.header("⚙️ System")
    if model: st.success(f"🟢 {active_model} 가동 중")
    else: st.error("🔴 API 연결 확인 필요"); st.stop()

# 4. 입력 섹션
st.title("DS AEO & Schema Master")
urls_input = st.text_area("Target URLs", height=80, placeholder="(검색하고 싶은 URL 주소를 복사해서 붙여넣기 해주세요)")
context_input = st.text_area("Context Details (강조할 키워드/의도)", placeholder="예: 클래시스, 볼뉴머, 6.78MHz 고주파, 안전한 리프팅")

def extract_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1: return json.loads(text[start:end+1])
        return None
    except: return None

# 5. 실행 로직
if st.button("🚀 데이터 추출 및 AEO 분석 시작", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    if urls:
        for url in urls:
            st.markdown(f"### 🌐 분석 결과: {url}")
            try:
                # [Step 1] 크롤링 및 기존 데이터 노출
                with st.spinner("현재 페이지 데이터 수집 중..."):
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    # 스키마 추출
                    scripts = soup.find_all("script", type="application/ld+json")
                    current_schemas = [json.loads(s.string, strict=False) for s in scripts if s.string]
                    
                    # 텍스트 추출
                    for s in soup(["script", "style"]): s.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                # 크롤링 내용 선노출
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    with st.expander("📄 현재 페이지 텍스트 (요약)", expanded=True):
                        st.write(page_text[:500] + "...")
                with col_c2:
                    with st.expander("🧩 발견된 기존 스키마", expanded=True):
                        st.json(current_schemas) if current_schemas else st.info("스키마 없음")

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

                    Return ONLY JSON:
                    {{
                      "정석 타입": {{"ko": "...", "en": "...", "schema": "...", "code": {{}}, "query": "..."}},
                      "신뢰 타입": {{"ko": "...", "en": "...", "schema": "...", "code": {{}}, "query": "..."}},
                      "글로벌 트렌드": {{"ko": "...", "en": "...", "schema": "...", "code": {{}}, "query": "..."}}
                    }}
                    """
                    response = model.generate_content(prompt)
                    result = extract_json(response.text)

                # [Step 3] 결과 디스플레이
                if result:
                    st.markdown("#### 💡 AEO 전략 제안")
                    t_cols = st.columns(3)
                    tones = ["정석 타입", "신뢰 타입", "글로벌 트렌드"]
                    
                    for i, tone in enumerate(tones):
                        with t_cols[i]:
                            st.subheader(f"🎭 {tone}")
                            data = result.get(tone, {})
                            
                            # 번역 탭/버전 선택 (Streamlit의 탭 기능 활용)
                            tab_ko, tab_en = st.tabs(["🇰🇷 한국어", "🇺🇸 English"])
                            with tab_ko:
                                st.write(data.get('ko', '내용 없음'))
                                st.code(data.get('ko', ''), language="text") # 복사용
                            with tab_en:
                                st.write(data.get('en', 'No Content'))
                                st.code(data.get('en', ''), language="text") # 복사용
                            
                            st.caption(f"**추천 스키마:** `{data.get('schema')}`")
                            with st.expander("JSON-LD 코드 보기"):
                                st.json(data.get('code'))
                            
                            q = data.get('query', '')
                            st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={urllib.parse.quote(q)}", use_container_width=True)
                else: st.error("AI 분석 결과 파싱 실패")

            except Exception as e: st.error(f"오류: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Digital AI Alchemist DS - VAIB-X Team</div>", unsafe_allow_html=True)