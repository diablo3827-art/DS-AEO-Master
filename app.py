import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 보안 및 모델 설정 (404/429 Failsafe)
try:
    if "GOOGLE_API_KEY" not in st.secrets:
        st.error("❌ Streamlit Secrets에 'GOOGLE_API_KEY'가 없습니다.")
        st.stop()
        
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # 404 에러 방지를 위해 'models/' 접두사를 붙인 가장 안정적인 명칭 사용
    # 1.5-flash는 무료 티어에서도 비교적 넉넉한 쿼터를 제공합니다.
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    
except Exception as e:
    st.error(f"⚠️ 초기 설정 오류: {str(e)}")
    st.stop()

# 3. JSON 추출 강화 함수 (Extra Data 방지)
def extract_clean_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            return json.loads(text[start_idx:end_idx+1])
        return None
    except: return None

# 4. 사이드바 구성
with st.sidebar:
    st.header("⚙️ About")
    st.markdown("본 도구는 URL에서 데이터를 추출하여 AEO 최적화 문구와 스키마를 생성합니다.")
    st.success(f"🤖 가동 모델: {model.model_name}")
    st.info("🔒 보안: API Key는 내부 금고에서 보호 중입니다.")

# 5. 메인 화면
st.title("DS AEO & Schema Master (Gemini Powered)")
st.markdown("### Input Configurations")

urls_input = st.text_area("Target URLs (한 줄에 하나씩)", height=100, placeholder="https://classys.co.kr")
context_input = st.text_area("Context Details", placeholder="비즈니스 목적을 입력하세요. (예: 볼뉴머 제품 홍보)")

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
                    # 크롤링 (3000자 제한)
                    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for s in soup(["script", "style"]): s.extract()
                    page_text = soup.get_text(separator=' ', strip=True)[:3000]

                    # AI 호출 (429/404 방어)
                    prompt = f"Analyze context: {context_input}\nText: {page_text}\nReturn ONLY JSON."
                    try:
                        response = model.generate_content(prompt)
                        result = extract_clean_json(response.text)
                    except Exception as api_err:
                        if "429" in str(api_err):
                            st.error("🚨 할당량 초과! 1분 뒤 다시 시도하거나 요금제를 확인하세요.")
                        elif "404" in str(api_err):
                            st.error("🚨 모델 경로 오류(404)! 라이브러리 업데이트가 필요할 수 있습니다.")
                        raise api_err
                    
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
            except Exception as e:
                st.error(f"❌ 오류 발생: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)