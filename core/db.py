from sqlalchemy import create_engine, text
from core.settings import settings

url = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
engine = create_engine(url, pool_pre_ping=True)

def healthcheck():
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar()
