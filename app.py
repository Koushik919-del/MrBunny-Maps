import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="GPS Website", layout="wide")

st.title("🌍 My GPS Website")

# Ask browser for location
location = streamlit_js_eval(
    js_expressions="navigator.geolocation.getCurrentPosition(pos => ({lat: pos.coords.latitude, lon: pos.coords.longitude}))",
    key="getLocation",
)

if location is None:
    st.info("📍 Please allow location access in your browser.")
else:
    lat = location["lat"]
    lon = location["lon"]

    st.success(f"Your Location: {lat}, {lon}")

    # Create map with Folium
    m = folium.Map(location=[lat, lon], zoom_start=15)
    folium.Marker([lat, lon], popup="You are here!").add_to(m)

    # Display map
    st_folium(m, width=700, height=500)
