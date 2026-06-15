import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests 
import json
import os
from datetime import datetime

st.set_page_config(
    page_title="Nova Maps",
    page_icon=" 📍 ",
    layout="wide",
    initial_sidebar_state="expanded",
)

TOMTOM_API_KEY = st.secrets.get("TOMTOM_API_KEY", os.getenv("TOMTOM_API_KEY", ""))
ORS_API_KEY    = st.secrets.get("ORS_API_KEY",    os.getenv("ORS_API_KEY"     ""))
