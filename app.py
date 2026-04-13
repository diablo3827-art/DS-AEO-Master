import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 보안 및 모델 설정 (Streamlit Secrets 활용)
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # [중요] 404 에러 방지용 모델 설정
    # 가장 범용적인 'gemini-1.5-flash'를 기본으로 사용합니다.
    model = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"⚠️ 설정 오류: {str(e)}. Streamlit Secrets를 확인해주세요.")
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
    except Exception:
        return None

# 4. 사이드바 구성
with st.sidebar:
    st.header("⚙️ About")
    st.markdown("본 도구는 URL에서 데이터를 추출하여 Gemini가 AEO 최적화 문구와 스키마를 생성합니다.")
    st.success("🔒 보안: API Key는 내부 금고에서 관리 중입니다.")

# 5. 메인 화면
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
            with st.spinner("데이터 추출 중..."):
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                for script in soup(["script", "style"]): script.extract()
                page_text = soup.get_text(separator=' ', strip=True)[:3000]
                
                scripts = soup.find_all("script", type="application/ld+json")
                schemas = [json.loads(s.string, strict=False) for s in scripts if s.string]

            with st.expander("📄 추출된 기존 Schema 데이터", expanded=False):
                st.json(schemas) if schemas else st.info("기존 스키마가 없습니다.")

            with st.spinner("Gemini AI 분석 중..."):
                # 모델명으로 인한 404 에러를 방지하기 위해 가장 안정적인 프롬프트 구조 사용
                prompt = f"""
                Analyze the following content and return ONLY a valid JSON object.
                Business Intent: {context_input}
                Page Text: {page_text}

                Format:
                {{
                  "Humorous": {{"text": "한국어", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}},
                  "Academic": {{"text": "한국어", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}},
                  "Global Trend": {{"text": "한국어", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}}
                }}
                """
                
                # 호출 시 모델이 지원되지 않는 경우를 대비한 try-except
                try:
                    response = model.generate_content(prompt)
                    result = extract_clean_json(response.text)
                except Exception as model_err:
                    st.error(f"모델 호출 중 오류 발생: {str(model_err)}")
                    st.info("💡 팁: requirements.txt의 라이브러리 버전을 높여보세요.")
                    st.stop()
                
                if not result:
                    st.error("⚠️ AI 응답 형식이 올바르지 않습니다.")
                    continue

            # 결과 출력
            cols = st.columns(3)
            tones = ["Humorous", "Academic", "Global Trend"]
            for i, tone in enumerate(tones):
                with cols[i]:
                    st.markdown(f"#### 🎭 {tone}")
                    data = result.get(tone, {})
                    st.info(data.get('text', '생성 실패'))
                    q = data.get('searchQuery', '')
                    encoded_q = urllib.parse.quote(q)
                    st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={encoded_q}", use_container_width=True)

        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)