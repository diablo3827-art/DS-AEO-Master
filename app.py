import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 보안 및 모델 설정 (Failsafe & Quota Handling)
try:
    if "GOOGLE_API_KEY" not in st.secrets:
        st.error("❌ Streamlit Secrets에 'GOOGLE_API_KEY'가 없습니다. Settings > Secrets를 확인해주세요.")
        st.stop()
        
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # 429 할당량 에러를 피하기 위해 가장 안정적인 1.5-flash 모델 사용
    model = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"⚠️ 초기 설정 오류: {str(e)}")
    st.stop()

# 3. JSON 추출 강화 함수 (Extra Data 에러 방지)
def extract_clean_json(text):
    try:
        # 마크다운 태그 제거
        text = re.sub(r'```json\s?|\s?```', '', text).strip()
        # 첫 번째 '{'와 마지막 '}' 사이의 순수 JSON 블록만 확보
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
    st.success(f"🤖 가동 모델: {model.model_name}")
    st.info("🔒 보안: API Key는 내부 금고에서 안전하게 관리 중입니다.")

# 5. 메인 화면 구성
st.title("DS AEO & Schema Master (Gemini Powered)")
st.markdown("### Input Configurations")

urls_input = st.text_area("Target URLs (한 줄에 하나씩)", height=100, placeholder="https://classys.co.kr")
context_input = st.text_area("Context Details", placeholder="비즈니스 목적을 입력하세요. (예: '볼뉴머 리프팅 장비 소개')")

if st.button("🚀 Start Analysis", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if not urls:
        st.warning("⚠️ 분석할 URL을 입력해주세요.")
        st.stop()
        
    for url in urls:
        st.markdown("---")
        st.subheader(f"🌐 Analysis for: {url}")
        
        try:
            # Step 1: 데이터 추출 (3000자 제한)
            with st.spinner("페이지 스캔 및 데이터 추출 중..."):
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                for script in soup(["script", "style"]): script.extract()
                page_text = soup.get_text(separator=' ', strip=True)[:3000]
                
                scripts = soup.find_all("script", type="application/ld+json")
                schemas = [json.loads(s.string, strict=False) for s in scripts if s.string]

            with st.expander("📄 추출된 기존 Schema 데이터", expanded=False):
                st.json(schemas) if schemas else st.info("기존 스키마가 발견되지 않았습니다.")

            # Step 2: Gemini 분석 (Quota Handling 추가)
            with st.spinner("Gemini AI 분석 중..."):
                prompt = f"""
                Analyze the following content and generate AEO optimized texts.
                Business Intent: {context_input}
                Existing Schemas: {json.dumps(schemas, ensure_ascii=False)}
                Page Text: {page_text}

                Return ONLY a valid JSON object:
                {{
                  "Humorous": {{"text": "한국어 내용", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}},
                  "Academic": {{"text": "한국어 내용", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}},
                  "Global Trend": {{"text": "한국어 내용", "schemaType": "...", "schemaCode": {{}}, "searchQuery": "..."}}
                }}
                """
                
                try:
                    response = model.generate_content(prompt)
                    result = extract_clean_json(response.text)
                except Exception as e:
                    if "429" in str(e):
                        st.error("🚨 API 호출 한도가 초과되었습니다! (429 Quota Exceeded)")
                        st.info("💡 해결책: 1분 뒤에 다시 시도하거나, Google AI Studio에서 결제 수단(Pay-as-you-go)을 등록하세요.")
                        st.stop()
                    else:
                        raise e
                
                if not result:
                    st.error("⚠️ AI 응답 형식이 올바르지 않습니다.")
                    continue

            # Step 3: 결과 출력
            cols = st.columns(3)
            tones = ["Humorous", "Academic", "Global Trend"]
            
            for i, tone in enumerate(tones):
                with cols[i]:
                    st.markdown(f"#### 🎭 {tone}")
                    data = result.get(tone, {})
                    st.info(data.get('text', '내용 생성 실패'))
                    st.caption(f"**추천 스키마:** `{data.get('schemaType', 'N/A')}`")
                    
                    with st.expander("Schema Code 확인"):
                        st.json(data.get('schemaCode', {}))
                    
                    q = data.get('searchQuery', '')
                    encoded_q = urllib.parse.quote(q)
                    st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={encoded_q}", use_container_width=True)

        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)