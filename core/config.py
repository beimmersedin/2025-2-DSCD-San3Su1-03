# core/config.py
import os
import functools
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

@functools.lru_cache(maxsize=1)  # 혹은 @st.cache_resource
def get_openai_client() -> OpenAI:
    """
    우선순위:
      1) st.secrets["openai"]["api_key"]
      2) 환경변수 OPENAI_API_KEY (자동 .env 로드)
    """
    # .env 로드 (없으면 무시)
    load_dotenv()

    api_key = None
    if "openai" in st.secrets:
        api_key = st.secrets["openai"].get("api_key")

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    assert api_key, "OPENAI_API_KEY 미설정: .env 또는 .streamlit/secrets.toml 에 키를 넣어주세요."
    return OpenAI(api_key=api_key)
