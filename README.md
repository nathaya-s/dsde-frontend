## **Overview**

This project provides an interactive visualization platform for Bangkok city data, integrating:

* Traffy Fongdue complaints 
* CCTV map layer
* BMA news
* Incident map
* District performance metrics
* flood risk map
* Police station locations
* Population choropleth by district
* Summary charts

The dashboard is built with **Streamlit**, **Folium**, **Altair**, and **Plotly**.

---

## **Installation**

1. Clone the repository:

```bash
git clone https://github.com/nathaya-s/dsde-frontend.git
cd dsde-frontend
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## **Configuration (Secrets / Environment Variables)**

The app uses **Streamlit secrets** to store sensitive information. Create a `secrets.toml` file in `.streamlit/`:

```toml
# .streamlit/secrets.toml

MAPBOX_API_KEY = "your_mapbox_api_key"

PG_HOST = "localhost"
PG_PORT = "5432"
PG_DB   = "your_db_name"
PG_USER = "your_db_user"
PG_PASS = "your_db_password"
PG_SSLMODE = "require"  # or "" if not using SSL

SNAPSHOT_BASE = "http://127.0.0.1:9000/snapshot"
API_URL = "http://your_api_url"
```

**Usage in code**:

```python
MAPBOX_API_KEY = st.secrets["MAPBOX_API_KEY"]
PG_HOST = st.secrets.get("PG_HOST", "localhost")
PG_PORT = st.secrets.get("PG_PORT", "5432")
PG_DB   = st.secrets.get("PG_DB")
PG_USER = st.secrets.get("PG_USER")
PG_PASS = st.secrets.get("PG_PASS")
PG_SSL  = st.secrets.get("PG_SSLMODE")  
SNAPSHOT_BASE = st.secrets.get("SNAPSHOT_BASE", "http://127.0.0.1:9000/snapshot")
API_URL = st.secrets.get("API_URL")
```

---

## **Running the App**

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

---

## **Dependencies**

* Python >= 3.10
* Streamlit
* pandas, numpy
* altair, plotly
* folium, streamlit-folium
* psycopg2-binary
* requests

(See `requirements.txt` for full versions)

---

## **Project Structure**

```
project-name/
│
├─ app.py                 # Main Streamlit app
├─ db_utils.py            # Database helper functions
├─ model_api.py
├─ requirements.txt       # Python dependencies
├─ .streamlit/
│   └─ secrets.toml       # API keys and DB credentials
├─ data/                  # flood_risk.csv
```

---