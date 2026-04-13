import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import google.generativeai as genai
import re

# 1. 페이지 설정
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

# 2. 보안 및 모델 설정 (Failsafe 자동 탐색 로직 적용)
try:
    # Streamlit Secrets에서 API 키 로드
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # 404 에러 방지: 작동하는 모델 이름을 순차적으로 시도합니다.
    model_candidates = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    model = None
    
    for m_name in model_candidates:
        try:
            temp_model = genai.GenerativeModel(m_name)
            # 가벼운 핑 테스트로 작동 여부 확인
            temp_model.generate_content("ping", generation_config={"max_output_tokens": 1})
            model = temp_model
            break 
        except:
            continue
            
    if not model:
        st.error("⚠️ 모든 Gemini 모델 호출에 실패했습니다. API 키 권한이나 라이브러리 버전을 확인해주세요.")
        st.stop()
        
except Exception as e:
    st.error(f"⚠️ 초기 설정 오류: {str(e)}. Streamlit Secrets를 확인해주세요.")
    st.stop()

# 3. JSON 추출 강화 함수 (파싱 에러 완벽 방어)
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

# 5. 메인 화면
st.title("DS AEO & Schema Master (Gemini Powered)")
st.markdown("### Input Configurations")

urls_