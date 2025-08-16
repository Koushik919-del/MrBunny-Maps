import streamlit as st
import folium
from streamlit_folium import st_folium
import requests

st.set_page_config(page_title="Free Maps Clone", layout="wide")
st.title("🗺️ Free Google Maps Clone")

# Sidebar input
st.sidebar.header("Search & Directions")
start_address = st.sidebar.text_input("Start Address", "San Francisco")
end_address = st.sidebar.text_input("Destination Address", "Los Angeles")

def geocode(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json"}
    headers = {"User-Agent": "MyFreeMapsApp/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except requests.RequestException:
        st.error(f"Network error while geocoding '{address}'.")
    except ValueError:
        st.error(f"Error decoding geocoding response for '{address}'.")
    return None

# Initialize session state
if "route_data" not in st.session_state:
    st.session_state.route_data = None

if st.sidebar.button("Find Route"):
    start_coords = geocode(start_address)
    end_coords = geocode(end_address)
    if start_coords and end_coords:
        route_url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson"
        try:
            res = requests.get(route_url, timeout=10).json()
            coords = res["routes"][0]["geometry"]["coordinates"]
            distance_km = res["routes"][0]["distance"] / 1000
            duration_min = res["routes"][0]["duration"] / 60

            # Save route in session_state
            st.session_state.route_data = {
                "start_coords": start_coords,
                "end_coords": end_coords,
                "coords": coords,
                "distance": distance_km,
                "duration": duration_min
            }
        except Exception:
            st.error("Error fetching route from OSRM. Please try again.")
    else:
        st.error("Could not geocode one of the addresses.")

# Display route if it exists
if st.session_state.route_data:
    rd = st.session_state.route_data
    st.success(f"Distance: {rd['distance']:.2f} km | Duration: {rd['duration']:.1f} min")

    m = folium.Map(location=rd["start_coords"], zoom_start=6)
    folium.Marker(rd["start_coords"], popup="Start", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(rd["end_coords"], popup="End", icon=folium.Icon(color="red")).add_to(m)
    folium.PolyLine([(lat, lon) for lon, lat in rd["coords"]], color="blue", weight=5).add_to(m)

    st_folium(m, width=900, height=600)
else:
    st.info("Enter addresses in the sidebar and click 'Find Route'.")
