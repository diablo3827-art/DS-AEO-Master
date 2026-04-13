import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 모델 최적화 및 보안 설정
def initialize_model():
    try:
        # Secrets에서 키 로드 확인
        if "GOOGLE_API_KEY" not in st.secrets:
            st.error("⚠️ Streamlit Secrets에 'GOOGLE_API_KEY'가 없습니다.")
            st.stop()
            
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        
        # 2026년 현재 가장 안정적인 모델 명칭 리스트
        # DS님의 Paid Tier 권한에 맞춘 Gemini 3 Flash를 1순위로 설정
        model_names = ["gemini-3-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]
        
        for name in model_names:
            try:
                m = genai.GenerativeModel(name)
                # 실제로 작동하는지 최소 토큰으로 테스트
                m.generate_content("test", generation_config={"max_output_tokens": 1})
                return m
            except Exception:
                continue
        return None
    except Exception as e:
        st.error(f"초기화 중 치명적 오류: {str(e)}")
        return None

model = initialize_model()

if not model:
    st.error("❌ 모든 Gemini 모델 호출에 실패했습니다.")
    st.info("💡 해결책: 1. API 키가 활성 상태인지 확인 / 2. requirements.txt에서 google-generativeai 버전을 최신으로 업그레이드")
    st.stop()

# 3. JSON 추출 강화 함수
def extract_clean_json(text):
    try:
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx:end_idx+1]
            return json.loads(json_str)
        return None
    except:
        return None

# 4. 사이드바 구성
with st.sidebar:
    st.header("⚙️ About")
    st.markdown("본 도구는 URL 데이터를 분석하여 AEO 최적화 문구와 스키마를 생성합니다.")
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
        st.stop()
        
    for url in urls:
        st.markdown("---")
        st.subheader(f"🌐 Analysis for: {url}")
        
        try:
            with st.spinner("AI 분석 엔진 가동 중..."):
                # Step 1: 크롤링 (3000자 제한)
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                for script in soup(["script", "style"]): script.extract()
                page_text = soup.get_text(separator=' ', strip=True)[:3000]
                
                # Step 2: Gemini 분석
                prompt = f"""
                Analyze the following content and return ONLY a valid JSON object.
                Context: {context_input}
                Text: {page_text}
                
                Structure:
                {{
                  "Humorous": {{"text": "한국어 내용", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}},
                  "Academic": {{"text": "한국어 내용", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}},
                  "Global Trend": {{"text": "한국어 내용", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}}
                }}
                """
                
                response = model.generate_content(prompt)
                result = extract_clean_json(response.text)
                
                if not result:
                    st.error("AI 응답 파싱 실패. 다시 시도해 주세요.")
                    continue

            # Step 3: 결과 출력
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