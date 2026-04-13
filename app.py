import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 모델 진단 및 설정
def get_working_model():
    if "GOOGLE_API_KEY" not in st.secrets:
        st.error("❌ Streamlit Secrets에 'GOOGLE_API_KEY'가 설정되지 않았습니다.")
        return None, "Secrets Missing"

    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # 시도해볼 모델 후보군 (2026 표준)
    candidates = ["gemini-3-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    errors = []

    for name in candidates:
        try:
            m = genai.GenerativeModel(name)
            # 핑 테스트
            m.generate_content("test", generation_config={"max_output_tokens": 1})
            return m, None
        except Exception as e:
            errors.append(f"{name}: {str(e)}")
            continue
            
    return None, errors

model, debug_errors = get_working_model()

# 사이드바에 진단 정보 표시
with st.sidebar:
    st.header("⚙️ System Status")
    if model:
        st.success(f"🤖 가동 중: {model.model_name}")
    else:
        st.error("❌ 모델 연결 실패")
        with st.expander("상세 에러 로그 확인"):
            for err in debug_errors:
                st.write(err)
    st.info("🔒 API Key는 Secrets 금고에서 관리 중")

if not model:
    st.stop()

# 3. JSON 추출 및 메인 로직 (이전과 동일, 안정화 버전)
def extract_clean_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx:end_idx+1]
            return json.loads(json_str)
        return None
    except: return None

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
                with st.spinner("AI 분석 중..."):
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for s in soup(["script", "style"]): s.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                    prompt = f"Analyze and return JSON for: {page_text}\nContext: {context_input}"
                    response = model.generate_content(prompt)
                    result = extract_clean_json(response.text)
                    
                    if result:
                        cols = st.columns(3)
                        tones = ["Humorous", "Academic", "Global Trend"]
                        for i, tone in enumerate(tones):
                            with cols[i]:
                                st.markdown(f"#### 🎭 {tone}")
                                data = result.get(tone, {})
                                st.info(data.get('text', '생성 실패'))
                                q = data.get('searchQuery', '')
                                st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={urllib.parse.quote(q)}", use_container_width=True)
                    else:
                        st.error("AI 응답 파싱 실패")
            except Exception as e:
                st.error(f"❌ 오류: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)