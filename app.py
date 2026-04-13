import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 보안: Secrets에서 API 키 로드 (UI 노출 없음)
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # 토큰 효율이 좋은 flash 모델로 설정
    model = genai.GenerativeModel("gemini-1.5-flash")
except Exception:
    st.error("⚠️ GOOGLE_API_KEY가 설정되지 않았습니다. Streamlit Cloud의 Settings > Secrets에 키를 등록해주세요.")
    st.stop()

# 3. 사이드바 구성
with st.sidebar:
    st.header("⚙️ About")
    st.markdown("본 도구는 URL에서 텍스트와 스키마를 추출하여 Gemini AI가 AEO 최적화 문구와 스키마 추천을 생성합니다.")
    st.info("🔒 API Key는 시스템 내부에서 안전하게 관리됩니다.")

# 4. 메인 화면
st.title("DS AEO & Schema Master (Gemini Powered)")
st.markdown("### Input Configurations")

urls_input = st.text_area("Target URLs (한 줄에 하나씩 입력)", height=100, placeholder="https://classys.co.kr")
context_input = st.text_area("Context Details", placeholder="비즈니스의 목적이나 페이지의 의도를 입력하세요. (예: '볼뉴머 리프팅 장비 소개 페이지')")

if st.button("🚀 Start Analysis", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if not urls:
        st.warning("⚠️ 분석할 URL을 입력해주세요.")
        st.stop()
        
    for url in urls:
        st.markdown("---")
        st.subheader(f"🌐 Analysis for: {url}")
        
        try:
            # Step 1: 데이터 추출
            with st.spinner("페이지 내용 및 스키마 추출 중..."):
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                for script in soup(["script", "style"]):
                    script.extract()
                
                page_text = soup.get_text(separator=' ', strip=True)[:4000] # 토큰 절약을 위한 4000자 제한
                
                scripts = soup.find_all("script", type="application/ld+json")
                schemas = []
                for s in scripts:
                    try:
                        if s.string:
                            schemas.append(json.loads(s.string, strict=False))
                    except: pass

            # 데이터 프리뷰
            with st.expander("📄 추출된 기존 Schema 데이터", expanded=False):
                st.json(schemas) if schemas else st.info("기존 스키마가 없습니다.")

            # Step 2: Gemini AEO 생성
            with st.spinner("Gemini AI가 AEO 최적화 분석 중..."):
                prompt = f"""
                Analyze the following webpage content and generate AEO optimized texts in 3 tones.
                Context: {context_input}
                Existing Schemas: {json.dumps(schemas, ensure_ascii=False)}
                Page Text: {page_text}

                Tasks:
                1. Humorous tone (센스있는 한국어)
                2. Academic tone (전문적인 한국어)
                3. Global Trend tone (최신 트렌드/밈 한국어)
                
                For each tone, include:
                - Optimized Text
                - Recommended Schema Type
                - JSON-LD Schema Code
                - Search Query for testing

                Return ONLY a raw JSON object:
                {{
                  "Humorous": {{"text": "", "schemaType": "", "schemaCode": {{}}, "searchQuery": ""}},
                  "Academic": {{"text": "", "schemaType": "", "schemaCode": {{}}, "searchQuery": ""}},
                  "Global Trend": {{"text": "", "schemaType": "", "schemaCode": {{}}, "searchQuery": ""}}
                }}
                """
                
                response = model.generate_content(prompt)
                res_text = response.text.strip()
                
                # 마크다운 태그 제거용 클린업
                if "```json" in res_text:
                    res_text = res_text.split("```json")[1].split("```")[0]
                elif "```" in res_text:
                    res_text = res_text.split("```")[1].split("```")[0]
                
                result = json.loads(res_text.strip())

            # Step 3: 결과 출력
            st.markdown("### 💡 Recommended AEO & Schemas")
            cols = st.columns(3)
            tones = ["Humorous", "Academic", "Global Trend"]
            
            for i, tone in enumerate(tones):
                with cols[i]:
                    st.markdown(f"#### 🎭 {tone}")
                    data = result.get(tone, {})
                    st.info(data.get('text', '내용 생성 실패'))
                    st.caption(f"**추천 스키마:** `{data.get('schemaType')}`")
                    
                    with st.expander("Schema Code 확인"):
                        st.json(data.get('schemaCode', {}))
                    
                    q = data.get('searchQuery', '')
                    encoded_q = urllib.parse.quote(q)
                    st.link_button(f"🔍 '{q}' 테스트", f"https://www.genspark.ai/search?query={encoded_q}", use_container_width=True)

        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - VAIB-X Team Leader</div>", unsafe_allow_html=True)