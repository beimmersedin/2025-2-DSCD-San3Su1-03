import streamlit as st

def hide_default_nav():
    css = """
    <style>
      /* 구버전/일반 */
      [data-testid="stSidebarNav"] { display: none !important; }
      /* 일부 버전에서 nav는 sidebar 내부 role="navigation"으로 렌더됨 */
      section[data-testid="stSidebar"] div[role="navigation"] { display: none !important; }
      /* 여백 보정(선택) */
      section[data-testid="stSidebar"] > div:has(> div[role="navigation"]) { padding-top: 0 !important; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
