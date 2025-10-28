import streamlit as st
import pandas as pd
import requests
import time
import io
import zipfile
import re
from typing import List, Dict, Any
from rapidfuzz import fuzz # 🔹 문자열 유사도 계산용
import traceback # 상세 오류 로깅용

# Selenium 관련 라이브러리는 이 버전에서는 사용하지 않습니다.

# =========================================================
# ⚙️ 1. 설정 정보
# =========================================================
KAKAO_REST_API_KEY = "c2c5289d7f9ea5cfa234222f18883527"

TARGET_REGIONS = ["서울", "경기"]

TARGET_THEMES = [
    "한옥카페", "오션뷰 카페", "브런치 맛집", "베이커리 카페",
    "수목원", "자연휴양림", "미술관", "박물관", "문화 유적지", "테마파크",
    # 중복 테스트를 위한 키워드 추가
    "호수공원"
]

MAX_API_PAGES = 5
AI_TEST_IMAGE_COUNT = 100
MAX_IMAGES_PER_PLACE = 3  # ✅ 각 장소당 최대 이미지 개수
GPS_SIMILARITY_THRESHOLD = 0.001 # ✅ 핵심 키워드 중복 제거 시 사용할 GPS 근접 기준 (약 100m)

# =========================================================
# 2. API 요청 함수
# =========================================================
def search_kakao_local_api(query: str, page: int) -> Dict[str, Any]:
    """Kakao Local API (장소 검색)"""
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": query, "size": 15, "page": page}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Local API 요청 오류 ({query}, page {page}): {e}")
        return {}


def search_kakao_image_api_multi(query: str, count: int = 3) -> List[str]:
    """Kakao Image Search API (한 장소당 여러 장 이미지)"""
    url = "https://dapi.kakao.com/v2/search/image"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": query, "sort": "accuracy", "size": count}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        image_urls = [d.get('image_url') for d in data.get('documents', []) if d.get('image_url')]
        processed_urls = []
        for src in image_urls:
            if src and src.startswith('http'):
                if "//t1.daumcdn.net/" in src or "//img1.kakaocdn.net/" in src :
                    src = re.sub(r'\.q\d+', '', src)
                    src = re.sub(r'/[RC]\d+x\d+/', '/origin/', src)
                    src = re.sub(r'[RC]\d+x\d+', 'origin', src)
                processed_urls.append(src)
        return processed_urls[:count]
    except Exception as e:
        st.warning(f"Image API 요청 오류 ({query}): {e}")
        return []


# =========================================================
# ✨ 3. 유사도 및 핵심 키워드 기반 중복 판정 함수
# =========================================================
def get_core_keyword(place_name: str) -> str:
    """장소명에서 핵심 키워드(앞부분) 추출"""
    parts = place_name.split()
    if len(parts) > 1:
        common_suffixes = ["풋살장", "산책길", "입구", "주차장", "문화센터", "도서관", "미술관", "정문", "후문", "매표소", "놀이터"]
        # 마지막 단어가 시설명이고, 그 앞 단어가 있다면 앞부분을 핵심으로 간주
        if parts[-1] in common_suffixes and len(parts) > 1 :
             # 예: "서서울호수공원 풋살장" -> "서서울호수공원"
             # 예: "어린이대공원 정문" -> "어린이대공원"
            return " ".join(parts[:-1])
        # 또는 특정 키워드로 시작하면 그것을 핵심으로 (예: 카페 이름)
        # elif parts[0] in ["스타벅스", "투썸플레이스"]: return parts[0] + " " + parts[1] # "스타벅스 OO점"
    # 기본적으로는 첫 단어 또는 전체 이름 반환 (짧은 이름 대비)
    return parts[0] if len(parts) > 1 else place_name


def is_gps_close(new_place: Dict[str, Any], existing_place: Dict[str, Any], threshold: float) -> bool:
    """두 장소의 GPS 좌표가 가까운지 확인"""
    try:
        lat_diff = abs(float(new_place['GPS_위도']) - float(existing_place['GPS_위도']))
        lon_diff = abs(float(new_place['GPS_경도']) - float(existing_place['GPS_경도']))
        return lat_diff < threshold and lon_diff < threshold
    except (TypeError, ValueError, KeyError):
        return False # 좌표 정보 없으면 False

def is_duplicate_enhanced(new_place: Dict[str, Any], existing_places: List[Dict[str, Any]],
                          name_threshold: int = 85, core_name_threshold: int = 90,
                          address_threshold: int = 80, gps_threshold_similar: float = 0.0005, # 유사도용 GPS 기준 (약 50m)
                          gps_threshold_core: float = GPS_SIMILARITY_THRESHOLD ) -> bool: # 핵심 키워드용 GPS 기준 (약 100m)
    """강화된 중복 검사: 유사도 + 핵심 키워드 포함 여부"""

    new_core = get_core_keyword(new_place['장소명'])

    for existing_place in existing_places:
        # 1. 기본적인 유사도 검사 (이름/주소/GPS)
        if is_similar_place(new_place, existing_place, name_threshold, address_threshold, gps_threshold_similar):
            st.write(f"[중복제거(유사도)] '{new_place['장소명']}'는 '{existing_place['장소명']}'과(와) 유사 → 스킵")
            return True

        # 2. 핵심 키워드 포함 검사 (GPS 근접 시)
        existing_core = get_core_keyword(existing_place['장소명'])
        # GPS가 설정된 임계값(gps_threshold_core) 이내로 가까울 때만 핵심 키워드 검사 수행
        if is_gps_close(new_place, existing_place, gps_threshold_core):
            # 새 장소 이름에 기존 핵심 키워드가 포함되거나, 그 반대 경우 (더 엄격하게)
            # 그리고 두 핵심 키워드가 어느 정도 유사할 때 (완전히 다른 공원 이름 방지)
            core_sim = fuzz.token_set_ratio(new_core, existing_core)
            if (new_core in existing_place['장소명'] or existing_core in new_place['장소명']) and core_sim > 70: # 핵심 키워드 유사도 70점 이상
                st.write(f"[중복제거(핵심키워드)] '{new_place['장소명']}'는 '{existing_place['장소명']}'의 핵심('{existing_core}')과 관련 있고 가까움 → 스킵")
                return True

    return False # 모든 검사를 통과하면 중복 아님

# (is_similar_place 함수는 이전 코드와 동일하게 유지, 여기서 호출됨)
def is_similar_place(new_place: Dict[str, Any], existing_place: Dict[str, Any],
                     name_threshold: int, address_threshold: int, gps_threshold: float) -> bool:
    """이름(token_set_ratio), 주소(token_set_ratio), GPS 근접성을 기반으로 두 장소가 유사한지 판단"""

    if not all(k in new_place and new_place[k] is not None for k in ['장소명', 'GPS_위도', 'GPS_경도']) or \
       not all(k in existing_place and existing_place[k] is not None for k in ['장소명', 'GPS_위도', 'GPS_경도']):
        return False

    name_similarity = fuzz.token_set_ratio(new_place['장소명'], existing_place['장소명'])
    addr_similarity = 0
    if new_place.get('주소') and existing_place.get('주소'):
        addr_similarity = fuzz.token_set_ratio(str(new_place['주소']), str(existing_place['주소']))
    gps_close = is_gps_close(new_place, existing_place, gps_threshold)

    # 이름 유사도가 높고 (주소 유사도가 높거나 || GPS가 매우 가깝거나)
    if name_similarity >= name_threshold and (addr_similarity >= address_threshold or gps_close):
        return True
    return False


# =========================================================
# 4. API 기반 데이터 수집 함수 (강화된 중복 제거 적용)
# =========================================================
def crawl_api_data_with_images(keywords: List[str], max_api_pages: int) -> pd.DataFrame:
    all_data = [] # 최종 저장될, 중복 제거된 데이터
    total_bar = st.progress(0, text="전체 키워드 진행률")

    for i, keyword in enumerate(keywords):
        st.info(f"--- '{keyword}' 데이터 수집 시작 (API) ---")
        page = 1
        is_end = False
        processed_api_ids_this_keyword = set() # API 페이징 중복 방지

        while page <= max_api_pages and not is_end:
            # st.write(f"  > API 페이지 {page} 수집 중...") # 로그 간소화
            json_data = search_kakao_local_api(keyword, page)
            if not json_data: break

            documents = json_data.get('documents', [])
            is_end = json_data.get('meta', {}).get('is_end', True)
            if not documents: break

            for doc_index, doc in enumerate(documents):
                place_id = doc.get('id')
                if place_id in processed_api_ids_this_keyword: continue
                processed_api_ids_this_keyword.add(place_id)

                place_name = doc.get('place_name')
                address = doc.get('road_address_name') or doc.get('address_name')
                category_name = doc.get('category_name')
                latitude = doc.get('y')
                longitude = doc.get('x')

                if not place_name or not address or not latitude or not longitude:
                    st.warning(f"  -> 필수 정보 누락 스킵: {place_name}")
                    continue

                new_entry = {
                    '장소명': place_name.strip(),
                    '카테고리_RAW': category_name,
                    '주소': address.strip(),
                    'GPS_위도': float(latitude),
                    'GPS_경도': float(longitude),
                    'Kakao_Place_ID': place_id,
                    '크롤링_소스': 'KakaoAPI'
                }

                # ✨ 강화된 중복 체크 호출 ✨
                if is_duplicate_enhanced(new_entry, all_data):
                    continue # 중복이면 다음 장소로

                # 🔍 다중 이미지 검색 (중복이 아닐 경우에만 수행)
                try:
                    # 이미지 검색 시 '지역' 정보 추가하여 정확도 향상
                    region_hint = keyword.split()[0] if len(keyword.split()) > 1 else ""
                    search_query = f"{region_hint} {place_name}".strip()
                    image_urls = search_kakao_image_api_multi(search_query, count=MAX_IMAGES_PER_PLACE)
                    new_entry['image_urls'] = ", ".join(image_urls)
                except Exception as e:
                    st.warning(f"  -> {place_name} 이미지 검색 실패: {e}")
                    new_entry['image_urls'] = ""

                all_data.append(new_entry) # 최종 리스트에 추가

            page += 1
            time.sleep(0.3)

        total_bar.progress((i + 1) / len(keywords), text=f"키워드: {keyword} 수집 완료.")

    st.success(f"✅ 총 {len(all_data)}개 장소 수집 완료 (강화된 중복 제거 적용)")
    return pd.DataFrame(all_data)


# =========================================================
# 5. AI 테스트 이미지 다운로드 (ZIP 압축)
# =========================================================
def download_images_for_ai_test(df, total_goal):
    if 'image_urls' not in df.columns: return None, 0

    all_urls = []
    for urls_str in df['image_urls'].dropna().astype(str):
        urls_in_row = [url.strip() for url in urls_str.split(',') if url.strip().startswith('http')]
        all_urls.extend(urls_in_row)

    unique_urls = list(dict.fromkeys(all_urls))
    if not unique_urls: return None, 0

    urls_to_download = unique_urls[:total_goal]

    zip_buffer = io.BytesIO()
    download_count = 0
    headers = {
        'Referer': 'https://developers.kakao.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    }

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        progress_bar = st.progress(0, text=f"이미지 다운로드 중 (0/{len(urls_to_download)})")
        for i, url in enumerate(urls_to_download):
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()

                file_name = f"image_{i+1}.jpg" # 기본 파일명
                try:
                    mask = df['image_urls'].astype(str).str.contains(re.escape(url), na=False)
                    if mask.any():
                        row = df[mask].iloc[0]
                        category_part = str(row.get('카테고리_RAW', 'Unknown')).split('>')[-1].strip()
                        place_part = str(row.get('장소명', f'Place{i+1}'))
                        category = re.sub(r'[\\/*?:"<>|]', '', category_part)
                        place_name = re.sub(r'[\\/*?:"<>|]', '', place_part)
                        file_name = f"{category[:10]}_{place_name[:20]}_{i+1}.jpg"
                except Exception: pass

                zf.writestr(f"ai_test_images/{file_name}", response.content)
                download_count += 1
            except Exception as e:
                st.warning(f"  -> 다운로드 실패: {url[:50]} ({e})")

            progress_bar.progress((i + 1) / len(urls_to_download), text=f"이미지 다운로드 중 ({i+1}/{len(urls_to_download)})")

    progress_bar.empty()
    return zip_buffer, download_count


# =========================================================
# 6. Streamlit UI
# =========================================================
def app():
    st.set_page_config(page_title="카카오 API 크롤러", layout="wide")
    st.title("🗺️ 라이프 레코더: 카카오 API 데이터 크롤러")
    st.markdown("##### **API 기반 수집** + **강화된 유사도/핵심키워드 기반 중복 제거** 적용")
    st.success("✅ 이름/위치 유사 시 핵심 키워드가 같으면 하나로 처리 (예: 공원 내 다른 시설 중복 방지).")
    st.divider()

    if 'api_image_data' not in st.session_state:
        st.session_state.api_image_data = pd.DataFrame()

    # 1️⃣ 데이터 수집 설정
    st.header("1. 데이터 수집 설정")
    col1, col2 = st.columns(2)
    with col1: region_input = st.text_area("검색 지역", '\n'.join(TARGET_REGIONS), height=100)
    with col2: theme_input = st.text_area("검색 테마", '\n'.join(TARGET_THEMES), height=150)
    pages_input = st.number_input("키워드당 최대 API 페이지", 1, 15, MAX_API_PAGES)

    # 2️⃣ 수집 실행
    if st.button("🚀 API 데이터 수집 시작 (중복 제거 강화)"):
        st.session_state.api_image_data = pd.DataFrame()
        regions = [r.strip() for r in region_input.split('\n') if r.strip()]
        themes = [t.strip() for t in theme_input.split('\n') if t.strip()]
        keywords = [f"{r} {t}" for r in regions for t in themes]

        if not keywords: st.error("지역과 테마를 입력하세요."); return

        st.info(f"총 {len(keywords)}개 키워드로 API 수집 시작...")
        with st.spinner("API 호출 및 강화된 중복 제거 진행 중..."):
            final_df = crawl_api_data_with_images(keywords, pages_input)

        if final_df.empty:
            st.error("수집된 데이터가 없습니다.")
            st.session_state.api_image_data = pd.DataFrame()
            st.subheader("수집 데이터 미리보기")
            st.dataframe(st.session_state.api_image_data)
            return

        # --- 최종 데이터 처리 및 저장 ---
        original_count = len(final_df) # 강화된 유사도 필터 후 count

        # 최종 ID 중복 제거 (안전 장치)
        final_df['Kakao_Place_ID'] = final_df['Kakao_Place_ID'].astype(str).fillna('UNKNOWN_ID')
        final_df.drop_duplicates(subset=['Kakao_Place_ID'], keep='first', inplace=True)
        final_df = final_df[final_df['Kakao_Place_ID'] != 'UNKNOWN_ID'].reset_index(drop=True)
        final_dedup_count = len(final_df)

        final_df = final_df.astype(object).where(pd.notnull(final_df), None)
        st.session_state.api_image_data = final_df

        csv_filename = "kakao_api_places_final_dedup.csv" # 파일명 변경
        try:
            final_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            st.success(f"✅ 수집 성공! 유사도/핵심키워드 필터 후 {original_count}건, 최종 ID 중복 제거 후 {final_dedup_count}건 확보.")
            st.info(f"💾 데이터가 `{csv_filename}` 파일로 저장되었습니다.")
        except Exception as e_csv: st.error(f"CSV 저장 실패: {e_csv}")

        st.subheader(f"수집 데이터 미리보기 (최종 {final_dedup_count}건)")
        display_df = final_df.copy()
        if 'image_urls' in display_df.columns:
            display_df['image_urls_display'] = display_df['image_urls'].apply(
                lambda x: (str(x).split(',')[0].strip()[:40] + '...') if pd.notna(x) and str(x) else None
            )
            st.dataframe(display_df.drop(columns=['image_urls']))
        else:
            st.dataframe(display_df)

    st.divider()

    # 3️⃣ AI 테스트용 이미지 다운로드
    st.header("3. AI 모델 테스트 이미지 다운로드")
    if not st.session_state.api_image_data.empty:
        df_display = st.session_state.api_image_data
        total_unique_urls = 0
        if 'image_urls' in df_display.columns:
             all_urls_for_count = []
             for urls_str in df_display['image_urls'].dropna().astype(str):
                  urls_in_row = [url.strip() for url in urls_str.split(',') if url.strip().startswith('http')]
                  all_urls_for_count.extend(urls_in_row)
             total_unique_urls = len(list(dict.fromkeys(all_urls_for_count)))

        st.info(f"다운로드 가능한 이미지 URL: **{total_unique_urls}개**, 목표: {AI_TEST_IMAGE_COUNT}장")
        zip_buffer, downloaded_count = download_images_for_ai_test(df_display, AI_TEST_IMAGE_COUNT)

        if zip_buffer and downloaded_count > 0:
            st.download_button(
                label=f"✅ ai_test_images.zip 다운로드 ({downloaded_count}장 압축됨)",
                data=zip_buffer.getvalue(), file_name="ai_test_images.zip", mime="application/zip", key="download_button_final"
            )
        elif downloaded_count == 0 and total_unique_urls > 0: st.error("이미지 다운로드 실패. 로그 확인.")
        elif total_unique_urls == 0 : st.warning("크롤링된 데이터에 유효한 이미지 URL이 없습니다.")
        else: st.warning("다운로드 준비 중 오류.")
    else:
        st.warning("먼저 API 데이터 수집을 완료해주세요.")

if __name__ == '__main__':
    app()

