# core/db.py
import os
from sqlalchemy import create_engine, text

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        assert url, "DATABASE_URL 미설정"
        _engine = create_engine(url, pool_pre_ping=True)
        with _engine.connect() as c:
            c.execute(text("SELECT 1"))
    return _engine

def insert_photo_record(user_id, bucket, key, content_type, size, taken_at=None, lon=None, lat=None):
    sql = """
    INSERT INTO photos (user_id, s3_bucket, s3_key, content_type, byte_size, taken_at, gps)
    VALUES (:uid, :bucket, :key, :ct, :size, :taken_at,
            CASE WHEN :lon IS NULL OR :lat IS NULL THEN NULL
                 ELSE ST_GeogFromText('POINT(' || :lon || ' ' || :lat || ')') END)
    RETURNING id;
    """
    eng = get_engine()
    with eng.begin() as conn:
        return conn.execute(text(sql), {
            "uid": user_id,
            "bucket": bucket,
            "key": key,
            "ct": content_type,
            "size": size,
            "taken_at": taken_at,
            "lon": lon, "lat": lat
        }).scalar()
