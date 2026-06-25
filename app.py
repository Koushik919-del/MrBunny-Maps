import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim, Photon
from geopy.extra.rate_limiter import RateLimiter
from geopy.distance import geodesic
import requests
import json
import os
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nova Maps",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── API Keys ──────────────────────────────────────────────────────────────────
TOMTOM_API_KEY = st.secrets.get("TOMTOM_API_KEY", os.getenv("TOMTOM_API_KEY", ""))
ORS_API_KEY    = st.secrets.get("ORS_API_KEY",    os.getenv("ORS_API_KEY",    "" ))
STADIA_API_KEY = st.secrets.get("STADIA_API_KEY", os.getenv("STADIA_API_KEY", ""))

# ── Geocoder ──────────────────────────────────────────────────────────────────
geolocator = Nominatim(user_agent="nova-maps-app (contact: your-email@example.com)")
geocode_with_limit = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1,      # Nominatim policy: max 1 request/sec
    max_retries=2,
    error_wait_seconds=2.0,
    swallow_exceptions=False,
)

# Fallback geocoder — used automatically if Nominatim is rate-limited or
# temporarily blocking this IP (403). Different infrastructure, no API key needed.
photon_geolocator = Photon(user_agent="nova-maps-app (contact: your-email@example.com)")
photon_geocode_with_limit = RateLimiter(
    photon_geolocator.geocode,
    min_delay_seconds=1,
    max_retries=1,
    error_wait_seconds=2.0,
    swallow_exceptions=False,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def geocode(address: str):
    """Return (lat, lon, display_name) or None. Falls back to Photon if Nominatim is blocked/rate-limited."""
    try:
        loc = geocode_with_limit(address, timeout=10)
        if loc:
            return loc.latitude, loc.longitude, loc.address
        return None  # Nominatim responded but found nothing — don't fall back, it's a genuine no-match
    except Exception as e:
        if "403" in str(e) or "429" in str(e):
            st.caption("Primary geocoder is rate-limited — trying a fallback…")
            try:
                loc = photon_geocode_with_limit(address, timeout=10)
                if loc:
                    return loc.latitude, loc.longitude, loc.address
                return None
            except Exception as e2:
                st.error(f"Both geocoders failed. Primary: rate-limited. Fallback error: {e2}")
                return None
        else:
            st.error(f"Geocoding error: {e}")
            return None

def get_route(origin_coords, dest_coords, mode="car"):
    """Get route from OpenRouteService."""
    if not ORS_API_KEY:
        # Fallback: straight line
        return None, None
    profile_map = {"car": "driving-car", "walk": "foot-walking", "bike": "cycling-regular"}
    profile = profile_map.get(mode, "driving-car")
    url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [[origin_coords[1], origin_coords[0]], [dest_coords[1], dest_coords[0]]]}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        feature = data["features"][0]
        coords = [(c[1], c[0]) for c in feature["geometry"]["coordinates"]]
        summary = feature["properties"]["summary"]
        dist_km = round(summary["distance"] / 1000, 2)
        dur_min = round(summary["duration"] / 60, 1)
        return coords, {"distance_km": dist_km, "duration_min": dur_min}
    except Exception as e:
        st.warning(f"Routing error: {e}")
        return None, None

def get_traffic_flow(lat: float, lon: float):
    """Get real-time traffic flow from TomTom."""
    if not TOMTOM_API_KEY:
        return None
    url = (
        f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        f"?point={lat},{lon}&key={TOMTOM_API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        d = r.json().get("flowSegmentData", {})
        return {
            "current_speed":   d.get("currentSpeed", "N/A"),
            "free_flow_speed": d.get("freeFlowSpeed", "N/A"),
            "confidence":      d.get("confidence", "N/A"),
            "road_closure":    d.get("roadClosure", False),
        }
    except Exception:
        return None

def get_traffic_incidents(lat: float, lon: float, radius: float = 0.1):
    """Get traffic incidents near a point from TomTom."""
    if not TOMTOM_API_KEY:
        return []
    bbox = f"{lon-radius},{lat-radius},{lon+radius},{lat+radius}"
    url = (
        f"https://api.tomtom.com/traffic/services/5/incidentDetails"
        f"?bbox={bbox}&fields={{incidents{{type,geometry{{type,coordinates}},properties{{iconCategory,magnitudeOfDelay,events{{description,code,iconCategory}},startTime,endTime,from,to,length,delay,roadNumbers,timeValidity}}}}}}&language=en-GB&t=1111&key={TOMTOM_API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json().get("incidents", [])
    except Exception:
        return []

def traffic_color(current, free_flow):
    """Return a color based on congestion ratio."""
    try:
        ratio = current / free_flow
        if ratio >= 0.9:  return "green"
        if ratio >= 0.65: return "orange"
        return "red"
    except Exception:
        return "gray"

def build_map(center, zoom, markers=None, route_coords=None,
              show_traffic_layer=False, incidents=None, map_style="OpenStreetMap",
              accuracy_circle=None):

    stadia_url = "https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}{r}.png"
    if STADIA_API_KEY:
        stadia_url += f"?api_key={STADIA_API_KEY}"

    tile_options = {
        "OpenStreetMap":   ("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                            "© OpenStreetMap contributors"),
        "CartoDB Dark":    ("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
                            "© OpenStreetMap © CARTO"),
        "CartoDB Light":   ("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                            "© OpenStreetMap © CARTO"),
        "Stadia Terrain":  (stadia_url if STADIA_API_KEY else
                            "https://tile.opentopomap.org/{z}/{x}/{y}.png",
                            "© Stadia Maps © Stamen Design © OpenStreetMap" if STADIA_API_KEY else
                            "© OpenTopoMap (CC-BY-SA) © OpenStreetMap contributors"),
        "Satellite (Esri)":("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                            "© Esri © DigitalGlobe © GeoEye"),
    }

    tiles, attr = tile_options.get(map_style, tile_options["OpenStreetMap"])
    m = folium.Map(location=center, zoom_start=zoom, tiles=tiles, attr=attr)

    # Traffic tile overlay from TomTom
    if show_traffic_layer and TOMTOM_API_KEY:
        traffic_url = (
            f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/"
            f"{{z}}/{{x}}/{{y}}.png?key={TOMTOM_API_KEY}"
        )
        folium.TileLayer(
            tiles=traffic_url,
            attr="© TomTom",
            name="Traffic Flow",
            overlay=True,
            control=True,
            opacity=0.7,
        ).add_to(m)

    # Route polyline
    if route_coords:
        folium.PolyLine(route_coords, color="#1a73e8", weight=5, opacity=0.85).add_to(m)

    # Geolocation accuracy circle
    if accuracy_circle and accuracy_circle.get("radius_m"):
        folium.Circle(
            location=[accuracy_circle["lat"], accuracy_circle["lon"]],
            radius=accuracy_circle["radius_m"],
            color="#1a73e8",
            fill=True,
            fill_color="#1a73e8",
            fill_opacity=0.12,
            weight=1,
        ).add_to(m)

    # Markers
    for mk in (markers or []):
        icon_color = mk.get("color", "red")
        icon_name  = mk.get("icon",  "map-marker")
        popup_html = mk.get("popup", mk.get("label", ""))
        folium.Marker(
            location=[mk["lat"], mk["lon"]],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=mk.get("label", ""),
            icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
        ).add_to(m)

    # Traffic incidents
    for inc in (incidents or []):
        try:
            coords = inc["geometry"]["coordinates"]
            props  = inc.get("properties", {})
            events = props.get("events", [{}])
            desc   = events[0].get("description", "Incident") if events else "Incident"
            delay  = props.get("delay", 0)
            lat_i  = coords[1] if inc["geometry"]["type"] == "Point" else coords[0][1]
            lon_i  = coords[0] if inc["geometry"]["type"] == "Point" else coords[0][0]
            popup  = f"<b>⚠️ {desc}</b><br>Delay: {delay}s"
            folium.CircleMarker(
                location=[lat_i, lon_i],
                radius=8, color="orange", fill=True, fill_color="orange",
                popup=folium.Popup(popup, max_width=220),
                tooltip=desc,
            ).add_to(m)
        except Exception:
            continue

    folium.LayerControl().add_to(m)
    return m

# ── Session state defaults ────────────────────────────────────────────────────
defaults = {
    "center": [34.0, -117.2],   # Menifee, CA default
    "zoom": 12,
    "markers": [],
    "route_coords": None,
    "route_info": None,
    "traffic_data": None,
    "incidents": [],
    "active_tab": "Search",
    "location_accuracy": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Overall dark nav feel */
[data-testid="stSidebar"] {
    background: #1a1a2e;
    color: #e0e0e0;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown p {
    color: #e0e0e0 !important;
}
.main-title {
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(90deg, #1a73e8, #34a853);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.1rem;
}
.route-card {
    background: #f0f7ff;
    border-left: 4px solid #1a73e8;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
}
.traffic-card {
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
}
.traffic-green  { background:#e6f9ee; border-left:4px solid #34a853; }
.traffic-orange { background:#fff3e0; border-left:4px solid #fb8c00; }
.traffic-red    { background:#fce8e6; border-left:4px solid #ea4335; }

/* ── Fullscreen map ─────────────────────────────────────────────────────── */
.block-container {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    padding-left: 0rem !important;
    padding-right: 0rem !important;
    max-width: 100% !important;
}
header[data-testid="stHeader"] {
    height: 0px;
    display: none;
}
iframe {
    height: 100vh !important;
}
div[data-testid="stVerticalBlock"] > div:has(iframe) {
    height: 100vh !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="main-title">🗺️ Nova Maps</div>', unsafe_allow_html=True)
    st.caption("Powered by OSM · TomTom · ORS")
    st.divider()

    tab = st.radio(
        "Mode",
        ["Search", "Directions", "Traffic", "Layers"],
        index=["Search", "Directions", "Traffic", "Layers"].index(
            st.session_state.active_tab
        ),
    )
    st.session_state.active_tab = tab
    st.divider()

    # ── Search tab ──────────────────────────────────────────────────────────
    if tab == "Search":
        st.subheader("🔍 Search Location")
        search_query = st.text_input("Enter address or place", placeholder="e.g. Eiffel Tower, Paris")
        col1, col2 = st.columns(2)
        search_btn = col1.button("Search", use_container_width=True, type="primary")
        clear_btn  = col2.button("Clear",  use_container_width=True)

        if clear_btn:
            st.session_state.markers = []
            st.session_state.route_coords = None
            st.session_state.route_info = None
            st.session_state.traffic_data = None
            st.session_state.incidents = []
            st.rerun()

        if search_btn and search_query:
            result = geocode(search_query)
            if result:
                lat, lon, name = result
                st.session_state.center = [lat, lon]
                st.session_state.zoom   = 15
                st.session_state.markers = [{
                    "lat": lat, "lon": lon,
                    "label": name[:60],
                    "popup": f"<b>{name}</b><br>📍 {lat:.5f}, {lon:.5f}",
                    "color": "blue", "icon": "map-marker",
                }]
                st.success(f"Found: {name[:80]}")
            else:
                st.error("Location not found. Try a more specific address.")

        st.divider()
        st.caption("Or use your current location:")
        location = streamlit_geolocation()

        if location and location.get("latitude"):
            loc_lat, loc_lon = location["latitude"], location["longitude"]
            accuracy = location.get("accuracy")
            st.session_state.center = [loc_lat, loc_lon]
            st.session_state.zoom   = 15
            st.session_state.markers = [{
                "lat": loc_lat, "lon": loc_lon,
                "label": "My Location",
                "popup": f"<b>📍 You are here</b><br>{loc_lat:.5f}, {loc_lon:.5f}"
                         + (f"<br>Accuracy: ±{accuracy:.0f} m" if accuracy else ""),
                "color": "blue", "icon": "user",
            }]
            st.session_state.location_accuracy = {
                "lat": loc_lat, "lon": loc_lon, "radius_m": accuracy
            } if accuracy else None
            if accuracy:
                st.success(f"Located you at {loc_lat:.5f}, {loc_lon:.5f} (±{accuracy:.0f} m)")
                if accuracy > 200:
                    st.caption("⚠️ Low precision — likely Wi-Fi/IP-based location (common on desktop). Try on a phone with GPS/location services on for a tighter fix.")
            else:
                st.success(f"Located you at {loc_lat:.5f}, {loc_lon:.5f}")

    # ── Directions tab ──────────────────────────────────────────────────────
    elif tab == "Directions":
        st.subheader("🧭 Get Directions")
        origin_input = st.text_input("From", placeholder="Start address")
        dest_input   = st.text_input("To",   placeholder="Destination address")
        mode = st.selectbox("Travel mode", ["car", "walk", "bike"],
                            format_func=lambda x: {"car":"🚗 Drive","walk":"🚶 Walk","bike":"🚲 Bike"}[x])

        if st.button("Get Directions", type="primary", use_container_width=True):
            if origin_input and dest_input:
                with st.spinner("Calculating route…"):
                    orig = geocode(origin_input)
                    dest = geocode(dest_input)
                    if orig and dest:
                        o_lat, o_lon, o_name = orig
                        d_lat, d_lon, d_name = dest
                        route_coords, info = get_route((o_lat, o_lon), (d_lat, d_lon), mode)
                        st.session_state.markers = [
                            {"lat": o_lat, "lon": o_lon, "label": "Start",
                             "popup": f"<b>🟢 Start</b><br>{o_name[:80]}",
                             "color": "green", "icon": "play"},
                            {"lat": d_lat, "lon": d_lon, "label": "End",
                             "popup": f"<b>🔴 End</b><br>{d_name[:80]}",
                             "color": "red", "icon": "flag"},
                        ]
                        st.session_state.route_coords = route_coords
                        st.session_state.route_info   = info
                        mid = [(o_lat + d_lat) / 2, (o_lon + d_lon) / 2]
                        st.session_state.center = mid
                        st.session_state.zoom   = 12
                        if info:
                            st.markdown(f"""
                            <div class="route-card">
                            🛣️ <b>{info['distance_km']} km</b> &nbsp;|&nbsp;
                            ⏱️ <b>{info['duration_min']} min</b>
                            </div>""", unsafe_allow_html=True)
                    else:
                        st.error("Could not geocode one or both addresses.")
            else:
                st.warning("Please enter both origin and destination.")

        if not ORS_API_KEY:
            st.info("💡 Add an ORS API key in secrets for turn-by-turn routing.")

    # ── Traffic tab ─────────────────────────────────────────────────────────
    elif tab == "Traffic":
        st.subheader("🚦 Traffic Info")
        traffic_loc = st.text_input("Check traffic near", placeholder="Address or place")

        col1, col2 = st.columns(2)
        show_layer = col1.checkbox("Show traffic layer", value=True)
        show_incidents = col2.checkbox("Show incidents", value=True)

        if st.button("Get Traffic", type="primary", use_container_width=True):
            if traffic_loc:
                result = geocode(traffic_loc)
                if result:
                    lat, lon, name = result
                    st.session_state.center = [lat, lon]
                    st.session_state.zoom   = 14
                    with st.spinner("Fetching traffic data…"):
                        tf = get_traffic_flow(lat, lon)
                        incidents = get_traffic_incidents(lat, lon) if show_incidents else []
                        st.session_state.traffic_data = tf
                        st.session_state.incidents    = incidents
                    if tf:
                        color = traffic_color(tf["current_speed"], tf["free_flow_speed"])
                        emoji = {"green": "🟢", "orange": "🟡", "red": "🔴"}.get(color, "⚪")
                        st.markdown(f"""
                        <div class="traffic-card traffic-{color}">
                        {emoji} <b>Current speed:</b> {tf['current_speed']} km/h<br>
                        🏁 <b>Free-flow speed:</b> {tf['free_flow_speed']} km/h<br>
                        📊 <b>Confidence:</b> {tf['confidence']}<br>
                        🚧 <b>Road closure:</b> {'Yes ⚠️' if tf['road_closure'] else 'No'}
                        </div>""", unsafe_allow_html=True)
                    else:
                        if not TOMTOM_API_KEY:
                            st.info("Add a TomTom API key in secrets to see live traffic.")
                    if incidents:
                        st.warning(f"⚠️ {len(incidents)} incident(s) near this area.")
                else:
                    st.error("Location not found.")
            else:
                st.warning("Enter a location to check traffic.")

        st.session_state["show_traffic_layer"] = show_layer

    # ── Layers tab ──────────────────────────────────────────────────────────
    elif tab == "Layers":
        st.subheader("🗂️ Map Style")
        map_style = st.selectbox("Base layer", [
            "OpenStreetMap", "CartoDB Dark", "CartoDB Light",
            "Stadia Terrain", "Satellite (Esri)",
        ])
        st.session_state["map_style"] = map_style
        st.info("Switch between map styles instantly. Satellite imagery via Esri.")
        if map_style == "Stadia Terrain":
            if STADIA_API_KEY:
                st.caption("✅ Using Stadia Maps terrain tiles (API key configured).")
            else:
                st.caption("ℹ️ No Stadia API key set — using OpenTopoMap (free, no key needed) as the terrain source instead. Add a `STADIA_API_KEY` in secrets for Stadia's tiles.")

    # ── API key status ───────────────────────────────────────────────────────
    st.divider()
    with st.expander("🔑 API Key Status"):
        st.markdown(
            f"**TomTom:** {'✅ Connected' if TOMTOM_API_KEY else '❌ Not set'}\n\n"
            f"**OpenRouteService:** {'✅ Connected' if ORS_API_KEY else '❌ Not set'}\n\n"
            f"**Stadia Maps:** {'✅ Connected' if STADIA_API_KEY else '⚪ Not set (using free OpenTopoMap fallback)'}"
        )
        st.caption("Set keys in `.streamlit/secrets.toml` or environment variables.")

# ── Main map area ─────────────────────────────────────────────────────────────
show_traffic = st.session_state.get("show_traffic_layer", False) and tab == "Traffic"
style        = st.session_state.get("map_style", "OpenStreetMap")

m = build_map(
    center=st.session_state.center,
    zoom=st.session_state.zoom,
    markers=st.session_state.markers,
    route_coords=st.session_state.route_coords,
    show_traffic_layer=show_traffic,
    incidents=st.session_state.incidents if tab == "Traffic" else [],
    map_style=style,
    accuracy_circle=st.session_state.get("location_accuracy") if tab == "Search" else None,
)

map_data = st_folium(m, use_container_width=True, height=1000, returned_objects=["last_clicked"])

# ── Click-to-explore ──────────────────────────────────────────────────────────
if map_data and map_data.get("last_clicked"):
    click_lat = map_data["last_clicked"]["lat"]
    click_lon = map_data["last_clicked"]["lng"]
    with st.expander(f"📍 Clicked: {click_lat:.5f}, {click_lon:.5f}", expanded=True):
        col1, col2, col3 = st.columns(3)
        if col1.button("Set as Origin"):
            st.session_state.active_tab = "Directions"
            st.rerun()
        if col2.button("Traffic here") and TOMTOM_API_KEY:
            tf = get_traffic_flow(click_lat, click_lon)
            if tf:
                color = traffic_color(tf["current_speed"], tf["free_flow_speed"])
                emoji = {"green": "🟢", "orange": "🟡", "red": "🔴"}.get(color, "⚪")
                st.markdown(
                    f"{emoji} Speed: **{tf['current_speed']}** / {tf['free_flow_speed']} km/h &nbsp; "
                    f"| Closure: {'⚠️ Yes' if tf['road_closure'] else 'No'}"
                )
        if col3.button("Drop pin here"):
            st.session_state.markers.append({
                "lat": click_lat, "lon": click_lon,
                "label": f"Pin {click_lat:.3f},{click_lon:.3f}",
                "popup": f"📍 {click_lat:.5f}, {click_lon:.5f}",
                "color": "red", "icon": "map-pin",
            })
            st.rerun()

# ── Route summary (bottom) ────────────────────────────────────────────────────
if st.session_state.route_info and tab == "Directions":
    info = st.session_state.route_info
    st.markdown(f"""
    <div class="route-card">
    🛣️ &nbsp;<b>Distance:</b> {info['distance_km']} km &nbsp;&nbsp;
    ⏱️ &nbsp;<b>Est. time:</b> {info['duration_min']} min
    </div>""", unsafe_allow_html=True)

# ── MrBunny assistant widget (loaded from its own file) ───────────────────────
try:
    with open("mrbunny_widget.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=1, width=1)
except FileNotFoundError:
    pass  # widget file not present; app still works fine without it
