# pages/00_Upload.py
import sys, os, uuid
import streamlit as st
import time
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from app import render_sidebar, is_logged_in
from core.ui import hide_default_nav

hide_default_nav()
render_sidebar()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.storage import get_storage
from core.db import insert_photo_record

load_dotenv()

st.title("Image Upload")

# 1) 로그인 여부 확인
auth = st.session_state.get("auth")
if not auth or "user_id" not in auth:
    st.warning("로그인이 필요합니다. 먼저 로그인 페이지에서 로그인해주세요.")
    time.sleep(2)
    st.switch_page("app.py")
    st.stop()

# 2) 로그인된 사용자 ID 확보
user_id = auth["user_id"]

# 3) 화면엔 읽기전용으로 보여주기(선택)
st.text_input("User ID (UUID)", value=user_id, disabled=True)

storage = get_storage()
st.caption(f"Storage backend: **{type(storage).__name__}**")
if hasattr(storage, "bucket"):
    st.caption(f"Bucket: **{getattr(storage, 'bucket', None)}**")

imgs_id = st.number_input("IMGS ID", min_value=1, step=1)
files = st.file_uploader("Select an image", type=["jpg","jpeg","png"], accept_multiple_files=True)

if files and imgs_id:
    for file in files:
        img = Image.open(file).convert("RGB")
        raw = BytesIO()
        img.save(raw, format="JPEG", quality=92)
        data = raw.getvalue()        # 바이트를 미리 확보
        size = len(data)             # DB에 넣을 파일 크기  
        key  = f"users/{user_id}/imgs/{int(imgs_id)}/original/{uuid.uuid4()}.jpg"

        # 4) S3/Local 업로드
        try:
            etag = storage.put(BytesIO(data), key, content_type="image/jpeg")
            st.success(f"[{file.name}] 업로드 완료 (etag={etag})")
        except Exception as e:
            st.error(f"S3 업로드 실패: {e!r}")
            continue

        # 5) DB 적재 (user_id는 세션에서)
        try:
            photo_id = insert_photo_record(
                user_id=user_id,
                bucket=getattr(storage, "bucket", "local-bucket"),
                key=key,
                content_type="image/jpeg",
                size=size,
                taken_at=None, lon=None, lat=None
            )
            st.success(f"DB 기록 완료 → photo_id={photo_id}")
        except Exception as e:
            st.error(f"DB insert 실패: {e!r}")
            continue

        # 6) 미리보기
        try:
            st.image(img, caption=file.name, use_container_width=True)
            st.write("Preview URL:", storage.url(key))
        except Exception:
            st.info("Local backend: presigned URL 없음")
