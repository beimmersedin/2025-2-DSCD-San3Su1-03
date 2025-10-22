import os
import time
import bcrypt
import streamlit as st
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

# ---------------------------------------------------------
# 0) DB 접속 정보 불러오기 (secrets 우선, 없으면 환경변수 사용)
# ---------------------------------------------------------
def get_db_url():
    if "postgres" in st.secrets:
        cfg = st.secrets["postgres"]
        host = cfg.get("host")
        port = cfg.get("port", 5432)
        user = cfg.get("user")
        password = cfg.get("password")
        database = cfg.get("database")
    else:
        load_dotenv()
        host = os.getenv("PGHOST")
        port = os.getenv("PGPORT", "5432")
        user = os.getenv("PGUSER")
        password = os.getenv("PGPASSWORD")
        database = os.getenv("PGDATABASE")

    assert all([host, port, user, password, database]), "DB 접속정보가 없습니다."
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

@st.cache_resource
def get_engine():
    engine = create_engine(get_db_url(), pool_pre_ping=True)
    # 연결 확인
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine

# ---------------------------------------------------------
# 1) 초기 스키마 생성 (users 테이블)
# ---------------------------------------------------------
def ensure_schema(engine):
    create_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_sql))

# ---------------------------------------------------------
# 2) 회원가입/로그인 비즈니스 로직
# ---------------------------------------------------------
def hash_password(plain: str) -> str:
    # bcrypt는 내부적으로 솔트를 포함 → 같은 비번도 매번 다른 해시
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_user(engine, email: str, password: str) -> bool:
    if not email or not password:
        raise ValueError("이메일/비밀번호는 비어 있을 수 없습니다.")
    pwd_hash = hash_password(password)
    sql = "INSERT INTO users (email, password_hash) VALUES (:email, :pwd)"
    try:
        with engine.begin() as conn:
            conn.execute(text(sql), {"email": email.lower().strip(), "pwd": pwd_hash})
        return True
    except IntegrityError:
        # UNIQUE(email) 위반
        return False

def get_user_by_email(engine, email: str):
    sql = "SELECT id, email, password_hash, created_at FROM users WHERE email = :email"
    with engine.begin() as conn:
        row = conn.execute(text(sql), {"email": email.lower().strip()}).fetchone()
        return dict(row._mapping) if row else None

# ---------------------------------------------------------
# 3) 간단한 세션 관리
# ---------------------------------------------------------
def login_user(user_dict: dict):
    st.session_state["auth"] = {
        "user_id": user_dict["id"],
        "email": user_dict["email"],
        "login_at": datetime.utcnow().isoformat()
    }

def logout_user():
    st.session_state.pop("auth", None)

def is_logged_in():
    return "auth" in st.session_state

# ---------------------------------------------------------
# 4) UI
# ---------------------------------------------------------
st.set_page_config(page_title="Life-Recorder Demo", page_icon="📍", layout="centered")
st.title("📍Life Recorder (Streamlit + PostgreSQL)📍")

engine = get_engine()
ensure_schema(engine)

tab_login, tab_signup, tab_profile = st.tabs(["로그인", "회원가입", "내 정보"])

with tab_signup:
    st.subheader("회원가입")
    with st.form("signup_form", clear_on_submit=False):
        new_email = st.text_input("이메일", placeholder="you@example.com")
        new_pw = st.text_input("비밀번호", type="password")
        new_pw2 = st.text_input("비밀번호 확인", type="password")
        submitted = st.form_submit_button("회원가입")

    if submitted:
        if new_pw != new_pw2:
            st.error("비밀번호 확인이 일치하지 않습니다.")
        elif len(new_pw) < 8:
            st.error("비밀번호는 8자 이상을 권장합니다.")
        else:
            ok = create_user(engine, new_email, new_pw)
            if ok:
                st.success("회원가입 완료! 이제 로그인 탭에서 로그인하세요.")
            else:
                st.warning("이미 가입된 이메일입니다.")

with tab_login:
    st.subheader("로그인")
    if is_logged_in():
        st.info(f"이미 로그인됨: {st.session_state['auth']['email']}")
        if st.button("로그아웃"):
            logout_user()
            st.success("로그아웃 되었습니다.")
            st.rerun()
    else:
        with st.form("login_form"):
            email = st.text_input("이메일", placeholder="you@example.com", key="login_email")
            pw = st.text_input("비밀번호", type="password", key="login_pw")
            remember = st.checkbox("로그인 유지 (브라우저 세션 동안)")
            submitted = st.form_submit_button("로그인")
        if submitted:
            user = get_user_by_email(engine, email)
            if not user:
                st.error("존재하지 않는 이메일입니다.")
            elif not verify_password(pw, user["password_hash"]):
                st.error("비밀번호가 올바르지 않습니다.")
            else:
                login_user(user)
                st.success("로그인 성공!")
                # 간단한 UX: 성공 후 살짝 대기 → rerun
                time.sleep(0.5)
                st.rerun()

with tab_profile:
    st.subheader("내 정보")
    if not is_logged_in():
        st.warning("로그인이 필요합니다.")
    else:
        auth = st.session_state["auth"]
        st.write(f"**이메일**: {auth['email']}")
        # 실제 서비스라면 여기에 프로필 수정, 비밀번호 변경 로직 등을 추가
        if st.button("로그아웃", key="logout_btn2"):
            logout_user()
            st.success("로그아웃 되었습니다.")
            st.rerun()
