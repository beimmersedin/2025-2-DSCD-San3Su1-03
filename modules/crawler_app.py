import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
import time

# =========================================================
# ⚠️ 1. 설정 정보
# =========================================================

TARGET_KEYWORDS = [
    "서울 한옥카페", 
    "제주 오름 명소", 
    "부산 오션뷰 카페", 
    "경주 문화 유적지"
]

MAX_PAGES_PER_KEYWORD = 3 

# =========================================================
# 2. WebDriver 설정 및 초기화 함수 (Headless)
# =========================================================
def create_chrome_driver():
    """
    WebDriver를 설정하고 반환합니다. 키워드별로 새로운 드라이버를 사용합니다.
    """
    chrome_options = Options()
    
    # 🚨 Headless 모드 설정
    chrome_options.add_argument("--headless")
    
    # 서버 환경 및 오류 방지를 위한 필수 옵션들
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--disable-popup-blocking") 

    # 드라이버 자동 관리 및 설치
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    
    return webdriver.Chrome(service=service, options=chrome_options)

# =========================================================
# 3. 크롤링 핵심 함수
# =========================================================

def crawl_kakao_map(keyword, max_pages, driver):
    """특정 키워드로 카카오맵을 검색하여 장소 데이터 수집"""
    
    base_url = "https://map.kakao.com/"
    driver.get(base_url)
    
    st.info(f"--- '{keyword}' 데이터 크롤링 시작 ---")
    place_list = []
    
    try:
        # 1. 검색창 로드 대기 및 키워드 입력 (***수정된 부분***)
        # 검색창이 클릭 가능한 상태가 될 때까지 기다립니다.
        search_box = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "search.keyword.query"))
        )
        
        search_box.clear() # 이전 키워드가 남아있을 경우를 대비해 검색창을 비웁니다.
        search_box.send_keys(keyword)
        time.sleep(1) # 입력 후 짧은 딜레이 추가 (안정성 강화)
        
        # 2. 검색 버튼 클릭 로직
        try:
            # 검색 버튼이 클릭 가능한 상태가 될 때까지 최대 10초 대기
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "search.keyword.submit"))
            )
            search_button.click() #클릭
            
        except TimeoutException:
            st.error("검색 버튼을 클릭 가능한 상태로 찾지 못했습니다. 페이지 구조를 확인하세요.")
            return pd.DataFrame()
        except ElementClickInterceptedException:
            st.warning("경고: 클릭이 가로막혔습니다. (새로운 기능 안내 등) 1초 대기 후 JavaScript로 재시도합니다.")
            time.sleep(1)
            # JavaScript를 이용해 강제 클릭
            driver.execute_script("document.getElementById('search.keyword.submit').click();")
            
        except NoSuchElementException as e:
            st.error(f"검색 버튼을 찾지 못했습니다: {e}")
            return pd.DataFrame() 
        
        # 3. 검색 결과 목록 로드 대기 (강화)
        # 검색 결과가 'info.search.place.list' 내에 실제로 나타날 때까지 기다립니다.
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#info\\.search\\.place\\.list > li:nth-child(1)"))
        )
        time.sleep(3) # 안정화 딜레이
        
        # --- 크롤링 루프 시작 ---
        page = 1
        while page <= max_pages:
            st.write(f"  > 페이지 {page} 수집 중...")
            time.sleep(1) 
            
            # 모든 장소 아이템을 가져옵니다.
            place_items = driver.find_elements(By.CSS_SELECTOR, "#info\.search\.place\.list > li")

            if not place_items:
                st.warning("    -> 더 이상 장소 항목이 없습니다. 크롤링 종료.")
                break

            for item in place_items:
                try:
                    # 장소명
                    name_elem = item.find_element(By.CSS_SELECTOR, ".head_item .tit_name")
                    place_name = name_elem.text
                    
                    # 주소
                    address_elem = item.find_element(By.CSS_SELECTOR, ".addr p:nth-child(1)")
                    address = address_elem.text
                    
                    place_list.append({
                        '장소명': place_name,
                        '카테고리': keyword, 
                        '주소': address,
                        '크롤링_소스': 'KakaoMap'
                    })
                except NoSuchElementException:
                    continue
            
            # 다음 페이지로 이동
            if page < max_pages:
                try:
                    # 페이지 번호 버튼 클릭 로직
                    next_page_xpath = f'//a[text()="{page + 1}"]'
                    
                    if page % 5 == 0:
                        next_btn = driver.find_element(By.XPATH, '//a[@id="info.search.page.next"]')
                    else:
                        next_btn = driver.find_element(By.XPATH, next_page_xpath)

                    next_btn.click()
                    time.sleep(2) # 페이지 이동 후 로딩 대기
                    page += 1
                except NoSuchElementException:
                    st.warning("    -> 다음 페이지 버튼이 없습니다. 크롤링 종료.")
                    break
            else:
                break

    except Exception as e:
        # 키워드 처리 중 최종적으로 잡는 오류 (모든 키워드에 대해 크롤링을 완료하기 위함)
        st.error(f"❌ 크롤링 중 치명적인 오류 발생: {e}")
        
    return pd.DataFrame(place_list)


# =========================================================
# 4. Streamlit UI
# =========================================================
def app():
    st.set_page_config(page_title="장소 데이터 크롤링 도구", layout="wide")
    st.title("라이프 레코더: 장소 데이터 크롤러")
    st.markdown("##### 맞춤형 추천 시스템 구축을 위한 카카오맵 데이터 수집 파이프라인")
    
    st.divider()

    # --- 입력 설정 ---
    keyword_input = st.text_area(
        "크롤링할 키워드 목록 (줄바꿈으로 구분)", 
        value='\n'.join(TARGET_KEYWORDS)
    )
    pages_input = st.number_input(
        "키워드당 최대 페이지 수 (페이지당 약 15개 장소)", 
        min_value=1, 
        value=MAX_PAGES_PER_KEYWORD
    )

    # --- 크롤링 실행 버튼 ---
    if st.button(" 크롤링 시작 및 데이터 수집"):
        
        # 1. 키워드 정리
        keywords = [k.strip() for k in keyword_input.split('\n') if k.strip()]
        if not keywords:
            st.error("크롤링할 키워드를 입력해 주세요.")
            return

        # 2. 크롤링 실행
        all_data = []
        total_bar = st.progress(0, text="전체 크롤링 진행률")
        
        for i, keyword in enumerate(keywords):
            # 키워드별로 드라이버 새로 생성
            with st.spinner(f"키워드 '{keyword}'를 위해 드라이버를 준비 중입니다..."):
                try:
                    driver = create_chrome_driver()
                except Exception as e:
                    st.error(f"웹 드라이버 초기화 실패: {e}. Chrome 버전과 호환성을 확인하세요.")
                    continue

            total_bar.progress((i) / len(keywords), text=f"키워드: {keyword} 수집 중...")
            
            # 크롤링 함수 실행
            df_tag = crawl_kakao_map(keyword, pages_input, driver)
            all_data.append(df_tag)
            
            # 드라이버 세션 종료 (리소스 해제)
            driver.quit() 
            
            total_bar.progress((i + 1) / len(keywords), text=f"키워드: {keyword} 수집 완료.")
        
        # 3. 결과 정리 및 출력
        if all_data:
            final_crawled_df = pd.concat(all_data, ignore_index=True)
            final_crawled_df.drop_duplicates(subset=['장소명', '주소'], inplace=True)
            
            st.success(f"크롤링 성공! 총 {len(final_crawled_df)}개의 유효 장소 데이터가 수집되었습니다.")
            
            # 4. 데이터 표시
            st.subheader("수집된 장소 데이터 미리보기")
            st.dataframe(final_crawled_df)
            
            # 5. 다음 단계 안내
            st.markdown(
                """
                ---
                ### 다음 단계: Geocoding 및 PostGIS 적재
                수집된 이 데이터(장소명, 주소)를 활용하여 다음 단계인 **Kakao Geocoding API**를 이용해 좌표를 추출하고 **PostGIS DB에 적재**해야 합니다. 
                """
            )
        else:
            st.warning("수집된 데이터가 없습니다. 키워드나 페이지 오류를 확인하세요.")
            
if __name__ == '__main__':
    app()
