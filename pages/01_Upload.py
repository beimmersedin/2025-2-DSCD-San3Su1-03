# pages/01_Upload.py
import sys, os, uuid
import streamlit as st
from PIL import Image
from io import BytesIO
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.storage import get_storage

st.title("POI Image Upload")
storage = get_storage()

poi_id = st.number_input("POI ID", min_value=1, step=1)
file = st.file_uploader("Select an image", type=["jpg","jpeg","png"])

if file and poi_id:
    img = Image.open(file).convert("RGB")
    buf = BytesIO(); img.save(buf, format="JPEG", quality=92); buf.seek(0)
    key = f"poi/{int(poi_id)}/original/{uuid.uuid4()}.jpg"
    storage.put(buf, key, content_type="image/jpeg")
    st.success(f"Uploaded as {key}")
    try:
        url = storage.url(key)   # local이면 파일경로, s3면 presigned URL
        st.image(img, caption=key, use_container_width=True)
        st.write("Preview URL:", url)
    except Exception as e:
        st.info("Local backend: no presigned URL")
