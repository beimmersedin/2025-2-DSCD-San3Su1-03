import streamlit as st
import pandas as pd
from modules.exif_pipeline import extract_exif_df
from modules.route_builder import build_route_geojson
from core.db import engine
import pydeck as pdk

st.title("01 · Route Visualization")

files = st.file_uploader("Upload photos", type=["jpg","jpeg","png"], accept_multiple_files=True)
if files:
    df = extract_exif_df(files)                 # taken_at, lat, lon ...
    route_gj, stops_df = build_route_geojson(df) # GeoJSON line + stops

    # 저장 (예시)
    df.to_sql("photo_tmp", engine, if_exists="replace", index=False)

    # 시각화
    st.map(df.rename(columns={"lat":"latitude","lon":"longitude"}))  # quick preview
    st.subheader("Route")
    st.pydeck_chart(pdk.Deck(
        initial_view_state=pdk.ViewState(latitude=df.lat.mean(), longitude=df.lon.mean(), zoom=11),
        layers=[]
    ))
