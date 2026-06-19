import streamlit as st
import pandas as pd
import geopandas as gpd
from typing import Dict, Optional, Tuple, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# PAGE CONFIGURATION & MINIMALIST DESIGN
# ============================================================================
st.set_page_config(
    page_title="Coordinate & Elevation Suite",
    page_icon="⟠",
    layout="centered"
)

st.markdown("""
    <style>
        /* Minimalist Modern Theme */
        .main { background-color: #FAFAFA; }
        h1 { color: #111827; font-weight: 800; font-size: 2.2rem; letter-spacing: -0.025em; margin-bottom: 0rem; }
        p.subtitle { color: #6B7280; font-size: 1.1rem; margin-bottom: 2rem; }
        .stSelectbox label, .stRadio label { font-weight: 600; color: #374151; }
        .stTabs [data-baseweb="tab-list"] { gap: 2rem; }
        .stTabs [data-baseweb="tab"] { height: 3.5rem; white-space: pre-wrap; background-color: transparent; }
        .stTabs [aria-selected="true"] { color: #2563EB !important; border-bottom: 2px solid #2563EB !important; }
        hr { border-color: #E5E7EB; }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA LOAD & SETUP
# ============================================================================
@st.cache_data
def load_county_epsg_codes() -> Dict[str, int]:
    """Load Indiana County EPSG codes robustly from CSV file"""
    try:
        df = pd.read_csv('indiana_county_epsg.csv')
        df.columns = df.columns.str.strip()
        epsg_dict = {}
        for _, row in df.iterrows():
            county = str(row['County']).strip().upper()
            code = str(row['EPSG_Code']).strip()
            if code.replace('.','',1).isdigit():
                epsg_dict[county] = int(float(code))
        return epsg_dict
    except Exception as e:
        st.error(f"Error loading indiana_county_epsg.csv: {e}")
        return {}

INDIANA_COUNTY_EPSG = load_county_epsg_codes()

def get_robust_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# ============================================================================
# CORE FUNCTIONS
# ============================================================================
def fetch_elevation_usgs(lat: float, lon: float, session: requests.Session) -> Optional[float]:
    """Reliable USGS EPQS Elevation fetcher."""
    try:
        url = f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Feet&wkid=4326&includeDate=false"
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            val = resp.json().get('value')
            if val is not None and str(val).strip() != '' and str(val).lower() != 'nodata':
                return round(float(val), 2)
    except:
        pass
    return None

def latlon_to_county(lat: float, lon: float, epsg: int) -> Tuple[Optional[float], Optional[float]]:
    try:
        gdf = gpd.GeoDataFrame([1], geometry=gpd.points_from_xy([lon], [lat]), crs='EPSG:4326')
        gdf_proj = gdf.to_crs(f'EPSG:{epsg}')
        return round(gdf_proj.geometry.x.iloc[0], 3), round(gdf_proj.geometry.y.iloc[0], 3)
    except:
        return None, None

def county_to_latlon(easting: float, northing: float, epsg: int) -> Tuple[Optional[float], Optional[float]]:
    try:
        gdf = gpd.GeoDataFrame([1], geometry=gpd.points_from_xy([easting], [northing]), crs=f'EPSG:{epsg}')
        gdf_wgs = gdf.to_crs('EPSG:4326')
        return round(gdf_wgs.geometry.y.iloc[0], 6), round(gdf_wgs.geometry.x.iloc[0], 6)
    except:
        return None, None

# ============================================================================
# BATCH PROCESSOR
# ============================================================================
def process_dataframe(df: pd.DataFrame, operation: str, epsg: Optional[int] = None) -> pd.DataFrame:
    out_df = df.copy()
    session = get_robust_session()
    
    # Identify Coordinate Columns dynamically
    cols = [c.lower() for c in df.columns]
    lat_col = df.columns[[i for i, c in enumerate(cols) if 'lat' in c]][0] if any('lat' in c for c in cols) else None
    lon_col = df.columns[[i for i, c in enumerate(cols) if 'lon' in c]][0] if any('lon' in c for c in cols) else None
    east_col = df.columns[[i for i, c in enumerate(cols) if 'east' in c or 'x' == c]][0] if any('east' in c or 'x' == c for c in cols) else None
    north_col = df.columns[[i for i, c in enumerate(cols) if 'north' in c or 'y' == c]][0] if any('north' in c or 'y' == c for c in cols) else None

    with st.spinner("Processing data..."):
        # Task 1: Elevation Only
        if operation == "Elevation Only (USA Coverage)":
            points = list(zip(df[lat_col], df[lon_col]))
            with ThreadPoolExecutor(max_workers=5) as executor:
                elevs = list(executor.map(lambda p: fetch_elevation_usgs(p[0], p[1], session), points))
            out_df['Elevation_Feet'] = elevs

        # Task 2: Lat/Lon -> Indiana
        elif operation == "Lat/Lon ➔ Indiana County":
            eastings, northings = [], []
            for _, row in df.iterrows():
                e, n = latlon_to_county(row[lat_col], row[lon_col], epsg)
                eastings.append(e); northings.append(n)
            out_df['Easting_ft'] = eastings
            out_df['Northing_ft'] = northings

        # Task 3: Indiana -> Lat/Lon
        elif operation == "Indiana County ➔ Lat/Lon":
            lats, lons = [], []
            for _, row in df.iterrows():
                lat, lon = county_to_latlon(row[east_col], row[north_col], epsg)
                lats.append(lat); lons.append(lon)
            out_df['Latitude_WGS84'] = lats
            out_df['Longitude_WGS84'] = lons

        # Task 4: Lat/Lon -> Indiana + Elevation
        elif operation == "Lat/Lon ➔ Indiana County + Elevation":
            eastings, northings = [], []
            for _, row in df.iterrows():
                e, n = latlon_to_county(row[lat_col], row[lon_col], epsg)
                eastings.append(e); northings.append(n)
            out_df['Easting_ft'] = eastings
            out_df['Northing_ft'] = northings
            
            points = list(zip(df[lat_col], df[lon_col]))
            with ThreadPoolExecutor(max_workers=5) as executor:
                elevs = list(executor.map(lambda p: fetch_elevation_usgs(p[0], p[1], session), points))
            out_df['Elevation_Feet'] = elevs

    return out_df

# ============================================================================
# MAIN UI
# ============================================================================
def main():
    st.markdown("<h1>Spatial Operations Suite</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Precise Coordinate & Elevation Workflows</p>", unsafe_allow_html=True)
    
    if not INDIANA_COUNTY_EPSG:
        st.error("Error: Please ensure indiana_county_epsg.csv is loaded correctly.")
        return

    # --- OPERATION SELECTION ---
    operations = [
        "Elevation Only (USA Coverage)",
        "Lat/Lon ➔ Indiana County",
        "Indiana County ➔ Lat/Lon",
        "Lat/Lon ➔ Indiana County + Elevation"
    ]
    selected_operation = st.selectbox("Select Operation", operations)
    
    # --- COUNTY SELECTION (If applicable) ---
    selected_county = None
    epsg_code = None
    if "Indiana" in selected_operation:
        selected_county = st.selectbox("Select Target County (Applies to all points)", sorted(INDIANA_COUNTY_EPSG.keys()))
        epsg_code = INDIANA_COUNTY_EPSG[selected_county]
        st.caption(f"EPSG Code: {epsg_code}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # --- INPUT METHODS (TABS) ---
    tab1, tab2 = st.tabs(["✍️ Manual Entry", "📁 Batch Processing (CSV)"])

    # TAB 1: MANUAL ENTRY
    with tab1:
        st.write("Enter single point coordinates below:")
        col1, col2 = st.columns(2)
        
        # Determine inputs based on operation
        if selected_operation == "Indiana County ➔ Lat/Lon":
            with col1:
                easting = st.number_input("Easting (X)", value=0.0, format="%.3f")
            with col2:
                northing = st.number_input("Northing (Y)", value=0.0, format="%.3f")
            
            if st.button("Process Point", type="primary", use_container_width=True):
                if easting != 0.0 or northing != 0.0:
                    df_in = pd.DataFrame({'Easting': [easting], 'Northing': [northing]})
                    res = process_dataframe(df_in, selected_operation, epsg_code)
                    st.success("Transformation Complete")
                    st.dataframe(res, use_container_width=True)
        
        else:
            with col1:
                lat = st.number_input("Latitude", value=39.7684, format="%.6f")
            with col2:
                lon = st.number_input("Longitude", value=-86.1581, format="%.6f")
                
            if st.button("Process Point", type="primary", use_container_width=True):
                if lat != 0.0 or lon != 0.0:
                    df_in = pd.DataFrame({'Latitude': [lat], 'Longitude': [lon]})
                    res = process_dataframe(df_in, selected_operation, epsg_code)
                    st.success("Task Complete")
                    st.dataframe(res, use_container_width=True)

    # TAB 2: CSV UPLOAD
    with tab2:
        st.write("Upload a CSV file for bulk processing.")
        
        # Provide appropriate template
        if selected_operation == "Indiana County ➔ Lat/Lon":
            st.info("Required CSV columns: 'Easting' and 'Northing' (or 'X' and 'Y').")
            template_df = pd.DataFrame({'Point_ID': [1, 2], 'Easting': [200000, 200500], 'Northing': [150000, 150500]})
        else:
            st.info("Required CSV columns: 'Latitude' and 'Longitude' (or 'Lat' and 'Lon').")
            template_df = pd.DataFrame({'Point_ID': [1, 2], 'Latitude': [39.7684, 40.4431], 'Longitude': [-86.1581, -85.3524]})
            
        st.download_button("Download CSV Template", data=template_df.to_csv(index=False), file_name="template.csv", mime="text/csv")
        
        uploaded_file = st.file_uploader("Upload Data", type=['csv'], label_visibility="collapsed")
        
        if uploaded_file is not None:
            df_upload = pd.read_csv(uploaded_file)
            st.write("Preview:")
            st.dataframe(df_upload.head(3), use_container_width=True)
            
            if st.button("Process Batch File", type="primary", use_container_width=True):
                res_batch = process_dataframe(df_upload, selected_operation, epsg_code)
                st.success(f"Successfully processed {len(res_batch)} points.")
                st.dataframe(res_batch, use_container_width=True)
                
                st.download_button(
                    label="Download Results",
                    data=res_batch.to_csv(index=False),
                    file_name="processed_spatial_data.csv",
                    mime="text/csv",
                    type="secondary",
                    use_container_width=True
                )

if __name__ == "__main__":
    main()
