# 🗺️ Nova Maps

A full-featured Google Maps alternative built with Streamlit, Folium, OpenStreetMap, TomTom, and OpenRouteService.

---

## ✨ Features

| Feature | Provider | Free Tier |
|---|---|---|
| Interactive map | Folium + OpenStreetMap | ✅ Unlimited |
| Geocoding / Address search | Nominatim (OSM) | ✅ Unlimited |
| Place / POI search | TomTom Search API | ✅ 2,500 req/day |
| Turn-by-turn directions | OpenRouteService | ✅ 2,000 req/day |
| Live traffic flow | TomTom Traffic API | ✅ 2,500 req/day |
| Traffic incidents | TomTom Incidents API | ✅ 2,500 req/day |
| Traffic map overlay | TomTom Tile API | ✅ 2,500 req/day |
| Satellite imagery | Esri World Imagery | ✅ Unlimited |
| Multiple map styles | CartoDB, Stadia, OSM | ✅ Unlimited |

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/Nova Maps.git
cd Nova Maps
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add API keys
Edit `.streamlit/secrets.toml`:
```toml
TOMTOM_API_KEY = "your_tomtom_key_here"
ORS_API_KEY    = "your_ors_key_here"
```

**Get free API keys:**
- **TomTom** (traffic + places): https://developer.tomtom.com → Create app → Copy key
- **OpenRouteService** (directions): https://openrouteservice.org/dev/#/signup → Copy token

### 4. Run the app
```bash
streamlit run app.py
```

---

## ☁️ Deploy to Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to https://share.streamlit.io
3. Click **New app** → select your repo → `app.py`
4. Under **Advanced settings → Secrets**, paste:
```toml
TOMTOM_API_KEY = "your_tomtom_key_here"
ORS_API_KEY    = "your_ors_key_here"
```
5. Click **Deploy** — your app will be live at a public URL!

---

## 🗂️ Project Structure

```
Nova Maps/
├── app.py                  # Main Streamlit app
├── requirements.txt        # Python dependencies
├── README.md
└── .streamlit/
    ├── config.toml         # Theme and server config
    └── secrets.toml        # API keys (DO NOT commit this!)
```

---

## 🔐 Security Note

Add `.streamlit/secrets.toml` to your `.gitignore` to avoid leaking API keys:
```
echo ".streamlit/secrets.toml" >> .gitignore
```

---

## 🛣️ Roadmap Ideas

- [ ] Saved favorites / bookmarks
- [ ] Share route via URL
- [ ] Street View embed (Google Maps Embed API)
- [ ] ETA with live traffic factored in (TomTom Routing API)
- [ ] Multi-stop route planning
- [ ] User login with saved history
