import streamlit as st
from openai import OpenAI
import json
import tempfile
import os

# --- 0. 클라이언트 초기화 ---
client = OpenAI()

st.title("📸 AI 여행일기 생성기 (이미지 자동 태깅 + 음식 구분)")

# --- 1. Streamlit 입력 영역 ---
st.header("1️⃣ 여행 사진 업로드")
uploaded_files = st.file_uploader(
    "여러 장의 이미지를 업로드하세요",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

st.header("2️⃣ SNS 게시글 옵션 설정")
platform = st.selectbox("플랫폼 선택", ["Instagram", "Blog", "X(Twitter)"])
mood = st.text_input("분위기 (예: 따뜻하고 감성적인 가을 하루)", "Calm and sentimental")
include_elements = st.text_input("포함할 요소 (쉼표로 구분)", "afternoon walk, autumn leaves")
language = st.selectbox("출력 언어", ["Korean", "English"])

generate_btn = st.button("✏️ 여행일기 생성하기")

# --- 2. 이미지 분석 함수 ---
def analyze_photo(image_path):
    """OpenAI Vision API로 이미지 분석 → 태그 및 음식/장소 구분"""
    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "이 사진의 주요 시각적 요소를 한국어로 태그 형태로 요약해줘. "
                                "음식이면 음식 이름도 포함하고, 장소라면 유형(예: 카페, 해변, 산 등)도 포함해줘."
                    },
                    {"type": "input_image", "image_url": f"file://{os.path.abspath(image_path)}"}
                ]
            }
        ],
        temperature=0.3
    )

    tags_text = response.output_text.strip()
    tags = [t.strip() for t in tags_text.replace("\n", " ").split(",") if t.strip()]
    return tags

# --- 3. 버튼 클릭 시 처리 ---
if generate_btn:
    if not uploaded_files:
        st.warning("이미지를 한 장 이상 업로드하세요.")
    else:
        photos = []

        with st.spinner("📷 이미지 분석 중..."):
            for file in uploaded_files:
                # 임시 파일로 저장
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(file.read())
                    tmp_path = tmp_file.name

                tags = analyze_photo(tmp_path)
                photos.append({
                    "time": "N/A",
                    "location_address": "Unknown",
                    "tags": tags
                })

        # 메타데이터 구성
        photo_metadata = {
            "trip_date": "2025-10-28",
            "photos": photos,
            "weather": "자동 감지되지 않음"
        }

        user_request = {
            "platform": platform,
            "mood": mood,
            "include_elements": [e.strip() for e in include_elements.split(",")],
            "language": language
        }

        st.success("✅ 이미지 분석 완료!")

        st.subheader("📊 생성된 태그 결과")
        st.json(photo_metadata)

        # --- 4. 여행일기 생성 ---
        st.info("✍️ 여행 일기 작성 중... 잠시만 기다려주세요.")

        system_prompt = f"""
        You are a professional Korean travel influencer and food blogger.
        Based on the given photo metadata and user request, write a social media post.
        Output JSON only:
        {{
          "title": "짧고 감성적인 제목 ({language})",
          "content": "여행일기 본문 ({language})",
          "hashtags": ["관련", "해시태그"]
        }}
        """

        user_prompt = f"""
        <photo_metadata>
        {json.dumps(photo_metadata, indent=2, ensure_ascii=False)}
        </photo_metadata>

        <user_request>
        {json.dumps(user_request, indent=2, ensure_ascii=False)}
        </user_request>
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            st.subheader("📝 생성된 여행 일기")
            st.markdown(f"### {result['title']}")
            st.write(result["content"])
            st.markdown("**해시태그:** " + " ".join([f"#{t}" for t in result["hashtags"]]))

        except Exception as e:
            st.error(f"API 호출 중 오류 발생: {e}")
