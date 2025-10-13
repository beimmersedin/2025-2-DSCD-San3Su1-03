import streamlit as st
from core.db import healthcheck

st.set_page_config(page_title="Life Recorder", page_icon="📍", layout="wide")
st.title("Life Recorder")
st.caption("Photo metadata → route visualization, AI summary, trip recommendations")

ok = "OK" if healthcheck()==1 else "DB not connected"
st.info(f"DB health: {ok}")

st.markdown("""
Use the pages on the left:
1. **Route Visualization** - upload photos, see map & stops  
2. **AI Summary & Caption** - generate shareable text  
3. **Trip Recommendations** - discover next destinations  
4. **My Page** (optional) - view saved results
""")
