import streamlit as st
import folium
from streamlit_folium import st_folium
import requests

# --- Page setup ---
st.set_page_config(page_title="Nova Maps", layout="wide")
st.title("📍Nova Maps – Better Than Google Maps")

# --- Sidebar controls ---
st.sidebar.header("Search & Directions")
start_address = st.sidebar.text_input("Start Address", "1600 Amphitheatre Parkway, Mountain View, CA")
end_address = st.sidebar.text_input("Destination Address", "1 Infinite Loop, Cupertino, CA")
mode = st.sidebar.selectbox("Travel Mode", ["driving", "walking", "cycling"])
unit = st.sidebar.selectbox("Distance Unit", ["Kilometers", "Miles"])

# --- Geocode function ---
def geocode(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "addressdetails": 1, "accept-language": "en"}
    headers = {"User-Agent": "NovaMaps/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        st.error(f"Could not geocode '{address}'")
    return None

# --- Initialize session state ---
if "route_data" not in st.session_state:
    st.session_state.route_data = None

# --- Find Route Button ---
if st.sidebar.button("Find Route"):
    start_coords = geocode(start_address)
    end_coords = geocode(end_address)
    if start_coords and end_coords:
        try:
            route_url = f"http://router.project-osrm.org/route/v1/{mode}/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson"
            res = requests.get(route_url, timeout=10).json()
            coords = res["routes"][0]["geometry"]["coordinates"]
            distance_km = res["routes"][0]["distance"] / 1000
            duration_min = res["routes"][0]["duration"] / 60
            st.session_state.route_data = {
                "start_coords": start_coords,
                "end_coords": end_coords,
                "coords": coords,
                "distance_km": distance_km,
                "duration_min": duration_min,
                "mode": mode
            }
        except:
            st.error("Error fetching route from OSRM")
    else:
        st.error("Could not geocode one of the addresses")

# --- Display Map ---
with st.container():
    if st.session_state.route_data:
        rd = st.session_state.route_data

        # Distance conversion
        if unit == "Miles":
            distance = rd["distance_km"] * 0.621371
            distance_label = "mi"
        else:
            distance = rd["distance_km"]
            distance_label = "km"

        st.sidebar.success(
            f"Mode: {rd['mode'].capitalize()}\nDistance: {distance:.2f} {distance_label}\nDuration: {rd['duration_min']:.1f} min"
        )

        # --- Map with English tiles ---
        m = folium.Map(
            location=rd["start_coords"],
            zoom_start=14,
            tiles="https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
            attr='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
        )

        folium.Marker(rd["start_coords"], popup="Start", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(rd["end_coords"], popup="End", icon=folium.Icon(color="red")).add_to(m)
        folium.PolyLine([(lat, lon) for lon, lat in rd["coords"]], color="blue", weight=5).add_to(m)
        folium.CircleMarker(location=rd["start_coords"], radius=5, color="blue", fill=True, fill_color="blue", popup="Current Location").add_to(m)

        # Display full-width map
        st_folium(m, width=1200, height=700, use_container_width=True)

    else:
        # Default world map if no route
        m = folium.Map(
            location=[37.422, -122.084],
            zoom_start=5,
            tiles="https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
            attr='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
        )
        st_folium(m, width=1200, height=700, use_container_width=True)
