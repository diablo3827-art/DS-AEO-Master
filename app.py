import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 지능형 모델 로드 (0.8.6 버전 호환 로직)
@st.cache_resource
def load_stable_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # 사용 가능한 모델 목록 확인
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2026년 안정성 우선 순위
        targets = ["models/gemini-1.5-flash", "models/gemini-3-flash", "models/gemini-pro"]
        
        for target in targets:
            if target in models:
                return genai.GenerativeModel(target), target
        
        if models:
            return genai.GenerativeModel(models[0]), models[0]
        return None, "No models available"
    except Exception as e:
        return None, str(e)

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ Secrets에 'GOOGLE_API_KEY'가 없습니다.")
    st.stop()

model, active_model_name = load_stable_model(st.secrets["GOOGLE_API_KEY"])

with st.sidebar:
    st.header("⚙️ System Status")
    if model:
        st.success(f"🤖 연결 성공: {active_model_name}")
    else:
        st.error(f"❌ 연결 실패: {active_model_name}")
        st.stop()

# 3. JSON 추출 및 메인 로직
def extract_clean_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return None
    except: return None

st.title("DS AEO & Schema Master (Gemini Powered)")
urls_input = st.text_area("Target URLs", height=100, placeholder="https://classys.co.kr")
context_input = st.text_area("Context Details", placeholder="비즈니스 목적 입력")

if st.button("🚀 Start Analysis", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    if urls:
        for url in urls:
            st.markdown("---")
            try:
                with st.spinner(f"{active_model_name} 분석 중..."):
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for s in soup(["script", "style"]): s.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                    prompt = f"Scraped Text: {page_text}\nContext: {context_input}\nReturn ONLY JSON with 3 tones."
                    response = model.generate_content(prompt)
                    result = extract_clean_json(response.text)
                    
                    if result:
                        cols = st.columns(3)
                        for i, tone in enumerate(["Humorous", "Academic", "Global Trend"]):
                            with cols[i]:
                                st.markdown(f"#### 🎭 {tone}")
                                data = result.get(tone, {})
                                st.info(data.get('text', '생성 실패'))
                                q = data.get('searchQuery', '')
                                st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={urllib.parse.quote(q)}", use_container_width=True)
            except Exception as e:
                st.error(f"❌ 오류: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)