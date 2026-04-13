import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 모델 설정 (Failsafe 로직)
@st.cache_resource
def load_stable_model(api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 2026년 기준 가장 성능 좋은 모델 순서
        targets = ["models/gemini-3-flash", "models/gemini-2.5-flash", "models/gemini-1.5-flash"]
        for target in targets:
            if target in models:
                return genai.GenerativeModel(target), target
        if models: return genai.GenerativeModel(models[0]), models[0]
        return None, "No models"
    except Exception as e: return None, str(e)

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ Secrets에 'GOOGLE_API_KEY'가 없습니다.")
    st.stop()

model, active_model_name = load_stable_model(st.secrets["GOOGLE_API_KEY"])

with st.sidebar:
    st.header("⚙️ System Status")
    if model: st.success(f"🟢 연결 성공: {active_model_name}")
    else: st.error("🔴 연결 실패"); st.stop()

# 3. JSON 추출 함수 (더 정교하게 수정)
def extract_clean_json(text):
    try:
        # 마크다운 블록 제거
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return None
    except: return None

# 4. 메인 UI
st.title("DS AEO & Schema Master (Gemini Powered)")
urls_input = st.text_area("Target URLs", height=100, placeholder="https://classys.co.kr")
context_input = st.text_area("Context Details", placeholder="비즈니스 목적 (예: 볼뉴머 리프팅)")

if st.button("🚀 Start Analysis", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    if urls:
        for url in urls:
            st.markdown("---")
            try:
                with st.spinner(f"{active_model_name} 분석 중..."):
                    # 크롤링
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for s in soup(["script", "style"]): s.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                    # 프롬프트 강화 (JSON 구조를 명확히 지시)
                    prompt = f"""
                    Scraped Page Text: {page_text}
                    User Context: {context_input}
                    
                    Based on the text above, generate AEO (Answer Engine Optimization) content in 3 tones:
                    1. Humorous (재치있고 재미있게)
                    2. Academic (전문적이고 신뢰감 있게)
                    3. Global Trend (최신 트렌드/밈 스타일)

                    Return ONLY a JSON object with this EXACT structure:
                    {{
                      "Humorous": {{"text": "...", "searchQuery": "..."}},
                      "Academic": {{"text": "...", "searchQuery": "..."}},
                      "Global Trend": {{"text": "...", "searchQuery": "..."}}
                    }}
                    """
                    
                    response = model.generate_content(prompt)
                    result = extract_clean_json(response.text)
                    
                    if result:
                        cols = st.columns(3)
                        tones = ["Humorous", "Academic", "Global Trend"]
                        for i, tone in enumerate(tones):
                            with cols[i]:
                                st.markdown(f"#### 🎭 {tone}")
                                data = result.get(tone, {})
                                text_val = data.get('text', '내용 생성 오류')
                                st.info(text_val)
                                q = data.get('searchQuery', '')
                                st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={urllib.parse.quote(q)}", use_container_width=True)
                    else:
                        st.error("❌ AI 응답이 JSON 형식이 아닙니다.")
                        with st.expander("AI 원본 대답 보기 (디버깅용)"):
                            st.write(response.text)
            except Exception as e:
                st.error(f"❌ 오류: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)