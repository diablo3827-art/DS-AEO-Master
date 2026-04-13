import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 모델 설정 (지능형 자동 선택 로직)
@st.cache_resource
def get_best_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # 1단계: 현재 API 키로 접근 가능한 모든 모델 리스트 확보
        available_models = [m.name for m in genai.list_models() 
                           if 'generateContent' in m.supported_generation_methods]
        
        # 2단계: 선호 순위 리스트 (2026 표준)
        preference = [
            "models/gemini-3-flash", 
            "models/gemini-1.5-flash", 
            "models/gemini-2.0-flash", 
            "models/gemini-pro"
        ]
        
        # 3단계: 매칭되는 첫 번째 모델 선택
        for target in preference:
            if target in available_models:
                return genai.GenerativeModel(target), target
        
        # 4단계: 매칭되는 게 없으면 목록의 첫 번째 모델이라도 반환
        if available_models:
            return genai.GenerativeModel(available_models[0]), available_models[0]
        return None, None
    except Exception as e:
        return None, str(e)

# 초기화 실행
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ Secrets에 'GOOGLE_API_KEY'가 없습니다!")
    st.stop()

model, model_name = get_best_model(st.secrets["GOOGLE_API_KEY"])

# 사이드바 상태 표시
with st.sidebar:
    st.header("⚙️ System Status")
    if model:
        st.success(f"🤖 가동 모델: {model_name}")
    else:
        st.error(f"❌ 모델 찾기 실패: {model_name}")
        st.stop()
    st.info("🔒 API Key 보안 가동 중")

# 3. JSON 정밀 추출 함수
def extract_clean_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return None
    except: return None

# 4. 메인 UI
st.title("DS AEO & Schema Master (Gemini Powered)")
st.markdown("### Input Configurations")

urls_input = st.text_area("Target URLs (한 줄에 하나씩)", height=100, placeholder="https://classys.co.kr")
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
                with st.spinner(f"{model_name} 분석 엔진 가동 중..."):
                    # 크롤링
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for s in soup(["script", "style"]): s.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                    # AI 분석
                    prompt = f"Scraped Text: {page_text}\nContext: {context_input}\nGenerate 3-toned AEO texts and return ONLY JSON."
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
                        st.error("AI 응답 형식이 올바르지 않습니다.")
            except Exception as e:
                st.error(f"❌ 분석 오류: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)