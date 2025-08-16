import streamlit as st
import folium
from streamlit_folium import st_folium
import requests

st.set_page_config(page_title="Free Maps Clone", layout="wide")
st.title("🗺️ Free Google Maps Clone")

# Sidebar for user input
st.sidebar.header("Search & Directions")
start_address = st.sidebar.text_input("Start Address", "San Francisco")
end_address = st.sidebar.text_input("Destination Address", "Los Angeles")

if st.sidebar.button("Find Route"):
    
    # Step 1: Geocode addresses using Nominatim
    def geocode(address):
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json"}
        r = requests.get(url, params=params)
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        return None

    start_coords = geocode(start_address)
    end_coords = geocode(end_address)

    if start_coords and end_coords:
        # Step 2: Get route from OSRM demo server
        route_url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson"
        res = requests.get(route_url).json()

        coords = res["routes"][0]["geometry"]["coordinates"]
        distance_km = res["routes"][0]["distance"] / 1000
        duration_min = res["routes"][0]["duration"] / 60

        st.success(f"Distance: {distance_km:.2f} km | Duration: {duration_min:.1f} min")

        # Step 3: Show map
        m = folium.Map(location=start_coords, zoom_start=6)
        folium.Marker(start_coords, popup="Start", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(end_coords, popup="End", icon=folium.Icon(color="red")).add_to(m)

        folium.PolyLine([(lat, lon) for lon, lat in coords], color="blue", weight=5).add_to(m)

        st_folium(m, width=900, height=600)

    else:
        st.error("Could not geocode one of the addresses.")
else:
    st.info("Enter addresses in the sidebar to search and get directions.")
