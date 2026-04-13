import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 지능형 모델 로드 로직 (404 에러 원천 차단)
@st.cache_resource
def load_best_available_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # 현재 키로 사용 가능한 모델 목록 싹 긁어오기
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2026년 우선순위 리스트
        targets = ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "models/gemini-pro"]
        
        for target in targets:
            if target in models:
                return genai.GenerativeModel(target), target
        
        # 리스트에 없으면 첫 번째 모델이라도 반환
        if models:
            return genai.GenerativeModel(models[0]), models[0]
        return None, "No models found"
    except Exception as e:
        return None, str(e)

# 보안: Secrets 확인
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ Streamlit Secrets에 'GOOGLE_API_KEY'가 없습니다.")
    st.stop()

model, active_model_name = load_best_available_model(st.secrets["GOOGLE_API_KEY"])

# 사이드바 상태 표시
with st.sidebar:
    st.header("⚙️ System Status")
    if model:
        st.success(f"🤖 모델 연결 성공: {active_model_name}")
    else:
        st.error(f"❌ 모델 로드 실패: {active_model_name}")
        st.info("💡 팁: GitHub의 requirements.txt 버전을 높이고 잠시 기다려주세요.")
        st.stop()
    st.info("🔒 API Key 보안 관리 중")

# 3. JSON 추출 및 메인 로직 (안정화 버전)
def extract_clean_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return None
    except: return None

st.title("DS AEO & Schema Master (Gemini Powered)")
st.markdown("### Input Configurations")

urls_input = st.text_area("Target URLs", height=100, placeholder="https://classys.co.kr")
context_input = st.text_area("Context Details", placeholder="비즈니스 목적을 입력하세요.")

if st.button("🚀 Start Analysis", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    if not urls:
        st.warning("⚠️ URL을 입력해주세요.")
    else:
        for url in urls:
            st.markdown("---")
            st.subheader(f"🌐 Analysis for: {url}")
            try:
                with st.spinner(f"{active_model_name} 분석 중..."):
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for s in soup(["script", "style"]): s.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                    prompt = f"Scraped Text: {page_text}\nContext: {context_input}\nGenerate AEO JSON with tones: Humorous, Academic, Global Trend."
                    response = model.generate_content(prompt)
                    result = extract_clean_json(response.text)
                    
                    if result:
                        cols = st.columns(3)
                        tones = ["Humorous", "Academic", "Global Trend"]
                        for i, tone in enumerate(tones):
                            with cols[i]:
                                st.markdown(f"#### 🎭 {tone}")
                                data = result.get(tone, {})
                                st.info(data.get('text', '내용 생성 실패'))
                                q = data.get('searchQuery', '')
                                st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={urllib.parse.quote(q)}", use_container_width=True)
                    else:
                        st.error("AI 응답 파싱 실패")
            except Exception as e:
                st.error(f"❌ 오류: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)