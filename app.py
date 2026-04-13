import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai

# 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 보안: Secrets에서 API 키 로드
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # 2026년 최신 모델인 gemini-3-flash로 업데이트
    model = genai.GenerativeModel("gemini-3-flash")
except Exception:
    st.error("⚠️ GOOGLE_API_KEY 설정 오류. Streamlit Cloud의 Settings > Secrets를 확인하세요.")
    st.stop()

# 사이드바
with st.sidebar:
    st.header("⚙️ About")
    st.markdown("본 도구는 URL에서 텍스트와 스키마를 추출하여 Gemini AI가 AEO 최적화 문구와 스키마 추천을 생성합니다.")
    st.info("🔒 API Key는 시스템 내부에서 안전하게 관리됩니다.")

# 메인 화면
st.title("DS AEO & Schema Master (Gemini Powered)")
st.markdown("### Input Configurations")

urls_input = st.text_area("Target URLs (한 줄에 하나씩 입력)", height=100, placeholder="https://classys.co.kr")
context_input = st.text_area("Context Details", placeholder="비즈니스의 목적이나 페이지의 의도를 입력하세요.")

if st.button("🚀 Start Analysis", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    if not urls:
        st.warning("⚠️ 분석할 URL을 입력해주세요.")
        st.stop()
        
    for url in urls:
        st.markdown("---")
        st.subheader(f"🌐 Analysis for: {url}")
        
        try:
            with st.spinner("데이터 추출 및 분석 중..."):
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                for script in soup(["script", "style"]): script.extract()
                page_text = soup.get_text(separator=' ', strip=True)[:4000]

                prompt = f"""
                Web Content: {page_text}
                Analyze and return ONLY a raw JSON:
                {{
                  "Humorous": {{"text": "", "schemaType": "", "schemaCode": {{}}, "searchQuery": ""}},
                  "Academic": {{"text": "", "schemaType": "", "schemaCode": {{}}, "searchQuery": ""}},
                  "Global Trend": {{"text": "", "schemaType": "", "schemaCode": {{}}, "searchQuery": ""}}
                }}
                """
                response = model.generate_content(prompt)
                res_text = response.text.strip()
                if "
http://googleusercontent.com/immersive_entry_chip/0

---

