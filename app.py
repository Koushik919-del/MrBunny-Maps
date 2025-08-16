import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="GPS Website", layout="wide")
st.title("🌍 My GPS Website (Google Maps style)")

# Make a folium map (default location if GPS not yet available)
m = folium.Map(location=[20, 0], zoom_start=2)

# Add a little JS script that requests GPS
gps_js = """
<script>
navigator.geolocation.getCurrentPosition(
  function(position) {
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;
    window.parent.postMessage({lat: lat, lon: lon}, "*");
  },
  function(error) {
    console.log("Error: " + error.message);
  }
);
</script>
"""

# Add HTML with GPS JS
m.get_root().html.add_child(folium.Element(gps_js))

# Show the map
output = st_folium(m, width=800, height=500)

# Listen for GPS values
if output and "last_object_clicked" in output and output["last_object_clicked"]:
    st.write("📍 You clicked:", output["last_object_clicked"])
