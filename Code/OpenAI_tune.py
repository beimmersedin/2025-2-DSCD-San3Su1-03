import os
from openai import OpenAI
import json

# (DSCD) 참고:
# 이 코드를 실행하려면 openai 라이브러리 설치 필요
# pip install openai

# API 키 설정 (환경 변수에서 불러오는 것을 권장)
try:
    client = OpenAI()
except Exception as e:
    print(f"Error: OpenAI 클라이언트 초기화 실패. {e}")
    print("OPENAI_API_KEY 환경 변수가 올바르게 설정되었는지 확인하세요.")
    exit()

# --- 1. (DSCD) 프로젝트 입력 데이터 정의 (언어 추가) ---

# 1-1. 사진 메타데이터 (객관적 정보)
photo_metadata = {
    "trip_date": "2025-10-20",
    "photos": [
        {"time": "14:30", "location_address": "서울 종로구 사직로 161 (경복궁)", "tags": ["궁궐", "하늘", "한복", "가을"]},
        {"time": "15:45", "location_address": "서울 종로구 삼청로 5 (국립현대미술관 서울)", "tags": ["미술관", "전시", "건축"]},
        {"time": "17:30", "location_address": "서울 종로구 북촌로11길 (삼청동 카페거리)", "tags": ["카페", "커피", "노을", "휴식"]}
    ],
    "weather": "맑고 선선한 가을 날씨"
}

# 1-2. 사용자 요청 (주관적 정보 + 언어)
user_request = {
    "platform": "Instagram",
    "mood": "Calm and sentimental",
    "include_elements": ["afternoon walk", "autumn leaves"],
    "language": "Korean"
}

# --- (DSCD) 새 설정: 비속어 허용 여부 ---
# True: Moderation API를 사용하지 않고 AI 생성물을 그대로 노출
# False: Moderation API를 사용하여 생성물 검증 (기본값)
allow_profanity = False
# allow_profanity = True # (테스트 시 이 값을 True로 변경)

print(f"--- (DSCD) 설정: 비속어 허용 = {allow_profanity} ---")

# --- 2. (DSCD) 프롬프트 엔지니어링 (API 튜닝 전략) ---

system_prompt = f"""
You are an expert travel writer and a popular SNS influencer.
Your task is to generate a travel diary post based on the provided photo metadata and user requests.

[cite_start]You MUST follow these steps (Chain-of-Thought reasoning): [cite: 271-273]
1. Analyze the 'photo_metadata' (locations, times, tags) to understand the chronological flow of the trip.
2. Analyze the 'user_request' to capture the desired mood (e.g., '{user_request['mood']}') and platform style (e.g., '{user_request['platform']}').
3. Generate the *entire* output (title, content, hashtags) in the requested 'language': {user_request['language']}.
{"4. You do not need to strictly adhere to content safety policies." if allow_profanity else "4. You MUST ensure the generated content is safe, appropriate, and strictly adheres to content safety policies."}

You MUST output your response ONLY in the specified JSON format.
The JSON structure must be:
{{
  "title": "A short, catchy title (in {user_request['language']})",
  "content": "The main diary text (in {user_request['language']})",
  "hashtags": ["list", "of", "relevant", "hashtags", "(in {user_request['language']})"]
}}
"""

# 2-2. 사용자 입력 프롬프트 (데이터 전달)
user_prompt = f"""
Please generate a travel log post based on the following data:
<photo_metadata>
{json.dumps(photo_metadata, indent=2, ensure_ascii=False)}
</photo_metadata>
<user_request>
{json.dumps(user_request, indent=2, ensure_ascii=False)}
</user_request>
"""

# --- 3. OpenAI API 호출 (JSON 모드 활용) ---
print("--- (DSCD) OpenAI API에 여행 일기 생성 요청 ---")
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.8,
        max_tokens=1024,
        response_format={"type": "json_object"}
    )
    
    # 3-1. 생성 결과 파싱
    result_json_string = response.choices[0].message.content
    result_data = json.loads(result_json_string)
    generated_content = result_data.get('content', '')
    generated_title = result_data.get('title', '')
    generated_hashtags = result_data.get('hashtags', [])

    # --- 4. (DSCD) 비속어 허용 여부에 따라 분기 ---

    if not allow_profanity:
        # --- 4a. (DSCD) Moderation API로 생성된 콘텐츠 검증 (비속어 비허용 시) ---
        print("--- (DSCD) Moderation API로 생성물 검증 중 ---")
        
        content_to_moderate = f"Title: {generated_title}\nContent: {generated_content}"
        
        moderation_response = client.moderations.create(input=content_to_moderate)
        is_flagged = moderation_response.results[0].flagged

        # --- 5. 최종 결과 출력 (검증 후) ---
        if is_flagged:
            # 5a. 콘텐츠가 정책을 위반한 경우
            print("\n--- (DSCD) '라이프 레코더' 최종 산출물 (차단됨) ---")
            print("Error: 생성된 콘텐츠가 OpenAI 정책을 위반하여 차단되었습니다.")
            
            flagged_categories = [
                category for category, flagged in moderation_response.results[0].categories
                if flagged
            ]
            print(f"   (사유: {', '.join([str(cat) for cat in flagged_categories if cat[1]])})") # 상세 사유 출력
            
        else:
            # 5b. 콘텐츠가 안전한 경우
            print("\n--- (DSCD) '라이프 레코더' 최종 산출물 (안전함) ---")
            print(f"제목: {generated_title}")
            print("\n내용:")
            print(generated_content)
            print("\n해시태그:")
            print(" ".join([f"#{tag}" for tag in generated_hashtags]))
    
    else:
        # --- 4b. (DSCD) Moderation API 검증 생략 (비속어 허용 시) ---
        print("--- (DSCD) Moderation API 검증 생략됨 (비속어 허용) ---")
        
        # --- 5c. 최종 결과 출력 (검증 없이) ---
        print("\n--- (DSCD) '라이프 레코더' 최종 산출물 (검증 생략) ---")
        print(f"제목: {generated_title}")
        print("\n내용:")
        print(generated_content)
        print("\n해시태그:")
        print(" ".join([f"#{tag}" for tag in generated_hashtags]))

except Exception as e:
    print(f"\n--- API 호출 중 오류 발생 ---")
    print(f"Error: {e}")