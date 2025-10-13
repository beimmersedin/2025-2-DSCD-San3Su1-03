CREATE EXTENSION IF NOT EXISTS postgis;

-- 앨범/사진
CREATE TABLE IF NOT EXISTS album(
  id SERIAL PRIMARY KEY,
  title TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS photo(
  id SERIAL PRIMARY KEY,
  album_id INT REFERENCES album(id),
  taken_at TIMESTAMP,
  device TEXT,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  geom GEOGRAPHY(POINT),       -- PostGIS
  url TEXT                      -- S3 or local path
);

-- 경로(라인) & 정차(포인트)
CREATE TABLE IF NOT EXISTS route(
  id SERIAL PRIMARY KEY,
  album_id INT REFERENCES album(id),
  geom GEOGRAPHY(LINESTRING),
  length_km DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS stop(
  id SERIAL PRIMARY KEY,
  album_id INT REFERENCES album(id),
  geom GEOGRAPHY(POINT),
  dwell_min INT
);

-- 요약/캡션/추천
CREATE TABLE IF NOT EXISTS summary(
  id SERIAL PRIMARY KEY,
  album_id INT REFERENCES album(id),
  episode_idx INT,
  text TEXT,
  caption TEXT
);

CREATE TABLE IF NOT EXISTS recommendation(
  id SERIAL PRIMARY KEY,
  album_id INT REFERENCES album(id),
  place_name TEXT,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  reason TEXT
);
