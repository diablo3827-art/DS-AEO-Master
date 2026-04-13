import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import os
import google.generativeai as genai

# Keys will be loaded from st.secrets directly

# Set up the page config
st.set_page_config(page_title="DS AEO & Schema Master", layout="wide")

st.title("DS AEO & Schema Master (Gemini Powered)")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ About")
    st.markdown("This tool extracts text and Schema.org structured data from URLs and uses Gemini to generate 3-toned AEO optimized texts with Schema recommendations.\n\n*Note: The Gemini API Key is securely managed via Streamlit Secrets.*")

# Main input section
st.markdown("### Input Configurations")
urls_input = st.text_area("Target URLs (Enter one URL per line)", height=100, placeholder="https://example.com\nhttps://example.com/about")
context_input = st.text_area("Context Details", placeholder="Describe the business or page intent to guide the AEO text generation. e.g., 'We sell organic dog food online.'")

if st.button("🚀 Start Analysis", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
        st.stop()
        
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
    except KeyError:
        st.error("⚠️ API key is missing. Please add GOOGLE_API_KEY to your Streamlit secrets (.streamlit/secrets.toml) or Cloud Settings!")
        st.stop()
        
    # Initialize Gemini Model
    genai.configure(api_key=api_key)
    # Ensure JSON format is requested via prompt (as Gemini-pro handles standard queries)
    model = genai.GenerativeModel("gemini-pro")

    st.markdown("---")
    
    for url in urls:
        st.subheader(f"🌐 Analysis for: {url}")
        
        try:
            # Step 1: URL Fetch, Text and Schema Extraction
            with st.spinner("Fetching Content & Extracting Schemas..."):
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Grab visible text, skip scripts/styles
                for script in soup(["script", "style"]):
                    script.extract()
                page_text = soup.get_text(separator=' ', strip=True)
                # Keep it concise to avoid token limit overflow - limit roughly 5000 characters
                page_text_short = page_text[:5000]
                
                scripts = soup.find_all("script", type="application/ld+json")
                schemas = []
                for s in scripts:
                    try:
                        data = json.loads(s.string, strict=False)
                        schemas.append(data)
                    except Exception:
                        pass

            # Display Extracted Schema & Text snippet
            with st.expander("📄 Extracted Schema.org (ld+json) Data", expanded=False):
                if schemas:
                    st.json(schemas)
                else:
                    st.info("No application/ld+json schema found on this page.")
                    
            with st.expander("📝 Extracted Page Text (Preview)", expanded=False):
                st.text(page_text_short[:500] + "\n\n... (truncated)")

            # Step 2: AEO Generation (Gemini API)
            with st.spinner("Generating AEO Optimized Texts and Schema Recommendations via Gemini..."):
                prompt = f"""
                You are an expert SEO and AEO (Answer Engine Optimization) specialist and a Schema.org master.
                The user wants to generate AEO text and recommend a matching Schema.org configuration based on a scraped webpage.
                
                Here is a truncated version of the text extracted from the target URL:
                {page_text_short}
                
                Here are the currently existing schemas found on the target URL (if any):
                {json.dumps(schemas, ensure_ascii=False, indent=2)}
                
                Context of the user's business/intent (important!):
                {context_input}
                
                Task:
                1. Analyze the page text, the user's context, and the existing schemas.
                2. Generate an AEO-optimized short answer/phrase describing the core value proposition in 3 different tones:
                   - Humorous (한국어로 센스있고 재미있게 작성)
                   - Academic (한국어로 전문적이고 학술적인 느낌으로 작성)
                   - Global Trend (한국어로 최신 글로벌 밈 트렌드 느낌으로 작성)
                3. For each tone, recommend a suitable Schema.org type (e.g., Organization, Product, FAQPage) and provide the relevant JSON-LD code block.
                4. Provide a simple search query (searchQuery) for each tone that the user can click to test the idea on Answer Engines.
                
                Return ONLY a valid JSON object matching EXACTLY this structure (do not output any markdown formatting like ```json, just raw JSON string):
                {{
                  "Humorous": {{
                    "text": "Generated AEO text here",
                    "schemaType": "Recommended Schema Type",
                    "schemaCode": {{"@context": "https://schema.org", "@type": "..."}},
                    "searchQuery": "Search keyword"
                  }},
                  "Academic": {{
                    "text": "Generated AEO text here",
                    "schemaType": "Recommended Schema Type",
                    "schemaCode": {{"@context": "https://schema.org", "@type": "..."}},
                    "searchQuery": "Search keyword"
                  }},
                  "Global Trend": {{
                    "text": "Generated AEO text here",
                    "schemaType": "Recommended Schema Type",
                    "schemaCode": {{"@context": "https://schema.org", "@type": "..."}},
                    "searchQuery": "Search keyword"
                  }}
                }}
                """
                
                response = model.generate_content(prompt)
                res_text = response.text.strip()
                
                # Fail-safe cleanup incase gemini wraps in markdown
                if res_text.startswith("```json"):
                    res_text = res_text[7:]
                if res_text.startswith("```"):
                    res_text = res_text[3:]
                if res_text.endswith("```"):
                    res_text = res_text[:-3]
                    
                result = json.loads(res_text.strip())
            
            # Step 3: Display Results
            st.markdown("### 💡 Recommended AEO & Schemas (Powered by Gemini)")
            cols = st.columns(3)
            tones = ["Humorous", "Academic", "Global Trend"]
            
            for index, tone in enumerate(tones):
                with cols[index]:
                    st.markdown(f"#### 🎭 {tone}")
                    tone_data = result.get(tone, {})
                    
                    st.info(f"**AEO Text:**\n\n{tone_data.get('text', '')}")
                    
                    st.markdown(f"**Schema Type:** `{tone_data.get('schemaType', '')}`")
                    with st.expander("View Schema Code", expanded=False):
                        st.json(tone_data.get('schemaCode', {}))
                    
                    query = tone_data.get('searchQuery', '')
                    encoded_query = urllib.parse.quote(query)
                    genspark_url = f"https://www.genspark.ai/search?query={encoded_query}"
                    
                    # Ensure Genspark Deep Link is prominently placed next to result
                    st.link_button(f"🔍 Test '{query}' on Genspark", genspark_url, use_container_width=True)
                    
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Network Error processing {url}: {str(e)}")
        except json.JSONDecodeError as e:
            st.error(f"❌ Failed to parse response from Gemini into JSON. \n\nError: {str(e)}\n\nRaw output snippet:\n {res_text[:300]}")
        except Exception as e:
            st.error(f"❌ An unexpected error occurred: {str(e)}")
            
        st.markdown("---")

st.markdown("<div style='text-align: center; color: gray;'>Developed by DS - Empowering your web presence with AEO & Schemas</div>", unsafe_allow_html=True)
