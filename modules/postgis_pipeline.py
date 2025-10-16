import pandas as pd
from geopy.geocoders import Kakao
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
import time
import os

# =========================================================
# ⚠️ 1. API 키 및 DB 정보 설정 (반드시 수정 필요)
# =========================================================

# 팀원에게 전달받은 Kakao REST API 키를 여기에 입력하세요.
KAKAO_API_KEY = "c2c5289d7f9ea5cfa234222f18883527"

# DB 접속 URL 설정
# 형식: "postgresql+psycopg2://[유저]:[비밀번호]@[호스트]:[포트]/[DB이름]"
# 유저: postgres, 호스트: localhost, 포트: 5432, DB이름: life_recorder_db
DB_URL = "postgresql+psycopg2://postgres:san3su1@localhost:3103/Life_Recoder_db"

# =========================================================
# 2. Geocoding 함수 정의 (주소 -> 좌표 변환)
# =========================================================

geolocator = Kakao(api_key=KAKAO_API_KEY)

def geocode_address(address):
    """주소를 받아 위도와 경도 좌표를 반환하는 함수"""
    try:
        # API 호출 횟수 제한 방지를 위해 딜레이를 줍니다.
        time.sleep(0.1) 
        
        # Geocoding API 호출
        location = geolocator.geocode(address, timeout=5)
        
        if location:
            # 성공 시 위도(latitude)와 경도(longitude) 반환
            return location.latitude, location.longitude
        else:
            # 주소를 찾을 수 없는 경우 None 반환
            return None, None
            
    except Exception as e:
        # API 오류 (타임아웃, 네트워크 등) 발생 시 오류 메시지 출력
        print(f"Error geocoding {address}: {e}")
        return None, None

# =========================================================
# 3. 데이터 로드 및 전처리 (CSV 파일 로드)
# =========================================================

def load_crawled_data():
    """
    Streamlit 크롤러가 생성한 CSV 파일에서 데이터를 로드하는 함수.
    """
    file_path = 'kakao_map_places_raw.csv'  # Streamlit 앱에서 저장한 파일명
    
    if os.path.exists(file_path):
        print(f"CSV 파일 '{file_path}'에서 데이터 로드 중...")
        raw_df = pd.read_csv(file_path)
        
        # 주소, 장소명, 카테고리가 필수적으로 존재하는지 확인
        required_cols = ['장소명', '카테고리', '주소']
        if not all(col in raw_df.columns for col in required_cols):
             print(f"경고: 필수 컬럼({required_cols})이 CSV에 부족합니다.")
             return pd.DataFrame()
             
        return raw_df
    else:
        print(f"❌ 오류: 크롤링된 CSV 파일 '{file_path}'을 찾을 수 없습니다.")
        print("Streamlit 앱을 실행하여 CSV 파일을 생성하거나 경로를 확인하세요.")
        return pd.DataFrame()

# =========================================================
# 4. PostGIS 적재 및 공간 인덱스 생성
# =========================================================

def save_to_postgis(df, table_name='recommendation_spots'):
    """DataFrame을 PostGIS 테이블에 적재하고 공간 인덱스를 생성하는 함수"""
    try:
        print(f"Connecting to database: {DB_URL.split('@')[-1]}")
        # SQLAlchemy 엔진 생성
        engine = create_engine(DB_URL)
        
        # GPS 좌표가 없는 데이터는 건너뛰거나 따로 처리
        df_clean = df.dropna(subset=['GPS_위도', 'GPS_경도'])
        
        if df_clean.empty:
            print("❌ 적재할 유효한 GPS 좌표 데이터가 없습니다. Geocoding 실패율을 확인하세요.")
            return

        # 1. 일반 데이터를 PostgreSQL 테이블에 적재
        print(f"-> 일반 데이터 {len(df_clean)}건 테이블 '{table_name}'에 적재 시작...")
        # 'if_exists' 옵션을 'replace'로 설정하여 실행할 때마다 테이블을 새로 만듭니다.
        df_clean.to_sql(table_name, engine, if_exists='replace', index=False)
        print("-> 일반 데이터 적재 완료.")
        
        # 2. PostGIS 공간 인덱스 및 geom 컬럼 생성 (SQL 실행)
        with engine.connect() as connection:
            # PostGIS 확장 활성화 (안전을 위해 다시 실행 가능)
            connection.execute(
                "CREATE EXTENSION IF NOT EXISTS postgis;"
            )
            # geometry 컬럼 생성 (위도/경도를 공간 데이터 형식으로 변환)
            # ST_MakePoint(경도, 위도)를 사용하며, SRID 4326(GPS 표준)을 지정합니다.
            connection.execute(
                f"""
                ALTER TABLE {table_name} ADD COLUMN geom geometry(Point, 4326);
                UPDATE {table_name} SET geom = ST_SetSRID(ST_MakePoint("GPS_경도", "GPS_위도"), 4326);
                """
            )
            # GIST 공간 인덱스 생성 (검색 속도 최적화)
            connection.execute(
                f"CREATE INDEX {table_name}_geom_idx ON {table_name} USING GIST (geom);"
            )
            connection.commit()
            print(f"✅ PostGIS geom 컬럼 및 GIST 공간 인덱스 생성 완료.")
            print(f"테이블 '{table_name}'에 최종 데이터 적재 성공.")

    except SQLAlchemyError as e:
        print(f"\n\n🚨 데이터베이스 연결/적재 오류 발생 🚨")
        print(f"오류 상세: {e}")
        print("DB_URL, 비밀번호, 포트 번호, life_recorder_db 이름이 정확한지 확인하세요.")
    except Exception as e:
        print(f"예상치 못한 오류 발생: {e}")

# =========================================================
# 5. 메인 실행 파이프라인
# =========================================================

if __name__ == '__main__':
    # 1. 크롤링 데이터 로드
    raw_df = load_crawled_data()
    
    if raw_df.empty:
        print("로드된 크롤링 데이터가 없습니다. 작업을 종료합니다.")
    else:
        print(f"총 {len(raw_df)}건의 크롤링 데이터 로드 완료.")
        
        # 2. Geocoding 수행
        print("--- Geocoding (주소 -> 좌표) 시작 ---")
        # apply를 사용하여 모든 주소에 대해 geocode_address 함수 실행
        raw_df[['GPS_위도', 'GPS_경도']] = raw_df['주소'].apply(
            lambda x: pd.Series(geocode_address(x))
        )
        print("--- Geocoding 완료 ---")
        
        # 3. PostGIS 적재
        save_to_postgis(raw_df)
